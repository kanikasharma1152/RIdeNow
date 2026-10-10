"""
Demand Predictor
================
Predicts ride demand by geographic zone and time window.

Method: rule-based heuristic (time-of-day + day-of-week + DB historical counts).
Architecture: designed to drop in a scikit-learn or LightGBM model once enough
              historical data is available (>30 days, >500 completed rides).

All predictions carry a `method` field: "rule_based" | "ml_predicted".
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# ─── Zone Grid ────────────────────────────────────────────────────────────────
# Approximate 0.5° × 0.5° grid cells used as "zones".
# Each zone is keyed by (lat_bin, lon_bin) rounded to 1 decimal place.

GRID_RESOLUTION = 0.05  # ~5 km squares


def _zone_key(lat: float, lon: float) -> tuple[float, float]:
    """Snap lat/lon to nearest grid cell center."""
    return (
        round(round(lat / GRID_RESOLUTION) * GRID_RESOLUTION, 3),
        round(round(lon / GRID_RESOLUTION) * GRID_RESOLUTION, 3),
    )


# ─── Time-of-Day Multipliers ──────────────────────────────────────────────────
# Based on typical urban mobility patterns.
# hour → demand multiplier (1.0 = baseline)

HOUR_MULTIPLIER: dict[int, float] = {
    0: 0.3, 1: 0.2, 2: 0.2, 3: 0.1, 4: 0.2, 5: 0.4,
    6: 0.8, 7: 1.6, 8: 2.0, 9: 1.8, 10: 1.2, 11: 1.0,
    12: 1.3, 13: 1.1, 14: 0.9, 15: 1.0, 16: 1.2, 17: 1.8,
    18: 2.2, 19: 2.0, 20: 1.6, 21: 1.4, 22: 1.0, 23: 0.6,
}

# Day-of-week multiplier: 0=Monday … 6=Sunday
DAY_MULTIPLIER: dict[int, float] = {
    0: 1.0,  # Monday
    1: 1.0,  # Tuesday
    2: 1.0,  # Wednesday
    3: 1.1,  # Thursday
    4: 1.3,  # Friday
    5: 1.5,  # Saturday
    6: 1.2,  # Sunday
}


def _time_demand_factor(dt: datetime) -> float:
    """Compute demand multiplier for a given datetime."""
    hour_mult = HOUR_MULTIPLIER.get(dt.hour, 1.0)
    day_mult = DAY_MULTIPLIER.get(dt.weekday(), 1.0)
    return hour_mult * day_mult


# ─── Demand Level Labels ──────────────────────────────────────────────────────

def _demand_label(score: float) -> str:
    if score >= 1.8:
        return "HIGH"
    if score >= 1.0:
        return "MEDIUM"
    return "LOW"


# ─── Public API ───────────────────────────────────────────────────────────────

async def predict_zone_demand(
    lat: float,
    lon: float,
    db: "AsyncSession | None" = None,
    at: datetime | None = None,
) -> dict:
    """
    Predict demand for a geographic zone at a given time.

    Returns:
        {
            "zone": {"lat": float, "lon": float},
            "demand_level": "LOW" | "MEDIUM" | "HIGH",
            "demand_score": float,   # 0.0–3.0+
            "hour_factor": float,
            "day_factor": float,
            "historical_ride_count": int | None,
            "method": "rule_based",
        }
    """
    now = at or datetime.now(timezone.utc)
    zone = _zone_key(lat, lon)

    # Base time factor
    hour_factor = HOUR_MULTIPLIER.get(now.hour, 1.0)
    day_factor = DAY_MULTIPLIER.get(now.weekday(), 1.0)
    time_factor = hour_factor * day_factor

    # Historical DB lookup (optional — enriches score if DB is available)
    historical_count: int | None = None
    db_factor = 1.0

    if db is not None:
        try:
            historical_count = await _query_historical_count(db, zone, now)
            if historical_count is not None and historical_count > 0:
                # Normalize: assume 20 rides/cell/hour = "high demand"
                db_factor = min(historical_count / 20.0, 2.0)
        except Exception:
            pass

    # Combined score
    if historical_count is not None:
        # Blend 60% time-based, 40% historical
        demand_score = time_factor * 0.6 + db_factor * 0.4 * 2.0
    else:
        demand_score = time_factor

    return {
        "zone": {"lat": zone[0], "lon": zone[1]},
        "demand_level": _demand_label(demand_score),
        "demand_score": round(demand_score, 3),
        "hour_factor": hour_factor,
        "day_factor": day_factor,
        "historical_ride_count": historical_count,
        "method": "rule_based",
    }


from app.core.redis import cache_get, cache_set

DEMAND_HOTSPOTS_CACHE_TTL = 180  # seconds


async def get_demand_hotspots(
    db: "AsyncSession",
    limit: int = 5,
    at: datetime | None = None,
    use_cache: bool = True,
) -> list[dict]:
    """
    Return top demand hotspots from historical ride pickup data.

    Aggregates past 7-day ride pickups by grid zone, ranks by count,
    and enriches with current time factor. Cached in Redis for 180s.
    """
    cache_key = f"ml:hotspots:{limit}"
    if use_cache and at is None:
        try:
            cached = await cache_get(cache_key)
            if cached and isinstance(cached, list):
                return cached
        except Exception:
            pass

    now = at or datetime.now(timezone.utc)
    time_factor = _time_demand_factor(now)

    hotspots: list[dict] = []

    try:
        from sqlalchemy import text

        rows = await db.execute(
            text("""
                SELECT
                    ROUND(CAST(pickup_latitude AS NUMERIC), 1) AS lat_bin,
                    ROUND(CAST(pickup_longitude AS NUMERIC), 1) AS lon_bin,
                    COUNT(*) AS ride_count
                FROM rides
                WHERE
                    pickup_latitude IS NOT NULL
                    AND pickup_longitude IS NOT NULL
                    AND created_at >= NOW() - INTERVAL '7 days'
                    AND status IN ('COMPLETED', 'STARTED')
                GROUP BY lat_bin, lon_bin
                ORDER BY ride_count DESC
                LIMIT :limit
            """),
            {"limit": limit},
        )

        for row in rows:
            lat_bin = float(row.lat_bin) if row.lat_bin is not None else 0.0
            lon_bin = float(row.lon_bin) if row.lon_bin is not None else 0.0
            count = int(row.ride_count)
            score = min(count / 20.0, 2.0) * time_factor

            hotspots.append({
                "zone": {"lat": lat_bin, "lon": lon_bin},
                "historical_rides_7d": count,
                "current_demand_score": round(score, 3),
                "demand_level": _demand_label(score),
                "time_factor": round(time_factor, 3),
                "method": "rule_based",
            })

        if use_cache and at is None and hotspots:
            try:
                await cache_set(cache_key, hotspots, ttl=DEMAND_HOTSPOTS_CACHE_TTL)
            except Exception:
                pass

    except Exception:
        # Fallback: no data available yet
        pass

    return hotspots


async def _query_historical_count(
    db: "AsyncSession",
    zone: tuple[float, float],
    at: datetime,
) -> int | None:
    """
    Count rides in the same zone cell and same hour-of-day over the past 30 days.
    Returns None if DB query fails (no crash).
    """
    try:
        from sqlalchemy import text

        lat_min = zone[0] - GRID_RESOLUTION / 2
        lat_max = zone[0] + GRID_RESOLUTION / 2
        lon_min = zone[1] - GRID_RESOLUTION / 2
        lon_max = zone[1] + GRID_RESOLUTION / 2

        result = await db.execute(
            text("""
                SELECT COUNT(*) FROM rides
                WHERE
                    pickup_latitude BETWEEN :lat_min AND :lat_max
                    AND pickup_longitude BETWEEN :lon_min AND :lon_max
                    AND EXTRACT(HOUR FROM created_at) = :hour
                    AND created_at >= NOW() - INTERVAL '30 days'
                    AND status IN ('COMPLETED', 'STARTED')
            """),
            {
                "lat_min": lat_min,
                "lat_max": lat_max,
                "lon_min": lon_min,
                "lon_max": lon_max,
                "hour": at.hour,
            },
        )
        row = result.scalar()
        return int(row) if row is not None else 0
    except Exception:
        return None
