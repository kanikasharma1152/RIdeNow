"""
RideNow — Health & Admin Intelligence Router (Phase 14)
=========================================================
Endpoints:
- GET /health/system    → Full system health check (admin only)
- GET /health/ai        → AI telemetry summary (admin only)
- GET /admin/intelligence      → Full admin intelligence dashboard
- GET /admin/ai-metrics        → AI metrics detail
- GET /admin/ride-reliability  → Stale rides and reliability data
"""

import logging
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.routers.user import get_current_user
from app.models.user import User
from app.core.exceptions import UnauthorizedAccessError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Admin Intelligence"])


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Enforce admin-only access for intelligence/health endpoints."""
    if current_user.role != "admin":
        raise UnauthorizedAccessError(
            "System health and admin intelligence are restricted to administrators."
        )
    return current_user


# ─── System Health ────────────────────────────────────────────────────────────

@router.get(
    "/health/system",
    summary="System Health Center",
    description="Real health checks for all RideNow dependencies. Admin only.",
)
async def system_health(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.services.health import check_all_services
    return await check_all_services(db)


@router.get(
    "/health/ai",
    summary="AI Telemetry Summary",
    description="Recent AI interaction metrics. Admin only. Never contains user message content.",
)
async def ai_health(
    admin: User = Depends(require_admin),
):
    from app.observability.telemetry import telemetry
    return await telemetry.get_recent_ai_metrics(limit=500)


# ─── Admin Intelligence ───────────────────────────────────────────────────────

@router.get(
    "/admin/intelligence",
    summary="Admin Intelligence Dashboard",
    description="Aggregated real-time intelligence: rides, drivers, AI, safety, system.",
)
async def admin_intelligence(
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    import asyncio
    from app.services.analytics import get_dashboard_analytics
    from app.services.ride_reliability import get_reliability_metrics
    from app.observability.telemetry import telemetry

    results = await asyncio.gather(
        get_dashboard_analytics(db),
        get_reliability_metrics(db),
        telemetry.get_recent_ai_metrics(limit=200),
        return_exceptions=True,
    )

    analytics = results[0] if not isinstance(results[0], Exception) else {}
    reliability = results[1] if not isinstance(results[1], Exception) else {}
    ai_metrics = results[2] if not isinstance(results[2], Exception) else {}

    # Safety stats
    safety_stats = {}
    try:
        from app.repositories.safety import get_admin_safety_aggregates
        safety_stats = await get_admin_safety_aggregates(db)
    except Exception as exc:
        logger.debug(f"Could not fetch safety stats: {exc}")

    # WebSocket stats
    ws_stats = {}
    try:
        from app.core.connection_manager import ws_manager
        ws_stats = ws_manager.get_connection_stats()
    except Exception:
        pass

    return {
        "platform": analytics,
        "ride_reliability": reliability,
        "ai_metrics": ai_metrics,
        "safety": safety_stats,
        "websocket": ws_stats,
        "request_id": getattr(request.state, "request_id", None),
    }


@router.get(
    "/admin/ai-metrics",
    summary="AI Metrics Detail",
    description="Detailed AI telemetry — tool calls, latency, error rates. Admin only.",
)
async def admin_ai_metrics(
    admin: User = Depends(require_admin),
):
    from app.observability.telemetry import telemetry
    return await telemetry.get_recent_ai_metrics(limit=500)


@router.get(
    "/admin/ride-reliability",
    summary="Ride Reliability Report",
    description="Stale rides, rejection stats, cancellation rates. Admin only.",
)
async def admin_ride_reliability(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.services.ride_reliability import get_reliability_metrics
    return await get_reliability_metrics(db)
