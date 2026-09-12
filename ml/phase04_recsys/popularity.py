"""Task 4.2 — Popularity baseline from toy events vs catalog scores.

v1 ranks by seeded Postgres `recommendation_items.score` (item 10 → 0.95, …).
Event counts are a *different* popularity signal: how often the item appeared
in our implicit log. They need not agree.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from ml.phase02_features.toy_events import ITEM_SCORES, TOY_EVENTS


def interaction_counts(events: list[dict[str, Any]] | None = None) -> dict[int, int]:
    rows = events if events is not None else TOY_EVENTS
    counts: Counter[int] = Counter(int(row["item_id"]) for row in rows)
    return dict(counts)


def popularity_table(
    events: list[dict[str, Any]] | None = None,
    catalog: dict[int, float] | None = None,
) -> list[dict[str, Any]]:
    catalog_scores = catalog if catalog is not None else ITEM_SCORES
    counts = interaction_counts(events)
    rows = []
    for item_id, catalog_score in catalog_scores.items():
        rows.append(
            {
                "item_id": int(item_id),
                "interaction_count": int(counts.get(item_id, 0)),
                "catalog_score": float(catalog_score),
            }
        )
    rows.sort(key=lambda row: (-row["interaction_count"], -row["catalog_score"], row["item_id"]))
    return rows


def popularity_rank(events: list[dict[str, Any]] | None = None) -> list[int]:
    return [row["item_id"] for row in popularity_table(events)]


def main() -> None:
    print(f"{'item':>6} {'count':>8} {'catalog':>8}")
    for row in popularity_table():
        print(f"{row['item_id']:6d} {row['interaction_count']:8d} {row['catalog_score']:8.2f}")


if __name__ == "__main__":
    main()
