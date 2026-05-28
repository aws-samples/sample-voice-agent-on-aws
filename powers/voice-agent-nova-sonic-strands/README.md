# Amazon Nova Sonic + Strands BidiAgent Voice Agent Power

A Kiro power for building real-time voice agents with [Amazon Nova Sonic](https://docs.aws.amazon.com/nova/latest/userguide/speech.html) and [Strands Agents BidiAgent](https://strandsagents.com/latest/user-guide/concepts/multimodal/speech-to-speech/).

This is a documentation-only power: a single root `POWER.md` plus capability-specific files in `steering/`. There is no `mcp.json` in this repo.

## Included Capabilities

- WebSocket server with Strands BidiAgent orchestrating Amazon Nova Sonic speech-to-speech
- Custom tool integration for the voice agent
- Browser-based client with microphone capture and audio playback

## How It Works In Kiro

1. Kiro loads the root `POWER.md` into the initial context window.
2. Kiro infers user intent from the prompt.
3. Kiro retrieves only the relevant files from `steering/`.

## Install In Kiro

Install this repository from:

- GitHub URL
- Local path

When installing from disk, select the repository root as the local power path.

## Configuration

Requires AWS credentials with access to Amazon Bedrock (Amazon Nova Sonic model):

```bash
export AWS_DEFAULT_REGION="us-east-1"
```

## Project Structure

When scaffolded, the power instructs Kiro to create:

```
project/
├── README.md           # Setup and run instructions (venv, install, run)
├── websocket/          # Server-side: BidiAgent + Amazon Nova Sonic orchestrator
│   ├── server.py       # FastAPI WebSocket server
│   ├── agent.py        # BidiAgent session handler (hardcoded config)
│   ├── tools.py        # Custom tools (optional, on request)
│   └── requirements.txt
└── client/             # Client-side: Browser UI (thin — audio I/O only)
    ├── client.py       # Python HTTP server that serves the web page
    ├── index.html      # Browser UI with mic capture + audio playback
    └── requirements.txt
```

## License

MIT
