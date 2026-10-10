"""
Retry & Timeout Utilities — Phase 14
======================================
Bounded exponential backoff for safe retries of read-only or idempotent operations.

SAFETY CONTRACT:
- NEVER use for: ride booking, cancellation, completion, SOS, payment mutations
- SAFE for: geocoding, route calculation, read-only external API calls
- All retries are bounded (max_attempts)
- Exponential backoff with jitter to avoid thundering herd
"""

import asyncio
import logging
import random
from typing import Any, Callable, Tuple, Type

logger = logging.getLogger(__name__)


async def with_retry(
    coro_fn: Callable,
    *args: Any,
    max_attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 5.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    operation_name: str = "operation",
    **kwargs: Any,
) -> Any:
    """
    Execute an async coroutine function with bounded exponential backoff.

    Usage:
        result = await with_retry(geocode_address, "Palasia, Indore",
                                  max_attempts=3, operation_name="geocode")

    Parameters:
        coro_fn: Async callable to retry
        *args: Positional args for coro_fn
        max_attempts: Maximum total attempts (default 3)
        base_delay: Initial wait between retries in seconds (default 0.5)
        max_delay: Cap on wait time (default 5.0s)
        retryable_exceptions: Which exceptions trigger a retry
        operation_name: Used in log messages only
        **kwargs: Keyword args for coro_fn
    """
    last_exception = None

    for attempt in range(1, max_attempts + 1):
        try:
            return await coro_fn(*args, **kwargs)
        except retryable_exceptions as exc:
            last_exception = exc
            if attempt == max_attempts:
                logger.warning(
                    f"[Retry] {operation_name} failed after {max_attempts} attempt(s): {exc}"
                )
                raise

            # Exponential backoff with jitter
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            jitter = random.uniform(0, delay * 0.1)
            wait = delay + jitter

            logger.info(
                f"[Retry] {operation_name} attempt {attempt}/{max_attempts} failed: {exc}. "
                f"Retrying in {wait:.2f}s..."
            )
            await asyncio.sleep(wait)

    raise last_exception


async def with_timeout(
    coro_fn: Callable,
    *args: Any,
    timeout_seconds: float = 10.0,
    operation_name: str = "operation",
    **kwargs: Any,
) -> Any:
    """
    Execute an async coroutine with a hard timeout.

    Raises asyncio.TimeoutError if the operation exceeds the timeout.
    """
    try:
        return await asyncio.wait_for(
            coro_fn(*args, **kwargs),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        logger.warning(f"[Timeout] {operation_name} exceeded {timeout_seconds}s timeout")
        raise


async def with_retry_and_timeout(
    coro_fn: Callable,
    *args: Any,
    max_attempts: int = 3,
    timeout_seconds: float = 10.0,
    base_delay: float = 0.5,
    max_delay: float = 5.0,
    operation_name: str = "operation",
    **kwargs: Any,
) -> Any:
    """
    Combination of retry + per-attempt timeout.
    Each individual attempt has its own timeout.
    Total max time ≈ max_attempts * timeout_seconds + backoff overhead.
    """

    async def _attempt_with_timeout():
        return await with_timeout(
            coro_fn, *args,
            timeout_seconds=timeout_seconds,
            operation_name=operation_name,
            **kwargs,
        )

    return await with_retry(
        _attempt_with_timeout,
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        retryable_exceptions=(Exception,),
        operation_name=operation_name,
    )
