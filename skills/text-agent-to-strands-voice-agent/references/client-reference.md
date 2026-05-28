# Client Implementation Reference

Detailed reference for the browser and Python CLI clients. For the minimal version, see SKILL.md Part 1.

## Browser Client

The browser client uses Web Audio API to capture microphone input, stream it as base64-encoded PCM over WebSocket, and play back audio responses.

### Audio Capture with AudioWorklet

```javascript
class PCMProcessor extends AudioWorkletProcessor {
    process(inputs) {
        const input = inputs[0][0];
        if (input) {
            const pcm = new Int16Array(input.length);
            for (let i = 0; i < input.length; i++) {
                pcm[i] = Math.max(-32768, Math.min(32767, input[i] * 32768));
            }
            this.port.postMessage(pcm.buffer);
        }
        return true;
    }
}
registerProcessor('pcm-processor', PCMProcessor);
```

### Audio Playback

```javascript
let nextPlayTime = 0;

function playAudioChunk(base64Audio) {
    const pcm = base64ToInt16Array(base64Audio);
    const float32 = new Float32Array(pcm.length);
    for (let i = 0; i < pcm.length; i++) {
        float32[i] = pcm[i] / 32768;
    }
    const buffer = playbackCtx.createBuffer(1, float32.length, sampleRate);
    buffer.getChannelData(0).set(float32);
    const source = playbackCtx.createBufferSource();
    source.buffer = buffer;
    source.connect(playbackCtx.destination);
    const startTime = Math.max(playbackCtx.currentTime, nextPlayTime);
    source.start(startTime);
    nextPlayTime = startTime + buffer.duration;
}
```

### Event Types

| Event type | Fields | Action |
|-----------|--------|--------|
| `bidi_audio_stream` | `audio` (base64) | Decode and play through speaker |
| `bidi_transcript_stream` | `role`, `text` | Display transcript |
| `tool_use_stream` | `current_tool_use` | Show tool call in progress |
| `tool_result` | `tool_result` | Show tool completion |
| `system` | `message` | Show system message |
| `memory_history` | `turns`, `session_id` | Display loaded history |

## Python CLI Client

For testing without a browser. Uses `pyaudio` for mic capture and speaker playback:

```python
import asyncio, json, base64, pyaudio, websockets

RATE, CHANNELS, CHUNK = 16000, 1, 1024

async def run(url, system_prompt):
    async with websockets.connect(url) as ws:
        await ws.send(json.dumps({
            "type": "config",
            "voice": "matthew",
            "model_id": "amazon.nova-2-sonic-v1:0",
            "input_rate": RATE,
            "output_rate": RATE,
            "system_prompt": system_prompt,
        }))

        pa = pyaudio.PyAudio()
        mic = pa.open(format=pyaudio.paInt16, channels=CHANNELS,
                      rate=RATE, input=True, frames_per_buffer=CHUNK)
        spk = pa.open(format=pyaudio.paInt16, channels=CHANNELS,
                      rate=RATE, output=True, frames_per_buffer=CHUNK)

        async def send_audio():
            while True:
                data = mic.read(CHUNK, exception_on_overflow=False)
                await ws.send(json.dumps({
                    "type": "bidi_audio_input",
                    "audio": base64.b64encode(data).decode(),
                    "format": "pcm", "sample_rate": RATE, "channels": 1
                }))
                await asyncio.sleep(0.01)

        async def recv_events():
            async for msg in ws:
                evt = json.loads(msg)
                if evt.get("type") == "bidi_audio_stream":
                    spk.write(base64.b64decode(evt["audio"]))
                elif evt.get("type") == "bidi_transcript_stream":
                    print(f"[{evt.get('role','')}] {evt.get('text','')}")

        await asyncio.gather(send_audio(), recv_events())
```

## Migration Checklist

- [ ] System prompt is voice-optimized (see `references/voice-prompt-guide.md`)
- [ ] Sample rates match the model (16kHz for Nova Sonic)
- [ ] Text input fallback works for accessibility
- [ ] Audio playback is gapless (no clicks between chunks)
- [ ] Tool results are spoken naturally, not as raw JSON
- [ ] Agent greets, uses caller's name, and says goodbye
