# OpenAI Function-Calling Migration Example

Migrates an OpenAI function-calling text agent to a Strands BidiAgent voice agent with Nova Sonic.

## Before (`text_agent.py`)

An OpenAI chat completion agent with function-calling tools.

## After (`voice_agent.py`)

The same tools running as a real-time voice agent via BidiAgent + Nova Sonic.

## Key Changes

1. System prompt rewritten for voice
2. OpenAI function schemas converted to Strands `@tool` decorators
3. Chat completion loop replaced with `BidiAgent.run()` over WebSocket
4. Added FastAPI server with WebSocket endpoint
