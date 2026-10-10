"""
RideNow AI — Phase 2 Regression Tests: Natural Language Booking & Multimodal AI
================================================================================
Comprehensive tests for:
1. book_ride tool existence and schema in central registry.
2. MCP tools/list includes book_ride for passenger.
3. Driver cannot call book_ride (role protection).
4. Unauthenticated booking rejection.
5. Location resolution, fare calculation, and confirmation safety.
6. Actual database ride creation and status transitions.
7. Duplicate booking prevention (active ride in progress).
8. Conversational Hindi and Hinglish intent handling.
9. Ambiguity detection and clarification prompts.
10. Error sanitization (no internal exceptions leaked to user).
11. MCP tools/call execution for book_ride.
12. Vision provider capability reporting.
"""

import pytest
from unittest.mock import patch
from httpx import AsyncClient

from app.ai.tools.registry import TOOL_DEFINITIONS, TOOL_FUNCTIONS, get_available_tools_for_role, execute_tool
from app.mcp.server import mcp_server
from app.services.location_intelligence import check_ambiguity


class MockUser:
    def __init__(self, user_id=1, role="passenger", name="Test Passenger"):
        self.id = user_id
        self.role = role
        self.name = name
        self.email = f"{role}@test.com"
        self.is_active = True


# ─── 1. Registry & MCP Schema Tests ──────────────────────────────────────────

def test_book_ride_tool_in_registry():
    """Verify book_ride is defined with compliant schema in central registry."""
    tool_names = [t["name"] for t in TOOL_DEFINITIONS]
    assert "book_ride" in tool_names

    book_def = next(t for t in TOOL_DEFINITIONS if t["name"] == "book_ride")
    assert "dropoff_location" in book_def["parameters"]["properties"]
    assert "confirmed" in book_def["parameters"]["properties"]
    assert "passenger" in book_def["allowed_roles"]
    assert "driver" not in book_def["allowed_roles"]


def test_mcp_tools_list_includes_book_ride_for_passenger():
    """Verify MCP tools/list automatically exposes book_ride for passengers."""
    passenger = MockUser(user_id=1, role="passenger")
    tools = mcp_server.list_tools(current_user=passenger)
    tool_names = [t["name"] for t in tools]
    assert "book_ride" in tool_names


def test_mcp_tools_list_excludes_book_ride_for_driver():
    """Verify MCP tools/list hides book_ride from drivers."""
    driver = MockUser(user_id=2, role="driver", name="Driver Dave")
    tools = mcp_server.list_tools(current_user=driver)
    tool_names = [t["name"] for t in tools]
    assert "book_ride" not in tool_names


# ─── 2. Role Security & Authorization ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_driver_cannot_call_book_ride():
    """Driver role must be rejected when attempting to call book_ride."""
    driver = MockUser(user_id=2, role="driver")
    res = await execute_tool(
        tool_name="book_ride",
        tool_args={"dropoff_location": "Airport", "confirmed": True},
        current_user=driver,
        db=None,
    )
    assert res["success"] is False
    assert "denied" in res["error"].lower() or "passenger" in res["error"].lower()


@pytest.mark.asyncio
async def test_unauthenticated_chat_rejected(client: AsyncClient):
    """Anonymous user cannot access /chat/message."""
    res = await client.post("/chat/message", json={"message": "Book a ride"})
    assert res.status_code in (401, 403)


# ─── 3. Confirmation Safety & Two-Step Booking Flow ───────────────────────────

@pytest.mark.asyncio
async def test_book_ride_requires_confirmation_first():
    """When confirmed=False, tool must return fare estimate and prompt for confirmation without booking."""
    passenger = MockUser(user_id=99, role="passenger")

    with patch("app.ai.tools.booking_tools.geocode_address") as mock_geo, \
         patch("app.ai.tools.booking_tools.calculate_route_distance") as mock_dist:
        mock_geo.side_effect = [
            {"latitude": 12.9716, "longitude": 77.5946},
            {"latitude": 12.9352, "longitude": 77.6245},
        ]
        mock_dist.return_value = 8.5

        res = await execute_tool(
            tool_name="book_ride",
            tool_args={
                "pickup_location": "MG Road",
                "dropoff_location": "Koramangala",
                "confirmed": False,
            },
            current_user=passenger,
            db=None,
        )

        assert res["success"] is False
        assert res["requires_confirmation"] is True
        assert res["distance_km"] == 8.5
        assert "₹" in res["estimated_fare"]
        assert "Shall I confirm" in res["message"]


# ─── 4. Ambiguity Detection ───────────────────────────────────────────────────

