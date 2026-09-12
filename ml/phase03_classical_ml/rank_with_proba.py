"""Task 3.4 — Rank candidates by P(click) for one held-out user.

Same *output shape* as production `model.predict`: `list[int]` of item ids,
length ≤ 5. Scoring uses `predict_proba[:, 1]`, not hard `predict` (0.5 is
not a ranking).
"""

from __future__ import annotations

from typing import Any

from sklearn.linear_model import LogisticRegression

from ml.phase02_features.encode import numeric_matrix
from ml.phase02_features.toy_events import ITEM_SCORES
from ml.phase03_classical_ml.train_logreg import fit_logreg, labeled_matrix, prepared_rows

TOP_K = 5


def user_snapshot(rows: list[dict[str, Any]], user_id: int) -> dict[str, Any]:
    """Latest point-in-time feature row for this user (or Redis-like zeros)."""
    owned = [row for row in rows if int(row["user_id"]) == user_id]
    if not owned:
        return {
            "user_id": user_id,
            "click_count_before": 0,
            "purchase_count_before": 0,
            "last_item_id_before": None,
            "has_last_item": 0,
            "same_as_last_item": 0,
        }
    return max(owned, key=lambda row: row["timestamp"])


def candidate_row(snapshot: dict[str, Any], item_id: int, item_score: float) -> dict[str, Any]:
    last = snapshot.get("last_item_id_before")
    return {
        "click_count_before": int(snapshot.get("click_count_before") or 0),
        "purchase_count_before": int(snapshot.get("purchase_count_before") or 0),
        "item_score": float(item_score),
        "same_as_last_item": int(last is not None and int(last) == int(item_id)),
        "has_last_item": int(last is not None),
        "item_id": int(item_id),
    }


def rank_candidates(
    model: LogisticRegression,
    snapshot: dict[str, Any],
    catalog: dict[int, float] | None = None,
    *,
    k: int = TOP_K,
) -> list[int]:
    items = catalog if catalog is not None else ITEM_SCORES
    rows = [candidate_row(snapshot, item_id, score) for item_id, score in items.items()]
    X = numeric_matrix(rows)
    p_click = model.predict_proba(X)[:, 1]
    scored = sorted(
        zip((row["item_id"] for row in rows), p_click, strict=True),
        key=lambda pair: (-float(pair[1]), int(pair[0])),
    )
    ranked: list[int] = []
    for item_id, _ in scored:
        if item_id not in ranked:
            ranked.append(int(item_id))
        if len(ranked) >= k:
            break
    return ranked


def rank_held_out_user(user_id: int = 123, *, k: int = TOP_K) -> tuple[list[int], LogisticRegression]:
    """Train without this user's rows, then rank the catalog for them."""
    rows = prepared_rows()
    others = [row for row in rows if int(row["user_id"]) != user_id]
    model, _, _ = fit_logreg(others)
    snapshot = user_snapshot(rows, user_id)
    return rank_candidates(model, snapshot, k=k), model


def main() -> None:
    ids, model = rank_held_out_user(123)
    X, _ = labeled_matrix(prepared_rows()[:1])
    print("held-out user 123 top", ids)
    print("predict_proba shape demo", model.predict_proba(X).shape)


if __name__ == "__main__":
    main()
