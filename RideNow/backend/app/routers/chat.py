import base64
import logging
import time
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.routers.user import get_current_user
from app.schemas.chat import ChatRequest, ChatResponse
from app.ai.agent.agent import process_chat_message
from app.ai.agent.memory import clear_conversation_history
from app.ai.agent.context import update_user_context
from app.ai.llm.vision_provider import get_vision_provider
from app.core.redis import rate_limit_check
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/chat",
    tags=["AI Assistant"],
)


@router.post(
    "/message",
    response_model=ChatResponse,
    summary="Chat with RideNow AI Assistant (Multimodal)",
    description="Send a message to the AI Assistant. Supports text, user GPS coordinates, and optional visual images.",
)
async def chat_message_api(
    request: Request,
    chat_request: ChatRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not settings.AI_CHAT_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI Assistant is temporarily disabled.",
        )

    # Rate limiting check
    is_allowed = await rate_limit_check(
        identifier=f"user:{current_user.id}",
        max_requests=settings.REDIS_RATE_LIMIT_REQUESTS,
        window_seconds=settings.REDIS_RATE_LIMIT_WINDOW_SECONDS,
    )
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait a moment before sending more messages.",
        )

    # Phase 14: Propagate or generate request_id for traceability
    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())[:8]
    start_time = time.monotonic()

    modality = chat_request.input_type or "text"
    prompt_text = chat_request.message.strip()
    visual_context_meta = None

    # 1. Location telemetry integration
    if chat_request.latitude is not None and chat_request.longitude is not None:
        try:
            await update_user_context(
                current_user.id,
                {
                    "pickup_coords": {
                        "latitude": chat_request.latitude,
                        "longitude": chat_request.longitude,
                    },
                    "pickup": "Current GPS Location",
                },
                role=current_user.role,
            )
        except Exception as exc:
            logger.warning(f"Could not persist user GPS to context: {exc}")

    # 2. Image understanding foundation
    if chat_request.image_base64:
        modality = "multimodal"
        raw_b64 = chat_request.image_base64
        # Strip data URL prefix if sent by frontend
        if "," in raw_b64:
            raw_b64 = raw_b64.split(",", 1)[1]

        # Validate max size (~10MB limit in base64 is ~13.5MB chars)
        if len(raw_b64) > 14 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Image size exceeds the 10MB limit.",
            )

        try:
            vision_provider = get_vision_provider()
            v_res = await vision_provider.analyze_location_image(
                image_base64=raw_b64,
                query=prompt_text,
                user_latitude=chat_request.latitude,
                user_longitude=chat_request.longitude,
            )
            visual_context_meta = v_res

            if v_res.get("supported"):
                clues = ", ".join(v_res.get("visual_clues", []))
                prompt_text += f"\n[Visual Location Analysis: {clues}]"
            else:
                # If vision is not supported on current model tier, report capability honestly
                prompt_text += f"\n[User attached an image. Note: {v_res.get('message')}]"
        except Exception as exc:
            logger.warning(f"Multimodal vision processing failed: {exc}")
            prompt_text += "\n[Note: Image upload could not be processed due to a transient error.]"

    # 3. Unified Agent execution
    error_type = None
    response = {}
    try:
        response = await process_chat_message(
            message=prompt_text,
            current_user=current_user,
            db=db,
        )
    except Exception as exc:
        error_type = type(exc).__name__
        logger.error(f"[Chat] Agent execution failed for user {current_user.id}: {exc}")
        response = {
            "reply": "I ran into a temporary issue. Please try again in a moment.",
            "tools_executed": [],
            "suggested_actions": ["Try Again"],
        }

    # 4. Phase 14: Record AI telemetry (metadata only — no user message content)
    latency_ms = round((time.monotonic() - start_time) * 1000, 2)
    tools_executed = response.get("tools_executed", [])
    tools_called = [t.get("tool", "") for t in tools_executed if isinstance(t, dict)]
    tools_succeeded = [t.get("tool", "") for t in tools_executed
                       if isinstance(t, dict) and not t.get("result", {}).get("error")]
    tools_failed = [t.get("tool", "") for t in tools_executed
                    if isinstance(t, dict) and t.get("result", {}).get("error")]
    fallback_used = response.get("fallback_used", False)

    try:
        from app.observability.telemetry import telemetry
        await telemetry.record_ai_request(
            request_id=request_id,
            user_id=current_user.id,
            channel=modality,
            intent=response.get("detected_intent"),
            model=settings.GROQ_MODEL,
            tools_called=tools_called,
            tools_succeeded=tools_succeeded,
            tools_failed=tools_failed,
            latency_ms=latency_ms,
            fallback_used=fallback_used,
            error_type=error_type,
        )
    except Exception as exc:
        logger.debug(f"[Telemetry] Record failed: {exc}")

    return ChatResponse(
        reply=response["reply"],
        tools_executed=response.get("tools_executed", []),
        suggested_actions=response.get("suggested_actions", []),
        visual_context=visual_context_meta,
        input_modality=modality,
    )


@router.delete(
    "/history",
    summary="Clear conversation history",
    description="Resets the user's active AI chat context and memory.",
)
async def clear_history_api(
    current_user=Depends(get_current_user),
):
    await clear_conversation_history(current_user.id)
    return {"success": True, "message": "Chat context cleared."}
