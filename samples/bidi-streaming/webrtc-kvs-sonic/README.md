# WebRTC Voice Agent (KVS + Nova Sonic)

A bidirectional voice agent using **WebRTC** for browser audio transport and **Amazon Nova Sonic** for native speech-to-speech. Uses **Amazon Kinesis Video Streams (KVS)** signaling channels for TURN/STUN server credentials, enabling NAT traversal without a WebSocket relay.

Unlike the WebSocket-based samples (Strands, Sonic, Pipecat), this agent uses WebRTC peer connections for audio — lower latency, no base64 encoding overhead, and native browser media handling.

Based on: [amazon-bedrock-agentcore-samples/06-bi-directional-streaming-webrtc](https://github.com/awslabs/amazon-bedrock-agentcore-samples/tree/main/01-tutorials/01-AgentCore-runtime/06-bi-directional-streaming-webrtc)

## Deploy to AgentCore

```bash
# Install deployment dependencies
pip install -r deployment/agentcore/requirements.txt

# Set your AWS account ID
export ACCOUNT_ID=123456789012

# Set VPC configuration (required — agent needs internet egress for KVS TURN servers)
export SUBNET_IDS=subnet-0123456789abcdef0       # Private subnet with NAT gateway
export SECURITY_GROUP_ID=sg-0123456789abcdef0     # Security group allowing outbound

# Deploy to AgentCore
python deployment/agentcore/deploy.py webrtc-kvs-sonic

# Start the web client
./deployment/agentcore/start_client.sh webrtc-kvs-sonic
```

### VPC Setup (Required)

When AgentCore Runtime is connected to a VPC, it does not have internet access by default — it can only communicate with resources inside the same VPC. This agent needs outbound internet to reach KVS TURN servers, so you must configure your VPC for internet egress.

For full details, see [VPC configuration for AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-vpc.html) and [Internet access considerations](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-vpc.html#internet-access-considerations) in the AgentCore docs.

#### How VPC Connectivity Works

When you configure VPC connectivity, AgentCore creates elastic network interfaces (ENIs) in your VPC using the service-linked role `AWSServiceRoleForBedrockAgentCoreNetwork`. Each ENI gets a private IP from the subnets you specify, and security groups control what the runtime can talk to.

> **Note:** ENIs are shared across agents using the same subnet/security group config. When you delete an agent, the ENI may persist for up to 8 hours before automatic removal.

#### Internet Access Architecture

AgentCore in a public subnet does _not_ get internet access. You need this setup:

1. **Private subnets** — Place the AgentCore Runtime network interfaces in private subnets. AgentCore creates ENIs with private IPs in these subnets.

2. **Public subnet with NAT Gateway** — Deploy a NAT Gateway in a public subnet to provide outbound internet access for the private subnets.

3. **Internet Gateway (IGW)** — Attach an IGW to your VPC so the NAT Gateway can reach the internet.

#### Routing Configuration

Update your subnet route tables:

| Route Table | Destination | Target |
|-------------|-------------|--------|
| Private subnet | `0.0.0.0/0` | NAT Gateway |
| Public subnet | `0.0.0.0/0` | Internet Gateway |

#### Security Group

- Outbound: Allow all outbound traffic (or at minimum TCP/UDP to KVS TURN server endpoints)
- Inbound: Not required — the runtime only initiates outbound connections

Apply the principle of least privilege — allow only the minimum required traffic.

#### Supported Availability Zones

Subnets must be in supported AZs or the configuration will fail. Here are the supported AZ IDs per region:

| Region | Supported AZs |
|--------|---------------|
| us-east-1 (N. Virginia) | `use1-az1`, `use1-az2`, `use1-az4` |
| us-east-2 (Ohio) | `use2-az1`, `use2-az2`, `use2-az3` |
| us-west-2 (Oregon) | `usw2-az1`, `usw2-az2`, `usw2-az3` |
| eu-west-1 (Ireland) | `euw1-az1`, `euw1-az2`, `euw1-az3` |
| eu-central-1 (Frankfurt) | `euc1-az1`, `euc1-az2`, `euc1-az3` |
| ap-southeast-2 (Sydney) | `apse2-az1`, `apse2-az2`, `apse2-az3` |
| ap-northeast-1 (Tokyo) | `apne1-az1`, `apne1-az2`, `apne1-az4` |
| ap-south-1 (Mumbai) | `aps1-az1`, `aps1-az2`, `aps1-az3` |
| ap-southeast-1 (Singapore) | `apse1-az1`, `apse1-az2`, `apse1-az3` |
| ap-northeast-2 (Seoul) | `apne2-az1`, `apne2-az2`, `apne2-az3` |
| eu-west-2 (London) | `euw2-az1`, `euw2-az2`, `euw2-az3` |
| eu-west-3 (Paris) | `euw3-az1`, `euw3-az2`, `euw3-az3` |
| eu-north-1 (Stockholm) | `eun1-az1`, `eun1-az2`, `eun1-az3` |
| ca-central-1 (Canada) | `cac1-az1`, `cac1-az2`, `cac1-az4` |

To check the AZ ID of your subnet:

```bash
aws ec2 describe-subnets --subnet-ids subnet-12345678 --query 'Subnets[0].AvailabilityZoneId'
```

#### VPC Endpoints (If No Internet Access)

If your VPC does not have internet access via NAT Gateway, you need these VPC endpoints for AgentCore to function:

- **Amazon ECR** (for container images): `com.amazonaws.<region>.ecr.dkr` and `com.amazonaws.<region>.ecr.api`
- **Amazon S3** (for ECR layer storage): `com.amazonaws.<region>.s3` (Gateway endpoint)
- **CloudWatch Logs**: `com.amazonaws.<region>.logs`

#### Best Practices

- Configure at least two private subnets in different AZs for high availability
- Place subnets in the same AZs as resources they connect to (reduces cross-AZ latency)
- Use VPC endpoints for AWS services when possible (lower latency, avoids NAT gateway charges)
- Enable VPC Flow Logs for auditing and monitoring

#### IAM Permissions

AgentCore uses the service-linked role `AWSServiceRoleForBedrockAgentCoreNetwork` to create and manage ENIs. This role is created automatically on first VPC configuration. The required permission is included in the `BedrockAgentCoreFullAccess` managed policy.

#### Set VPC Environment Variables

```bash
export SUBNET_IDS=subnet-0123456789abcdef0       # Private subnet (with NAT gateway route)
export SECURITY_GROUP_ID=sg-0123456789abcdef0     # Security group allowing outbound
```

#### Using the `agentcore` CLI Directly (Alternative to `deploy.py`)

```bash
cd samples/bidi-streaming/webrtc-kvs-sonic/websocket

agentcore configure \
  -e bot.py \
  --deployment-type container \
  --disable-memory \
  --vpc \
  --subnets $SUBNET_IDS \
  --security-groups $SECURITY_GROUP_ID \
  --non-interactive

agentcore deploy \
  --env KVS_CHANNEL_NAME=voice-agent-webrtc \
  --env AWS_REGION=us-east-1
```

#### Troubleshooting VPC Connectivity

| Issue | Solution |
|-------|----------|
| Connection timeouts | Verify security group rules, check route tables, confirm target resource is running |
| DNS resolution failures | Ensure DNS resolution is enabled in your VPC, verify DHCP options |
| Missing ENIs | Check IAM permissions for the service-linked role, check service quotas |

### Attach KVS IAM Permissions

The execution role needs KVS and Bedrock permissions. After deployment:

```bash
ROLE_NAME=<role-from-deploy-output>

aws iam put-role-policy \
  --role-name $ROLE_NAME \
  --policy-name kvs-access \
  --policy-document file://webrtc-kvs-sonic/kvs-iam-policy.json

aws iam put-role-policy \
  --role-name $ROLE_NAME \
  --policy-name bedrock-nova-sonic \
  --policy-document file://webrtc-kvs-sonic/bedrock-iam-policy.json
```

### Cleanup

```bash
python deployment/agentcore/cleanup.py webrtc-kvs-sonic
```

## Local Testing

No MCP Gateways required — the agent talks directly to Bedrock and KVS.

```bash
# 1. Install server dependencies
pip install -r samples/bidi-streaming/webrtc-kvs-sonic/websocket/requirements.txt

# 2. Set AWS credentials
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION=us-east-1

# 3. Start the agent (port 8080)
cd samples/bidi-streaming/webrtc-kvs-sonic/websocket
python bot.py

# 4. In another terminal, start the client (port 7860, opens browser)
cd samples/bidi-streaming/webrtc-kvs-sonic/client
pip install -r requirements.txt
python client.py --local
```

Open `http://localhost:7860` and click Connect. Speak into your microphone — the agent responds in real time.

## Architecture

![WebRTC KVS Architecture](../../../assets/webrtc-kvs-sonic-architecture.svg)


The browser captures microphone audio via WebRTC. The agent receives audio frames through `aiortc`, resamples to 16kHz PCM, and streams to Nova Sonic. Responses come back as 24kHz PCM, buffered into WebRTC frames, and played in the browser via `<audio>`.

KVS provides TURN/STUN credentials for NAT traversal — no WebSocket relay needed for the audio path.

## Key Components

| File | Purpose |
|------|---------|
| `websocket/bot.py` | FastAPI server, WebRTC offer/answer, ICE handling, IMDS credentials |
| `websocket/kvs.py` | KVS signaling channel and TURN server helpers |
| `websocket/audio.py` | Audio resampling (av) and WebRTC output track (av.AudioFifo) |
| `websocket/nova_sonic.py` | Nova Sonic bidirectional streaming session |
| `client/client.py` | HTTP server that serves the HTML client and proxies agent calls |
| `client/webrtc-client.html` | Browser-based WebRTC voice client |

## Audio Configuration

| Parameter | Value |
|-----------|-------|
| Input Sample Rate | 16kHz |
| Output Sample Rate | 24kHz |
| Format | 16-bit PCM mono |
| Model | amazon.nova-2-sonic-v1:0 |
| Voice | matthew |
| WebRTC Frame Size | 20ms |

## How It Works

### WebRTC Connection Flow

1. Browser requests ICE config → agent fetches TURN/STUN credentials from KVS
2. Browser creates WebRTC offer → agent creates peer connection and answer
3. ICE candidates are exchanged → NAT traversal via KVS TURN servers
4. Audio track established → agent starts Nova Sonic session

### Audio Flow

- **Browser → Nova Sonic**: WebRTC captures mic → `aiortc` receives frames → `av.AudioResampler` converts to 16kHz/16-bit/mono → base64-encoded and streamed to Nova Sonic
- **Nova Sonic → Browser**: Agent receives audio chunks → raw PCM buffered in `av.AudioFifo` → `OutputTrack` serves fixed-size 20ms frames → WebRTC plays via `<audio>`

## IAM Permissions

The agent needs:
- `kinesisvideo:DescribeSignalingChannel`, `CreateSignalingChannel`, `GetSignalingChannelEndpoint`, `GetIceServerConfig` for KVS
- `bedrock:InvokeModelWithBidirectionalStream` for Nova Sonic

See `kvs-iam-policy.json` and `bedrock-iam-policy.json`.

## Key Dependencies

| Package | Purpose |
|---------|---------|
| `aws-sdk-bedrock-runtime` | Nova Sonic streaming (requires Python 3.12+) |
| `aiortc` | WebRTC peer connections |
| `av` | Audio resampling and frame buffering (FFmpeg) |
| `boto3` | KVS signaling channel and TURN servers |
| `fastapi` / `uvicorn` | HTTP server |
