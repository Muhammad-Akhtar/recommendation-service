"""Task 2.5 — Missing values, ID types, and train-only scaling.

- New user / first event: `last_item_id_before` is missing → `has_last_item=0`.
  That matches Redis `get_user_features` defaults (`last_item_id=None`, counts 0).
- `user_id` / `item_id` / `last_item_id_before` are identifiers, not magnitudes.
  They stay out of the numeric matrix (categorical later, not now).
- `item_score` (~0.57–0.95) and `click_count_before` (0, 1, 2, …) are different
  scales. Standardize score with **train** mean/std only, then apply to test.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.preprocessing import StandardScaler

# Honest numeric inputs for a later classifier. No IDs, no raw event_type, no label.
NUMERIC_FEATURE_NAMES = (
    "click_count_before",
    "purchase_count_before",
    "item_score",
    "same_as_last_item",
    "has_last_item",
)

ID_FIELDS = ("user_id", "item_id", "last_item_id_before")


def add_missing_value_flags(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        enriched = dict(row)
        has_last = row.get("last_item_id_before") is not None
        enriched["has_last_item"] = 1 if has_last else 0
        enriched["same_as_last_item"] = int(bool(row.get("same_as_last_item")))
        out.append(enriched)
    return out


def numeric_matrix(rows: list[dict[str, Any]]) -> np.ndarray:
    """Rows × NUMERIC_FEATURE_NAMES. IDs are intentionally absent."""
    matrix = []
    for row in rows:
        matrix.append([float(row[name]) for name in NUMERIC_FEATURE_NAMES])
    return np.asarray(matrix, dtype=float)


def fit_item_score_scaler(train_rows: list[dict[str, Any]]) -> StandardScaler:
    """Fit on the train fold only — never on test or the full table."""
    scaler = StandardScaler()
    scores = np.array([[row["item_score"]] for row in train_rows], dtype=float)
    scaler.fit(scores)
    return scaler


def apply_item_score_scaler(
    rows: list[dict[str, Any]], scaler: StandardScaler
) -> list[dict[str, Any]]:
    scores = np.array([[row["item_score"]] for row in rows], dtype=float)
    scaled = scaler.transform(scores).ravel()
    out = []
    for row, value in zip(rows, scaled, strict=True):
        enriched = dict(row)
        enriched["item_score_std"] = float(value)
        out.append(enriched)
    return out


def new_user_numeric_row(row: dict[str, Any]) -> bool:
    """Practical exercise 3: first event looks like Redis defaults (all zeros)."""
    return (
        int(row["click_count_before"]) == 0
        and int(row["purchase_count_before"]) == 0
        and int(row["has_last_item"]) == 0
    )


def main() -> None:
    from ml.phase02_features.point_in_time import build_training_rows
    from ml.phase02_features.splits import temporal_split

    rows = add_missing_value_flags(build_training_rows())
    train, test = temporal_split(rows)
    scaler = fit_item_score_scaler(train)
    train_s = apply_item_score_scaler(train, scaler)
    test_s = apply_item_score_scaler(test, scaler)
    print("numeric columns:", NUMERIC_FEATURE_NAMES)
    print("IDs kept out:", ID_FIELDS)
    print(
        "train item_score_std mean~="
        f"{np.mean([r['item_score_std'] for r in train_s]):.3f} "
        f"(scaler mean={float(scaler.mean_[0]):.3f})"
    )
    print(
        "test item_score_std mean~="
        f"{np.mean([r['item_score_std'] for r in test_s]):.3f} "
        "(not forced to 0 — test stats were not fitted)"
    )
    new_user = next(r for r in rows if r["user_id"] == 1001)
    print("exercise 3 user 1001 first row zeros?", new_user_numeric_row(new_user))


if __name__ == "__main__":
    main()
