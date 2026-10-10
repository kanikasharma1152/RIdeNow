"""
Phase 6: Driver Location WebSocket Broadcast Tests
===================================================
Verifies that PATCH /drivers/location correctly:
- Updates driver coordinates in the database
- Returns the updated location response
- The WS broadcast mechanism is accessible (broadcast_to_role exists)
"""

import pytest
import random
import string
from httpx import AsyncClient


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

async def make_driver_token(client: AsyncClient):
    """Register a user, make them a driver, return auth token and user_id."""
    suffix = "".join(random.choices(string.ascii_lowercase, k=6))
    phone_digits = "".join(random.choices(string.digits, k=8))
    email = f"phase6driver_{suffix}@mobilitytest.com"
    phone = f"98{phone_digits}"

    reg = await client.post("/users/register", json={
        "name": f"P6 Driver {suffix}",
        "email": email,
        "phone": phone,
        "password": "Password123!",
        "role": "driver",
    })
    assert reg.status_code in (200, 201), reg.text
    user_id = reg.json()["id"]

    login = await client.post("/users/login", data={
        "username": email,
        "password": "Password123!",
    })
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    dr = await client.post(
        "/drivers/register",
        json={
            "license_number": f"P6DL_{suffix[:4]}",
            "vehicle_type": "sedan",
            "vehicle_number": f"MP09P6_{suffix[:3]}",
            "vehicle_model": "Maruti Swift",
        },
        headers=headers,
    )
    assert dr.status_code in (200, 201), dr.text

    return headers, user_id


# ─────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_driver_location_update_returns_coords(client: AsyncClient):
    """Driver can update location and gets back correct coordinates."""
    headers, _ = await make_driver_token(client)

    resp = await client.patch(
        "/drivers/location",
        json={"latitude": 22.7196, "longitude": 75.8577},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "driver_id" in data
    assert abs(data["latitude"] - 22.7196) < 0.0001
    assert abs(data["longitude"] - 75.8577) < 0.0001
    assert "location_updated_at" in data


@pytest.mark.asyncio
async def test_driver_location_update_multiple_times(client: AsyncClient):
    """Repeated location updates work and return latest coordinates."""
    headers, _ = await make_driver_token(client)

    coords = [
        (22.7196, 75.8577),
        (22.7200, 75.8590),
        (22.7210, 75.8600),
    ]
    for lat, lng in coords:
        r = await client.patch(
            "/drivers/location",
            json={"latitude": lat, "longitude": lng},
            headers=headers,
        )
        assert r.status_code == 200
        assert abs(r.json()["latitude"] - lat) < 0.0001


@pytest.mark.asyncio
async def test_driver_location_requires_driver_role(client: AsyncClient):
    """Passenger cannot call PATCH /drivers/location."""
    suffix = "".join(random.choices(string.ascii_lowercase, k=6))
    phone_digits = "".join(random.choices(string.digits, k=8))
    email = f"phase6p_{suffix}@mobilitytest.com"
    phone = f"99{phone_digits}"

    reg = await client.post("/users/register", json={
        "name": f"P6 Passenger {suffix}",
        "email": email,
        "phone": phone,
        "password": "Password123!",
        "role": "passenger",
    })
    assert reg.status_code in (200, 201)
    login = await client.post("/users/login", data={
        "username": email,
        "password": "Password123!",
    })
    token = login.json()["access_token"]

    resp = await client.patch(
        "/drivers/location",
        json={"latitude": 22.7196, "longitude": 75.8577},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_driver_location_requires_auth(client: AsyncClient):
    """Unauthenticated request to PATCH /drivers/location is rejected."""
    resp = await client.patch(
        "/drivers/location",
        json={"latitude": 22.7196, "longitude": 75.8577},
    )
    assert resp.status_code in (401, 403)


def test_ws_manager_has_broadcast_method():
    """ws_manager singleton exposes broadcast_to_role method."""
    from app.core.connection_manager import ws_manager
    assert hasattr(ws_manager, "broadcast_to_role")
    assert callable(ws_manager.broadcast_to_role)


def test_ws_manager_has_send_personal_message():
    """ws_manager singleton exposes send_personal_message method."""
    from app.core.connection_manager import ws_manager
    assert hasattr(ws_manager, "send_personal_message")
    assert callable(ws_manager.send_personal_message)


@pytest.mark.asyncio
async def test_ws_manager_no_connections_broadcast_is_noop():
    """Broadcasting to empty role set does not raise."""
    from app.core.connection_manager import ConnectionManager
    mgr = ConnectionManager()
    await mgr.broadcast_to_role("admin", {"type": "driver_location", "data": {}})


def test_ws_manager_driver_to_user_registration():
    """Driver-to-user mapping is correctly stored and retrieved."""
    from app.core.connection_manager import ConnectionManager
    mgr = ConnectionManager()
    mgr.register_driver_id(driver_id=42, user_id=101)
    assert mgr.get_user_id_for_driver(42) == 101
    assert mgr.get_user_id_for_driver(999) is None
