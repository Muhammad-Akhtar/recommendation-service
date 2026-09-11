"""Task 1.7 — Data leakage.

If a feature is a copy of the label, a classifier can 'perfectly' predict
without learning anything usable at serving time.

In the recommendation service this would look like training on clicks that
happen *after* the prediction, or on Redis counts that already include the
label event (Phase 2 covers that on real fields).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


@dataclass(frozen=True)
class LeakageResult:
    leaky_test_accuracy: float
    honest_test_accuracy: float


def make_classification_table(n: int = 80, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """y is correlated with x, but not identical — honest features are imperfect."""
    rng = np.random.default_rng(seed)
    x = rng.normal(0, 1.0, size=n)
    y = (x + rng.normal(0, 0.85, size=n) > 0).astype(int)
    return x.reshape(-1, 1), y


def run_leakage_experiment(seed: int = 0) -> LeakageResult:
    x, y = make_classification_table(seed=seed)
    leaky = y.reshape(-1, 1).astype(float)
    X_leaky = np.hstack([x, leaky])  # second column *is* the label
    X_honest = x

    X_train_l, X_test_l, y_train, y_test = train_test_split(
        X_leaky, y, test_size=0.3, random_state=seed, stratify=y
    )
    X_train_h, X_test_h, _, _ = train_test_split(
        X_honest, y, test_size=0.3, random_state=seed, stratify=y
    )

    leaky_clf = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=500, random_state=seed),
    )
    honest_clf = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=500, random_state=seed),
    )
    leaky_clf.fit(X_train_l, y_train)
    honest_clf.fit(X_train_h, y_train)

    return LeakageResult(
        leaky_test_accuracy=float(accuracy_score(y_test, leaky_clf.predict(X_test_l))),
        honest_test_accuracy=float(accuracy_score(y_test, honest_clf.predict(X_test_h))),
    )


LEAKAGE_LESSON = (
    "this is why we must not train on data unavailable at serving time"
)


def main() -> None:
    r = run_leakage_experiment()
    print(f"With leaky=y column:    test accuracy={r.leaky_test_accuracy:.3f}")
    print(f"Without leaky column:   test accuracy={r.honest_test_accuracy:.3f}")
    print(LEAKAGE_LESSON)


if __name__ == "__main__":
    main()
