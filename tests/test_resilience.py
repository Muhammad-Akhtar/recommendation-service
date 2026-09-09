"""Resilience: retry backoff + Redis circuit breaker + consumer DLQ helpers."""

from __future__ import annotations

import pytest

from app.config import get_settings
from app.events import UserInteractionEvent
from app.kafka_consumer import process_event
from app.main import read_recommendations
from app.recommendation_store import POPULAR_RECOMMENDATIONS
from app.resilience import (
    CircuitBreaker,
    CircuitOpenError,
    call_with_circuit,
    is_transient_error,
    reset_redis_breaker_for_tests,
    retry_async,
)


@pytest.fixture(autouse=True)
def _reset_breaker_and_settings():
    get_settings.cache_clear()
    reset_redis_breaker_for_tests()
    yield
    get_settings.cache_clear()
    reset_redis_breaker_for_tests()


@pytest.mark.asyncio
async def test_retry_async_retries_transient_then_succeeds():
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise TimeoutError("slow")
        return "ok"

    result = await retry_async(
        flaky,
        attempts=2,
        base_delay=0.001,
        operation="test_retry",
    )
    assert result == "ok"
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_retry_async_does_not_retry_non_transient():
    calls = {"n": 0}

    async def bad():
        calls["n"] += 1
        raise ValueError("logic error")

    with pytest.raises(ValueError):
        await retry_async(bad, attempts=3, base_delay=0.001, operation="test_no_retry")
    assert calls["n"] == 1


def test_is_transient_error_heuristics():
    assert is_transient_error(TimeoutError("x"))
    assert is_transient_error(ConnectionError("x"))
    assert not is_transient_error(ValueError("bad payload"))


@pytest.mark.asyncio
async def test_circuit_breaker_opens_and_short_circuits():
    breaker = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout=60.0)

    async def boom():
        raise TimeoutError("down")

    with pytest.raises(TimeoutError):
        await call_with_circuit(breaker, boom, operation="t1")
    with pytest.raises(TimeoutError):
        await call_with_circuit(breaker, boom, operation="t2")

    assert breaker.state == "open"
    with pytest.raises(CircuitOpenError):
        await call_with_circuit(breaker, boom, operation="t3")


@pytest.mark.asyncio
async def test_redis_circuit_open_falls_back_to_popular(monkeypatch):
    """After enough Redis failures, breaker opens and serve path skips Redis wait."""

    class AlwaysBrokenRedis:
        async def get(self, key: str):
            raise TimeoutError("redis slow")

        async def set(self, key: str, value: str, ex=None):
            raise TimeoutError("redis slow")

        async def ping(self):
            raise TimeoutError("redis slow")

    monkeypatch.setattr("app.main.redis_client", AlwaysBrokenRedis())

    def boom_pool():
        raise RuntimeError("postgres down")

    monkeypatch.setattr("app.main.get_pool", boom_pool)

    # Trip the breaker (threshold default 3)
    for _ in range(3):
        result = await read_recommendations(user_id=555)
        assert result.model_version == "popular-fallback"

    # Next call should hit circuit-open path quickly and still degrade
    result = await read_recommendations(user_id=555)
    assert result.recommendations == POPULAR_RECOMMENDATIONS
    assert result.model_version == "popular-fallback"


@pytest.mark.asyncio
async def test_consumer_durable_failure_goes_to_dlq(monkeypatch):
    published: list[UserInteractionEvent] = []

    async def boom_save():
        raise TimeoutError("pg down")

    async def fake_dlq(event, *, error, instance_id="api"):
        published.append(event)

    monkeypatch.setattr("app.kafka_consumer._save_event_durable", boom_save)
    monkeypatch.setattr("app.kafka_consumer.publish_to_dlq", fake_dlq)
    monkeypatch.setenv("CONSUMER_PG_ATTEMPTS", "2")
    monkeypatch.setenv("RETRY_BASE_DELAY_SECONDS", "0.001")
    get_settings.cache_clear()

    event = UserInteractionEvent(user_id=1, item_id=2, event_type="click")
    await process_event(event, "test-instance")

    assert len(published) == 1
    assert published[0].user_id == 1
