# Skills

Skills are structured prompts that guide AI coding assistants to generate voice agent code. They contain architecture patterns, code templates, and implementation details that an AI assistant follows when you ask it to build or migrate a voice agent.

## What's a Skill?

A skill is a `SKILL.md` file with:
- **Trigger conditions** — when the AI should activate the skill (e.g., "build a voice agent")
- **Project structure** — what files and folders to create
- **Code patterns** — working examples the AI follows when generating code
- **Reference files** — detailed implementation guides for server, client, and sub-agents

## Available Skills

| Skill | What It Does |
|-------|-------------|
| [nova-sonic-voice-agent](nova-sonic-voice-agent/) | Build a real-time voice agent from scratch using Strands BidiAgent + Nova Sonic |
| [text-agent-to-strands-voice-agent](text-agent-to-strands-voice-agent/) | Migrate an existing text-based agent (LangChain, OpenAI, etc.) to a Nova Sonic voice agent |

## Supported AI Assistants

| Assistant | How to Register |
|-----------|----------------|
| **Kiro** | Copy skill folder to `.kiro/skills/` — auto-detected by trigger conditions |
| **Claude Code** | Reference skill files in `CLAUDE.md` at project root |
| **Cursor** | Copy `SKILL.md` to `.cursor/rules/` |
| **Any other** | Paste `SKILL.md` content into system instructions or context |

See each skill's README for detailed registration instructions.
