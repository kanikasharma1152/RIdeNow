"""
Anomaly Detector
================
Real-time safety monitoring for active rides.

Detects:
  1. ROUTE_DEVIATION  — driver is far from expected OSRM route corridor
  2. LONG_STOP        — vehicle hasn't moved for unexpectedly long time
  3. SPEED_ANOMALY    — vehicle moving much faster than plausible (GPS glitch / unsafe)

Returns structured anomaly events — does NOT create DB records directly.
The calling service (safety.py) is responsible for persisting and notifying.

All results carry:
  - `anomaly_type`: str or None
  - `severity`: "LOW" | "MEDIUM" | "HIGH" | None
  - `details`: dict with diagnostic info
"""

from __future__ import annotations

import math
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# ─── Thresholds ───────────────────────────────────────────────────────────────

# Max distance from any point on the OSRM route corridor (km)
ROUTE_DEVIATION_THRESHOLD_KM = 0.5

# How long (seconds) a vehicle can be stationary before flagging
LONG_STOP_THRESHOLD_SECONDS = 300  # 5 minutes

# Max realistic vehicle speed (km/h) — above this is likely GPS error
MAX_PLAUSIBLE_SPEED_KMH = 200.0

# Minimum distance moved (meters) to count as "not stopped"
MIN_MOVEMENT_METERS = 50.0


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _distance_to_segment_km(
    px: float, py: float,
    ax: float, ay: float,
    bx: float, by: float,
) -> float:
    """
    Minimum distance from point P to line segment AB (all in lat/lon degrees).
    Returns distance in km.
    """
    dx = bx - ax
    dy = by - ay
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq < 1e-12:
        return _haversine_km(px, py, ax, ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg_len_sq))
    proj_x = ax + t * dx
    proj_y = ay + t * dy
    return _haversine_km(px, py, proj_x, proj_y)


# ─── Route Deviation Detection ────────────────────────────────────────────────

def check_route_deviation(
    current_lat: float,
    current_lon: float,
    route_waypoints: list[tuple[float, float]],
    threshold_km: float = ROUTE_DEVIATION_THRESHOLD_KM,
) -> dict:
    """
    Check if the vehicle's current position deviates from the expected route.

    Args:
        current_lat, current_lon: current GPS position
        route_waypoints: list of (lat, lon) tuples from OSRM route geometry
        threshold_km: maximum allowed deviation in km

    Returns:
        {
            "is_deviated": bool,
            "min_distance_km": float,
            "threshold_km": float,
            "anomaly_type": "ROUTE_DEVIATION" | None,
            "severity": "LOW" | "MEDIUM" | "HIGH" | None,
        }
    """
    if not route_waypoints or len(route_waypoints) < 2:
        return {
            "is_deviated": False,
            "min_distance_km": 0.0,
            "threshold_km": threshold_km,
            "anomaly_type": None,
            "severity": None,
            "note": "insufficient_waypoints",
        }

    # Find minimum distance from current position to any route segment
    min_dist = float("inf")
    for i in range(len(route_waypoints) - 1):
        a = route_waypoints[i]
        b = route_waypoints[i + 1]
        dist = _distance_to_segment_km(
            current_lat, current_lon,
            a[0], a[1],
            b[0], b[1],
        )
        if dist < min_dist:
            min_dist = dist

    is_deviated = min_dist > threshold_km

    severity = None
    anomaly_type = None
    if is_deviated:
        anomaly_type = "ROUTE_DEVIATION"
        if min_dist > threshold_km * 4:
            severity = "HIGH"
        elif min_dist > threshold_km * 2:
            severity = "MEDIUM"
        else:
            severity = "LOW"

    return {
        "is_deviated": is_deviated,
        "min_distance_km": round(min_dist, 3),
        "threshold_km": threshold_km,
        "anomaly_type": anomaly_type,
        "severity": severity,
    }


# ─── Long Stop Detection ──────────────────────────────────────────────────────

def check_long_stop(
    last_position_update: datetime,
    last_lat: float,
    last_lon: float,
    current_lat: float,
    current_lon: float,
    now: datetime | None = None,
    threshold_seconds: int = LONG_STOP_THRESHOLD_SECONDS,
) -> dict:
    """
    Check if the vehicle has been stationary for too long.

    Args:
        last_position_update: datetime of the previous location ping
        last_lat, last_lon: previous GPS coordinates
        current_lat, current_lon: current GPS coordinates
        now: current time (defaults to UTC now)
        threshold_seconds: seconds before flagging a long stop

    Returns:
        {
            "is_long_stop": bool,
            "stationary_seconds": float,
            "threshold_seconds": int,
            "distance_moved_m": float,
            "anomaly_type": "LONG_STOP" | None,
            "severity": str | None,
        }
    """
    now = now or datetime.now(timezone.utc)

    # Normalize timezone
    if last_position_update.tzinfo is None:
        last_position_update = last_position_update.replace(tzinfo=timezone.utc)

    elapsed_seconds = (now - last_position_update).total_seconds()
    distance_moved_m = _haversine_km(last_lat, last_lon, current_lat, current_lon) * 1000.0

    is_long_stop = (
        distance_moved_m < MIN_MOVEMENT_METERS
        and elapsed_seconds > threshold_seconds
    )

    severity = None
    anomaly_type = None
    if is_long_stop:
        anomaly_type = "LONG_STOP"
        if elapsed_seconds > threshold_seconds * 3:
            severity = "HIGH"
        elif elapsed_seconds > threshold_seconds * 1.5:
            severity = "MEDIUM"
        else:
            severity = "LOW"

    return {
        "is_long_stop": is_long_stop,
        "stationary_seconds": round(elapsed_seconds, 1),
        "threshold_seconds": threshold_seconds,
        "distance_moved_m": round(distance_moved_m, 1),
        "anomaly_type": anomaly_type,
        "severity": severity,
    }


