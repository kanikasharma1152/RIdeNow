from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rejection import RideDriverRejection


async def create_rejection(
    db: AsyncSession,
    ride_id: int,
    driver_id: int,
) -> RideDriverRejection:
    rejection = RideDriverRejection(
        ride_id=ride_id,
        driver_id=driver_id,
    )
    db.add(rejection)
    await db.commit()
    await db.refresh(rejection)
    return rejection


async def get_rejected_driver_ids(
    db: AsyncSession,
    ride_id: int,
) -> list[int]:
    """Return list of driver_ids that have rejected this ride."""
    result = await db.execute(
        select(RideDriverRejection.driver_id).where(
            RideDriverRejection.ride_id == ride_id
        )
    )
    return list(result.scalars().all())


async def has_driver_rejected(
    db: AsyncSession,
    ride_id: int,
    driver_id: int,
) -> bool:
    result = await db.execute(
        select(RideDriverRejection).where(
            RideDriverRejection.ride_id == ride_id,
            RideDriverRejection.driver_id == driver_id,
        )
    )
    return result.scalar_one_or_none() is not None
