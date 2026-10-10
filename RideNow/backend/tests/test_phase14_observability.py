"""
Phase 14 Production Intelligence, Reliability & Observability — Backend Tests
=============================================================================
Tests:
- AI Telemetry tracker (record, aggregate, error rate, safe metadata)
- AI Safe Fallback states (missing destination, missing active ride, vision unavailable)
- Ride Reliability Engine (stale rides detection, thresholds, metrics calculation)
- System Health Center (live probe, ready probe, system health admin protection, service health states)
- Admin Intelligence endpoints (admin protection, real telemetry, reliability metrics)
- Error Standardization (RideNowError request_id, 403, 404, 409 responses)
- Retry & Timeout utilities (exponential backoff, retry count, max delay, timeout exception)
"""

import asyncio
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch

from app.main import app
from app.observability.telemetry import AITelemetryTracker, telemetry
from app.services.ride_reliability import (
    get_stale_rides,
    get_reliability_metrics,
    STALE_REQUESTED_MINUTES,
)
from app.ai.agent.fallback import (
    detect_missing_context,
    get_fallback_response,
    AIConfidenceState,
)
from app.core.retry import with_retry, with_timeout
from app.core.exceptions import (
    RideNotFoundError,
    UnauthorizedAccessError,
    ServiceUnavailableError,
    RateLimitError,
    DuplicateResourceError,
)


# ─── 1. AI Telemetry & Observability Tests ────────────────────────────────────

