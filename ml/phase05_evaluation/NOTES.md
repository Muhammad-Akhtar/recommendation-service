# Phase 5 — recorded experiments

K=5 (same as `model.predict` top 5). Evaluator is offline in `ml/phase05_evaluation/` — not on `GET /recommendations`.

## Task 5.1–5.2 (temporal test, n=10)

| | accuracy | precision | recall | F1 | ROC-AUC | log loss |
| --- | --- | --- | --- | --- | --- | --- |
| ML logreg | 0.600 | 0.667 | 0.400 | 0.500 | 0.560 | 0.835 |
| Dummy most_frequent | 0.500 | 0.000 | 0.000 | 0.000 | 0.500 | 18.02 |

Dummy did **not** win accuracy on this split. It still loses log loss badly (over-confident majority class). Accuracy is not the story.

## Task 5.4

Relevant `{10}`: list A `[10,20,30,40,50]` NDCG@5=1.000; list B `[20,30,40,50,10]` NDCG@5=0.387. Same five items → same bag accuracy.

## Task 5.5 — mean over test-window users (skip empty relevant)

| System | precision@5 | recall@5 | hit_rate@5 | map@5 | ndcg@5 |
| --- | --- | --- | --- | --- | --- |
| popularity_v1 | 0.100 | 0.375 | 0.500 | 0.108 | 0.184 |
| heuristic_v2 | 0.100 | 0.375 | 0.500 | 0.087 | 0.167 |
| ml_logreg | 0.100 | 0.375 | 0.500 | 0.087 | 0.167 |

On this toy catalog the ML list matched v2; **v1 wins NDCG**. That is the lesson: do not ship “ML is better” from accuracy or one CTR snapshot.

## Exercises

1. Relevant item below K → Hit Rate@5 = 0 even if a pair classifier looks fine.
2. Duplicate ids: unique-first Precision@K (documented in `ranking_metrics.py`).
3. User with no relevant test items: metric returns `None` (skipped, not 0).
