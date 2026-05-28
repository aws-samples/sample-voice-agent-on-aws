import logging
import os
import traceback
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect
from opentelemetry import baggage, context, trace

from strands.experimental.bidi.agent import BidiAgent
from strands.experimental.bidi.models.nova_sonic import BidiNovaSonicModel

# Import tools
from tools import get_current_time, get_weather

# All available in-app tools by name
AVAILABLE_TOOLS = {
    "get_current_time": get_current_time,
    "get_weather": get_weather,
}

# Profile definitions: maps profile name → system_prompt + tools
PROFILES = {
    "General Assistant": {
        "system_prompt": "You are a friendly and helpful general-purpose assistant. Answer questions clearly and concisely. Be conversational and natural in your responses. You have access to a get_current_time tool for time-related questions and a get_weather tool for weather inquiries. When the user asks about weather, always say something like 'Hold on while I check the weather for you, this might take a moment' BEFORE calling the get_weather tool, because it takes about 15 seconds to complete.",
        "tools": ["get_current_time", "get_weather"],
        "gateway_arns": [],
    },
    "Finance Agent": {
        "system_prompt": (
            "You are a friendly, chatty customer service assistant for Any Bank. "
            "Keep responses short and conversational — one to two sentences max. "
            "Sound like a helpful colleague, not a system reading data.\n\n"
            "GREETING:\n"
            "- When the conversation starts, immediately say: 'Welcome to Any Bank! I'm here to help with your banking needs. What can I do for you today?'\n"
            "- Do NOT wait for the user to speak first. Greet them proactively.\n\n"
            "RULES:\n"
            "- Never mention tool names, function names, or parameters aloud. "
            "Never say things like 'authenticate_user' or 'get_account_balance'.\n"
            "- Never read out JSON, IDs, or technical details. Summarize naturally.\n"
            "- Convert account numbers to spoken digits: '12345' becomes 'one two three four five'.\n"
            "- Speak dates naturally: 'January first, nineteen ninety' not '1990-01-01'.\n\n"
            "TOOL RESULTS:\n"
            "- When you call a tool and receive a result, IMMEDIATELY share the answer with the user.\n"
            "- Do NOT wait for the user to ask again. Speak the result right away.\n"
            "- Do NOT say 'let me check' or 'just a moment' and then go silent. "
            "If you say you're checking, you MUST follow up with the answer in the same turn.\n\n"
            "AUTHENTICATION:\n"
            "- Greet the user warmly and ask for their name.\n"
            "- For account-specific questions (balance, transactions, transfers), "
            "ask for account ID and date of birth ONCE. After verified, never ask again in this session.\n"
            "- For general questions (FAQ, mortgage rates, bank policies), NO authentication needed.\n\n"
            "AFTER AUTHENTICATION:\n"
            "- Help with balances, transactions, transfers, mortgage info, and general FAQ.\n"
            "- Summarize results briefly: 'Your balance is fifteen thousand two hundred dollars.'\n"
            "- After helping, ask: 'Anything else I can help with?'\n\n"
            "SCOPE:\n"
            "- Banking and mortgage topics only.\n"
            "- Out of scope: 'Sorry, I can only help with banking questions.'"
        ),
        "tools": ["mcp"],
        "gateway_arns": [],
    }
}


# Import hooks - may not be available in all versions
try:
    from strands.experimental.bidi.hooks.events import BidiMessageAddedEvent
    HOOKS_AVAILABLE = True
except ImportError:
    try:
        from strands.experimental.hooks.events import BidiMessageAddedEvent
        HOOKS_AVAILABLE = True
    except ImportError:
        HOOKS_AVAILABLE = False
        BidiMessageAddedEvent = None

# Import hook events for tool call interception
try:
    from strands.experimental.hooks.events import BidiBeforeToolCallEvent, BidiAfterToolCallEvent
    from strands.hooks import HookProvider
    TOOL_HOOKS_AVAILABLE = True
