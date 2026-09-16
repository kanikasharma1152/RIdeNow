"""
RideNow Driver AI Copilot Tools — Phase 6
==========================================
AI tool functions exclusively for the driver role.
All data access is scoped to the currently authenticated driver.

Security note: these tools are only reachable through the registry
when current_user.role == "driver".
"""

import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def get_driver_summary(current_user, db: AsyncSession, **kwargs) -> dict:
    """
    Returns a quick operational summary for the driver:
    online status, earnings today, completed rides today, acceptance rate.
    """
    from app.services.driver import get_my_driver_profile
    from app.services.ride import get_driver_earnings

    try:
        driver = await get_my_driver_profile(db, current_user.id)
        stats = await get_driver_earnings(db, current_user.id)

        def _get_val(obj, key, default=0):
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        today_earnings = _get_val(stats, "today_earnings", 0)
        today_rides = _get_val(stats, "today_rides", 0)
        total_rides = _get_val(stats, "total_rides", 0)

        return {
            "success": True,
            "is_online": getattr(driver, "is_online", False),
            "is_available": getattr(driver, "is_available", False),
            "today_earnings": f"₹{today_earnings}",
            "today_rides": today_rides,
            "total_completed": total_rides,
        }
    except Exception as exc:
        logger.warning(f"get_driver_summary failed: {exc}")
        return {"success": False, "error": "Unable to retrieve driver summary at this time."}


async def get_route_tip(
    current_user=None,
    db: AsyncSession = None,
    pickup_location: str = "your current location",
    dropoff_location: str = "the destination",
    **kwargs,
) -> dict:
    """
    Returns a quick routing tip for the driver based on current ride context.
    Placeholder — in production this would call a routing/ML service.
    """
    pickup = pickup_location or kwargs.get("pickup_location") or "your current location"
    dropoff = dropoff_location or kwargs.get("dropoff_location") or "the destination"
    return {
        "success": True,
        "tip": (
            f"Optimal route from '{pickup}' to '{dropoff}': "
            "Use the main highway during peak hours to avoid city congestion. "
            "Estimated ETA improvement: ~8 minutes."
        ),
        "avoid": ["Narrow lanes", "Railway crossings"],
    }


# ─── Tool Definition Schemas for registry ─────────────────────────────────────

COPILOT_TOOL_DEFINITIONS = [
    {
        "name": "get_driver_summary",
        "description": "Returns the driver's current operational summary: online status, today's earnings, and completed ride count.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "allowed_roles": ["driver"],
    },
    {
        "name": "get_route_tip",
        "description": "Provides a routing tip for the driver for a given pickup and dropoff location.",
        "parameters": {
            "type": "object",
            "properties": {
                "pickup_location": {
                    "type": "string",
                    "description": "The ride pickup address or landmark.",
                },
                "dropoff_location": {
                    "type": "string",
                    "description": "The ride dropoff address or landmark.",
                },
            },
            "required": [],
        },
        "allowed_roles": ["driver"],
    },
]

COPILOT_TOOL_FUNCTIONS = {
    "get_driver_summary": get_driver_summary,
    "get_route_tip": get_route_tip,
}
