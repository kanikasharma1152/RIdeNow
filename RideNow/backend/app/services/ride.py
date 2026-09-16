"""
Ride service — business logic for all ride operations.

State machine:
  REQUESTED → ACCEPTED (auto-match or driver accepts)
  ACCEPTED  → STARTED  (driver starts ride)
  STARTED   → COMPLETED (driver completes ride)
  REQUESTED | ACCEPTED → CANCELLED (passenger cancels)
  ACCEPTED  → REQUESTED (driver rejects; re-match attempted)
"""

from decimal import Decimal
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.notification import send_notification
from app.core.connection_manager import ws_manager


async def _emit_ws_event(
    event_type: str,
    ride_id: int,
    passenger_user_id: int | None = None,
    driver_user_id: int | None = None,
    payload: dict | None = None,
):
    try:
        await ws_manager.send_ride_event(
            event_type=event_type,
            ride_id=ride_id,
            passenger_user_id=passenger_user_id,
            driver_user_id=driver_user_id,
            payload=payload or {},
        )
    except Exception:
        pass

from app.repositories.ride import (
    create_ride,
    get_ride_by_id,
    get_ride_by_id_for_update,
    get_rides_by_passenger,
    get_rides_by_driver,
    get_rides_by_passenger_paginated,
    get_rides_by_driver_paginated,
    get_requested_rides,
    assign_driver,
    reset_ride_to_requested,
    update_ride_status,
    cancel_ride,
    get_driver_earnings_stats,
)

from app.repositories.rejection import (
    create_rejection,
    get_rejected_driver_ids,
    has_driver_rejected,
)

from app.repositories.driver import (
    get_driver_by_user_id,
    get_driver_by_id,
    get_available_drivers,
    update_driver_availability,
)

from app.services.google_map import (
    geocode_address,
    calculate_route_distance,
)

from app.core.exceptions import (
    RideNotFoundError,
    UnauthorizedRideAccessError,
    InvalidRideStateError,
    DriverNotFoundError,
    DriverUnavailableError,
    NoAvailableDriverError,
    DuplicateResourceError,
)

# ─── Fare Configuration ───────────────────────────────────────────────────────

BASE_FARE = Decimal("50.00")
PER_KM_RATE = Decimal("12.00")

MAX_PAGE_SIZE = 50


def calculate_fare(distance_km: float | Decimal) -> Decimal:
    distance = Decimal(str(distance_km))
    fare = BASE_FARE + (distance * PER_KM_RATE)
    return fare.quantize(Decimal("0.01"))


# ─── State Machine ────────────────────────────────────────────────────────────

VALID_TRANSITIONS: dict[str, list[str]] = {
    "REQUESTED": ["ACCEPTED"],
    "ACCEPTED": ["STARTED", "REQUESTED", "CANCELLED"],
    "STARTED": ["COMPLETED"],
    "COMPLETED": [],
    "CANCELLED": [],
}


def validate_transition(current: str, new: str):
    allowed = VALID_TRANSITIONS.get(current, [])
    if new not in allowed:
        raise InvalidRideStateError(
            f"Cannot change ride status from {current} to {new}"
        )


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))


def _clamp_page_size(page_size: int) -> int:
    return min(max(page_size, 1), MAX_PAGE_SIZE)


# ─── Driver Matching Helpers ──────────────────────────────────────────────────

async def find_next_available_driver(
    db: AsyncSession,
    ride,
    extra_excluded_driver_ids: list[int] | None = None,
):
    """
    Find the nearest available and eligible driver for a ride.
    Considers:
      - Driver is online and available (is_online=True, is_available=True)
      - Driver has valid latitude and longitude coordinates
      - Excludes any driver who has rejected this ride
      - Excludes any extra driver IDs passed (e.g. current rejecting driver)
    Returns:
      Nearest Driver or None if no eligible driver is found.
    """
    if ride.pickup_latitude is None or ride.pickup_longitude is None:
        return None

    excluded_ids = set(await get_rejected_driver_ids(db, ride_id=ride.id))
    if extra_excluded_driver_ids:
        excluded_ids.update(extra_excluded_driver_ids)

    drivers = await get_available_drivers(db)

    eligible = [
        d for d in drivers
        if d.id not in excluded_ids
        and d.latitude is not None
        and d.longitude is not None
        and d.is_online is True
        and d.is_available is True
    ]

    if not eligible:
        return None

    return min(
        eligible,
        key=lambda d: _haversine(
            ride.pickup_latitude, ride.pickup_longitude,
            d.latitude, d.longitude,
        ),
    )


