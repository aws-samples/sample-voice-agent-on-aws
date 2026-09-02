"""WebRTC + WebSocket server bridging browser audio to Strands BidiAgent and Nova Sonic.

Exposes:
  POST /invocations — WebRTC signaling (ice_config, offer, ice_candidate, disconnect)
  GET  /ws          — Legacy WebSocket endpoint (kept for transition)
  GET  /ping        — Health check
"""

import json
import logging
import os
import time

from fastapi import BackgroundTasks, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from aiortc import RTCConfiguration, RTCPeerConnection, RTCSessionDescription
from aiortc.sdp import candidate_from_sdp

from strands.experimental.bidi import BidiAgent
from strands.experimental.bidi.models import BidiNovaSonicModel
from strands.experimental.bidi.tools import stop_conversation

from audio_track import OutputTrack
from config import AWS_REGION, CLOUDFRONT_ORIGIN, NOVA_SONIC_VOICE, SYSTEM_PROMPT
from tools import convert_units, nutrition_lookup, search_recipes, set_timer
from webrtc_io import WebRTCBidiInput, WebRTCBidiOutput

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)
logging.getLogger("awscrt").setLevel(logging.CRITICAL)

if not logging.getLogger().isEnabledFor(logging.DEBUG):

    class _PingFilter(logging.Filter):
        def filter(self, record):
            return "GET /ping" not in record.getMessage()

    logging.getLogger("uvicorn.access").addFilter(_PingFilter())

IS_CONTAINER = os.environ.get("CONTAINER_ENV")

_kvs_initialized = False


def _ensure_kvs():
    global _kvs_initialized
    if not _kvs_initialized and IS_CONTAINER:
        import kvs
        kvs.init()
        _kvs_initialized = True

app = FastAPI(title="Family Recipe Assistant Voice Server")

