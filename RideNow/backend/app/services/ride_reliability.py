"""
Ride Reliability Engine — Phase 14
====================================
Detects stale/stuck ride states and computes reliability metrics.

Principles:
- Does NOT automatically cancel rides (only detects and reports)
- Configurable thresholds
- Provides data for admin intelligence
- All data from real DB queries
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.models.ride import Ride

logger = logging.getLogger(__name__)

# ── Configurable Stale Thresholds ────────────────────────────────────────────
STALE_REQUESTED_MINUTES = 10     # REQUESTED with no driver for 10+ min
STALE_ACCEPTED_MINUTES = 60      # ACCEPTED but not started for 60+ min
STALE_STARTED_MINUTES = 300      # STARTED but not completed for 5+ hours

ACTIVE_STATUSES = ("REQUESTED", "ACCEPTED", "STARTED")
TERMINAL_STATUSES = ("COMPLETED", "CANCELLED")


async def get_stale_rides(db: AsyncSession) -> List[Dict[str, Any]]:
    """
    Returns rides that appear stuck in an unexpected state.
    Does NOT cancel or modify them — only detects and reports.
    """
    now = datetime.now(timezone.utc)
    stale = []

    try:
        stmt = select(Ride).where(Ride.status.in_(ACTIVE_STATUSES))
        result = await db.execute(stmt)
        active_rides = result.scalars().all()

        for ride in active_rides:
            threshold_minutes = None
            if ride.status == "REQUESTED":
                threshold_minutes = STALE_REQUESTED_MINUTES
            elif ride.status == "ACCEPTED":
                threshold_minutes = STALE_ACCEPTED_MINUTES
            elif ride.status == "STARTED":
                threshold_minutes = STALE_STARTED_MINUTES

            if threshold_minutes is None:
                continue

            # Use completed_at / started_at / created_at for last state change time
            last_update = getattr(ride, "completed_at", None) or getattr(ride, "started_at", None) or ride.created_at
            if last_update is None:
                continue

            # Normalize to UTC-aware
            if last_update.tzinfo is None:
                last_update = last_update.replace(tzinfo=timezone.utc)

            age_minutes = (now - last_update).total_seconds() / 60

            if age_minutes >= threshold_minutes:
                stale.append({
                    "ride_id": ride.id,
                    "status": ride.status,
                    "stuck_for_minutes": round(age_minutes, 1),
                    "threshold_minutes": threshold_minutes,
                    "passenger_id": ride.passenger_id,
                    "driver_id": ride.driver_id,
                    "pickup_location": ride.pickup_location,
                    "last_updated": last_update.isoformat(),
                })
    except Exception as exc:
        logger.error(f"[Reliability] get_stale_rides failed: {exc}")

    return stale


async def get_reliability_metrics(db: AsyncSession) -> Dict[str, Any]:
    """
    Returns real-time ride reliability metrics for the admin intelligence panel.
    All values calculated from real DB data.
    """
    now_utc = datetime.now(timezone.utc)
    # Database columns are TIMESTAMP WITHOUT TIME ZONE; asyncpg requires naive UTC datetimes
    window_24h = (now_utc - timedelta(hours=24)).replace(tzinfo=None)

    try:
        # Rides by status
        status_stmt = select(Ride.status, func.count(Ride.id)).group_by(Ride.status)
        status_result = await db.execute(status_stmt)
        rides_by_status = {row[0]: row[1] for row in status_result.fetchall()}

        # Active ride count
        active_count = sum(
            rides_by_status.get(s, 0) for s in ACTIVE_STATUSES
        )

        # Stale rides
        stale_rides = await get_stale_rides(db)
        stale_count = len(stale_rides)

        # Cancellations in last 24h
        cancel_stmt = select(func.count(Ride.id)).where(
            and_(
                Ride.status == "CANCELLED",
                Ride.created_at >= window_24h,
            )
        )
        cancel_result = await db.execute(cancel_stmt)
        recent_cancellations = cancel_result.scalar() or 0

        # Rejections in last 24h (from rejection table if available)
        recent_rejections = 0
        try:
            from app.models.rejection import RideRejection
            rej_stmt = select(func.count(RideRejection.id)).where(
                RideRejection.created_at >= window_24h
            )
            rej_result = await db.execute(rej_stmt)
            recent_rejections = rej_result.scalar() or 0
        except Exception:
            pass  # rejection table may not exist in test DB

        # Driver rejection rate (rejections / total accepted in window)
        completed_24h = 0
        try:
            comp_stmt = select(func.count(Ride.id)).where(
                and_(
                    Ride.status == "COMPLETED",
                    Ride.created_at >= window_24h,
                )
            )
            comp_result = await db.execute(comp_stmt)
            completed_24h = comp_result.scalar() or 0
        except Exception:
            pass

        total_attempted = completed_24h + recent_cancellations + recent_rejections
        rejection_rate = (
            round(recent_rejections / total_attempted * 100, 1)
            if total_attempted > 0 else 0.0
        )

        return {
            "active_rides_count": active_count,
            "stale_rides_count": stale_count,
            "stale_rides": stale_rides[:20],  # cap at 20 for response size
            "rides_by_status": rides_by_status,
            "recent_cancellations_24h": recent_cancellations,
            "recent_rejections_24h": recent_rejections,
            "completed_rides_24h": completed_24h,
            "driver_rejection_rate_pct": rejection_rate,
            "stale_thresholds_minutes": {
                "REQUESTED": STALE_REQUESTED_MINUTES,
                "ACCEPTED": STALE_ACCEPTED_MINUTES,
                "STARTED": STALE_STARTED_MINUTES,
            },
        }

    except Exception as exc:
        logger.error(f"[Reliability] get_reliability_metrics failed: {exc}")
        return {
            "active_rides_count": 0,
            "stale_rides_count": 0,
            "stale_rides": [],
            "rides_by_status": {},
            "error": str(exc),
        }
