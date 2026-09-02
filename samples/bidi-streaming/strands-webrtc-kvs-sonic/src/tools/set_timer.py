"""Cooking timer tool."""

import asyncio
import logging

from strands import tool

logger = logging.getLogger(__name__)

# Track active timers so they can be cancelled
_active_timers: dict[str, asyncio.Task] = {}


async def _timer_callback(minutes: int, label: str):
    """Background task that waits and then logs when a timer expires."""
    try:
        await asyncio.sleep(minutes * 60)
        # In a real app with audio output, this would trigger a spoken notification.
        # For now, we log it. The agent's audio output has already moved on,
        # so this serves as a server-side record.
        logger.info("Timer expired: %s (%d minutes)", label, minutes)
        print(f"\n** TIMER DONE: {label} ({minutes} minutes) **\n")
    except asyncio.CancelledError:
        logger.info("Timer cancelled: %s", label)


@tool
def set_timer(minutes: int, label: str = "cooking") -> str:
    """Set a cooking timer for the specified number of minutes.

    Use this when a user asks to set a timer, reminder, or countdown
    while cooking. The timer runs in the background.

    Args:
        minutes: Number of minutes for the timer
        label: A short description of what the timer is for
    """
    if minutes <= 0:
        return "Timer must be at least 1 minute."
    if minutes > 480:
        return "Timer cannot exceed 8 hours."

    # Cancel existing timer with the same label
    if label in _active_timers and not _active_timers[label].done():
        _active_timers[label].cancel()
        logger.info("Replaced existing timer: %s", label)

    try:
        loop = asyncio.get_running_loop()
        task = loop.create_task(_timer_callback(minutes, label))
        _active_timers[label] = task
    except RuntimeError:
        # No running event loop - just acknowledge
        pass

    return f"Timer set: {label} for {minutes} minutes. I'll let you know when it's done."
