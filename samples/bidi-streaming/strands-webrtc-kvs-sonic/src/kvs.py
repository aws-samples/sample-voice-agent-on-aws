"""KVS signaling channel management for WebRTC TURN credentials."""

import logging
import os

import boto3

logger = logging.getLogger(__name__)

channel_arn = None
_https_endpoint = None


def init(channel_name=None, region=None):
    global channel_arn, _https_endpoint
    channel_name = channel_name or os.environ.get("KVS_CHANNEL_NAME", "voice-agent-webrtc")
    region = region or os.environ.get("AWS_REGION", "us-east-1")

    client = boto3.client("kinesisvideo", region_name=region)
    try:
        resp = client.describe_signaling_channel(ChannelName=channel_name)
        channel_arn = resp["ChannelInfo"]["ChannelARN"]
    except client.exceptions.ResourceNotFoundException:
        resp = client.create_signaling_channel(ChannelName=channel_name, ChannelType="SINGLE_MASTER")
        channel_arn = resp["ChannelARN"]

    logger.info("KVS signaling channel: %s", channel_arn)

    resp = client.get_signaling_channel_endpoint(
        ChannelARN=channel_arn,
        SingleMasterChannelEndpointConfiguration={"Protocols": ["HTTPS"], "Role": "MASTER"},
    )
    _https_endpoint = resp["ResourceEndpointList"][0]["ResourceEndpoint"]


def get_ice_servers(region=None, client_id=None):
    region = region or os.environ.get("AWS_REGION", "us-east-1")
    client = boto3.client("kinesis-video-signaling", region_name=region, endpoint_url=_https_endpoint)
    params = {"ChannelARN": channel_arn, "Service": "TURN"}
    if client_id:
        params["ClientId"] = client_id
    return client.get_ice_server_config(**params)["IceServerList"]


def get_rtc_ice_servers(region=None, client_id=None, turn_only=False):
    from aiortc import RTCIceServer

    servers = []
    for s in get_ice_servers(region, client_id):
        urls = [u for u in s["Uris"] if u.startswith("turn:")] if turn_only else s["Uris"]
        if urls:
            servers.append(RTCIceServer(urls=urls, username=s.get("Username"), credential=s.get("Password")))
    return servers
