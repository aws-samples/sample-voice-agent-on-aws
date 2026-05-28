# Text Agent to Nova Sonic Voice Agent — Skill

A coding skill that guides the migration of any text-based agent into a real-time voice agent using Strands BidiAgent with Amazon Nova Sonic. Works with Kiro, Claude Code, and other AI coding assistants.

Strands BidiAgent provides bidirectional audio streaming — it takes your existing system prompt and @tool functions and runs them as a live speech-to-speech agent over WebSocket.

## What This Skill Does

Guides AI coding assistants to migrate a text agent to voice, covering:

| Part | What It Covers |
|------|---------------|
| Frontend | Browser WebSocket client with Web Audio API mic capture (16kHz PCM), audio playback, text input fallback, config event with system prompt |
| Orchestrator | FastAPI + Strands BidiAgent + BidiNovaSonicModel server, voice prompt optimization rules (brevity, number spelling, confirmations, no structured output), tool integration via @tool decorators or MCP Gateway |

Additional content:

- System dependency callouts (aws_sdk_bedrock_runtime, pyaudio, portaudio)
- Voice prompt rewriting guide with complete before/after examples
- Three migration examples (LangChain, OpenAI function-calling, custom Bedrock Converse)

## When To Use This Skill

- Migrating an existing text-based agent to voice
- Converting a chatbot to a Nova Sonic voice agent
- Rewriting a system prompt for voice interaction
- Porting tools from another framework (LangChain, OpenAI, etc.) to BidiAgent

## When NOT To Use This Skill

- Building a voice agent from scratch → use `nova-sonic-voice-agent` skill instead
- TTS/STT without a live agent loop
- Deployment or infrastructure only

## Skill Contents

```
text-agent-to-strands-voice-agent/
├── SKILL.md                              # Main skill — 2-part migration guide
├── README.md                             # This file
├── references/
│   ├── voice-prompt-guide.md             # Detailed prompt rewriting reference
│   ├── server-reference.md               # Production server details (splitting, observability)
│   └── client-reference.md               # Audio capture/playback, Python CLI, event handling
└── examples/
    ├── langchain-migration/              # LangChain create_react_agent → BidiAgent
    ├── openai-migration/                 # OpenAI function-calling → BidiAgent
    └── custom-migration/                 # Bedrock Converse toolSpec → BidiAgent
```

---

## Register and Use in Kiro

Kiro uses a `.kiro/skills/` directory in your workspace to discover skills.

### Step 1 — Copy the skill into your project

```bash
mkdir -p .kiro/skills
cp -r skills/text-agent-to-strands-voice-agent .kiro/skills/text-agent-to-strands-voice-agent
```

### Step 2 — Use it

Open Kiro and start a conversation. When you mention migrating a text agent to voice, converting a chatbot, or rewriting prompts for speech, Kiro automatically loads the skill and follows its instructions.

Example prompts:
- "Migrate my LangChain agent to a Nova Sonic voice agent"
- "Convert this text chatbot to real-time voice"
- "Rewrite my system prompt for voice interaction"

### How it works in Kiro

Kiro reads the `SKILL.md` front-matter (`name` and `description` fields) to decide when to activate the skill. When a user prompt matches the trigger conditions, Kiro loads `SKILL.md` into context and follows its migration instructions. The `references/` and `examples/` folders provide additional detail that Kiro pulls in as needed.

---

## Register and Use in Claude Code

Claude Code uses a `CLAUDE.md` file in your project root for persistent instructions.

### Option A — Reference the skill file (recommended)

Create or edit `CLAUDE.md` in your project root and add:

```markdown
## Text-to-Voice Migration Skill

When I ask about migrating a text agent to voice, converting a chatbot to Nova Sonic,
or rewriting prompts for speech, read and follow the instructions in these files:

- skills/text-agent-to-strands-voice-agent/SKILL.md (main migration guide)
- skills/text-agent-to-strands-voice-agent/references/voice-prompt-guide.md (prompt rewriting)
- skills/text-agent-to-strands-voice-agent/references/server-reference.md (server details)
- skills/text-agent-to-strands-voice-agent/references/client-reference.md (browser client)
```

### Option B — Inline the skill content

Open `skills/text-agent-to-strands-voice-agent/SKILL.md` from the file explorer, copy its contents, and paste it into your `CLAUDE.md` file.

### Step 2 — Use it

Start Claude Code and ask it to migrate your agent:

```
> Migrate my LangChain agent to a real-time voice agent with Nova Sonic
> Convert this OpenAI function-calling bot to BidiAgent
> Rewrite this system prompt for voice — it currently returns JSON
```

Claude Code reads `CLAUDE.md` on every interaction, sees the skill reference, and follows the migration patterns in `SKILL.md` when generating code.

### How it works in Claude Code

Claude Code loads `CLAUDE.md` at the start of every session. When you reference skill files, Claude Code reads them on demand when the topic is relevant. The skill provides migration steps, prompt rewriting rules, and framework-specific examples so Claude Code generates consistent, working voice agent code from your existing text agent.

---

## Related

- **Skill**: `skills/nova-sonic-voice-agent/` — For building a voice agent from scratch
- **Power**: `powers/voice-agent-nova-sonic-strands/` — The Kiro power these skills are derived from

## Source

This skill is sourced from [aws-samples/amazon-nova-samples](https://github.com/aws-samples/amazon-nova-samples/tree/main/skills/text-agent-to-strands-voice-agent).
