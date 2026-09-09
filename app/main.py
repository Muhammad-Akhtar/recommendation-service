import json
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Path, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, generate_latest

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
from .logging_config import configure_logging, get_logger
from .model_quality import (
    compare_model_quality,
    record_recommendation_click_if_matched,
    snapshot_from_counts,
)
from .metrics import (
    POSTGRES_FAILURES,
    RECOMMENDATION_LATENCY,
    RECOMMENDATION_REQUESTS,
    REDIS_FAILURES,
    REDIS_HITS,
    REDIS_MISSES,
)
from .middleware import RequestIdMiddleware
from .recommendation_service import generate_recommendations
from .recommendation_store import POPULAR_RECOMMENDATIONS
from .recommender import get_recommendations
from .redis_client import redis_client
from .schemas import (
    HealthResponse,
    InteractionPublishResponse,
    ModelQualityResponse,
    ModelQualityVersionStats,
    ReadyResponse,
    RecommendationResponse,
)
from .tracing import configure_tracing, get_tracer

settings = get_settings()
configure_logging(settings.log_level)
configure_tracing(
    service_name=settings.otel_service_name,
    exporter=settings.otel_traces_exporter,
)

logger = get_logger("main")
tracer = get_tracer("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
    except Exception as e:
        # Graceful degradation: pods can still serve /health, /ready (fallback),
        # and popular recommendations when Postgres is not reachable from the cluster.
        logger.warning("postgres_init_failed", error=str(e))
    try:
        await start_producer()
        logger.info("kafka_producer_started")
    except Exception as e:
        logger.warning("kafka_producer_not_started", error=str(e))
    yield
    await stop_producer()
    await close_db()


app = FastAPI(lifespan=lifespan)
app.add_middleware(RequestIdMiddleware)


def _cache_key(user_id: int) -> str:
    return f"cache:recommendations:{user_id}"


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness: process is up. Does not check Redis or Postgres."""
    return HealthResponse(
        status="ok",
        version=get_settings().service_version,
    )


@app.get("/demo/cpu-burn")
async def demo_cpu_burn(
    duration_ms: int = 50,
) -> dict[str, int | str]:
    """
    Task 24 helper: burn CPU briefly so HPA can observe utilization.

    FastAPI /health alone is too cheap to push CPU on modern machines.
    Keep duration small (e.g. 20–100ms). Do not use in real product paths.
    """
    duration_ms = max(1, min(duration_ms, 500))
    deadline = time.perf_counter() + (duration_ms / 1000.0)
    # Busy-wait on purpose (demo only)
    x = 0
    while time.perf_counter() < deadline:
        x = (x + 1) % 1_000_003
    return {
        "status": "ok",
        "duration_ms": duration_ms,
        "service_version": get_settings().service_version,
    }


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


@app.get("/metrics")
async def metrics() -> Response:
    """Prometheus scrape endpoint (Task 21)."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def _counter_value(metric_name: str, labels: dict[str, str]) -> float:
    """Read a labeled counter sample from the default Prometheus registry."""
    total = 0.0
    for metric in REGISTRY.collect():
        for sample in metric.samples:
            if sample.name != metric_name:
                continue
            if any(sample.labels.get(k) != v for k, v in labels.items()):
                continue
            total += sample.value
    return total


@app.get("/monitoring/model-quality", response_model=ModelQualityResponse)
async def model_quality() -> ModelQualityResponse:
    """
    Monitoring-side CTR snapshot (Task 22).

    Does not run during prediction — only reads counters already recorded.
    """
    versions = ("v1", "v2")
    snapshots = []
    for version in versions:
        served = _counter_value(
            "recommendations_served_total",
            {"model_version": version},
        )
        clicked = _counter_value(
            "recommendations_clicked_total",
            {"model_version": version},
        )
        snap = snapshot_from_counts(version, served, clicked)
        snapshots.append(snap)

    ranked = compare_model_quality(snapshots)
    best = ranked[0].model_version if ranked and ranked[0].recommendations_served else None

    return ModelQualityResponse(
        versions=[
            ModelQualityVersionStats(
                model_version=s.model_version,
                recommendations_served=s.recommendations_served,
                recommendations_clicked=s.recommendations_clicked,
                ctr=s.ctr,
            )
            for s in ranked
        ],
        best_by_ctr=best,
    )


@app.post(
    "/interactions",
    response_model=InteractionPublishResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_interaction(event: UserInteractionEvent) -> InteractionPublishResponse:
    """Publish a user interaction event to Kafka (Task 15)."""
    await publish_user_interaction(event)

    # Simulated recommendation feedback for CTR (Task 22) — off model path.
    if event.event_type.lower() == "click":
        await record_recommendation_click_if_matched(
            user_id=event.user_id,
            item_id=event.item_id,
            redis_client=redis_client,
        )

    logger.info(
        "interaction_published",
        user_id=event.user_id,
        item_id=event.item_id,
        event_type=event.event_type,
        topic=get_settings().kafka_topic,
    )
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
    source = "unknown"
    model_version_label = "none"
    started = time.perf_counter()

    with tracer.start_as_current_span("recommendations") as span:
        span.set_attribute("user.id", user_id)

        try:
            # 1. Try Redis cache
            try:
                with tracer.start_as_current_span("redis_cache_lookup"):
                    cached = await redis_client.get(cache_key)

                if cached:
                    REDIS_HITS.inc()
                    logger.info(
                        "cache_hit",
                        user_id=user_id,
                        cache_key=cache_key,
                    )
                    data = json.loads(cached)
                    response = RecommendationResponse(**data)
                    source = "cache"
                    model_version_label = response.model_version
                    span.set_attribute("recommendation.source", source)
                    return response

                REDIS_MISSES.inc()
                logger.info(
                    "cache_miss",
                    user_id=user_id,
                    cache_key=cache_key,
                )
            except Exception as e:
                redis_available = False
                REDIS_FAILURES.labels(operation="cache_get").inc()
                logger.warning(
                    "redis_unavailable",
                    user_id=user_id,
                    operation="cache_get",
                    error=str(e),
                )

            # 2. Feature Store → Model (primary personalization path)
            if redis_available:
                try:
                    response = await generate_recommendations(
                        user_id,
                        redis_client,
                        model_version=settings.model_version,
                    )
                    try:
                        with tracer.start_as_current_span("redis_cache_write"):
                            await redis_client.set(
                                cache_key,
                                response.model_dump_json(),
                                ex=settings.cache_ttl,
                            )
                    except Exception as e:
                        REDIS_FAILURES.labels(operation="cache_set").inc()
                        logger.warning(
                            "redis_unavailable",
                            user_id=user_id,
                            operation="cache_set",
                            error=str(e),
                        )
                    source = "model"
                    model_version_label = response.model_version
                    span.set_attribute("recommendation.source", source)
                    return response
                except Exception as e:
                    logger.warning(
                        "model_path_unavailable",
                        user_id=user_id,
                        error=str(e),
                    )

            # 3. Cache/model miss/fail → PostgreSQL recommendation store
            try:
                with tracer.start_as_current_span("postgres_recommendation_store"):
                    pool = get_pool()
                    async with pool.acquire() as connection:
                        recommendations = await get_recommendations(user_id, connection)

                response = RecommendationResponse(
                    user_id=user_id,
                    recommendations=recommendations,
                    model_version="postgres-store",
                )
                logger.info("postgres_store_hit", user_id=user_id)

                if redis_available:
                    try:
                        with tracer.start_as_current_span("redis_cache_write"):
                            await redis_client.set(
                                cache_key,
                                response.model_dump_json(),
                                ex=settings.cache_ttl,
                            )
                    except Exception as e:
                        REDIS_FAILURES.labels(operation="cache_set").inc()
                        logger.warning(
                            "redis_unavailable",
                            user_id=user_id,
                            operation="cache_set",
                            error=str(e),
                        )

                source = "postgres-store"
                model_version_label = response.model_version
                span.set_attribute("recommendation.source", source)
                return response

            except Exception as e:
                POSTGRES_FAILURES.labels(operation="recommendation_store").inc()
                logger.warning(
                    "postgres_unavailable",
                    user_id=user_id,
                    operation="recommendation_store",
                    error=str(e),
                )

            # 4. Store miss/fail → popular recommendations
            logger.info("popular_fallback", user_id=user_id)
            response = RecommendationResponse(
                user_id=user_id,
                recommendations=POPULAR_RECOMMENDATIONS,
                model_version="popular-fallback",
            )
            source = "popular-fallback"
            model_version_label = response.model_version
            span.set_attribute("recommendation.source", source)
            return response
        finally:
            elapsed = time.perf_counter() - started
            RECOMMENDATION_LATENCY.observe(elapsed)
            RECOMMENDATION_REQUESTS.labels(
                source=source,
                model_version=model_version_label,
            ).inc()
            span.set_attribute("recommendation.latency_seconds", elapsed)
            logger.info(
                "recommendation_served",
                user_id=user_id,
                source=source,
                model_version=model_version_label,
                latency_seconds=round(elapsed, 6),
            )