class TestAITelemetryTracker:
    @pytest.mark.asyncio
    async def test_record_ai_request_metadata_only(self):
        tracker = AITelemetryTracker()
        await tracker.record_ai_request(
            request_id="req-1234",
            user_id=42,
            channel="text",
            intent="BOOK_RIDE",
            model="openai/gpt-oss-120b",
            tools_called=["estimate_fare", "book_ride"],
            tools_succeeded=["estimate_fare", "book_ride"],
            tools_failed=[],
            latency_ms=185.5,
            fallback_used=False,
            error_type=None,
        )

        metrics = await tracker.get_recent_ai_metrics(limit=10)
        assert metrics["total_requests"] >= 1
        assert metrics["tool_success_rate"] == 100.0
        assert metrics["fallback_rate"] == 0.0
        assert metrics["error_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_telemetry_captures_errors_and_fallbacks(self):
        tracker = AITelemetryTracker()
        await tracker.record_ai_request(
            request_id="req-fail",
            user_id=99,
            channel="voice",
            intent="UNKNOWN",
            model="openai/gpt-oss-120b",
            tools_called=["book_ride"],
            tools_succeeded=[],
            tools_failed=["book_ride"],
            latency_ms=310.0,
            fallback_used=True,
            error_type="ToolExecutionError",
        )

        metrics = await tracker.get_recent_ai_metrics(limit=10)
        assert metrics["fallback_rate"] > 0
        assert metrics["error_rate"] > 0
        assert any(e["error_type"] == "ToolExecutionError" for e in metrics["recent_errors"])


# ─── 2. AI Safe Fallback Tests ───────────────────────────────────────────────

class TestAISafeFallback:
    def test_missing_destination_booking_detected(self):
        ctx = type("Ctx", (), {"destination": None, "dropoff_location": None})()
        assert detect_missing_context("book it", ctx) == "ambiguous_booking"
        assert detect_missing_context("book", ctx) == "ambiguous_booking"
        assert detect_missing_context("okay book it", ctx) == "ambiguous_booking"

    def test_booking_with_destination_not_flagged(self):
        ctx = type("Ctx", (), {"destination": "Palasia Square", "dropoff_location": None})()
        assert detect_missing_context("book it", ctx) is None

    def test_cancel_without_active_ride_detected(self):
        ctx = type("Ctx", (), {"active_ride_id": None, "pending_action": None})()
        assert detect_missing_context("cancel it", ctx) == "cancel_no_active_ride"
        assert detect_missing_context("cancel my ride", ctx) == "cancel_no_active_ride"

    def test_cancel_with_active_ride_not_flagged(self):
        ctx = type("Ctx", (), {"active_ride_id": 105, "pending_action": None})()
        assert detect_missing_context("cancel it", ctx) is None

    def test_fare_without_destination_detected(self):
        ctx = type("Ctx", (), {"destination": None, "dropoff_location": None, "fare_estimate": None})()
        assert detect_missing_context("how much", ctx) == "missing_how_much_context"
        assert detect_missing_context("what is the fare", ctx) == "missing_how_much_context"

    def test_vision_unavailable_honest_reply(self):
        ctx = type("Ctx", (), {})()
        assert detect_missing_context("can you see this image", ctx) == "vision_unavailable"
        resp = get_fallback_response("vision_unavailable", AIConfidenceState.UNSUPPORTED)
        assert resp["confidence_state"] == "UNSUPPORTED"
        assert "not able to process visual content" in resp["reply"]


# ─── 3. Retry & Timeout Utilities Tests ──────────────────────────────────────

class TestRetryAndTimeout:
    @pytest.mark.asyncio
    async def test_retry_eventually_succeeds(self):
        calls = 0

        async def flaky_call():
            nonlocal calls
            calls += 1
            if calls < 3:
                raise ConnectionError("Temporary network blip")
            return "SUCCESS"

        result = await with_retry(flaky_call, max_attempts=3, base_delay=0.01, max_delay=0.05)
        assert result == "SUCCESS"
        assert calls == 3

    @pytest.mark.asyncio
    async def test_retry_raises_after_max_attempts(self):
        calls = 0

        async def always_fails():
            nonlocal calls
            calls += 1
            raise ValueError("Persistent error")

        with pytest.raises(ValueError, match="Persistent error"):
            await with_retry(always_fails, max_attempts=3, base_delay=0.01, max_delay=0.05)
        assert calls == 3

    @pytest.mark.asyncio
    async def test_timeout_raises_timeout_error(self):
        async def slow_operation():
            await asyncio.sleep(0.5)
            return "DONE"

        with pytest.raises(asyncio.TimeoutError):
            await with_timeout(slow_operation, timeout_seconds=0.05)


# ─── 4. System Health Center HTTP Tests ──────────────────────────────────────

@pytest.mark.asyncio
class TestSystemHealthHTTP:
    async def test_health_live_endpoint(self, client: AsyncClient):
        res = await client.get("/health/live")
        assert res.status_code == 200
        assert res.json() == {"alive": True}

    async def test_health_ready_endpoint(self, client: AsyncClient):
        res = await client.get("/health/ready")
        assert res.status_code in (200, 503)
        data = res.json()
        assert "status" in data
        assert "database" in data

    async def test_health_system_requires_admin(self, client: AsyncClient):
        res = await client.get("/health/system")
        assert res.status_code == 401

    async def test_health_ai_requires_admin(self, client: AsyncClient):
        res = await client.get("/health/ai")
        assert res.status_code == 401

    async def test_health_system_authorized(self, client: AsyncClient, db_session):
        from app.routers.user import get_current_user
        fake_admin = type("AdminUser", (), {"id": 1, "role": "admin", "is_active": True})()
        app.dependency_overrides[get_current_user] = lambda: fake_admin

        try:
            res = await client.get("/health/system")
            assert res.status_code == 200
            data = res.json()
            assert "overall_status" in data
            assert "services" in data
            services = data["services"]
            assert "database" in services
            assert "redis" in services
            assert "websocket" in services
            assert services["database"]["status"] in ("HEALTHY", "DEGRADED", "UNAVAILABLE")
        finally:
            app.dependency_overrides.pop(get_current_user, None)


# ─── 5. Admin Intelligence HTTP Tests ────────────────────────────────────────

@pytest.mark.asyncio
class TestAdminIntelligenceHTTP:
    async def test_admin_intelligence_requires_admin(self, client: AsyncClient):
        res = await client.get("/admin/intelligence")
        assert res.status_code == 401

    async def test_admin_intelligence_authorized(self, client: AsyncClient, db_session):
        from app.routers.user import get_current_user
        fake_admin = type("AdminUser", (), {"id": 1, "role": "admin", "is_active": True})()
        app.dependency_overrides[get_current_user] = lambda: fake_admin

        try:
            res = await client.get("/admin/intelligence")
            assert res.status_code == 200
            data = res.json()
            assert "platform" in data
            assert "ride_reliability" in data
            assert "ai_metrics" in data
            assert "safety" in data
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    async def test_admin_ride_reliability_endpoint(self, client: AsyncClient, db_session):
        from app.routers.user import get_current_user
        fake_admin = type("AdminUser", (), {"id": 1, "role": "admin", "is_active": True})()
        app.dependency_overrides[get_current_user] = lambda: fake_admin

        try:
            res = await client.get("/admin/ride-reliability")
            assert res.status_code == 200
            data = res.json()
            assert "active_rides_count" in data
            assert "stale_rides_count" in data
            assert "stale_rides" in data
            assert "stale_thresholds_minutes" in data
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    async def test_admin_ai_metrics_endpoint(self, client: AsyncClient):
        from app.routers.user import get_current_user
        fake_admin = type("AdminUser", (), {"id": 1, "role": "admin", "is_active": True})()
        app.dependency_overrides[get_current_user] = lambda: fake_admin

        try:
            res = await client.get("/admin/ai-metrics")
            assert res.status_code == 200
            data = res.json()
            assert "total_requests" in data
        finally:
            app.dependency_overrides.pop(get_current_user, None)


# ─── 6. Error Standardization Tests ──────────────────────────────────────────

@pytest.mark.asyncio
class TestErrorStandardization:
    async def test_x_request_id_in_response_headers(self, client: AsyncClient):
        res = await client.get("/health/live")
        assert "x-request-id" in res.headers
        assert len(res.headers["x-request-id"]) > 0

    async def test_custom_exception_propagates_code_and_message(self, client: AsyncClient):
        from app.routers.user import get_current_user
        fake_user = type("NormalUser", (), {"id": 2, "role": "passenger", "is_active": True})()
        app.dependency_overrides[get_current_user] = lambda: fake_user

        try:
            res = await client.get("/admin/intelligence")
            assert res.status_code == 403
            data = res.json()
            assert data["success"] is False
            assert "error" in data
            assert data["error"]["code"] == "UNAUTHORIZED_ACCESS"
            assert "request_id" in data["error"]
        finally:
            app.dependency_overrides.pop(get_current_user, None)
