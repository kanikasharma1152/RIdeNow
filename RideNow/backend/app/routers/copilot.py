"""
RideNow Driver AI Copilot Router — Phase 6
==========================================
Endpoints for authenticated drivers to access Copilot intelligence:
- GET /driver/copilot/briefing
- POST /driver/copilot/chat
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.routers.user import get_current_user
from app.models.user import User
from app.services.copilot import get_driver_copilot_briefing, ask_copilot

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/driver/copilot", tags=["Driver Copilot"])


class CopilotQueryRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500, description="Driver question or instruction for Copilot")


def require_driver(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "driver":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Driver Copilot is exclusively available to registered drivers.",
        )
    return current_user


@router.get(
    "/briefing",
    summary="Get Driver Shift Briefing",
    description="Returns driver performance stats, hotspots, and proactive AI coaching tips.",
)
async def get_briefing(
    current_user: User = Depends(require_driver),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await get_driver_copilot_briefing(current_user, db)
    except Exception as exc:
        logger.error(f"Error generating briefing for driver {current_user.id}: {exc}")
        raise HTTPException(status_code=500, detail="Unable to generate driver briefing.")


@router.post(
    "/chat",
    summary="Chat with Driver Copilot",
    description="Ask Copilot for route tips, positioning suggestions, or earnings advice.",
)
async def chat_copilot(
    request: CopilotQueryRequest,
    current_user: User = Depends(require_driver),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await ask_copilot(request.message, current_user, db)
    except Exception as exc:
        logger.error(f"Error querying copilot for driver {current_user.id}: {exc}")
        raise HTTPException(status_code=500, detail="Unable to query driver copilot.")
