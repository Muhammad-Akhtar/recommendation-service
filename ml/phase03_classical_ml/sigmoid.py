"""Task 3.1–3.2 — Sigmoid by hand, then one v2-style weighted example.

Logistic regression is not a black box: it computes z = w·x + b, then
p = 1 / (1 + e^{-z}) in (0, 1). v2 already adds popularity + clicks + last
item with **guessed** weights. Here those weights are still guessed — Task 3.3
will *learn* them.
"""

from __future__ import annotations

import math
from typing import Any


def sigmoid(z: float) -> float:
    """Map log-odds z to a probability in (0, 1)."""
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    exp_z = math.exp(z)
    return exp_z / (1.0 + exp_z)


# Task 3.2 — fake weights in the same *direction* as production v2
# (app/model.py: score + 0.01*clicks + 0.05*purchases + 0.5 if last item).
# We also add a weight on item_score and an intercept (new-user baseline).
W_ITEM_SCORE = 2.0
W_CLICKS = 0.01
W_PURCHASES = 0.05
W_SAME_LAST = 0.5
B_INTERCEPT = -1.2

# Worked example (must match weighted_logit below):
#   item_score=0.95, click_count_before=2, purchase_count_before=1, same_as_last_item=1
#   z = 2.0*0.95 + 0.01*2 + 0.05*1 + 0.5*1 + (-1.2)
#     = 1.90 + 0.02 + 0.05 + 0.50 - 1.20
#     = 1.27
#   p = sigmoid(1.27)
EXAMPLE_ROW = {
    "item_score": 0.95,
    "click_count_before": 2,
    "purchase_count_before": 1,
    "same_as_last_item": 1,
}
EXAMPLE_Z = 1.27


def weighted_logit(row: dict[str, Any]) -> float:
    """z = w·x + b for one user–item row (v2-like intuition, still not learned)."""
    return (
        W_ITEM_SCORE * float(row["item_score"])
        + W_CLICKS * float(row["click_count_before"])
        + W_PURCHASES * float(row["purchase_count_before"])
        + W_SAME_LAST * float(row["same_as_last_item"])
        + B_INTERCEPT
    )


def main() -> None:
    for z in (0.0, 2.0, -2.0):
        print(f"sigmoid({z}) = {sigmoid(z):.4f}")
    z = weighted_logit(EXAMPLE_ROW)
    print(f"example z={z:.4f} (expected {EXAMPLE_Z}) p={sigmoid(z):.4f}")


if __name__ == "__main__":
    main()
