"""Task 3.5 — Compare ML P(click) order to the production v2 heuristic.

Constants copied from `app/model.py` SimpleRecommendationModelV2. We do not
import Redis or call FastAPI. No claim that ML is better — Phase 5 measures
ranking.
"""

from __future__ import annotations

from typing import Any

from ml.phase02_features.toy_events import ITEM_SCORES
from ml.phase03_classical_ml.rank_with_proba import (
    candidate_row,
    rank_held_out_user,
    user_snapshot,
)
from ml.phase03_classical_ml.train_logreg import prepared_rows

# Copied from app/model.py — guessed weights, not learned.
V2_CLICK_WEIGHT = 0.01
V2_PURCHASE_WEIGHT = 0.05
V2_LAST_ITEM_BOOST = 0.5


def v2_score(
    item_score: float,
    click_count: int,
    purchase_count: int,
    last_item_id: int | None,
    item_id: int,
) -> float:
    final_score = (
        float(item_score)
        + int(click_count) * V2_CLICK_WEIGHT
        + int(purchase_count) * V2_PURCHASE_WEIGHT
    )
    if last_item_id is not None and int(item_id) == int(last_item_id):
        final_score += V2_LAST_ITEM_BOOST
    return final_score


def comparison_table(
    user_id: int = 123,
    catalog: dict[int, float] | None = None,
) -> list[dict[str, Any]]:
    items = catalog if catalog is not None else ITEM_SCORES
    rows = prepared_rows()
    snapshot = user_snapshot(rows, user_id)
    ml_ids, model = rank_held_out_user(user_id)
    ml_rank = {item_id: rank for rank, item_id in enumerate(ml_ids, start=1)}

    scored: list[dict[str, Any]] = []
    for item_id, item_score in items.items():
        feat = candidate_row(snapshot, item_id, item_score)
        p_click = float(model.predict_proba([list(feat[k] for k in (
            "click_count_before",
            "purchase_count_before",
            "item_score",
            "same_as_last_item",
            "has_last_item",
        ))])[0, 1])
        heuristic = v2_score(
            item_score,
            int(snapshot.get("click_count_before") or 0),
            int(snapshot.get("purchase_count_before") or 0),
            snapshot.get("last_item_id_before"),
            item_id,
        )
        scored.append(
            {
                "item_id": item_id,
                "v2_score": heuristic,
                "p_click": p_click,
                "ml_rank_top5": ml_rank.get(item_id),
            }
        )
    scored.sort(key=lambda row: (-row["v2_score"], row["item_id"]))
    for rank, row in enumerate(scored, start=1):
        row["v2_rank"] = rank
    return scored


def main() -> None:
    table = comparison_table(123)
    print(f"{'item':>6} {'v2_score':>10} {'p_click':>10} {'v2_rank':>8} {'ml_top5':>8}")
    for row in table[:10]:
        print(
            f"{row['item_id']:6d} {row['v2_score']:10.4f} {row['p_click']:10.4f} "
            f"{row['v2_rank']:8d} {str(row['ml_rank_top5'] or '-'):>8}"
        )
    print("No winner claimed — Phase 5 will score NDCG@5.")


if __name__ == "__main__":
    main()
