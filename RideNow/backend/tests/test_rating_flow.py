"""
Rating Flow Regression Tests
==============================
Covers the complete passenger → rate ride flow including the
timezone NameError bug fix in services/ride.py (enrich_ride_with_driver_info).

Tests:
  1. timezone imported correctly in ride service (unit)
  2. datetime.now(timezone.utc) is callable (unit)
  3. POST /ratings requires auth (HTTP)
  4. GET /ratings/ride/{id} requires auth (HTTP)
  5. POST /ratings returns 422 for rating outside 1-5 (HTTP)
  6. Rating service rejects non-completed rides (service unit)
  7. Rating service rejects rides belonging to another passenger (service unit)
  8. Rating service prevents duplicate ratings (service unit)
"""
import pytest
import uuid
from datetime import datetime, timezone
from httpx import AsyncClient

from app.main import app


# ─── Unit: import guard ───────────────────────────────────────────────────────

def test_timezone_importable_from_ride_service():
    """
    Regression: 'from datetime import datetime' (without timezone) caused
    NameError: name 'timezone' is not defined inside enrich_ride_with_driver_info,
    making every GET /rides/{id} return HTTP 500 when the ride has a driver.
    """
    from app.services import ride as ride_service
    import inspect
    source = inspect.getsource(ride_service)
    assert "from datetime import datetime, timezone" in source, (
        "timezone must be imported alongside datetime in app/services/ride.py"
    )


def test_timezone_utc_usable():
    """datetime.now(timezone.utc) must work (would fail if import was missing)."""
    now = datetime.now(timezone.utc)
    assert now.tzinfo is not None


# ─── HTTP: Rating endpoint auth contract ─────────────────────────────────────

@pytest.mark.asyncio
async def test_post_ratings_requires_auth(client: AsyncClient):
    """POST /ratings must return 401 without Authorization header."""
    resp = await client.post("/ratings", json={"ride_id": 1, "rating": 5})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_ratings_ride_requires_auth(client: AsyncClient):
    """GET /ratings/ride/{id} must return 401 without auth."""
    resp = await client.get("/ratings/ride/1")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_rating_schema_rejects_out_of_range(client: AsyncClient, db_session):
    """POST /ratings must return 422 for rating values outside 1-5."""
    from app.models.user import User
    from app.core.security import create_access_token

    # Create a real passenger in the test DB so auth passes
    uid = str(uuid.uuid4())[:8]
    user = User(
        name=f"Schema Test Pax {uid}",
        email=f"schema_pax_{uid}@test.com",
        password_hash="x",
        role="passenger",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    # rating=0 is below minimum (ge=1)
    resp0 = await client.post("/ratings", json={"ride_id": 1, "rating": 0}, headers=headers)
    assert resp0.status_code == 422, f"Expected 422 for rating=0, got {resp0.status_code}"

    # rating=6 is above maximum (le=5)
    resp6 = await client.post("/ratings", json={"ride_id": 1, "rating": 6}, headers=headers)
    assert resp6.status_code == 422, f"Expected 422 for rating=6, got {resp6.status_code}"


# ─── Service unit: rating validation rules ────────────────────────────────────

def _make_uid() -> str:
    """Return a short unique string for test emails/license numbers."""
    return str(uuid.uuid4())[:8]


async def _create_user(db, role="passenger"):
    from app.models.user import User
    uid = _make_uid()
    user = User(
        name=f"Test {role} {uid}",
        email=f"test_{role}_{uid}@test.com",
        password_hash="x",
        role=role,
    )
    db.add(user)
    await db.flush()
    return user


async def _create_driver(db, user_id, suffix=""):
    from app.models.driver import Driver
    uid = _make_uid()
    driver = Driver(
        user_id=user_id,
        license_number=f"LIC-{uid}{suffix}",
        vehicle_model="Test Car",
        vehicle_number=f"TS-{uid}",
        vehicle_type="sedan",
    )
    db.add(driver)
    await db.flush()
    return driver


async def _create_ride(db, passenger_id, driver_id, status="COMPLETED"):
    from app.models.ride import Ride
    ride = Ride(
        passenger_id=passenger_id,
        driver_id=driver_id,
        pickup_location="A",
        dropoff_location="B",
        status=status,
        fare=100.0,
        distance_km=5.0,
    )
    db.add(ride)
    await db.commit()
    return ride


@pytest.mark.asyncio
async def test_rating_service_rejects_non_completed_ride(db_session):
    """submit_rating raises ValueError for rides that are not COMPLETED."""
    from app.services.ratings import submit_rating

    pax = await _create_user(db_session, "passenger")
    drv_user = await _create_user(db_session, "driver")
    drv = await _create_driver(db_session, drv_user.id)
    ride = await _create_ride(db_session, pax.id, drv.id, status="REQUESTED")

    with pytest.raises(ValueError, match="Only completed rides can be rated"):
        await submit_rating(
            db=db_session,
            passenger_id=pax.id,
            ride_id=ride.id,
            rating=4,
        )


@pytest.mark.asyncio
async def test_rating_service_rejects_wrong_passenger(db_session):
    """submit_rating raises ValueError when another passenger tries to rate."""
    from app.services.ratings import submit_rating

    owner = await _create_user(db_session, "passenger")
    other = await _create_user(db_session, "passenger")
    drv_user = await _create_user(db_session, "driver")
    drv = await _create_driver(db_session, drv_user.id)
    ride = await _create_ride(db_session, owner.id, drv.id, status="COMPLETED")

    with pytest.raises(ValueError, match="only rate your own ride"):
        await submit_rating(
            db=db_session,
            passenger_id=other.id,
            ride_id=ride.id,
            rating=3,
        )


@pytest.mark.asyncio
async def test_rating_service_rejects_duplicate(db_session):
    """submit_rating raises ValueError on a second rating for the same ride."""
    from app.services.ratings import submit_rating

    pax = await _create_user(db_session, "passenger")
    drv_user = await _create_user(db_session, "driver")
    drv = await _create_driver(db_session, drv_user.id)
    ride = await _create_ride(db_session, pax.id, drv.id, status="COMPLETED")

    # First rating — must succeed
    await submit_rating(db=db_session, passenger_id=pax.id, ride_id=ride.id, rating=5)

    # Second rating — must raise
    with pytest.raises(ValueError, match="already been rated"):
        await submit_rating(db=db_session, passenger_id=pax.id, ride_id=ride.id, rating=4)
