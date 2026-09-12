"""Task 4.4 — Beginner item-kNN with cosine similarity.

Recommend items whose interaction *columns* are close to `last_item_id`.
An item is most similar to itself (~1.0). Cold-start items (all zeros) have
undefined cosine with everyone — production v1 can still rank them by catalog
score; CF cannot.
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from ml.phase04_recsys.interaction_matrix import implicit_matrix


def item_cosine(matrix: np.ndarray) -> np.ndarray:
    """Items × items cosine on columns (users are the dimensions)."""
    if matrix.size == 0:
        return np.zeros((0, 0))
    return cosine_similarity(matrix.T)


def similar_to(
    last_item_id: int,
    *,
    k: int = 5,
) -> list[tuple[int, float]]:
    matrix, _users, items = implicit_matrix()
    if last_item_id not in items:
        return []
    sim = item_cosine(matrix)
    idx = items.index(last_item_id)
    ranked = sorted(
        ((items[j], float(sim[idx, j])) for j in range(len(items))),
        key=lambda pair: (-pair[1], pair[0]),
    )
    return ranked[:k]


def main() -> None:
    matrix, _, items = implicit_matrix()
    sim = item_cosine(matrix)
    for i, item_id in enumerate(items):
        self_sim = float(sim[i, i])
        print(f"item {item_id} self-cosine={self_sim:.3f}")
    print("similar to last_item 10:", similar_to(10))


if __name__ == "__main__":
    main()
