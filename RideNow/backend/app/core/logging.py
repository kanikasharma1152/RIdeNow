"""
RideNow — Structured Logging & Observability
=============================================
Provides consistent request logging, request ID propagation, and safe metadata
formatting without exposing sensitive credentials (passwords, JWTs, API keys).
"""

import json
import logging
import time
import uuid
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("ridenow.access")

# Redacted headers and parameters for security
SENSITIVE_HEADERS = {"authorization", "cookie", "x-api-key", "set-cookie"}
SENSITIVE_KEYS = {"password", "token", "secret", "access_token", "refresh_token", "api_key", "credentials"}


def sanitize_value(key: str, value: any) -> any:
    """Mask sensitive string fields."""
    if isinstance(key, str) and any(s in key.lower() for s in SENSITIVE_KEYS):
        return "***REDACTED***"
    return value


def sanitize_dict(data: dict) -> dict:
    """Recursively sanitize sensitive keys in a dictionary."""
    if not isinstance(data, dict):
        return data
    sanitized = {}
    for k, v in data.items():
        if isinstance(v, dict):
            sanitized[k] = sanitize_dict(v)
        elif isinstance(v, list):
            sanitized[k] = [sanitize_dict(item) if isinstance(item, dict) else sanitize_value(k, item) for item in v]
        else:
            sanitized[k] = sanitize_value(k, v)
    return sanitized


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Asynchronous middleware that:
    1. Assigns a unique X-Request-ID to every HTTP request.
    2. Measures exact request duration in milliseconds.
    3. Logs structured metadata on completion without leaking confidential payloads.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        start_time = time.monotonic()
        method = request.method
        path = request.url.path

        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            duration_ms = round((time.monotonic() - start_time) * 1000, 2)
            logger.error(
                json.dumps({
                    "event": "request_error",
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "duration_ms": duration_ms,
                    "error": type(exc).__name__,
                })
            )
            raise exc

        duration_ms = round((time.monotonic() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = request_id

        # Don't spam logs for frequent health checks or static asset probes unless error
        if path == "/health" and status_code < 400:
            return response

        log_level = logging.INFO if status_code < 400 else (logging.WARNING if status_code < 500 else logging.ERROR)
        logger.log(
            log_level,
            json.dumps({
                "event": "http_request",
                "request_id": request_id,
                "method": method,
                "path": path,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "client_ip": request.client.host if request.client else "unknown",
            })
        )

        return response
