"""
RideNow Admin Analytics Service — Phase 7
=========================================
Business logic for platform analytics and AI-powered operational insights.
Combines raw DB metrics with Groq LLM intelligence to produce actionable recommendations.
"""

import logging
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.analytics import (
    get_overview_metrics,
    get_recent_rides_trend,
    get_top_pickup_hotspots,
    get_admin_fleet_drivers,
)
from app.ai.llm import get_llm_provider
from app.core.redis import cache_get, cache_set, cache_delete

logger = logging.getLogger(__name__)

ADMIN_ANALYTICS_CACHE_KEY = "admin:dashboard_analytics"
ADMIN_ANALYTICS_CACHE_TTL = 60  # seconds


async def get_dashboard_analytics(db: AsyncSession, use_cache: bool = True) -> Dict[str, Any]:
    """Compile comprehensive analytics dashboard payload with 60s Redis caching."""
    if use_cache:
        try:
            cached = await cache_get(ADMIN_ANALYTICS_CACHE_KEY)
            if cached and isinstance(cached, dict):
                return cached
        except Exception as exc:
            logger.warning(f"Cache read error for admin analytics: {exc}")

    overview = await get_overview_metrics(db)
    trend = await get_recent_rides_trend(db, days=7)
    hotspots = await get_top_pickup_hotspots(db, limit=5)
    fleet = await get_admin_fleet_drivers(db, limit=20)

    payload = {
        "success": True,
        "overview": overview,
        "trend_7d": trend,
        "top_hotspots": hotspots,
        "fleet_drivers": fleet,
    }

    if use_cache:
        try:
            await cache_set(ADMIN_ANALYTICS_CACHE_KEY, payload, ttl=ADMIN_ANALYTICS_CACHE_TTL)
        except Exception as exc:
            logger.warning(f"Cache write error for admin analytics: {exc}")

    return payload


async def invalidate_admin_analytics_cache() -> None:
    """Explicitly invalidate the admin analytics cache when rides or drivers change."""
    try:
        await cache_delete(ADMIN_ANALYTICS_CACHE_KEY)
    except Exception as exc:
        logger.warning(f"Cache invalidation error for admin analytics: {exc}")



async def generate_ai_insights(db: AsyncSession) -> Dict[str, Any]:
    """
    Synthesize operational insights using Groq LLM based on current platform KPIs.
    Falls back to deterministic insights if Groq is unconfigured.
    """
    analytics = await get_dashboard_analytics(db)
    overview = analytics["overview"]
    hotspots = analytics["top_hotspots"]

    provider = get_llm_provider()
    if provider.is_available():
        prompt = (
            f"You are the Chief Operations AI for RideNow Mobility Platform.\n"
            f"Current KPIs:\n"
            f"- Total Rides: {overview['total_rides']}\n"
            f"- Completion Rate: {overview['completion_rate_pct']}%\n"
            f"- Active Drivers Online: {overview['active_drivers_online']}\n"
            f"- Gross Revenue: ₹{overview['total_revenue_inr']}\n"
            f"- Top Hotspots: {[h['location'] for h in hotspots]}\n\n"
            f"Provide 3 concise, bulleted strategic recommendations for improving driver utilization, "
            f"reducing cancellations, and capturing peak demand."
        )
        messages = [
            {"role": "system", "content": "You are RideNow's Executive Operations AI."},
            {"role": "user", "content": prompt},
        ]
        try:
            res = await provider.generate_response(messages)
            return {
                "success": True,
                "ai_insights": res.get("content", ""),
                "metrics_snapshot": overview,
            }
        except Exception as exc:
            logger.warning(f"Groq analytics synthesis failed: {exc}")

    # Deterministic fallback insights
    comp_rate = overview["completion_rate_pct"]
    driver_count = overview["active_drivers_online"]
    insights = [
        f"Platform completion rate is currently {comp_rate}%. Target benchmark is 85%+.",
        f"With {driver_count} active drivers online, consider introducing driver surge multipliers during 8-10 AM and 5-8 PM.",
        "Reposition idle drivers towards the top pickup locations to reduce passenger ETA under 4 minutes.",
    ]

    return {
        "success": True,
        "ai_insights": "\n\n".join([f"- {i}" for i in insights]),
        "metrics_snapshot": overview,
    }
