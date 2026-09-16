from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.ratings import (
    create_rating,
    get_rating_by_ride,
    get_driver_ratings
)
from app.repositories.ride import get_ride_by_id


async def submit_rating(
    db: AsyncSession,
    passenger_id: int,
    ride_id: int,
    rating: int,
    comment: str | None = None,
    feedback: str | None = None,
):
    final_comment = comment if comment is not None else feedback
    ride = await get_ride_by_id(db, ride_id)

    if not ride:
        raise ValueError("Ride not found")

    if ride.passenger_id != passenger_id:
        raise ValueError("You can only rate your own ride")

    if ride.status != "COMPLETED":
        raise ValueError("Only completed rides can be rated")

    if not ride.driver_id:
        raise ValueError("Ride has no assigned driver")

    existing_rating = await get_rating_by_ride(db, ride_id)

    if existing_rating:
        raise ValueError("This ride has already been rated")

    return await create_rating(
        db=db,
        ride_id=ride_id,
        passenger_id=passenger_id,
        driver_id=ride.driver_id,
        rating=rating,
        comment=final_comment
    )


async def get_driver_rating_list(
    db: AsyncSession,
    driver_id: int
):
    return await get_driver_ratings(db, driver_id)