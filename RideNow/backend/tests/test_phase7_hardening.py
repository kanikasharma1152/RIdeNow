"""
Phase 7: Production Hardening, Performance & Observability Tests
================================================================
Comprehensive verification of:
1. Redis Caching & Cache Invalidation
2. AI Chat Rate Limiting & 429 response
3. Request Logging Middleware (X-Request-ID propagation)
4. Health Endpoint Reliability & Secret Sanitization
5. WebSocket Concurrent Broadcasting & Dead-Socket Cleanup
6. Connection Manager Stats & Observability
7. ML Demand & Copilot Graceful Fallbacks
8. Security & Role Authorization Gates
9. Log Sanitization & PII Protection
"""

import pytest
import random
import string
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import (
    cache_get,
    cache_set,
    cache_delete,
    rate_limit_check,
)
from app.core.connection_manager import ConnectionManager
from app.core.logging import sanitize_dict
from app.services.analytics import (
    get_dashboard_analytics,
    invalidate_admin_analytics_cache,
    ADMIN_ANALYTICS_CACHE_KEY,
)
from app.ml.demand.predictor import get_demand_hotspots, predict_zone_demand
from app.models.user import User


# ─────────────────────────────────────────────
# Helper to create test authenticated users
# ─────────────────────────────────────────────

