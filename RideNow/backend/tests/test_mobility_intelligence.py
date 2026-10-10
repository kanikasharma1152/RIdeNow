"""
RideNow — Phase 5 AI Mobility Intelligence & Predictive Experience Tests
========================================================================
Verifies:
1. get_demand_forecast tool (demand level, score, congestion)
2. get_eta_prediction tool (trip duration, driver pickup ETA, traffic factor)
3. get_smart_pickup_points tool (walking distance, accessibility rating, curbside recommendation)
4. AI Trip Planner with backward departure calculation based on target arrival
5. AI Trip Planner default departure time
6. User mobility analytics & spend aggregation (strictly isolated by user)
7. Driver matching transparency & explainability tool
8. Ride recommendation tool (actionable departure and pickup tips)
9. POST /mobility/trip-plan REST endpoint
10. GET /mobility/summary REST endpoint
11. GET /mobility/smart-pickup REST endpoint
12. GET /mobility/recommendation REST endpoint
13. GET /mobility/matching-explanation REST endpoint
14. AI Agent fallback for trip planning query
15. AI Agent fallback for user spend & mobility query
16. Driver copilot dynamic demand hotspots from ML layer
"""

import pytest
from unittest.mock import patch
from datetime import datetime, timezone
from httpx import AsyncClient
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.ride import Ride
from app.ai.agent.agent import process_chat_message
from app.ai.tools.mobility_tools import (
    get_demand_forecast_tool,
    get_eta_prediction_tool,
    get_smart_pickup_points_tool,
    get_trip_plan_tool,
    get_user_mobility_summary_tool,
    get_ride_recommendation_tool,
    get_driver_matching_explanation_tool,
)
from app.services.mobility import (
    plan_trip,
    get_user_mobility_analytics,
    resolve_smart_pickup_points,
    explain_driver_matching,
    get_ride_recommendation,
)
from app.services.copilot import get_driver_copilot_briefing


# ─── Helper Fixtures ─────────────────────────────────────────────────────────

async def _create_test_user(client: AsyncClient, prefix: str, role: str = "passenger"):
    import random, string
    suffix = "".join(random.choices(string.ascii_lowercase, k=6))
    phone_digits = "".join(random.choices(string.digits, k=8))
    email = f"{prefix}_{suffix}@mobilitytest.com"
    phone = f"97{phone_digits}"

    reg = await client.post("/users/register", json={
        "name": f"User {prefix}",
        "email": email,
        "phone": phone,
        "password": "Password123!",
        "role": role,
    })
    assert reg.status_code in (200, 201), f"Reg error: {reg.text}"
    user_id = reg.json()["id"]

    login = await client.post("/users/login", data={"username": email, "password": "Password123!"})
    assert login.status_code == 200, f"Login error: {login.text}"
    token = login.json()["access_token"]

    return {
        "email": email,
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
        "user_id": user_id,
        "name": f"User {prefix}",
    }


# ─── Tool Tests ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_demand_forecast_tool():
    """Verify demand forecast returns valid demand level, score, and summary."""
    res = await get_demand_forecast_tool(latitude=22.7196, longitude=75.8577, location="Indore Junction")
    assert res["success"] is True
    assert res["demand_level"] in ("LOW", "MEDIUM", "HIGH")
    assert isinstance(res["demand_score"], float)
    assert "summary" in res
    assert "Indore Junction" in res["summary"]


@pytest.mark.asyncio
async def test_get_eta_prediction_tool():
    """Verify ETA prediction returns trip duration, distance, and confidence."""
    with patch("app.services.google_map.calculate_route_distance", return_value=8.5):
        res = await get_eta_prediction_tool(
            pickup_location="Palasia Square",
            dropoff_location="Airport Terminal",
            pickup_latitude=22.72,
            pickup_longitude=75.88,
            dropoff_latitude=22.72,
            dropoff_longitude=75.80,
        )
    assert res["success"] is True
    assert res["trip_distance_km"] > 0
    assert res["trip_eta_minutes"] > 0
    assert res["total_eta_minutes"] >= res["trip_eta_minutes"]
    assert "summary" in res


@pytest.mark.asyncio
async def test_get_smart_pickup_points_tool():
    """Verify smart pickup points return curbside and landmark options."""
    res = await get_smart_pickup_points_tool(
        location="Indore Central Mall",
        latitude=22.72,
        longitude=75.88,
    )
    assert res["success"] is True
    assert "recommended_point" in res
    assert res["recommended_point"]["is_recommended"] is True
    assert res["recommended_point"]["walking_distance_meters"] >= 0
    assert len(res["all_pickup_options"]) >= 2


