# LangChain Migration Example

Migrates a LangChain `create_react_agent` text agent to a Strands BidiAgent voice agent with Nova Sonic.

## Before (`text_agent.py`)

A LangChain ReAct agent with tools for account balance and mortgage rates.

## After (`voice_agent.py`)

The same tools and logic running as a real-time voice agent via BidiAgent + Nova Sonic.

## Key Changes

1. System prompt rewritten for voice (brevity, confirmations, natural numbers)
2. LangChain tools converted to Strands `@tool` decorators
3. Agent loop replaced with `BidiAgent.run()` over WebSocket
4. Added FastAPI server with WebSocket endpoint
