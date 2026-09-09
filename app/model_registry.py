from .model import (
    RecommendationModel,
    SimpleRecommendationModel,
    SimpleRecommendationModelV2,
)

MODELS: dict[str, RecommendationModel] = {
    "v1": SimpleRecommendationModel(version="v1"),
    "v2": SimpleRecommendationModelV2(version="v2"),
}


def get_model(version: str) -> RecommendationModel:
    model = MODELS.get(version)
    if model is None:
        raise ValueError(f"Unknown model version: {version}")
    return model