except ImportError:
    TOOL_HOOKS_AVAILABLE = False
    BidiBeforeToolCallEvent = None
    BidiAfterToolCallEvent = None
    HookProvider = None

# Import memory - may not be available if bedrock-agentcore not installed
try:
    from memory import VoiceAgentMemory
    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False
    VoiceAgentMemory = None

logger = logging.getLogger(__name__)

# Get tracer for custom spans
tracer = trace.get_tracer(__name__)


DEFAULT_SYSTEM_PROMPT = '''You are a friendly companion having a casual chat. Be warm, conversational, and natural. Keep responses concise and engaging.'''


def get_system_prompt() -> str:
    """Get the default system prompt for the banking assistant."""
    return DEFAULT_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Memory Hook
# ---------------------------------------------------------------------------

class MemoryHook:
    """BidiAgent hook that stores conversation turns to AgentCore Memory.
    
    Only functional when the hooks API is available in the installed strands version.
    """

    def __init__(self, memory: VoiceAgentMemory, actor_id: str, session_id: str):
        self.memory = memory
        self.actor_id = actor_id
        self.session_id = session_id

    async def on_message_added(self, event):
        """Store each conversation turn to memory as it happens."""
        message = event.message if hasattr(event, 'message') else {}
        role = message.get("role", "")
        if role not in ("user", "assistant"):
            return

        for block in message.get("content", []):
            if "text" in block and block["text"].strip():
                self.memory.store_turn(
                    self.actor_id, self.session_id, role, block["text"]
                )


# ---------------------------------------------------------------------------
# MCP Tool Pass-Through Hook
# ---------------------------------------------------------------------------

class MCPToolPassThroughHook:
    """Hook that cancels local tool execution for MCP gateway tools.
    
    When the agent is configured with MCP gateways, tool calls are handled by
    AgentCore's runtime infrastructure. This hook prevents the BidiAgent from
    trying to execute those tools locally (which would fail with 'Unknown tool'
    and send an error result back to the model, breaking the conversation).
    
    The ToolUseStreamEvent is still forwarded to the client for display before
    this hook fires, so the client sees tool activity.
    """

    def __init__(self, mcp_tool_names: set = None):
        """Initialize with optional set of known MCP tool names.
        
        Args:
            mcp_tool_names: Set of tool names handled by MCP gateways.
                           If None, ALL unknown tools are treated as MCP tools.
        """
        self.mcp_tool_names = mcp_tool_names or set()
        self._is_catch_all = mcp_tool_names is None

    def register_hooks(self, registry, **kwargs):
        """Register the before_tool_call callback with the hook registry."""
        try:
            from strands.experimental.hooks.events import BidiBeforeToolCallEvent, BidiAfterToolCallEvent
            registry.add_callback(BidiBeforeToolCallEvent, self._on_before_tool_call)
            registry.add_callback(BidiAfterToolCallEvent, self._on_after_tool_call)
            logger.info("   ✅ MCPToolPassThroughHook registered BidiBeforeToolCallEvent + BidiAfterToolCallEvent callbacks")
        except (ImportError, Exception) as e:
            logger.warning(f"   ⚠️ MCPToolPassThroughHook could not register: {e}")

    async def _on_before_tool_call(self, event):
        """Cancel local execution for MCP gateway tools."""
        tool_use = event.tool_use
        tool_name = tool_use.get("name", "")
        
        # If no local tool is found (selected_tool is None), it's an MCP tool
        if event.selected_tool is None:
            logger.info(f"🔧 [MCP] Tool '{tool_name}' not in local registry - handled by AgentCore gateway, skipping local execution")
            event.cancel_tool = f"Tool result provided by AgentCore MCP gateway"
            return

        # Check against known MCP tool names
        if self.mcp_tool_names and tool_name in self.mcp_tool_names:
            logger.info(f"🔧 [MCP] Tool '{tool_name}' is a known MCP tool - skipping local execution")
            event.cancel_tool = f"Tool result provided by AgentCore MCP gateway"

    async def _on_after_tool_call(self, event):
        """Rewrite cancelled MCP tool results to success status.
        
        When a tool is cancelled because it's an MCP gateway tool, the SDK creates
        an error result. We rewrite it to success so the model doesn't get confused.
        """
        if event.cancel_message and "AgentCore MCP gateway" in event.cancel_message:
            # Rewrite the result status from error to success
            event.result = {
                "toolUseId": event.result["toolUseId"],
                "status": "success",
                "content": [{"text": "Tool executed successfully via MCP gateway."}],
            }
            logger.info(f"🔧 [MCP] Rewrote tool result to success for '{event.tool_use.get('name', 'unknown')}'")


