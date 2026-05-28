# Sub-Agents (A2A)

Text-based Strands agents deployed as A2A servers on AgentCore Runtime. The voice agent communicates with these sub-agents via the [Agent-to-Agent (A2A) protocol](https://a2a-protocol.org/).

## Architecture

```
Voice Agent (BidiAgent + Nova Sonic)
    │
    ├── A2A ──→ auth_agent      (authenticate users, verify identity)
    ├── A2A ──→ banking_agent   (balances, transactions, transfers)
    ├── A2A ──→ mortgage_agent  (rates, calculations, eligibility)
    │
    └── MCP ──→ faq_kb_mcp      (RAG via Bedrock Knowledge Base)
```

## Sub-Agents

| Agent | Port | Tools | Description |
|-------|------|-------|-------------|
| `auth_agent` | 9000 | `authenticate_user`, `verify_identity` | User authentication and identity verification |
| `banking_agent` | 9000 | `get_account_balance`, `get_recent_transactions`, `transfer_funds`, `get_account_summary` | Account management and transactions |
| `mortgage_agent` | 9000 | `get_mortgage_rates`, `calculate_mortgage_payment`, `check_mortgage_eligibility`, `get_mortgage_application_status` | Mortgage services |

## Why A2A instead of MCP?

| Aspect | MCP (Tools) | A2A (Sub-Agents) |
|--------|-------------|------------------|
| Interaction | Single tool call → result | Multi-turn conversation with reasoning |
| Intelligence | Stateless function execution | Agent with its own LLM and system prompt |
| Autonomy | Caller decides when/how to use | Sub-agent reasons about how to fulfill request |
| Discovery | Tool list via MCP protocol | Agent Card at `/.well-known/agent-card.json` |
| Protocol | MCP over stdio/SSE | JSON-RPC over HTTP |
| Port | 8000 (AgentCore) | 9000 (AgentCore) |

MCP is ideal for stateless tools (like the FAQ KB that just queries a knowledge base). A2A is better for domain-specific agents that need their own reasoning — the auth agent decides what verification steps are needed, the banking agent validates transfers, the mortgage agent explains eligibility.

## Deployment

Each sub-agent is deployed independently to AgentCore Runtime as an A2A server:

```bash
cd auth_agent
agentcore create --protocol A2A
agentcore deploy
```

After deployment, each agent gets a Runtime ARN that the voice agent uses to invoke it.

## Local Testing

```bash
# Start a sub-agent locally
cd auth_agent
pip install -r requirements.txt
python main.py

# Test with curl (JSON-RPC)
curl -X POST http://localhost:9000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "req-001",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "Authenticate user john with account 1234567890"}],
        "messageId": "msg-001"
      }
    }
  }'
```

## Agent Cards

Each deployed sub-agent exposes an Agent Card at `/.well-known/agent-card.json` for discovery:

```bash
curl http://localhost:9000/.well-known/agent-card.json
```
