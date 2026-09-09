"""Service layer: Redis features + Postgres candidates → Model (Task 19)."""

from __future__ import annotations

import time

import redis.asyncio as redis

from .config import get_settings
from .database import get_pool
from .feature_store import get_user_features
from .logging_config import get_logger
from .metrics import (
    MODEL_PREDICTION_ERRORS,
    MODEL_PREDICTION_LATENCY,
    MODEL_PREDICTIONS,
    POSTGRES_FAILURES,
    RECOMMENDATION_COUNT,
)
from .model_quality import record_recommendations_served
from .model_registry import get_model
from .prediction_logger import build_prediction_log, log_prediction
from .recommendation_repository import get_recommendation_items
from .resilience import call_with_circuit, get_redis_breaker, retry_async
from .schemas import RecommendationResponse
from .tracing import get_tracer

logger = get_logger("recommendation_service")
tracer = get_tracer("recommendation_service")


async def generate_recommendations(
    user_id: int,
    redis_client: redis.Redis,
    *,
    model_version: str = "v1",
) -> RecommendationResponse:
    """
    Orchestrate inference without putting SQL or Redis details in the model:

      1. Online features from Redis (circuit-breaker protected)
      2. Candidate items from PostgreSQL (short retry on transient errors)
      3. Model ranks features + candidates
      4. Log prediction + quality impressions (monitoring; not drift)
    """
    settings = get_settings()
    with tracer.start_as_current_span("generate_recommendations") as span:
        span.set_attribute("user.id", user_id)
        span.set_attribute("model.version", model_version)

        with tracer.start_as_current_span("redis_get_features"):
            features = await call_with_circuit(
                get_redis_breaker(),
                lambda: get_user_features(user_id, redis_client),
                operation="features_get",
            )

        try:
            with tracer.start_as_current_span("postgres_get_candidates"):

                async def _fetch_candidates():
                    pool = get_pool()
                    async with pool.acquire() as connection:
                        return await get_recommendation_items(connection, limit=20)

                candidates = await retry_async(
                    _fetch_candidates,
                    attempts=settings.postgres_fetch_attempts,
                    base_delay=settings.retry_base_delay_seconds,
                    operation="postgres_get_candidates",
                )
        except Exception:
            POSTGRES_FAILURES.labels(operation="get_candidates").inc()
            logger.warning(
                "postgres_unavailable",
                user_id=user_id,
                operation="get_candidates",
            )
            raise

        if not candidates:
            raise RuntimeError("No active recommendation candidates in PostgreSQL")

        model = get_model(model_version)
        with tracer.start_as_current_span("model_predict") as model_span:
            model_span.set_attribute("model.version", model.version)
            started = time.perf_counter()
            try:
                recommendations = model.predict(features, candidates)
            except Exception:
                MODEL_PREDICTION_ERRORS.labels(model_version=model.version).inc()
                raise
            elapsed = time.perf_counter() - started

        MODEL_PREDICTIONS.labels(model_version=model.version).inc()
        MODEL_PREDICTION_LATENCY.labels(model_version=model.version).observe(elapsed)
        RECOMMENDATION_COUNT.labels(model_version=model.version).observe(
            len(recommendations)
        )

        prediction = build_prediction_log(
            user_id=user_id,
            model_version=model.version,
            features=features,
            recommendations=recommendations,
        )
        log_prediction(prediction)

        await record_recommendations_served(
            user_id=user_id,
            model_version=model.version,
            item_ids=recommendations,
            redis_client=redis_client,
        )

        return RecommendationResponse(
            user_id=user_id,
            recommendations=recommendations,
            model_version=model.version,
        )
