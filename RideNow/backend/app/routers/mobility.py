"""
RideNow AI — Mobility REST API Router (Phase 5)
==============================================
Exposes predictive mobility endpoints:
- POST /mobility/trip-plan: Calculate backwards departure schedule, ETA, and fare range
- GET  /mobility/summary: Authenticated user's isolated travel analytics & spend
- GET  /mobility/smart-pickup: Curbside and landmark pickup suggestions
- GET  /mobility/recommendation: Real-time route and departure tips
- GET  /mobility/matching-explanation: Transparency for driver matching algorithm
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.routers.user import get_current_user
from app.models.user import User
from app.services.mobility import (
    plan_trip,
    get_user_mobility_analytics,
    resolve_smart_pickup_points,
    explain_driver_matching,
    get_ride_recommendation,
)

router = APIRouter(prefix="/mobility", tags=["AI Mobility Intelligence"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class TripPlanRequest(BaseModel):
    destination: str = Field(..., description="Target dropoff location or landmark")
    origin: Optional[str] = Field("Current Location", description="Starting location or landmark")
    target_arrival_time: Optional[str] = Field(None, description="Desired arrival time (e.g. '8:00 PM', '14:30')")
    preferred_departure_time: Optional[str] = Field(None, description="Optional target departure time")
    pickup_latitude: Optional[float] = None
    pickup_longitude: Optional[float] = None
    dropoff_latitude: Optional[float] = None
    dropoff_longitude: Optional[float] = None


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/trip-plan")
async def create_trip_plan(
    req: TripPlanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate an AI trip plan with calculated optimal departure time,
    traffic congestion factors, fare range, and smart pickup points.
    """
    plan = await plan_trip(
        origin=req.origin or "Current Location",
        destination=req.destination,
        target_arrival_time=req.target_arrival_time,
        preferred_departure_time=req.preferred_departure_time,
        user_id=current_user.id,
        pickup_latitude=req.pickup_latitude,
        pickup_longitude=req.pickup_longitude,
        dropoff_latitude=req.dropoff_latitude,
        dropoff_longitude=req.dropoff_longitude,
        db=db,
    )
    return {"success": True, "data": plan}


@router.get("/summary")
async def get_my_mobility_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch personalized travel analytics for the authenticated user.
    Strictly isolated: returns total spend, completed rides, top destinations, and preferred travel window.
    """
    summary = await get_user_mobility_analytics(user_id=current_user.id, db=db)
    return {"success": True, "data": summary}


@router.get("/smart-pickup")
async def get_smart_pickup(
    lat: float = Query(..., description="Current latitude"),
    lon: float = Query(..., description="Current longitude"),
    address: Optional[str] = Query(None, description="Current street address or landmark"),
    _: User = Depends(get_current_user),
):
    """
    Suggest nearby high-accessibility pickup spots to minimize driver navigation delay.
    """
    pickups = resolve_smart_pickup_points(latitude=lat, longitude=lon, address=address)
    return {"success": True, "data": pickups}


@router.get("/recommendation")
async def get_travel_recommendation(
    destination: str = Query(..., description="Destination address or landmark"),
    origin: Optional[str] = Query("Current Location", description="Starting location"),
    target_time: Optional[str] = Query(None, description="Desired arrival or departure time"),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve real-time departure and timing recommendations for a prospective route.
    """
    rec = await get_ride_recommendation(
        origin=origin,
        destination=destination,
        db=db,
        target_time=target_time,
    )
    return {"success": True, "data": rec}


@router.get("/matching-explanation")
async def get_driver_matching_info(
    lat: Optional[float] = Query(22.7196, description="Pickup latitude"),
    lon: Optional[float] = Query(75.8577, description="Pickup longitude"),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Provides explainability details for RideNow's multi-signal ML matching engine.
    """
    explanation = await explain_driver_matching(pickup_lat=lat, pickup_lon=lon, db=db)
    return {"success": True, "data": explanation}
