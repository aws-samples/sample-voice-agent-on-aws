# WebSocket Server

## Overview

The voice agent runs as a FastAPI WebSocket server that accepts client connections, creates a BidiAgent per session, and relays audio between the client and Amazon Nova Sonic. The server is split into two files: `server.py` (FastAPI app, event splitting, startup) and `agent.py` (BidiAgent session logic).

## Folder: `websocket/`

Create this folder with the following files:

- `server.py` — FastAPI application with WebSocket endpoint
- `agent.py` — BidiAgent session handler
- `tools.py` — Custom tools (only create if the user asks for tools)
- `requirements.txt` — Python dependencies

---

## server.py

The main entry point. Runs a FastAPI server with a `/ws` WebSocket endpoint and a `/ping` health check.

```python
import logging
import uvicorn
import os
import json
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from agent import handle_websocket_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Large-event splitting
# ---------------------------------------------------------------------------
MAX_WS_MESSAGE_SIZE = 10000


def split_large_event(event_dict, max_size=MAX_WS_MESSAGE_SIZE):
    """Split a large event into smaller chunks by dividing the audio field.

    Ensures splits occur at base64 boundaries (4-char alignment) to avoid corruption.
    """
    event_json = json.dumps(event_dict)
    event_size = len(event_json.encode("utf-8"))

    if event_size <= max_size:
        return [event_dict]

    if "audio" not in event_dict or not isinstance(event_dict["audio"], str):
        return [event_dict]

    audio_content = event_dict["audio"]
    template = {k: v for k, v in event_dict.items() if k != "audio"}
    template["audio"] = ""
    overhead = len(json.dumps(template).encode("utf-8"))

    max_content_size = max_size - overhead - 100
    max_content_size = (max_content_size // 4) * 4  # Align to base64

    if max_content_size <= 0:
        return [event_dict]

    chunks = []
    for i in range(0, len(audio_content), max_content_size):
        chunk_audio = audio_content[i:i + max_content_size]
        chunk_event = {k: v for k, v in event_dict.items() if k != "audio"}
        chunk_event["audio"] = chunk_audio
        chunks.append(chunk_event)

    logger.info(f"Split audio event ({event_size} bytes) into {len(chunks)} chunks")
    return chunks


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
app = FastAPI(title="Amazon Nova Sonic Voice Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Starting Amazon Nova Sonic Voice Agent server...")
    logger.info(f"📍 Region: {os.getenv('AWS_DEFAULT_REGION', 'us-east-1')}")


@app.get("/ping")
async def ping():
    """Health check endpoint."""
    import time
    return {"status": "Healthy", "time_of_last_update": int(time.time())}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    async def chunked_send_json(event_dict):
        """Send output events, splitting large audio payloads."""
        chunks = split_large_event(event_dict)
        for chunk in chunks:
            await websocket.send_json(chunk)

    await handle_websocket_session(websocket, send_output=chunked_send_json)


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8081"))
    uvicorn.run(app, host=host, port=port)
```

---

## agent.py

Handles a single WebSocket session: waits for a config event (as a readiness signal), creates the BidiAgent with hardcoded settings, and runs the bidirectional audio loop.

```python
import logging
import traceback

from fastapi import WebSocket, WebSocketDisconnect

from strands.experimental.bidi.agent import BidiAgent
from strands.experimental.bidi.models.nova_sonic import BidiNovaSonicModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hardcoded agent configuration — edit these to change behavior
# ---------------------------------------------------------------------------
MODEL_ID = "amazon.nova-2-sonic-v1:0"
REGION = "us-east-1"
VOICE = "tiffany"
INPUT_RATE = 16000
OUTPUT_RATE = 16000
SYSTEM_PROMPT = """You are a friendly voice assistant. Be warm, conversational, and concise."""


async def handle_websocket_session(websocket: WebSocket, send_output=None):
    """Handle a single WebSocket voice session."""
    output_fn = send_output or websocket.send_json

    try:
        # Wait for config event from client (just a readiness signal)
        await _wait_for_config(websocket)

        # Create agent with hardcoded settings
        agent = _create_agent()
        logger.info(f"✅ Agent ready: model={MODEL_ID}, voice={VOICE}")

        # Acknowledge
        await output_fn({
            "type": "system",
            "message": f"Ready: {MODEL_ID} with voice={VOICE}",
        })

        # Input handler: reads messages from the WebSocket
        async def handle_input():
            while True:
                message = await websocket.receive_json()

                if message.get("type") == "text_input":
                    text = message.get("text", "")
                    logger.info(f"Text input: {text}")
                    await agent.send(text)
                    continue

                # Audio and other events pass through to agent
                return message

        # Run the bidirectional agent
        await agent.run(inputs=[handle_input], outputs=[output_fn])

    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        if "CANCELLED" in str(e):
            logger.warning(f"Cleanup error (ignored): {e}")
        else:
            logger.error(f"Error: {e}")
            traceback.print_exc()
            try:
                await output_fn({"type": "error", "message": str(e)})
            except Exception:
                pass
    finally:
        logger.info("Session closed")


async def _wait_for_config(websocket: WebSocket):
    """Wait for the client to send a config event (readiness signal)."""
    while True:
        message = await websocket.receive_json()

        if message.get("type") == "config":
            logger.info("📥 Client ready (config event received)")
            return
        else:
            await websocket.send_json({
                "type": "system",
                "message": "Please send a config event first.",
            })


def _create_agent() -> BidiAgent:
    """Create a BidiAgent with hardcoded configuration."""
    model = BidiNovaSonicModel(
        region=REGION,
        model_id=MODEL_ID,
        provider_config={
            "audio": {
                "input_rate": INPUT_RATE,
                "output_rate": OUTPUT_RATE,
                "voice": VOICE,
            }
        },
    )

    return BidiAgent(
        model=model,
        tools=[],
        system_prompt=SYSTEM_PROMPT,
    )
```

