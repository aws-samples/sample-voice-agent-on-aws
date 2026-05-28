# Browser Client

## Overview

The browser client captures microphone audio, sends it to the voice agent over WebSocket, and plays back audio responses. It consists of a Python HTTP server (`client.py`) that serves a single-page HTML application (`index.html`).

The client is intentionally simple — it does not manage profiles, system prompts, or model configuration. All agent configuration (system prompt, voice, model) is hardcoded on the WebSocket server side. The client only handles audio I/O and display.

## Folder: `client/`

Create this folder with the following files:

- `client.py` — Python HTTP server that serves the web page
- `index.html` — Browser UI with microphone capture and audio playback
- `requirements.txt` — Python dependencies (minimal)

---

## client.py

A simple Python HTTP server that serves the client page. No profiles, no config API — just serves the HTML.

```python
#!/usr/bin/env python3
import argparse
import os
import sys
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse


class VoiceClientHandler(BaseHTTPRequestHandler):
    """HTTP handler that serves the voice agent client."""

    websocket_url = None

    def log_message(self, format, *args):
        sys.stderr.write(f"[{self.log_date_time_string()}] {format % args}\n")

    def do_GET(self):
        parsed_path = urlparse(self.path)

        if parsed_path.path in ("/", "/index.html"):
            self.serve_client_page()
        else:
            self.send_error(404, "Not found")

    def serve_client_page(self):
        """Serve the HTML client with the WebSocket URL injected."""
        try:
            html_path = os.path.join(os.path.dirname(__file__), "index.html")
            with open(html_path, "r", encoding="utf-8") as f:
                html_content = f.read()

            # Inject WebSocket URL
            if self.websocket_url:
                html_content = html_content.replace(
                    "{{WEBSOCKET_URL}}", self.websocket_url
                )
            else:
                html_content = html_content.replace("{{WEBSOCKET_URL}}", "")

            content = html_content.encode()
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.send_header("Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404, "index.html not found")


def main():
    parser = argparse.ArgumentParser(description="Voice Agent Browser Client")
    parser.add_argument(
        "--ws-url",
        default="ws://localhost:8081/ws",
        help="WebSocket server URL (default: ws://localhost:8081/ws)",
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="HTTP server port (default: 8000)"
    )
    parser.add_argument(
        "--no-browser", action="store_true", help="Don't open browser automatically"
    )

    args = parser.parse_args()

    VoiceClientHandler.websocket_url = args.ws_url

    print("=" * 60)
    print("🎙️  Amazon Nova Sonic Voice Agent Client")
    print("=" * 60)
    print(f"🔗 WebSocket: {args.ws_url}")
    print(f"🌐 Server:    http://localhost:{args.port}")
    print(f"💡 Press Ctrl+C to stop")
    print("=" * 60)

    if not args.no_browser:
        webbrowser.open(f"http://localhost:{args.port}")

    httpd = HTTPServer(("", args.port), VoiceClientHandler)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")


if __name__ == "__main__":
    main()
```

---

## index.html

A single-page application with:
- Microphone capture using Web Audio API (ScriptProcessorNode, downsampled to 16kHz PCM mono)
- Audio playback using scheduled AudioBufferSourceNodes
- Chat transcript display with speculative/final transcript handling
- Connect/disconnect button
- Text input as alternative to voice

The client sends a minimal `config` event on connect (just `{"type": "config"}`) to signal readiness. The server uses its own hardcoded settings for voice, model, system prompt, etc.

---

## Audio Logic (JavaScript)

The following sections describe the exact audio implementation patterns to use. These are adapted from the working strands client sample.

### Global State

```javascript
let ws = null;
let audioContext = null;        // For microphone capture
let audioPlaybackContext = null; // For audio output
let isRecording = false;
let isBotSpeaking = false;
let nextPlayTime = 0;
let initialBufferCount = 0;
const INITIAL_BUFFER_CHUNKS = 3;
const SAMPLE_RATE = 16000;      // Amazon Nova Sonic uses 16kHz
```

### Microphone Capture

Uses `ScriptProcessorNode` with a 4096-sample buffer. The browser's native sample rate is downsampled to 16kHz. While the bot is speaking, mic input is suppressed (factor 0.15) to reduce echo while still allowing barge-in.

