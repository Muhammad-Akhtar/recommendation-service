"""Task 6.3–6.4 — Pure v3 ranker: load artifact, score candidates, no I/O.

`predict(features, candidates) -> list[int]` matches production. Features are
UserFeatures-shaped (click_count, purchase_count, last_item_id). Candidates
expose `item_id` and `score`. This module does not import redis or asyncpg.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

import joblib
import numpy as np

from ml.phase06_train_serve.schema import (
    ARTIFACT_PATH,
    FEATURE_NAMES,
    FEATURE_SCHEMA_VERSION,
    META_PATH,
    MODEL_VERSION,
    TOP_K,
)


class FeatureSchemaError(ValueError):
    """Serving feature names / schema do not match the artifact metadata."""


class FeaturesLike(Protocol):
    click_count: int
    purchase_count: int
    last_item_id: int | None


class CandidateLike(Protocol):
    item_id: int
    score: float


def load_meta(meta_path: Path = META_PATH) -> dict[str, Any]:
    return json.loads(meta_path.read_text(encoding="utf-8"))


def assert_feature_alignment(
    names: list[str],
    expected: list[str] | None = None,
) -> None:
    want = list(expected) if expected is not None else list(FEATURE_NAMES)
    if names != want:
        raise FeatureSchemaError(
            f"feature names {names} do not match artifact schema {want}"
        )


def assert_schema_version(
    meta: dict[str, Any],
    expected: str = FEATURE_SCHEMA_VERSION,
) -> None:
    got = meta.get("feature_schema_version")
    if got != expected:
        raise FeatureSchemaError(
            f"feature_schema_version {got!r} does not match serving {expected!r}"
        )


def serving_row(features: FeaturesLike, candidate: CandidateLike) -> dict[str, float]:
    last = features.last_item_id
    return {
        "click_count_before": float(features.click_count),
        "purchase_count_before": float(features.purchase_count),
        "item_score": float(candidate.score),
        "same_as_last_item": float(
            last is not None and int(last) == int(candidate.item_id)
        ),
        "has_last_item": float(last is not None),
    }


def matrix_from_rows(
    rows: list[dict[str, float]],
    feature_names: list[str],
) -> np.ndarray:
    assert_feature_alignment(feature_names, feature_names)
    return np.asarray(
        [[float(row[name]) for name in feature_names] for row in rows],
        dtype=float,
    )


class LogisticRankingModel:
    """v3 — sklearn Pipeline artifact. No Redis/Postgres/Kafka."""

    def __init__(
        self,
        artifact_path: Path | str = ARTIFACT_PATH,
        *,
        meta_path: Path | str | None = None,
        require_schema_version: bool = True,
    ) -> None:
        self.version = MODEL_VERSION
        self.artifact_path = Path(artifact_path)
        self.meta_path = Path(meta_path) if meta_path is not None else META_PATH
        self.pipeline = joblib.load(self.artifact_path)
        self.meta = load_meta(self.meta_path)
        self.feature_names = list(self.meta["feature_names"])
        unknown = [name for name in self.feature_names if name not in FEATURE_NAMES]
        if unknown:
            raise FeatureSchemaError(f"unknown serving features {unknown}")
        if require_schema_version:
            assert_schema_version(self.meta)

    def predict(
        self,
        features: FeaturesLike,
        candidates: list[CandidateLike],
        *,
        k: int = TOP_K,
    ) -> list[int]:
        if not candidates:
            raise ValueError("candidates must not be empty")
        rows = [serving_row(features, candidate) for candidate in candidates]
        # Named columns from meta.json — never a silent positional shuffle.
        X = np.asarray(
            [[row[name] for name in self.feature_names] for row in rows],
            dtype=float,
        )
        p_click = self.pipeline.predict_proba(X)[:, 1]
        scored = sorted(
            zip((int(c.item_id) for c in candidates), p_click, strict=True),
            key=lambda pair: (-float(pair[1]), pair[0]),
        )
        ranked: list[int] = []
        for item_id, _ in scored:
            if item_id not in ranked:
                ranked.append(item_id)
            if len(ranked) >= k:
                break
        return ranked


def main() -> None:
    """Task 6.6 — smoke inference for a synthetic user with click_count=2."""
    from dataclasses import dataclass

    from ml.phase02_features.toy_events import ITEM_SCORES

    @dataclass
    class Features:
        click_count: int
        purchase_count: int
        last_item_id: int | None
        user_id: int = 123

    @dataclass
    class Candidate:
        item_id: int
        score: float

    model = LogisticRankingModel()
    features = Features(click_count=2, purchase_count=0, last_item_id=10)
    candidates = [
        Candidate(item_id=item_id, score=score)
        for item_id, score in ITEM_SCORES.items()
    ]
    ids = model.predict(features, candidates)
    print(f"model_version={model.version} ids={ids}")


if __name__ == "__main__":
    main()
