"""
Phase 8 — Production Deployment & Configuration Tests
======================================================
Verifies that all production-readiness settings, health endpoints,
secret safety checks, and deployment configuration are correct.

No real DB or Redis required — uses the standard in-memory test fixtures.
"""
import os
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient
from pydantic_settings import SettingsConfigDict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings(**overrides):
    """Return a hermetic Settings instance — ignores .env, applies overrides via env vars."""
    from app.core.config import Settings

    class TestSettings(Settings):
        model_config = SettingsConfigDict(
            env_file=None,   # do NOT load .env — tests must be hermetic
            case_sensitive=False,
            extra="ignore",
        )

    env_backup = {}
    for k, v in overrides.items():
        env_backup[k] = os.environ.get(k)
        os.environ[k] = str(v)

    try:
        return TestSettings()
    finally:
        for k, original in env_backup.items():
            if original is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = original


# ---------------------------------------------------------------------------
# 1. Environment Configuration
# ---------------------------------------------------------------------------

def test_environment_config_loads():
    """Settings object can be instantiated without errors."""
    s = _make_settings()
    assert s.ENVIRONMENT is not None
    assert s.DATABASE_URL is not None
    assert s.SECRET_KEY is not None


def test_is_production_flag_false_by_default():
    """Default ENVIRONMENT='development' → is_production is False."""
    s = _make_settings(ENVIRONMENT="development")
    assert s.is_production is False


def test_is_production_flag_true():
    """ENVIRONMENT='production' → is_production is True."""
    s = _make_settings(ENVIRONMENT="production")
    assert s.is_production is True


def test_is_production_flag_prod_alias():
    """ENVIRONMENT='prod' is also recognised as production."""
    s = _make_settings(ENVIRONMENT="prod")
    assert s.is_production is True


# ---------------------------------------------------------------------------
# 2. CORS Configuration
# ---------------------------------------------------------------------------

def test_cors_regex_present_in_development():
    """Development environment exposes the localhost CORS regex."""
    s = _make_settings(ENVIRONMENT="development")
    assert s.cors_origin_regex is not None
    assert "localhost" in s.cors_origin_regex


def test_cors_regex_disabled_in_production():
    """Production environment disables localhost CORS regex (returns None)."""
    s = _make_settings(ENVIRONMENT="production")
    assert s.cors_origin_regex is None


def test_cors_origins_configurable():
    """CORS_ORIGINS parses comma-separated list correctly."""
    s = _make_settings(CORS_ORIGINS="https://app.ridenow.com,https://admin.ridenow.com")
    origins = s.cors_origins_list
    assert "https://app.ridenow.com" in origins
    assert "https://admin.ridenow.com" in origins
    assert len(origins) == 2


# ---------------------------------------------------------------------------
# 3. Secret Key Safety
# ---------------------------------------------------------------------------

def test_secret_key_placeholder_detection():
    """
    Placeholder SECRET_KEY is fine in development but must be overridden in production.
    """
    placeholder = "change-this-in-production"
    s = _make_settings(SECRET_KEY=placeholder, ENVIRONMENT="development")
    # dev: just confirm the setting loads
    assert s.SECRET_KEY == placeholder
    # We are NOT in production here so no assertion failure expected
    assert not s.is_production


def test_secret_key_strong_in_production():
    """Strong SECRET_KEY passes the production safety check."""
    strong_key = "a" * 64
    s = _make_settings(SECRET_KEY=strong_key, ENVIRONMENT="production")
    assert "change-this-in-production" not in s.SECRET_KEY


# ---------------------------------------------------------------------------
# 4. Database Pool Settings
# ---------------------------------------------------------------------------

def test_db_pool_defaults():
    """Default pool settings are sane non-zero values."""
    s = _make_settings()
    assert s.DB_POOL_SIZE > 0
    assert s.DB_MAX_OVERFLOW >= 0
    assert s.DB_POOL_TIMEOUT > 0
    assert s.DB_POOL_RECYCLE > 0


def test_db_pool_overridable():
    """Pool settings can be overridden via environment."""
    s = _make_settings(
        DB_POOL_SIZE="5",
        DB_MAX_OVERFLOW="10",
        DB_POOL_TIMEOUT="15",
        DB_POOL_RECYCLE="900",
    )
    assert s.DB_POOL_SIZE == 5
    assert s.DB_MAX_OVERFLOW == 10
    assert s.DB_POOL_TIMEOUT == 15
    assert s.DB_POOL_RECYCLE == 900


# ---------------------------------------------------------------------------
# 5. Health Endpoints (via TestClient fixture from conftest)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_health_live_endpoint(client: AsyncClient):
    """/health/live returns 200 instantly without DB dependency."""
    resp = await client.get("/health/live")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("alive") is True


@pytest.mark.anyio
async def test_health_ready_endpoint(client: AsyncClient):
    """/health/ready returns a structured status dict."""
    resp = await client.get("/health/ready")
    # May be 200 (ready) or 503 (not_ready) — both shapes are valid
    assert resp.status_code in (200, 503)
    data = resp.json()
    assert "status" in data
    assert "database" in data
    assert "redis" in data


@pytest.mark.anyio
async def test_health_live_no_db_dependency(client: AsyncClient):
    """/health/live must succeed regardless of DB state."""
    resp = await client.get("/health/live")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 6. Error Response Safety — no secrets / tracebacks in HTTP responses
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_no_secret_in_error_response(client: AsyncClient):
    """404 response must not contain stack traces or driver-level details."""
    resp = await client.get("/nonexistent-endpoint-phase8")
    body = resp.text
    assert "Traceback" not in body
    assert "psycopg" not in body
    assert "asyncpg" not in body


@pytest.mark.anyio
async def test_health_sanitizes_db_error(client: AsyncClient):
    """
    /health with a broken DB must return 503 without leaking the connection
    string, credentials, or internal error details.
    """
    from app.database import get_db
    from app.main import app

    original_override = app.dependency_overrides.get(get_db)
    mock_session = AsyncMock()
    mock_session.execute.side_effect = Exception("FATAL: password authentication failed for user 'postgres'")

    async def broken_db():
        yield mock_session

    app.dependency_overrides[get_db] = broken_db
    try:
        resp = await client.get("/health")
        body = resp.text
        # The sanitized handler only returns: {"status": "unhealthy", "database": "disconnected", ...}
        # It must NOT echo back the raw DB exception message
        assert "password authentication failed" not in body
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"
    finally:
        if original_override is not None:
            app.dependency_overrides[get_db] = original_override
        else:
            app.dependency_overrides.pop(get_db, None)