# ---------------------------------------------------------------------------
# Session Handler
# ---------------------------------------------------------------------------

async def handle_websocket_session(
    websocket: WebSocket,
    default_gateway_arns: list,
    send_output=None,
    memory: Optional[VoiceAgentMemory] = None,
):
    """
    Handle a WebSocket session: wait for config event, initialize agent, and run.

    Args:
        websocket: The accepted WebSocket connection.
        default_gateway_arns: Gateway ARNs from environment (used as fallback).
        send_output: Optional async callable for sending output events. Defaults to websocket.send_json.
        memory: Optional VoiceAgentMemory instance for conversation persistence.
    """
    agent = None
    output_fn = send_output or websocket.send_json

    logger.info(f"Connection from {websocket.client}")
    logger.info(f"⏳ Waiting for config event from client...")

    try:
        # Wait for initial config event
        config = await _wait_for_config(websocket)
        if config is None:
            return

        # Handle memory: load history if enabled
        history_messages = []
        memory_enabled = config.get("memory_enabled", False) and memory is not None
        actor_id = config.get("actor_id", "")
        session_id = config.get("session_id", "")

        if memory_enabled and actor_id:
            if not session_id:
                session_id = memory.generate_session_id()
                logger.info(f"🧠 Generated new session ID: {session_id}")

            logger.info(f"🧠 Memory enabled: actor={actor_id}, session={session_id}")
            logger.info(f"🧠 Loading chat history from memory...")
            
            # Run synchronous memory load in a thread to avoid blocking the event loop
            import asyncio
            loop = asyncio.get_event_loop()
            history_messages = await loop.run_in_executor(None, memory.load_history, actor_id, session_id)
            logger.info(f"🧠 Loaded {len(history_messages)} turns from memory")

            # Send history to client for display
            if history_messages:
                history_turns = []
                for msg in history_messages:
                    text_parts = [b["text"] for b in msg.get("content", []) if "text" in b]
                    if text_parts:
                        history_turns.append({
                            "role": msg["role"],
                            "content": " ".join(text_parts),
                        })

                await output_fn({
                    "type": "memory_history",
                    "turns": history_turns,
                    "session_id": session_id,
                    "message": f"Loaded {len(history_turns)} turns from previous conversation",
                })
            else:
                await output_fn({
                    "type": "memory_history",
                    "turns": [],
                    "session_id": session_id,
                    "message": "No previous conversation history found",
                })

        # Initialize agent from config
        # If we have history, inject it into the system prompt as context
        effective_system_prompt = config.get("system_prompt") or get_system_prompt()
        if history_messages:
            history_text = "\n\nPrevious conversation context:\n"
            for msg in history_messages:
                role = msg.get("role", "unknown")
                text_parts = [b["text"] for b in msg.get("content", []) if "text" in b]
                if text_parts:
                    history_text += f"  {role}: {' '.join(text_parts)}\n"
            history_text += "\nContinue the conversation naturally, referencing the above context when relevant."
            effective_system_prompt = effective_system_prompt + history_text
            logger.info(f"🧠 Injected {len(history_messages)} turns into system prompt as context")

        config["system_prompt"] = effective_system_prompt
        agent = _create_agent(config, default_gateway_arns)
        logger.info(f"✅ Agent initialized successfully")
        logger.info(f"   Config: model={config['model_id']}, region={config['region']}, voice={config['voice']}, audio={config['input_rate']}Hz/{config['output_rate']}Hz")
        if memory_enabled:
            logger.info(f"   Memory: enabled (actor={actor_id}, session={session_id}, history={len(history_messages)} turns)")

        # Send acknowledgment back to client
        await output_fn({
            "type": "system",
            "message": f"Configuration applied: {config['model_id']} with voice={config['voice']}, region={config['region']}",
            "memory_available": memory is not None,
            "memory_enabled": memory_enabled,
            "session_id": session_id if memory_enabled else None,
        })

        # Define input handler
        async def handle_websocket_input():
            """Handle incoming messages from the client, filtering config, text, and audio."""
            while True:
                message = await websocket.receive_json()

                # Handle subsequent config events (not allowed after initialization)
                if message.get("type") == "config":
                    logger.info(f"⚠️ Config event received after initialization - ignoring")
                    await websocket.send_json({
                        "type": "system",
                        "message": "Configuration can only be set once per session. Please reconnect to change settings."
                    })
                    continue

                # Check if it's a text message from the client
                elif message.get("type") == "text_input":
                    text = message.get("text", "")
                    logger.info(f"Received text input: {text}")
                    await agent.send(text)
                    continue

                # Audio and other events - pass through to agent
                else:
                    return message

        # Wrap output function to capture and store transcripts to memory
        async def memory_aware_output(event_dict):
            """Send output, log tool events, and store transcripts to memory if enabled."""
            event_type = event_dict.get("type", "")
            
            # Log all events for debugging (helps diagnose missing tool events)
            if event_type not in ("bidi_audio_stream", "bidi_response_start"):
                # Skip noisy audio/response-start events, log everything else
                logger.info(f"📤 [Output] Sending event to client: type={event_type}")
            
            await output_fn(event_dict)
            
            # Log tool use events with details
            if event_type == "tool_use_stream":
                tool_info = event_dict.get("current_tool_use", {})
                tool_name = tool_info.get("name", "unknown")
                tool_input = tool_info.get("input", {})
                logger.info(f"🔧 Tool call: {tool_name} (input keys: {list(tool_input.keys()) if isinstance(tool_input, dict) else 'N/A'})")
            elif event_type == "tool_result":
                tool_result = event_dict.get("tool_result", {})
                tool_name = tool_result.get("name", "unknown") if isinstance(tool_result, dict) else "unknown"
                status = tool_result.get("status", "unknown") if isinstance(tool_result, dict) else "unknown"
                logger.info(f"🔧 Tool result: {tool_name} (status={status})")
            elif event_type == "tool_cancel_event":
                logger.info(f"🔧 Tool cancelled (MCP gateway handling)")
            elif "tool_cancel_event" in event_dict:
                logger.info(f"🔧 Tool cancelled (MCP gateway handling)")
            
            # Store transcripts to memory
            if memory_enabled and memory and event_type == "bidi_transcript_stream":
                text = event_dict.get("text", "")
                role = event_dict.get("role", "")
                is_final = event_dict.get("is_final", True)
                if text and role in ("user", "assistant") and is_final:
                    logger.info(f"🧠 [Runtime] Storing conversation to AgentCore Memory: role={role}, text={text[:60]}...")
                    import asyncio
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, memory.store_turn, actor_id, session_id, role, text)
                    logger.info(f"🧠 [Runtime] Memory store call completed for {role} turn")

        # Start the agent with the input handler
        invocation_state = config.get("invocation_state")
        await agent.run(
            inputs=[handle_websocket_input],
            outputs=[memory_aware_output],
            invocation_state=invocation_state,
        )

    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        # Ignore AWS CRT cancelled future errors during cleanup
        if "InvalidStateError" in type(e).__name__ or "CANCELLED" in str(e):
            logger.warning(f"Ignoring CRT cleanup error: {e}")
        else:
            logger.error(f"Error: {e}")
            traceback.print_exc()
            try:
                await output_fn({"type": "error", "message": str(e)})
            except Exception:
                pass
    finally:
        logger.info("Connection closed")


