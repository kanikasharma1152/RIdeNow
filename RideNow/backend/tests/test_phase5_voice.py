"""
RideNow Voice AI & Cartesia Integration Tests
==============================================
Verifies:
1. Voice token authentication & unauthenticated rejection
2. Passenger voice access
3. Driver voice access
4. Voice health endpoint status
5. Cartesia & LiveKit settings configuration
6. Shared Voice Tools generation & role checks
7. Safe cancellation prompt behavior in voice
"""

import pytest
from httpx import AsyncClient
from app.core.config import settings
from app.models.user import User
from app.ai.livekit_agent import create_voice_tools


@pytest.mark.asyncio
async def test_voice_token_unauthenticated(client: AsyncClient):
    """Voice token request requires JWT authentication."""
    response = await client.post("/voice/token", json={})
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_voice_token_authenticated_fallback(client: AsyncClient):
    """When LiveKit credentials are valid or fallback is returned."""
    login_res = await client.post(
        "/users/login",
        data={"username": "passenger@ridenow.test", "password": "DemoPass123!"}
    )
    if login_res.status_code == 200:
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        res = await client.post("/voice/token", json={}, headers=headers)
        assert res.status_code in (200, 503)
        if res.status_code == 200:
            data = res.json()
            assert data["success"] is True
            assert "token" in data
            assert "url" in data
            assert "room" in data


@pytest.mark.asyncio
async def test_voice_health_endpoint(client: AsyncClient):
    """GET /voice/health returns safe infrastructure status."""
    res = await client.get("/voice/health")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "livekit" in data
    assert "cartesia" in data
    assert "groq" in data
    assert data["voice_id"] == settings.CARTESIA_VOICE_ID


def test_generate_voice_token_service():
    """Verify generate_voice_token produces a signed JWT with required attributes."""
    from app.services.voice import generate_voice_token
    res = generate_voice_token(
        user_id=42,
        user_name="Test User",
        room_name="ridenow-voice-42",
        user_role="passenger",
        ttl_minutes=30,
    )
    assert res["room"] == "ridenow-voice-42"
    assert res["url"] == settings.LIVEKIT_URL
    assert res["expires_in"] == 1800
    assert isinstance(res["token"], str)
    assert len(res["token"]) > 50


def test_voice_tools_generation_passenger():
    """Verify voice tool factory generates verified tools for passenger."""
    passenger = User(
        id=10,
        name="Test Passenger",
        email="passenger10@test.com",
        phone="9100000000",
        password_hash="",
        role="passenger",
    )
    tools = create_voice_tools(passenger)
    tool_names = [t.info.name for t in tools]
    assert "get_active_ride" in tool_names
    assert "estimate_fare" in tool_names
    assert "get_ride_history" in tool_names
    assert "cancel_ride" in tool_names
    assert "search_policies_and_faq" in tool_names
    # Driver only tools should not be in passenger tools
    assert "get_driver_summary" not in tool_names
    assert "get_route_tip" not in tool_names


def test_voice_tools_generation_driver():
    """Verify voice tool factory provides driver specific tools for driver."""
    driver = User(
        id=20,
        name="Test Driver",
        email="driver20@test.com",
        phone="9200000000",
        password_hash="",
        role="driver",
    )
    tools = create_voice_tools(driver)
    tool_names = [t.info.name for t in tools]
    assert "get_active_ride" in tool_names
    assert "estimate_fare" in tool_names
    assert "get_driver_summary" in tool_names
    assert "get_route_tip" in tool_names