@pytest.mark.asyncio
async def test_plan_trip_calculation_with_target_arrival():
    """Verify backward departure time calculation when target arrival is 8:00 PM."""
    with patch("app.services.google_map.calculate_route_distance", return_value=10.0):
        plan = await plan_trip(
            origin="Bhawarkua",
            destination="Airport",
            target_arrival_time="8:00 PM",
            pickup_latitude=22.70,
            pickup_longitude=75.86,
            dropoff_latitude=22.72,
            dropoff_longitude=75.80,
        )
    assert plan["success"] is True
    assert plan["distance_km"] > 0
    assert plan["recommended_departure_time"] is not None
    assert plan["target_arrival_time"] == "08:00 PM"
    assert plan["auto_booked"] is False
    assert plan["fare_range"]["min"] > 0
    assert plan["fare_range"]["max"] >= plan["fare_range"]["min"]
    assert len(plan["smart_pickup_points"]) >= 2


@pytest.mark.asyncio
async def test_plan_trip_default_departure():
    """Verify trip planning without arrival time defaults to leaving now."""
    with patch("app.services.google_map.calculate_route_distance", return_value=5.0):
        plan = await plan_trip(
            origin="Vijay Nagar",
            destination="Railway Station",
            pickup_latitude=22.75,
            pickup_longitude=75.89,
            dropoff_latitude=22.72,
            dropoff_longitude=75.86,
        )
    assert plan["success"] is True
    assert plan["recommended_departure_time"] is not None
    assert plan["total_duration_minutes"] > 0


