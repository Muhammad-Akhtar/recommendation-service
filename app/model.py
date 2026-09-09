from pydantic import BaseModel

from .features import UserFeatures
from .recommendation_repository import RecommendationCandidate


class RecommendationModel:
    """Interface for recommendation models (Task 19)."""

    def __init__(self, version: str) -> None:
        self.version = version

    def predict(
        self,
        features: BaseModel,
        candidates: list[RecommendationCandidate],
    ) -> list[int]:
        raise NotImplementedError


class SimpleRecommendationModel(RecommendationModel):
    """v1 — rank primarily by PostgreSQL candidate popularity score."""

    def predict(
        self,
        features: BaseModel,
        candidates: list[RecommendationCandidate],
    ) -> list[int]:
        assert isinstance(features, UserFeatures)
        # Candidates are already ordered by score DESC from the repository.
        return [c.item_id for c in candidates[:5]]


class SimpleRecommendationModelV2(RecommendationModel):
    """v2 — popularity score + online user features."""

    def predict(
        self,
        features: BaseModel,
        candidates: list[RecommendationCandidate],
    ) -> list[int]:
        assert isinstance(features, UserFeatures)

        ranked: list[tuple[float, int]] = []
        for candidate in candidates:
            final_score = (
                candidate.score
                + features.click_count * 0.01
                + features.purchase_count * 0.05
            )
            # Personalization: strongly boost the user's last interacted item when present.
            if (
                features.last_item_id is not None
                and candidate.item_id == features.last_item_id
            ):
                final_score += 0.5
            ranked.append((final_score, candidate.item_id))

        ranked.sort(key=lambda row: (-row[0], row[1]))
        return [item_id for _, item_id in ranked[:5]]
