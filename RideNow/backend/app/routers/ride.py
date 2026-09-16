from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.ride import RideCreate, RideResponse, RideRejectionResponse
from app.schemas.pagination import PaginatedResponse

from app.services.ride import (
    request_ride,
    get_ride,
    get_passenger_rides,
    get_driver_rides,
    get_available_rides,
    accept_ride,
    change_ride_status,
    cancel_passenger_ride,
    auto_match_driver,
    reject_ride,
    get_passenger_rides_paginated,
    get_driver_rides_paginated,
)

from app.routers.user import (
    get_current_user,
    require_passenger,
    require_driver,
)

from app.core.exceptions import (
    RideNowError,
    RideNotFoundError,
    UnauthorizedRideAccessError,
    InvalidRideStateError,
    DriverNotFoundError,
    DriverUnavailableError,
    NoAvailableDriverError,
    DuplicateResourceError,
)


router = APIRouter(
    prefix="/rides",
    tags=["Rides"],
)


def _handle_ridenow_error(e: RideNowError):
    raise HTTPException(
        status_code=e.status_code,
        detail=e.message,
    )


# =========================
# Passenger - Request Ride
# =========================

@router.post(
    "/request",
    response_model=RideResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Request a new ride",
    description="Passenger creates a ride request. Backend geocodes and calculates distance automatically.",
)
async def request_ride_api(
    ride_data: RideCreate,
    current_user=Depends(require_passenger),
    db: AsyncSession = Depends(get_db),
):
    try:
        ride = await request_ride(
            db=db,
            passenger_id=current_user.id,
            pickup_location=ride_data.pickup_location,
            dropoff_location=ride_data.dropoff_location,
            distance_km=ride_data.distance_km,
            pickup_latitude=ride_data.pickup_latitude,
            pickup_longitude=ride_data.pickup_longitude,
        )
        return ride
    except RideNowError as e:
        _handle_ridenow_error(e)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# =========================
# Passenger - My Rides (legacy — keeps frontend compatible)
# =========================

@router.get(
    "/my",
    response_model=list[RideResponse],
    summary="Get passenger rides",
    description="Returns all rides for the authenticated passenger (no pagination).",
)
async def my_rides_api(
    current_user=Depends(require_passenger),
    db: AsyncSession = Depends(get_db),
):
    return await get_passenger_rides(
        db=db,
        passenger_id=current_user.id,
    )


# =========================
# Passenger - Paginated Ride History
# =========================

@router.get(
    "/my/history",
    response_model=PaginatedResponse[RideResponse],
    summary="Paginated passenger ride history",
    description="Filterable, paginated ride history for the authenticated passenger.",
)
async def my_rides_history_api(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=50, description="Page size (max 50)"),
    ride_status: Optional[str] = Query(None, alias="status", description="Filter by ride status"),
    start_date: Optional[datetime] = Query(None, description="Filter from date"),
    end_date: Optional[datetime] = Query(None, description="Filter to date"),
    sort: Optional[str] = Query("newest", description="Sort order: newest or oldest"),
    current_user=Depends(require_passenger),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await get_passenger_rides_paginated(
            db=db,
            passenger_id=current_user.id,
            page=page,
            page_size=page_size,
            status=ride_status,
            start_date=start_date,
            end_date=end_date,
            sort=sort or "newest",
        )
    except RideNowError as e:
        _handle_ridenow_error(e)


# =========================
# Driver - Available Rides
# =========================

