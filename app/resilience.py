"""Lightweight resilience primitives (retry + circuit breaker).

Used for Redis (breaker), Kafka publish / Postgres candidates (retry),
and Kafka consumer durable-write retries before DLQ.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from .logging_config import get_logger
from .metrics import (
    CIRCUIT_BREAKER_OPEN,
    RETRIES_TOTAL,
)

logger = get_logger("resilience")

T = TypeVar("T")


class CircuitOpenError(RuntimeError):
    """Raised when the circuit is open and calls are short-circuited."""


class CircuitBreaker:
    """
    Simple closed → open → half-open breaker.

    - closed: calls allowed; failures count toward threshold
    - open: calls rejected until recovery_timeout elapses
    - half-open: one probe allowed; success closes, failure re-opens
    """

    def __init__(
        self,
        *,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
    ) -> None:
        self.name = name
        self.failure_threshold = max(1, failure_threshold)
        self.recovery_timeout = max(0.1, recovery_timeout)
        self._failures = 0
        self._opened_at: float | None = None
        self._half_open = False

    @property
    def state(self) -> str:
        if self._opened_at is None:
            return "closed"
        if self._half_open:
            return "half_open"
        return "open"

    def allow(self) -> bool:
        if self._opened_at is None:
            return True
        elapsed = time.monotonic() - self._opened_at
        if elapsed >= self.recovery_timeout:
            self._half_open = True
            return True
        return False

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None
        self._half_open = False

    def record_failure(self) -> None:
        self._failures += 1
        if self._half_open or self._failures >= self.failure_threshold:
            self._opened_at = time.monotonic()
            self._half_open = False
            CIRCUIT_BREAKER_OPEN.labels(name=self.name).inc()
            logger.warning(
                "circuit_opened",
                name=self.name,
                failures=self._failures,
                recovery_timeout=self.recovery_timeout,
            )


def is_transient_error(exc: BaseException) -> bool:
    """Heuristic: retry timeouts / connection blips, not logic/validation errors."""
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError, ConnectionError, OSError)):
        return True
    name = type(exc).__name__.lower()
    transient_tokens = (
        "timeout",
        "timedout",
        "connection",
        "unavailable",
        "temporary",
        "brokenpipe",
        "reset",
    )
    blob = f"{name} {exc}".lower()
    return any(token in blob for token in transient_tokens)


async def retry_async(
    func: Callable[[], Awaitable[T]],
    *,
    attempts: int = 2,
    base_delay: float = 0.05,
    operation: str = "operation",
    retry_on: Callable[[BaseException], bool] = is_transient_error,
) -> T:
    """Run async func up to `attempts` times with exponential backoff."""
    attempts = max(1, attempts)
    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await func()
        except Exception as exc:  # noqa: BLE001 — classified by retry_on
            last_exc = exc
            if attempt >= attempts or not retry_on(exc):
                raise
            delay = base_delay * (2 ** (attempt - 1))
            RETRIES_TOTAL.labels(operation=operation).inc()
            logger.warning(
                "retrying",
                operation=operation,
                attempt=attempt,
                attempts=attempts,
                delay_seconds=delay,
                error=str(exc),
            )
            await asyncio.sleep(delay)
    assert last_exc is not None
    raise last_exc


async def call_with_circuit(
    breaker: CircuitBreaker,
    func: Callable[[], Awaitable[T]],
    *,
    operation: str,
) -> T:
    """Execute func if breaker allows; record success/failure."""
    if not breaker.allow():
        raise CircuitOpenError(f"{breaker.name} circuit open ({operation})")
    try:
        result = await func()
    except Exception:
        breaker.record_failure()
        raise
    breaker.record_success()
    return result


# Process-wide Redis breaker (shared by cache + feature reads on the API)
_redis_breaker: CircuitBreaker | None = None


def get_redis_breaker() -> CircuitBreaker:
    global _redis_breaker
    if _redis_breaker is None:
        from .config import get_settings

        settings = get_settings()
        _redis_breaker = CircuitBreaker(
            name="redis",
            failure_threshold=settings.redis_circuit_failure_threshold,
            recovery_timeout=settings.redis_circuit_recovery_seconds,
        )
    return _redis_breaker


def reset_redis_breaker_for_tests() -> None:
    """Test helper — clear singleton so settings can be re-applied."""
    global _redis_breaker
    _redis_breaker = None
