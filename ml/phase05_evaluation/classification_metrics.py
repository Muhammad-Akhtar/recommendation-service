"""Task 5.1–5.2 — Pointwise click-model metrics vs a dummy baseline.

Accuracy is the wrong headline for recommendations (class imbalance + order).
We still compute it so we can watch DummyClassifier(strategy="most_frequent")
win accuracy while losing ROC-AUC or log loss.
"""

from __future__ import annotations

import math

import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)

from ml.phase03_classical_ml.train_logreg import fit_logreg, labeled_matrix


def classification_report(y_true: np.ndarray, proba: np.ndarray) -> dict[str, float]:
    y_hat = (proba[:, 1] >= 0.5).astype(int)
    out = {
        "accuracy": float(accuracy_score(y_true, y_hat)),
        "precision": float(precision_score(y_true, y_hat, zero_division=0)),
        "recall": float(recall_score(y_true, y_hat, zero_division=0)),
        "f1": float(f1_score(y_true, y_hat, zero_division=0)),
        "log_loss": float(log_loss(y_true, proba, labels=[0, 1])),
    }
    if len(set(y_true.tolist())) > 1:
        out["roc_auc"] = float(roc_auc_score(y_true, proba[:, 1]))
    else:
        out["roc_auc"] = float("nan")
    return out


def evaluate_logreg_and_dummy() -> dict[str, dict[str, float]]:
    model, _train, test = fit_logreg()
    X_test, y_test = labeled_matrix(test)
    ml_proba = model.predict_proba(X_test)
    dummy = DummyClassifier(strategy="most_frequent")
    X_train, y_train = labeled_matrix(_train)
    dummy.fit(X_train, y_train)
    dummy_proba = dummy.predict_proba(X_test)
    return {
        "ml": classification_report(y_test, ml_proba),
        "dummy_most_frequent": classification_report(y_test, dummy_proba),
    }


def all_finite(metrics: dict[str, float]) -> bool:
    for key, value in metrics.items():
        if key == "roc_auc" and value != value:
            continue
        if not math.isfinite(value):
            return False
    return True


def main() -> None:
    reports = evaluate_logreg_and_dummy()
    for name, metrics in reports.items():
        print(name, metrics)


if __name__ == "__main__":
    main()