@pytest.mark.asyncio
async def test_user_mobility_summary_isolation(client: AsyncClient, db_session: AsyncSession):
    """Verify user mobility analytics strictly isolate user spend and ride counts."""
    user_a = await _create_test_user(client, "MobilityA")
    user_b = await _create_test_user(client, "MobilityB")

    # Seed 2 completed rides for User A directly in DB
    ride1 = Ride(
        passenger_id=user_a["user_id"],
        pickup_location="Home A",
        dropoff_location="Office",
        pickup_latitude=22.72,
        pickup_longitude=75.88,
        status="COMPLETED",
        fare=Decimal("150.00"),
        distance_km=Decimal("8.0"),
        created_at=datetime.now(timezone.utc),
    )
    ride2 = Ride(
        passenger_id=user_a["user_id"],
        pickup_location="Office",
        dropoff_location="Railway Station",
        pickup_latitude=22.75,
        pickup_longitude=75.89,
        status="COMPLETED",
        fare=Decimal("250.00"),
        distance_km=Decimal("12.0"),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add_all([ride1, ride2])
    await db_session.commit()

    # Check User A analytics
    stats_a = await get_user_mobility_analytics(user_a["user_id"], db_session)
    assert stats_a["lifetime_stats"]["completed_trips"] == 2
    assert stats_a["lifetime_stats"]["total_spend_inr"] == 400.00
    assert stats_a["lifetime_stats"]["average_fare_inr"] == 200.00

    # Check User B analytics (Must be 0 — strict user isolation)
    stats_b = await get_user_mobility_analytics(user_b["user_id"], db_session)
    assert stats_b["lifetime_stats"]["completed_trips"] == 0
    assert stats_b["lifetime_stats"]["total_spend_inr"] == 0.00


@pytest.mark.asyncio
async def test_driver_matching_explanation_tool(db_session: AsyncSession):
    """Verify driver matching explainability returns the 4 signals and weights."""
    res = await explain_driver_matching(pickup_lat=22.72, pickup_lon=75.88, db=db_session)
    assert res["success"] is True
    criteria = res["matching_criteria"]
    weights = {c["signal"]: c["weight_pct"] for c in criteria}
    assert 40 in weights.values()
    assert 30 in weights.values()
    assert 20 in weights.values()
    assert 10 in weights.values()
    assert "explainability_summary" in res


@pytest.mark.asyncio
async def test_get_ride_recommendation_tool(db_session: AsyncSession):
    """Verify ride recommendation generates actionable departure advice."""
    with patch("app.services.google_map.calculate_route_distance", return_value=6.0):
        rec = await get_ride_recommendation(
            origin="Geeta Bhawan",
            destination="Chappan Dukan",
            db=db_session,
        )
        assert rec["success"] is True
        assert "recommended_departure" in rec["departure_recommendation"]
        assert len(rec["actionable_tips"]) > 0


# ─── REST API Tests ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mobility_rest_trip_plan(client: AsyncClient):
    """Test POST /mobility/trip-plan endpoint."""
    user = await _create_test_user(client, "RestPlan")
    with patch("app.services.google_map.calculate_route_distance", return_value=7.2):
        resp = await client.post(
            "/mobility/trip-plan",
            headers=user["headers"],
            json={
                "origin": "Palasia",
                "destination": "Airport",
                "target_arrival_time": "9:30 PM",
                "pickup_latitude": 22.72,
                "pickup_longitude": 75.88,
                "dropoff_latitude": 22.72,
                "dropoff_longitude": 75.80,
            },
        )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["success"] is True
    assert data["target_arrival_time"] == "09:30 PM"
    assert data["recommended_departure_time"] is not None
    assert data["auto_booked"] is False


@pytest.mark.asyncio
async def test_mobility_rest_summary(client: AsyncClient):
    """Test GET /mobility/summary endpoint."""
    user = await _create_test_user(client, "RestSummary")
    resp = await client.get("/mobility/summary", headers=user["headers"])
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["success"] is True
    assert data["user_id"] == user["user_id"]
    assert "lifetime_stats" in data


@pytest.mark.asyncio
async def test_mobility_rest_smart_pickup(client: AsyncClient):
    """Test GET /mobility/smart-pickup endpoint."""
    user = await _create_test_user(client, "RestPickup")
    resp = await client.get(
        "/mobility/smart-pickup?lat=22.72&lon=75.88&address=Treasure%20Island%20Mall",
        headers=user["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) >= 2
    assert any(p["is_recommended"] for p in data)


@pytest.mark.asyncio
async def test_mobility_rest_recommendation(client: AsyncClient):
    """Test GET /mobility/recommendation endpoint."""
    user = await _create_test_user(client, "RestRec")
    with patch("app.services.google_map.calculate_route_distance", return_value=4.5):
        resp = await client.get(
            "/mobility/recommendation?origin=Palasia&destination=Bhawarkua",
            headers=user["headers"],
        )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["success"] is True
    assert "departure_recommendation" in data


@pytest.mark.asyncio
async def test_mobility_rest_matching_explanation(client: AsyncClient):
    """Test GET /mobility/matching-explanation endpoint."""
    user = await _create_test_user(client, "RestExplain")
    resp = await client.get("/mobility/matching-explanation?lat=22.72&lon=75.88", headers=user["headers"])
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["success"] is True
    assert "matching_criteria" in data


# ─── AI Agent Fallback Tests ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ai_agent_fallback_trip_plan(client: AsyncClient, db_session: AsyncSession):
    """Test AI chat agent fallback handles trip planning natural language query."""
    user_info = await _create_test_user(client, "AiPlan")
    user = await db_session.get(User, user_info["user_id"])
    with patch("app.services.google_map.calculate_route_distance", return_value=9.0):
        res = await process_chat_message(
            "reach Indore Airport by 8:30 PM",
            current_user=user,
            db=db_session,
        )
    reply_l = res["reply"].lower()
    assert "trip" in reply_l or "departure" in reply_l or "fare" in reply_l or "airport" in reply_l or "योजना" in reply_l
    assert any(t["tool"] == "get_trip_plan" for t in res["tools_executed"])


@pytest.mark.asyncio
async def test_ai_agent_fallback_spend(client: AsyncClient, db_session: AsyncSession):
    """Test AI chat agent fallback handles spending / mobility analytics query."""
    user_info = await _create_test_user(client, "AiSpend")
    user = await db_session.get(User, user_info["user_id"])
    res = await process_chat_message(
        "how much did I spend this month?",
        current_user=user,
        db=db_session,
    )
    assert "spend" in res["reply"].lower()
    assert any(t["tool"] == "get_user_mobility_summary" for t in res["tools_executed"])


@pytest.mark.asyncio
async def test_ai_agent_fallback_smart_pickup(client: AsyncClient, db_session: AsyncSession):
    """Test AI chat agent fallback handles smart pickup query.

    The agent may route this via get_smart_pickup_points tool OR inline via Groq.
    We verify a meaningful pickup-related answer is produced in either case.
    """
    user_info = await _create_test_user(client, "AiPickup")
    user = await db_session.get(User, user_info["user_id"])
    res = await process_chat_message(
        "best pickup point near Indore Junction Railway Station",
        current_user=user,
        db=db_session,
    )
    reply_lower = res["reply"].lower()
    # Accept either a pickup-focused reply OR the tool being explicitly executed
    tool_fired = any(t["tool"] == "get_smart_pickup_points" for t in res["tools_executed"])
    reply_relevant = any(w in reply_lower for w in [
        "pickup", "spot", "curbside", "gate", "entrance", "main exit",
        "railway", "station", "platform", "junction"
    ])
    assert reply_relevant or tool_fired, (
        f"Expected pickup-related reply or tool execution. "
        f"Reply: {res['reply'][:200]} | Tools: {res['tools_executed']}"
    )


@pytest.mark.asyncio
async def test_copilot_briefing_dynamic_hotspots(client: AsyncClient, db_session: AsyncSession):
    """Verify driver copilot briefing returns dynamic demand hotspots."""
    driver_info = await _create_test_user(client, "CopilotDriver", role="driver")
    user = await db_session.get(User, driver_info["user_id"])
    briefing = await get_driver_copilot_briefing(user, db_session)
    assert briefing["success"] is True
    assert len(briefing["demand_zones"]) >= 1
    zone = briefing["demand_zones"][0]
    assert "zone" in zone
    assert "surge_factor" in zone
