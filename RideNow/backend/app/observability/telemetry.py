"""
AI Telemetry — Phase 14
=======================
Lightweight Redis-backed (with in-memory fallback) AI telemetry tracker.

Security contract:
- Does NOT store raw user messages
- Does NOT store passwords, JWTs, API keys, payment data
- Stores only: metadata (user_id, intent category, tool names, latency, error types)
- All records expire after 24 hours (Redis TTL)
- In-memory fallback capped at 1000 entries
"""

import json
import logging
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_TELEMETRY_KEY = "ridenow:telemetry:ai_requests"
_TOOL_METRICS_KEY = "ridenow:telemetry:tool_calls"
_TELEMETRY_TTL = 86400  # 24 hours
_MAX_IN_MEMORY = 1000
_MAX_RECENT_RECORDS = 500  # max records returned in metrics summary


class AITelemetryTracker:
    """
    Tracks AI interaction metadata using Redis sorted sets (score = unix timestamp).
    Falls back to an in-memory deque if Redis is unavailable.
    """

    def __init__(self):
        self._in_memory_requests: deque = deque(maxlen=_MAX_IN_MEMORY)
        self._in_memory_tools: deque = deque(maxlen=_MAX_IN_MEMORY)

    def _get_redis(self):
        """Return Redis client or None if unavailable."""
        try:
            from app.core.redis import get_redis_client, is_using_fallback
            if is_using_fallback():
                return None
            return get_redis_client()
        except Exception:
            return None

    async def record_ai_request(
        self,
        request_id: str,
        user_id: int,
        channel: str,                   # "text" | "voice" | "multimodal"
        intent: Optional[str],
        model: str,
        tools_called: List[str],
        tools_succeeded: List[str],
        tools_failed: List[str],
        latency_ms: float,
        fallback_used: bool,
        error_type: Optional[str],
        timestamp: Optional[str] = None,
    ) -> None:
        """Record a single AI request. Never stores raw message content."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()

        record = {
            "request_id": request_id,
            "user_id": user_id,
            "channel": channel,
            "intent": intent or "unknown",
            "model": model,
            "tools_called": tools_called,
            "tools_succeeded": tools_succeeded,
            "tools_failed": tools_failed,
            "tool_count": len(tools_called),
            "tool_success_count": len(tools_succeeded),
            "tool_failure_count": len(tools_failed),
            "latency_ms": round(latency_ms, 2),
            "fallback_used": fallback_used,
            "error_type": error_type,
            "timestamp": timestamp,
        }

        score = time.time()
        redis = self._get_redis()

        if redis:
            try:
                await redis.zadd(
                    _TELEMETRY_KEY,
                    {json.dumps(record): score},
                )
                # Trim to recent 10000 entries and enforce TTL
                await redis.zremrangebyrank(_TELEMETRY_KEY, 0, -10001)
                await redis.expire(_TELEMETRY_KEY, _TELEMETRY_TTL)
            except Exception as exc:
                logger.debug(f"[Telemetry] Redis write failed, using in-memory: {exc}")
                self._in_memory_requests.append(record)
        else:
            self._in_memory_requests.append(record)

    async def record_tool_call(
        self,
        request_id: str,
        tool_name: str,
        duration_ms: float,
        success: bool,
        error_category: Optional[str] = None,
        retry_count: int = 0,
    ) -> None:
        """Record a single tool execution result."""
        record = {
            "request_id": request_id,
            "tool_name": tool_name,
            "duration_ms": round(duration_ms, 2),
            "success": success,
            "error_category": error_category,
            "retry_count": retry_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        score = time.time()
        redis = self._get_redis()

        if redis:
            try:
                await redis.zadd(
                    _TOOL_METRICS_KEY,
                    {json.dumps(record): score},
                )
                await redis.zremrangebyrank(_TOOL_METRICS_KEY, 0, -5001)
                await redis.expire(_TOOL_METRICS_KEY, _TELEMETRY_TTL)
            except Exception as exc:
                logger.debug(f"[Telemetry] Tool metric Redis write failed: {exc}")
                self._in_memory_tools.append(record)
        else:
            self._in_memory_tools.append(record)

    async def get_recent_ai_metrics(self, limit: int = 500) -> Dict[str, Any]:
        """
        Returns aggregated AI metrics from recent records.
        Never exposes individual user messages.
        """
        records = await self._fetch_recent_records(_TELEMETRY_KEY, limit)
        if not records:
            records = list(self._in_memory_requests)[-limit:]

        if not records:
            return {
                "total_requests": 0,
                "avg_latency_ms": None,
                "tool_success_rate": None,
                "fallback_rate": None,
                "error_rate": None,
                "top_intents": [],
                "top_tools": [],
                "recent_errors": [],
                "data_available": False,
            }

        total = len(records)
        latencies = [r["latency_ms"] for r in records if r.get("latency_ms") is not None]
        avg_latency = round(sum(latencies) / len(latencies), 1) if latencies else None

        total_tool_calls = sum(r.get("tool_count", 0) for r in records)
        total_tool_success = sum(r.get("tool_success_count", 0) for r in records)
        tool_success_rate = (
            round(total_tool_success / total_tool_calls * 100, 1)
            if total_tool_calls > 0 else None
        )

        fallback_count = sum(1 for r in records if r.get("fallback_used"))
        fallback_rate = round(fallback_count / total * 100, 1) if total > 0 else 0.0

        error_count = sum(1 for r in records if r.get("error_type"))
        error_rate = round(error_count / total * 100, 1) if total > 0 else 0.0

        # Top intents
        intent_counts: Dict[str, int] = {}
        for r in records:
            intent = r.get("intent", "unknown")
            intent_counts[intent] = intent_counts.get(intent, 0) + 1
        top_intents = sorted(intent_counts.items(), key=lambda x: -x[1])[:5]

        # Top tools
        tool_counts: Dict[str, int] = {}
        for r in records:
            for t in r.get("tools_called", []):
                tool_counts[t] = tool_counts.get(t, 0) + 1
        top_tools = sorted(tool_counts.items(), key=lambda x: -x[1])[:10]

        # Recent errors (last 10, no user data)
        recent_errors = [
            {
                "request_id": r.get("request_id"),
                "error_type": r.get("error_type"),
                "intent": r.get("intent"),
                "timestamp": r.get("timestamp"),
            }
            for r in reversed(records)
            if r.get("error_type")
        ][:10]

        return {
            "total_requests": total,
            "avg_latency_ms": avg_latency,
            "tool_success_rate": tool_success_rate,
            "fallback_rate": fallback_rate,
            "error_rate": error_rate,
            "top_intents": [{"intent": k, "count": v} for k, v in top_intents],
            "top_tools": [{"tool": k, "count": v} for k, v in top_tools],
            "recent_errors": recent_errors,
            "data_available": True,
            "period": "last_24h",
        }

    async def _fetch_recent_records(self, key: str, limit: int) -> List[Dict]:
        """Fetch recent records from Redis sorted set."""
        redis = self._get_redis()
        if not redis:
            return []
        try:
            raw = await redis.zrange(key, -limit, -1)
            records = []
            for item in raw:
                try:
                    records.append(json.loads(item))
                except Exception:
                    pass
            return records
        except Exception as exc:
            logger.debug(f"[Telemetry] Redis fetch failed: {exc}")
            return []


# Singleton instance
telemetry = AITelemetryTracker()
