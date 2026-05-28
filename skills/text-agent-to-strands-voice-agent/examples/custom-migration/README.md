# Custom Bedrock Converse Migration Example

Migrates a custom Bedrock Converse agent (using `toolSpec` directly) to a Strands BidiAgent voice agent with Nova Sonic.

## Before (`text_agent.py`)

A custom agent using Bedrock Converse API with `toolSpec` tool definitions.

## After (`voice_agent.py`)

The same tools running as a real-time voice agent via BidiAgent + Nova Sonic.

## Key Changes

1. System prompt rewritten for voice
2. Bedrock `toolSpec` definitions converted to Strands `@tool` decorators
3. Converse API loop replaced with `BidiAgent.run()` over WebSocket
4. Added FastAPI server with WebSocket endpoint
