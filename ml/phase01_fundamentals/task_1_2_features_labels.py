"""Task 1.2 — Features vs labels.

A table of examples has both inputs (features) and answers (labels).
Training uses both. Inference uses only features.

X = features the model may see.  y = the target we want to predict.
Mixing y into X is how leakage starts (see Task 1.7).
"""

from typing import Any


def split_xy(rows: list[dict[str, Any]]) -> tuple[list[Any], list[Any]]:
    """Split row dicts with keys 'x' and 'y' into feature list X and label list y."""
    X = [row["x"] for row in rows]
    y = [row["y"] for row in rows]
    if len(X) != len(y):
        raise ValueError("X and y must have the same length")
    return X, y


def main() -> None:
    # Same relationship as Task 1.1, now stored as a labeled table.
    rows = [{"x": x, "y": 2 * x + 1} for x in range(6)]
    X, y = split_xy(rows)
    print("rows:", rows)
    print("X (features only):", X)
    print("y (labels):       ", y)
    print("y in X?", any(item == y for item in X) and X == y)


if __name__ == "__main__":
    main()
