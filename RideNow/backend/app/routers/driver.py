import asyncio
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.driver import (
    DriverCreate,
    DriverResponse,
    DriverUpdate,
    DriverLocationUpdate,
    DriverLocationResponse,
)
from app.schemas.earnings import EarningsResponse

from app.services.driver import (
    register_driver,
    get_driver,
    get_my_driver_profile,
    get_available_driver_list,
    change_driver_status,
    change_driver_location,
    update_driver_profile_service,
)

from app.services.ride import get_driver_earnings
from app.core.connection_manager import ws_manager
from app.routers.user import get_current_user, require_role
from app.core.exceptions import RideNowError, DuplicateResourceError


router = APIRouter(
    prefix="/drivers",
    tags=["Drivers"],
)



def _handle_ridenow_error(e: RideNowError):
    raise HTTPException(status_code=e.status_code, detail=e.message)


# =========================
# Register Driver
# =========================

@router.post(
    "/register",
    response_model=DriverResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register as a driver",
    description="Create a driver profile for the authenticated user.",
)
async def register_driver_api(
    driver_data: DriverCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        driver = await register_driver(
            db=db,
            user_id=current_user.id,
            license_number=driver_data.license_number,
            vehicle_type=driver_data.vehicle_type,
            vehicle_number=driver_data.vehicle_number,
            vehicle_model=driver_data.vehicle_model,
        )
        return driver
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# =========================
# My Driver Profile
# =========================

@router.get(
    "/me/profile",
    response_model=DriverResponse,
    summary="Get my driver profile",
    description="Returns the authenticated driver's profile.",
)
async def get_my_driver(
    current_user=Depends(require_role("driver")),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await get_my_driver_profile(db, current_user.id)
    except RideNowError as e:
        _handle_ridenow_error(e)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# =========================
# Update Driver Profile
# =========================

@router.patch(
    "/me",
    response_model=DriverResponse,
    summary="Update driver profile",
    description="Update vehicle info or license for the authenticated driver.",
)
async def update_my_driver_profile(
    update_data: DriverUpdate,
    current_user=Depends(require_role("driver")),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await update_driver_profile_service(
            db=db,
            user_id=current_user.id,
            vehicle_type=update_data.vehicle_type,
            vehicle_number=update_data.vehicle_number,
            vehicle_model=update_data.vehicle_model,
            license_number=update_data.license_number,
        )
    except DuplicateResourceError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.message,
        )
    except RideNowError as e:
        _handle_ridenow_error(e)


# =========================
# Driver Earnings
# =========================

@router.get(
    "/earnings",
    response_model=EarningsResponse,
    summary="Get driver earnings",
    description="Returns total/today/week/month earnings calculated from completed rides.",
)
async def get_earnings_api(
    start_date: Optional[datetime] = Query(None, description="Filter from date"),
    end_date: Optional[datetime] = Query(None, description="Filter to date"),
    current_user=Depends(require_role("driver")),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await get_driver_earnings(
            db=db,
            user_id=current_user.id,
            start_date=start_date,
            end_date=end_date,
        )
    except RideNowError as e:
        _handle_ridenow_error(e)


# =========================
# Available Drivers
# =========================

@router.get(
    "/available",
    response_model=list[DriverResponse],
    summary="List available drivers",
    description="Returns all drivers that are online and available.",
)
async def get_available_drivers_api(
    current_user=Depends(require_role("driver")),
    db: AsyncSession = Depends(get_db),
):
    return await get_available_driver_list(db)


# =========================
# Update Driver Status
# =========================

@router.patch(
    "/status",
    response_model=DriverResponse,
    summary="Update online/availability status",
    description="Toggle driver online/offline and availability.",
)
async def update_driver_status_api(
    is_online: bool,
    is_available: bool,
    current_user=Depends(require_role("driver")),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await change_driver_status(
            db=db,
            user_id=current_user.id,
            is_online=is_online,
            is_available=is_available,
        )
    except RideNowError as e:
        _handle_ridenow_error(e)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# =========================
# Get Driver By ID
# =========================

@router.get(
    "/{driver_id}",
    response_model=DriverResponse,
    summary="Get driver by ID",
)
async def get_driver_api(
    driver_id: int,
    current_user=Depends(require_role("driver")),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await get_driver(db, driver_id)
    except RideNowError as e:
        _handle_ridenow_error(e)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# =========================
# Update Driver Location
# =========================

@router.patch(
    "/location",
    response_model=DriverLocationResponse,
    summary="Update driver location",
    description="Send current GPS coordinates for the authenticated driver.",
)
async def update_driver_location_api(
    location_data: DriverLocationUpdate,
    current_user=Depends(require_role("driver")),
    db: AsyncSession = Depends(get_db),
):
    try:
        driver = await change_driver_location(
            db=db,
            user_id=current_user.id,
            latitude=location_data.latitude,
            longitude=location_data.longitude,
        )

        # Broadcast real-time location to admin subscribers and any passenger
        # watching this driver via WebSocket — fire-and-forget, non-blocking
        location_event = {
            "type": "driver_location",
            "data": {
                "driver_id": driver.id,
                "user_id": current_user.id,
                "latitude": driver.latitude,
                "longitude": driver.longitude,
            },
        }
        asyncio.ensure_future(ws_manager.broadcast_to_role("admin", location_event))


        return {
            "driver_id": driver.id,
            "latitude": driver.latitude,
            "longitude": driver.longitude,
            "location_updated_at": driver.location_updated_at,
        }
    except RideNowError as e:
        _handle_ridenow_error(e)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )