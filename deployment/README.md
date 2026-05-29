# Deployment

Scripts and utilities for deploying voice agents and setting up the workshop environment.

## Subfolders

### `agentcore/` — Amazon Bedrock AgentCore Runtime

Deploy voice agent samples to AgentCore Runtime — a managed serverless environment for AI agents on AWS.

| File | Purpose |
|------|---------|
| `deploy.py` | Deploy agent + MCP Gateways + Memory + A2A sub-agents |
| `cleanup.py` | Tear down all deployed resources |
| `start_client.sh` | Launch browser client with SigV4 presigned URL |
| `websocket_helpers.py` | SigV4 presigned URL generation for WebSocket connections |
| `agent_role.json` | IAM policy for the agent execution role |
| `trust_policy.json` | IAM trust policy for AgentCore |
| `requirements.txt` | Python dependencies for deployment scripts |

**Usage:**

```bash
pip install -r deployment/agentcore/requirements.txt
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Deploy
python deployment/agentcore/deploy.py strands-sonic

# Start client
./deployment/agentcore/start_client.sh strands-sonic

# Clean up
python deployment/agentcore/cleanup.py strands-sonic
```

Supported samples: `strands-sonic`, `bedrock-sonic`, `pipecat-sonic`, `langchain-transcribe-polly`, `webrtc-kvs-sonic`

### `workshop/` — Workshop Environment Setup

Utilities for the EC2-based workshop environment.

| File | Purpose |
|------|---------|
| `set-env.sh` | Set AWS credentials (IMDS), Account ID, CloudFront proxy URLs |

**Usage:**

```bash
source deployment/workshop/set-env.sh
```

Sets: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AWS_DEFAULT_REGION`, `ACCOUNT_ID`, `WORKSHOP_PASSWORD`, `CLOUDFRONT_BASE_URL`, `WS_BASE_URL`, `CLIENT_BASE_URL`
