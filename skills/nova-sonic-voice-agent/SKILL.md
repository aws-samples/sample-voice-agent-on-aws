---
name: nova-sonic-voice-agent
description: "Build a real-time voice agent from scratch using Amazon Nova Sonic and Strands BidiAgent. Covers two layers: (1) Orchestrator — FastAPI + Strands BidiAgent WebSocket server with custom tools and sub-agents, (2) Frontend — browser client with Web Audio API for mic capture and audio playback. TRIGGER when: user wants to build a voice agent; user asks about Amazon Nova Sonic; user mentions BidiAgent, speech-to-speech, real-time voice, or audio streaming agent; user wants to add tools or sub-agents to a voice agent. SKIP when: user is migrating an existing text agent (use text-agent-to-nova-sonic-voice skill instead); user wants TTS/STT without a live agent loop; user is asking about deployment or infrastructure only."
---

# Build a Nova Sonic Voice Agent

This skill creates a real-time voice agent from scratch using Strands BidiAgent with Amazon Nova Sonic. The agent runs as a WebSocket server that streams bidirectional audio with the user's browser.

## Architecture

```
Browser (mic + speaker)  ←WebSocket→  FastAPI Server  ←BidiStream→  Amazon Nova Sonic
                                          ↕
                                    Tools / Sub-Agents
```

## Prerequisites

- Python 3.11+
- AWS credentials with access to Amazon Bedrock (Amazon Nova Sonic model)
- A modern browser with microphone access

### Install Dependencies

```bash
pip install strands-agents strands-agents-builder aws-sdk-bedrock-runtime
pip install fastapi uvicorn[standard] websockets
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `AWS_DEFAULT_REGION` | Yes | AWS region (default: `us-east-1`) |
| `AWS_ACCESS_KEY_ID` | Yes* | AWS access key (*auto-detected from profile) |
| `AWS_SECRET_ACCESS_KEY` | Yes* | AWS secret key (*auto-detected from profile) |

## Project Structure

```
project/
├── README.md
├── websocket/
│   ├── server.py           # FastAPI WebSocket server with event splitting
│   ├── agent.py            # BidiAgent session handler (config: voice, model, prompt)
│   ├── tools.py            # Custom @tool functions (optional)
│   ├── subagents.py        # Sub-agents as tools (optional)
│   └── requirements.txt
└── client/
    ├── client.py           # Python HTTP server serving the web page
    ├── index.html          # Browser UI with mic capture + audio playback
    └── requirements.txt
```

## Part 1 — WebSocket Server (Orchestrator)

### server.py — FastAPI Application

The server exposes a `/ws` WebSocket endpoint and splits large audio events at base64 boundaries:

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

MAX_WS_MESSAGE_SIZE = 10000

def split_large_event(event_dict, max_size=MAX_WS_MESSAGE_SIZE):
    """Split large audio events into smaller chunks at base64 boundaries."""
    event_json = json.dumps(event_dict)
    if len(event_json.encode("utf-8")) <= max_size:
        return [event_dict]
    if "audio" not in event_dict or not isinstance(event_dict["audio"], str):
        return [event_dict]

    audio_content = event_dict["audio"]
    template = {k: v for k, v in event_dict.items() if k != "audio"}
    template["audio"] = ""
    overhead = len(json.dumps(template).encode("utf-8"))
    max_content_size = ((max_size - overhead - 100) // 4) * 4

    chunks = []
    for i in range(0, len(audio_content), max_content_size):
        chunk_event = {k: v for k, v in event_dict.items() if k != "audio"}
        chunk_event["audio"] = audio_content[i:i + max_content_size]
        chunks.append(chunk_event)
    return chunks

app = FastAPI(title="Nova Sonic Voice Agent")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/ping")
async def ping():
    import time
    return {"status": "Healthy", "time_of_last_update": int(time.time())}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    async def chunked_send_json(event_dict):
        for chunk in split_large_event(event_dict):
            await websocket.send_json(chunk)
    await handle_websocket_session(websocket, send_output=chunked_send_json)

if __name__ == "__main__":
    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8081")))
```

### agent.py — BidiAgent Session Handler

