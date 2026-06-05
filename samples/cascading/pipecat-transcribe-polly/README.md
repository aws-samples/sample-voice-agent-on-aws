# Pipecat Voice Agent — Cascading Architecture (Transcribe + Nova 2 Lite + Polly)

A voice agent using the [Pipecat](https://github.com/pipecat-ai/pipecat) framework with the classic "cascading" pipeline: **Amazon Transcribe** (STT) → **Amazon Nova 2 Lite** (LLM) → **Amazon Polly** (TTS). Unlike the native speech-to-speech approach in `pipecat-sonic`, this sample processes audio through three separate stages, wired together as a Pipecat pipeline of frame processors.

## Architecture

![Pipecat Cascading Architecture](../../../assets/pipecat-transcribe-polly-architecture.png)

```
browser mic
    │  (WebRTC audio frames)
    ▼
transport.input()
    ▼
AWSTranscribeSTTService     # speech → text   (Amazon Transcribe streaming)
    ▼
user_aggregator             # add user turn to conversation context
    ▼
AWSBedrockLLMService        # text → text     (Amazon Nova 2 Lite, Converse)
    ▼
AWSPollyTTSService          # text → speech   (Amazon Polly)
    ▼
transport.output()
    ▼
assistant_aggregator        # add bot turn to conversation context
    │  (WebRTC audio frames)
    ▼
browser speakers
```

Pipecat owns the hard parts of real-time voice: WebRTC audio transport, Silero voice-activity detection, turn-taking, interruption handling, and frame scheduling between the three services. You just declare the pipeline — the order of processors *is* the data flow.

## Prerequisites

- Python 3.11+ (Pipecat requirement)
- AWS credentials with access to Amazon Transcribe, Bedrock (Nova 2 Lite enabled in *Model access*), and Polly
- A region where all three are available. `us-east-1` works; note Polly's `generative` engine is region-limited (fall back to `neural` if needed).

## Setup

### 1. Install dependencies

```bash
cd samples/cascading/pipecat-transcribe-polly/server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Provide AWS credentials

The Pipecat AWS services use the standard boto3 credential chain, so any of these work — pick one:

- **An existing profile / SSO / instance role** (recommended). If `aws sts get-caller-identity` already succeeds, you're done — skip to step 3.
- **Static keys**, exported in the shell you'll run the bot from:

  ```bash
  export AWS_ACCESS_KEY_ID=your-access-key
  export AWS_SECRET_ACCESS_KEY=your-secret-key
  # export AWS_SESSION_TOKEN=your-session-token   # only for temporary credentials
  ```

### 3. Set the application environment variables

`bot.py` reads these at startup (via `python-dotenv`). The defaults below work for most users — set only the ones you want to change. Two ways to provide them:

**Option A — export in your shell** (simplest for a quick run):

```bash
export AWS_REGION=us-east-1
export NOVA_MODEL_ID=us.amazon.nova-2-lite-v1:0
export POLLY_VOICE_ID=Ruth
export POLLY_ENGINE=generative
export TRANSCRIBE_LANGUAGE=en-US
```

**Option B — a `.env` file** in the `server/` directory (persists across runs). Create `server/.env` with:

```dotenv
# Region for Transcribe, Bedrock (Nova 2 Lite), and Polly
AWS_REGION=us-east-1

# LLM — Nova 2 Lite cross-region inference profile
NOVA_MODEL_ID=us.amazon.nova-2-lite-v1:0

# TTS — Polly voice and engine
POLLY_VOICE_ID=Ruth
POLLY_ENGINE=generative

# STT — Transcribe streaming language code
TRANSCRIBE_LANGUAGE=en-US
```

> **Heads up:** `bot.py` calls `load_dotenv(override=True)`, so values in `.env` override your shell environment. If you rely on an AWS profile or SSO for credentials, do **not** add empty `AWS_ACCESS_KEY_ID=` / `AWS_SECRET_ACCESS_KEY=` lines to `.env` — blank values will override your working credentials and break authentication. Either omit them entirely or comment them out.

See the [Configuration](#configuration) section below for what each variable controls.

## Run

```bash
python bot.py
```

Pipecat's development runner starts a local WebRTC server and prints a URL:

```
🚀 Bot ready!
   → Open: http://localhost:7860
```

Open it in your browser, allow microphone access, and click **Connect**. The agent greets you, then you can talk. First launch takes ~20s while Pipecat downloads the Silero VAD model; subsequent runs are fast.

> The browser client is served automatically by Pipecat's `webrtc` dev transport — there's no separate JavaScript build to run.

## Key Components

| File | Purpose |
|------|---------|
| `server/bot.py` | Pipecat pipeline: Transcribe STT + Nova 2 Lite LLM + Polly TTS, plus session lifecycle |
| `server/requirements.txt` | Python dependencies (`pipecat-ai` with AWS + Silero + transport extras) |

`server/bot.py` is organized into three clearly separated parts:

1. **Service construction** — `AWSTranscribeSTTService`, `AWSBedrockLLMService` (Nova 2 Lite), and `AWSPollyTTSService`, each configured from environment variables.
2. **Pipeline assembly** — the ordered list of processors. The order is the data flow; audio must be transcribed before the LLM sees it and synthesized before playback.
3. **Lifecycle** — `on_client_connected` seeds a greeting, `on_client_disconnected` tears the pipeline down.

## Configuration

All configuration is via environment variables (see [Setup](#setup) for how to set them):

| Variable | Default | Notes |
|----------|---------|-------|
| `AWS_REGION` | `us-east-1` | Region for all three services. |
| `NOVA_MODEL_ID` | `us.amazon.nova-2-lite-v1:0` | Bedrock cross-region inference profile. |
| `POLLY_VOICE_ID` | `Ruth` | Any Polly voice. Generative voices: `Ruth`, `Matthew`, `Stephen`, `Amy`. |
| `POLLY_ENGINE` | `generative` | Set to `neural` if generative isn't available in your region. |
| `TRANSCRIBE_LANGUAGE` | `en-US` | Transcribe streaming language code. |

### STT (Amazon Transcribe)

```python
stt = AWSTranscribeSTTService(
    region=AWS_REGION,
    settings=AWSTranscribeSTTService.Settings(language=_language(TRANSCRIBE_LANGUAGE)),
)
```

### LLM (Amazon Nova 2 Lite)

```python
llm = AWSBedrockLLMService(
    model=NOVA_MODEL_ID,
    aws_region=AWS_REGION,
    settings=AWSBedrockLLMService.Settings(temperature=0.7, top_p=0.9, max_tokens=1024),
)
```

Any Bedrock text model that supports the Converse API can drop in here — same `AWSBedrockLLMService`, just a different `model` ID. For the current list of model IDs and their cross-region inference profiles, see [Supported foundation models in Amazon Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html).

### TTS (Amazon Polly)

```python
tts = AWSPollyTTSService(
    region=AWS_REGION,
    settings=AWSPollyTTSService.Settings(
        voice=POLLY_VOICE, engine=POLLY_ENGINE, language=_language(TRANSCRIBE_LANGUAGE),
    ),
)
```

## Swapping Providers

Pipecat's value is that providers are interchangeable. To experiment, change one service line and its import — the rest of the pipeline is unchanged. For example, swap Transcribe for Deepgram (`DeepgramSTTService`), Nova for another Bedrock model (still `AWSBedrockLLMService`, different `model`), or Polly for ElevenLabs (`ElevenLabsTTSService`). Add the matching `pipecat-ai[...]` extra to `requirements.txt` and set the relevant API key as an environment variable.

## Deploy

This `server/bot.py` is compatible with Pipecat Cloud without code changes. See the [Pipecat deployment docs](https://docs.pipecat.ai/pipecat-cloud/introduction). For an AWS-hosted variant (FastAPI + WebSocket + AgentCore), see the [pipecat-sonic](../../bidi-streaming/pipecat-sonic/) sample in this repo.

## Troubleshooting

- **Polly `ValidationException` on engine** — `generative` isn't in your region; set `POLLY_ENGINE=neural` or change `AWS_REGION`.
- **Bedrock `AccessDeniedException`** — enable Nova 2 Lite in the Bedrock *Model access* page and confirm the `bedrock:InvokeModel` permission.
- **No transcript / no response** — check the browser granted mic access and that your AWS credentials are valid (`aws sts get-caller-identity`).
- **First run is slow** — Silero VAD downloads on first launch; subsequent runs are fast.

## Resources

- [Pipecat Framework](https://github.com/pipecat-ai/pipecat)
- [Pipecat AWS Plugin](https://github.com/pipecat-ai/pipecat/tree/main/src/pipecat/services/aws)
- [Amazon Transcribe](https://aws.amazon.com/transcribe/)
- [Amazon Polly](https://aws.amazon.com/polly/)
- [Amazon Bedrock](https://aws.amazon.com/bedrock/)
