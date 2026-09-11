# Phase 11 — Progressive Model Improvement

## Objective

Only after Phases 1–10 work: try stronger **classical** models in a fixed loop. Do not add complexity that does not beat the current champion on the **same** snapshot.

```text
Train → Evaluate → Compare → Understand → Save → Integrate → Monitor
```

Order:

1. Logistic Regression (already v3 — re-run as champion reference)
2. Decision Tree
3. Random Forest
4. Gradient Boosting (`sklearn.ensemble.GradientBoostingClassifier` or `HistGradientBoostingClassifier`)
5. Better feature engineering (recency, counts per item — still tiny)
6. More ranking-oriented approaches (still pointwise unless a small pairwise experiment is easy)

No XGBoost requirement here (optional mention; full LTR in Phase 12). No neural nets.

## Why This Phase Exists

Random Forest is not “better” by default. This phase builds the habit of beating v1/v2/v3 with evidence.

## Relationship To Existing Recommendation Service

Integration means: new artifact + new `MODEL_VERSION` (e.g. `v4-rf`) implementing `predict(features, candidates)`. Same service I/O. Default production version stays the Phase 8/9 champion until a row in the experiment log wins **and** we explicitly switch.

## Prerequisites

- Phase 8 experiment log format
- Phase 5 ranking metrics
- Phase 6 save/load Pipeline

## Concepts To Learn

- Tree ensembles vs linear models (non-linear interactions, e.g. last_item × score)
- Hyperparameters: `max_depth`, `n_estimators`, learning rate
- Feature engineering only when it could exist **at serving time**
- Pointwise ranking limits (independent scores per item)

## Tasks

### Task 11.1 — Freeze champion numbers

Copy v1, v2, v3 NDCG@5 from Phase 8 into `ml/phase11_improve/LEADERBOARD.md`.

**Verify:** three rows present.

### Task 11.2 — Decision tree (full, not just Phase 3 demo)

Train, evaluate ranking metrics, save artifact if ≥ champion on NDCG@5 **or** document why not.

### Task 11.3 — Random Forest

Same protocol. One hyperparameter sweep at most (e.g. depth 3 vs 8) — two runs, not twenty.

### Task 11.4 — Gradient boosting (sklearn)

Same protocol. Watch overfitting on the tiny set.

### Task 11.5 — One new serving-legal feature

Example: `is_last_item` already used; add `log1p(click_count)` **or** `purchase_share = purchase / (click+purchase+1)`. Must be computable from `UserFeatures` + candidate.

**Verify:** Redis/Postgres schema unchanged; derived in ranker/training only.

### Task 11.6 — Integrate only a winner

If a model beats v3 on NDCG@5 **and** is not obviously overfit (train NDCG >> test), register it as `v4`. Otherwise leave registry alone and write why.

**Verify:** `pytest tests/` still green; default `MODEL_VERSION` still champion.

### Task 11.7 — Monitor hook

List which Prometheus counters you would watch after a hypothetical v4 canary (predictions, latency, CTR). No Grafana required.

## Practical Exercises

1. Depth=20 tree on 40 rows — expect train NDCG 1.0, test collapse.
2. Remove `item_score` from RF; if NDCG dies, the ensemble was relying on popularity (not a shame — then v1 was enough).
3. Compare latency 100 predicts: LR vs RF on CPU.

## Implementation Work

```text
ml/phase11_improve/
  LEADERBOARD.md
  train_tree.py
  train_rf.py
  train_gbdt.py
  features_plus.py
  test_phase11.py
```

## Tests / Verification

`pytest ml/phase11_improve/test_phase11.py -q`

Leaderboard parser: every run has NDCG@5.

## Expected Outcome

A leaderboard. Maybe still logistic. That is a successful phase if the reasoning is written down.

## Interview Questions

1. When do tree ensembles beat logistic regression?
2. Why can GBDT crush a 40-row dataset and fail in production?
3. What serving-time constraint limits new features?
4. Why keep the popularity baseline on the leaderboard?
5. How would you integrate v4 without touching Kafka?

## Completion Checklist

- [ ] Tasks 11.1–11.7 verified
- [ ] Leaderboard updated
- [ ] No unjustified deep learning
- [ ] Default prod model documented
- [ ] Index: Phase 11 `COMPLETED`

## What The Next Phase Will Need

- A working classical pipeline to contrast with **advanced** ideas
- Clear beginner/intermediate/advanced labels
- Permission **not** to implement everything

## Previous Phase

[`10_ML_MONITORING_AND_DRIFT.md`](10_ML_MONITORING_AND_DRIFT.md)

## Next Phase

[`12_ADVANCED_RECOMMENDATION_SYSTEMS.md`](12_ADVANCED_RECOMMENDATION_SYSTEMS.md)

## Recommended References

- [scikit-learn Ensemble methods](https://scikit-learn.org/stable/modules/ensemble.html)
- [scikit-learn Gradient Boosting](https://scikit-learn.org/stable/modules/ensemble.html#gradient-boosting)
- [Google Rules of ML](https://developers.google.com/machine-learning/guides/rules-of-ml) — don’t launch complexity without gains