@router.get(
    "/available",
    response_model=list[RideResponse],
    summary="Get available rides",
    description="Returns rides with status REQUESTED that have no assigned driver.",
)
async def available_rides_api(
    current_user=Depends(require_driver),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await get_available_rides(
            db=db,
            user_id=current_user.id,
        )
    except RideNowError as e:
        _handle_ridenow_error(e)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# =========================
# Auto-match driver
# =========================

@router.patch(
    "/{ride_id}/match",
    response_model=RideResponse,
    summary="Auto-match nearest driver",
    description="Finds and assigns the nearest available driver to the ride.",
)
async def match_driver_api(
    ride_id: int,
    current_user=Depends(require_passenger),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await auto_match_driver(
            db=db,
            ride_id=ride_id,
            passenger_id=current_user.id,
        )
    except RideNowError as e:
        _handle_ridenow_error(e)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# =========================
# Driver - Accept Ride
# =========================

@router.patch(
    "/{ride_id}/accept",
    response_model=RideResponse,
    summary="Accept a ride",
    description="Driver accepts an available ride request.",
)
async def accept_ride_api(
    ride_id: int,
    current_user=Depends(require_driver),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await accept_ride(
            db=db,
            user_id=current_user.id,
            ride_id=ride_id,
        )
    except RideNowError as e:
        _handle_ridenow_error(e)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# =========================
# Driver - Reject Ride
# =========================

@router.post(
    "/{ride_id}/reject",
    response_model=RideRejectionResponse,
    summary="Reject an assigned ride",
    description="Driver rejects the assigned ride. The rejection is recorded, the driver is marked available again, and the system automatically searches for and assigns the next nearest eligible driver.",
    responses={
        200: {
            "description": "Ride rejected successfully",
            "content": {
                "application/json": {
                    "examples": {
                        "next_driver_found": {
                            "summary": "Next driver found",
                            "value": {
                                "message": "Ride rejected. Searching for another driver.",
                                "ride_id": 20,
                                "next_driver_found": True,
                            },
                        },
                        "no_driver_found": {
                            "summary": "No available drivers found",
                            "value": {
                                "message": "No available drivers found. Please wait or try again.",
                                "ride_id": 20,
                                "next_driver_found": False,
                            },
                        },
                    }
                }
            },
        },
        400: {"description": "Invalid ride state for rejection (e.g. completed, cancelled, started)"},
        403: {"description": "Driver not assigned to this ride or passenger role"},
        404: {"description": "Ride or driver not found"},
        409: {"description": "Driver has already rejected this ride"},
    },
)
async def reject_ride_api(
    ride_id: int,
    current_user=Depends(require_driver),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await reject_ride(
            db=db,
            user_id=current_user.id,
            ride_id=ride_id,
        )
    except RideNowError as e:
        _handle_ridenow_error(e)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# =========================
# Driver - My Rides (legacy)
# =========================

@router.get(
    "/driver/my",
    response_model=list[RideResponse],
    summary="Get driver rides",
    description="Returns all rides assigned to the authenticated driver (no pagination).",
)
async def driver_rides_api(
    current_user=Depends(require_driver),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await get_driver_rides(
            db=db,
            user_id=current_user.id,
        )
    except RideNowError as e:
        _handle_ridenow_error(e)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# =========================
# Driver - Paginated Ride History
# =========================

@router.get(
    "/driver/my/history",
    response_model=PaginatedResponse[RideResponse],
    summary="Paginated driver ride history",
    description="Filterable, paginated ride history for the authenticated driver.",
)
async def driver_rides_history_api(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    ride_status: Optional[str] = Query(None, alias="status"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    sort: Optional[str] = Query("newest", description="Sort order: newest or oldest"),
    current_user=Depends(require_driver),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await get_driver_rides_paginated(
            db=db,
            user_id=current_user.id,
            page=page,
            page_size=page_size,
            status=ride_status,
            start_date=start_date,
            end_date=end_date,
            sort=sort or "newest",
        )
    except RideNowError as e:
        _handle_ridenow_error(e)


# =========================
# Driver - Start Ride
# =========================

@router.patch(
    "/{ride_id}/start",
    response_model=RideResponse,
    summary="Start a ride",
    description="Driver starts an accepted ride.",
)
async def start_ride_api(
    ride_id: int,
    current_user=Depends(require_driver),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await change_ride_status(
            db=db,
            user_id=current_user.id,
            ride_id=ride_id,
            new_status="STARTED",
        )
    except RideNowError as e:
        _handle_ridenow_error(e)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# =========================
# Driver - Complete Ride
# =========================

@router.patch(
    "/{ride_id}/complete",
    response_model=RideResponse,
    summary="Complete a ride",
    description="Driver completes a started ride. Fare is calculated automatically.",
)
async def complete_ride_api(
    ride_id: int,
    current_user=Depends(require_driver),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await change_ride_status(
            db=db,
            user_id=current_user.id,
            ride_id=ride_id,
            new_status="COMPLETED",
        )
    except RideNowError as e:
        _handle_ridenow_error(e)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# =========================
# Passenger - Cancel Ride
# =========================

@router.patch(
    "/{ride_id}/cancel",
    response_model=RideResponse,
    summary="Cancel a ride",
    description="Passenger cancels a ride. Only REQUESTED or ACCEPTED rides can be cancelled.",
)
async def cancel_ride_api(
    ride_id: int,
    current_user=Depends(require_passenger),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await cancel_passenger_ride(
            db=db,
            passenger_id=current_user.id,
            ride_id=ride_id,
        )
    except RideNowError as e:
        _handle_ridenow_error(e)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# =========================
# Get Ride By ID
# =========================

@router.get(
    "/{ride_id}",
    response_model=RideResponse,
    summary="Get ride details",
    description="Returns ride details. Only the ride's passenger or assigned driver can view it.",
)
async def get_ride_api(
    ride_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await get_ride(
            db=db,
            ride_id=ride_id,
            user_id=current_user.id,
        )
    except RideNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
        )
    except UnauthorizedRideAccessError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=e.message,
        )
    except RideNowError as e:
        _handle_ridenow_error(e)
    except ValueError as e:
        if str(e) == "Ride not found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
