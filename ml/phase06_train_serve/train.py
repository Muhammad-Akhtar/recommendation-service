"""Task 6.2 — Fit a scaler+logreg Pipeline and persist it.

Offline only: Phase 2 rows + temporal split. The Pipeline must be saved as
one artifact so serving never fits a new scaler on request traffic.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ml.phase02_features.splits import max_timestamp, min_timestamp, temporal_split
from ml.phase03_classical_ml.train_logreg import labeled_matrix, prepared_rows
from ml.phase05_evaluation.classification_metrics import classification_report
from ml.phase06_train_serve.schema import (
    ARTIFACT_PATH,
    ARTIFACTS_DIR,
    FEATURE_NAMES,
    FEATURE_SCHEMA_VERSION,
    META_PATH,
    MODEL_VERSION,
    REPO_ROOT,
)


def build_pipeline(*, C: float = 1.0) -> Pipeline:
    return Pipeline(
        [
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(C=C, max_iter=1000, solver="lbfgs")),
        ]
    )


def train_artifact(
    *,
    artifact_path: Path = ARTIFACT_PATH,
    meta_path: Path = META_PATH,
    C: float = 1.0,
    feature_names: list[str] | None = None,
) -> tuple[Pipeline, dict]:
    names = list(feature_names) if feature_names is not None else list(FEATURE_NAMES)
    train, test = temporal_split(prepared_rows())
    X_train, y_train = _matrix(train, names)
    X_test, y_test = _matrix(test, names)
    pipeline = build_pipeline(C=C)
    pipeline.fit(X_train, y_train)
    proba = pipeline.predict_proba(X_test)
    metrics = classification_report(y_test, proba)

    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, artifact_path)

    try:
        artifact_ref = artifact_path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        artifact_ref = artifact_path.as_posix()
    meta = {
        "model_version": MODEL_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "feature_names": names,
        "trained_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "sklearn_version": sklearn.__version__,
        "n_train": len(train),
        "n_test": len(test),
        "train_max_timestamp": max_timestamp(train),
        "test_min_timestamp": min_timestamp(test),
        "C": C,
        "metrics": {k: _json_float(v) for k, v in metrics.items()},
        "artifact": artifact_ref,
    }
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return pipeline, meta


def _matrix(rows, names: list[str]):
    if names == list(FEATURE_NAMES):
        return labeled_matrix(rows)
    import numpy as np

    X = []
    for row in rows:
        X.append([float(row[name]) for name in names])
    y = np.array([int(row["clicked"]) for row in rows], dtype=int)
    return np.asarray(X, dtype=float), y


def _json_float(value: float) -> float | None:
    if value != value or abs(value) == float("inf"):
        return None
    return float(value)


def main() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    pipeline, meta = train_artifact()
    loaded = joblib.load(ARTIFACT_PATH)
    X, _ = labeled_matrix(prepared_rows()[:3])
    original = pipeline.predict_proba(X)
    round_trip = loaded.predict_proba(X)
    print("wrote", ARTIFACT_PATH)
    print("meta", META_PATH)
    print("metrics", meta["metrics"])
    print("round_trip_ok", (original == round_trip).all())


if __name__ == "__main__":
    main()
