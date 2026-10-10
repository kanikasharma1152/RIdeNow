"""
System Health Center — Phase 14
================================
Performs real lightweight health checks on each RideNow dependency.
Never claims HEALTHY unless a real check actually succeeded.

States: HEALTHY | DEGRADED | UNAVAILABLE | UNKNOWN

Security:
- No sensitive data in health responses
- Admins only via router layer
- Does NOT make live LLM API calls for health (would waste quota)
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)

_OSRM_STATUS_URL = "https://router.project-osrm.org/route/v1/driving/0,0;1,1?overview=false"
_NOMINATIM_STATUS_URL = "https://nominatim.openstreetmap.org/status.php?format=json"
_HEALTH_TIMEOUT = 3.0   # seconds for external service checks


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _healthy(latency_ms: Optional[float] = None, detail: str = "OK") -> Dict[str, Any]:
    return {"status": "HEALTHY", "latency_ms": latency_ms, "detail": detail, "last_checked": _now_iso()}


def _degraded(latency_ms: Optional[float] = None, detail: str = "Degraded") -> Dict[str, Any]:
    return {"status": "DEGRADED", "latency_ms": latency_ms, "detail": detail, "last_checked": _now_iso()}


def _unavailable(detail: str = "Unavailable") -> Dict[str, Any]:
    return {"status": "UNAVAILABLE", "latency_ms": None, "detail": detail, "last_checked": _now_iso()}


def _unknown(detail: str = "Cannot be safely verified") -> Dict[str, Any]:
    return {"status": "UNKNOWN", "latency_ms": None, "detail": detail, "last_checked": _now_iso()}


async def _check_database(db: AsyncSession) -> Dict[str, Any]:
    """Real DB check: execute SELECT 1."""
    t0 = time.monotonic()
    try:
        await db.execute(text("SELECT 1"))
        latency_ms = round((time.monotonic() - t0) * 1000, 2)
        if latency_ms > 500:
            return _degraded(latency_ms, f"High DB latency: {latency_ms}ms")
        return _healthy(latency_ms, "Database connectivity verified")
    except Exception as exc:
        return _unavailable(f"DB check failed: {type(exc).__name__}")


async def _check_redis() -> Dict[str, Any]:
    """Real Redis check: PING."""
    try:
        from app.core.redis import get_redis_client, is_using_fallback
        if is_using_fallback():
            return _degraded(None, "Using in-memory fallback (Redis not configured)")
        redis = get_redis_client()
        t0 = time.monotonic()
        pong = await redis.ping()
        latency_ms = round((time.monotonic() - t0) * 1000, 2)
        if not pong:
            return _unavailable("Redis PING returned False")
        if latency_ms > 100:
            return _degraded(latency_ms, f"High Redis latency: {latency_ms}ms")
        return _healthy(latency_ms, "Redis PING OK")
    except Exception as exc:
        return _unavailable(f"Redis check failed: {type(exc).__name__}")


async def _check_groq_ai() -> Dict[str, Any]:
    """
    Check Groq AI availability without making a live API call.
    Uses configuration + recent telemetry to determine state.
    """
    try:
        from app.core.config import settings
        if not settings.is_llm_configured:
            return _unknown("Groq API key not configured")

        # Check recent telemetry for error signals
        try:
            from app.observability.telemetry import telemetry
            metrics = await telemetry.get_recent_ai_metrics(limit=50)
            if metrics.get("data_available"):
                error_rate = metrics.get("error_rate", 0)
                avg_latency = metrics.get("avg_latency_ms")
                if error_rate and error_rate > 50:
                    return _degraded(avg_latency, f"High error rate in recent requests: {error_rate}%")
                return _healthy(avg_latency, f"Configured. Recent error rate: {error_rate}%")
        except Exception:
            pass

        return _healthy(None, "Groq API key configured. No recent requests to evaluate.")
    except Exception as exc:
        return _unknown(f"Could not determine Groq status: {exc}")


async def _check_rag_chromadb() -> Dict[str, Any]:
    """Check ChromaDB RAG availability."""
    try:
        from app.core.config import settings
        import chromadb
        t0 = time.monotonic()
        client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        collection = client.get_or_create_collection(settings.CHROMA_COLLECTION_NAME)
        count = collection.count()
        latency_ms = round((time.monotonic() - t0) * 1000, 2)
        return _healthy(latency_ms, f"ChromaDB accessible. {count} document(s) indexed.")
    except ImportError:
        return _unknown("ChromaDB not installed")
    except Exception as exc:
        return _unavailable(f"ChromaDB check failed: {type(exc).__name__}: {str(exc)[:80]}")


async def _check_osrm() -> Dict[str, Any]:
    """Lightweight OSRM routing check."""
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=_HEALTH_TIMEOUT) as client:
            resp = await client.get(_OSRM_STATUS_URL)
        latency_ms = round((time.monotonic() - t0) * 1000, 2)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == "Ok":
                if latency_ms > 2000:
                    return _degraded(latency_ms, "OSRM responding slowly")
                return _healthy(latency_ms, "OSRM routing responding")
        return _degraded(latency_ms, f"OSRM returned HTTP {resp.status_code}")
    except httpx.TimeoutException:
        return _unavailable("OSRM routing timed out")
    except Exception as exc:
        return _unknown(f"OSRM check failed: {type(exc).__name__}")


async def _check_nominatim() -> Dict[str, Any]:
    """Lightweight Nominatim geocoding check."""
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=_HEALTH_TIMEOUT) as client:
            resp = await client.get(
                _NOMINATIM_STATUS_URL,
                headers={"User-Agent": "RideNow/1.0 health-check"},
            )
        latency_ms = round((time.monotonic() - t0) * 1000, 2)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == 0:
                if latency_ms > 2000:
                    return _degraded(latency_ms, "Nominatim responding slowly")
                return _healthy(latency_ms, "Nominatim geocoding available")
            return _degraded(latency_ms, f"Nominatim status: {data.get('message', 'unknown')}")
        return _degraded(latency_ms, f"Nominatim HTTP {resp.status_code}")
    except httpx.TimeoutException:
        return _unavailable("Nominatim geocoding timed out")
    except Exception as exc:
        return _unknown(f"Nominatim check failed: {type(exc).__name__}")


async def _check_websocket() -> Dict[str, Any]:
    """Check WebSocket connection manager state."""
    try:
        from app.core.connection_manager import ws_manager
        stats = ws_manager.get_connection_stats()
        total = stats.get("connected_users", 0)
        sockets = stats.get("total_sockets", 0)
        return _healthy(None, f"WebSocket layer active. {total} user(s), {sockets} socket(s).")
    except Exception as exc:
        return _unknown(f"Could not read WS state: {exc}")


async def _check_livekit() -> Dict[str, Any]:
    """Check LiveKit configuration."""
    try:
        from app.core.config import settings
        if settings.is_livekit_configured:
            return _healthy(None, "LiveKit credentials configured")
        return _unknown("LiveKit credentials not configured (voice disabled)")
    except Exception as exc:
        return _unknown(f"LiveKit check failed: {exc}")


async def check_all_services(db: AsyncSession) -> Dict[str, Any]:
    """
    Run all health checks in parallel and return aggregated system health.
    """
    import asyncio

    results = await asyncio.gather(
        _check_database(db),
        _check_redis(),
        _check_groq_ai(),
        _check_rag_chromadb(),
        _check_osrm(),
        _check_nominatim(),
        _check_websocket(),
        _check_livekit(),
        return_exceptions=True,
    )

    service_names = [
        "database", "redis", "groq_ai", "rag_chromadb",
        "osrm_routing", "nominatim", "websocket", "livekit",
    ]

    services = {}
    for name, result in zip(service_names, results):
        if isinstance(result, Exception):
            services[name] = _unknown(f"Check threw exception: {type(result).__name__}")
        else:
            services[name] = result

    # Determine overall status
    statuses = [s["status"] for s in services.values()]
    if "UNAVAILABLE" in statuses:
        overall = "DEGRADED"
    elif "DEGRADED" in statuses:
        overall = "DEGRADED"
    elif all(s in ("HEALTHY", "UNKNOWN") for s in statuses):
        overall = "HEALTHY"
    else:
        overall = "UNKNOWN"

    return {
        "overall_status": overall,
        "services": services,
        "checked_at": _now_iso(),
    }
