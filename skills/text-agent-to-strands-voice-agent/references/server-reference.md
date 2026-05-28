# Server Implementation Reference

Detailed reference for the FastAPI WebSocket voice agent server. For the minimal version, see SKILL.md Part 2. This covers production concerns.

## Full Session Handler

The production session handler includes:

- **Config event parsing**: Waits for the first WebSocket message with voice, model, region, sample rates, system prompt, and gateway ARNs
- **Multi-model support**: Creates `BidiNovaSonicModel`, `BidiOpenAIRealtimeModel`, or `BidiGeminiLiveModel` based on `model_id`
- **Text input routing**: Handles `text_input` messages alongside audio frames
- **Memory integration**: Optional AgentCore Memory for conversation persistence across sessions
- **Observability**: Optional OpenTelemetry tracing via custom spans and baggage

## Config Event Schema

```json
{
    "type": "config",
    "voice": "matthew",
    "model_id": "amazon.nova-2-sonic-v1:0",
    "region": "us-east-1",
    "input_rate": 16000,
    "output_rate": 16000,
    "system_prompt": "...",
    "gateway_arns": ["arn:aws:bedrock-agentcore:..."],
    "api_key": null,
    "memory_enabled": true,
    "session_id": "session_20240304",
    "actor_id": "user-sarah"
}
```

## Large Event Splitting

WebSocket frames have size limits. The server splits large audio events into chunks aligned to base64 boundaries:

```python
MAX_WS_MESSAGE_SIZE = 10000

def split_large_event(event_dict, max_size=MAX_WS_MESSAGE_SIZE):
    if len(json.dumps(event_dict).encode("utf-8")) <= max_size:
        return [event_dict]
    if "audio" not in event_dict:
        return [event_dict]

    audio = event_dict["audio"]
    template = {k: v for k, v in event_dict.items() if k != "audio"}
    overhead = len(json.dumps({**template, "audio": ""}).encode("utf-8"))
    chunk_size = ((max_size - overhead - 100) // 4) * 4

    return [{**template, "audio": audio[i:i + chunk_size]}
            for i in range(0, len(audio), chunk_size)]
```

## Credential Refresh (AgentCore Runtime)

When deployed on AgentCore Runtime, the server refreshes IAM credentials from IMDS automatically. See `samples/bidi-streaming/strands-sonic/websocket/server.py` for the full implementation.

## Requirements

System prerequisite (macOS): `brew install portaudio`
System prerequisite (Debian/Ubuntu): `apt-get install -y portaudio19-dev gcc g++ make`

Python packages:
```
uvicorn[standard]
fastapi
strands-agents
aws_sdk_bedrock_runtime
pyaudio
boto3
botocore
```

## Tool Migration Pattern

1. **Extract** the tool's name, description, and input schema from the text agent
2. **Create** an MCP server with matching `Tool` definitions
3. **Implement** `call_tool` to invoke the existing function logic
4. **Deploy** behind an AgentCore MCP Gateway
5. **Pass** the gateway ARN to `mcp_gateway_arn` on the BidiModel
