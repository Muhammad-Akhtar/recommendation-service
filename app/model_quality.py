"""Model-quality signals: served impressions, clicks, CTR (Task 22).

Serving path only records counters + a short-lived Redis impression.
CTR / version comparison are computed from metrics (monitoring side).
"""

from __future__ import annotations

import json

import redis.asyncio as redis
from pydantic import BaseModel

from .logging_config import get_logger
from .metrics import RECOMMENDATIONS_CLICKED, RECOMMENDATIONS_SERVED

logger = get_logger("model_quality")

LAST_RECS_KEY_PREFIX = "last_recs:"
LAST_RECS_TTL_SECONDS = 3600


def last_recs_key(user_id: int) -> str:
    return f"{LAST_RECS_KEY_PREFIX}{user_id}"


async def record_recommendations_served(
    *,
    user_id: int,
    model_version: str,
    item_ids: list[int],
    redis_client: redis.Redis,
) -> None:
    """Count served items and remember them for click attribution."""
    if not item_ids:
        return

    RECOMMENDATIONS_SERVED.labels(model_version=model_version).inc(len(item_ids))

    payload = json.dumps(
        {
            "model_version": model_version,
            "item_ids": item_ids,
        }
    )
    try:
        await redis_client.set(
            last_recs_key(user_id),
            payload,
            ex=LAST_RECS_TTL_SECONDS,
        )
    except Exception as e:
        logger.warning(
            "impression_store_failed",
            user_id=user_id,
            model_version=model_version,
            error=str(e),
        )


async def record_recommendation_click_if_matched(
    *,
    user_id: int,
    item_id: int,
    redis_client: redis.Redis,
) -> bool:
    """
    If the clicked item was in the user's last recommendation list,
    count it as a recommendation click for that model version.
    """
    try:
        raw = await redis_client.get(last_recs_key(user_id))
    except Exception as e:
        logger.warning(
            "impression_read_failed",
            user_id=user_id,
            item_id=item_id,
            error=str(e),
        )
        return False

    if not raw:
        return False

    data = json.loads(raw)
    item_ids = data.get("item_ids") or []
    model_version = data.get("model_version") or "unknown"

    if item_id not in item_ids:
        return False

    RECOMMENDATIONS_CLICKED.labels(model_version=model_version).inc()
    logger.info(
        "recommendation_clicked",
        user_id=user_id,
        item_id=item_id,
        model_version=model_version,
    )
    return True


def calculate_ctr(recommendations_served: float, recommendations_clicked: float) -> float:
    """CTR = clicks / recommendations_served (0 if nothing served)."""
    if recommendations_served <= 0:
        return 0.0
    return recommendations_clicked / recommendations_served


class ModelQualitySnapshot(BaseModel):
    model_version: str
    recommendations_served: float
    recommendations_clicked: float
    ctr: float


def compare_model_quality(
    snapshots: list[ModelQualitySnapshot],
) -> list[ModelQualitySnapshot]:
    """Sort versions by CTR descending (best first) for canary / A-B review."""
    return sorted(snapshots, key=lambda row: row.ctr, reverse=True)


def snapshot_from_counts(
    model_version: str,
    served: float,
    clicked: float,
) -> ModelQualitySnapshot:
    return ModelQualitySnapshot(
        model_version=model_version,
        recommendations_served=served,
        recommendations_clicked=clicked,
        ctr=calculate_ctr(served, clicked),
    )
