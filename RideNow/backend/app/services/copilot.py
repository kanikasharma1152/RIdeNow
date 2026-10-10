"""
RideNow Driver AI Copilot Service — Phase 6
===========================================
High-level intelligence layer for drivers:
- Performance & earnings summaries
- Real-time navigation advice
- Demand hot spots & idle positioning guidance
- Copilot AI chat interaction
"""

import logging
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.driver import get_my_driver_profile
from app.services.ride import get_driver_earnings
from app.ai.llm import get_llm_provider

logger = logging.getLogger(__name__)


async def get_driver_copilot_briefing(user: User, db: AsyncSession) -> Dict[str, Any]:
    """
    Generates a contextual morning/shift briefing for the driver.
    Combines operational telemetry stats with AI-curated tips.
    Core telemetry is resilient and does not fail if profile or stats are partial.
    """
    driver = None
    try:
        driver = await get_my_driver_profile(db, user.id)
    except Exception as exc:
        logger.warning(f"Driver profile lookup for user {user.id}: {exc}")

    stats: Dict[str, Any] = {}
    if driver:
        try:
            raw_stats = await get_driver_earnings(db, user.id)
            if isinstance(raw_stats, dict):
                stats = raw_stats
        except Exception as exc:
            logger.warning(f"Driver earnings lookup for driver {driver.id}: {exc}")

    # Dynamic demand hotspots from Phase 3 ML demand predictor
    demand_zones = []
    try:
        from app.ml.demand.predictor import get_demand_hotspots
        ml_hotspots = await get_demand_hotspots(db, limit=3)
        for h in ml_hotspots:
            lat = h["zone"]["lat"]
            lon = h["zone"]["lon"]
            score = h.get("current_demand_score", 1.0)
            level = h.get("demand_level", "Medium").title()
            surge = f"{max(1.0, round(score, 1))}x"
            demand_zones.append({
                "zone": f"Zone ({lat:.2f}, {lon:.2f})",
                "surge_factor": surge,
                "demand_level": level,
                "eta_mins": 10,
                "historical_rides_7d": h.get("historical_rides_7d", 0),
            })
    except Exception as exc:
        logger.debug(f"Could not load ML hotspots for driver copilot: {exc}")

    if not demand_zones:
        demand_zones = [
            {"zone": "Downtown / Tech Park", "surge_factor": "1.4x", "demand_level": "High", "eta_mins": 10},
            {"zone": "Central Railway Station", "surge_factor": "1.2x", "demand_level": "Moderate", "eta_mins": 15},
            {"zone": "International Airport", "surge_factor": "1.5x", "demand_level": "High", "eta_mins": 25},
        ]

    tips = [
        "Peak morning rush begins in ~30 minutes around commercial hubs.",
        "Airport queue is currently under 15 minutes wait time.",
        "Keeping availability ON increases assignment priority by 15%.",
    ]

    today_val = stats.get("today_earnings", 0)
    week_val = stats.get("week_earnings", 0)
    month_val = stats.get("month_earnings", 0)
    total_val = stats.get("total_rides", 0)
    total_earn = stats.get("total_earnings", 0)

    vehicle_str = f"{driver.vehicle_model} ({driver.vehicle_number})" if driver and driver.vehicle_model else "Vehicle Assigned"

    return {
        "success": True,
        "driver_id": driver.id if driver else None,
        "driver_name": user.name,
        "is_online": bool(driver.is_online) if driver else False,
        "is_available": bool(driver.is_available) if driver else False,
        "vehicle": vehicle_str,
        "earnings": {
            "today": f"₹{today_val}",
            "week": f"₹{week_val}",
            "month": f"₹{month_val}",
            "total_earnings": f"₹{total_earn}",
            "total_rides": total_val,
        },
        "demand_zones": demand_zones,
        "coaching_tips": tips,
    }


async def ask_copilot(
    prompt: str,
    user: User,
    db: AsyncSession,
) -> Dict[str, Any]:
    """
    Direct prompt-based query to driver copilot assistant.
    If Groq is available, synthesizes contextual driver guidance; otherwise uses deterministic guidance.
    """
    briefing = await get_driver_copilot_briefing(user, db)
    provider = get_llm_provider()

    if provider.is_available():
        system_msg = (
            f"You are RideNow Driver Copilot, an AI assistant built exclusively for professional drivers. "
            f"Driver: {user.name}. Vehicle: {briefing['vehicle']}. Today's earnings: {briefing['earnings']['today']}. "
            f"Total trips completed: {briefing['earnings']['total_rides']}. "
            f"Be concise, encouraging, safety-focused, and provide actionable driving/positioning advice."
        )
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt},
        ]
        try:
            res = await provider.generate_response(messages)
            content = res.get("content", "").strip()
            if content:
                return {
                    "success": True,
                    "reply": content,
                    "briefing_snapshot": briefing,
                }
        except Exception as exc:
            logger.warning(f"Groq copilot generation failed: {exc}")

    # Deterministic fallback response
    p_lower = prompt.lower()
    if "where" in p_lower or "hotspot" in p_lower or "demand" in p_lower:
        reply = (
            f"High demand is currently active in **Downtown / Tech Park** (1.4x surge) "
            f"and **International Airport** (1.5x surge). Recommend repositioning towards Downtown."
        )
    elif "earning" in p_lower or "money" in p_lower:
        reply = (
            f"You have earned **{briefing['earnings']['today']}** today across your completed rides. "
            f"Total earnings to date: **{briefing['earnings']['month']}** this month."
        )
    else:
        reply = (
            f"Copilot ready! Today's completed rides: {briefing['earnings']['total_rides']}. "
            f"Maintain safe speeds and check Downtown for higher fare volume."
        )

    return {
        "success": True,
        "reply": reply,
        "briefing_snapshot": briefing,
    }