---

## tools.py (Only If Requested)

Create this file only when the user explicitly asks for custom tools. Tools are Python functions decorated with `@tool` from Strands:

```python
from strands import tool


@tool
def get_weather(city: str) -> str:
    """Get the current weather for a city.

    Args:
        city: The city name to get weather for.
    """
    # Replace with real API call
    return f"The weather in {city} is sunny and 72°F."


@tool
def get_time() -> str:
    """Get the current time."""
    from datetime import datetime
    return f"The current time is {datetime.now().strftime('%I:%M %p')}."
```

When tools are added, update `agent.py` to import and pass them:

```python
from tools import get_weather, get_time

# In _create_agent():
return BidiAgent(
    model=model,
    tools=[get_weather, get_time],
    system_prompt=system_prompt,
)
```

---

## Sub-Agents (Strands Agent as Tool)

When the user asks to create a sub-agent, use the Strands "agent as tool" pattern. A sub-agent is a full Strands `Agent` instance (text-based, using a reasoning model) that gets wrapped and passed as a tool to the BidiAgent. Amazon Nova Sonic invokes it mid-stream like any other tool.

**Default reasoning model**: Use `us.amazon.nova-2-lite-v1:0` for sub-agents unless the user specifies otherwise.

### Sub-Agent Pattern

Create a `subagents.py` file in the `websocket/` folder:

```python
from strands import Agent
from strands.models.bedrock import BedrockModel


def create_subagent_tool(
    name: str,
    description: str,
    system_prompt: str,
    tools: list = None,
    model_id: str = "us.amazon.nova-2-lite-v1:0",
    region: str = "us-east-1",
):
    """Create a Strands Agent and return it as a tool for the BidiAgent.

    The sub-agent uses a text-based reasoning model (default: Nova Lite)
    and can have its own tools. It is invoked by the voice agent when
    Nova Sonic decides the sub-agent's expertise is needed.

    Args:
        name: Tool name exposed to the BidiAgent (e.g., "finance_agent").
        description: What this sub-agent does — Amazon Nova Sonic uses this to decide when to call it.
        system_prompt: Instructions for the sub-agent's behavior.
        tools: Optional list of @tool functions the sub-agent can use.
        model_id: Bedrock model ID for reasoning (default: us.amazon.nova-2-lite-v1:0).
        region: AWS region for the model.

    Returns:
        The Agent instance configured as a tool (pass directly to BidiAgent tools list).
    """
    model = BedrockModel(
        model_id=model_id,
        region_name=region,
    )

    agent = Agent(
        model=model,
        tools=tools or [],
        system_prompt=system_prompt,
        name=name,
        description=description,
    )

    return agent
```

### Example: Creating Sub-Agents

```python
# subagents.py
from strands import Agent, tool
from strands.models.bedrock import BedrockModel


# --- Sub-agent specific tools ---

@tool
def lookup_order(order_id: str) -> str:
    """Look up an order by ID.

    Args:
        order_id: The order ID to look up.
    """
    # Replace with real database/API call
    return f"Order {order_id}: shipped on May 20, arriving May 23."


@tool
def check_balance(account_id: str) -> str:
    """Check account balance.

    Args:
        account_id: The account ID to check.
    """
    return f"Account {account_id} balance: $4,250.00"


# --- Sub-agent definitions ---

def create_order_agent(region: str = "us-east-1"):
    """Create an order tracking sub-agent."""
    model = BedrockModel(
        model_id="us.amazon.nova-2-lite-v1:0",
        region_name=region,
    )

    return Agent(
        model=model,
        tools=[lookup_order],
        system_prompt="You are an order tracking specialist. Look up orders and provide status updates. Be concise.",
        name="order_tracker",
        description="Tracks and provides status updates for customer orders. Call this when the user asks about an order, shipment, or delivery.",
    )


def create_finance_agent(region: str = "us-east-1"):
    """Create a finance sub-agent."""
    model = BedrockModel(
        model_id="us.amazon.nova-2-lite-v1:0",
        region_name=region,
    )

    return Agent(
        model=model,
        tools=[check_balance],
        system_prompt="You are a finance assistant. Help with account balances, transactions, and financial questions. Be precise with numbers.",
        name="finance_agent",
        description="Handles financial queries including account balances, transactions, and money-related questions. Call this for any banking or finance topic.",
    )
```