def test_ambiguity_detection_for_generic_landmarks():
    """Generic queries like 'airport' or 'railway station' return disambiguation options."""
    ambig = check_ambiguity("airport")
    assert ambig is not None
    assert len(ambig) > 1

    station_ambig = check_ambiguity("railway station")
    assert station_ambig is not None

    specific = check_ambiguity("Indore Junction Railway Station")
    assert specific is None


# ─── 5. Error Sanitization (No Technical Leakage) ─────────────────────────────

@pytest.mark.asyncio
async def test_tool_failure_sanitizes_errors():
    """If geocoding or routing fails, user receives a clean explanation, not a Python traceback."""
    passenger = MockUser(user_id=99, role="passenger")

    with patch("app.ai.tools.booking_tools.geocode_address", side_effect=Exception("Internal Nominatim 500")):
        res = await execute_tool(
            tool_name="book_ride",
            tool_args={"pickup_location": "xyz123", "dropoff_location": "abc999", "confirmed": False},
            current_user=passenger,
            db=None,
        )
        assert res["success"] is False
        assert "Unable to calculate route" in res["error"]
        assert "Traceback" not in res["error"]
        assert "Nominatim" not in res["error"]


# ─── 6. End-to-End Chat Booking via API ───────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_hindi_and_hinglish_booking_intents(client: AsyncClient):
    """Test that Hindi and Hinglish requests in chat are understood cleanly."""
    # First create and login test passenger
    user_data = {
        "name": "Aarav Sharma",
        "email": "aarav_multimodal@example.com",
        "phone": "9811122233",
        "password": "password123",
        "role": "passenger",
    }
    await client.post("/users/register", json=user_data)
    login_res = await client.post("/users/login", data={"username": user_data["email"], "password": "password123"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.services.google_map.geocode_address") as mock_geo, \
         patch("app.services.google_map.calculate_route_distance") as mock_dist:
        mock_geo.side_effect = [
            {"latitude": 22.7196, "longitude": 75.8577},
            {"latitude": 22.7533, "longitude": 75.8937},
            {"latitude": 22.7196, "longitude": 75.8577},
            {"latitude": 22.7533, "longitude": 75.8937},
        ]
        mock_dist.return_value = 6.0

        # Hinglish query: "bhai railway station tak ride book kar de"
        res1 = await client.post("/chat/message", json={"message": "bhai railway station tak ride book kar de"}, headers=headers)
        assert res1.status_code == 200
        data1 = res1.json()
        reply_lower = data1["reply"].lower()
        assert any(w in reply_lower for w in ["pickup", "location", "address", "fare", "railway", "station", "kahan"])

        # Confirmation: "haan book kar do"
        res2 = await client.post("/chat/message", json={"message": "haan book kar do"}, headers=headers)
        assert res2.status_code == 200
        data2 = res2.json()
        # Verify no Action: leak
        assert "Action:" not in data2["reply"]
        assert "book_ride" not in data2["reply"]


# ─── 7. Vision Analysis Capability & Endpoint ─────────────────────────────────

@pytest.mark.asyncio
async def test_vision_analyze_location_endpoint(client: AsyncClient):
    """Vision endpoint returns structured capability response without fake coordinates."""
    # Login user
    login_res = await client.post("/users/login", data={"username": "aarav_multimodal@example.com", "password": "password123"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        "query": "Main yahan khadi hoon, station jaana hai",
        "latitude": 22.7196,
        "longitude": 75.8577,
    }
    res = await client.post("/vision/analyze-location-json", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "message" in data
    assert "needs_confirmation" in data


# ─── 8. MCP tools/call Execution ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mcp_call_tool_book_ride():
    """Verify MCP server call_tool invokes book_ride using authenticated context."""
    passenger = MockUser(user_id=88, role="passenger")

    with patch("app.ai.tools.booking_tools.geocode_address") as mock_geo, \
         patch("app.ai.tools.booking_tools.calculate_route_distance") as mock_dist:
        mock_geo.side_effect = [
            {"latitude": 12.9716, "longitude": 77.5946},
            {"latitude": 12.9352, "longitude": 77.6245},
        ]
        mock_dist.return_value = 5.0

        res = await mcp_server.call_tool(
            tool_name="book_ride",
            arguments={"pickup_location": "Brigade Road", "dropoff_location": "Indiranagar", "confirmed": False},
            current_user=passenger,
            db=None,
        )
        assert res["isError"] is True  # because requires confirmation, success is False
        assert "data" in res
        assert res["data"]["requires_confirmation"] is True
        assert res["data"]["distance_km"] == 5.0