async def _assign_and_notify_driver(
    db: AsyncSession,
    ride,
    driver,
    is_reassignment: bool = False,
):
    """
    Assigns driver to ride, updates driver availability to False,
    and sends notifications to both driver and passenger.
    """
    ride = await assign_driver(db=db, ride=ride, driver_id=driver.id)
    await update_driver_availability(db=db, driver=driver, is_available=False)

    # Driver notification: "New ride request available."
    await send_notification(
        db=db,
        user_id=driver.user_id,
        ride_id=ride.id,
        title="New Ride Request",
        message="New ride request available.",
    )

    # Passenger notification
    if is_reassignment:
        await send_notification(
            db=db,
            user_id=ride.passenger_id,
            ride_id=ride.id,
            title="Driver Reassigned",
            message="Your ride has been assigned to another driver.",
        )
    else:
        await send_notification(
            db=db,
            user_id=ride.passenger_id,
            ride_id=ride.id,
            title="Driver Matched",
            message="A new nearby driver has been assigned to your ride.",
        )

    # Real-time WebSocket notifications
    await _emit_ws_event(
        event_type="RIDE_ASSIGNED",
        ride_id=ride.id,
        driver_user_id=driver.user_id,
        payload={
            "ride_id": ride.id,
            "status": ride.status,
            "pickup_location": ride.pickup_location,
            "dropoff_location": ride.dropoff_location,
            "distance_km": float(ride.distance_km) if ride.distance_km else None,
            "pickup_latitude": ride.pickup_latitude,
            "pickup_longitude": ride.pickup_longitude,
            "passenger_id": ride.passenger_id,
        },
    )

    await _emit_ws_event(
        event_type="DRIVER_REASSIGNED" if is_reassignment else "DRIVER_MATCHED",
        ride_id=ride.id,
        passenger_user_id=ride.passenger_id,
        payload={
            "ride_id": ride.id,
            "status": ride.status,
            "driver_id": driver.id,
            "vehicle_model": driver.vehicle_model,
            "vehicle_number": driver.vehicle_number,
            "vehicle_type": driver.vehicle_type,
            "driver_latitude": driver.latitude,
            "driver_longitude": driver.longitude,
        },
    )

    return ride


# ─── Passenger: Request Ride ──────────────────────────────────────────────────

async def request_ride(
    db: AsyncSession,
    passenger_id: int,
    pickup_location: str,
    dropoff_location: str,
    distance_km: float | None = None,
    pickup_latitude: float | None = None,
    pickup_longitude: float | None = None,
):
    if not pickup_location.strip():
        raise ValueError("Pickup location is required")

    if not dropoff_location.strip():
        raise ValueError("Dropoff location is required")

    if pickup_location.strip().lower() == dropoff_location.strip().lower():
        raise ValueError("Pickup and dropoff locations cannot be the same")

    if pickup_latitude is None or pickup_longitude is None:
        pickup_coords = await geocode_address(pickup_location)
        pickup_latitude = pickup_coords["latitude"]
        pickup_longitude = pickup_coords["longitude"]

    dropoff_coords = await geocode_address(dropoff_location)
    dropoff_latitude = dropoff_coords["latitude"]
    dropoff_longitude = dropoff_coords["longitude"]

    distance_km = await calculate_route_distance(
        pickup_latitude, pickup_longitude,
        dropoff_latitude, dropoff_longitude,
    )

    if distance_km <= 0:
        raise ValueError("Unable to calculate a valid route distance")

    ride = await create_ride(
        db=db,
        passenger_id=passenger_id,
        pickup_location=pickup_location,
        dropoff_location=dropoff_location,
        distance_km=distance_km,
        pickup_latitude=pickup_latitude,
        pickup_longitude=pickup_longitude,
    )

    # Attempt to auto-match the nearest available driver immediately
    try:
        nearest_driver = await find_next_available_driver(db=db, ride=ride)
        if nearest_driver:
            ride = await _assign_and_notify_driver(
                db=db,
                ride=ride,
                driver=nearest_driver,
                is_reassignment=False,
            )
    except Exception:
        # If auto-matching fails on creation, ride remains in REQUESTED state
        pass

    return ride


