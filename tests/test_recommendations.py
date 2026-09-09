import json

import pytest

from app.config import get_settings
from app.features import UserFeatures
from app.main import read_recommendations
from app.recommendation_repository import RecommendationCandidate
from app.recommendation_store import (
    POPULAR_RECOMMENDATIONS,
    get_recommendations,
    save_recommendations,
)


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
    RecommendationCandidate(item_id=90, score=0.65),
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


class FakeConnection:
    """In-memory stand-in for asyncpg so tests don't need Postgres."""

    def __init__(self, initial: dict[int, list[int]] | None = None):
        self.rows = dict(initial or {})

    async def fetchrow(self, query: str, user_id: int):
        if user_id not in self.rows:
            return None
        return {"recommendations": self.rows[user_id]}

    async def execute(self, query: str, user_id: int, recommendations_json: str):
        self.rows[user_id] = json.loads(recommendations_json)


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


@pytest.fixture
def mock_candidates(monkeypatch):
    async def fake_get_items(connection, *, limit: int = 20):
        return SEED_CANDIDATES[:limit]

    monkeypatch.setattr(
        "app.recommendation_service.get_recommendation_items",
        fake_get_items,
    )


@pytest.mark.asyncio
async def test_store_user_exists():
    connection = FakeConnection()
    await save_recommendations(123, [10, 25, 42, 81, 99], connection)

    result = await get_recommendations(123, connection)

    assert result == [10, 25, 42, 81, 99]


@pytest.mark.asyncio
async def test_store_user_missing_raises():
    connection = FakeConnection()

    with pytest.raises(KeyError, match="999"):
        await get_recommendations(999, connection)


@pytest.mark.asyncio
async def test_api_model_path_uses_postgres_candidates(monkeypatch, mock_candidates):
    """v1 returns top candidates by popularity score."""
    redis = FakeRedis()
    connection = FakeConnection({123: [10, 25, 42, 81, 99]})
    monkeypatch.setattr("app.main.redis_client", redis)
    monkeypatch.setattr("app.main.get_pool", lambda: FakePool(connection))
    monkeypatch.setattr(
        "app.recommendation_service.get_pool",
        lambda: FakePool(connection),
    )

    result = await read_recommendations(user_id=123)

    assert result.user_id == 123
    assert result.recommendations == [10, 20, 30, 40, 50]
    assert result.model_version == "v1"
    assert "cache:recommendations:123" in redis.data


@pytest.mark.asyncio
async def test_api_model_path_with_features_still_v1_popularity(
    monkeypatch,
    mock_candidates,
):
    redis = FakeRedis(
        {
            "features:user:123": UserFeatures(
                user_id=123,
                click_count=3,
                purchase_count=2,
                last_item_id=99,
            ).model_dump_json(),
        }
    )
    connection = FakeConnection()
    monkeypatch.setattr("app.main.redis_client", redis)
    monkeypatch.setattr("app.main.get_pool", lambda: FakePool(connection))
    monkeypatch.setattr(
        "app.recommendation_service.get_pool",
        lambda: FakePool(connection),
    )

    result = await read_recommendations(user_id=123)

    # v1 ignores feature values for ranking; still popularity top-5.
    assert result.recommendations == [10, 20, 30, 40, 50]
    assert result.model_version == "v1"


@pytest.mark.asyncio
async def test_api_unknown_user_gets_candidate_top5(monkeypatch, mock_candidates):
    redis = FakeRedis()
    connection = FakeConnection()
    monkeypatch.setattr("app.main.redis_client", redis)
    monkeypatch.setattr("app.main.get_pool", lambda: FakePool(connection))
    monkeypatch.setattr(
        "app.recommendation_service.get_pool",
        lambda: FakePool(connection),
    )

    result = await read_recommendations(user_id=999)

    assert result.user_id == 999
    assert result.recommendations == [10, 20, 30, 40, 50]
    assert result.model_version == "v1"


@pytest.mark.asyncio
async def test_api_cache_hit_skips_model(monkeypatch):
    redis = FakeRedis(
        {
            "cache:recommendations:123": json.dumps(
                {
                    "user_id": 123,
                    "recommendations": [1, 2, 3],
                    "model_version": "v1",
                }
            ),
        }
    )
    connection = FakeConnection({123: [10, 25, 42, 81, 99]})
    monkeypatch.setattr("app.main.redis_client", redis)
    monkeypatch.setattr("app.main.get_pool", lambda: FakePool(connection))

    result = await read_recommendations(user_id=123)

    assert result.recommendations == [1, 2, 3]
    assert result.model_version == "v1"


@pytest.mark.asyncio
async def test_api_model_and_postgres_failure_returns_popular(monkeypatch):
    class BrokenRedis(FakeRedis):
        async def get(self, key: str):
            raise RuntimeError("redis down")

    monkeypatch.setattr("app.main.redis_client", BrokenRedis())

    def boom():
        raise RuntimeError("postgres down")

    monkeypatch.setattr("app.main.get_pool", boom)

    result = await read_recommendations(user_id=123)

    assert result.recommendations == POPULAR_RECOMMENDATIONS
    assert result.model_version == "popular-fallback"


@pytest.mark.asyncio
async def test_api_postgres_fallback_when_model_fails(monkeypatch):
    redis = FakeRedis()
    connection = FakeConnection({123: [10, 25, 42, 81, 99]})
    monkeypatch.setattr("app.main.redis_client", redis)
    monkeypatch.setattr("app.main.get_pool", lambda: FakePool(connection))

    async def boom(*args, **kwargs):
        raise RuntimeError("model path failed")

    monkeypatch.setattr("app.main.generate_recommendations", boom)

    result = await read_recommendations(user_id=123)

    assert result.recommendations == [10, 25, 42, 81, 99]
    assert result.model_version == "postgres-store"
