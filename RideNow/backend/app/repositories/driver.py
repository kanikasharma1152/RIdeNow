from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.driver import Driver

from datetime import datetime


async def create_driver(
    db: AsyncSession,
    user_id: int,
    license_number: str,
    vehicle_type: str,
    vehicle_number: str,
    vehicle_model: str
):
    driver = Driver(
        user_id=user_id,
        license_number=license_number,
        vehicle_type=vehicle_type,
        vehicle_number=vehicle_number,
        vehicle_model=vehicle_model
    )

    db.add(driver)

    await db.commit()
    await db.refresh(driver)

    return driver


async def get_driver_by_id(
    db: AsyncSession,
    driver_id: int
):
    result = await db.execute(
        select(Driver).where(
            Driver.id == driver_id
        )
    )

    return result.scalar_one_or_none()


async def get_driver_by_user_id(
    db: AsyncSession,
    user_id: int
):
    result = await db.execute(
        select(Driver).where(
            Driver.user_id == user_id
        )
    )

    return result.scalar_one_or_none()


async def get_driver_by_license(
    db: AsyncSession,
    license_number: str
):
    result = await db.execute(
        select(Driver).where(
            Driver.license_number == license_number
        )
    )

    return result.scalar_one_or_none()


async def get_driver_by_vehicle_number(
    db: AsyncSession,
    vehicle_number: str
):
    result = await db.execute(
        select(Driver).where(
            Driver.vehicle_number == vehicle_number
        )
    )

    return result.scalar_one_or_none()


async def get_available_drivers(
    db: AsyncSession
):
    result = await db.execute(
        select(Driver).where(
            Driver.is_online.is_(True),
            Driver.is_available.is_(True)
        )
    )

    return result.scalars().all()


async def update_driver_status(
    db: AsyncSession,
    driver: Driver,
    is_online: bool,
    is_available: bool
):
    driver.is_online = is_online
    driver.is_available = is_available

    await db.commit()
    await db.refresh(driver)

    return driver

async def update_driver_availability(
    db: AsyncSession,
    driver: Driver,
    is_available: bool
):
    driver.is_available = is_available

    await db.commit()
    await db.refresh(driver)

    return driver

from datetime import datetime


async def update_driver_location(
    db: AsyncSession,
    driver: Driver,
    latitude: float,
    longitude: float
):
    driver.latitude = latitude
    driver.longitude = longitude
    driver.location_updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(driver)

    return driver


async def update_driver_profile(
    db: AsyncSession,
    driver: Driver,
    vehicle_type: str | None = None,
    vehicle_number: str | None = None,
    vehicle_model: str | None = None,
    license_number: str | None = None,
) -> Driver:
    if vehicle_type is not None:
        driver.vehicle_type = vehicle_type
    if vehicle_number is not None:
        driver.vehicle_number = vehicle_number
    if vehicle_model is not None:
        driver.vehicle_model = vehicle_model
    if license_number is not None:
        driver.license_number = license_number

    await db.commit()
    await db.refresh(driver)
    return driver