```javascript
async function startRecording() {
    const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true }
    });

    audioContext = new AudioContext();
    const source = audioContext.createMediaStreamSource(stream);
    const processor = audioContext.createScriptProcessor(4096, 1, 1);

    processor.onaudioprocess = (e) => {
        if (!ws || ws.readyState !== WebSocket.OPEN) return;

        const inputData = e.inputBuffer.getChannelData(0);

        // Suppress mic while bot is speaking (reduce echo, allow barge-in)
        const suppressionFactor = isBotSpeaking ? 0.15 : 1.0;

        // Downsample from browser's native rate to 16kHz
        const downsampleRatio = audioContext.sampleRate / SAMPLE_RATE;
        const outputLength = Math.floor(inputData.length / downsampleRatio);
        const int16Data = new Int16Array(outputLength);

        for (let i = 0; i < outputLength; i++) {
            const sourceIndex = Math.floor(i * downsampleRatio);
            int16Data[i] = Math.max(-32768, Math.min(32767,
                inputData[sourceIndex] * 32768 * suppressionFactor));
        }

        // Convert Int16Array to base64
        const bytes = new Uint8Array(int16Data.buffer);
        let binary = '';
        for (let i = 0; i < bytes.length; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        const base64Audio = btoa(binary);

        ws.send(JSON.stringify({
            type: "bidi_audio_input",
            audio: base64Audio,
            format: "pcm",
            sample_rate: SAMPLE_RATE,
            channels: 1
        }));
    };

    source.connect(processor);
    processor.connect(audioContext.destination);
    isRecording = true;
}

function stopRecording() {
    if (audioContext) {
        audioContext.close();
        audioContext = null;
    }
    isRecording = false;
}
```

### Audio Playback

Uses scheduled `AudioBufferSourceNode` playback. Each incoming audio chunk is decoded from base64 → Int16 → Float32, then scheduled at `nextPlayTime` for gapless playback. The playback context is created lazily on first audio chunk. An active source counter ensures `isBotSpeaking` stays true until all scheduled chunks finish playing.

```javascript
let activeSources = 0; // Track number of playing/scheduled sources

async function playAudioOutput(base64Audio) {
    if (!audioPlaybackContext) {
        audioPlaybackContext = new AudioContext({ sampleRate: SAMPLE_RATE });
        nextPlayTime = 0;
        initialBufferCount = 0;
        activeSources = 0;
    }

    if (audioPlaybackContext.state === 'suspended') {
        await audioPlaybackContext.resume();
    }

    isBotSpeaking = true;

    // Decode base64 to Int16 PCM
    const binaryString = atob(base64Audio);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
    }
    const int16Data = new Int16Array(bytes.buffer);

    // Convert Int16 to Float32
    const float32Data = new Float32Array(int16Data.length);
    for (let i = 0; i < int16Data.length; i++) {
        float32Data[i] = int16Data[i] / 32768.0;
    }

    // Create AudioBuffer
    const buffer = audioPlaybackContext.createBuffer(1, float32Data.length, SAMPLE_RATE);
    buffer.getChannelData(0).set(float32Data);

    initialBufferCount++;

    const currentTime = audioPlaybackContext.currentTime;

    // Reset nextPlayTime if it's fallen behind (gap in audio)
    if (nextPlayTime < currentTime) {
        nextPlayTime = currentTime + 0.05; // Small buffer delay
    }

    // Schedule playback
    const source = audioPlaybackContext.createBufferSource();
    source.buffer = buffer;
    source.connect(audioPlaybackContext.destination);
    source.start(nextPlayTime);
    nextPlayTime += buffer.duration;

    // Track active sources to know when bot finishes speaking
    activeSources++;
    source.onended = () => {
        activeSources--;
        if (activeSources <= 0) {
            activeSources = 0;
            isBotSpeaking = false;
        }
    };
}

function stopBotAudio() {
    isBotSpeaking = false;
    initialBufferCount = 0;
    nextPlayTime = 0;
    activeSources = 0;
    if (audioPlaybackContext) {
        audioPlaybackContext.close();
        audioPlaybackContext = null;
    }
}
```

### WebSocket Connection

```javascript
async function connect() {
    const wsUrl = "{{WEBSOCKET_URL}}"; // Injected by client.py

    ws = new WebSocket(wsUrl);

    ws.onopen = async () => {
        // Send minimal config to signal readiness
        ws.send(JSON.stringify({ type: "config" }));

        // Start recording automatically
        await startRecording();
    };

    ws.onmessage = async (event) => {
        const data = JSON.parse(event.data);

        switch (data.type) {
            case 'bidi_audio_stream':
                await playAudioOutput(data.audio);
                break;

            case 'bidi_transcript_stream':
                // Amazon Nova Sonic sends speculative (is_final=false) then final transcripts
                if (data.is_final === false) {
                    updateSpeculativeTranscript(data.role, data.text);
                } else {
                    finalizeTranscript(data.role, data.text);
                }
                break;

            case 'bidi_interruption':
                // User barged in — stop audio playback
                stopBotAudio();
                break;

            case 'tool_use_stream':
                showToolUse(data.current_tool_use.name);
                break;

            case 'tool_result':
                showToolResult(data.tool_result);
                break;

            case 'system':
                showSystemMessage(data.message);
                break;

            case 'error':
                showError(data.message);
                break;
        }
    };

    ws.onclose = () => {
        stopRecording();
        stopBotAudio();
    };
}

function disconnect() {
    stopRecording();
    if (ws) ws.close();
}
```

