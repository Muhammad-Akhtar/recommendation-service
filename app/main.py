import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, Path, Response, status

from .config import get_settings
from .database import close_db, get_pool, init_db
from .events import UserInteractionEvent
from .event_store import list_user_events
from .feature_store import get_user_features
from .features import UserEventRecord, UserFeatures
from .kafka_producer import (
    check_kafka,
    check_schema_registry,
    publish_user_interaction,
    start_producer,
    stop_producer,
)
from .recommendation_service import generate_recommendations
from .recommendation_store import POPULAR_RECOMMENDATIONS
from .recommender import get_recommendations
from .redis_client import redis_client
from .schemas import (
    HealthResponse,
    InteractionPublishResponse,
    ReadyResponse,
    RecommendationResponse,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    try:
        await start_producer()
    except Exception as e:
        print(f"Kafka producer not started: {e}")
    yield
    await stop_producer()
    await close_db()


app = FastAPI(lifespan=lifespan)


def _cache_key(user_id: int) -> str:
    return f"cache:recommendations:{user_id}"


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness: process is up. Does not check Redis or Postgres."""
    return HealthResponse(status="ok")


@app.get("/ready", response_model=ReadyResponse)
async def ready(response: Response) -> ReadyResponse:
    """
    Readiness: can we still serve a useful recommendation?

    Redis, Postgres, and Kafka are optional (popular fallback exists).
    We report their status but only require the fallback path.
    """
    redis_status = "up"
    try:
        await redis_client.ping()
    except Exception:
        redis_status = "down"

    postgres_status = "up"
    try:
        pool = get_pool()
        async with pool.acquire() as connection:
            await connection.fetchval("SELECT 1")
    except Exception:
        postgres_status = "down"

    kafka_status = "up" if await check_kafka() else "down"
    schema_registry_status = "up" if check_schema_registry() else "down"

    fallback_ok = bool(POPULAR_RECOMMENDATIONS)
    fallback_status = "available" if fallback_ok else "unavailable"

    if not fallback_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadyResponse(
            status="not_ready",
            redis=redis_status,
            postgres=postgres_status,
            kafka=kafka_status,
            schema_registry=schema_registry_status,
            fallback=fallback_status,
        )

    return ReadyResponse(
        status="ready",
        redis=redis_status,
        postgres=postgres_status,
        kafka=kafka_status,
        schema_registry=schema_registry_status,
        fallback=fallback_status,
    )


@app.post(
    "/interactions",
    response_model=InteractionPublishResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_interaction(event: UserInteractionEvent) -> InteractionPublishResponse:
    """Publish a user interaction event to Kafka (Task 15)."""
    await publish_user_interaction(event)
    return InteractionPublishResponse(
        status="published",
        topic=get_settings().kafka_topic,
        event=event,
    )


@app.get(
    "/features/{user_id}",
    response_model=UserFeatures,
)
async def read_user_features(
    user_id: int = Path(
        ...,
        description="The user's integer ID",
        ge=1,
    ),
) -> UserFeatures:
    """Read *online* features from Redis (materialized view for inference)."""
    return await get_user_features(user_id, redis_client)


@app.get(
    "/events/{user_id}",
    response_model=list[UserEventRecord],
)
async def read_user_events(
    user_id: int = Path(
        ...,
        description="The user's integer ID",
        ge=1,
    ),
) -> list[UserEventRecord]:
    """Read durable event history from PostgreSQL (system of record)."""
    pool = get_pool()
    async with pool.acquire() as connection:
        rows = await list_user_events(user_id, connection)
    return [
        UserEventRecord(
            id=row["id"],
            user_id=row["user_id"],
            item_id=row["item_id"],
            event_type=row["event_type"],
            created_at=row["created_at"].isoformat(),
        )
        for row in rows
    ]


@app.get(
    "/recommendations/{user_id}",
    response_model=RecommendationResponse,
)
async def read_recommendations(
    user_id: int = Path(
        ...,
        description="The user's integer ID",
        ge=1,
    ),
) -> RecommendationResponse:
    """
    Serve recommendations (Task 19 flow):

    Cache → Feature Store + Model → PostgreSQL store → popular fallback
    """
    settings = get_settings()
    cache_key = _cache_key(user_id)
    redis_available = True

    # 1. Try Redis cache
    try:
        cached = await redis_client.get(cache_key)

        if cached:
            print("Cache HIT")
            data = json.loads(cached)
            return RecommendationResponse(**data)

        print("Cache MISS")
    except Exception as e:
        redis_available = False
        print(f"Redis unavailable while reading cache: {e}")

    # 2. Feature Store → Model (primary personalization path)
    if redis_available:
        try:
            response = await generate_recommendations(
                user_id,
                redis_client,
                model_version=settings.model_version,
            )
            try:
                await redis_client.set(
                    cache_key,
                    response.model_dump_json(),
                    ex=settings.cache_ttl,
                )
            except Exception as e:
                print(f"Redis unavailable while writing cache: {e}")
            return response
        except Exception as e:
            print(f"Model/feature path unavailable: {e}")

    # 3. Cache/model miss/fail → PostgreSQL recommendation store
    try:
        pool = get_pool()
        async with pool.acquire() as connection:
            recommendations = await get_recommendations(user_id, connection)

        response = RecommendationResponse(
            user_id=user_id,
            recommendations=recommendations,
            model_version="postgres-store",
        )
        print(f"PostgreSQL store HIT for user_id: {user_id}")

        if redis_available:
            try:
                await redis_client.set(
                    cache_key,
                    response.model_dump_json(),
                    ex=settings.cache_ttl,
                )
            except Exception as e:
                print(f"Redis unavailable while writing cache: {e}")

        return response

    except Exception as e:
        print(f"Recommendation store unavailable: {e}")

    # 4. Store miss/fail → popular recommendations
    print("Using popular recommendations")
    return RecommendationResponse(
        user_id=user_id,
        recommendations=POPULAR_RECOMMENDATIONS,
        model_version="popular-fallback",
    )
