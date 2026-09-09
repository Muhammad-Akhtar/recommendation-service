"""Online feature store backed by Redis (Task 18).

Redis holds *materialized* features for low-latency inference.
PostgreSQL `user_events` is the durable source of truth (see event_store.py).

Key pattern: features:user:{user_id}
"""

from __future__ import annotations

import redis.asyncio as redis

from .events import UserInteractionEvent
from .features import UserFeatures

FEATURE_KEY_PREFIX = "features:user:"


def feature_key(user_id: int) -> str:
    return f"{FEATURE_KEY_PREFIX}{user_id}"


async def get_user_features(
    user_id: int,
    redis_client: redis.Redis,
) -> UserFeatures:
    """Load online features for a user, or defaults if none materialized yet."""
    raw = await redis_client.get(feature_key(user_id))
    if not raw:
        return UserFeatures(user_id=user_id)
    return UserFeatures.model_validate_json(raw)


async def update_user_features(
    user_id: int,
    redis_client: redis.Redis,
    *,
    click_count: int | None = None,
    purchase_count: int | None = None,
    last_item_id: int | None = None,
) -> UserFeatures:
    """Overwrite selected fields and persist online features in Redis."""
    features = await get_user_features(user_id, redis_client)

    if click_count is not None:
        features.click_count = click_count
    if purchase_count is not None:
        features.purchase_count = purchase_count
    if last_item_id is not None:
        features.last_item_id = last_item_id

    await redis_client.set(feature_key(user_id), features.model_dump_json())
    return features


async def apply_interaction_event(
    event: UserInteractionEvent,
    redis_client: redis.Redis,
) -> UserFeatures:
    """
    Materialize online features from an interaction event.

    Call this *after* persisting the raw event to PostgreSQL so Redis stays
    a derived view, not the system of record.
    """
    features = await get_user_features(event.user_id, redis_client)

    event_type = event.event_type.lower()
    if event_type == "click":
        features.click_count += 1
    elif event_type == "purchase":
        features.purchase_count += 1

    features.last_item_id = event.item_id

    await redis_client.set(
        feature_key(event.user_id),
        features.model_dump_json(),
    )
    return features