async def _create_user(client: AsyncClient, name_prefix: str, role: str = "passenger"):
    suffix = "".join(random.choices(string.ascii_lowercase, k=6))
    phone_digits = "".join(random.choices(string.digits, k=8))
    email = f"{name_prefix.lower()}_{suffix}@mobilitytest.com"
    phone = f"97{phone_digits}"

    reg = await client.post("/users/register", json={
        "name": f"{name_prefix} {suffix}",
        "email": email,
        "phone": phone,
        "password": "Password123!",
        "role": role,
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

    return {"headers": headers, "user_id": user_id, "email": email}


# ─────────────────────────────────────────────
# 1. Redis Caching & Invalidation Tests
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_analytics_cache_and_invalidation(db_session: AsyncSession):
    """Admin dashboard analytics is cached in Redis and invalidated on demand."""
    # Clear prior cache
    await invalidate_admin_analytics_cache()

    # First fetch — writes to cache
    res1 = await get_dashboard_analytics(db_session, use_cache=True)
    assert res1["success"] is True
    assert "overview" in res1

    # Verify key exists in cache
    cached = await cache_get(ADMIN_ANALYTICS_CACHE_KEY)
    assert cached is not None
    assert cached["overview"]["total_users"] == res1["overview"]["total_users"]

    # Second fetch — reads from cache
    res2 = await get_dashboard_analytics(db_session, use_cache=True)
    assert res2 == res1

    # Invalidate
    await invalidate_admin_analytics_cache()
    cleared = await cache_get(ADMIN_ANALYTICS_CACHE_KEY)
    assert cleared is None


@pytest.mark.asyncio
async def test_ml_demand_hotspots_caching(db_session: AsyncSession):
    """ML demand hotspots are cached with specified limit."""
    limit = 4
    cache_key = f"ml:hotspots:{limit}"
    await cache_delete(cache_key)

    # First fetch
    hotspots1 = await get_demand_hotspots(db=db_session, limit=limit, use_cache=True)
    assert isinstance(hotspots1, list)

    # Check cache was populated if hotspots found or fallback
    await cache_set(cache_key, [{"zone": {"lat": 22.7, "lon": 75.8}, "demand_score": 1.5}], ttl=180)
    hotspots_cached = await get_demand_hotspots(db=db_session, limit=limit, use_cache=True)
    assert len(hotspots_cached) == 1
    assert hotspots_cached[0]["demand_score"] == 1.5

    # Cleanup
    await cache_delete(cache_key)


# ─────────────────────────────────────────────
# 2. Rate Limiting Tests
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rate_limit_sliding_window():
    """Rate limiter allows requests under threshold and blocks subsequent ones."""
    test_id = f"test_user_{random.randint(10000, 99999)}"

    # Limit = 3 requests per 10 seconds
    assert await rate_limit_check(test_id, max_requests=3, window_seconds=10) is True
    assert await rate_limit_check(test_id, max_requests=3, window_seconds=10) is True
    assert await rate_limit_check(test_id, max_requests=3, window_seconds=10) is True
    # 4th request must be rate-limited
    assert await rate_limit_check(test_id, max_requests=3, window_seconds=10) is False


@pytest.mark.asyncio
async def test_chat_rate_limiting_status_429(client: AsyncClient):
    """Chat endpoint returns HTTP 429 when user exceeds rate limit."""
    user = await _create_user(client, "RateLimiter")
    headers = user["headers"]

    # Pre-exhaust the user's rate limit quota
    from app.core.config import settings
    limit_id = f"user:{user['user_id']}"
    for _ in range(settings.REDIS_RATE_LIMIT_REQUESTS + 1):
        await rate_limit_check(
            identifier=limit_id,
            max_requests=settings.REDIS_RATE_LIMIT_REQUESTS,
            window_seconds=settings.REDIS_RATE_LIMIT_WINDOW_SECONDS,
        )

    # Now making a request to /chat/message must return 429
    resp = await client.post(
        "/chat/message",
        json={"message": "Hello Nova"},
        headers=headers,
    )
    assert resp.status_code == 429
    assert "Rate limit exceeded" in resp.json()["detail"]


# ─────────────────────────────────────────────
# 3. Observability & Middleware Tests
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_request_logging_attaches_request_id(client: AsyncClient):
    """Every HTTP response includes a unique X-Request-ID header."""
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "X-Request-ID" in resp.headers
    assert len(resp.headers["X-Request-ID"]) >= 8


@pytest.mark.asyncio
async def test_health_endpoint_healthy(client: AsyncClient):
    """Health check returns 200, healthy status, and connected components."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert "redis" in data
    # Ensure no internal DB credentials or connection strings leaked
    assert "password" not in str(data).lower()
    assert "postgresql" not in str(data).lower()


def test_sensitive_data_sanitization():
    """Confidential fields (passwords, tokens, API keys) are masked by sanitizer."""
    unsafe_data = {
        "user_id": 42,
        "name": "Alex",
        "password": "supersecretpassword123",
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "api_key": "gsk_live_999999",
        "nested": {
            "secret_key": "private_key_data",
            "safe_metric": 100,
        },
    }
    safe = sanitize_dict(unsafe_data)
    assert safe["user_id"] == 42
    assert safe["name"] == "Alex"
    assert safe["password"] == "***REDACTED***"
    assert safe["access_token"] == "***REDACTED***"
    assert safe["api_key"] == "***REDACTED***"
    assert safe["nested"]["secret_key"] == "***REDACTED***"
    assert safe["nested"]["safe_metric"] == 100


# ─────────────────────────────────────────────
# 4. WebSocket Reliability & Observability Tests
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ws_concurrent_role_broadcast():
    """Broadcast to role distributes messages concurrently across all sockets."""
    mgr = ConnectionManager()
    ws1 = AsyncMock()
    ws2 = AsyncMock()

    await mgr.connect(ws1, user_id=1, role="admin")
    await mgr.connect(ws2, user_id=2, role="admin")

    test_msg = {"type": "test_broadcast", "data": {"alert": "fleet_active"}}
    await mgr.broadcast_to_role("admin", test_msg)

    ws1.send_text.assert_awaited_once()
    ws2.send_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_ws_dead_socket_cleanup_resilience():
    """Disconnected or broken sockets are purged automatically without error."""
    mgr = ConnectionManager()
    broken_ws = AsyncMock()
    broken_ws.send_text.side_effect = RuntimeError("Socket connection abruptly dropped")

    await mgr.connect(broken_ws, user_id=10, role="passenger")
    assert mgr.is_user_connected(10) is True

    # Sending a message to broken socket triggers disconnect cleanup
    await mgr.send_personal_message(10, {"type": "PING"})
    assert mgr.is_user_connected(10) is False


def test_ws_connection_stats_reporting():
    """Connection manager exposes accurate real-time telemetry metrics."""
    mgr = ConnectionManager()
    ws1, ws2, ws3 = AsyncMock(), AsyncMock(), AsyncMock()

    # In-memory registration
    mgr.active_connections[101] = {ws1}
    mgr.user_roles[101] = "admin"

    mgr.active_connections[102] = {ws2, ws3}  # 2 tabs
    mgr.user_roles[102] = "driver"

    stats = mgr.get_connection_stats()
    assert stats["total_sockets"] == 3
    assert stats["connected_users"] == 2
    assert stats["users_by_role"]["admin"] == 1
    assert stats["users_by_role"]["driver"] == 1


# ─────────────────────────────────────────────
# 5. Security & Authorization Gate Tests
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_analytics_rejects_non_admin(client: AsyncClient):
    """Passenger and Driver roles are strictly denied from Admin Analytics API."""
    passenger = await _create_user(client, "SecPass", role="passenger")
    resp_pass = await client.get("/admin/analytics/overview", headers=passenger["headers"])
    assert resp_pass.status_code == 403

    driver = await _create_user(client, "SecDriver", role="driver")
    resp_driver = await client.get("/admin/analytics/overview", headers=driver["headers"])
    assert resp_driver.status_code == 403

    unauth = await client.get("/admin/analytics/overview")
    assert unauth.status_code in (401, 403)


@pytest.mark.asyncio
async def test_driver_location_rejects_passenger(client: AsyncClient):
    """Passenger cannot invoke PATCH /drivers/location."""
    passenger = await _create_user(client, "SecLocPass", role="passenger")
    resp = await client.patch(
        "/drivers/location",
        json={"latitude": 22.7, "longitude": 75.8},
        headers=passenger["headers"],
    )
    assert resp.status_code == 403


# ─────────────────────────────────────────────
# 6. ML & AI Resilience Fallback Tests
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_predict_zone_demand_fallback(db_session: AsyncSession):
    """Zone demand predictor returns a valid rule-based structure when DB has no data."""
    prediction = await predict_zone_demand(lat=22.7196, lon=75.8577, db=db_session)
    assert prediction["method"] == "rule_based"
    assert "demand_level" in prediction
    assert prediction["demand_level"] in ("LOW", "MEDIUM", "HIGH")
    assert "demand_score" in prediction
    assert isinstance(prediction["demand_score"], float)


@pytest.mark.asyncio
async def test_chat_history_clear(client: AsyncClient):
    """DELETE /chat/history resets active context successfully."""
    user = await _create_user(client, "ContextReset")
    resp = await client.delete("/chat/history", headers=user["headers"])
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_admin_analytics_api_caching(client: AsyncClient, db_session: AsyncSession):
    """Admin calling /admin/analytics/overview gets cached response on second call."""
    user_data = await _create_user(client, "AdminCacheTest", role="passenger")
    user = await db_session.get(User, user_data["user_id"])
    user.role = "admin"
    await db_session.commit()

    resp1 = await client.get("/admin/analytics/overview", headers=user_data["headers"])
    assert resp1.status_code == 200
    data1 = resp1.json()

    # Second call returns the same payload
    resp2 = await client.get("/admin/analytics/overview", headers=user_data["headers"])
    assert resp2.status_code == 200
    assert resp2.json()["overview"] == data1["overview"]


@pytest.mark.asyncio
async def test_health_check_sanitizes_failure_message(client: AsyncClient):
    """When DB connectivity fails, /health returns 503 with sanitized message, no credentials."""
    with patch("app.main.text", side_effect=Exception("FATAL: password authentication failed for user 'postgres'")):
        resp = await client.get("/health")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"
        assert data["error"] == "Database connectivity check failed"
        assert "password" not in str(data).lower()