async def _wait_for_config(websocket: WebSocket) -> dict | None:
    """Wait for the initial config event from the client. Returns parsed config or None."""
    while True:
        message = await websocket.receive_json()

        if message.get("type") == "config":
            voice = message.get("voice", "tiffany")
            input_rate = message.get("input_sample_rate", message.get("input_rate", 16000))
            output_rate = message.get("output_sample_rate", message.get("output_rate", 16000))
            model_id = message.get("model_id", "amazon.nova-2-sonic-v1:0")
            region = message.get("region", "us-east-1")
            gateway_arns = message.get("gateway_arns", None)
            system_prompt = message.get("system_prompt", None)
            profile_name = message.get("profile", None)

            # Memory fields
            memory_enabled = message.get("memory_enabled", False)
            actor_id = message.get("actor_id", "")
            session_id = message.get("session_id", "")

            # BidiAgent config
            invocation_state = message.get("invocation_state", None)
            tools_config = message.get("tools", None)

            # Resolve profile → system_prompt + tools if profile is provided
            if profile_name and profile_name in PROFILES:
                profile = PROFILES[profile_name]
                if not system_prompt:
                    system_prompt = profile["system_prompt"]
                if not tools_config:
                    tools_config = profile["tools"]
                if not gateway_arns and profile.get("gateway_arns"):
                    gateway_arns = profile["gateway_arns"]
                logger.info(f"📋 Profile: {profile_name}")

            logger.info(f"📥 Received config event:")
            logger.info(f"   Voice: {voice}")
            logger.info(f"   Model: {model_id}")
            logger.info(f"   Region: {region}")
            logger.info(f"   Audio: {input_rate}Hz input, {output_rate}Hz output")
            if memory_enabled:
                logger.info(f"   Memory: enabled (actor={actor_id}, session={session_id or 'new'})")
            if invocation_state:
                logger.info(f"   Invocation state: {list(invocation_state.keys())}")
            if tools_config:
                logger.info(f"   Tools: {tools_config}")

            return {
                "voice": voice,
                "input_rate": input_rate,
                "output_rate": output_rate,
                "model_id": model_id,
                "region": region,
                "gateway_arns": gateway_arns,
                "system_prompt": system_prompt,
                "api_key": message.get("api_key", None),
                "memory_enabled": memory_enabled,
                "actor_id": actor_id,
                "session_id": session_id,
                "invocation_state": invocation_state,
                "tools": tools_config,
            }
        else:
            logger.warning(f"⚠️ Expected config event, got {message.get('type')}")
            await websocket.send_json({
                "type": "system",
                "message": "Please send config event first"
            })


