# Kiro Powers

This directory contains Kiro powers for voice agent development workflows.

## Available Powers

| Power | Path | Description |
|-------|------|-------------|
| **Voice Agent (Sonic + Strands BidiAgent + AgentCore)** | `voice-agent-sonic-strands-bidiagent-agentcore/` | Build voice agents with Strands Agents BidiAgent, Amazon Nova Sonic, and Amazon Bedrock AgentCore |

## Install in Kiro

To install a power locally in Kiro:

1. Open the Command Palette (Cmd+Shift+P)
2. Search for "Add Power" or use the Powers panel in the sidebar
3. Select "Local path"
4. Point to the specific power subfolder, e.g.:
   ```
   powers/voice-agent-sonic-strands-bidiagent-agentcore/
   ```

## Structure

```
powers/
├── README.md                                          # This file
└── voice-agent-sonic-strands-bidiagent-agentcore/     # Voice agent power
    ├── POWER.md                                       # Root power file
    └── steering/                                      # Capability-specific guides
        ├── bidiagent-basics.md
        ├── websocket-server.md
        ├── mcp-gateway-tools.md
        ├── a2a-subagents.md
        ├── agentcore-deployment.md
        ├── memory-integration.md
        ├── telemetry-observability.md
        └── client-browser.md
```

## Adding More Powers

Additional powers can be added as sibling folders (e.g., `powers/pipecat-nova-sonic/`, `powers/langchain-cascading/`).