# ─── Get Ride By ID ───────────────────────────────────────────────────────────

async def get_ride(
    db: AsyncSession,
    ride_id: int,
    user_id: int,
):
    ride = await get_ride_by_id(db, ride_id)

    if not ride:
        raise RideNotFoundError()

    if ride.passenger_id == user_id:
        return ride

    driver = await get_driver_by_user_id(db, user_id)

    if driver and ride.driver_id == driver.id:
        return ride

    raise UnauthorizedRideAccessError()


# ─── Passenger: Ride History (legacy + paginated) ─────────────────────────────

async def get_passenger_rides(
    db: AsyncSession,
    passenger_id: int,
):
    return await get_rides_by_passenger(db=db, passenger_id=passenger_id)


async def get_passenger_rides_paginated(
    db: AsyncSession,
    passenger_id: int,
    page: int = 1,
    page_size: int = 10,
    status: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    sort: str = "newest",
):
    page_size = _clamp_page_size(page_size)
    page = max(page, 1)

    items, total, total_pages = await get_rides_by_passenger_paginated(
        db=db,
        passenger_id=passenger_id,
        page=page,
        page_size=page_size,
        status=status,
        start_date=start_date,
        end_date=end_date,
        sort=sort,
    )

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
    }


# ─── Driver: Ride History (legacy + paginated) ────────────────────────────────

async def get_driver_rides(
    db: AsyncSession,
    user_id: int,
):
    driver = await get_driver_by_user_id(db, user_id)
    if not driver:
        raise DriverNotFoundError()
    return await get_rides_by_driver(db=db, driver_id=driver.id)


async def get_driver_rides_paginated(
    db: AsyncSession,
    user_id: int,
    page: int = 1,
    page_size: int = 10,
    status: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    sort: str = "newest",
):
    driver = await get_driver_by_user_id(db, user_id)
    if not driver:
        raise DriverNotFoundError()

    page_size = _clamp_page_size(page_size)
    page = max(page, 1)

    items, total, total_pages = await get_rides_by_driver_paginated(
        db=db,
        driver_id=driver.id,
        page=page,
        page_size=page_size,
        status=status,
        start_date=start_date,
        end_date=end_date,
        sort=sort,
    )

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
    }


# ─── Driver: Available Rides ─────────────────────────────────────────────────

async def get_available_rides(
    db: AsyncSession,
    user_id: int,
):
    driver = await get_driver_by_user_id(db, user_id)
    if not driver:
        raise DriverNotFoundError()
    if not driver.is_online:
        raise DriverUnavailableError("Driver is offline")
    if not driver.is_available:
        raise DriverUnavailableError("Driver is not available")

    return await get_requested_rides(db)


# ─── Driver: Accept Ride ─────────────────────────────────────────────────────

async def accept_ride(
    db: AsyncSession,
    user_id: int,
    ride_id: int,
):
    driver = await get_driver_by_user_id(db, user_id)
    if not driver:
        raise DriverNotFoundError()
    if not driver.is_online:
        raise DriverUnavailableError("Driver is offline")
    if not driver.is_available:
        raise DriverUnavailableError("Driver is not available")

    ride = await get_ride_by_id(db, ride_id)
    if not ride:
        raise RideNotFoundError()

    validate_transition(ride.status, "ACCEPTED")

    if ride.driver_id is not None:
        raise InvalidRideStateError("Ride already has a driver")

    # Check driver hasn't already rejected this ride
    if await has_driver_rejected(db, ride_id=ride.id, driver_id=driver.id):
        raise InvalidRideStateError("You have already rejected this ride")

    ride = await assign_driver(db=db, ride=ride, driver_id=driver.id)
    await update_driver_availability(db=db, driver=driver, is_available=False)

    await send_notification(
        db=db,
        user_id=ride.passenger_id,
        ride_id=ride.id,
        title="Ride Accepted",
        message="Your ride has been accepted by a driver.",
    )

    await _emit_ws_event(
        event_type="RIDE_ACCEPTED",
        ride_id=ride.id,
        passenger_user_id=ride.passenger_id,
        driver_user_id=driver.user_id,
        payload={"ride_id": ride.id, "status": "ACCEPTED", "driver_id": driver.id},
    )

    return ride


