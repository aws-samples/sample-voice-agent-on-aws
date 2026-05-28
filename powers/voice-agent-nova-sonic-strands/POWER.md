---
name: "nova-sonic-strands-bidiagent"
displayName: "Amazon Nova Sonic + Strands BidiAgent"
description: "Build real-time voice agents with Amazon Nova Sonic and Strands Agents BidiAgent — covering bidirectional streaming, WebSocket server, custom tools, and browser client."
keywords: ["voice", "agent", "strands", "bidiagent", "amazon nova sonic", "speech-to-speech", "s2s", "bedrock", "websocket", "audio", "realtime", "streaming"]
author: "AWS"
---

# Amazon Nova Sonic + Strands BidiAgent

Use this power for building real-time voice agents with Strands Agents BidiAgent and Amazon Nova Sonic.

## How Kiro Uses This Power

1. Kiro loads this `POWER.md` into the initial context window.
2. Kiro infers the user's intent from the prompt.
3. Kiro retrieves only the steering files that match that intent.

Do not load all steering files by default. Load the minimum set needed for the task. If the task is only setup or dependency installation, stay in this `POWER.md` and do not load capability steering files.

**Do NOT scaffold or generate code immediately when the power is activated.** Wait for the user to describe what they want to build. Ask clarifying questions if the request is vague (e.g., "What should the voice agent do?", "Do you need any tools or sub-agents?"). Only start generating files once the user has provided enough context about their requirements.

## Onboarding

Before using any capability, confirm:

- AWS credentials are configured with access to Amazon Bedrock (Amazon Nova Sonic model).
- Python 3.11+ is available.
- The `strands-agents` package is installed.

### Install Dependencies

```bash
pip install strands-agents strands-agents-builder aws-sdk-bedrock-runtime
pip install fastapi uvicorn websockets
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `AWS_DEFAULT_REGION` | AWS region (default: `us-east-1`) |
| `AWS_ACCESS_KEY_ID` | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key |

### Core Pattern

```python
from strands.experimental.bidi.agent import BidiAgent
from strands.experimental.bidi.models.nova_sonic import BidiNovaSonicModel

model = BidiNovaSonicModel(
    region="us-east-1",
    model_id="amazon.nova-2-sonic-v1:0",
    provider_config={
        "audio": {
            "input_rate": 16000,
            "output_rate": 16000,
            "voice": "tiffany",
        }
    },
)

agent = BidiAgent(
    model=model,
    tools=[],
    system_prompt="You are a helpful voice assistant.",
)

await agent.run(inputs=[input_handler], outputs=[output_handler])
```

## Project Structure

When the user asks to scaffold or create a voice agent project, create two folders and a root README:

```
project/
├── README.md           # Setup and run instructions
├── websocket/          # Server-side: BidiAgent + Amazon Nova Sonic orchestrator
│   ├── server.py       # FastAPI WebSocket server
│   ├── agent.py        # BidiAgent session handler (hardcoded config: voice, model, system prompt)
│   ├── tools.py        # Custom tools (only if user asks for tools)
│   └── requirements.txt
└── client/             # Client-side: Browser UI (thin — no config management)
    ├── client.py       # Python HTTP server that serves the web page
    ├── index.html      # Browser UI with mic capture + audio playback
    └── requirements.txt
```

### Generated README.md

Always generate a `README.md` at the project root with setup and run instructions. Use this template:

```markdown
# Amazon Nova Sonic Voice Agent

Real-time voice agent powered by Amazon Nova Sonic and Strands Agents BidiAgent.

## Prerequisites

- Python 3.11+
- AWS credentials with access to Amazon Bedrock (Amazon Nova Sonic model)
- A modern browser with microphone access (Chrome, Firefox, Edge)

## Setup

### 1. Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate  # On macOS/Linux
# .venv\Scripts\activate   # On Windows
```

### 2. Install dependencies

```bash
pip install -r websocket/requirements.txt
```

### 3. Configure AWS credentials

```bash
export AWS_DEFAULT_REGION=us-east-1
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
```

Or use an AWS profile:

```bash
export AWS_PROFILE=your-profile
export AWS_DEFAULT_REGION=us-east-1
```

## Running

### Start the WebSocket server

```bash
cd websocket
python server.py
```

The server starts on `http://localhost:8081`. You should see:
```
🚀 Starting Nova Sonic Voice Agent server...
📍 Region: us-east-1
```

### Start the browser client

In a separate terminal (with the same virtual environment activated):

```bash
cd client
python client.py --ws-url ws://localhost:8081/ws
```

This opens your browser automatically. Click "Start Conversation" and speak.

## Project Structure

- `websocket/` — Server-side BidiAgent orchestrator (FastAPI + Amazon Nova Sonic)
- `client/` — Browser client (Python HTTP server + HTML/JS audio UI)

## Configuration

Voice, model, and system prompt are configured in `websocket/agent.py`. Edit the constants at the top of the file:

```python
MODEL_ID = "amazon.nova-2-sonic-v1:0"
REGION = "us-east-1"
VOICE = "tiffany"
SYSTEM_PROMPT = "You are a friendly voice assistant."
```

## Available Voices

| Voice | Description |
|-------|-------------|
| tiffany | Female, warm and conversational |
| matthew | Male, professional |
| ruth | Female, clear and articulate |
| gregory | Male, deep and authoritative |
| joanna | Female, friendly |
```

Adapt the README content based on what was actually generated (e.g., include sub-agents section if sub-agents were created, include tools section if tools were added).

### Folder Responsibilities

- **websocket/**: Contains the Strands BidiAgent orchestrator. This is the server that connects to Nova Sonic, handles bidirectional audio streaming, and optionally invokes tools. It exposes a WebSocket endpoint that the client connects to. All agent configuration (system prompt, voice, model, region) is hardcoded here.
- **client/**: Contains a Python HTTP server that serves a web page. The web page captures microphone audio, sends it over WebSocket to the server, and plays back audio responses. The client is thin — it does not manage configuration or profiles.

## When To Load Steering Files

Load only the exact file that matches the user's requested functionality.

- Load `steering/websocket-server.md` when the user is building the WebSocket server, creating the BidiAgent orchestrator, handling audio sessions, configuring voices, splitting large audio events, adding custom tools, or creating sub-agents for the voice agent.
- Load `steering/client-browser.md` when the user is building the browser client, capturing microphone audio, playing back responses, creating the client HTTP server, or designing the UI.

### Multi-File Retrieval Rules

- Load no steering files for installation, SDK selection, auth, or environment setup. Use this `POWER.md` only.
- Load exactly one steering file when the request is narrowly scoped to one capability.
- Load both steering files when the user asks to scaffold the full project or needs both server and client.

## Available Steering Files

- `steering/websocket-server.md`
- `steering/client-browser.md`

## Key References

- [Strands Agents Documentation](https://strandsagents.com/)
- [BidiAgent Speech-to-Speech Guide](https://strandsagents.com/latest/user-guide/concepts/multimodal/speech-to-speech/)
- [Amazon Nova Sonic User Guide](https://docs.aws.amazon.com/nova/latest/userguide/speech.html)
