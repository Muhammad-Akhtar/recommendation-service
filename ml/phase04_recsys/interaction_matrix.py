"""Task 4.3 — Implicit user–item matrix (no star ratings).

Kafka events are implicit: view / click / purchase. Cell = 1 if the user
clicked or purchased that item, else 0. Most cells are zeros (sparse).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ml.phase02_features.labels import POSITIVE_EVENT_TYPES
from ml.phase02_features.toy_events import ITEM_SCORES, TOY_EVENTS


def implicit_matrix(
    events: list[dict[str, Any]] | None = None,
    *,
    item_ids: list[int] | None = None,
) -> tuple[np.ndarray, list[int], list[int]]:
    rows = events if events is not None else TOY_EVENTS
    users = sorted({int(row["user_id"]) for row in rows})
    items = item_ids if item_ids is not None else sorted(ITEM_SCORES.keys())
    index_u = {user_id: i for i, user_id in enumerate(users)}
    index_i = {item_id: j for j, item_id in enumerate(items)}
    matrix = np.zeros((len(users), len(items)), dtype=float)
    for row in rows:
        if str(row["event_type"]).lower() not in POSITIVE_EVENT_TYPES:
            continue
        u = index_u.get(int(row["user_id"]))
        i = index_i.get(int(row["item_id"]))
        if u is None or i is None:
            continue
        matrix[u, i] = 1.0
    return matrix, users, items


def sparsity(matrix: np.ndarray) -> float:
    cells = matrix.size
    if cells == 0:
        return 1.0
    return float(np.count_nonzero(matrix == 0) / cells)


def main() -> None:
    matrix, users, items = implicit_matrix()
    print("users", users)
    print("items", items)
    print(matrix)
    print(f"sparsity={sparsity(matrix):.3f} (zeros/cells); values={sorted(set(matrix.ravel()))}")


if __name__ == "__main__":
    main()
