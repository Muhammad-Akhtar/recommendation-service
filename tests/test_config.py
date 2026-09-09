import redis.asyncio as redis
import pytest

from app.config import Settings, get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_settings_defaults_when_env_not_set(monkeypatch):
    for name in (
        "REDIS_URL",
        "REDIS_TIMEOUT",
        "CACHE_TTL",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)

    assert settings.redis_url == "redis://redis:6379"
    assert settings.redis_timeout == 1.0
    assert settings.cache_ttl == 120
    assert settings.postgres_host == "postgres"
    assert settings.postgres_port == 5432
    assert settings.postgres_db == "recommendations"
    assert settings.postgres_user == "recommendation_user"
    assert settings.postgres_password == "recommendation_password"


def test_settings_env_overrides_defaults(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://custom-redis:6379")
    monkeypatch.setenv("REDIS_TIMEOUT", "0.1")
    monkeypatch.setenv("CACHE_TTL", "60")
    monkeypatch.setenv("POSTGRES_HOST", "db")
    monkeypatch.setenv("POSTGRES_PORT", "5433")
    monkeypatch.setenv("POSTGRES_DB", "recs")
    monkeypatch.setenv("POSTGRES_USER", "user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")

    settings = Settings(_env_file=None)

    assert settings.redis_url == "redis://custom-redis:6379"
    assert settings.redis_timeout == 0.1
    assert settings.cache_ttl == 60
    assert settings.postgres_host == "db"
    assert settings.postgres_port == 5433
    assert settings.postgres_db == "recs"
    assert settings.postgres_user == "user"
    assert settings.postgres_password == "secret"


def test_redis_client_uses_configured_url_and_timeout(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://settings-redis:6380/0")
    monkeypatch.setenv("REDIS_TIMEOUT", "0.05")
    get_settings.cache_clear()

    settings = get_settings()
    client = redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=settings.redis_timeout,
        socket_timeout=settings.redis_timeout,
    )
    pool_kwargs = client.connection_pool.connection_kwargs

    assert pool_kwargs["host"] == "settings-redis"
    assert pool_kwargs["port"] == 6380


@pytest.mark.asyncio
async def test_recommendations_use_configured_cache_ttl(monkeypatch):
    monkeypatch.setenv("CACHE_TTL", "120")
    get_settings.cache_clear()

    captured = {}

    class FakeRedis:
        async def get(self, key):
            return None

        async def set(self, key, value, ex=None):
            captured["ex"] = ex
            captured["key"] = key

        async def ping(self):
            return True

    class FakeConnection:
        async def fetchrow(self, query, user_id):
            return {"recommendations": [1, 2, 3]}

    class FakePool:
        def acquire(self):
            return FakeAcquire()

    class FakeAcquire:
        async def __aenter__(self):
            return FakeConnection()

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr("app.main.redis_client", FakeRedis())
    monkeypatch.setattr("app.main.get_pool", lambda: FakePool())
    monkeypatch.setattr(
        "app.recommendation_service.get_pool",
        lambda: FakePool(),
    )

    from app.recommendation_repository import RecommendationCandidate

    async def fake_items(connection, *, limit: int = 20):
        return [
            RecommendationCandidate(item_id=10, score=0.95),
            RecommendationCandidate(item_id=20, score=0.91),
            RecommendationCandidate(item_id=30, score=0.88),
            RecommendationCandidate(item_id=40, score=0.84),
            RecommendationCandidate(item_id=50, score=0.80),
        ][:limit]

    monkeypatch.setattr(
        "app.recommendation_service.get_recommendation_items",
        fake_items,
    )

    import app.main as main_module

    main_module.get_settings.cache_clear()

    result = await main_module.read_recommendations(user_id=123)

    # Model v1 returns top PostgreSQL candidates; TTL still applied on cache write.
    assert result.recommendations == [10, 20, 30, 40, 50]
    assert result.model_version == "v1"
    assert captured["ex"] == 120
    assert captured["key"] == "cache:recommendations:123"
