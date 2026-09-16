"""
RideNow AI — Controlled Driver Tools
====================================
Driver-specific tools for checking earnings, vehicle stats, and availability.
Enforces role check: only users with role="driver" can invoke.
"""

from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.driver import get_my_driver_profile, change_driver_status
from app.services.ride import get_driver_earnings
from app.core.exceptions import RideNowError


async def get_driver_status_tool(
    current_user,
    db: AsyncSession,
    **kwargs,
) -> Dict[str, Any]:
    """
    Get profile, vehicle details, and online availability for the driver.
    """
    if current_user.role != "driver":
        return {"success": False, "message": "This tool is only available for registered drivers."}

    try:
        driver = await get_my_driver_profile(db, current_user.id)
        return {
            "success": True,
            "driver_id": driver.id,
            "vehicle_type": driver.vehicle_type,
            "vehicle_model": driver.vehicle_model,
            "vehicle_number": driver.vehicle_number,
            "is_online": driver.is_online,
            "is_available": driver.is_available,
            "location_updated_at": str(driver.location_updated_at) if driver.location_updated_at else None,
        }
    except RideNowError as exc:
        return {"success": False, "message": exc.message}
    except Exception as exc:
        return {"success": False, "message": str(exc)}


async def get_driver_earnings_tool(
    current_user,
    db: AsyncSession,
    **kwargs,
) -> Dict[str, Any]:
    """
    Get driver earnings statistics: today, this week, this month, and total.
    """
    if current_user.role != "driver":
        return {"success": False, "message": "Earnings data is only accessible to drivers."}

    try:
        stats = await get_driver_earnings(db, current_user.id)
        
        def _get_val(obj, key, default=0):
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        today_val = _get_val(stats, "today_earnings", 0)
        week_val = _get_val(stats, "week_earnings", 0)
        month_val = _get_val(stats, "month_earnings", 0)
        total_val = _get_val(stats, "total_earnings", 0)
        completed = _get_val(stats, "total_rides", 0)

        return {
            "success": True,
            "today_earnings": f"₹{today_val}",
            "week_earnings": f"₹{week_val}",
            "month_earnings": f"₹{month_val}",
            "total_earnings": f"₹{total_val}",
            "completed_rides": completed,
        }
    except RideNowError as exc:
        return {"success": False, "message": exc.message}
    except Exception as exc:
        return {"success": False, "message": "Unable to retrieve earnings data at this time."}