# ─── Speed Anomaly Detection ──────────────────────────────────────────────────

def check_speed_anomaly(
    prev_lat: float,
    prev_lon: float,
    prev_time: datetime,
    curr_lat: float,
    curr_lon: float,
    curr_time: datetime | None = None,
    max_speed_kmh: float = MAX_PLAUSIBLE_SPEED_KMH,
) -> dict:
    """
    Check if the instantaneous speed between two GPS pings is implausibly high.
    This catches GPS glitches and unsafe driving.

    Returns:
        {
            "speed_kmh": float,
            "is_anomalous": bool,
            "anomaly_type": "SPEED_ANOMALY" | None,
            "severity": str | None,
        }
    """
    curr_time = curr_time or datetime.now(timezone.utc)

    if prev_time.tzinfo is None:
        prev_time = prev_time.replace(tzinfo=timezone.utc)
    if curr_time.tzinfo is None:
        curr_time = curr_time.replace(tzinfo=timezone.utc)

    elapsed_seconds = (curr_time - prev_time).total_seconds()
    if elapsed_seconds < 1:
        return {
            "speed_kmh": 0.0,
            "is_anomalous": False,
            "anomaly_type": None,
            "severity": None,
            "note": "insufficient_time_elapsed",
        }

    distance_km = _haversine_km(prev_lat, prev_lon, curr_lat, curr_lon)
    speed_kmh = (distance_km / elapsed_seconds) * 3600.0

    is_anomalous = speed_kmh > max_speed_kmh
    severity = None
    anomaly_type = None

    if is_anomalous:
        anomaly_type = "SPEED_ANOMALY"
        if speed_kmh > max_speed_kmh * 2:
            severity = "HIGH"
        elif speed_kmh > max_speed_kmh * 1.5:
            severity = "MEDIUM"
        else:
            severity = "LOW"

    return {
        "speed_kmh": round(speed_kmh, 1),
        "is_anomalous": is_anomalous,
        "anomaly_type": anomaly_type,
        "severity": severity,
    }


# ─── Composite Safety Check ───────────────────────────────────────────────────

def run_safety_checks(
    current_lat: float,
    current_lon: float,
    current_time: datetime | None = None,
    route_waypoints: list[tuple[float, float]] | None = None,
    prev_lat: float | None = None,
    prev_lon: float | None = None,
    prev_time: datetime | None = None,
    last_position_update: datetime | None = None,
) -> dict:
    """
    Run all anomaly detectors and return a unified safety report.

    Returns:
        {
            "safe": bool,
            "anomalies": list[dict],
            "highest_severity": str | None,
            "checks": {
                "route_deviation": dict | None,
                "long_stop": dict | None,
                "speed": dict | None,
            }
        }
    """
    now = current_time or datetime.now(timezone.utc)
    anomalies: list[dict] = []
    checks: dict = {
        "route_deviation": None,
        "long_stop": None,
        "speed": None,
    }

    # Route deviation
    if route_waypoints:
        rd = check_route_deviation(current_lat, current_lon, route_waypoints)
        checks["route_deviation"] = rd
        if rd["is_deviated"]:
            anomalies.append(rd)

    # Long stop
    if prev_lat is not None and prev_lon is not None and last_position_update is not None:
        ls = check_long_stop(
            last_position_update=last_position_update,
            last_lat=prev_lat,
            last_lon=prev_lon,
            current_lat=current_lat,
            current_lon=current_lon,
            now=now,
        )
        checks["long_stop"] = ls
        if ls["is_long_stop"]:
            anomalies.append(ls)

        # Speed check
        if prev_time is not None:
            sp = check_speed_anomaly(
                prev_lat=prev_lat,
                prev_lon=prev_lon,
                prev_time=prev_time,
                curr_lat=current_lat,
                curr_lon=current_lon,
                curr_time=now,
            )
            checks["speed"] = sp
            if sp["is_anomalous"]:
                anomalies.append(sp)

    severity_order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, None: 0}
    highest_severity = max(
        (a.get("severity") for a in anomalies),
        key=lambda s: severity_order.get(s, 0),
        default=None,
    )

    return {
        "safe": len(anomalies) == 0,
        "anomalies": anomalies,
        "highest_severity": highest_severity,
        "checks": checks,
    }