### Wiring Sub-Agents into the BidiAgent

Update `agent.py` to import and pass sub-agents as tools:

```python
from subagents import create_order_agent, create_finance_agent

# In _create_agent():
def _create_agent() -> BidiAgent:
    """Create a BidiAgent with sub-agents as tools."""
    model = BidiNovaSonicModel(
        region=REGION,
        model_id=MODEL_ID,
        provider_config={
            "audio": {
                "input_rate": INPUT_RATE,
                "output_rate": OUTPUT_RATE,
                "voice": VOICE,
            }
        },
    )

    # Create sub-agents (each is passed as a tool)
    order_agent = create_order_agent(region=REGION)
    finance_agent = create_finance_agent(region=REGION)

    return BidiAgent(
        model=model,
        tools=[order_agent, finance_agent],
        system_prompt=SYSTEM_PROMPT,
    )
```

### How It Works

1. The BidiAgent (Amazon Nova Sonic) sees each sub-agent as a tool with a `name` and `description`.
2. When the user's voice request matches a sub-agent's description, Amazon Nova Sonic invokes it as a tool call.
3. The sub-agent runs synchronously using its own reasoning model (Nova Lite) and its own tools.
4. The sub-agent's text response is returned to Amazon Nova Sonic, which speaks it back to the user.
5. Audio streaming continues uninterrupted — the sub-agent call happens mid-conversation.

### Sub-Agent Design Guidelines

- **Keep descriptions clear**: Amazon Nova Sonic uses the `description` field to decide when to route to a sub-agent. Be specific about what triggers it.
- **Use Nova 2 Lite by default**: `us.amazon.nova-2-lite-v1:0` is fast and cost-effective for text reasoning. Use `us.amazon.nova-2-pro-v1:0` only if the sub-agent needs stronger reasoning.
- **Give sub-agents their own tools**: Sub-agents can call APIs, query databases, etc. via their own `@tool` functions.
- **Keep sub-agent responses concise**: Amazon Nova Sonic will speak the response aloud, so long text responses create awkward pauses.
- **System prompt matters**: Tell the sub-agent to be brief since its output will be spoken.

### File Structure with Sub-Agents

```
websocket/
├── server.py           # FastAPI WebSocket server
├── agent.py            # BidiAgent session handler (imports sub-agents)
├── subagents.py        # Sub-agent definitions (Agent as tool)
├── tools.py            # Simple @tool functions (optional)
└── requirements.txt
```

### Requirements Update

When using sub-agents, `requirements.txt` stays the same — `strands-agents` and `aws-sdk-bedrock-runtime` include everything needed:

```
strands-agents
strands-agents-builder
aws-sdk-bedrock-runtime
fastapi
uvicorn[standard]
websockets
```

---

## requirements.txt

```
strands-agents
strands-agents-builder
aws-sdk-bedrock-runtime
fastapi
uvicorn[standard]
websockets
```

---

## Config Event Format

The client sends a minimal config event to signal readiness. All actual configuration is hardcoded in `agent.py` on the server:

```json
{
  "type": "config"
}
```

The server ignores any extra fields in the config event and uses its own defaults for voice, model, region, and system prompt. To change agent behavior, edit the constants in `agent.py`.

## Available Voices

| Voice | Description |
|-------|-------------|
| `tiffany` | Female, warm and conversational |
| `matthew` | Male, professional |
| `ruth` | Female, clear and articulate |
| `gregory` | Male, deep and authoritative |
| `joanna` | Female, friendly |

## Audio Configuration

- Input: 16000 Hz, 16-bit PCM, mono, base64-encoded
- Output: 16000 or 24000 Hz, base64-encoded
- Large audio events (>10KB) are split at base64 boundaries (4-char alignment)

## Running Locally

```bash
cd websocket
pip install -r requirements.txt
export AWS_DEFAULT_REGION=us-east-1
python server.py
```

The server starts on port 8081 by default. Override with `PORT` env var.

## Key Behaviors

- **One agent per connection**: Each WebSocket connection gets its own BidiAgent instance.
- **Config-first protocol**: The client must send a `{"type": "config"}` event before audio flows (acts as a readiness signal).
- **Server-side configuration**: Voice, model, region, and system prompt are hardcoded in `agent.py`. Edit the constants at the top of the file to change behavior.
- **Barge-in**: Amazon Nova Sonic handles voice activity detection natively — no external VAD needed.
- **Text input**: Clients can send `{"type": "text_input", "text": "..."}` alongside audio.
- **Tool use mid-stream**: If tools are configured, they execute without pausing the audio flow.
