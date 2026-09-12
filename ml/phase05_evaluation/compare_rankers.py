"""Task 5.5 — Offline compare popularity (v1), heuristic (v2), ML scorer.

Lists are length K=5, matching `model.predict`. Metrics live here — never on
`GET /recommendations`. Winner on NDCG may lose on pointwise accuracy.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from ml.phase02_features.splits import temporal_split
from ml.phase02_features.toy_events import ITEM_SCORES
from ml.phase03_classical_ml.compare_v2 import v2_score
from ml.phase03_classical_ml.rank_with_proba import rank_candidates, user_snapshot
from ml.phase03_classical_ml.train_logreg import fit_logreg, prepared_rows
from ml.phase05_evaluation.ranking_metrics import (
    K_DEFAULT,
    average_precision_at_k,
    hit_rate_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)

METRIC_FNS = {
    "precision@5": precision_at_k,
    "recall@5": recall_at_k,
    "hit_rate@5": hit_rate_at_k,
    "map@5": average_precision_at_k,
    "ndcg@5": ndcg_at_k,
}


def v1_rank(k: int = K_DEFAULT) -> list[int]:
    ordered = sorted(ITEM_SCORES.items(), key=lambda item: (-item[1], item[0]))
    return [item_id for item_id, _ in ordered[:k]]


def v2_rank(snapshot: dict[str, Any], k: int = K_DEFAULT) -> list[int]:
    scored = []
    last = snapshot.get("last_item_id_before")
    clicks = int(snapshot.get("click_count_before") or 0)
    purchases = int(snapshot.get("purchase_count_before") or 0)
    for item_id, item_score in ITEM_SCORES.items():
        scored.append(
            (
                v2_score(item_score, clicks, purchases, last, item_id),
                int(item_id),
            )
        )
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [item_id for _, item_id in scored[:k]]


def relevant_by_user(test_rows: list[dict[str, Any]]) -> dict[int, set[int]]:
    mapping: dict[int, set[int]] = defaultdict(set)
    for row in test_rows:
        if int(row["clicked"]) != 1:
            continue
        mapping[int(row["user_id"])].add(int(row["item_id"]))
    return dict(mapping)


def mean_ignore_none(values: list[float | None]) -> float | None:
    kept = [v for v in values if v is not None]
    if not kept:
        return None
    return sum(kept) / len(kept)


def compare_systems(k: int = K_DEFAULT) -> dict[str, dict[str, float | None]]:
    rows = prepared_rows()
    train, test = temporal_split(rows)
    model, _, _ = fit_logreg(train)
    relevant = relevant_by_user(test)
    lists = {
        "popularity_v1": {},
        "heuristic_v2": {},
        "ml_logreg": {},
    }
    catalog_pop = v1_rank(k)
    for user_id, rel in relevant.items():
        snapshot = user_snapshot(train, user_id)
        lists["popularity_v1"][user_id] = catalog_pop
        lists["heuristic_v2"][user_id] = v2_rank(snapshot, k)
        lists["ml_logreg"][user_id] = rank_candidates(model, snapshot, k=k)

    summary: dict[str, dict[str, float | None]] = {}
    for system, per_user in lists.items():
        summary[system] = {}
        for metric_name, fn in METRIC_FNS.items():
            summary[system][metric_name] = mean_ignore_none(
                [fn(per_user[user_id], rel, k) for user_id, rel in relevant.items()]
            )
    return summary


def markdown_table(summary: dict[str, dict[str, float | None]]) -> str:
    metrics = list(METRIC_FNS)
    header = "| System | " + " | ".join(metrics) + " |"
    sep = "| --- | " + " | ".join("---" for _ in metrics) + " |"
    lines = [header, sep]
    for system, scores in summary.items():
        cells = []
        for metric in metrics:
            value = scores[metric]
            cells.append("—" if value is None else f"{value:.3f}")
        lines.append("| " + system + " | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main() -> None:
    summary = compare_systems()
    print(markdown_table(summary))


if __name__ == "__main__":
    main()
