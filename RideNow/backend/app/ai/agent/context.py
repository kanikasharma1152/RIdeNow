"""
RideNow AI — Structured Conversation Context Engine
===================================================
Manages session-scoped, non-sensitive conversation context in Redis:
- Destination, pickup, coordinates, distance, duration, fare
- Active ride telemetry (ride_id, status, driver_id)
- Pending action safety state (BOOK_RIDE, CANCEL_RIDE)
- Modality-independent (shared seamlessly between Text chat and LiveKit voice)
"""

import json
import logging
import time
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)

CONTEXT_TTL_SECONDS = 1800  # 30 minutes


class ConversationContext(BaseModel):
    user_id: int
    role: str = "passenger"

    # Trip planning context
    pickup: Optional[str] = None
    destination: Optional[str] = None
    pickup_coords: Optional[Dict[str, float]] = None      # {"latitude": ..., "longitude": ...}
    destination_coords: Optional[Dict[str, float]] = None # {"latitude": ..., "longitude": ...}
    distance_km: Optional[float] = None
    estimated_fare: Optional[float] = None
    currency: str = "INR"

    # Active ride tracking
    active_ride_id: Optional[int] = None
    active_ride_status: Optional[str] = None
    driver_id: Optional[int] = None

    # Safety confirmation gate
    pending_action: Optional[str] = None  # "BOOK_RIDE" | "CANCEL_RIDE" | None
    pending_action_data: Optional[Dict[str, Any]] = None

    # Memory of last tool execution
    last_tool_name: Optional[str] = None
    last_tool_result: Optional[Dict[str, Any]] = None

    # Metadata
    last_modality: str = "text"  # "text" | "voice" | "multimodal"
    updated_at: float = Field(default_factory=time.time)


def _context_key(user_id: int) -> str:
    return f"conversation_context:user:{user_id}"


async def get_user_context(user_id: int, role: str = "passenger") -> ConversationContext:
    """
    Retrieve structured conversation context for a user from Redis.
    Returns a fresh context if none exists or if expired.
    """
    client = get_redis_client()
    key = _context_key(user_id)
    try:
        raw = await client.get(key)
        if raw:
            data = json.loads(raw)
            return ConversationContext(**data)
    except Exception as exc:
        logger.warning(f"Failed to fetch conversation context for user {user_id}: {exc}")

    return ConversationContext(user_id=user_id, role=role)


async def update_user_context(
    user_id: int,
    updates: Dict[str, Any],
    role: str = "passenger",
) -> ConversationContext:
    """
    Update specific fields of user's conversation context and reset TTL.
    """
    ctx = await get_user_context(user_id, role=role)
    ctx_dict = ctx.model_dump()

    # Update valid non-None fields
    for k, v in updates.items():
        if hasattr(ctx, k):
            ctx_dict[k] = v

    ctx_dict["updated_at"] = time.time()
    updated_ctx = ConversationContext(**ctx_dict)

    client = get_redis_client()
    key = _context_key(user_id)
    try:
        await client.set(
            key,
            json.dumps(updated_ctx.model_dump(), default=str),
            ex=CONTEXT_TTL_SECONDS,
        )
    except Exception as exc:
        logger.warning(f"Failed to persist conversation context for user {user_id}: {exc}")

    return updated_ctx


async def clear_user_context(user_id: int) -> None:
    """Clear structured conversation context."""
    client = get_redis_client()
    key = _context_key(user_id)
    try:
        await client.delete(key)
    except Exception as exc:
        logger.warning(f"Failed to clear conversation context for user {user_id}: {exc}")


async def set_pending_action(
    user_id: int,
    action: str,
    data: Dict[str, Any],
    role: str = "passenger",
) -> ConversationContext:
    """Store an unconfirmed action requiring explicit user consent."""
    return await update_user_context(
        user_id,
        {
            "pending_action": action,
            "pending_action_data": data,
        },
        role=role,
    )


async def clear_pending_action(user_id: int, role: str = "passenger") -> ConversationContext:
    """Clear any pending unconfirmed action."""
    return await update_user_context(
        user_id,
        {
            "pending_action": None,
            "pending_action_data": None,
        },
        role=role,
    )
