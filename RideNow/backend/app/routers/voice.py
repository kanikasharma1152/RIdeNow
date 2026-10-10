"""
RideNow Voice Router — Phase 5
==============================
Provides endpoints for LiveKit voice room token generation.
Authenticated users can request an access token to join the voice assistant room.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.routers.user import get_current_user
from app.models.user import User
from app.services.voice import generate_voice_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["Voice"])


class VoiceTokenRequest(BaseModel):
    room_name: Optional[str] = Field(None, description="Custom room name; defaults to 'ridenow-voice-{user_id}'")


class VoiceTokenResponse(BaseModel):
    success: bool
    token: str
    room: str
    url: str
    expires_in: int


@router.post(
    "/token",
    response_model=VoiceTokenResponse,
    summary="Generate a LiveKit Voice Room Access Token",
    description="Returns a signed LiveKit JWT token for client-side voice streaming with the AI assistant.",
)
async def get_voice_token(
    request: VoiceTokenRequest = VoiceTokenRequest(),
    current_user: User = Depends(get_current_user),
):
    if not settings.is_livekit_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Voice interface is currently not configured or disabled on this server.",
        )

    # Each session MUST use a unique room name.
    # Reusing the same room (e.g. "ridenow-voice-25") causes the old agent job
    # — blocked on asyncio.create_future() — to remain in the room.  The
    # LiveKit worker sees the room still occupied and does NOT dispatch a new
    # agent job for the reconnecting client, so the second connection is silent.
    # A UUID suffix guarantees a brand-new room (and therefore a brand-new agent
    # job) on every connection, while still namespacing by user.
    import uuid
    room_name = request.room_name or f"ridenow-voice-{current_user.id}-{uuid.uuid4().hex[:8]}"

    try:
        data = generate_voice_token(
            user_id=current_user.id,
            user_name=current_user.name,
            room_name=room_name,
            user_role=current_user.role,
        )
        return VoiceTokenResponse(
            success=True,
            token=data["token"],
            room=data["room"],
            url=data["url"],
            expires_in=data["expires_in"],
        )
    except Exception as exc:
        logger.error(f"Failed to generate voice token for user {current_user.id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate voice session.",
        )


@router.get(
    "/health",
    summary="Check Voice AI Infrastructure Status",
    description="Returns configuration status of LiveKit, Cartesia, and Groq without exposing credentials.",
)
async def get_voice_health():
    return {
        "status": "online" if (settings.is_livekit_configured and settings.is_cartesia_configured and settings.is_llm_configured) else "degraded",
        "livekit": settings.is_livekit_configured,
        "cartesia": settings.is_cartesia_configured,
        "groq": settings.is_llm_configured,
        "voice_id": settings.CARTESIA_VOICE_ID,
        "tts_model": settings.CARTESIA_MODEL,
        "stt_model": settings.CARTESIA_STT_MODEL,
        "llm_model": settings.GROQ_MODEL,
    }
