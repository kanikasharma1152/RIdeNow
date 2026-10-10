"""
ML API Router
=============
Exposes ML predictions via REST endpoints.

Routes:
  GET /ml/demand          — Demand level for a lat/lon point
  GET /ml/demand/hotspots — Top demand hotspots from historical data
  GET /ml/eta             — ETA prediction for pickup→dropoff
  GET /ml/match           — Rank available drivers for a pickup point (admin/debug)
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.routers.user import get_current_user
from app.ml.demand.predictor import predict_zone_demand, get_demand_hotspots
from app.ml.eta.predictor import predict_eta

router = APIRouter(prefix="/ml", tags=["ML Predictions"])


# ─── Demand ───────────────────────────────────────────────────────────────────

@router.get("/demand")
async def demand_for_location(
    lat: float = Query(..., description="Latitude of the zone center"),
    lon: float = Query(..., description="Longitude of the zone center"),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    Return the predicted demand level for a geographic location at the current time.

    - `demand_level`: LOW | MEDIUM | HIGH
    - `demand_score`: 0.0–3.0+ composite score
    - `method`: "rule_based" (no ML model trained yet)
    """
    result = await predict_zone_demand(lat=lat, lon=lon, db=db)
    return {"success": True, "data": result}


@router.get("/demand/hotspots")
async def demand_hotspots(
    limit: int = Query(5, ge=1, le=20, description="Max number of hotspots to return"),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    Return the top demand hotspot zones based on 7-day historical ride pickups,
    adjusted by current time-of-day factor.
    """
    hotspots = await get_demand_hotspots(db=db, limit=limit)
    return {
        "success": True,
        "count": len(hotspots),
        "data": hotspots,
        "note": "rule_based — historical pickup density × time-of-day multiplier",
    }


# ─── ETA ──────────────────────────────────────────────────────────────────────

@router.get("/eta")
async def eta_prediction(
    pickup_lat: float = Query(...),
    pickup_lon: float = Query(...),
    dropoff_lat: float = Query(...),
    dropoff_lon: float = Query(...),
    driver_lat: float | None = Query(None, description="Driver's current latitude"),
    driver_lon: float | None = Query(None, description="Driver's current longitude"),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    Predict ETA for a complete trip:
      - Driver to pickup point (if driver coordinates provided)
      - Pickup to dropoff
      - Total end-to-end

    Combines OSRM routing + time-of-day congestion + historical correction.
    """
    result = await predict_eta(
        pickup_lat=pickup_lat,
        pickup_lon=pickup_lon,
        dropoff_lat=dropoff_lat,
        dropoff_lon=dropoff_lon,
        driver_lat=driver_lat,
        driver_lon=driver_lon,
        db=db,
    )
    return {"success": True, "data": result}


# ─── Health / Model Info ──────────────────────────────────────────────────────

@router.get("/info")
async def ml_info(_: dict = Depends(get_current_user)):
    """
    Return metadata about the current ML layer state.
    """
    return {
        "success": True,
        "data": {
            "demand_model": {
                "type": "rule_based",
                "description": "Time-of-day × day-of-week × historical DB counts",
                "ready_for_ml": False,
                "required_training_samples": 500,
            },
            "eta_model": {
                "type": "osrm_corrected",
                "description": "OSRM routing + congestion multiplier + historical correction",
                "ready_for_ml": False,
                "required_training_samples": 200,
            },
            "anomaly_detector": {
                "type": "rule_based",
                "description": "Route deviation + long stop + speed anomaly detection",
                "active": True,
            },
            "driver_matching": {
                "type": "rule_based",
                "description": "Multi-signal: distance(40%) + ETA(30%) + rating(20%) + acceptance(10%)",
                "active": True,
            },
        },
    }
