# Server Reference

Complete implementation details for the WebSocket server orchestrator.

## server.py — Full Implementation

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
    """Split a large event into smaller chunks by dividing the audio field.

    Ensures splits occur at base64 boundaries (4-char alignment) to avoid corruption.
    Returns a list of event dicts to send.
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
        chunk_event = {k: v for k, v in event_dict.items() if k != "audio"}
        chunk_event["audio"] = audio_content[i:i + max_content_size]
        chunks.append(chunk_event)

    logger.info(f"Split audio event ({event_size} bytes) into {len(chunks)} chunks")
    return chunks


app = FastAPI(title="Nova Sonic Voice Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Starting Nova Sonic Voice Agent server...")
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

## agent.py — Full Implementation

```python
import logging
import traceback

from fastapi import WebSocket, WebSocketDisconnect

from strands.experimental.bidi.agent import BidiAgent
from strands.experimental.bidi.models.nova_sonic import BidiNovaSonicModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Agent configuration — edit these to change behavior
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
        await _wait_for_config(websocket)
        agent = _create_agent()
        logger.info(f"✅ Agent ready: model={MODEL_ID}, voice={VOICE}")

        await output_fn({
            "type": "system",
            "message": f"Ready: {MODEL_ID} with voice={VOICE}",
        })

        async def handle_input():
            while True:
                message = await websocket.receive_json()
                if message.get("type") == "text_input":
                    text = message.get("text", "")
                    logger.info(f"Text input: {text}")
                    await agent.send(text)
                    continue
                return message

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

## tools.py — Custom Tools Pattern

```python
from strands import tool
import json


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

When tools are added, update `_create_agent()` in `agent.py`:

```python
from tools import get_weather, get_time

def _create_agent() -> BidiAgent:
    model = BidiNovaSonicModel(...)
    return BidiAgent(model=model, tools=[get_weather, get_time], system_prompt=SYSTEM_PROMPT)
```

## requirements.txt

```
strands-agents
strands-agents-builder
aws-sdk-bedrock-runtime
fastapi
uvicorn[standard]
websockets
```

## WebSocket Event Protocol

### Client → Server

| Event | Description |
|-------|-------------|
| `{"type": "config"}` | Signal readiness (server uses hardcoded config) |
| `{"type": "bidi_audio_input", "audio": "<base64>", "format": "pcm", "sample_rate": 16000, "channels": 1}` | Microphone audio chunk |
| `{"type": "text_input", "text": "..."}` | Text input (alternative to voice) |

### Server → Client

| Event | Description |
|-------|-------------|
| `{"type": "system", "message": "..."}` | Status messages |
| `{"type": "bidi_audio_stream", "audio": "<base64>"}` | Audio response |
| `{"type": "bidi_transcript_stream", "role": "...", "text": "...", "is_final": bool}` | Transcript |
| `{"type": "bidi_interruption"}` | User barged in |
| `{"type": "tool_use_stream", "current_tool_use": {"name": "..."}}` | Tool invocation |
| `{"type": "tool_result", "tool_result": {...}}` | Tool result |
| `{"type": "error", "message": "..."}` | Error |

## Key Behaviors

- **One agent per connection**: Each WebSocket gets its own BidiAgent instance
- **Config-first protocol**: Client must send `{"type": "config"}` before audio flows
- **Barge-in**: Nova Sonic handles VAD natively — no external silence detection needed
- **Tool use mid-stream**: Tools execute without pausing the audio flow
- **Large event splitting**: Audio events >10KB are split at base64 boundaries
