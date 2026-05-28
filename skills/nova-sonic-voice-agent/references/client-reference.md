# Browser Client Reference

Complete implementation for the browser-based voice agent client.

## Overview

The client captures microphone audio via Web Audio API, streams it to the server over WebSocket, and plays back audio responses. It consists of a Python HTTP server (`client.py`) that serves a single-page HTML application (`index.html`).

## client.py

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
        try:
            html_path = os.path.join(os.path.dirname(__file__), "index.html")
            with open(html_path, "r", encoding="utf-8") as f:
                html_content = f.read()

            if self.websocket_url:
                html_content = html_content.replace("{{WEBSOCKET_URL}}", self.websocket_url)
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
    parser.add_argument("--ws-url", default="ws://localhost:8081/ws", help="WebSocket server URL")
    parser.add_argument("--port", type=int, default=8000, help="HTTP server port (default: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser automatically")

    args = parser.parse_args()
    VoiceClientHandler.websocket_url = args.ws_url

    print("=" * 60)
    print("🎙️  Nova Sonic Voice Agent Client")
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

## Audio Implementation (JavaScript)

### Global State

```javascript
let ws = null;
let audioContext = null;
let audioPlaybackContext = null;
let isRecording = false;
let isBotSpeaking = false;
let nextPlayTime = 0;
let activeSources = 0;
const SAMPLE_RATE = 16000;
```

### Microphone Capture

Uses ScriptProcessorNode with 4096-sample buffer. Downsamples from browser native rate to 16kHz. Suppresses mic input while bot is speaking (factor 0.15) to reduce echo while allowing barge-in.

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
        const suppressionFactor = isBotSpeaking ? 0.15 : 1.0;
        const downsampleRatio = audioContext.sampleRate / SAMPLE_RATE;
        const outputLength = Math.floor(inputData.length / downsampleRatio);
        const int16Data = new Int16Array(outputLength);

        for (let i = 0; i < outputLength; i++) {
            const sourceIndex = Math.floor(i * downsampleRatio);
            int16Data[i] = Math.max(-32768, Math.min(32767,
                inputData[sourceIndex] * 32768 * suppressionFactor));
        }

        const bytes = new Uint8Array(int16Data.buffer);
        let binary = '';
        for (let i = 0; i < bytes.length; i++) {
            binary += String.fromCharCode(bytes[i]);
        }

        ws.send(JSON.stringify({
            type: "bidi_audio_input",
            audio: btoa(binary),
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

Scheduled AudioBufferSourceNode playback for gapless output. Tracks active sources to know when bot finishes speaking.

```javascript
async function playAudioOutput(base64Audio) {
    if (!audioPlaybackContext) {
        audioPlaybackContext = new AudioContext({ sampleRate: SAMPLE_RATE });
        nextPlayTime = 0;
        activeSources = 0;
    }

    if (audioPlaybackContext.state === 'suspended') {
        await audioPlaybackContext.resume();
    }

    isBotSpeaking = true;

    // Decode base64 → Int16 → Float32
    const binaryString = atob(base64Audio);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
    }
    const int16Data = new Int16Array(bytes.buffer);
    const float32Data = new Float32Array(int16Data.length);
    for (let i = 0; i < int16Data.length; i++) {
        float32Data[i] = int16Data[i] / 32768.0;
    }

    const buffer = audioPlaybackContext.createBuffer(1, float32Data.length, SAMPLE_RATE);
    buffer.getChannelData(0).set(float32Data);

    const currentTime = audioPlaybackContext.currentTime;
    if (nextPlayTime < currentTime) {
        nextPlayTime = currentTime + 0.05;
    }

    const source = audioPlaybackContext.createBufferSource();
    source.buffer = buffer;
    source.connect(audioPlaybackContext.destination);
    source.start(nextPlayTime);
    nextPlayTime += buffer.duration;

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
    const wsUrl = "{{WEBSOCKET_URL}}";
    ws = new WebSocket(wsUrl);

    ws.onopen = async () => {
        ws.send(JSON.stringify({ type: "config" }));
        await startRecording();
    };

    ws.onmessage = async (event) => {
        const data = JSON.parse(event.data);

        switch (data.type) {
            case 'bidi_audio_stream':
                await playAudioOutput(data.audio);
                break;
            case 'bidi_transcript_stream':
                if (data.is_final === false) {
                    updateSpeculativeTranscript(data.role, data.text);
                } else {
                    finalizeTranscript(data.role, data.text);
                }
                break;
            case 'bidi_interruption':
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
```

### Transcript Display

Nova Sonic sends speculative transcripts (`is_final: false`) that get replaced by final ones:

```javascript
function updateSpeculativeTranscript(role, text) {
    const prefix = role === 'user' ? '🎤' : '🔊';
    let el = document.getElementById('speculative-msg');
    if (el) {
        el.textContent = `${prefix} ${text}`;
    } else {
        el = addMessage(`${prefix} ${text}`, role);
        el.id = 'speculative-msg';
        el.style.opacity = '0.6';
    }
}

function finalizeTranscript(role, text) {
    const prefix = role === 'user' ? '🎤' : '🔊';
    const speculative = document.getElementById('speculative-msg');
    if (speculative) speculative.remove();
    addMessage(`${prefix} ${text}`, role);
}
```

### Text Input

```javascript
function sendTextMessage(text) {
    if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ type: "text_input", text: text }));
}
```

## Audio Format Details

| Parameter | Value |
|-----------|-------|
| Sample rate | 16000 Hz |
| Bit depth | 16-bit signed integer (PCM) |
| Channels | 1 (mono) |
| Encoding | Base64 over JSON |
| Echo cancellation | Enabled via getUserMedia |
| Noise suppression | Enabled via getUserMedia |
| Echo suppression | Mic gain × 0.15 while bot speaks |

## requirements.txt

```
# No external dependencies — uses Python standard library only
```

## Running

```bash
cd client
python client.py --ws-url ws://localhost:8081/ws
```

| Flag | Default | Description |
|------|---------|-------------|
| `--ws-url` | `ws://localhost:8081/ws` | WebSocket server URL |
| `--port` | `8000` | HTTP server port |
| `--no-browser` | false | Don't auto-open browser |