# ─── Driver: Reject Ride ─────────────────────────────────────────────────────

async def reject_ride(
    db: AsyncSession,
    user_id: int,
    ride_id: int,
) -> dict:
    driver = await get_driver_by_user_id(db, user_id)
    if not driver:
        raise DriverNotFoundError()

    ride = await get_ride_by_id_for_update(db, ride_id)
    if not ride:
        raise RideNotFoundError()

    # Only the assigned driver can reject
    if ride.driver_id != driver.id:
        raise UnauthorizedRideAccessError("You are not assigned to this ride")

    # Completed or cancelled rides cannot be rejected
    if ride.status in ("STARTED", "COMPLETED", "CANCELLED"):
        raise InvalidRideStateError(
            f"Cannot reject a ride with status {ride.status}"
        )

    if ride.status not in ("ACCEPTED", "REQUESTED"):
        raise InvalidRideStateError(
            f"Cannot reject a ride with status {ride.status}"
        )

    # Prevent duplicate rejection
    if await has_driver_rejected(db, ride_id=ride.id, driver_id=driver.id):
        raise DuplicateResourceError("You have already rejected this ride")

    # 1. Create RideDriverRejection record
    await create_rejection(db=db, ride_id=ride.id, driver_id=driver.id)

    # 2. Make the current driver available again
    await update_driver_availability(db=db, driver=driver, is_available=True)

    # 3. Remove driver assignment from ride and keep ride active in REQUESTED state
    ride = await reset_ride_to_requested(db=db, ride=ride)

    # Notify rejecting driver via WebSocket that rejection succeeded
    await _emit_ws_event(
        event_type="RIDE_REJECTED",
        ride_id=ride.id,
        driver_user_id=driver.user_id,
        payload={"ride_id": ride.id, "status": "REJECTED"},
    )

    # 4. Search for next eligible driver
    next_driver = await find_next_available_driver(
        db=db,
        ride=ride,
        extra_excluded_driver_ids=[driver.id],
    )

    if next_driver:
        await _assign_and_notify_driver(
            db=db,
            ride=ride,
            driver=next_driver,
            is_reassignment=True,
        )
        return {
            "message": "Ride rejected. Searching for another driver.",
            "ride_id": ride.id,
            "next_driver_found": True,
        }
    else:
        # No eligible driver remains — keep ride in REQUESTED state
        await send_notification(
            db=db,
            user_id=ride.passenger_id,
            ride_id=ride.id,
            title="No Driver Available",
            message="No available drivers found. Please wait or try again.",
        )
        await _emit_ws_event(
            event_type="NO_DRIVER_AVAILABLE",
            ride_id=ride.id,
            passenger_user_id=ride.passenger_id,
            payload={"ride_id": ride.id, "status": "REQUESTED"},
        )
        return {
            "message": "No available drivers found. Please wait or try again.",
            "ride_id": ride.id,
            "next_driver_found": False,
        }


# ─── Driver: Start / Complete Ride ───────────────────────────────────────────

