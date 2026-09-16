"""
RideNow AI — Conversation Session Memory
========================================
Stores conversation history per user in Redis (or in-memory fallback)
with a sliding window of recent turns and automated TTL expiration.
"""

import json
import logging
from typing import List, Dict, Any

from app.core.config import settings
from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)


def _get_history_key(user_id: int) -> str:
    return f"chat_history:user:{user_id}"


async def get_conversation_history(user_id: int, max_turns: int = 10) -> List[Dict[str, str]]:
    """
    Retrieve recent conversation turns for a user in chronological order.
    Returns list of {"role": "user"|"assistant", "content": "..."}.
    """
    client = get_redis_client()
    key = _get_history_key(user_id)
    limit = max_turns * 2

    raw_items = await client.lrange(key, -limit, -1)
    history = []
    for item in raw_items:
        try:
            history.append(json.loads(item))
        except Exception:
            pass

    return history


async def append_message_to_history(user_id: int, role: str, content: str):
    """Append a user or assistant message to the end of conversation history."""
    client = get_redis_client()
    key = _get_history_key(user_id)

    payload = json.dumps({"role": role, "content": content})
    # Store at end of chronological sequence
    await client.rpush(key, payload)

    # Trim to max turns
    limit = settings.CHAT_MAX_HISTORY_TURNS * 2
    await client.ltrim(key, -limit, -1)

    # Reset TTL
    await client.expire(key, settings.REDIS_CHAT_TTL_SECONDS)


async def clear_conversation_history(user_id: int):
    """Clear chat history for a user."""
    client = get_redis_client()
    await client.delete(_get_history_key(user_id))
