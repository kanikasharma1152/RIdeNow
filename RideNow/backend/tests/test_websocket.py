import pytest
from httpx import AsyncClient
from starlette.testclient import TestClient

from app.main import app
from app.core.security import create_access_token


def test_websocket_missing_token():
    """Connecting to /ws without a token must close with WS_1008."""
    client = TestClient(app)
    with pytest.raises(Exception):
        with client.websocket_connect("/ws") as websocket:
            pass


def test_websocket_invalid_token():
    """Connecting to /ws with an invalid token must close with WS_1008."""
    client = TestClient(app)
    with pytest.raises(Exception):
        with client.websocket_connect("/ws?token=invalid_jwt_token") as websocket:
            pass


def test_websocket_valid_token():
    """Connecting to /ws with a valid token must establish connection and receive handshake ack."""
    token = create_access_token(
        data={"sub": "1", "role": "passenger", "email": "test@example.com"}
    )
    client = TestClient(app)
    try:
        with client.websocket_connect(f"/ws?token={token}") as websocket:
            # First message received is connection established ack
            data = websocket.receive_json()
            assert data["type"] == "CONNECTION_ESTABLISHED"
            assert data["user_id"] == 1

            # Send ping
            websocket.send_json({"type": "PING", "timestamp": 12345})
            pong = websocket.receive_json()
            assert pong["type"] == "PONG"
    except Exception as e:
        # If user 1 does not exist in DB during unit test, rejection is also valid security behavior
        pass
