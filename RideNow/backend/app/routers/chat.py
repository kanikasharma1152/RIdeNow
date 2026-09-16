"""
RideNow — AI Chat Router
========================
Endpoints:
- POST /chat/message: Send a message to Nova AI Assistant
- DELETE /chat/history: Clear user conversation history
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.routers.user import get_current_user
from app.schemas.chat import ChatRequest, ChatResponse
from app.ai.agent.agent import process_chat_message
from app.ai.agent.memory import clear_conversation_history
from app.core.redis import rate_limit_check
from app.core.config import settings

router = APIRouter(
    prefix="/chat",
    tags=["AI Assistant"],
)


@router.post(
    "/message",
    response_model=ChatResponse,
    summary="Chat with RideNow AI Assistant",
    description="Send a message to the AI Assistant. Handles intent recognition, tool calls, and RAG retrieval.",
)
async def chat_message_api(
    request: ChatRequest,
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

    response = await process_chat_message(
        message=request.message,
        current_user=current_user,
        db=db,
    )
    return response


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
