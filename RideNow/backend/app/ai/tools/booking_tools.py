"""
RideNow AI — Natural Language Ride Booking Tool
===============================================
Handles conversational ride creation with:
1. Role-based security (passenger only; driver disallowed)
2. Location resolution & geocoding via existing service layer
3. Transparent fare calculation using standard pricing (₹50 base + ₹12/km)
4. Two-step confirmation safety (asks confirmation with exact fare)
5. Idempotent booking protection (prevents duplicate active rides)
6. Direct integration with existing app.services.ride engine
"""

import json
import logging
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_client
from app.services.ride import (
    request_ride,
    get_passenger_rides,
    calculate_fare,
)
from app.services.google_map import geocode_address, calculate_route_distance
from app.services.location_intelligence import check_ambiguity
from app.core.exceptions import RideNowError

logger = logging.getLogger(__name__)

PENDING_BOOKING_TTL = 600  # 10 minutes


def _pending_key(user_id: int) -> str:
    return f"pending_booking:user:{user_id}"


async def store_pending_booking(user_id: int, booking_data: Dict[str, Any]) -> None:
    client = get_redis_client()
    key = _pending_key(user_id)
    await client.set(key, json.dumps(booking_data, default=str), ex=PENDING_BOOKING_TTL)


async def get_pending_booking(user_id: int) -> Optional[Dict[str, Any]]:
    client = get_redis_client()
    key = _pending_key(user_id)
    raw = await client.get(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


async def clear_pending_booking(user_id: int) -> None:
    client = get_redis_client()
    key = _pending_key(user_id)
    await client.delete(key)


async def book_ride_tool(
    current_user,
    db: AsyncSession,
    pickup_location: Optional[str] = None,
    dropoff_location: Optional[str] = None,
    pickup_latitude: Optional[float] = None,
    pickup_longitude: Optional[float] = None,
    dropoff_latitude: Optional[float] = None,
    dropoff_longitude: Optional[float] = None,
    confirmed: bool = False,
    vehicle_type: Optional[str] = "standard",
    idempotency_key: Optional[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Validates and executes a ride booking for the authenticated passenger.
    If confirmed=False, returns fare & details asking for confirmation.
    If confirmed=True, calls existing ride service and creates the trip.
    """
    # 1. Authorization: Only passengers may book rides
    if getattr(current_user, "role", None) != "passenger":
        return {
            "success": False,
            "error": "Permission denied: Only passengers can book rides. Driver accounts cannot request trips.",
        }

    # 2. Check pending booking memory if arguments are omitted on confirmation
    if (not pickup_location or not dropoff_location) and confirmed:
        pending = await get_pending_booking(current_user.id)
        if pending:
            pickup_location = pickup_location or pending.get("pickup_location")
            dropoff_location = dropoff_location or pending.get("dropoff_location")
            pickup_latitude = pickup_latitude or pending.get("pickup_latitude")
            pickup_longitude = pickup_longitude or pending.get("pickup_longitude")
            dropoff_latitude = dropoff_latitude or pending.get("dropoff_latitude")
            dropoff_longitude = dropoff_longitude or pending.get("dropoff_longitude")

    if not pickup_location or not pickup_location.strip():
        return {
            "success": False,
            "requires_input": True,
            "missing_field": "pickup_location",
            "message": "Where should the driver pick you up? Please provide a pickup address or landmark.",
        }

    if not dropoff_location or not dropoff_location.strip():
        return {
            "success": False,
            "requires_input": True,
            "missing_field": "dropoff_location",
            "message": "Where would you like to go? Please provide your destination address or landmark.",
        }

    # 3. Check for ambiguous generic destinations
    ambiguity_options = check_ambiguity(dropoff_location)
    if ambiguity_options:
        return {
            "success": False,
            "requires_clarification": True,
            "options": ambiguity_options,
            "message": f"Which specific location do you mean? For example: {', '.join(ambiguity_options)}.",
        }

    # 4. Prevent duplicate booking: check if user already has an active ride in progress
    try:
        my_rides = await get_passenger_rides(db, current_user.id)
        rides_list = my_rides if isinstance(my_rides, list) else getattr(my_rides, "items", [])
        active_ride = next(
            (r for r in rides_list if r.status in ("REQUESTED", "ACCEPTED", "STARTED")),
            None,
        )
        if active_ride:
            return {
                "success": False,
                "already_active": True,
                "ride_id": active_ride.id,
                "status": active_ride.status,
                "pickup_location": active_ride.pickup_location,
                "dropoff_location": active_ride.dropoff_location,
                "message": (
                    f"You already have an active ride #{active_ride.id} in progress ({active_ride.status}) "
                    f"from '{active_ride.pickup_location}' to '{active_ride.dropoff_location}'. "
                    f"Please complete or cancel your active ride before booking a new one."
                ),
            }
    except Exception as exc:
        logger.warning(f"Error checking active rides before booking: {exc}")

    # 5. Location resolution and distance calculation
    try:
        # Geocode pickup if lat/lng missing
        if pickup_latitude is None or pickup_longitude is None:
            pick_coords = await geocode_address(pickup_location)
            pickup_latitude = pick_coords["latitude"]
            pickup_longitude = pick_coords["longitude"]

        # Geocode dropoff if lat/lng missing
        if dropoff_latitude is None or dropoff_longitude is None:
            drop_coords = await geocode_address(dropoff_location)
            dropoff_latitude = drop_coords["latitude"]
            dropoff_longitude = drop_coords["longitude"]

        # Calculate driving distance via OSRM
        dist_km = await calculate_route_distance(
            pickup_latitude, pickup_longitude,
            dropoff_latitude, dropoff_longitude,
        )
        fare_amt = calculate_fare(dist_km)
    except Exception as exc:
        logger.warning(f"Location resolution failed for booking: {exc}")
        return {
            "success": False,
            "error": "Unable to calculate route for the given locations. Please check the address names and try again.",
        }

    # 6. Safety Confirmation Gate: If not explicitly confirmed, return confirmation prompt
    if not confirmed:
        booking_data = {
            "pickup_location": pickup_location.strip(),
            "dropoff_location": dropoff_location.strip(),
            "pickup_latitude": pickup_latitude,
            "pickup_longitude": pickup_longitude,
            "dropoff_latitude": dropoff_latitude,
            "dropoff_longitude": dropoff_longitude,
            "distance_km": float(dist_km),
            "estimated_fare": float(fare_amt),
        }
        await store_pending_booking(current_user.id, booking_data)

        return {
            "success": False,
            "requires_confirmation": True,
            "pickup": pickup_location.strip(),
            "dropoff": dropoff_location.strip(),
            "distance_km": float(dist_km),
            "estimated_fare": f"₹{fare_amt}",
            "message": (
                f"🚖 **Trip Summary:**\n"
                f"- **From:** {pickup_location.strip()}\n"
                f"- **To:** {dropoff_location.strip()}\n"
                f"- **Distance:** {dist_km} km\n"
                f"- **Estimated Fare:** **₹{fare_amt}**\n\n"
                f"Shall I confirm and book this ride for you?"
            ),
        }

    # 7. Confirmed booking execution through existing service layer
    try:
        ride = await request_ride(
            db=db,
            passenger_id=current_user.id,
            pickup_location=pickup_location.strip(),
            dropoff_location=dropoff_location.strip(),
            distance_km=dist_km,
            pickup_latitude=pickup_latitude,
            pickup_longitude=pickup_longitude,
        )

        # Clear pending booking state upon success
        await clear_pending_booking(current_user.id)

        driver_info = "Searching for the nearest available driver..."
        if ride.driver_id:
            driver_info = f"Driver assigned (Driver #{ride.driver_id})!"

        return {
            "success": True,
            "ride_id": ride.id,
            "status": ride.status,
            "pickup": ride.pickup_location,
            "dropoff": ride.dropoff_location,
            "distance_km": float(ride.distance_km) if ride.distance_km else float(dist_km),
            "fare": float(ride.fare) if ride.fare else float(fare_amt),
            "driver_id": ride.driver_id,
            "message": (
                f"🎉 **Ride #{ride.id} booked successfully!**\n\n"
                f"- **Pickup:** {ride.pickup_location}\n"
                f"- **Destination:** {ride.dropoff_location}\n"
                f"- **Fare:** ₹{ride.fare or fare_amt}\n"
                f"- **Status:** `{ride.status}` ({driver_info})\n\n"
                f"You can track your ride live on your dashboard map."
            ),
        }
    except RideNowError as exc:
        logger.error(f"RideNowError during book_ride: {exc.message}")
        return {"success": False, "error": exc.message}
    except Exception as exc:
        logger.error(f"Unexpected error during book_ride: {exc}", exc_info=True)
        return {
            "success": False,
            "error": "Could not complete the ride booking right now. Please try again in a moment.",
        }
