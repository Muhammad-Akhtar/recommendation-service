# Task 5.4 — Same pointwise accuracy, different NDCG@5

Fixed pair set for one user: relevant `{10}`; judged items `{10, 20, 30, 40, 50}`.
Treat “predicted positive” = appeared in the top-5 list. Both lists contain
every judged item, so **accuracy on those five pairs is identical** (one
positive, four negatives, all five ranked).

| List | Ranked ids | Accuracy on pairs | NDCG@5 |
| --- | --- | --- | --- |
| A (relevant first) | `[10, 20, 30, 40, 50]` | 1.0 of the relevant item is in the set | **1.000** |
| B (relevant last) | `[20, 30, 40, 50, 10]` | same | **0.387** (`1 / log2(6)`) |

Order is the product. Classification accuracy on a bag of pairs cannot see it.
