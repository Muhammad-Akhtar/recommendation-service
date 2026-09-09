"""Task 22 — prediction logging + model quality / CTR."""

from __future__ import annotations

import json

import pytest
from prometheus_client import REGISTRY

from app.features import UserFeatures
from app.model_quality import (
    calculate_ctr,
    compare_model_quality,
    last_recs_key,
    record_recommendation_click_if_matched,
    record_recommendations_served,
    snapshot_from_counts,
)
from app.prediction_logger import PredictionLog, build_prediction_log, log_prediction
from app.recommendation_repository import RecommendationCandidate
from app.recommendation_service import generate_recommendations


class FakeRedis:
    def __init__(self, initial: dict[str, str] | None = None):
        self.data = dict(initial or {})

    async def get(self, key: str):
        return self.data.get(key)

    async def set(self, key: str, value: str, ex=None):
        self.data[key] = value


class FakePool:
    def __init__(self):
        pass

    def acquire(self):
        return FakeAcquire()


class FakeAcquire:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *args):
        return False


SEED_CANDIDATES = [
    RecommendationCandidate(item_id=10, score=0.95),
    RecommendationCandidate(item_id=20, score=0.91),
    RecommendationCandidate(item_id=30, score=0.88),
    RecommendationCandidate(item_id=40, score=0.84),
    RecommendationCandidate(item_id=50, score=0.80),
]


def _counter_value(name: str, labels: dict[str, str]) -> float:
    value = 0.0
    for metric in REGISTRY.collect():
        for sample in metric.samples:
            if sample.name != name:
                continue
            if any(sample.labels.get(k) != v for k, v in labels.items()):
                continue
            value += sample.value
    return value


def test_prediction_log_fields():
    features = UserFeatures(
        user_id=7,
        click_count=3,
        purchase_count=1,
        last_item_id=99,
    )
    log = build_prediction_log(
        user_id=7,
        model_version="v1",
        features=features,
        recommendations=[10, 20, 30, 40, 50],
    )
    assert isinstance(log, PredictionLog)
    assert log.recommendation_count == 5
    assert log.click_count == 3
    assert log.purchase_count == 1
    assert log.last_item_id == 99
    assert log.model_version == "v1"
    log_prediction(log)  # should not raise


def test_calculate_ctr():
    assert calculate_ctr(10_000, 500) == 0.05
    assert calculate_ctr(0, 10) == 0.0


def test_compare_model_versions_by_ctr():
    v1 = snapshot_from_counts("v1", served=50_000, clicked=2_100)  # 4.2%
    v2 = snapshot_from_counts("v2", served=50_000, clicked=3_050)  # 6.1%
    ranked = compare_model_quality([v1, v2])
    assert ranked[0].model_version == "v2"
    assert ranked[1].model_version == "v1"
    assert abs(ranked[0].ctr - 0.061) < 1e-9


@pytest.mark.asyncio
async def test_served_and_clicked_attribution(monkeypatch):
    redis = FakeRedis()
    before_served = _counter_value(
        "recommendations_served_total",
        {"model_version": "v1"},
    )
    before_clicked = _counter_value(
        "recommendations_clicked_total",
        {"model_version": "v1"},
    )

    await record_recommendations_served(
        user_id=42,
        model_version="v1",
        item_ids=[10, 20, 30, 40, 50],
        redis_client=redis,
    )
    assert last_recs_key(42) in redis.data
    payload = json.loads(redis.data[last_recs_key(42)])
    assert payload["item_ids"] == [10, 20, 30, 40, 50]

    matched = await record_recommendation_click_if_matched(
        user_id=42,
        item_id=20,
        redis_client=redis,
    )
    unmatched = await record_recommendation_click_if_matched(
        user_id=42,
        item_id=999,
        redis_client=redis,
    )

    assert matched is True
    assert unmatched is False
    assert (
        _counter_value("recommendations_served_total", {"model_version": "v1"})
        >= before_served + 5
    )
    assert (
        _counter_value("recommendations_clicked_total", {"model_version": "v1"})
        >= before_clicked + 1
    )


@pytest.mark.asyncio
async def test_generate_recommendations_logs_and_records_metrics(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(
        "app.recommendation_service.get_pool",
        lambda: FakePool(),
    )

    async def fake_items(connection, *, limit: int = 20):
        return SEED_CANDIDATES[:limit]

    monkeypatch.setattr(
        "app.recommendation_service.get_recommendation_items",
        fake_items,
    )

    before_pred = _counter_value("model_predictions_total", {"model_version": "v1"})
    before_served = _counter_value(
        "recommendations_served_total",
        {"model_version": "v1"},
    )

    result = await generate_recommendations(101, redis, model_version="v1")

    assert result.recommendations == [10, 20, 30, 40, 50]
    assert result.model_version == "v1"
    assert last_recs_key(101) in redis.data
    assert (
        _counter_value("model_predictions_total", {"model_version": "v1"})
        >= before_pred + 1
    )
    assert (
        _counter_value("recommendations_served_total", {"model_version": "v1"})
        >= before_served + 5
    )