async def change_ride_status(
    db: AsyncSession,
    user_id: int,
    ride_id: int,
    new_status: str,
):
    driver = await get_driver_by_user_id(db, user_id)
    if not driver:
        raise DriverNotFoundError()

    ride = await get_ride_by_id(db, ride_id)
    if not ride:
        raise RideNotFoundError()

    if ride.driver_id != driver.id:
        raise UnauthorizedRideAccessError("You are not assigned to this ride")

    validate_transition(ride.status, new_status)

    fare = None
    if new_status == "COMPLETED":
        fare = calculate_fare(ride.distance_km)

    ride = await update_ride_status(db=db, ride=ride, status=new_status, fare=fare)

    if new_status == "STARTED":
        await send_notification(
            db=db,
            user_id=ride.passenger_id,
            ride_id=ride.id,
            title="Ride Started",
            message="Your ride has started. Enjoy your trip!",
        )

    if new_status == "COMPLETED":
        await send_notification(
            db=db,
            user_id=ride.passenger_id,
            ride_id=ride.id,
            title="Ride Completed",
            message=f"Your ride is completed. Fare: ₹{fare}",
        )
        await send_notification(
            db=db,
            user_id=driver.user_id,
            ride_id=ride.id,
            title="Ride Completed",
            message=f"Ride #{ride.id} completed. Fare: ₹{fare}",
        )
        await update_driver_availability(db=db, driver=driver, is_available=True)

    await _emit_ws_event(
        event_type=f"RIDE_{new_status}",
        ride_id=ride.id,
        passenger_user_id=ride.passenger_id,
        driver_user_id=driver.user_id,
        payload={
            "ride_id": ride.id,
            "status": new_status,
            "fare": float(fare) if fare else None,
        },
    )

    return ride


# ─── Passenger: Cancel Ride ───────────────────────────────────────────────────

async def cancel_passenger_ride(
    db: AsyncSession,
    passenger_id: int,
    ride_id: int,
):
    ride = await get_ride_by_id(db, ride_id)
    if not ride:
        raise RideNotFoundError()

    if ride.passenger_id != passenger_id:
        raise UnauthorizedRideAccessError("You are not allowed to cancel this ride")

    validate_transition(ride.status, "CANCELLED")

    driver = None
    if ride.status == "ACCEPTED" and ride.driver_id is not None:
        driver = await get_driver_by_id(db, ride.driver_id)

    ride = await cancel_ride(db=db, ride=ride)

    if driver:
        await update_driver_availability(db=db, driver=driver, is_available=True)
        await send_notification(
            db=db,
            user_id=driver.user_id,
            ride_id=ride.id,
            title="Ride Cancelled",
            message=f"Passenger cancelled ride #{ride.id}.",
        )

    await send_notification(
        db=db,
        user_id=ride.passenger_id,
        ride_id=ride.id,
        title="Ride Cancelled",
        message="Your ride has been cancelled.",
    )

    await _emit_ws_event(
        event_type="RIDE_CANCELLED",
        ride_id=ride.id,
        passenger_user_id=ride.passenger_id,
        driver_user_id=driver.user_id if driver else None,
        payload={"ride_id": ride.id, "status": "CANCELLED"},
    )

    return ride


# ─── Auto-match Driver (passenger initiates) ─────────────────────────────────

async def auto_match_driver(
    db: AsyncSession,
    ride_id: int,
    passenger_id: int,
):
    ride = await get_ride_by_id_for_update(db, ride_id)
    if not ride:
        raise RideNotFoundError()

    if ride.passenger_id != passenger_id:
        raise UnauthorizedRideAccessError("You are not allowed to match this ride")

    # If already matched and accepted, return existing match
    if ride.driver_id is not None and ride.status == "ACCEPTED":
        return ride

    if ride.status != "REQUESTED":
        raise InvalidRideStateError("Ride is no longer available for matching")

    if ride.pickup_latitude is None or ride.pickup_longitude is None:
        raise InvalidRideStateError("Ride pickup coordinates are required")

    next_driver = await find_next_available_driver(db=db, ride=ride)
    if not next_driver:
        raise NoAvailableDriverError("No available drivers found")

    return await _assign_and_notify_driver(
        db=db,
        ride=ride,
        driver=next_driver,
        is_reassignment=False,
    )


# ─── Driver: Earnings ─────────────────────────────────────────────────────────

async def get_driver_earnings(
    db: AsyncSession,
    user_id: int,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
):
    driver = await get_driver_by_user_id(db, user_id)
    if not driver:
        raise DriverNotFoundError()

    return await get_driver_earnings_stats(
        db=db,
        driver_id=driver.id,
        start_date=start_date,
        end_date=end_date,
    )
