"""Run v1 / v2 / v3 / v3-no-purchase on the frozen temporal split."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ml.phase02_features.splits import max_timestamp, min_timestamp, temporal_split
from ml.phase02_features.toy_events import ITEM_SCORES
from ml.phase03_classical_ml.rank_with_proba import user_snapshot
from ml.phase03_classical_ml.train_logreg import prepared_rows
from ml.phase05_evaluation.compare_rankers import (
    METRIC_FNS,
    mean_ignore_none,
    relevant_by_user,
    v1_rank,
    v2_rank,
)
from ml.phase06_train_serve.ranker import LogisticRankingModel
from ml.phase06_train_serve.schema import ARTIFACT_PATH, ARTIFACTS_DIR, FEATURE_NAMES, META_PATH
from ml.phase06_train_serve.train import train_artifact

HERE = Path(__file__).resolve().parent
SPLIT_META = HERE / "split_meta.json"


@dataclass
class Feat:
    click_count: int
    purchase_count: int
    last_item_id: int | None
    user_id: int = 0


@dataclass
class Cand:
    item_id: int
    score: float


def freeze_split() -> dict[str, Any]:
    train, test = temporal_split(prepared_rows())
    meta = {
        "n_train": len(train),
        "n_test": len(test),
        "train_max_timestamp": max_timestamp(train),
        "test_min_timestamp": min_timestamp(test),
        "cutoff_rule": "temporal 70/30 on Phase 2 PIT rows",
        "n_test_users_with_positives": len(relevant_by_user(test)),
    }
    SPLIT_META.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta


def _features(snapshot: dict[str, Any]) -> Feat:
    return Feat(
        click_count=int(snapshot.get("click_count_before") or 0),
        purchase_count=int(snapshot.get("purchase_count_before") or 0),
        last_item_id=snapshot.get("last_item_id_before"),
        user_id=int(snapshot.get("user_id") or 0),
    )


def _catalog() -> list[Cand]:
    return [Cand(item_id, score) for item_id, score in ITEM_SCORES.items()]


def _mean_metrics(per_user_lists: dict[int, list[int]], relevant: dict[int, set[int]]) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for name, fn in METRIC_FNS.items():
        out[name] = mean_ignore_none(
            [fn(per_user_lists[uid], rel, 5) for uid, rel in relevant.items()]
        )
    return out


def evaluate_rankers() -> dict[str, dict[str, float | None]]:
    train, test = temporal_split(prepared_rows())
    relevant = relevant_by_user(test)
    catalog = _catalog()
    v3 = LogisticRankingModel(ARTIFACT_PATH, meta_path=META_PATH)

    variant_joblib = ARTIFACTS_DIR / "click_logreg_v3_no_purchase.joblib"
    variant_meta = ARTIFACTS_DIR / "click_logreg_v3_no_purchase.meta.json"
    names = [n for n in FEATURE_NAMES if n != "purchase_count_before"]
    train_artifact(
        artifact_path=variant_joblib,
        meta_path=variant_meta,
        feature_names=names,
    )
    v3_np = LogisticRankingModel(variant_joblib, meta_path=variant_meta)

    lists: dict[str, dict[int, list[int]]] = {
        "v1": {},
        "v2": {},
        "v3": {},
        "v3-no-purchase": {},
    }
    pop = v1_rank(5)
    for user_id in relevant:
        snap = user_snapshot(train, user_id)
        feats = _features(snap)
        lists["v1"][user_id] = pop
        lists["v2"][user_id] = v2_rank(snap, 5)
        lists["v3"][user_id] = v3.predict(feats, catalog)
        lists["v3-no-purchase"][user_id] = v3_np.predict(feats, catalog)
    return {name: _mean_metrics(per_user, relevant) for name, per_user in lists.items()}


def latency_ms(n: int = 100) -> dict[str, float]:
    train, _ = temporal_split(prepared_rows())
    snap = user_snapshot(train, 123)
    feats = _features(snap)
    catalog = _catalog()
    v3 = LogisticRankingModel(ARTIFACT_PATH, meta_path=META_PATH)

    def bench(fn) -> float:
        fn()
        start = time.perf_counter()
        for _ in range(n):
            fn()
        return (time.perf_counter() - start) * 1000 / n

    v2_ms = bench(lambda: v2_rank(snap, 5))
    v3_ms = bench(lambda: v3.predict(feats, catalog))
    return {"v2": v2_ms, "v3": v3_ms}


def main() -> None:
    split = freeze_split()
    print("split", split)
    metrics = evaluate_rankers()
    lat = latency_ms()
    print("metrics", metrics)
    print("latency_ms", lat)


if __name__ == "__main__":
    main()
