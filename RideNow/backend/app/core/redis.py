"""
RideNow — Redis Client
=======================
Provides an async Redis client with graceful fallback to an in-memory
dictionary when Redis is not configured (development / CI).

Usage:
    from app.core.redis import get_redis, redis_client

    # As a FastAPI dependency:
    async def my_endpoint(redis = Depends(get_redis)):
        await redis.set("key", "value", ex=60)

    # Direct access (after app startup):
    value = await redis_client.get("key")
"""

import asyncio
import json
import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ─── In-Memory Fallback ───────────────────────────────────────────────────────

class _InMemoryRedis:
    """
    Minimal in-memory Redis-like client for development / testing.
    Supports: get, set, delete, exists, expire, ttl, lpush, lrange, ltrim, incr.
    NOT suitable for production (not persistent, single-process only).
    """

    def __init__(self):
        self._store: dict[str, Any] = {}
        self._expiry: dict[str, float] = {}  # key → expiry timestamp

    def _is_expired(self, key: str) -> bool:
        exp = self._expiry.get(key)
        if exp is None:
            return False
        if time.monotonic() > exp:
            self._store.pop(key, None)
            self._expiry.pop(key, None)
            return True
        return False

    async def get(self, key: str) -> Optional[str]:
        if self._is_expired(key):
            return None
        return self._store.get(key)

    async def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        self._store[key] = str(value)
        if ex is not None:
            self._expiry[key] = time.monotonic() + ex
        return True

    async def delete(self, *keys: str) -> int:
        count = 0
        for key in keys:
            if key in self._store:
                self._store.pop(key)
                self._expiry.pop(key, None)
                count += 1
        return count

    async def exists(self, *keys: str) -> int:
        return sum(1 for k in keys if k in self._store and not self._is_expired(k))

    async def expire(self, key: str, seconds: int) -> bool:
        if key in self._store:
            self._expiry[key] = time.monotonic() + seconds
            return True
        return False

    async def ttl(self, key: str) -> int:
        if self._is_expired(key):
            return -2
        exp = self._expiry.get(key)
        if exp is None:
            return -1
        remaining = int(exp - time.monotonic())
        return max(remaining, 0)

    async def incr(self, key: str) -> int:
        val = int(self._store.get(key, 0)) + 1
        self._store[key] = str(val)
        return val

    async def lpush(self, key: str, *values: Any) -> int:
        if key not in self._store:
            self._store[key] = []
        for v in reversed(values):
            self._store[key].insert(0, v)
        return len(self._store[key])

    @staticmethod
    def _bounded_index(length: int, idx: int) -> int:
        if idx < 0:
            idx = length + idx
        return idx

    async def rpush(self, key: str, *values: Any) -> int:
        if key not in self._store:
            self._store[key] = []
        for v in values:
            self._store[key].append(v)
        return len(self._store[key])

    async def lrange(self, key: str, start: int, end: int) -> list:
        lst = self._store.get(key, [])
        n = len(lst)
        if n == 0:
            return []
        s = self._bounded_index(n, start)
        e = self._bounded_index(n, end)
        s = max(0, s)
        e = min(n - 1, e)
        if s > e:
            return []
        return lst[s : e + 1]

    async def ltrim(self, key: str, start: int, end: int) -> bool:
        lst = self._store.get(key, [])
        n = len(lst)
        if n == 0:
            return True
        s = self._bounded_index(n, start)
        e = self._bounded_index(n, end)
        s = max(0, s)
        e = min(n - 1, e)
        if s > e:
            self._store[key] = []
        else:
            self._store[key] = lst[s : e + 1]
        return True

    async def publish(self, channel: str, message: str) -> int:
        # No-op for in-memory (pub/sub not supported in single-process fallback)
        return 0

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        pass


# ─── Redis Client Singleton ───────────────────────────────────────────────────

_redis_instance = None
_using_fallback = False


async def init_redis() -> None:
    """
    Initialize the Redis connection at app startup.
    Falls back to in-memory if REDIS_URL is not set or Redis is unreachable.
    """
    global _redis_instance, _using_fallback

    from app.core.config import settings

    if not settings.REDIS_URL:
        logger.warning("REDIS_URL not set — using in-memory Redis fallback (development only)")
        _redis_instance = _InMemoryRedis()
        _using_fallback = True
        return

    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=3,
        )
        await client.ping()
        _redis_instance = client
        _using_fallback = False
        logger.info(f"Redis connected: {settings.REDIS_URL}")
    except Exception as exc:
        logger.warning(
            f"Redis connection failed ({exc}) — using in-memory fallback (development only)"
        )
        _redis_instance = _InMemoryRedis()
        _using_fallback = True


async def close_redis() -> None:
    """Close the Redis connection at app shutdown."""
    global _redis_instance
    if _redis_instance is not None:
        await _redis_instance.close()
        _redis_instance = None


def get_redis_client():
    """Return the active Redis client (real or fallback)."""
    global _redis_instance, _using_fallback
    if _redis_instance is None:
        _redis_instance = _InMemoryRedis()
        _using_fallback = True
    return _redis_instance


async def get_redis():
    """FastAPI dependency — yields the Redis client."""
    yield get_redis_client()


def is_using_fallback() -> bool:
    """Returns True if in-memory fallback is active (no real Redis)."""
    return _using_fallback


# ─── Helpers ─────────────────────────────────────────────────────────────────

async def cache_get(key: str) -> Optional[Any]:
    """Get a JSON-decoded value from Redis."""
    client = get_redis_client()
    raw = await client.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


async def cache_set(key: str, value: Any, ttl: int = 300) -> None:
    """Store a JSON-encoded value in Redis with a TTL."""
    client = get_redis_client()
    await client.set(key, json.dumps(value, default=str), ex=ttl)


async def cache_delete(key: str) -> None:
    """Delete a key from Redis."""
    client = get_redis_client()
    await client.delete(key)


async def rate_limit_check(identifier: str, max_requests: int, window_seconds: int) -> bool:
    """
    Simple sliding-window rate limiter.
    Returns True if the request is allowed, False if rate-limited.
    """
    client = get_redis_client()
    key = f"rate_limit:{identifier}"
    count = await client.incr(key)
    if count == 1:
        await client.expire(key, window_seconds)
    return count <= max_requests
