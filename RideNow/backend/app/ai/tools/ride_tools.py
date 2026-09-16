"""
RideNow AI — Controlled Ride Tools (MCP-Style)
==============================================
Provides controlled, role-validated tools for checking rides, estimating fares,
and managing trips.
Security:
- All tools require authenticated current_user and db session
- Strictly call existing app.services.ride methods
- Enforce resource ownership and business rules
- Sensitive operations (cancellation) require explicit confirmation
"""

from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ride import (
    get_passenger_rides,
    get_driver_rides,
    get_ride,
    calculate_fare,
    cancel_passenger_ride,
)
from app.services.google_map import calculate_route_distance, geocode_address
from app.core.exceptions import RideNowError


async def get_active_ride_tool(
    current_user,
    db: AsyncSession,
    **kwargs,
) -> Dict[str, Any]:
    """
    Get the currently active ride (REQUESTED, ACCEPTED, or STARTED)
    for the authenticated user (passenger or driver).
    """
    try:
        if current_user.role == "driver":
            my_rides = await get_driver_rides(db, current_user.id)
        else:
            my_rides = await get_passenger_rides(db, current_user.id)

        rides_list = my_rides if isinstance(my_rides, list) else getattr(my_rides, "items", [])

        active = next(
            (r for r in rides_list if r.status in ("REQUESTED", "ACCEPTED", "STARTED")),
            None,
        )

        if not active:
            return {
                "has_active_ride": False,
                "message": "You currently have no active ride in progress.",
            }

        return {
            "has_active_ride": True,
            "ride_id": active.id,
            "status": active.status,
            "pickup_location": active.pickup_location,
            "dropoff_location": active.dropoff_location,
            "distance_km": float(active.distance_km) if active.distance_km else None,
            "fare": float(active.fare) if active.fare else None,
            "created_at": str(active.created_at),
        }
    except RideNowError as exc:
        return {"has_active_ride": False, "error": exc.message}
    except Exception as exc:
        return {"has_active_ride": False, "error": str(exc)}


async def get_ride_history_tool(
    current_user,
    db: AsyncSession,
    limit: int = 5,
    **kwargs,
) -> Dict[str, Any]:
    """
    Get the user's recent ride history.
    """
    try:
        if current_user.role == "driver":
            rides = await get_driver_rides(db, current_user.id)
        else:
            rides = await get_passenger_rides(db, current_user.id)

        rides_list = rides if isinstance(rides, list) else getattr(rides, "items", [])

        recent = rides_list[:limit]
        formatted = []
        for r in recent:
            formatted.append({
                "ride_id": r.id,
                "status": r.status,
                "pickup": r.pickup_location,
                "dropoff": r.dropoff_location,
                "distance_km": float(r.distance_km) if r.distance_km else None,
                "fare": float(r.fare) if r.fare else None,
                "date": str(r.created_at)[:16] if r.created_at else None,
            })

        return {
            "total_rides_returned": len(formatted),
            "rides": formatted,
        }
    except Exception as exc:
        return {"error": str(exc), "rides": []}


async def estimate_fare_tool(
    pickup_address: Optional[str] = None,
    dropoff_address: Optional[str] = None,
    distance_km: Optional[float] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Calculate an estimated fare for a trip.
    Can accept an explicit distance in km, or geocode and route between pickup and dropoff addresses.
    """
    try:
        calc_distance = distance_km

        if calc_distance is None:
            if not pickup_address or not dropoff_address:
                return {
                    "success": False,
                    "message": "Please provide either distance_km or both pickup_address and dropoff_address.",
                }

            # Geocode locations
            pick_coords = await geocode_address(pickup_address)
            drop_coords = await geocode_address(dropoff_address)

            if not pick_coords or not drop_coords:
                return {
                    "success": False,
                    "message": "Unable to find coordinates for the provided addresses. Please be more specific.",
                }

            # Calculate route distance via OSRM
            calc_distance = await calculate_route_distance(
                pick_coords[0], pick_coords[1],
                drop_coords[0], drop_coords[1],
            )

        fare = calculate_fare(calc_distance)
        return {
            "success": True,
            "distance_km": round(float(calc_distance), 2),
            "base_fare": "₹50.00",
            "per_km_rate": "₹12.00",
            "estimated_fare": f"₹{fare}",
            "currency": "INR",
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


async def cancel_ride_tool(
    current_user,
    db: AsyncSession,
    ride_id: int,
    confirmed: bool = False,
    **kwargs,
) -> Dict[str, Any]:
    """
    Cancel an active ride request.
    Requires confirmed=True to execute. If confirmed=False, returns a confirmation prompt.
    """
    if current_user.role != "passenger":
        return {
            "success": False,
            "message": "Only passengers can initiate ride cancellations.",
        }

    try:
        ride = await get_ride(db, ride_id, current_user.id)
        if not ride:
            return {"success": False, "message": f"Ride #{ride_id} not found."}

        if ride.status not in ("REQUESTED", "ACCEPTED"):
            return {
                "success": False,
                "message": f"Ride #{ride_id} is in status '{ride.status}' and cannot be cancelled.",
            }

        # Safe Confirmation Check
        if not confirmed:
            return {
                "success": False,
                "requires_confirmation": True,
                "ride_id": ride_id,
                "current_status": ride.status,
                "message": (
                    f"⚠️ Are you sure you want to cancel ride #{ride_id} "
                    f"from '{ride.pickup_location}' to '{ride.dropoff_location}'? "
                    "If the driver was matched more than 2 minutes ago, a ₹30 fee may apply. "
                    "Please reply 'confirm cancel' to proceed."
                ),
            }

        # Perform verified cancellation through existing service
        await cancel_passenger_ride(
            db=db,
            passenger_id=current_user.id,
            ride_id=ride_id,
        )

        return {
            "success": True,
            "ride_id": ride_id,
            "status": "CANCELLED",
            "message": f"Ride #{ride_id} has been cancelled successfully.",
        }

    except RideNowError as exc:
        return {"success": False, "message": exc.message}
    except Exception as exc:
        return {"success": False, "message": str(exc)}
