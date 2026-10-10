"""
Phase 13 Safety & Trust Intelligence — Backend Tests
=====================================================
Tests the complete Phase 13 safety layer:
- Safety intent classifiers
- Safety Center endpoint
- Universal SOS & driver SOS
- User-reported safety concerns
- Event acknowledgment & resolution
- Trusted contacts CRUD with phone validation
- Admin safety events feed & metrics
- AI safety tools execution
"""

import pytest
import string
import random
from httpx import AsyncClient
from unittest.mock import patch

from app.models.user import User
from app.ai.agent.resolver import (
    is_safety_concern_intent,
    is_sos_intent,
    is_share_ride_intent,
    is_vehicle_details_intent,
    is_route_concern_intent,
    is_safety_center_intent,
)
from app.ai.tools.registry import execute_tool


# ─── Auth Helper ─────────────────────────────────────────────────────────────

async def _create_test_user(client: AsyncClient, prefix: str, role: str = "passenger"):
    suffix = "".join(random.choices(string.ascii_lowercase, k=6))
    phone_digits = "".join(random.choices(string.digits, k=8))
    email = f"{prefix}_{suffix}@p13test.com"
    phone = f"98{phone_digits}"

    reg = await client.post("/users/register", json={
        "name": f"User {prefix}",
        "email": email,
        "phone": phone,
        "password": "Password123!",
        "role": "passenger" if role == "admin" else role,
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
        "role": role,
    }


# ─── 1. AI Intent Classifier Unit Tests (12 tests) ──────────────────────────

class TestSafetyIntentClassifiers:

    def test_sos_intent_positive(self):
        assert is_sos_intent("SOS") is True
        assert is_sos_intent("I need emergency help") is True
        assert is_sos_intent("call police") is True
        assert is_sos_intent("bachao") is True

    def test_sos_intent_negative(self):
        assert is_sos_intent("book a ride to airport") is False
        assert is_sos_intent("what is the fare") is False

    def test_safety_concern_positive(self):
        assert is_safety_concern_intent("I don't feel safe") is True
        assert is_safety_concern_intent("something feels wrong") is True
        assert is_safety_concern_intent("I feel unsafe right now") is True
        assert is_safety_concern_intent("darr lag raha hai") is True

    def test_safety_concern_negative(self):
        assert is_safety_concern_intent("take me to the railway station") is False
        assert is_safety_concern_intent("how long will driver take") is False

    def test_share_ride_positive(self):
        assert is_share_ride_intent("share my ride") is True
        assert is_share_ride_intent("share this trip with family") is True
        assert is_share_ride_intent("share location") is True

    def test_share_ride_negative(self):
        assert is_share_ride_intent("cancel my ride") is False

    def test_vehicle_details_positive(self):
        assert is_vehicle_details_intent("show me the car") is True
        assert is_vehicle_details_intent("what car is coming") is True
        assert is_vehicle_details_intent("plate number") is True

    def test_vehicle_details_negative(self):
        assert is_vehicle_details_intent("where is the driver") is False

    def test_route_concern_positive(self):
        assert is_route_concern_intent("wrong route") is True
        assert is_route_concern_intent("driver is taking a different route") is True
        assert is_route_concern_intent("galat rasta") is True

    def test_route_concern_negative(self):
        assert is_route_concern_intent("good route") is False

    def test_safety_center_positive(self):
        assert is_safety_center_intent("safety center") is True
        assert is_safety_center_intent("am i safe") is True
        assert is_safety_center_intent("open safety info") is True

    def test_safety_center_negative(self):
        assert is_safety_center_intent("open settings") is False


# ─── 2. HTTP Endpoint Tests (13 tests) ───────────────────────────────────────

@pytest.mark.asyncio
class TestSafetyCenterEndpoints:

    async def test_safety_center_unauthorized(self, client: AsyncClient):
        res = await client.get("/safety/center")
        assert res.status_code == 401

    async def test_safety_center_authorized(self, client: AsyncClient):
        user = await _create_test_user(client, "sc_user")
        res = await client.get("/safety/center", headers=user["headers"])
        assert res.status_code == 200
        data = res.json()
        assert "has_active_ride" in data or "trusted_contacts" in data or "safety_status" in data

    async def test_universal_sos_honesty(self, client: AsyncClient):
        user = await _create_test_user(client, "sos_user")
        res = await client.post("/safety/sos", headers=user["headers"], json={"note": "Test emergency"})
        assert res.status_code in [200, 201]
        data = res.json()
        # Verify honest reporting: emergency services NOT falsely claimed
        assert data.get("emergency_services_contacted") is False
        assert "disclaimer" in data or "112" in res.text

    async def test_driver_sos_rejected_for_passenger(self, client: AsyncClient):
        user = await _create_test_user(client, "pass_sos")
        res = await client.post("/safety/driver/sos", headers=user["headers"], json={})
        # Should be forbidden for non-drivers
        assert res.status_code in [403, 401]

    async def test_driver_sos_for_driver(self, client: AsyncClient):
        driver = await _create_test_user(client, "drv_sos", role="driver")
        res = await client.post("/safety/driver/sos", headers=driver["headers"], json={"note": "Driver emergency"})
        assert res.status_code in [200, 201]
        data = res.json()
        assert data.get("emergency_services_contacted") is False

    async def test_report_safety_concern(self, client: AsyncClient):
        user = await _create_test_user(client, "concern_user")
        payload = {
            "event_type": "USER_REPORTED_CONCERN",
            "severity": "HIGH",
            "description": "Passenger observed suspicious activity"
        }
        res = await client.post("/safety/events", headers=user["headers"], json=payload)
        assert res.status_code in [200, 201]
        data = res.json()
        assert data["event_type"] == "USER_REPORTED_CONCERN"
        assert data["status"] in ["OPEN", "ACTIVE"]

    async def test_get_active_safety_events(self, client: AsyncClient):
        user = await _create_test_user(client, "active_ev_user")
        # Report concern
        await client.post("/safety/events", headers=user["headers"], json={
            "event_type": "USER_REPORTED_CONCERN",
            "severity": "MEDIUM",
            "description": "Minor issue"
        })
        res = await client.get("/safety/active", headers=user["headers"])
        assert res.status_code == 200
        events = res.json()
        assert isinstance(events, list)
        assert len(events) >= 1

    async def test_acknowledge_and_resolve_safety_event(self, client: AsyncClient):
        user = await _create_test_user(client, "ack_user")
        # Create event
        ev_res = await client.post("/safety/events", headers=user["headers"], json={
            "event_type": "USER_REPORTED_CONCERN",
            "severity": "LOW",
            "description": "To be acknowledged"
        })
        event_id = ev_res.json()["id"]

        # Acknowledge
        ack_res = await client.post(f"/safety/events/{event_id}/acknowledge", headers=user["headers"])
        assert ack_res.status_code == 200
        assert ack_res.json()["status"] == "ACKNOWLEDGED"

        # Resolve
        res_res = await client.post(f"/safety/events/{event_id}/resolve", headers=user["headers"])
        assert res_res.status_code == 200
        assert res_res.json()["status"] == "RESOLVED"

    async def test_trusted_contacts_flow(self, client: AsyncClient):
        user = await _create_test_user(client, "tc_flow_user")
        # 1. Create contact
        create_res = await client.post("/safety/trusted-contacts", headers=user["headers"], json={
            "name": "Sister",
            "phone": "+91 98765 43210",
            "relationship": "Sibling"
        })
        assert create_res.status_code in [200, 201]
        contact_id = create_res.json()["id"]

        # 2. List contacts
        list_res = await client.get("/safety/trusted-contacts", headers=user["headers"])
        assert list_res.status_code == 200
        contacts = list_res.json()
        assert any(c["id"] == contact_id for c in contacts)

        # 3. Delete contact
        del_res = await client.delete(f"/safety/trusted-contacts/{contact_id}", headers=user["headers"])
        assert del_res.status_code in [200, 204]

    async def test_trusted_contact_invalid_phone_rejected(self, client: AsyncClient):
        user = await _create_test_user(client, "tc_invalid")
        res = await client.post("/safety/trusted-contacts", headers=user["headers"], json={
            "name": "Bad Phone",
            "phone": "invalid-letters",
            "relationship": "Friend"
        })
        assert res.status_code == 422

    async def test_admin_safety_events_and_metrics(self, client: AsyncClient):
        class MockAdmin:
            id = 1
            role = "admin"
            name = "Safety Admin"
            email = "admin@safetest.com"
            is_active = True

        from app.main import app
        from app.routers.user import get_current_user

        app.dependency_overrides[get_current_user] = lambda: MockAdmin()
        try:
            m_res = await client.get("/safety/admin/metrics")
            assert m_res.status_code == 200

            e_res = await client.get("/safety/admin/events")
            assert e_res.status_code == 200
        finally:
            app.dependency_overrides.pop(get_current_user, None)


# ─── 3. AI Safety Tools Direct Execution Tests (3 tests) ────────────────────

@pytest.mark.asyncio
class TestAISafetyToolsExecution:

    async def test_get_safety_center_tool(self, db_session):
        user = User(id=999, name="AI Safety User", email="ai_safety@test.com", phone="9999999999", password_hash="", role="passenger")
        res = await execute_tool("get_safety_center_tool", {}, user, db_session)
        assert res.get("success") is True
        assert "has_active_ride" in res
        assert "safety_status" in res

    async def test_trigger_sos_tool_honesty(self, db_session):
        user = User(id=998, name="SOS AI User", email="ai_sos@test.com", phone="9888888888", password_hash="", role="passenger")
        res = await execute_tool("trigger_sos_tool", {"trigger_type": "AI_TEST_SOS"}, user, db_session)
        assert res.get("success") is True
        # Verify emergency services was not falsely reported as contacted
        assert res.get("emergency_services_contacted") is False
        assert "disclaimer" in res

    async def test_create_safety_event_tool(self, db_session):
        user = User(id=997, name="Concern AI User", email="ai_concern@test.com", phone="9777777777", password_hash="", role="passenger")
        res = await execute_tool("create_safety_event_tool", {
            "event_type": "USER_REPORTED_CONCERN",
            "severity": "HIGH",
            "description": "AI reported concern"
        }, user, db_session)
        assert res.get("success") is True
        assert res.get("event_type") == "USER_REPORTED_CONCERN"
