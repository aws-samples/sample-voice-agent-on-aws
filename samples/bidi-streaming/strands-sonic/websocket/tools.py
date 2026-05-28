"""Default tools for the voice agent."""

import time
from datetime import datetime, timezone
from strands import tool


@tool
def get_current_time() -> str:
    """Get the current system date and time in UTC.

    Returns the current date and time in UTC in a human-readable format.
    """
    now = datetime.now(timezone.utc)
    return f"The current date and time is {now.strftime('%A, %B %d, %Y at %I:%M %p')} UTC."


@tool
def get_weather(location: str) -> str:
    """Get the current weather for a location. IMPORTANT: This tool takes approximately 15 seconds to complete as it fetches real-time data from external weather services. Before calling this tool, always tell the user something like "Hold on while I check the weather for you, this might take a moment."

    Args:
        location: City name or location to get weather for (e.g. "Seattle", "New York", "London")
    """
    # Simulate a slow external API call (15 seconds) to demo async tool processing
    time.sleep(15)

    weather_data = {
        "seattle": "Cloudy, 58 degrees Fahrenheit, light rain expected later today.",
        "new york": "Sunny, 75 degrees Fahrenheit, clear skies with a gentle breeze.",
        "san francisco": "Foggy, 62 degrees Fahrenheit, clearing by afternoon.",
        "london": "Overcast, 55 degrees Fahrenheit, chance of showers this evening.",
        "tokyo": "Partly cloudy, 72 degrees Fahrenheit, humid with a high of 78.",
        "los angeles": "Sunny, 82 degrees Fahrenheit, dry and warm all day.",
    }
    location_lower = location.lower().strip()
    if location_lower in weather_data:
        return f"Current weather in {location}: {weather_data[location_lower]}"
    else:
        return f"Current weather in {location}: Pleasant, around 70 degrees Fahrenheit with partly cloudy skies."
