# Samples

Working voice agent implementations organized by architecture pattern.

## Bidirectional Streaming (`bidi-streaming/`)

A single model handles audio input and output natively — no separate STT or TTS pipeline. Lowest latency.

| Sample | Framework | Transport | Key Feature |
|--------|-----------|-----------|-------------|
| [strands-sonic](bidi-streaming/strands-sonic/) | Strands BidiAgent | WebSocket | MCP Gateways, Memory, A2A sub-agents, multi-model ⭐ |
| [bedrock-sonic](bidi-streaming/bedrock-sonic/) | Raw Bedrock SDK | WebSocket | Full protocol control, low-level event handling |
| [pipecat-sonic](bidi-streaming/pipecat-sonic/) | Pipecat | WebSocket | Open-source pipeline, Silero VAD, RTVI/Protobuf |
| [livekit-sonic](bidi-streaming/livekit-sonic/) | LiveKit Agents | WebRTC | Room management, multi-participant |
| [webrtc-kvs-sonic](bidi-streaming/webrtc-kvs-sonic/) | aiortc + KVS | WebRTC | KVS TURN/STUN, NAT traversal |

## Cascading (`cascading/`)

Separate services chained together: STT → LLM → TTS. Higher latency but maximum flexibility — swap any component independently.

| Sample | Framework | Transport | Key Feature |
|--------|-----------|-----------|-------------|
| [livekit-transcribe-polly](cascading/livekit-transcribe-polly/) | LiveKit Agents | WebRTC | Transcribe + Nova Lite + Polly |
| [langchain-transcribe-polly](cascading/langchain-transcribe-polly/) | LangChain | WebSocket | LangChain agent + custom VAD |

## Which Sample Should I Start With?

- **Production-ready reference** → [strands-sonic](bidi-streaming/strands-sonic/) (most complete, AgentCore deployment)
- **Understand the protocol** → [bedrock-sonic](bidi-streaming/bedrock-sonic/) (raw SDK, no abstractions)
- **Open-source framework** → [pipecat-sonic](bidi-streaming/pipecat-sonic/) (Pipecat pipeline)
- **WebRTC + multi-participant** → [livekit-sonic](bidi-streaming/livekit-sonic/) (LiveKit Agents)
- **Flexible STT/LLM/TTS** → [livekit-transcribe-polly](cascading/livekit-transcribe-polly/) (swap any component)
