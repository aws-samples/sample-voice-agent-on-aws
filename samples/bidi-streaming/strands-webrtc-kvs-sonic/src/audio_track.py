"""WebRTC output audio track using av.AudioFifo for frame-exact chunking."""

import asyncio
import fractions
import time

import av
from aiortc.mediastreams import AudioFrame, MediaStreamTrack

OUTPUT_SAMPLE_RATE = 24000
BYTES_PER_SAMPLE = 2
FRAME_DURATION_MS = 20
SAMPLES_PER_FRAME = OUTPUT_SAMPLE_RATE * FRAME_DURATION_MS // 1000  # 480

_SILENCE = AudioFrame(format="s16", layout="mono", samples=SAMPLES_PER_FRAME)
_SILENCE.sample_rate = OUTPUT_SAMPLE_RATE
_SILENCE.planes[0].update(bytes(SAMPLES_PER_FRAME * BYTES_PER_SAMPLE))


class OutputTrack(MediaStreamTrack):
    """Streams Nova Sonic audio responses to the browser via WebRTC."""

    kind = "audio"

    def __init__(self):
        super().__init__()
        self._fifo = av.AudioFifo()
        self._timestamp = 0
        self._start_time = None
        self._frame_count = 0
        self._muted = False

    async def recv(self):
        if self._start_time is None:
            self._start_time = time.time()

        delay = self._start_time + self._frame_count * (FRAME_DURATION_MS / 1000) - time.time()
        if delay > 0:
            await asyncio.sleep(delay)

        if self._muted:
            frame = _SILENCE
        else:
            frame = self._fifo.read(SAMPLES_PER_FRAME, partial=False)
            if frame is None:
                frame = _SILENCE

        frame.pts = self._timestamp
        frame.time_base = fractions.Fraction(1, OUTPUT_SAMPLE_RATE)
        self._timestamp += SAMPLES_PER_FRAME
        self._frame_count += 1
        return frame

    def add_audio(self, audio_bytes):
        self._muted = False
        frame = AudioFrame(format="s16", layout="mono", samples=len(audio_bytes) // BYTES_PER_SAMPLE)
        frame.planes[0].update(audio_bytes)
        frame.sample_rate = OUTPUT_SAMPLE_RATE
        self._fifo.write(frame)

    def clear(self):
        self._muted = True
        self._fifo = av.AudioFifo()
