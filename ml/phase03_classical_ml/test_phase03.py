"""Verification for Phase 3 (Tasks 3.1–3.6)."""

import math

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from ml.phase02_features.encode import NUMERIC_FEATURE_NAMES
from ml.phase03_classical_ml.compare_v2 import comparison_table, v2_score
from ml.phase03_classical_ml.rank_with_proba import rank_held_out_user
from ml.phase03_classical_ml.sigmoid import (
    EXAMPLE_ROW,
    EXAMPLE_Z,
    sigmoid,
    weighted_logit,
)
from ml.phase03_classical_ml.train_logreg import (
    coef_table,
    fit_logreg,
    labeled_matrix,
    prepared_rows,
)
from ml.phase03_classical_ml.train_tree import fit_tree


def test_sigmoid_zero_is_half_and_monotone() -> None:
    assert sigmoid(0.0) == 0.5
    assert sigmoid(2.0) > sigmoid(0.0)
    assert sigmoid(-2.0) < 0.5
    assert sigmoid(2.0) < 1.0


def test_weighted_example_matches_comment_arithmetic() -> None:
    z = weighted_logit(EXAMPLE_ROW)
    assert abs(z - EXAMPLE_Z) < 1e-9
    expected = 2.0 * 0.95 + 0.01 * 2 + 0.05 * 1 + 0.5 * 1 - 1.2
    assert abs(z - expected) < 1e-9
    assert 0.0 < sigmoid(z) < 1.0


def test_logreg_predict_proba_shape_and_range() -> None:
    model, train, test = fit_logreg()
    assert len(train) > 0 and len(test) > 0
    X_test, _ = labeled_matrix(test)
    proba = model.predict_proba(X_test)
    assert proba.shape == (len(test), 2)
    assert float(np.min(proba)) >= 0.0
    assert float(np.max(proba)) <= 1.0
    names = [name for name, _ in coef_table(model)]
    assert names == list(NUMERIC_FEATURE_NAMES)


def test_ranker_returns_unique_item_ids_length_at_most_5() -> None:
    ids, _ = rank_held_out_user(123, k=5)
    assert isinstance(ids, list)
    assert all(isinstance(item_id, int) for item_id in ids)
    assert 1 <= len(ids) <= 5
    assert len(ids) == len(set(ids))


def test_v2_formula_matches_copied_constants() -> None:
    # last-item boost 0.5, click 0.01, purchase 0.05 — same as app/model.py
    assert abs(v2_score(0.95, 2, 1, 10, 10) - (0.95 + 0.02 + 0.05 + 0.5)) < 1e-9
    table = comparison_table(123)
    assert {row["item_id"] for row in table}
    assert all("v2_score" in row and "p_click" in row for row in table)


def test_tree_uses_our_features_and_reports_test_split() -> None:
    tree, train_acc, test_acc, text = fit_tree()
    assert 0.0 <= test_acc <= 1.0
    assert train_acc >= 0.0
    used = any(float(imp) > 0 for imp in tree.feature_importances_)
    assert used
    assert any(name in text for name in NUMERIC_FEATURE_NAMES)


def test_all_zero_labels_cannot_fit_two_class_logreg() -> None:
    rows = prepared_rows()
    X, _ = labeled_matrix(rows)
    y = np.zeros(len(rows), dtype=int)
    model = LogisticRegression(max_iter=200)
    try:
        model.fit(X, y)
        fitted = True
    except ValueError:
        fitted = False
    assert fitted is False


def test_unscaled_item_score_shrinks_after_standardscaler() -> None:
    rows = prepared_rows()
    X, y = labeled_matrix(rows)
    X_blown = X.copy()
    score_col = list(NUMERIC_FEATURE_NAMES).index("item_score")
    X_blown[:, score_col] *= 1000.0
    raw = LogisticRegression(max_iter=1000).fit(X_blown, y)
    scaled = LogisticRegression(max_iter=1000)
    Xs = StandardScaler().fit_transform(X_blown)
    scaled.fit(Xs, y)
    assert abs(float(raw.coef_[0, score_col])) != abs(float(scaled.coef_[0, score_col]))


def test_stronger_regularization_shrinks_coefficients() -> None:
    model_weak, _, _ = fit_logreg(C=100.0)
    model_strong, _, _ = fit_logreg(C=0.1)
    weak = float(np.linalg.norm(model_weak.coef_))
    strong = float(np.linalg.norm(model_strong.coef_))
    assert strong <= weak + 1e-9
    assert math.isfinite(weak) and math.isfinite(strong)
