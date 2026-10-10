"""
RideNow Admin Analytics Repository — Phase 7
============================================
Executes optimized SQL aggregation queries for admin dashboard metrics.
All operations are read-only aggregations.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List
from sqlalchemy import func, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ride import Ride
from app.models.user import User
from app.models.driver import Driver


async def get_overview_metrics(db: AsyncSession) -> Dict[str, Any]:
    """Total counts of users, drivers, rides, and gross platform volume."""
    total_users_q = await db.execute(select(func.count(User.id)))
    total_users = total_users_q.scalar() or 0

    total_drivers_q = await db.execute(select(func.count(Driver.id)))
    total_drivers = total_drivers_q.scalar() or 0

    active_drivers_q = await db.execute(select(func.count(Driver.id)).where(Driver.is_online == True))
    active_drivers = active_drivers_q.scalar() or 0

    rides_agg_q = await db.execute(
        select(
            func.count(Ride.id),
            func.coalesce(func.sum(Ride.fare), 0),
            func.coalesce(func.avg(Ride.distance_km), 0),
        ).where(Ride.status == "COMPLETED")
    )
    completed_rides, total_gmv, avg_dist = rides_agg_q.one()

    total_rides_q = await db.execute(select(func.count(Ride.id)))
    total_rides = total_rides_q.scalar() or 0

    cancelled_rides_q = await db.execute(select(func.count(Ride.id)).where(Ride.status == "CANCELLED"))
    cancelled_rides = cancelled_rides_q.scalar() or 0

    completion_rate = (completed_rides / total_rides * 100) if total_rides > 0 else 0.0

    return {
        "total_users": total_users,
        "total_drivers": total_drivers,
        "active_drivers_online": active_drivers,
        "total_rides": total_rides,
        "completed_rides": completed_rides,
        "cancelled_rides": cancelled_rides,
        "completion_rate_pct": round(completion_rate, 1),
        "total_revenue_inr": float(total_gmv),
        "average_distance_km": round(float(avg_dist), 2),
    }


async def get_recent_rides_trend(db: AsyncSession, days: int = 7) -> List[Dict[str, Any]]:
    """Returns ride volume and revenue grouped by day for the last N days."""
    since_date = datetime.utcnow() - timedelta(days=days)
    stmt = (
        select(
            func.date(Ride.created_at).label("day"),
            func.count(Ride.id).label("ride_count"),
            func.coalesce(func.sum(Ride.fare), 0).label("daily_fare"),
        )
        .where(Ride.created_at >= since_date)
        .group_by(func.date(Ride.created_at))
        .order_by(func.date(Ride.created_at))
    )
    result = await db.execute(stmt)
    return [
        {"date": str(row.day), "rides": row.ride_count, "revenue": float(row.daily_fare)}
        for row in result.all()
    ]


async def get_top_pickup_hotspots(db: AsyncSession, limit: int = 5) -> List[Dict[str, Any]]:
    """Returns most frequent pickup locations."""
    stmt = (
        select(
            Ride.pickup_location,
            func.count(Ride.id).label("ride_count"),
        )
        .group_by(Ride.pickup_location)
        .order_by(desc("ride_count"))
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [{"location": row.pickup_location, "count": row.ride_count} for row in result.all()]


async def get_admin_fleet_drivers(db: AsyncSession, limit: int = 20) -> List[Dict[str, Any]]:
    """Returns driver fleet list with user names, vehicle details, online status and current location."""
    stmt = (
        select(Driver, User.name, User.phone)
        .join(User, Driver.user_id == User.id)
        .order_by(desc(Driver.is_online), desc(Driver.id))
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()
    drivers = []
    for driver, name, phone in rows:
        drivers.append({
            "id": driver.id,
            "user_id": driver.user_id,
            "name": name or f"Captain #{driver.id}",
            "phone": phone,
            "vehicle_type": driver.vehicle_type,
            "vehicle_number": driver.vehicle_number,
            "vehicle_model": driver.vehicle_model,
            "is_online": bool(driver.is_online),
            "is_available": bool(driver.is_available),

            "latitude": driver.latitude,
            "longitude": driver.longitude,
            "location_updated_at": driver.location_updated_at.isoformat() if driver.location_updated_at else None,
        })
    return drivers
