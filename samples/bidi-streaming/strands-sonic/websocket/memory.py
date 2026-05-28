"""AgentCore Memory integration for the voice agent.

Provides helpers to load and store conversation turns using
Amazon Bedrock AgentCore Memory. Gracefully degrades if memory
is not configured or unavailable.
"""

import logging
import uuid
from typing import Optional

from bedrock_agentcore.memory import MemorySessionManager
from bedrock_agentcore.memory.constants import ConversationalMessage, MessageRole

logger = logging.getLogger(__name__)


class VoiceAgentMemory:
    """Manages conversation memory for voice agent sessions."""

    def __init__(self, memory_id: str, region: str):
        self.memory_id = memory_id
        self.region = region

    def generate_session_id(self) -> str:
        """Generate a new unique session ID."""
        return f"voice-session-{uuid.uuid4().hex[:12]}"

    def load_history(self, actor_id: str, session_id: str, k: int = 10) -> list[dict]:
        """Load last k turns from memory using list_events API directly.

        Returns messages in a format suitable for injecting into the system prompt.
        """
        try:
            import boto3
            client = boto3.client('bedrock-agentcore', region_name=self.region)
            
            response = client.list_events(
                memoryId=self.memory_id,
                actorId=actor_id,
                sessionId=session_id,
                maxResults=k,
            )
            
            events = response.get('events', [])
            logger.info(f"🧠 list_events returned {len(events)} events")

            messages = []
            for event in events:
                payload = event.get('payload', [])
                for item in payload:
                    conv = item.get('conversational', {})
                    if conv:
                        role = conv.get('role', '').lower()
                        content = conv.get('content', {}).get('text', '')
                        if role and content:
                            messages.append({
                                "role": role,
                                "content": [{"text": content}],
                            })

            # Sort by timestamp (events may come in reverse order)
            # The events are already ordered by eventTimestamp from the API
            
            logger.info(
                f"✅ Loaded {len(messages)} turns from memory "
                f"(actor={actor_id}, session={session_id})"
            )
            return messages

        except Exception as e:
            logger.warning(f"⚠️ Failed to load memory: {e}")
            import traceback
            traceback.print_exc()
            return []

    def store_turn(self, actor_id: str, session_id: str, role: str, content: str):
        """Store a single conversation turn to memory.

        Args:
            actor_id: User identifier.
            session_id: Session identifier.
            role: Message role ('user' or 'assistant').
            content: Text content of the message.
        """
        try:
            logger.info(f"🧠 [AgentCore Memory] Storing {role} turn to memory...")
            logger.info(f"   Memory ID: {self.memory_id}")
            logger.info(f"   Actor: {actor_id}, Session: {session_id}")
            logger.info(f"   Content preview: {content[:80]}{'...' if len(content) > 80 else ''}")

            session_mgr = MemorySessionManager(
                memory_id=self.memory_id,
                region_name=self.region,
            )
            session = session_mgr.create_memory_session(
                actor_id=actor_id,
                session_id=session_id,
            )
            msg_role = MessageRole.USER if role == "user" else MessageRole.ASSISTANT
            session.add_turns(
                messages=[ConversationalMessage(content, msg_role)]
            )
            logger.info(f"✅ [AgentCore Memory] Successfully stored {role} turn to memory (actor={actor_id}, session={session_id})")

        except Exception as e:
            logger.error(f"❌ [AgentCore Memory] Failed to store turn to memory: {e}")
            import traceback
            traceback.print_exc()
