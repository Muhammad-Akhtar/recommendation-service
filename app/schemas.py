from pydantic import BaseModel

from .events import UserInteractionEvent


class RecommendationRequest(BaseModel):
    user_id: int


class RecommendationData(BaseModel):
    user_id: int
    recommendations: list[int]


class RecommendationResponse(BaseModel):
    user_id: int
    recommendations: list[int]
    model_version: str | None = None


class HealthResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    status: str
    redis: str
    postgres: str
    kafka: str
    schema_registry: str
    fallback: str


class InteractionPublishResponse(BaseModel):
    status: str
    topic: str
    event: UserInteractionEvent


class ModelQualityVersionStats(BaseModel):
    model_version: str
    recommendations_served: float
    recommendations_clicked: float
    ctr: float


class ModelQualityResponse(BaseModel):
    """Read-only model-quality snapshot for monitoring / QA (Task 22)."""

    versions: list[ModelQualityVersionStats]
    best_by_ctr: str | None = None
