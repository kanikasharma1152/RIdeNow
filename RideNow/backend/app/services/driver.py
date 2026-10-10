from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User

from app.repositories.driver import (
    create_driver,
    get_driver_by_user_id,
    get_driver_by_license,
    get_driver_by_vehicle_number,
    get_driver_by_id,
    get_available_drivers,
    update_driver_status,
    update_driver_availability,
    update_driver_location,
    update_driver_profile,
)

from app.core.exceptions import (
    DriverNotFoundError,
    DuplicateResourceError,
    DriverUnavailableError,
)


async def register_driver(
    db: AsyncSession,
    user_id: int,
    license_number: str,
    vehicle_type: str,
    vehicle_number: str,
    vehicle_model: str
):
    # Check user
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise ValueError("User not found")

    # Already a driver?
    existing_driver = await get_driver_by_user_id(db, user_id)

    if existing_driver:
        # If the record is auto-provisioned (placeholder license like DL000025),
        # treat this call as an upsert and update the credentials.
        is_placeholder = (
            existing_driver.license_number.startswith("DL")
            and existing_driver.license_number[2:].isdigit()
        )
        if is_placeholder:
            # Update existing auto-provisioned record with real credentials
            existing_driver.license_number = license_number
            existing_driver.vehicle_type = vehicle_type
            existing_driver.vehicle_number = vehicle_number
            existing_driver.vehicle_model = vehicle_model
            await db.commit()
            await db.refresh(existing_driver)
            return existing_driver
        # Real duplicate — refuse
        raise ValueError("User is already registered as a driver")

    # Check license uniqueness (only for new records)
    existing_license = await get_driver_by_license(db, license_number)
    if existing_license:
        raise ValueError("License number is already registered")

    # Check vehicle uniqueness (only for new records)
    existing_vehicle = await get_driver_by_vehicle_number(db, vehicle_number)
    if existing_vehicle:
        raise ValueError("Vehicle number is already registered")

    # Create driver profile
    driver = await create_driver(
        db=db,
        user_id=user_id,
        license_number=license_number,
        vehicle_type=vehicle_type,
        vehicle_number=vehicle_number,
        vehicle_model=vehicle_model
    )

    # Change user role
    user.role = "driver"

    await db.commit()
    await db.refresh(user)

    return driver


async def get_or_create_driver(
    db: AsyncSession,
    user_id: int
):
    """
    Retrieves the Driver record for a user. If the user has role 'driver'
    and no Driver record exists yet, automatically provisions the initial Driver record.
    Ensures zero duplicate driver records are created.
    """
    driver = await get_driver_by_user_id(db, user_id)
    if driver:
        return driver

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError("User not found")
    if user.role != "driver":
        raise DriverNotFoundError("User is not a driver")

    license_num = f"DL{user_id:06d}"
    vehicle_num = f"RN{user_id:04d}"

    existing_lic = await get_driver_by_license(db, license_num)
    if existing_lic:
        license_num = f"DL{user_id:06d}X"

    existing_veh = await get_driver_by_vehicle_number(db, vehicle_num)
    if existing_veh:
        vehicle_num = f"RN{user_id:04d}X"

    driver = await create_driver(
        db=db,
        user_id=user_id,
        license_number=license_num,
        vehicle_type="sedan",
        vehicle_number=vehicle_num,
        vehicle_model="Standard Fleet Sedan",
    )
    return driver


async def get_driver(
    db: AsyncSession,
    driver_id: int
):
    driver = await get_driver_by_id(
        db,
        driver_id
    )

    if not driver:
        raise DriverNotFoundError()

    return driver


async def get_my_driver_profile(
    db: AsyncSession,
    user_id: int
):
    return await get_or_create_driver(db, user_id)


async def get_available_driver_list(
    db: AsyncSession
):
    return await get_available_drivers(db)


async def change_driver_status(
    db: AsyncSession,
    user_id: int,
    is_online: bool,
    is_available: bool
):
    driver = await get_or_create_driver(
        db,
        user_id
    )

    # Driver cannot be available while offline
    if not is_online and is_available:
        raise DriverUnavailableError(
            "Driver cannot be available while offline"
        )

    # If driver goes offline,
    # automatically make driver unavailable
    if not is_online:
        is_available = False

    return await update_driver_status(
        db=db,
        driver=driver,
        is_online=is_online,
        is_available=is_available
    )


async def set_driver_availability(
    db: AsyncSession,
    user_id: int,
    is_available: bool
):
    driver = await get_or_create_driver(
        db,
        user_id
    )

    if not driver.is_online and is_available:
        raise DriverUnavailableError(
            "Driver must be online to become available"
        )

    return await update_driver_availability(
        db=db,
        driver=driver,
        is_available=is_available
    )


async def change_driver_location(
    db: AsyncSession,
    user_id: int,
    latitude: float,
    longitude: float
):
    driver = await get_or_create_driver(db, user_id)

    return await update_driver_location(
        db=db,
        driver=driver,
        latitude=latitude,
        longitude=longitude
    )


async def update_driver_profile_service(
    db: AsyncSession,
    user_id: int,
    vehicle_type: str | None = None,
    vehicle_number: str | None = None,
    vehicle_model: str | None = None,
    license_number: str | None = None,
):
    """Update driver profile with uniqueness checks."""
    driver = await get_or_create_driver(db, user_id)

    if license_number is not None and license_number != driver.license_number:
        existing = await get_driver_by_license(db, license_number)
        if existing:
            raise DuplicateResourceError("License number is already registered")

    if vehicle_number is not None and vehicle_number != driver.vehicle_number:
        existing = await get_driver_by_vehicle_number(db, vehicle_number)
        if existing:
            raise DuplicateResourceError("Vehicle number is already registered")

    return await update_driver_profile(
        db=db,
        driver=driver,
        vehicle_type=vehicle_type,
        vehicle_number=vehicle_number,
        vehicle_model=vehicle_model,
        license_number=license_number,
    )