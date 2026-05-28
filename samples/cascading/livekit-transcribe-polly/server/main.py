"""LiveKit Agent Worker — Sandwich Architecture (Transcribe + Nova Lite + Polly).

Uses the LiveKit Agents framework with:
- Amazon Transcribe for STT (speech-to-text)
- Amazon Nova 2 Lite on Bedrock for LLM reasoning
- Amazon Polly for TTS (text-to-speech)

This is the "sandwich" pattern: STT → LLM → TTS, as opposed to the native
speech-to-speech approach used in livekit-sonic.
"""

from datetime import datetime, timezone

from livekit import agents
from livekit.agents import AgentSession, Agent, AutoSubscribe, function_tool
from livekit.plugins import aws


@function_tool()
async def get_current_time() -> str:
    """Get the current system date and time in UTC."""
    now = datetime.now(timezone.utc)
    return f"The current date and time is {now.strftime('%A, %B %d, %Y at %I:%M %p')} UTC."


async def entrypoint(ctx: agents.JobContext):
    """Main entrypoint — connects to LiveKit room and starts the sandwich pipeline."""
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # STT: Amazon Transcribe (streaming)
    stt = aws.STT()

    # LLM: Amazon Nova 2 Lite on Bedrock
    llm = aws.LLM(model="us.amazon.nova-2-lite-v1:0")

    # TTS: Amazon Polly
    tts = aws.TTS(voice="Matthew")

    # Create the agent with tools
    agent = Agent(
        instructions=(
            "You are a friendly and helpful voice assistant. "
            "Be warm, conversational, and concise. Keep responses to one or two sentences. "
            "You have access to a get_current_time tool for time-related questions."
        ),
        tools=[get_current_time],
    )

    # Create session with the sandwich pipeline
    session = AgentSession(
        stt=stt,
        llm=llm,
        tts=tts,
    )

    # Start the session
    await session.start(
        room=ctx.room,
        agent=agent,
    )


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
