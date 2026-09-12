"""Verification for Phase 6 (Tasks 6.1–6.6)."""

from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pytest

from app.model import SimpleRecommendationModel
from app.model_registry import get_model
from ml.phase03_classical_ml.train_logreg import labeled_matrix, prepared_rows
from ml.phase06_train_serve.ranker import (
    FeatureSchemaError,
    LogisticRankingModel,
    assert_feature_alignment,
    serving_row,
)
from ml.phase06_train_serve.schema import FEATURE_NAMES, MODEL_VERSION
from ml.phase06_train_serve.train import train_artifact

PIPELINE_NOTE = Path(__file__).with_name("NOTES_pipeline.md")


@dataclass
class FakeFeatures:
    click_count: int
    purchase_count: int = 0
    last_item_id: int | None = None
    user_id: int = 123


@dataclass
class FakeCandidate:
    item_id: int
    score: float


def test_pipeline_note_forbids_infrastructure_imports() -> None:
    text = PIPELINE_NOTE.read_text(encoding="utf-8").lower()
    assert "does not import `redis` or `asyncpg`" in text or (
        "does not import" in text and "redis" in text and "asyncpg" in text
    )
    ranker = Path(__file__).with_name("ranker.py").read_text(encoding="utf-8")
    assert "\nimport redis" not in ranker
    assert "from redis" not in ranker
    assert "import asyncpg" not in ranker
    assert "from asyncpg" not in ranker


def test_artifact_round_trips_predict_proba(tmp_path: Path) -> None:
    artifact = tmp_path / "click_logreg_v3.joblib"
    meta = tmp_path / "click_logreg_v3.meta.json"
    pipeline, payload = train_artifact(artifact_path=artifact, meta_path=meta)
    assert artifact.is_file()
    assert meta.is_file()
    assert payload["feature_names"] == list(FEATURE_NAMES)
    loaded = joblib.load(artifact)
    X, _ = labeled_matrix(prepared_rows()[:4])
    np.testing.assert_allclose(pipeline.predict_proba(X), loaded.predict_proba(X))


def test_ranker_returns_at_most_three_ids_for_three_candidates(tmp_path: Path) -> None:
    artifact = tmp_path / "m.joblib"
    meta = tmp_path / "m.meta.json"
    train_artifact(artifact_path=artifact, meta_path=meta)
    model = LogisticRankingModel(artifact, meta_path=meta)
    features = FakeFeatures(click_count=2, last_item_id=10)
    candidates = [
        FakeCandidate(10, 0.95),
        FakeCandidate(20, 0.91),
        FakeCandidate(30, 0.50),
    ]
    ids = model.predict(features, candidates)
    assert 1 <= len(ids) <= 3
    assert len(ids) == len(set(ids))
    assert set(ids) <= {10, 20, 30}


def test_wrong_feature_order_is_caught() -> None:
    shuffled = list(reversed(FEATURE_NAMES))
    with pytest.raises(FeatureSchemaError):
        assert_feature_alignment(shuffled, list(FEATURE_NAMES))


def test_empty_candidates_raise(tmp_path: Path) -> None:
    artifact = tmp_path / "m.joblib"
    meta = tmp_path / "m.meta.json"
    train_artifact(artifact_path=artifact, meta_path=meta)
    model = LogisticRankingModel(artifact, meta_path=meta)
    with pytest.raises(ValueError, match="empty"):
        model.predict(FakeFeatures(click_count=0), [])


def test_production_default_is_still_v1_popularity() -> None:
    model = get_model("v1")
    assert isinstance(model, SimpleRecommendationModel)
    assert model.version == "v1"
    with pytest.raises(ValueError, match="Unknown model version"):
        get_model("v3")


def test_smoke_prints_v3_and_ids(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    artifact = tmp_path / "m.joblib"
    meta = tmp_path / "m.meta.json"
    train_artifact(artifact_path=artifact, meta_path=meta)
    model = LogisticRankingModel(artifact, meta_path=meta)
    from ml.phase02_features.toy_events import ITEM_SCORES

    candidates = [
        FakeCandidate(item_id, score) for item_id, score in list(ITEM_SCORES.items())[:8]
    ]
    ids = model.predict(FakeFeatures(click_count=2, last_item_id=10), candidates)
    assert model.version == MODEL_VERSION
    assert 1 <= len(ids) <= 5
    row = serving_row(FakeFeatures(click_count=2, last_item_id=10), FakeCandidate(10, 0.95))
    assert row["same_as_last_item"] == 1.0
    assert row["click_count_before"] == 2.0
