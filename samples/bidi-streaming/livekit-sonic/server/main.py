"""LiveKit Agent Worker — Amazon Nova Sonic.

Runs the LiveKit agent worker that connects to a LiveKit server
and handles voice sessions using Amazon Nova Sonic 2.0.

Based on: https://aws.amazon.com/blogs/machine-learning/build-real-time-conversational-ai-experiences-using-amazon-nova-sonic-and-livekit/
"""

from datetime import datetime, timezone

from livekit import agents
from livekit.agents import AgentSession, Agent, AutoSubscribe, function_tool
from livekit.plugins.aws.experimental.realtime import RealtimeModel


@function_tool()
async def get_current_time() -> str:
    """Get the current system date and time in UTC."""
    now = datetime.now(timezone.utc)
    return f"The current date and time is {now.strftime('%A, %B %d, %Y at %I:%M %p')} UTC."


async def entrypoint(ctx: agents.JobContext):
    """Main entrypoint — connects to LiveKit room and starts Nova Sonic session."""
    # Connect to the LiveKit server
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # Initialize the Amazon Nova Sonic agent with tools
    agent = Agent(
        instructions=(
            "You are a friendly and helpful voice assistant powered by Amazon Nova Sonic. "
            "Be warm, conversational, and concise. Keep responses to one or two sentences. "
            "You have access to a get_current_time tool for time-related questions."
        ),
        tools=[get_current_time],
    )
    session = AgentSession(llm=RealtimeModel())

    # Start the session in the specified room
    await session.start(
        room=ctx.room,
        agent=agent,
    )


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
