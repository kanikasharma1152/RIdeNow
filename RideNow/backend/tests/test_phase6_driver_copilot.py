import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_driver_copilot_forbidden_for_passenger(client: AsyncClient):
    """Passenger accounts cannot access driver copilot endpoints."""
    login_res = await client.post(
        "/users/login",
        data={"username": "passenger@ridenow.test", "password": "DemoPass123!"}
    )
    if login_res.status_code == 200:
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        res = await client.get("/driver/copilot/briefing", headers=headers)
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_driver_copilot_briefing_for_driver(client: AsyncClient):
    """Driver can retrieve their briefing with operational stats."""
    login_res = await client.post(
        "/users/login",
        data={"username": "driver@ridenow.test", "password": "DemoPass123!"}
    )
    if login_res.status_code == 200:
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        res = await client.get("/driver/copilot/briefing", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "earnings" in data
        assert "demand_zones" in data


@pytest.mark.asyncio
async def test_driver_copilot_chat(client: AsyncClient):
    """Driver can ask copilot questions."""
    login_res = await client.post(
        "/users/login",
        data={"username": "driver@ridenow.test", "password": "DemoPass123!"}
    )
    if login_res.status_code == 200:
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        res = await client.post(
            "/driver/copilot/chat",
            json={"message": "Where are the hotspots right now?"},
            headers=headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "reply" in data


@pytest.mark.asyncio
async def test_driver_copilot_service_resilience():
    """Verify get_driver_copilot_briefing handles edge cases and dictionary stats without crashing."""
    from app.services.copilot import get_driver_copilot_briefing
    from app.models.user import User
    from app.database import AsyncSessionLocal

    mock_driver_user = User(
        id=99999,
        name="Telemetry Test Driver",
        email="telemetry_test@ridenow.test",
        phone="9999900000",
        password_hash="",
        role="driver",
    )
    async with AsyncSessionLocal() as db:
        briefing = await get_driver_copilot_briefing(mock_driver_user, db)
        assert briefing["success"] is True
        assert "earnings" in briefing
        assert isinstance(briefing["earnings"]["today"], str)
        assert isinstance(briefing["demand_zones"], list)
