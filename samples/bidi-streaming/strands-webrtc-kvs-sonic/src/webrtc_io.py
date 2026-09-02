"""BidiInput/BidiOutput adapters bridging aiortc tracks to Strands BidiAgent."""

import base64
import logging

import av
from aiortc.mediastreams import MediaStreamError

logger = logging.getLogger(__name__)

INPUT_SAMPLE_RATE = 16000
_resampler = av.AudioResampler(format="s16", layout="mono", rate=INPUT_SAMPLE_RATE)


class WebRTCBidiInput:
    """Reads audio frames from an aiortc track and yields bidi_audio_input events."""

    def __init__(self, track):
        self._track = track
        self._frame_count = 0

    async def __call__(self):
        try:
            frame = await self._track.recv()
        except MediaStreamError:
            raise StopAsyncIteration
        resampled = _resampler.resample(frame)
        pcm = b"".join(f.planes[0] for f in resampled) if resampled else b""
        if not pcm:
            return await self()
        self._frame_count += 1
        if self._frame_count % 500 == 1:
            logger.info("WebRTCBidiInput: sent %d audio frames (%d bytes)", self._frame_count, len(pcm))
        return {
            "type": "bidi_audio_input",
            "audio": base64.b64encode(pcm).decode("utf-8"),
            "format": "pcm",
            "sample_rate": INPUT_SAMPLE_RATE,
            "channels": 1,
        }


class WebRTCBidiOutput:
    """Receives BidiOutputEvents and routes audio to OutputTrack."""

    def __init__(self, output_track):
        self._output_track = output_track

    async def __call__(self, event):
        if not isinstance(event, dict):
            return
        event_type = event.get("type")
        if event_type == "bidi_audio_stream":
            audio_bytes = base64.b64decode(event["audio"])
            self._output_track.add_audio(audio_bytes)
        elif event_type == "bidi_interruption":
            self._output_track.clear()