def _create_agent(config: dict, default_gateway_arns: list, hooks: list = None, messages: list = None) -> BidiAgent:
    """Create and return a BidiAgent from the given config."""
    # Use gateway ARNs from config if provided, otherwise use environment defaults
    effective_gateway_arns = config["gateway_arns"] if config["gateway_arns"] else default_gateway_arns
    effective_system_prompt = config["system_prompt"] if config["system_prompt"] else get_system_prompt()

    if config["gateway_arns"]:
        logger.info(f"   Gateways: {len(config['gateway_arns'])} from config event")
    else:
        logger.info(f"   Gateways: {len(default_gateway_arns)} from environment")

    model_id = config["model_id"]
    logger.info(f"🎤 Initializing agent with model: {model_id}, voice: {config['voice']}, region: {config['region']}")
    logger.info(f"📝 System prompt: {effective_system_prompt[:100]}...")

    # Build tools list based on config
    tools_config = config.get("tools")
    agent_tools = []
    use_mcp = False
    
    if tools_config and "mcp" in tools_config:
        # MCP mode: tools come from gateway, no in-app tools
        use_mcp = True
        logger.info("   Tools: MCP Gateway (tools provided by gateway)")
    elif tools_config:
        # Load only the specified in-app tools
        for tool_name in tools_config:
            if tool_name in AVAILABLE_TOOLS:
                agent_tools.append(AVAILABLE_TOOLS[tool_name])
                logger.info(f"   Tool loaded: {tool_name}")
            else:
                logger.warning(f"   Tool not found: {tool_name}")
    else:
        # Default: load all in-app tools
        agent_tools = list(AVAILABLE_TOOLS.values())
        logger.info(f"   Tools: all ({len(agent_tools)} in-app tools)")

    # Only pass MCP gateway ARNs to model when in MCP mode
    if not use_mcp:
        model = _create_model(config, [])  # no MCP gateways
    else:
        model = _create_model(config, effective_gateway_arns)

    logger.info(f"   Creating BidiAgent: {len(agent_tools)} in-app tools, mcp={'yes' if use_mcp else 'no'}")

    # Build hooks list
    agent_hooks = []
    if use_mcp:
        # When deployed to AgentCore with MCP gateways, tool calls may be handled in two ways:
        # 1. AgentCore runtime intercepts toolUse events and handles them transparently
        #    (agent never sees them → client never gets tool events)
        # 2. Nova Sonic emits toolUse events that reach the agent, but the tools aren't
        #    in the local registry → "Unknown tool" error breaks the conversation
        #
        # This hook handles case 2: it cancels local execution for unknown tools and
        # rewrites the result to success, preventing the error from breaking the stream.
        # The ToolUseStreamEvent is still forwarded to the client for display.
        mcp_hook = MCPToolPassThroughHook(mcp_tool_names=None)  # catch-all for unknown tools
        agent_hooks.append(mcp_hook)
        logger.info("   Hook: MCPToolPassThroughHook registered (prevents local execution of MCP tools)")

    return BidiAgent(
        model=model,
        tools=agent_tools,
        system_prompt=effective_system_prompt,
        hooks=agent_hooks if agent_hooks else None,
    )


