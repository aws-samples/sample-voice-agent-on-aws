# Nova Sonic Voice Agent Skill

A coding skill for building real-time voice agents from scratch using [Amazon Nova Sonic](https://docs.aws.amazon.com/nova/latest/userguide/speech.html) and [Strands Agents BidiAgent](https://strandsagents.com/latest/user-guide/concepts/multimodal/speech-to-speech/). Works with Kiro, Claude Code, and other AI coding assistants.

## What This Skill Does

Guides AI coding assistants to scaffold and build a complete voice agent project with:

- **WebSocket server** — FastAPI + BidiAgent orchestrator with Amazon Nova Sonic
- **Custom tools** — `@tool` decorated functions invoked mid-conversation
- **Sub-agents** — Full Strands Agent instances used as tools for complex reasoning
- **Browser client** — Web Audio API mic capture and audio playback

## When To Use This Skill

- Building a voice agent from scratch
- Working with Amazon Nova Sonic or BidiAgent
- Adding speech-to-speech, real-time voice, or audio streaming to a project
- Adding tools or sub-agents to a voice agent

## When NOT To Use This Skill

- Migrating an existing text agent → use `text-agent-to-strands-voice-agent` skill instead
- TTS/STT without a live agent loop
- Deployment or infrastructure only

## Skill Contents

```
nova-sonic-voice-agent/
├── SKILL.md                        # Main skill instructions and code patterns
├── README.md                       # This file
└── references/
    ├── server-reference.md         # Full server implementation details
    ├── client-reference.md         # Full browser client implementation
    └── sub-agent-patterns.md       # Sub-agent design patterns and examples
```

---

## Register and Use in Kiro

Kiro uses a `.kiro/skills/` directory in your workspace to discover skills.

### Step 1 — Copy the skill into your project

```bash
mkdir -p .kiro/skills
cp -r skills/nova-sonic-voice-agent .kiro/skills/nova-sonic-voice-agent
```

### Step 2 — Use it

Open Kiro and start a conversation. When you mention building a voice agent, Nova Sonic, or BidiAgent, Kiro automatically loads the skill and follows its instructions.

Example prompts:
- "Build me a voice agent with Amazon Nova Sonic"
- "Create a real-time speech-to-speech agent with tools"
- "Add a finance sub-agent to my voice agent"

### How it works in Kiro

Kiro reads the `SKILL.md` front-matter (`name` and `description` fields) to decide when to activate the skill. When a user prompt matches the trigger conditions in the description, Kiro loads `SKILL.md` into context and follows its instructions to generate code. The `references/` folder provides additional detail that Kiro pulls in as needed.

---

## Register and Use in Claude Code

Claude Code uses a `CLAUDE.md` file in your project root for persistent instructions.

### Option A — Reference the skill file (recommended)

Create or edit `CLAUDE.md` in your project root and add:

```markdown
## Voice Agent Skill

When I ask about building voice agents with Amazon Nova Sonic or Strands BidiAgent,
read and follow the instructions in these files:

- skills/nova-sonic-voice-agent/SKILL.md (main instructions)
- skills/nova-sonic-voice-agent/references/server-reference.md (server details)
- skills/nova-sonic-voice-agent/references/client-reference.md (browser client details)
- skills/nova-sonic-voice-agent/references/sub-agent-patterns.md (sub-agent patterns)
```

### Option B — Inline the skill content

Open `skills/nova-sonic-voice-agent/SKILL.md` from the file explorer, copy its contents, and paste it into your `CLAUDE.md` file.

### Step 2 — Use it

Start Claude Code and ask it to build a voice agent:

```
> Build a real-time voice agent with Amazon Nova Sonic that can check the weather
> Create a voice agent with a finance sub-agent
> Scaffold a BidiAgent project with a browser client
```

Claude Code reads `CLAUDE.md` on every interaction, sees the skill reference, and follows the patterns in `SKILL.md` when generating code.

### How it works in Claude Code

Claude Code loads `CLAUDE.md` at the start of every session. When you reference skill files, Claude Code reads them on demand when the topic is relevant. The skill provides project structure, code patterns, and implementation details so Claude Code generates consistent, working voice agent code.

---

## Related

- **Power**: `powers/voice-agent-nova-sonic-strands/` — The Kiro power this skill is derived from
- **Skill**: `skills/text-agent-to-strands-voice-agent/` — For migrating existing text agents to voice
