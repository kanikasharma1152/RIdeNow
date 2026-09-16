import pytest
from httpx import AsyncClient
from starlette.testclient import TestClient

from app.main import app
from app.routers.user import get_current_user


class MockUser:
    id = 1
    name = "Test Passenger"
    email = "test@example.com"
    role = "passenger"
    is_active = True


def test_chat_unauthenticated():
    # Remove overrides for unauthenticated test
    app.dependency_overrides.pop(get_current_user, None)
    client = TestClient(app)
    response = client.post("/chat/message", json={"message": "What is my ride status?"})
    assert response.status_code == 401


def test_chat_estimate_fare_query():
    app.dependency_overrides[get_current_user] = lambda: MockUser()
    client = TestClient(app)

    response = client.post(
        "/chat/message",
        json={"message": "How much for 15 km?"},
        headers={"Authorization": "Bearer fake-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert "15" in data["reply"]
    # Verify tool was called
    tools = data.get("tools_executed", [])
    assert any(t["tool"] == "estimate_fare" for t in tools)


def test_chat_cancellation_policy_rag():
    app.dependency_overrides[get_current_user] = lambda: MockUser()
    client = TestClient(app)

    response = client.post(
        "/chat/message",
        json={"message": "What is the cancellation policy?"},
        headers={"Authorization": "Bearer fake-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    tools = data.get("tools_executed", [])
    assert any(t["tool"] == "search_policies_and_faq" for t in tools)


def test_chat_clear_history():
    app.dependency_overrides[get_current_user] = lambda: MockUser()
    client = TestClient(app)

    response = client.delete(
        "/chat/history",
        headers={"Authorization": "Bearer fake-token"},
    )
    assert response.status_code == 200
    assert response.json()["success"] is True

    # Clean up overrides
    app.dependency_overrides.pop(get_current_user, None)

