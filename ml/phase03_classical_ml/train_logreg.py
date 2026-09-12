"""Task 3.3 — Fit LogisticRegression on the Phase 2 labeled matrix.

`.fit()` searches for weights. That is the difference from v2, where the
same features are combined with constants we typed in `app/model.py`.
Do not import Redis; this is an offline table of dict rows.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression

from ml.phase02_features.encode import (
    NUMERIC_FEATURE_NAMES,
    add_missing_value_flags,
    numeric_matrix,
)
from ml.phase02_features.point_in_time import build_training_rows
from ml.phase02_features.splits import temporal_split


def prepared_rows() -> list[dict[str, Any]]:
    return add_missing_value_flags(build_training_rows())


def labeled_matrix(
    rows: list[dict[str, Any]],
) -> tuple[np.ndarray, np.ndarray]:
    X = numeric_matrix(rows)
    y = np.array([int(row["clicked"]) for row in rows], dtype=int)
    return X, y


def fit_logreg(
    train_rows: list[dict[str, Any]] | None = None,
    *,
    C: float = 1.0,
) -> tuple[LogisticRegression, list[dict[str, Any]], list[dict[str, Any]]]:
    rows = prepared_rows() if train_rows is None else train_rows
    if train_rows is None:
        train, test = temporal_split(rows)
    else:
        train, test = rows, []
    X, y = labeled_matrix(train)
    model = LogisticRegression(C=C, max_iter=1000, solver="lbfgs")
    model.fit(X, y)
    return model, train, test


def coef_table(model: LogisticRegression) -> list[tuple[str, float]]:
    return list(zip(NUMERIC_FEATURE_NAMES, (float(c) for c in model.coef_[0]), strict=True))


def main() -> None:
    model, train, test = fit_logreg()
    print("n_train", len(train), "n_test", len(test))
    print("intercept", float(model.intercept_[0]))
    for name, weight in coef_table(model):
        print(f"  {name:24s} {weight:+.4f}")
    X_test, _ = labeled_matrix(test)
    proba = model.predict_proba(X_test)
    print("predict_proba shape", proba.shape, "min", proba.min(), "max", proba.max())


if __name__ == "__main__":
    main()