def _create_model(config: dict, effective_gateway_arns: list):
    """Create the appropriate BidiModel based on model_id."""
    model_id = config["model_id"]

    # Nova Sonic
    if model_id.startswith("amazon.nova"):
        return BidiNovaSonicModel(
            region=config.get("region", "us-east-1"),
            model_id=model_id,
            provider_config={
                "audio": {
                    "input_rate": config["input_rate"],
                    "output_rate": config["output_rate"],
                    "voice": config["voice"],
                }
            },
            mcp_gateway_arn=effective_gateway_arns,
        )

    # OpenAI Realtime
    elif model_id.startswith("gpt-"):
        logger.info("Using OpenAI RealTime Model")
        try:
            from strands.experimental.bidi.models.openai_realtime import BidiOpenAIRealtimeModel
        except ImportError:
            raise RuntimeError(
                "OpenAI Realtime support not installed. "
                "Run: pip install 'strands-agents[bidi-openai]'"
            )

        api_key = config.get("api_key") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OpenAI API key is required. Provide it via config or OPENAI_API_KEY env var.")

        return BidiOpenAIRealtimeModel(
            model_id=model_id,
            provider_config={
                "audio": {
                    "voice": config["voice"],
                }
            },
            client_config={"api_key": api_key},
            mcp_gateway_arn=effective_gateway_arns,
       )

    # Gemini Live
    elif model_id.startswith("gemini"):
        logger.info("Using Gemini Live Model")
        try:
            from strands.experimental.bidi.models.gemini_live import BidiGeminiLiveModel
        except ImportError:
            raise RuntimeError(
                "Gemini Live support not installed. "
                "Run: pip install 'strands-agents[bidi-gemini]'"
            )

        api_key = config.get("api_key") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("Google API key is required. Provide it via config or GOOGLE_API_KEY env var.")

        # Set env var so the Gemini client picks it up
        os.environ["GOOGLE_API_KEY"] = api_key

        return BidiGeminiLiveModel(
            model_id=model_id,
            provider_config={
                "audio": {
                    "input_rate": config["input_rate"],
                    "output_rate": config["output_rate"],
                }
            },
            client_config={"api_key": api_key},
            mcp_gateway_arn=effective_gateway_arns,
        )

    else:
        raise RuntimeError(f"Unsupported model_id: {model_id}")