### Text Input (Alternative to Voice)

```javascript
function sendTextMessage(text) {
    if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ type: "text_input", text: text }));
}
```

### Transcript Display

Amazon Nova Sonic sends speculative transcripts (`is_final: false`) that get replaced by final transcripts (`is_final: true`). Handle this by maintaining a temporary speculative element:

```javascript
function updateSpeculativeTranscript(role, text) {
    const prefix = role === 'user' ? '🎤 User' : '🔊 Assistant';
    let el = document.getElementById('speculative-msg');
    if (el) {
        el.textContent = `${prefix}: ${text}`;
    } else {
        el = addMessage(`${prefix}: ${text}`, role);
        el.id = 'speculative-msg';
        el.style.opacity = '0.6';
    }
}

function finalizeTranscript(role, text) {
    const prefix = role === 'user' ? '🎤 User' : '🔊 Assistant';
    const speculative = document.getElementById('speculative-msg');
    if (speculative) speculative.remove();
    addMessage(`${prefix}: ${text}`, role);
}
```

---

## UI Layout

```
┌─────────────────────────────────────────┐
│  🎙️ Amazon Nova Sonic Voice Agent              │
├─────────────────────────────────────────┤
│                                         │
│  Chat Transcript Area                   │
│  - 🎤 User: "What's the weather?"      │
│  - 🔊 Assistant: "It's sunny and 72°F" │
│                                         │
├─────────────────────────────────────────┤
│  [Type a message...]          [📤 Send] │
├─────────────────────────────────────────┤
│  [🚀 Start Conversation]  [Status: ⚫]  │
└─────────────────────────────────────────┘
```

---

## requirements.txt

```
# No external dependencies needed — uses Python standard library only
```

The client uses only Python's built-in `http.server` module. No pip packages required.

---

## Running the Client

```bash
cd client
python client.py --ws-url ws://localhost:8081/ws
```

This opens a browser tab automatically. The client connects to the WebSocket server and is ready for voice interaction.

### Command-Line Options

| Flag | Default | Description |
|------|---------|-------------|
| `--ws-url` | `ws://localhost:8081/ws` | WebSocket server URL |
| `--port` | `8000` | HTTP server port |
| `--no-browser` | `false` | Don't auto-open browser |

---

## Event Protocol

### Client → Server

| Event | Description |
|-------|-------------|
| `{"type": "config"}` | Signal readiness (server uses its own hardcoded config) |
| `{"type": "bidi_audio_input", "audio": "<base64>", "format": "pcm", "sample_rate": 16000, "channels": 1}` | Microphone audio chunk |
| `{"type": "text_input", "text": "..."}` | Text input (alternative to voice) |

### Server → Client

| Event | Description |
|-------|-------------|
| `{"type": "system", "message": "..."}` | Status/config acknowledgment |
| `{"type": "bidi_audio_stream", "audio": "<base64>"}` | Audio response from Amazon Nova Sonic |
| `{"type": "bidi_transcript_stream", "role": "...", "text": "...", "is_final": bool}` | Real-time transcript (speculative or final) |
| `{"type": "bidi_interruption"}` | User barged in — stop playback |
| `{"type": "tool_use_stream", "current_tool_use": {"name": "..."}}` | Tool invocation in progress |
| `{"type": "tool_result", "tool_result": {...}}` | Tool result |
| `{"type": "error", "message": "..."}` | Error message |

---

## Audio Format Details

- **Sample rate**: 16000 Hz (Amazon Nova Sonic native rate)
- **Bit depth**: 16-bit signed integer (PCM)
- **Channels**: 1 (mono)
- **Encoding**: Base64 over JSON
- **Echo cancellation**: Enabled via `getUserMedia` constraints
- **Noise suppression**: Enabled via `getUserMedia` constraints
- **Frame size**: 4096 samples at native rate, downsampled to ~2730 samples at 16kHz
- **Echo suppression**: Mic gain reduced to 0.15 while bot is speaking (allows barge-in)

## Key Behaviors

- **Auto-start recording**: Microphone capture begins automatically after WebSocket connects.
- **Barge-in support**: Mic is not muted during playback — just suppressed. Amazon Nova Sonic detects user speech and sends `bidi_interruption` to stop playback.
- **Gapless playback**: Audio chunks are scheduled at `nextPlayTime` for seamless output.
- **Speculative transcripts**: Partial transcripts appear dimmed and are replaced by final versions.
- **Lazy AudioContext**: Playback context is created on first audio chunk (avoids browser autoplay restrictions).
