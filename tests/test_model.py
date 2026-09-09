import pytest

from app.features import UserFeatures
from app.model import SimpleRecommendationModel, SimpleRecommendationModelV2
from app.model_registry import get_model
from app.recommendation_repository import RecommendationCandidate


CANDIDATES = [
    RecommendationCandidate(item_id=10, score=0.95),
    RecommendationCandidate(item_id=20, score=0.91),
    RecommendationCandidate(item_id=30, score=0.88),
    RecommendationCandidate(item_id=40, score=0.84),
    RecommendationCandidate(item_id=50, score=0.80),
    RecommendationCandidate(item_id=60, score=0.76),
    RecommendationCandidate(item_id=90, score=0.65),
]


def test_v1_ranks_by_candidate_score_regardless_of_features():
    model = get_model("v1")
    features = UserFeatures(user_id=123, purchase_count=2, click_count=5)
    assert model.predict(features, CANDIDATES) == [10, 20, 30, 40, 50]
    assert model.version == "v1"


def test_v1_cold_user_same_popularity_top5():
    model = get_model("v1")
    features = UserFeatures(user_id=123)
    assert model.predict(features, CANDIDATES) == [10, 20, 30, 40, 50]


def test_v2_boosts_last_item_into_top_results():
    model = get_model("v2")
    assert isinstance(model, SimpleRecommendationModelV2)
    assert model.version == "v2"

    features = UserFeatures(
        user_id=123,
        click_count=10,
        purchase_count=2,
        last_item_id=90,
    )
    result = model.predict(features, CANDIDATES)
    assert result[0] == 90
    assert set(result).issubset({10, 20, 30, 40, 50, 60, 90})


def test_v2_cold_user_matches_popularity_order():
    model = get_model("v2")
    features = UserFeatures(user_id=1)
    assert model.predict(features, CANDIDATES) == [10, 20, 30, 40, 50]


def test_get_model_unknown_version():
    with pytest.raises(ValueError, match="Unknown model version"):
        get_model("v999")


def test_v1_and_v2_are_distinct_instances():
    v1 = get_model("v1")
    v2 = get_model("v2")
    assert isinstance(v1, SimpleRecommendationModel)
    assert v1.version == "v1"
    assert v2.version == "v2"
    assert v1 is not v2
