"""Service layer: Redis features + Postgres candidates → Model (Task 19)."""

from __future__ import annotations

import redis.asyncio as redis

from .database import get_pool
from .feature_store import get_user_features
from .model_registry import get_model
from .recommendation_repository import get_recommendation_items
from .schemas import RecommendationResponse


async def generate_recommendations(
    user_id: int,
    redis_client: redis.Redis,
    *,
    model_version: str = "v1",
) -> RecommendationResponse:
    """
    Orchestrate inference without putting SQL or Redis details in the model:

      1. Online features from Redis
      2. Candidate items from PostgreSQL
      3. Model ranks features + candidates
    """
    features = await get_user_features(user_id, redis_client)

    pool = get_pool()
    async with pool.acquire() as connection:
        candidates = await get_recommendation_items(connection, limit=20)

    if not candidates:
        raise RuntimeError("No active recommendation candidates in PostgreSQL")

    model = get_model(model_version)
    recommendations = model.predict(features, candidates)

    print(
        f"user_id={user_id} model_version={model.version} "
        f"recommendations={recommendations} "
        f"features=(clicks={features.click_count}, "
        f"purchases={features.purchase_count}, "
        f"last_item={features.last_item_id}) "
        f"candidates={len(candidates)}"
    )

    return RecommendationResponse(
        user_id=user_id,
        recommendations=recommendations,
        model_version=model.version,
    )
