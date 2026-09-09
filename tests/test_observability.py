"""Task 21 — observability: request IDs, metrics, structured log context."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from app.config import get_settings
from app.main import app, read_recommendations
from app.middleware import REQUEST_ID_HEADER
from app.recommendation_repository import RecommendationCandidate


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    from app.resilience import reset_redis_breaker_for_tests

    reset_redis_breaker_for_tests()
    yield
    get_settings.cache_clear()
    reset_redis_breaker_for_tests()


SEED_CANDIDATES = [
    RecommendationCandidate(item_id=10, score=0.95),
    RecommendationCandidate(item_id=20, score=0.91),
    RecommendationCandidate(item_id=30, score=0.88),
    RecommendationCandidate(item_id=40, score=0.84),
    RecommendationCandidate(item_id=50, score=0.80),
]


class FakeRedis:
    def __init__(self, initial: dict[str, str] | None = None):
        self.data = dict(initial or {})

    async def get(self, key: str):
        return self.data.get(key)

    async def set(self, key: str, value: str, ex=None):
        self.data[key] = value

    async def ping(self):
        return True


class BrokenRedis(FakeRedis):
    async def get(self, key: str):
        raise RuntimeError("redis down")

    async def set(self, key: str, value: str, ex=None):
        raise RuntimeError("redis down")


class FakeConnection:
    def __init__(self, initial: dict[int, list[int]] | None = None):
        self.rows = dict(initial or {})

    async def fetchrow(self, query: str, user_id: int):
        if user_id not in self.rows:
            return None
        return {"recommendations": self.rows[user_id]}

    async def fetchval(self, query: str):
        return 1


class FakePool:
    def __init__(self, connection: FakeConnection):
        self.connection = connection

    def acquire(self):
        return FakeAcquire(self.connection)


class FakeAcquire:
    def __init__(self, connection: FakeConnection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _counter_value(name: str, labels: dict[str, str] | None = None) -> float:
    """Read a Prometheus counter sample from the default registry."""
    value = 0.0
    for metric in REGISTRY.collect():
        if metric.name != name and not name.startswith(metric.name):
            # Counters are exposed as <name>_total
            continue
        for sample in metric.samples:
            if sample.name != f"{name}_total" and sample.name != name:
                continue
            if labels and any(sample.labels.get(k) != v for k, v in labels.items()):
                continue
            value += sample.value
    return value


@pytest.fixture
def client(monkeypatch):
    """HTTP client with Redis/Postgres patched so lifespan side effects are ok."""
    redis = FakeRedis()
    connection = FakeConnection({123: [10, 25, 42, 81, 99]})
    monkeypatch.setattr("app.main.redis_client", redis)
    monkeypatch.setattr("app.main.get_pool", lambda: FakePool(connection))
    monkeypatch.setattr("app.main.start_producer", _async_noop)
    monkeypatch.setattr("app.main.stop_producer", _async_noop)
    monkeypatch.setattr("app.main.init_db", _async_noop)
    monkeypatch.setattr("app.main.close_db", _async_noop)

    async def fake_get_items(connection, *, limit: int = 20):
        return SEED_CANDIDATES[:limit]

    monkeypatch.setattr(
        "app.recommendation_service.get_recommendation_items",
        fake_get_items,
    )
    monkeypatch.setattr(
        "app.recommendation_service.get_pool",
        lambda: FakePool(connection),
    )

    with TestClient(app) as test_client:
        yield test_client, redis


async def _async_noop(*args, **kwargs):
    return None


def test_request_id_generated_when_missing(client):
    test_client, _ = client
    response = test_client.get("/health")
    assert response.status_code == 200
    assert REQUEST_ID_HEADER in response.headers
    assert len(response.headers[REQUEST_ID_HEADER]) > 0


def test_request_id_echoes_inbound_header(client):
    test_client, _ = client
    response = test_client.get("/health", headers={REQUEST_ID_HEADER: "qa-corr-42"})
    assert response.headers[REQUEST_ID_HEADER] == "qa-corr-42"


def test_metrics_endpoint_exposes_prometheus_text(client):
    test_client, _ = client
    response = test_client.get("/metrics")
    assert response.status_code == 200
    body = response.text
    assert "recommendation_requests_total" in body
    assert "recommendation_latency_seconds" in body


@pytest.mark.asyncio
async def test_cache_hit_increments_redis_hit_metric(monkeypatch):
    before_hits = _counter_value("redis_hits")
    before_requests = _counter_value(
        "recommendation_requests",
        {"source": "cache", "model_version": "v1"},
    )

    redis = FakeRedis(
        {
            "cache:recommendations:55": json.dumps(
                {
                    "user_id": 55,
                    "recommendations": [1, 2, 3],
                    "model_version": "v1",
                }
            ),
        }
    )
    monkeypatch.setattr("app.main.redis_client", redis)
    monkeypatch.setattr(
        "app.main.get_pool",
        lambda: FakePool(FakeConnection()),
    )

    result = await read_recommendations(user_id=55)

    assert result.recommendations == [1, 2, 3]
    assert _counter_value("redis_hits") >= before_hits + 1
    assert (
        _counter_value(
            "recommendation_requests",
            {"source": "cache", "model_version": "v1"},
        )
        >= before_requests + 1
    )


@pytest.mark.asyncio
async def test_redis_failure_increments_failure_metric_and_falls_back(monkeypatch):
    before_failures = _counter_value("redis_failures", {"operation": "cache_get"})

    monkeypatch.setattr("app.main.redis_client", BrokenRedis())
    monkeypatch.setattr(
        "app.main.get_pool",
        lambda: FakePool(FakeConnection({77: [9, 8, 7]})),
    )

    result = await read_recommendations(user_id=77)

    assert result.model_version == "postgres-store"
    assert result.recommendations == [9, 8, 7]
    assert (
        _counter_value("redis_failures", {"operation": "cache_get"})
        >= before_failures + 1
    )


@pytest.mark.asyncio
async def test_model_path_increments_prediction_metric(monkeypatch):
    before = _counter_value("model_predictions", {"model_version": "v1"})

    redis = FakeRedis()
    connection = FakeConnection()
    monkeypatch.setattr("app.main.redis_client", redis)
    monkeypatch.setattr("app.main.get_pool", lambda: FakePool(connection))
    monkeypatch.setattr(
        "app.recommendation_service.get_pool",
        lambda: FakePool(connection),
    )

    async def fake_get_items(connection, *, limit: int = 20):
        return SEED_CANDIDATES[:limit]

    monkeypatch.setattr(
        "app.recommendation_service.get_recommendation_items",
        fake_get_items,
    )

    result = await read_recommendations(user_id=88)

    assert result.model_version == "v1"
    assert result.recommendations == [10, 20, 30, 40, 50]
    assert (
        _counter_value("model_predictions", {"model_version": "v1"}) >= before + 1
    )
