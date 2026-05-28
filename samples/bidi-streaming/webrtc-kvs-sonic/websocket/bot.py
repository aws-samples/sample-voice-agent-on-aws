"""WebRTC Voice Agent with Nova Sonic via KVS.

FastAPI server that bridges WebRTC audio from the browser to Nova Sonic
using KVS TURN servers. Routes ICE config, WebRTC offer/answer, and
ICE candidate exchange through /invocations.

Based on: https://github.com/awslabs/amazon-bedrock-agentcore-samples/tree/main/01-tutorials/01-AgentCore-runtime/06-bi-directional-streaming-webrtc
"""

import argparse
import asyncio
import os
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime

import requests
import uvicorn
from aiortc import RTCConfiguration, RTCPeerConnection, RTCSessionDescription
from aiortc.sdp import candidate_from_sdp
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

import kvs
from audio import OutputTrack
from nova_sonic import run_session

load_dotenv(override=True)

CHANNEL_NAME = os.getenv("KVS_CHANNEL_NAME", "voice-agent-webrtc")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# Active peer connections, keyed by pc_id
peer_connections = {}

# Credential refresh task handle
_credential_refresh_task = None


# ---------------------------------------------------------------------------
# IMDS credential helpers (same pattern as strands-sonic/bedrock-sonic/pipecat-sonic servers)
# ---------------------------------------------------------------------------


def get_imdsv2_token():
    """Get IMDSv2 token for secure metadata access."""
    try:
        resp = requests.put(
            "http://169.254.169.254/latest/api/token",
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
            timeout=2,
        )
        if resp.status_code == 200:
            return resp.text
    except Exception:
        pass
    return None


def get_credentials_from_imds():
    """Retrieve IAM role credentials from EC2 IMDS."""
    result = {
        "success": False, "credentials": None,
        "role_name": None, "method_used": None, "error": None,
    }
    try:
        token = get_imdsv2_token()
        headers = {"X-aws-ec2-metadata-token": token} if token else {}
        result["method_used"] = "IMDSv2" if token else "IMDSv1"

        role_resp = requests.get(
            "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
            headers=headers, timeout=2,
        )
        if role_resp.status_code != 200:
            result["error"] = f"Failed to retrieve IAM role: HTTP {role_resp.status_code}"
            return result

        role_name = role_resp.text.strip()
        result["role_name"] = role_name

        creds_resp = requests.get(
            f"http://169.254.169.254/latest/meta-data/iam/security-credentials/{role_name}",
            headers=headers, timeout=2,
        )
        if creds_resp.status_code != 200:
            result["error"] = f"Failed to retrieve credentials: HTTP {creds_resp.status_code}"
            return result

        creds = creds_resp.json()
        result["success"] = True
        result["credentials"] = {
            "AccessKeyId": creds["AccessKeyId"],
            "SecretAccessKey": creds["SecretAccessKey"],
            "Token": creds["Token"],
            "Expiration": creds["Expiration"],
        }
    except Exception as e:
        result["error"] = str(e)
    return result


async def refresh_credentials_from_imds():
    """Background task to refresh credentials from IMDS before expiry."""
    logger.info("Starting credential refresh task")
    while True:
        try:
            imds_result = get_credentials_from_imds()
            if imds_result["success"]:
                creds = imds_result["credentials"]
                os.environ["AWS_ACCESS_KEY_ID"] = creds["AccessKeyId"]
                os.environ["AWS_SECRET_ACCESS_KEY"] = creds["SecretAccessKey"]
                os.environ["AWS_SESSION_TOKEN"] = creds["Token"]
                logger.info(f"✅ Credentials refreshed ({imds_result['method_used']})")

                try:
                    expiration = datetime.fromisoformat(
                        creds["Expiration"].replace("Z", "+00:00")
                    )
                    now = datetime.now(expiration.tzinfo)
                    time_until_expiration = (expiration - now).total_seconds()
                    refresh_interval = min(max(time_until_expiration - 300, 60), 3600)
                    logger.info(f"   Next refresh in {refresh_interval:.0f}s")
                except Exception:
                    refresh_interval = 3600

                await asyncio.sleep(refresh_interval)
            else:
                logger.error(f"Failed to refresh credentials: {imds_result['error']}")
                await asyncio.sleep(300)
        except asyncio.CancelledError:
            logger.info("Credential refresh task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in credential refresh: {e}")
            await asyncio.sleep(300)


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _credential_refresh_task

    # Load credentials from IMDS if not already in environment
    if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
        logger.info("✅ Using credentials from environment (local mode)")
    else:
        logger.info("🔄 Fetching credentials from EC2 IMDS...")
        imds_result = get_credentials_from_imds()
        if imds_result["success"]:
            creds = imds_result["credentials"]
            os.environ["AWS_ACCESS_KEY_ID"] = creds["AccessKeyId"]
            os.environ["AWS_SECRET_ACCESS_KEY"] = creds["SecretAccessKey"]
            os.environ["AWS_SESSION_TOKEN"] = creds["Token"]
            logger.info(f"✅ Credentials loaded ({imds_result['method_used']})")
            _credential_refresh_task = asyncio.create_task(refresh_credentials_from_imds())
        else:
            logger.error(f"❌ Failed to fetch credentials: {imds_result['error']}")

    kvs.init(CHANNEL_NAME, AWS_REGION)
    yield

    # Cleanup
    if _credential_refresh_task and not _credential_refresh_task.done():
        _credential_refresh_task.cancel()
        try:
            await _credential_refresh_task
        except asyncio.CancelledError:
            pass

    for pc in peer_connections.values():
        await pc.close()


