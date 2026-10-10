import math
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ride import Ride


async def create_ride(
    db: AsyncSession,
    passenger_id: int,
    pickup_location: str,
    dropoff_location: str,
    distance_km: float,
    pickup_latitude: float | None = None,
    pickup_longitude: float | None = None,
):
    ride = Ride(
        passenger_id=passenger_id,
        pickup_location=pickup_location,
        dropoff_location=dropoff_location,
        distance_km=distance_km,
        pickup_latitude=pickup_latitude,
        pickup_longitude=pickup_longitude,
    )

    db.add(ride)
    await db.commit()
    await db.refresh(ride)

    return ride


async def get_ride_by_id(
    db: AsyncSession,
    ride_id: int,
):
    result = await db.execute(
        select(Ride).where(Ride.id == ride_id)
    )
    return result.scalar_one_or_none()


async def get_ride_by_id_for_update(
    db: AsyncSession,
    ride_id: int,
):
    result = await db.execute(
        select(Ride).where(Ride.id == ride_id).with_for_update()
    )
    return result.scalar_one_or_none()


async def get_rides_by_passenger(
    db: AsyncSession,
    passenger_id: int,
):
    """Legacy: returns all rides without pagination (used by dashboard)."""
    result = await db.execute(
        select(Ride)
        .where(Ride.passenger_id == passenger_id)
        .order_by(Ride.created_at.desc())
    )
    return result.scalars().all()


async def get_rides_by_driver(
    db: AsyncSession,
    driver_id: int,
):
    """Legacy: returns all driver rides without pagination."""
    result = await db.execute(
        select(Ride)
        .where(Ride.driver_id == driver_id)
        .order_by(Ride.created_at.desc())
    )
    return result.scalars().all()


async def get_rides_by_passenger_paginated(
    db: AsyncSession,
    passenger_id: int,
    page: int = 1,
    page_size: int = 10,
    status: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    sort: str = "newest",
):
    """Paginated, filterable ride history for passengers."""
    query = select(Ride).where(Ride.passenger_id == passenger_id)

    if status:
        query = query.where(Ride.status == status.upper())
    if start_date:
        query = query.where(Ride.created_at >= start_date)
    if end_date:
        query = query.where(Ride.created_at <= end_date)

    # Count total matching rows
    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar_one()

    # Fetch paginated rows — sort by created_at direction
    order_col = Ride.created_at.asc() if sort == "oldest" else Ride.created_at.desc()
    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(order_col).offset(offset).limit(page_size)
    )
    items = result.scalars().all()

    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return items, total, total_pages


async def get_rides_by_driver_paginated(
    db: AsyncSession,
    driver_id: int,
    page: int = 1,
    page_size: int = 10,
    status: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    sort: str = "newest",
):
    """Paginated, filterable ride history for drivers."""
    query = select(Ride).where(Ride.driver_id == driver_id)

    if status:
        query = query.where(Ride.status == status.upper())
    if start_date:
        query = query.where(Ride.created_at >= start_date)
    if end_date:
        query = query.where(Ride.created_at <= end_date)

    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar_one()

    order_col = Ride.created_at.asc() if sort == "oldest" else Ride.created_at.desc()
    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(order_col).offset(offset).limit(page_size)
    )
    items = result.scalars().all()

    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return items, total, total_pages


async def get_requested_rides(
    db: AsyncSession,
):
    result = await db.execute(
        select(Ride)
        .where(
            Ride.status == "REQUESTED",
            Ride.driver_id.is_(None),
        )
        .order_by(Ride.created_at.asc())
    )
    return result.scalars().all()


async def get_requested_rides_excluding_drivers(
    db: AsyncSession,
    ride_id: int,
    excluded_driver_ids: list[int],
):
    """Used after rejection: find the specific ride and available drivers (excluding those who rejected it)."""
    result = await db.execute(
        select(Ride).where(Ride.id == ride_id)
    )
    return result.scalar_one_or_none()


