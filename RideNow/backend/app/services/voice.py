"""
RideNow Voice Service — Phase 5
================================
Generates LiveKit access tokens so that client apps can join voice rooms.
Requires LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET in settings.
Returns HTTP 503 when LiveKit is not configured.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


def generate_voice_token(
    user_id: int,
    user_name: str,
    room_name: str,
    user_role: str = "passenger",
    ttl_minutes: Optional[int] = None,
) -> dict:
    """
    Generate a LiveKit access token for the given user and room.

    Returns a dict with:
      - token: str  — the signed JWT
      - room: str   — room name joined
      - url: str    — LiveKit server URL
      - expires_in: int — TTL in seconds
    """
    if not settings.is_livekit_configured:
        raise RuntimeError("LiveKit is not configured on this server.")

    try:
        import json
        from livekit.api import AccessToken, VideoGrants
    except ImportError as exc:
        raise RuntimeError(
            f"livekit-api package is not installed: {exc}"
        ) from exc

    ttl = ttl_minutes or settings.LIVEKIT_TOKEN_TTL_MINUTES
    expiry = datetime.utcnow() + timedelta(minutes=ttl)

    grants = VideoGrants(
        room_join=True,
        room=room_name,
        can_publish=True,
        can_subscribe=True,
    )

    metadata_str = json.dumps({
        "user_id": user_id,
        "name": user_name,
        "role": user_role,
    })

    token_builder = (
        AccessToken(
            api_key=settings.LIVEKIT_API_KEY,
            api_secret=settings.LIVEKIT_API_SECRET,
        )
        .with_identity(f"user-{user_id}")
        .with_name(user_name)
        .with_metadata(metadata_str)
        .with_grants(grants)
        .with_ttl(timedelta(minutes=ttl))
    )

    signed_token: str = token_builder.to_jwt()

    logger.info(f"Generated LiveKit token for user {user_id} in room '{room_name}' (ttl={ttl}m)")

    return {
        "token": signed_token,
        "room": room_name,
        "url": settings.LIVEKIT_URL,
        "expires_in": ttl * 60,
    }