app = FastAPI(title="WebRTC Voice Agent (KVS + Nova Sonic)", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/ping")
async def ping():
    """Health check for AgentCore Runtime."""
    return JSONResponse({"status": "Healthy", "time_of_last_update": int(time.time())})


@app.post("/invocations")
async def invocations(request: dict, background_tasks: BackgroundTasks):
    """Main endpoint — routes ICE config, offer/answer, and ICE candidate actions."""
    action = request.get("action")

    if action == "ice_config":
        return _handle_ice_config()
    elif action == "offer":
        return await _handle_offer(request.get("data", {}), background_tasks)
    elif action == "ice_candidate":
        return await _handle_ice_candidate(request.get("data", {}))
    elif action == "disconnect":
        return await _handle_disconnect(request.get("data", {}))

    return {"status": "healthy"}


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------


def _handle_ice_config():
    """Return KVS TURN/STUN server credentials for the browser."""
    return {
        "iceServers": [
            {
                "urls": server["Uris"],
                "username": server.get("Username"),
                "credential": server.get("Password"),
            }
            for server in kvs.get_ice_servers(AWS_REGION, client_id="web-client")
        ]
    }


async def _handle_offer(data, background_tasks):
    """Accept a WebRTC offer, create a peer connection, return an answer."""
    ice_servers = kvs.get_rtc_ice_servers(
        AWS_REGION, client_id="server", turn_only=data.get("turnOnly", False)
    )

    pc = RTCPeerConnection(RTCConfiguration(iceServers=ice_servers))
    audio_out = OutputTrack()
    pc.addTrack(audio_out)

    pc_id = f"pc_{len(peer_connections)}"
    peer_connections[pc_id] = pc

    @pc.on("track")
    async def on_track(track):
        if track.kind == "audio":
            background_tasks.add_task(run_session, track, audio_out, AWS_REGION, pc_id)

    @pc.on("iceconnectionstatechange")
    async def on_ice_state():
        logger.info(f"ICE state: {pc.iceConnectionState}")

    await pc.setRemoteDescription(
        RTCSessionDescription(sdp=data["sdp"], type=data["type"])
    )
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return {
        "pc_id": pc_id,
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type,
    }


async def _handle_disconnect(data):
    """Close and remove a peer connection."""
    pc = peer_connections.pop(data.get("pc_id"), None)
    if pc:
        await pc.close()
    return {"status": "success"}


async def _handle_ice_candidate(data):
    """Add trickled ICE candidates to an existing peer connection."""
    pc = peer_connections.get(data.get("pc_id"))
    if not pc:
        return {"status": "success"}

    for candidate_data in data.get("candidates", []):
        try:
            raw = candidate_data.get("candidate", "")
            if raw.startswith("candidate:"):
                raw = raw.split(":", 1)[1]

            candidate = candidate_from_sdp(raw)
            candidate.sdpMid = candidate_data.get("sdp_mid")
            candidate.sdpMLineIndex = candidate_data.get("sdp_mline_index")
            await pc.addIceCandidate(candidate)
        except Exception as e:
            logger.error(f"ICE candidate error: {e}")

    return {"status": "success"}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WebRTC Voice Agent (KVS + Nova Sonic)")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8080")))
    parser.add_argument("-v", "--verbose", action="count")
    args = parser.parse_args()

    logger.remove(0)
    logger.add(sys.stderr, level="TRACE" if args.verbose else "DEBUG")
    uvicorn.run(app, host=args.host, port=args.port)
