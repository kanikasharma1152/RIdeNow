"""
Smart Driver Matching Engine
============================
Multi-signal driver scoring to replace nearest-driver-only selection.

Scoring formula (weighted sum, higher = better match):
  distance_score  (40%) — closer driver scores higher
  eta_score       (30%) — lower ETA (with congestion) scores higher
  rating_score    (20%) — higher avg rating scores higher
  acceptance_score(10%) — higher acceptance rate scores higher

Each signal is normalized 0.0–1.0 before weighting.
The engine returns a ranked list of (driver, score, breakdown).

All outputs carry `method: "rule_based"` until an ML model replaces this.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# ─── Weights ──────────────────────────────────────────────────────────────────

WEIGHT_DISTANCE = 0.40
WEIGHT_ETA = 0.30
WEIGHT_RATING = 0.20
WEIGHT_ACCEPTANCE = 0.10

# Maximum plausible distance to consider a driver (km)
MAX_DRIVER_DISTANCE_KM = 15.0

# Default rating assumed when driver has no ratings yet
DEFAULT_RATING = 4.0

# Default acceptance rate assumed when driver has no history
DEFAULT_ACCEPTANCE_RATE = 0.85


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class DriverCandidate:
    """Lightweight driver record for scoring (no DB model dependency)."""
    driver_id: int
    user_id: int
    latitude: float
    longitude: float
    avg_rating: float = DEFAULT_RATING
    acceptance_rate: float = DEFAULT_ACCEPTANCE_RATE
    total_rides: int = 0
    # Raw distance from pickup (populated by engine)
    distance_km: float = 0.0
    # ETA minutes to reach pickup (populated by engine)
    eta_minutes: float = 0.0


@dataclass
class MatchResult:
    """Scoring result for one driver candidate."""
    driver_id: int
    user_id: int
    total_score: float
    distance_km: float
    eta_minutes: float
    breakdown: dict = field(default_factory=dict)
    method: str = "rule_based"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _normalize_inverse(value: float, max_value: float) -> float:
    """Lower value → higher score. Returns 0–1."""
    if max_value <= 0:
        return 1.0
    return max(0.0, 1.0 - (value / max_value))


def _normalize(value: float, min_val: float, max_val: float) -> float:
    """Higher value → higher score. Returns 0–1."""
    if max_val <= min_val:
        return 1.0
    return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))


# ─── DB Enrichment ────────────────────────────────────────────────────────────

async def _enrich_with_db_stats(
    db: "AsyncSession",
    candidates: list[DriverCandidate],
) -> list[DriverCandidate]:
    """
    Fetch avg rating and acceptance rate for each driver from DB.
    Falls back to defaults on error.
    """
    if not db or not candidates:
        return candidates

    driver_ids = [c.driver_id for c in candidates]

    try:
        from sqlalchemy import text

        # Avg ratings
        rating_result = await db.execute(
            text("""
                SELECT driver_id, AVG(rating) AS avg_rating, COUNT(*) AS cnt
                FROM ratings
                WHERE driver_id = ANY(:ids)
                GROUP BY driver_id
            """),
            {"ids": driver_ids},
        )
        ratings_map = {
            int(row.driver_id): (float(row.avg_rating), int(row.cnt))
            for row in rating_result
        }

        # Acceptance rate: rides offered vs rides accepted (driver_id)
        # Proxy: accepted rides / total rides assigned to driver
        acceptance_result = await db.execute(
            text("""
                SELECT
                    driver_id,
                    COUNT(*) AS total_assigned,
                    SUM(CASE WHEN status NOT IN ('REQUESTED') THEN 1 ELSE 0 END) AS accepted
                FROM rides
                WHERE
                    driver_id = ANY(:ids)
                    AND created_at >= NOW() - INTERVAL '30 days'
                GROUP BY driver_id
            """),
            {"ids": driver_ids},
        )
        acceptance_map = {
            int(row.driver_id): (
                float(row.accepted) / float(row.total_assigned)
                if row.total_assigned and float(row.total_assigned) > 0
                else DEFAULT_ACCEPTANCE_RATE
            )
            for row in acceptance_result
        }

        for c in candidates:
            if c.driver_id in ratings_map:
                avg_r, cnt = ratings_map[c.driver_id]
                c.avg_rating = avg_r
                c.total_rides = cnt
            if c.driver_id in acceptance_map:
                c.acceptance_rate = acceptance_map[c.driver_id]

    except Exception:
        pass

    return candidates


# ─── Scoring ─────────────────────────────────────────────────────────────────

def _score_candidates(
    candidates: list[DriverCandidate],
    pickup_lat: float,
    pickup_lon: float,
    congestion_factor: float = 1.0,
) -> list[MatchResult]:
    """
    Score each candidate and return sorted list (best first).
    """
    if not candidates:
        return []

    # Populate distance + ETA for each candidate
    for c in candidates:
        c.distance_km = _haversine_km(c.latitude, c.longitude, pickup_lat, pickup_lon)
        # ETA in minutes: distance / (30 km/h free-flow * congestion correction)
        effective_speed_kmh = 30.0 / congestion_factor
        c.eta_minutes = (c.distance_km / effective_speed_kmh) * 60.0

    # Compute per-signal ranges for normalization
    max_dist = max((c.distance_km for c in candidates), default=MAX_DRIVER_DISTANCE_KM)
    max_eta = max((c.eta_minutes for c in candidates), default=30.0)
    max_dist = max(max_dist, 0.1)
    max_eta = max(max_eta, 0.1)

    results: list[MatchResult] = []

    for c in candidates:
        dist_score = _normalize_inverse(c.distance_km, max_dist)
        eta_score = _normalize_inverse(c.eta_minutes, max_eta)
        rating_score = _normalize(c.avg_rating, 1.0, 5.0)
        acceptance_score = _normalize(c.acceptance_rate, 0.0, 1.0)

        total = (
            dist_score * WEIGHT_DISTANCE
            + eta_score * WEIGHT_ETA
            + rating_score * WEIGHT_RATING
            + acceptance_score * WEIGHT_ACCEPTANCE
        )

        results.append(MatchResult(
            driver_id=c.driver_id,
            user_id=c.user_id,
            total_score=round(total, 4),
            distance_km=round(c.distance_km, 2),
            eta_minutes=round(c.eta_minutes, 1),
            breakdown={
                "distance_score": round(dist_score, 3),
                "eta_score": round(eta_score, 3),
                "rating_score": round(rating_score, 3),
                "acceptance_score": round(acceptance_score, 3),
                "avg_rating": round(c.avg_rating, 2),
                "acceptance_rate": round(c.acceptance_rate, 3),
            },
            method="rule_based",
        ))

    results.sort(key=lambda r: r.total_score, reverse=True)
    return results


# ─── Public API ───────────────────────────────────────────────────────────────

async def rank_drivers(
    drivers: list,  # list of Driver model instances
    pickup_lat: float,
    pickup_lon: float,
    excluded_ids: set[int] | None = None,
    db: "AsyncSession | None" = None,
    congestion_factor: float = 1.0,
) -> list[MatchResult]:
    """
    Rank available driver ORM objects using multi-signal scoring.

    Args:
        drivers: list of Driver ORM instances (from get_available_drivers)
        pickup_lat, pickup_lon: ride pickup coordinates
        excluded_ids: set of driver IDs to skip (rejected drivers etc.)
        db: optional DB session for rating/acceptance enrichment
        congestion_factor: time-of-day multiplier (from demand predictor)

    Returns:
        Sorted list of MatchResult (best match first).
        Empty list if no eligible drivers.
    """
    excluded = excluded_ids or set()

    # Convert ORM → DriverCandidate (no DB coupling in scorer)
    candidates: list[DriverCandidate] = []
    for d in drivers:
        if d.id in excluded:
            continue
        if d.latitude is None or d.longitude is None:
            continue
        if not d.is_online or not d.is_available:
            continue

        dist = _haversine_km(d.latitude, d.longitude, pickup_lat, pickup_lon)
        if dist > MAX_DRIVER_DISTANCE_KM:
            continue  # Too far

        candidates.append(DriverCandidate(
            driver_id=d.id,
            user_id=d.user_id,
            latitude=d.latitude,
            longitude=d.longitude,
        ))

    if not candidates:
        return []

    # Enrich with DB stats if session available
    if db is not None:
        candidates = await _enrich_with_db_stats(db, candidates)

    return _score_candidates(candidates, pickup_lat, pickup_lon, congestion_factor)


async def find_best_driver(
    drivers: list,
    pickup_lat: float,
    pickup_lon: float,
    excluded_ids: set[int] | None = None,
    db: "AsyncSession | None" = None,
    congestion_factor: float = 1.0,
):
    """
    Return the single best-matched driver ORM object,
    or None if no eligible drivers found.
    """
    results = await rank_drivers(
        drivers=drivers,
        pickup_lat=pickup_lat,
        pickup_lon=pickup_lon,
        excluded_ids=excluded_ids,
        db=db,
        congestion_factor=congestion_factor,
    )

    if not results:
        return None

    best = results[0]

    # Find the original Driver ORM object by ID
    for d in drivers:
        if d.id == best.driver_id:
            # Attach score metadata for logging/debugging
            d._match_score = best.total_score
            d._match_breakdown = best.breakdown
            d._eta_minutes = best.eta_minutes
            return d

    return None
