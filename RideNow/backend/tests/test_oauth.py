import pytest
from unittest.mock import patch
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_oauth_config_endpoint(client: AsyncClient):
    """Test public Google OAuth config endpoint returns valid JSON."""
    response = await client.get("/users/oauth/google/config")
    assert response.status_code == 200
    data = response.json()
    assert "configured" in data
    assert "client_id" in data


@pytest.mark.asyncio
async def test_oauth_login_invalid_token(client: AsyncClient):
    """Calling oauth login with invalid/fake token returns 401."""
    response = await client.post(
        "/users/oauth/google",
        json={"credential": "invalid.fake.token", "role": "passenger"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_oauth_login_flow_with_mocked_google_token(client: AsyncClient):
    """Test full end-to-end OAuth flow with mocked tokeninfo validation."""
    mock_claims = {
        "sub": "google_test_sub_123456789",
        "email": "test_oauth_passenger@example.com",
        "name": "Test Google Passenger",
        "picture": "https://example.com/avatar.png",
        "aud": "mock_client_id",
    }

    with patch("app.services.oauth.verify_google_credential", return_value=mock_claims):
        # 1. First login creates the account
        res = await client.post(
            "/users/oauth/google",
            json={"credential": "valid.mock.token", "role": "passenger"},
        )
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "test_oauth_passenger@example.com"
        assert data["user"]["role"] == "passenger"
        token = data["access_token"]

        # 2. Verify issued JWT works on authenticated endpoint /users/me
        me_res = await client.get(
            "/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_res.status_code == 200
        assert me_res.json()["email"] == "test_oauth_passenger@example.com"

        # 3. Second login with same credential re-uses account without duplicate key error
        res2 = await client.post(
            "/users/oauth/google",
            json={"credential": "valid.mock.token", "role": "passenger"},
        )
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["user"]["id"] == data["user"]["id"]