```python
import logging
import traceback
from fastapi import WebSocket, WebSocketDisconnect
from strands.experimental.bidi.agent import BidiAgent
from strands.experimental.bidi.models.nova_sonic import BidiNovaSonicModel

logger = logging.getLogger(__name__)

MODEL_ID = "amazon.nova-2-sonic-v1:0"
REGION = "us-east-1"
VOICE = "tiffany"
INPUT_RATE = 16000
OUTPUT_RATE = 16000
SYSTEM_PROMPT = """You are a friendly voice assistant. Be warm, conversational, and concise."""

async def handle_websocket_session(websocket: WebSocket, send_output=None):
    output_fn = send_output or websocket.send_json
    try:
        await _wait_for_config(websocket)
        agent = _create_agent()
        logger.info(f"✅ Agent ready: model={MODEL_ID}, voice={VOICE}")
        await output_fn({"type": "system", "message": f"Ready: {MODEL_ID} with voice={VOICE}"})

        async def handle_input():
            while True:
                message = await websocket.receive_json()
                if message.get("type") == "text_input":
                    await agent.send(message.get("text", ""))
                    continue
                return message

        await agent.run(inputs=[handle_input], outputs=[output_fn])
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        if "CANCELLED" not in str(e):
            logger.error(f"Error: {e}")
            traceback.print_exc()
    finally:
        logger.info("Session closed")

async def _wait_for_config(websocket: WebSocket):
    while True:
        message = await websocket.receive_json()
        if message.get("type") == "config":
            logger.info("📥 Client ready")
            return
        await websocket.send_json({"type": "system", "message": "Send config event first."})

def _create_agent() -> BidiAgent:
    model = BidiNovaSonicModel(
        region=REGION, model_id=MODEL_ID,
        provider_config={"audio": {"input_rate": INPUT_RATE, "output_rate": OUTPUT_RATE, "voice": VOICE}},
    )
    return BidiAgent(model=model, tools=[], system_prompt=SYSTEM_PROMPT)
```

## Part 2 — Adding Tools

Create `tools.py` with `@tool` decorated functions:

```python
from strands import tool

@tool
def get_weather(city: str) -> str:
    """Get the current weather for a city.

    Args:
        city: The city name to get weather for.
    """
    return f"The weather in {city} is sunny and 72°F."
```

Wire into `agent.py`:

```python
from tools import get_weather

def _create_agent() -> BidiAgent:
    model = BidiNovaSonicModel(...)
    return BidiAgent(model=model, tools=[get_weather], system_prompt=SYSTEM_PROMPT)
```

## Part 3 — Adding Sub-Agents

Sub-agents are full Strands `Agent` instances (text-based) passed as tools to the BidiAgent. Nova Sonic invokes them mid-stream like any other tool.

```python
from strands import Agent, tool
from strands.models.bedrock import BedrockModel

@tool
def check_balance(account_id: str) -> str:
    """Check account balance."""
    return f"Account {account_id} balance: $4,250.00"

def create_finance_agent(region: str = "us-east-1"):
    model = BedrockModel(model_id="us.amazon.nova-2-lite-v1:0", region_name=region)
    return Agent(
        model=model,
        tools=[check_balance],
        system_prompt="You are a finance assistant. Be precise with numbers and concise.",
        name="finance_agent",
        description="Handles financial queries including account balances and transactions.",
    )
```

Wire into `agent.py`:

```python
from subagents import create_finance_agent

def _create_agent() -> BidiAgent:
    model = BidiNovaSonicModel(...)
    finance = create_finance_agent(region=REGION)
    return BidiAgent(model=model, tools=[finance], system_prompt=SYSTEM_PROMPT)
```

## Part 4 — Browser Client

See [references/client-reference.md](references/client-reference.md) for the full browser client implementation including:
- AudioWorklet microphone capture at 16kHz
- Gapless audio playback with scheduled AudioBufferSourceNodes
- Speculative/final transcript handling
- Barge-in support

## Available Voices

| Voice | Description |
|-------|-------------|
| `tiffany` | Female, warm and conversational |
| `matthew` | Male, professional |
| `ruth` | Female, clear and articulate |
| `gregory` | Male, deep and authoritative |
| `joanna` | Female, friendly |

## Audio Configuration

- Sample rate: 16000 Hz (Nova Sonic native)
- Bit depth: 16-bit signed integer PCM
- Channels: 1 (mono)
- Encoding: Base64 over JSON WebSocket

## Common Pitfalls

- **Sample rate mismatch**: Nova Sonic requires 16kHz. Wrong rate produces garbled audio.
- **Long system prompts**: Keep under ~500 words. Move details into tool descriptions.
- **JSON in tool results**: Return natural-language strings, not raw JSON — the response is spoken aloud.
- **Sub-agent verbosity**: Tell sub-agents to be brief since output is spoken.
- **Missing portaudio**: Install `portaudio` system library before `pip install pyaudio` (only needed for CLI clients).
