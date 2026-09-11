"""Verification for Phase 1 (Tasks 1.1–1.7)."""

from pathlib import Path

from ml.phase01_fundamentals.task_1_1_what_is_a_model import predict
from ml.phase01_fundamentals.task_1_2_features_labels import split_xy
from ml.phase01_fundamentals.task_1_3_parameters import fit_line
from ml.phase01_fundamentals.task_1_4_splits import (
    contaminated_test_indices,
    make_toy_indices,
    split_train_val_test,
    splits_are_disjoint,
)
from ml.phase01_fundamentals.task_1_6_overfit import (
    run_overfit_experiment,
    run_shuffled_label_experiment,
)
from ml.phase01_fundamentals.task_1_7_leakage import LEAKAGE_LESSON, run_leakage_experiment

FAMILIES_NOTE = Path(__file__).with_name("task_1_5_supervised_families.md")


def test_predict_x3_is_7() -> None:
    assert predict(3) == 7


def test_split_xy_lengths_and_features_exclude_labels() -> None:
    rows = [{"x": 0, "y": 1}, {"x": 3, "y": 7}, {"x": 4, "y": 9}]
    X, y = split_xy(rows)
    assert len(X) == len(y) == 3
    assert X == [0, 3, 4]
    assert y == [1, 7, 9]
    assert "y" not in str(X)


def test_learned_slope_near_2() -> None:
    model = fit_line(true_slope=2.0)
    assert 1.5 <= float(model.coef_[0]) <= 2.5


def test_learned_slope_near_5_when_truth_is_5() -> None:
    model = fit_line(true_slope=5.0)
    assert 4.5 <= float(model.coef_[0]) <= 5.5


def test_train_val_test_indices_are_disjoint() -> None:
    train, val, test = split_train_val_test(make_toy_indices(30))
    assert splits_are_disjoint(train, val, test)
    assert len(train) + len(val) + len(test) == 30


def test_leaking_test_into_train_creates_overlap() -> None:
    train, _, test = split_train_val_test(make_toy_indices(30))
    leaked = contaminated_test_indices(train, test)
    assert set(test.tolist()).issubset(set(leaked.tolist()))


def test_supervised_families_note_exists() -> None:
    text = FAMILIES_NOTE.read_text(encoding="utf-8").lower()
    assert FAMILIES_NOTE.is_file()
    for word in ("classification", "regression", "ranking", "unsupervised", "k-means"):
        assert word in text


def test_overfit_complex_wins_train_loses_test() -> None:
    r = run_overfit_experiment(seed=0)
    assert r.complex_train_mse < r.simple_train_mse
    assert r.complex_test_mse > r.simple_test_mse


def test_shuffled_labels_hurt_test_error() -> None:
    s = run_shuffled_label_experiment(seed=0)
    # No signal in train y vs x: test MSE should be large relative to a fitted line on real y=2x+1
    # (typical MSE on y in ~[1, 3] would be << 1 if learned; shuffled is much worse).
    assert s.complex_test_mse > 0.5
    assert s.simple_test_mse > 0.5


def test_leakage_accuracy_drops_without_label_column() -> None:
    r = run_leakage_experiment(seed=0)
    assert r.leaky_test_accuracy >= 0.99
    assert r.honest_test_accuracy < r.leaky_test_accuracy
    assert "serving time" in LEAKAGE_LESSON
