"""Prediction logging for model monitoring (Task 22).

Captures a compact record of each model inference for structured logs.
Heavy analytics / drift checks stay off the request path.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from .features import UserFeatures
from .logging_config import get_logger

logger = get_logger("prediction_logger")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PredictionLog(BaseModel):
    """Compact prediction record — important fields only, not the full feature blob."""

    user_id: int
    model_version: str
    recommendation_count: int
    click_count: int
    purchase_count: int
    last_item_id: int | None = None
    recommendations: list[int] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=_utc_now)


def build_prediction_log(
    *,
    user_id: int,
    model_version: str,
    features: UserFeatures,
    recommendations: list[int],
) -> PredictionLog:
    return PredictionLog(
        user_id=user_id,
        model_version=model_version,
        recommendation_count=len(recommendations),
        click_count=features.click_count,
        purchase_count=features.purchase_count,
        last_item_id=features.last_item_id,
        recommendations=list(recommendations),
    )


def log_prediction(prediction: PredictionLog) -> None:
    """Emit a structured prediction event (Task 21 logger)."""
    logger.info(
        "prediction_logged",
        user_id=prediction.user_id,
        model_version=prediction.model_version,
        recommendation_count=prediction.recommendation_count,
        click_count=prediction.click_count,
        purchase_count=prediction.purchase_count,
        last_item_id=prediction.last_item_id,
        recommendations=prediction.recommendations,
        timestamp=prediction.timestamp.isoformat(),
    )
