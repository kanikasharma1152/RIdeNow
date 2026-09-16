import pytest
from httpx import AsyncClient

# Basic async tests for auth endpoints

@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient):
    # Register
    user_data = {
        "name": "Test Passenger",
        "email": "testpassenger1@example.com",
        "phone": "9999999991",
        "password": "password123",
        "role": "passenger"
    }
    
    register_res = await client.post("/users/register", json=user_data)
    assert register_res.status_code in (201, 400) # 400 if already exists
    
    # Login
    login_data = {
        "username": "testpassenger1@example.com",
        "password": "password123"
    }
    login_res = await client.post("/users/login", data=login_data)
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    assert token is not None

    # Get Me
    me_res = await client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "testpassenger1@example.com"
