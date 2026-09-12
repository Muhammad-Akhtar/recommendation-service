"""Task 5.3 / 5.6 — Ranking metrics at K (binary relevance).

Microsoft Recommenders names the same family (`precision_at_k`, `ndcg_at_k`,
`map_at_k`). Their NDCG can use *graded* relevance; we stay **binary**
(clicked/purchased vs not). Discount: rel / log2(rank + 1) with rank starting
at 1 (DCG). See microsoft-recommenders.readthedocs.io evaluation.html.

Duplicates: Precision@K / NDCG walk **unique** item ids, first occurrence wins
(a repeated id does not get a second slot). Users with an empty relevant set
are skipped (return None) — not scored as 0 — so a cold user does not drag
NDCG to zero by definition.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

K_DEFAULT = 5


def unique_top(ranked: Iterable[int], k: int) -> list[int]:
    top: list[int] = []
    for item_id in ranked:
        if item_id in top:
            continue
        top.append(int(item_id))
        if len(top) >= k:
            break
    return top


def precision_at_k(
    ranked: Iterable[int],
    relevant: set[int],
    k: int = K_DEFAULT,
) -> float | None:
    if not relevant:
        return None
    top = unique_top(ranked, k)
    hits = sum(1 for item_id in top if item_id in relevant)
    return hits / k


def recall_at_k(
    ranked: Iterable[int],
    relevant: set[int],
    k: int = K_DEFAULT,
) -> float | None:
    if not relevant:
        return None
    top = unique_top(ranked, k)
    hits = sum(1 for item_id in top if item_id in relevant)
    return hits / len(relevant)


def hit_rate_at_k(
    ranked: Iterable[int],
    relevant: set[int],
    k: int = K_DEFAULT,
) -> float | None:
    if not relevant:
        return None
    top = unique_top(ranked, k)
    return 1.0 if any(item_id in relevant for item_id in top) else 0.0


def average_precision_at_k(
    ranked: Iterable[int],
    relevant: set[int],
    k: int = K_DEFAULT,
) -> float | None:
    if not relevant:
        return None
    top = unique_top(ranked, k)
    hits = 0
    summed = 0.0
    for rank, item_id in enumerate(top, start=1):
        if item_id not in relevant:
            continue
        hits += 1
        summed += hits / rank
    denom = min(len(relevant), k)
    return summed / denom if denom else 0.0


def _dcg(gains: list[float]) -> float:
    return sum(
        rel / math.log2(rank + 1) for rank, rel in enumerate(gains, start=1)
    )


def ndcg_at_k(
    ranked: Iterable[int],
    relevant: set[int],
    k: int = K_DEFAULT,
) -> float | None:
    if not relevant:
        return None
    top = unique_top(ranked, k)
    gains = [1.0 if item_id in relevant else 0.0 for item_id in top]
    gains.extend([0.0] * (k - len(gains)))
    ideal_ones = min(k, len(relevant))
    ideal = [1.0] * ideal_ones + [0.0] * (k - ideal_ones)
    idcg = _dcg(ideal)
    if idcg == 0:
        return None
    return _dcg(gains) / idcg
