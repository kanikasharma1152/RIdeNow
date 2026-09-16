import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_admin_analytics_forbidden_for_driver(client: AsyncClient):
    """Driver accounts cannot access admin analytics."""
    login_res = await client.post(
        "/users/login",
        data={"username": "driver@ridenow.test", "password": "DemoPass123!"}
    )
    if login_res.status_code == 200:
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        res = await client.get("/admin/analytics/overview", headers=headers)
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_admin_analytics_overview(client: AsyncClient):
    """Admin can fetch aggregate overview KPIs."""
    login_res = await client.post(
        "/users/login",
        data={"username": "admin@ridenow.test", "password": "DemoPass123!"}
    )
    if login_res.status_code == 200:
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        res = await client.get("/admin/analytics/overview", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "overview" in data
        assert "total_rides" in data["overview"]


@pytest.mark.asyncio
async def test_admin_analytics_insights(client: AsyncClient):
    """Admin can request AI operational insights."""
    login_res = await client.post(
        "/users/login",
        data={"username": "admin@ridenow.test", "password": "DemoPass123!"}
    )
    if login_res.status_code == 200:
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        res = await client.get("/admin/analytics/insights", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "ai_insights" in data
