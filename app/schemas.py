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
