"""Verification for Phase 7 (Tasks 7.1–7.6)."""

import json
from pathlib import Path

import pytest

from ml.phase02_features.point_in_time import build_training_rows
from ml.phase02_features.toy_events import TOY_EVENTS
from ml.phase06_train_serve.ranker import FeatureSchemaError, LogisticRankingModel
from ml.phase06_train_serve.train import train_artifact
from ml.phase07_feature_store.feature_rules import apply_event, empty_state
from ml.phase07_feature_store.replay import replay, replay_before
from ml.phase07_feature_store.skew_experiment import run_skew_experiment

TWO_PATHS = Path(__file__).with_name("NOTES_two_paths.md")
FRESHNESS = Path(__file__).with_name("NOTES_freshness.md")
SKEW_NOTES = Path(__file__).with_name("NOTES.md")


def test_each_serving_feature_has_a_training_counterpart() -> None:
    text = TWO_PATHS.read_text(encoding="utf-8")
    for serving, training in (
        ("click_count", "click_count_before"),
        ("purchase_count", "purchase_count_before"),
        ("last_item_id", "last_item_id_before"),
        ("candidate.score", "item_score"),
    ):
        assert serving in text
        assert training in text


def test_replay_three_events_matches_redis_rules() -> None:
    state = empty_state(123)
    state = apply_event(state, {"event_type": "click", "item_id": 10})
    state = apply_event(state, {"event_type": "click", "item_id": 20})
    state = apply_event(state, {"event_type": "purchase", "item_id": 30})
    assert state.click_count == 2
    assert state.purchase_count == 1
    assert state.last_item_id == 30


def test_view_only_updates_last_item() -> None:
    state = apply_event(empty_state(1), {"event_type": "view", "item_id": 94})
    assert state.click_count == 0
    assert state.purchase_count == 0
    assert state.last_item_id == 94


def test_pit_and_all_events_disagree_for_an_early_click() -> None:
    rows = build_training_rows()
    first_click = next(
        row
        for row in rows
        if row["user_id"] == 123 and row["event_type"] == "click"
    )
    pit = replay_before(list(TOY_EVENTS), 123, first_click["timestamp"])
    current = replay(list(TOY_EVENTS), user_id=123)[123]
    assert pit.click_count == 0
    assert current.click_count > pit.click_count
    assert first_click["click_count_before"] == pit.click_count


def test_skew_experiment_records_a_drop() -> None:
    scores = run_skew_experiment()
    notes = SKEW_NOTES.read_text(encoding="utf-8")
    assert scores["leaked_on_pit_roc_auc"] < scores["honest_roc_auc"]
    assert "0.560" in notes or "0.56" in notes
    assert "leak" in notes.lower()


def test_freshness_note_links_defaults_to_cold_start() -> None:
    text = FRESHNESS.read_text(encoding="utf-8").lower()
    assert "get_user_features" in text
    assert "cold" in text
    assert "circuit" in text


def test_schema_mismatch_raises(tmp_path: Path) -> None:
    artifact = tmp_path / "m.joblib"
    meta_path = tmp_path / "m.meta.json"
    _, meta = train_artifact(artifact_path=artifact, meta_path=meta_path)
    meta["feature_schema_version"] = "fs-wrong"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(FeatureSchemaError, match="feature_schema_version"):
        LogisticRankingModel(artifact, meta_path=meta_path, require_schema_version=True)
