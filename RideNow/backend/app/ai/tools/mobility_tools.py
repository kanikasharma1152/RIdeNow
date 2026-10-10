"""
RideNow AI — Mobility Intelligence Tools (Phase 5)
==================================================
Exposes mobility intelligence tools for AI agent and MCP server:
- get_demand_forecast: Real-time zone demand level & congestion
- get_eta_prediction: ML ETA calculation with congestion factor
- get_smart_pickup_points: Recommended boarding points with walking distance
- get_trip_plan: Backward departure calculation to meet target arrival
- get_user_mobility_summary: Isolated ride history, spend, and corridor statistics
- get_ride_recommendation: Actionable travel timing and savings advice
- get_driver_matching_explanation: Multi-signal driver scoring transparency
"""

import logging
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.google_map import geocode_address
from app.ml.demand.predictor import predict_zone_demand
from app.ml.eta.predictor import predict_eta
from app.services.mobility import (
    plan_trip,
    get_user_mobility_analytics,
    resolve_smart_pickup_points,
    explain_driver_matching,
    get_ride_recommendation,
)

logger = logging.getLogger(__name__)


async def get_demand_forecast_tool(
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    location: Optional[str] = None,
    current_user=None,
    db: Optional[AsyncSession] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Fetch current demand level, demand score, and peak travel factors for a location.
    """
    lat, lon = latitude, longitude
    loc_name = location or "Indore City Center"

    if lat is None or lon is None:
        try:
            coords = await geocode_address(loc_name)
            lat, lon = coords["latitude"], coords["longitude"]
        except Exception:
            lat, lon = 22.7196, 75.8577

    res = await predict_zone_demand(lat=lat, lon=lon, db=db)
    return {
        "success": True,
        "location": loc_name,
        "coordinates": {"latitude": lat, "longitude": lon},
        "demand_level": res.get("demand_level", "MEDIUM"),
        "demand_score": res.get("demand_score", 1.0),
        "hour_factor": res.get("hour_factor", 1.0),
        "summary": (
            f"Demand in {loc_name} is currently {res.get('demand_level', 'MEDIUM')} "
            f"(Score: {res.get('demand_score', 1.0)}). "
            f"{'Expect high driver dispatch activity and potential surge pricing.' if res.get('demand_level') == 'HIGH' else 'Normal ride availability.'}"
        ),
    }


async def get_eta_prediction_tool(
    pickup_location: Optional[str] = None,
    dropoff_location: Optional[str] = None,
    pickup_latitude: Optional[float] = None,
    pickup_longitude: Optional[float] = None,
    dropoff_latitude: Optional[float] = None,
    dropoff_longitude: Optional[float] = None,
    current_user=None,
    db: Optional[AsyncSession] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Calculate high-accuracy travel ETA between two points factoring in time-of-day traffic.
    """
    p_lat, p_lon = pickup_latitude, pickup_longitude
    d_lat, d_lon = dropoff_latitude, dropoff_longitude

    p_name = pickup_location or "Pickup Point"
    d_name = dropoff_location or "Dropoff Point"

    if p_lat is None or p_lon is None:
        try:
            coords = await geocode_address(p_name)
            p_lat, p_lon = coords["latitude"], coords["longitude"]
        except Exception:
            p_lat, p_lon = 22.7196, 75.8577

    if d_lat is None or d_lon is None:
        try:
            coords = await geocode_address(d_name)
            d_lat, d_lon = coords["latitude"], coords["longitude"]
        except Exception:
            d_lat, d_lon = 22.7533, 75.8937

    eta_res = await predict_eta(
        pickup_lat=p_lat,
        pickup_lon=p_lon,
        dropoff_lat=d_lat,
        dropoff_lon=d_lon,
        db=db,
    )

    return {
        "success": True,
        "pickup": p_name,
        "dropoff": d_name,
        "trip_distance_km": eta_res.get("trip_distance_km"),
        "trip_eta_minutes": eta_res.get("trip_eta_minutes"),
        "driver_pickup_eta_minutes": eta_res.get("driver_pickup_eta_minutes"),
        "total_eta_minutes": eta_res.get("total_eta_minutes"),
        "congestion_factor": eta_res.get("congestion_factor"),
        "confidence": eta_res.get("confidence"),
        "summary": (
            f"Estimated trip duration from {p_name} to {d_name} is "
            f"{eta_res.get('trip_eta_minutes')} minutes ({eta_res.get('trip_distance_km')} km), "
            f"with approximately {eta_res.get('driver_pickup_eta_minutes')} minutes for driver arrival."
        ),
    }


async def get_smart_pickup_points_tool(
    location: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    current_user=None,
    db: Optional[AsyncSession] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Suggest optimal pickup points near a location to save driver arrival time and walking effort.
    """
    lat, lon = latitude, longitude
    loc_name = location or "Current Location"

    if lat is None or lon is None:
        try:
            coords = await geocode_address(loc_name)
            lat, lon = coords["latitude"], coords["longitude"]
        except Exception:
            lat, lon = 22.7196, 75.8577

    points = resolve_smart_pickup_points(lat, lon, loc_name)
    recommended = next((p for p in points if p.get("is_recommended")), points[0] if points else None)

    return {
        "success": True,
        "reference_location": loc_name,
        "recommended_point": recommended,
        "all_pickup_options": points,
        "summary": (
            f"For {loc_name}, we recommend '{recommended['name']}' ({recommended['walking_distance_meters']}m walk). "
            f"{recommended['benefit']}."
            if recommended else "Smart pickup points resolved."
        ),
    }


async def get_trip_plan_tool(
    destination: str,
    origin: Optional[str] = None,
    target_arrival_time: Optional[str] = None,
    preferred_departure_time: Optional[str] = None,
    current_user=None,
    db: Optional[AsyncSession] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Plan a full trip backwards from a desired arrival time or forward from a departure time.
    Calculates departure schedule, ETA, traffic congestion, and fare estimate without auto-booking.
    """
    user_id = current_user.id if current_user else None
    plan = await plan_trip(
        origin=origin or "Current Location",
        destination=destination,
        target_arrival_time=target_arrival_time,
        preferred_departure_time=preferred_departure_time,
        user_id=user_id,
        db=db,
    )
    return plan


async def get_user_mobility_summary_tool(
    current_user=None,
    db: Optional[AsyncSession] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Fetch the authenticated passenger's personal travel history, total spend, and trip stats.
    Strictly isolates queries to the logged-in user.
    """
    if not current_user:
        return {"success": False, "error": "Authentication required to view mobility summary."}

    summary = await get_user_mobility_analytics(current_user.id, db)
    lifetime = summary.get("lifetime_stats", {})
    recent = summary.get("recent_30_days", {})

    return {
        "success": True,
        "user_name": current_user.name,
        "total_completed_rides": lifetime.get("completed_trips", 0),
        "total_spend_inr": lifetime.get("total_spend_inr", 0.0),
        "average_fare_inr": lifetime.get("average_fare_inr", 0.0),
        "monthly_spend_inr": recent.get("total_spend_inr", 0.0),
        "monthly_rides": recent.get("completed_trips", 0),
        "top_destinations": summary.get("top_destinations", []),
        "preferred_travel_window": summary.get("preferred_travel_window", "Flexible"),
        "summary": (
            f"You have completed {lifetime.get('completed_trips', 0)} ride(s) with total spend of ₹{lifetime.get('total_spend_inr', 0.0)}. "
            f"Over the last 30 days, you spent ₹{recent.get('total_spend_inr', 0.0)} across {recent.get('completed_trips', 0)} ride(s). "
            f"Preferred travel time: {summary.get('preferred_travel_window', 'Flexible')}."
        ),
    }


async def get_ride_recommendation_tool(
    destination: str,
    origin: Optional[str] = None,
    target_time: Optional[str] = None,
    current_user=None,
    db: Optional[AsyncSession] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Provide actionable timing and route recommendations for an upcoming trip.
    """
    return await get_ride_recommendation(
        origin=origin or "Current Location",
        destination=destination,
        db=db,
        target_time=target_time,
    )


async def get_driver_matching_explanation_tool(
    pickup_latitude: Optional[float] = None,
    pickup_longitude: Optional[float] = None,
    current_user=None,
    db: Optional[AsyncSession] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Explain how RideNow's smart driver matching algorithm evaluates candidates.
    """
    lat = pickup_latitude or 22.7196
    lon = pickup_longitude or 75.8577
    return await explain_driver_matching(pickup_lat=lat, pickup_lon=lon, db=db)
