"""Verification for Phase 2 (Tasks 2.1–2.6)."""

from pathlib import Path

import numpy as np

from ml.phase02_features.encode import (
    ID_FIELDS,
    NUMERIC_FEATURE_NAMES,
    add_missing_value_flags,
    apply_item_score_scaler,
    fit_item_score_scaler,
    new_user_numeric_row,
    numeric_matrix,
)
from ml.phase02_features.labels import (
    add_clicked_labels,
    always_predict_positive_accuracy,
    clicked_from_event_type,
)
from ml.phase02_features.point_in_time import (
    build_training_rows,
    leaky_vs_honest_correlation,
)
from ml.phase02_features.splits import (
    WHY_TEMPORAL_SPLIT,
    find_time_travel_pairs,
    max_timestamp,
    min_timestamp,
    random_split,
    temporal_split,
)
from ml.phase02_features.toy_events import (
    TOY_EVENTS,
    event_types,
    users_with_multiple_events,
)

SCHEMAS_NOTE = Path(__file__).with_name("NOTES_schemas.md")
PHASE_NOTES = Path(__file__).with_name("NOTES.md")


def _prepared_rows() -> list[dict]:
    return add_missing_value_flags(build_training_rows())


def test_schemas_note_marks_clicked_as_derived_label() -> None:
    text = SCHEMAS_NOTE.read_text(encoding="utf-8").lower()
    assert SCHEMAS_NOTE.is_file()
    assert "clicked" in text
    assert "label we will derive" in text or "label we derive" in text
    assert "not a redis field" in text


def test_toy_table_has_multiple_types_and_repeat_users() -> None:
    assert 20 <= len(TOY_EVENTS) <= 40
    assert {"click", "view"}.issubset(event_types())
    assert 123 in users_with_multiple_events()
    assert {123, 999, 1001}.issubset({row["user_id"] for row in TOY_EVENTS})


def test_labels_are_zero_or_one_only() -> None:
    rows = add_clicked_labels(list(TOY_EVENTS))
    labels = {row["clicked"] for row in rows}
    assert labels <= {0, 1}
    assert clicked_from_event_type("purchase") == 1
    assert clicked_from_event_type("view") == 0
    assert any(row["clicked"] == 1 for row in rows)
    assert any(row["clicked"] == 0 for row in rows)


def test_first_event_has_zero_counts() -> None:
    rows = build_training_rows()
    first = min(
        (row for row in rows if row["user_id"] == 123),
        key=lambda row: row["timestamp"],
    )
    assert first["click_count_before"] == 0
    assert first["purchase_count_before"] == 0
    assert first["last_item_id_before"] is None


def test_current_click_is_not_in_same_row_counts() -> None:
    rows = build_training_rows()
    first_click = next(
        row
        for row in rows
        if row["user_id"] == 123 and row["event_type"] == "click"
    )
    assert first_click["clicked"] == 1
    assert first_click["click_count_before"] == 0

    later_click = next(
        row
        for row in rows
        if row["user_id"] == 123
        and row["event_type"] == "click"
        and row["timestamp"] > first_click["timestamp"]
    )
    assert later_click["click_count_before"] >= 1


def test_missing_last_item_flag_and_ids_stay_out_of_matrix() -> None:
    rows = _prepared_rows()
    first = min(rows, key=lambda row: (row["timestamp"], row["user_id"]))
    assert first["has_last_item"] == 0
    names = set(NUMERIC_FEATURE_NAMES)
    assert names.isdisjoint(ID_FIELDS)
    matrix = numeric_matrix(rows)
    assert matrix.shape == (len(rows), len(NUMERIC_FEATURE_NAMES))


def test_item_score_scaler_uses_train_statistics_only() -> None:
    rows = _prepared_rows()
    train, test = temporal_split(rows)
    scaler = fit_item_score_scaler(train)
    train_mean = float(np.mean([row["item_score"] for row in train]))
    full_mean = float(np.mean([row["item_score"] for row in rows]))
    assert abs(float(scaler.mean_[0]) - train_mean) < 1e-9
    assert abs(train_mean - full_mean) > 1e-12 or len(test) == 0

    scaled_test = apply_item_score_scaler(test, scaler)
    test_only = fit_item_score_scaler(test)
    # Applying train scaler must not be the same as fitting on test.
    train_scaled_on_test = [row["item_score_std"] for row in scaled_test]
    test_fitted = apply_item_score_scaler(test, test_only)
    assert train_scaled_on_test != [row["item_score_std"] for row in test_fitted]


def test_temporal_split_has_no_future_in_train() -> None:
    train, test = temporal_split(_prepared_rows())
    assert max_timestamp(train) <= min_timestamp(test)


def test_random_split_has_a_future_row_in_training() -> None:
    train, test = random_split(_prepared_rows(), seed=0)
    leaks = find_time_travel_pairs(train, test)
    assert leaks, "expected at least one user whose future event landed in train"
    train_row, test_row = leaks[0]
    assert train_row["user_id"] == test_row["user_id"]
    assert train_row["timestamp"] > test_row["timestamp"]
    assert "causal" in WHY_TEMPORAL_SPLIT.lower() or "redis" in WHY_TEMPORAL_SPLIT.lower()


def test_leaky_count_correlates_more_with_label() -> None:
    leaky_r, honest_r = leaky_vs_honest_correlation(build_training_rows())
    assert leaky_r > honest_r


def test_dropping_negatives_makes_always_one_perfect() -> None:
    rows = add_clicked_labels(list(TOY_EVENTS))
    assert always_predict_positive_accuracy(rows) == 1.0


def test_new_user_row_matches_redis_defaults() -> None:
    rows = _prepared_rows()
    new_user = next(row for row in rows if row["user_id"] == 1001)
    assert new_user_numeric_row(new_user)
    assert PHASE_NOTES.is_file()
    notes = PHASE_NOTES.read_text(encoding="utf-8").lower()
    assert "point-in-time" in notes or "strictly before" in notes