_cors_origins = ["http://localhost:5173"]
if CLOUDFRONT_ORIGIN:
    _cors_origins.append(f"https://{CLOUDFRONT_ORIGIN}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared Nova Sonic model config
sonic_model = BidiNovaSonicModel(
    provider_config={
        "audio": {
            "voice": NOVA_SONIC_VOICE,
            "input_rate": 16000,
            "output_rate": 24000,
            "channels": 1,
            "format": "pcm",
        },
        "inference": {},
    },
    client_config={"region": AWS_REGION},
)

TOOLS = [search_recipes, set_timer, nutrition_lookup, convert_units, stop_conversation]

# Active peer connections
peer_connections = {}


@app.get("/ping")
async def ping():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# WebRTC signaling via HTTP
# ---------------------------------------------------------------------------


@app.post("/invocations")
async def invocations(request: dict, background_tasks: BackgroundTasks):
    action = request.get("action")
    if action == "ice_config":
        return _handle_ice_config()
    elif action == "offer":
        return await _handle_offer(request.get("data", {}), background_tasks)
    elif action == "ice_candidate":
        return await _handle_ice_candidate(request.get("data", {}))
    elif action == "disconnect":
        return await _handle_disconnect(request.get("data", {}))
    return {"status": "ok"}


def _handle_ice_config():
    if not IS_CONTAINER:
        return {"iceServers": []}
    _ensure_kvs()
    import kvs as _kvs

    return {
        "iceServers": [
            {"urls": s["Uris"], "username": s.get("Username"), "credential": s.get("Password")}
            for s in _kvs.get_ice_servers(AWS_REGION, client_id="web-client")
        ]
    }


async def _handle_offer(data, background_tasks):
    if IS_CONTAINER:
        _ensure_kvs()
        import kvs as _kvs

        ice_servers = _kvs.get_rtc_ice_servers(AWS_REGION, client_id="server", turn_only=True)
    else:
        ice_servers = []

    pc = RTCPeerConnection(RTCConfiguration(iceServers=ice_servers))
    audio_out = OutputTrack()
    pc.addTrack(audio_out)

    pc_id = f"pc_{len(peer_connections)}"
    peer_connections[pc_id] = pc

    @pc.on("track")
    async def on_track(track):
        if track.kind == "audio":
            background_tasks.add_task(_run_agent_session, track, audio_out, pc_id)

    @pc.on("iceconnectionstatechange")
    async def on_ice_state():
        logger.info("ICE state [%s]: %s", pc_id, pc.iceConnectionState)

    await pc.setRemoteDescription(RTCSessionDescription(sdp=data["sdp"], type=data["type"]))

    # Add browser's ICE candidates if included in the offer
    for c in data.get("candidates", []):
        try:
            raw = c.get("candidate", "")
            if raw.startswith("candidate:"):
                raw = raw.split(":", 1)[1]
            candidate = candidate_from_sdp(raw)
            candidate.sdpMid = c.get("sdp_mid")
            candidate.sdpMLineIndex = c.get("sdp_mline_index")
            await pc.addIceCandidate(candidate)
        except Exception as e:
            logger.error("ICE candidate error: %s", e)

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    sdp = pc.localDescription.sdp
    # In deployed mode, strip non-relay candidates from SDP so browser only sees TURN relays
    if IS_CONTAINER:
        sdp = "\r\n".join(
            line for line in sdp.split("\r\n")
            if not line.startswith("a=candidate:") or "typ relay" in line
        )

    return {"pc_id": pc_id, "sdp": sdp, "type": pc.localDescription.type}


async def _handle_ice_candidate(data):
    pc = peer_connections.get(data.get("pc_id"))
    if not pc:
        logger.warning("ICE candidate: pc_id %s not found", data.get("pc_id"))
        return {"status": "ok"}
    for c in data.get("candidates", []):
        try:
            raw = c.get("candidate", "")
            if raw.startswith("candidate:"):
                raw = raw.split(":", 1)[1]
            candidate = candidate_from_sdp(raw)
            candidate.sdpMid = c.get("sdp_mid")
            candidate.sdpMLineIndex = c.get("sdp_mline_index")
            await pc.addIceCandidate(candidate)
            logger.info("Added ICE candidate: %s", c.get("candidate", "")[:80])
        except Exception as e:
            logger.error("ICE candidate error: %s", e)
    return {"status": "ok"}


async def _handle_disconnect(data):
    pc = peer_connections.pop(data.get("pc_id"), None)
    if pc:
        await pc.close()
    return {"status": "ok"}


async def _run_agent_session(audio_track, output_track, pc_id):
    """Run BidiAgent with WebRTC I/O adapters."""
    logger.info("Starting BidiAgent session for %s", pc_id)
    agent = BidiAgent(
        model=sonic_model,
        tools=TOOLS,
        system_prompt=SYSTEM_PROMPT,
    )
    try:
        await agent.run(
            inputs=[WebRTCBidiInput(audio_track)],
            outputs=[WebRTCBidiOutput(output_track)],
        )
    except (Exception, StopAsyncIteration) as e:
        if type(e).__name__ != "StopAsyncIteration":
            logger.exception("Agent session error [%s]: %s", pc_id, type(e).__name__)
    finally:
        try:
            await agent.stop()
        except Exception:
            pass
        logger.info("Agent session ended [%s]", pc_id)


# ---------------------------------------------------------------------------
# Legacy WebSocket endpoint (kept for transition)
# ---------------------------------------------------------------------------

MAX_WS_MESSAGE_BYTES = 64 * 1024


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    agent = BidiAgent(model=sonic_model, tools=TOOLS, system_prompt=SYSTEM_PROMPT)
    session_start = time.monotonic()

    async def _receive():
        data = await ws.receive_json()
        if len(json.dumps(data)) > MAX_WS_MESSAGE_BYTES:
            raise ValueError("WebSocket message too large")
        return data

    async def _send(data):
        try:
            await ws.send_json(data)
        except TypeError:
            pass

    try:
        await ws.accept()
        await agent.run(inputs=[_receive], outputs=[_send])
    except WebSocketDisconnect:
        logger.info("WS client disconnected")
    except Exception as e:
        logger.exception("WS session error: %s", type(e).__name__)
    finally:
        logger.info("WS session ended (%.1fs)", time.monotonic() - session_start)
        try:
            await agent.stop()
        except Exception:
            pass
        try:
            await ws.close()
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn

    host = "0.0.0.0" if IS_CONTAINER else "127.0.0.1"
    uvicorn.run(app, host=host, port=8080)
