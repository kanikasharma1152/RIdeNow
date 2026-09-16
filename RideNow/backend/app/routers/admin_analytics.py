"""
RideNow Admin Analytics Router — Phase 7
========================================
Endpoints reserved exclusively for administrators:
- GET /admin/analytics/overview
- GET /admin/analytics/insights (AI powered)
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.routers.user import get_current_user
from app.models.user import User
from app.services.analytics import get_dashboard_analytics, generate_ai_insights

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/analytics", tags=["Admin Analytics"])


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin analytics are strictly restricted to system administrators.",
        )
    return current_user


@router.get(
    "/overview",
    summary="Get Platform Analytics Overview",
    description="Returns aggregate platform KPIs: gross volume, ride completion rate, active drivers, and 7-day trend.",
)
async def get_overview(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await get_dashboard_analytics(db)
    except Exception as exc:
        logger.error(f"Failed to fetch admin analytics: {exc}")
        raise HTTPException(status_code=500, detail="Unable to fetch admin analytics.")


@router.get(
    "/insights",
    summary="Generate AI Strategic Insights",
    description="Invokes Groq LLM to synthesize operational recommendations from real-time platform metrics.",
)
async def get_insights(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await generate_ai_insights(db)
    except Exception as exc:
        logger.error(f"Failed to generate AI insights: {exc}")
        raise HTTPException(status_code=500, detail="Unable to generate admin insights.")