async def get_active_ride_for_passenger(
    db: AsyncSession,
    passenger_id: int,
):
    """Return the most recent active ride for a passenger, or None."""
    result = await db.execute(
        select(Ride)
        .where(
            Ride.passenger_id == passenger_id,
            Ride.status.in_(["REQUESTED", "ACCEPTED", "STARTED"]),
        )
        .order_by(Ride.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def assign_driver(
    db: AsyncSession,
    ride: Ride,
    driver_id: int,
):
    ride.driver_id = driver_id
    ride.status = "ACCEPTED"

    await db.commit()
    await db.refresh(ride)

    return ride


async def reset_ride_to_requested(
    db: AsyncSession,
    ride: Ride,
):
    """Reset a ride back to REQUESTED status after driver rejection."""
    ride.driver_id = None
    ride.status = "REQUESTED"

    await db.commit()
    await db.refresh(ride)

    return ride


async def update_ride_status(
    db: AsyncSession,
    ride: Ride,
    status: str,
    fare=None,
):
    ride.status = status

    if status == "STARTED":
        ride.started_at = datetime.utcnow()
    elif status == "COMPLETED":
        ride.completed_at = datetime.utcnow()
        if fare is not None:
            ride.fare = fare

    await db.commit()
    await db.refresh(ride)

    return ride


async def cancel_ride(
    db: AsyncSession,
    ride: Ride,
):
    ride.status = "CANCELLED"

    await db.commit()
    await db.refresh(ride)

    return ride


async def get_driver_earnings_stats(
    db: AsyncSession,
    driver_id: int,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
):
    """
    Return aggregated earnings stats for a driver.
    Uses SQL-level aggregation — no in-memory calculation.
    """
    from decimal import Decimal
    from datetime import timezone
    import datetime as dt

    now = datetime.utcnow()

    today_start = datetime(now.year, now.month, now.day)
    week_start = today_start - dt.timedelta(days=now.weekday())
    month_start = datetime(now.year, now.month, 1)

    base_query = select(Ride).where(
        Ride.driver_id == driver_id,
        Ride.status == "COMPLETED",
        Ride.fare.is_not(None),
    )

    if start_date:
        base_query = base_query.where(Ride.created_at >= start_date)
    if end_date:
        base_query = base_query.where(Ride.created_at <= end_date)

    # Total completed rides and total earnings
    subq = base_query.subquery()
    agg = await db.execute(
        select(
            func.count(subq.c.id).label("total_rides"),
            func.coalesce(func.sum(subq.c.fare), 0).label("total_earnings"),
            func.coalesce(func.avg(subq.c.fare), 0).label("average_fare"),
        ).select_from(subq)
    )
    row = agg.one()

    # Today
    today_agg = await db.execute(
        select(func.coalesce(func.sum(Ride.fare), 0)).where(
            Ride.driver_id == driver_id,
            Ride.status == "COMPLETED",
            Ride.fare.is_not(None),
            Ride.completed_at >= today_start,
        )
    )
    today_earnings = today_agg.scalar_one()

    # This week
    week_agg = await db.execute(
        select(func.coalesce(func.sum(Ride.fare), 0)).where(
            Ride.driver_id == driver_id,
            Ride.status == "COMPLETED",
            Ride.fare.is_not(None),
            Ride.completed_at >= week_start,
        )
    )
    week_earnings = week_agg.scalar_one()

    # This month
    month_agg = await db.execute(
        select(func.coalesce(func.sum(Ride.fare), 0)).where(
            Ride.driver_id == driver_id,
            Ride.status == "COMPLETED",
            Ride.fare.is_not(None),
            Ride.completed_at >= month_start,
        )
    )
    month_earnings = month_agg.scalar_one()

    # Cancelled rides count
    cancelled_agg = await db.execute(
        select(func.count(Ride.id)).where(
            Ride.driver_id == driver_id,
            Ride.status == "CANCELLED",
        )
    )
    cancelled_rides = cancelled_agg.scalar_one()

    return {
        "total_rides": row.total_rides,
        "cancelled_rides": cancelled_rides,
        "total_earnings": Decimal(str(row.total_earnings)),
        "today_earnings": Decimal(str(today_earnings)),
        "week_earnings": Decimal(str(week_earnings)),
        "month_earnings": Decimal(str(month_earnings)),
        "average_fare": Decimal(str(row.average_fare)).quantize(Decimal("0.01")),
    }