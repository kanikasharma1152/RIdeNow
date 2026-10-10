"""
ETA Predictor
=============
Predicts estimated time of arrival (ETA) for a driver reaching a passenger
and for completing the trip.

Method:
  1. OSRM route gives raw distance (km) + duration (seconds) baseline.
  2. A time-of-day congestion multiplier adjusts for typical traffic patterns.
  3. A historical correction factor (from DB) tightens predictions over time.

All outputs carry:
  - `method`: "rule_based" | "osrm_corrected" | "ml_predicted"
  - `confidence`: "low" | "medium" | "high"
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# ─── Congestion Multipliers ───────────────────────────────────────────────────
# Maps hour-of-day → average speed reduction factor.
# 1.0 = free-flow speed. 2.0 = half speed (double travel time).

CONGESTION_FACTOR: dict[int, float] = {
    0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0,
    6: 1.2, 7: 1.6, 8: 2.0, 9: 1.8, 10: 1.3, 11: 1.1,
    12: 1.3, 13: 1.2, 14: 1.1, 15: 1.2, 16: 1.5, 17: 2.0,
    18: 2.2, 19: 1.9, 20: 1.5, 21: 1.3, 22: 1.1, 23: 1.0,
}

# Average urban driving speed in km/h when no OSRM data
FALLBACK_SPEED_KMH = 30.0


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Returns great-circle distance in km."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _congestion_at(dt: datetime) -> float:
    return CONGESTION_FACTOR.get(dt.hour, 1.0)


# ─── OSRM Helper ─────────────────────────────────────────────────────────────

async def _osrm_route(lat1: float, lon1: float, lat2: float, lon2: float) -> dict | None:
    """
    Call OSRM routing engine for distance + raw duration.
    Returns {"distance_km": float, "duration_seconds": float} or None on error.
    """
    try:
        from app.services.google_map import calculate_route_distance
        dist_km = await calculate_route_distance(
            f"{lat1},{lon1}", f"{lat2},{lon2}"
        )
        if dist_km and dist_km > 0:
            # OSRM duration estimate: OSRM defaults to ~60 km/h on open roads
            raw_duration_s = (dist_km / 60.0) * 3600
            return {"distance_km": dist_km, "duration_seconds": raw_duration_s}
    except Exception:
        pass
    return None


# ─── Historical Correction ────────────────────────────────────────────────────

async def _get_historical_correction(
    db: "AsyncSession",
    distance_km: float,
    hour: int,
) -> float:
    """
    Look up how historical actual trip times compare to our estimate.
    Returns a multiplier (1.0 = no correction needed).
    Only activates when ≥10 historical rides are available.
    """
    try:
        from sqlalchemy import text

        result = await db.execute(
            text("""
                SELECT
                    AVG(
                        EXTRACT(EPOCH FROM (completed_at - started_at))
                    ) AS avg_actual_seconds,
                    COUNT(*) AS sample_count
                FROM rides
                WHERE
                    status = 'COMPLETED'
                    AND started_at IS NOT NULL
                    AND completed_at IS NOT NULL
                    AND distance_km BETWEEN :dist_min AND :dist_max
                    AND EXTRACT(HOUR FROM started_at) = :hour
                    AND created_at >= NOW() - INTERVAL '30 days'
            """),
            {
                "dist_min": max(0, distance_km - 2.0),
                "dist_max": distance_km + 2.0,
                "hour": hour,
            },
        )
        row = result.fetchone()
        if row and row.sample_count and int(row.sample_count) >= 10:
            avg_actual = float(row.avg_actual_seconds)
            # Naive estimate for comparison: distance / 30km/h
            naive_estimate = (distance_km / FALLBACK_SPEED_KMH) * 3600
            if naive_estimate > 0:
                return avg_actual / naive_estimate
    except Exception:
        pass
    return 1.0


# ─── Public API ───────────────────────────────────────────────────────────────

async def predict_eta(
    pickup_lat: float,
    pickup_lon: float,
    dropoff_lat: float,
    dropoff_lon: float,
    driver_lat: float | None = None,
    driver_lon: float | None = None,
    db: "AsyncSession | None" = None,
    at: datetime | None = None,
) -> dict:
    """
    Predict ETA for a complete trip:
      - driver_pickup_eta_minutes: time for driver to reach passenger
      - trip_eta_minutes:          time for trip from pickup to dropoff
      - total_eta_minutes:         end-to-end estimate

    Returns:
        {
            "driver_pickup_eta_minutes": float,
            "trip_eta_minutes": float,
            "total_eta_minutes": float,
            "trip_distance_km": float,
            "driver_distance_km": float | None,
            "congestion_factor": float,
            "historical_correction": float,
            "method": str,
            "confidence": str,
        }
    """
    now = at or datetime.now(timezone.utc)
    congestion = _congestion_at(now)
    method = "rule_based"
    confidence = "low"

    # ── Trip distance (pickup → dropoff) ─────────────────────────────────────
    osrm_trip = await _osrm_route(pickup_lat, pickup_lon, dropoff_lat, dropoff_lon)

    if osrm_trip:
        trip_dist_km = osrm_trip["distance_km"]
        # Apply congestion to OSRM's free-flow duration
        raw_trip_secs = osrm_trip["duration_seconds"] * congestion
        method = "osrm_corrected"
        confidence = "medium"
    else:
        trip_dist_km = _haversine(pickup_lat, pickup_lon, dropoff_lat, dropoff_lon)
        raw_trip_secs = (trip_dist_km / FALLBACK_SPEED_KMH) * 3600 * congestion

    # ── Historical correction ─────────────────────────────────────────────────
    hist_correction = 1.0
    if db is not None:
        hist_correction = await _get_historical_correction(db, trip_dist_km, now.hour)
        if hist_correction != 1.0:
            method = "osrm_corrected"
            confidence = "high"

    trip_eta_secs = raw_trip_secs * hist_correction
    trip_eta_min = trip_eta_secs / 60.0

    # ── Driver pickup ETA ─────────────────────────────────────────────────────
    driver_dist_km: float | None = None
    driver_eta_min = 5.0  # default fallback

    if driver_lat is not None and driver_lon is not None:
        osrm_pickup = await _osrm_route(driver_lat, driver_lon, pickup_lat, pickup_lon)
        if osrm_pickup:
            driver_dist_km = osrm_pickup["distance_km"]
            driver_eta_min = (osrm_pickup["duration_seconds"] * congestion) / 60.0
        else:
            driver_dist_km = _haversine(driver_lat, driver_lon, pickup_lat, pickup_lon)
            driver_eta_min = (driver_dist_km / FALLBACK_SPEED_KMH) * 60.0 * congestion

    return {
        "driver_pickup_eta_minutes": round(driver_eta_min, 1),
        "trip_eta_minutes": round(trip_eta_min, 1),
        "total_eta_minutes": round(driver_eta_min + trip_eta_min, 1),
        "trip_distance_km": round(trip_dist_km, 2),
        "driver_distance_km": round(driver_dist_km, 2) if driver_dist_km is not None else None,
        "congestion_factor": round(congestion, 2),
        "historical_correction": round(hist_correction, 3),
        "method": method,
        "confidence": confidence,
    }
