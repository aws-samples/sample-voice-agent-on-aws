---
name: text-agent-to-nova-sonic-voice
description: "Migrate any text-based agent to a Nova Sonic voice agent using Strands BidiAgent. Covers two layers: (1) Frontend — browser WebSocket client with Web Audio API for mic capture and audio playback, (2) Orchestrator — FastAPI + Strands BidiAgent server that takes the text agent's system prompt and tools and runs them as a real-time speech-to-speech agent. TRIGGER when: user wants to add voice to an existing text agent; user asks about converting a chatbot to a Nova Sonic voice agent; user mentions text-to-voice migration, Strands BidiAgent, or Nova Sonic voice agent. SKIP when: user is building a text-only agent; user wants TTS/STT without a live agent loop; user is asking about deployment or infrastructure."
---

# Migrate a Text Agent to a Nova Sonic Voice Agent

This skill converts any text-based agent into a real-time voice agent using Strands BidiAgent with Amazon Nova Sonic. The migration is broken into two layers:

1. **Frontend** — Browser client that captures mic audio and plays back voice responses over WebSocket
2. **Orchestrator** — FastAPI + BidiAgent server that takes the text agent's system prompt and tools and runs them as a bidirectional audio streaming agent

## Prerequisites — Extract from the Text Agent

Before starting, locate these in the existing text agent (any framework):

| What | What to look for |
|------|-----------------|
| System prompt | The persona/instructions string passed to the LLM |
| Tools / functions | Name, description, and input schema of each callable tool |
| Model config | Temperature, max tokens, provider-specific settings |

## Part 1 — Frontend

The frontend is a browser-based WebSocket client that captures microphone audio, streams it to the orchestrator, and plays back audio responses.

### WebSocket Connection and Config Event

On connect, the client sends a config event with the voice-optimized system prompt:

```javascript
const ws = new WebSocket("ws://localhost:8080/ws");
ws.onopen = () => {
    ws.send(JSON.stringify({
        type: "config",
        voice: "matthew",
        model_id: "amazon.nova-2-sonic-v1:0",
        region: "us-east-1",
        input_rate: 16000,
        output_rate: 16000,
        system_prompt: voiceOptimizedPrompt
    }));
};
```

### Audio Capture and Playback

See [references/client-reference.md](references/client-reference.md) for full AudioWorklet implementation.

## Part 2 — Orchestrator

### Voice-Optimize the System Prompt

The text agent's system prompt must be rewritten for voice:

| Text pattern | Voice replacement |
|-------------|-------------------|
| "Respond with JSON / markdown / tables" | "Speak naturally. Never mention formatting." |
| "Provide comprehensive, detailed responses" | "Keep each response to one or two sentences." |
| `$15,234.56` | "fifteen thousand two hundred thirty-four dollars and fifty-six cents" |
| "Return error code and description" | "Apologize briefly and suggest what to try next" |

See [references/voice-prompt-guide.md](references/voice-prompt-guide.md) for complete before/after examples.

### Session Handler (agent.py)

```python
from strands.experimental.bidi.agent import BidiAgent
from strands.experimental.bidi.models.nova_sonic import BidiNovaSonicModel

async def handle_websocket_session(websocket):
    config = await websocket.receive_json()
    system_prompt = config.get("system_prompt", "You are a helpful voice assistant.")

    model = BidiNovaSonicModel(
        region=config.get("region", "us-east-1"),
        model_id="amazon.nova-2-sonic-v1:0",
        provider_config={"audio": {"input_rate": 16000, "output_rate": 16000, "voice": config.get("voice", "matthew")}},
    )
    agent = BidiAgent(model=model, tools=[], system_prompt=system_prompt)

    async def handle_input():
        while True:
            message = await websocket.receive_json()
            if message.get("type") == "text_input":
                await agent.send(message.get("text", ""))
                continue
            return message

    await agent.run(inputs=[handle_input], outputs=[websocket.send_json])
```

### Adding Tools

```python
from strands import tool

@tool
def get_balance(account_id: str) -> str:
    """Get account balance for the given account ID."""
    result = your_existing_function(account_id)
    return json.dumps(result)

agent = BidiAgent(model=model, tools=[get_balance], system_prompt=system_prompt)
```

For MCP Gateway tools:

```python
model = BidiNovaSonicModel(
    region="us-east-1",
    model_id="amazon.nova-2-sonic-v1:0",
    provider_config={"audio": {"input_rate": 16000, "output_rate": 16000, "voice": "matthew"}},
    mcp_gateway_arn=["arn:aws:bedrock-agentcore:us-east-1:123456:gateway/GW1"],
)
```

See [references/server-reference.md](references/server-reference.md) for production details.

## Examples

- [examples/langchain-migration/](examples/langchain-migration/) — LangChain → BidiAgent
- [examples/openai-migration/](examples/openai-migration/) — OpenAI function-calling → BidiAgent
- [examples/custom-migration/](examples/custom-migration/) — Bedrock Converse → BidiAgent

## Common Pitfalls

- **Long system prompts**: Keep under ~500 words. Move details into tool descriptions.
- **JSON in tool results**: Return natural-language strings, not raw JSON.
- **Sample rate**: Nova Sonic requires 16kHz. Mismatch produces garbled audio.
- **Missing portaudio**: Install `portaudio` system library before `pip install pyaudio`.
