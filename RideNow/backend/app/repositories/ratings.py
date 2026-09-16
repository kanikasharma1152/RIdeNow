from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ratings import Rating


async def create_rating(
    db: AsyncSession,
    ride_id: int,
    passenger_id: int,
    driver_id: int,
    rating: int,
    comment: str | None = None
):
    new_rating = Rating(
        ride_id=ride_id,
        passenger_id=passenger_id,
        driver_id=driver_id,
        rating=rating,
        comment=comment
    )

    db.add(new_rating)
    await db.commit()
    await db.refresh(new_rating)

    return new_rating


async def get_rating_by_ride(
    db: AsyncSession,
    ride_id: int
):
    result = await db.execute(
        select(Rating).where(Rating.ride_id == ride_id)
    )

    return result.scalar_one_or_none()


async def get_driver_ratings(
    db: AsyncSession,
    driver_id: int
):
    result = await db.execute(
        select(Rating)
        .where(Rating.driver_id == driver_id)
        .order_by(Rating.created_at.desc())
    )

    return result.scalars().all()