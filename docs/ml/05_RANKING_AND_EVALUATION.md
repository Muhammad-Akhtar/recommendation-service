# Phase 5 — Ranking and Evaluation

## Objective

Learn classification metrics **and** ranking metrics. Implement a small ranking evaluator. Compare popularity (v1), heuristic (v2), and the Phase 3 ML scorer **offline** — without claiming production superiority.

## Why This Phase Exists

A click classifier can have similar accuracy for two models while putting the relevant item in position 5 vs position 1. Recommendation quality is about **order**. CTR in production is delayed and noisy; we need offline metrics first.

## Relationship To Existing Recommendation Service

| Existing | Gap this phase fills |
| --- | --- |
| `calculate_ctr` in `app/model_quality.py` | Online, impression-based, not Precision@K |
| Prometheus counters | No NDCG / MAP |
| `GET /monitoring/model-quality` | Per-version CTR only |

Do **not** put NDCG inside `GET /recommendations`. Evaluator lives in `ml/phase05_evaluation/`.

K for our API is **5** (models return top 5).

## Prerequisites

- Phases 1–4 completed
- Ranked lists from v1/v2/ML on a toy test set

## Concepts To Learn

Classification (pointwise click prediction):

- Accuracy — often misleading with class imbalance
- Precision, recall, F1
- ROC-AUC
- Log loss

Ranking (listwise quality at K):

- Precision@K
- Recall@K
- Hit Rate@K (any relevant item in top K)
- MAP@K
- NDCG@K (order-sensitive; discounted gain)

Why order matters: two lists `[relevant, junk, …]` vs `[junk, junk, relevant, …]` can share accuracy if you only score the relevant pair, but NDCG differs.

## Tasks

### Task 5.1 — Classification metrics on the click model

On the temporal test split, compute accuracy, precision, recall, F1, ROC-AUC, log loss via `sklearn.metrics`.

**Verify:** all are finite; accuracy is not the only number in the report.

- [x] Done — `ml/phase05_evaluation/classification_metrics.py`

### Task 5.2 — Imbalanced dummy

Compare the ML model to `DummyClassifier(strategy="most_frequent")`.

**Verify:** dummy can win accuracy; ML should win ROC-AUC or log loss if the toy data is learnable. Record both.

- [x] Done — `ml/phase05_evaluation/classification_metrics.py`

### Task 5.3 — Implement ranking metrics ourselves

For one user, given `y_true` relevant item set and a ranked list, implement:

`precision_at_k`, `recall_at_k`, `hit_rate_at_k`, `average_precision_at_k`, `ndcg_at_k`

Use binary relevance. Discount: `rel / log2(rank+1)` with rank starting at 1.

**Verify:** if the only relevant item is at position 1, NDCG@5 = 1. If it is at position 5, NDCG@5 < 1.

- [x] Done — `ml/phase05_evaluation/ranking_metrics.py`

### Task 5.4 — Same accuracy, different ranking

Construct two ranked lists that a pointwise 0/1 accuracy (on a fixed set of pairs) treats similarly, but NDCG@5 disagrees.

**Verify:** written numbers side by side.

- [x] Done — `ml/phase05_evaluation/NOTES_same_accuracy.md`

### Task 5.5 — Compare three systems at K=5

| System | How to produce a list |
| --- | --- |
| Popularity baseline | v1 / catalog score |
| Rule-based v2 | production formula |
| ML model | sort by `predict_proba` |

Average Precision@5, Recall@5, HitRate@5, MAP@5, NDCG@5 over users in the test window.

**Verify:** a markdown table. Winner on NDCG may lose on accuracy — that is the lesson.

- [x] Done — `ml/phase05_evaluation/compare_rankers.py`

### Task 5.6 — Optional check vs Microsoft definitions

Read Microsoft Recommenders `ndcg_at_k` docs. Note binary relevance vs graded. We stay binary.

**Verify:** one comment in code citing the metric names.

- [x] Done — `ml/phase05_evaluation/ranking_metrics.py`

## Practical Exercises

1. Put all relevant items below K; Hit Rate@K → 0 even if the classifier is “accurate” on random pairs.
2. Duplicate recommendations; decide whether your Precision@K treats unique items only (document the choice).
3. User with no relevant items in the test window: skip or score 0 — pick one rule and test it.

## Implementation Work

```text
ml/phase05_evaluation/
  classification_metrics.py
  ranking_metrics.py
  compare_rankers.py
  NOTES_same_accuracy.md
  test_phase05.py
  NOTES.md
```

## Tests / Verification

`pytest ml/phase05_evaluation/test_phase05.py -q`

Must include analytic NDCG cases (perfect ranking, relevant at last slot).

## Expected Outcome

You refuse to say “the ML model is better” from accuracy or from a single CTR snapshot alone. You can compute NDCG@5 on a fixture.

## Interview Questions

1. Why is accuracy a poor recsys metric?
2. Precision@K vs Recall@K?
3. Why does NDCG discount lower ranks?
4. Offline metrics vs online CTR?
5. What is K in our service?

## Completion Checklist

- [x] Tasks 5.1–5.6 verified
- [x] pytest passes (including NDCG fixtures)
- [x] Comparison table exists
- [x] No metrics added to the request path
- [x] Index: Phase 5 `COMPLETED`

## What The Next Phase Will Need

- A chosen ranker (likely logistic) worth serving
- `predict(features, candidates) -> list[int]` contract
- Awareness that serving loads an **artifact**, not a notebook

## Previous Phase

[`04_RECOMMENDATION_SYSTEMS.md`](04_RECOMMENDATION_SYSTEMS.md)

## Next Phase

[`06_TRAINING_SERVING_PIPELINE.md`](06_TRAINING_SERVING_PIPELINE.md)

## Recommended References

- [scikit-learn Model evaluation](https://scikit-learn.org/stable/modules/model_evaluation.html)
- [Microsoft Recommenders — evaluation](https://microsoft-recommenders.readthedocs.io/en/latest/evaluation.html)
- [NDCG (background)](https://en.wikipedia.org/wiki/Discounted_cumulative_gain)
