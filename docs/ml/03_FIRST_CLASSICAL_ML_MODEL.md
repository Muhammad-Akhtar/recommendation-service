# Phase 3 — First Classical ML Model

## Objective

Train the first **genuine** ML model: Logistic Regression that estimates `P(click | features)`, with enough math that `.fit()` is not a black box. Optionally add a Decision Tree for comparison. Random Forest waits until Phase 11 unless this phase’s last task needs a one-file demo.

## Why This Phase Exists

v2 already combines `score`, clicks, purchases, and last item with **guessed** weights. Logistic regression learns those weights from labels built in Phase 2.

## Relationship To Existing Recommendation Service

Conceptual mapping (do **not** wire into FastAPI yet — that is Phase 6):

```text
Phase 3 offline:
  features → sigmoid(w·x + b) → probability

Today online:
  RecommendationService loads UserFeatures + candidates
  model.predict(...) returns top item ids

Later:
  for each candidate: p = clf.predict_proba(feature_row)
  rank by p  →  list[int]
```

Still no Redis/Postgres inside the model.

## Prerequisites

- Phases 1–2 completed
- Tiny labeled dataset from Phase 2 (or regenerated here)

## Concepts To Learn

```text
features x
    ↓
z = w·x + b     (weighted combination + intercept)
    ↓
p = 1 / (1 + e^{-z})     (sigmoid → probability in (0, 1))
    ↓
loss (log loss / binary cross-entropy)
    ↓
adjust w, b  (gradient descent conceptually)
```

- Weights: how much each feature pushes log-odds
- Bias / intercept: baseline log-odds when features are zero (new user)
- Probability vs hard class (`predict` vs `predict_proba`)
- Decision threshold (0.5 is not sacred)
- Regularization (`C` in sklearn) as a hyperparameter
- Decision tree: recursive splits; different inductive bias; still classical ML

Use scikit-learn **after** computing one sigmoid by hand on a 2-feature example.

## Tasks

### Task 3.1 — Sigmoid by hand

Implement `sigmoid(z)` and compute `p` for `z = 0, 2, -2`.

**Verify:** `sigmoid(0) == 0.5`; larger `z` → `p` closer to 1.

- [x] Done — `ml/phase03_classical_ml/sigmoid.py`

### Task 3.2 — One weighted example

Using fake weights similar to v2’s intuition, compute `z` and `p` for one user–item row (`item_score`, `click_count_before`, `purchase_count_before`, `same_as_last_item`).

**Verify:** printed formula in a comment matches the numbers.

- [x] Done — `ml/phase03_classical_ml/sigmoid.py`

### Task 3.3 — Fit LogisticRegression

Train `sklearn.linear_model.LogisticRegression` on the Phase 2 matrix. Print `coef_` with feature names and `intercept_`.

**Verify:** `predict_proba` shape `(n, 2)`; probabilities in `[0, 1]`.

- [x] Done — `ml/phase03_classical_ml/train_logreg.py`

### Task 3.4 — Rank candidates for one user

Hold a user out. For 5–10 candidate items, build feature rows, score with `predict_proba[:, 1]`, sort descending, take top 5.

**Verify:** output is a `list[int]` of item ids — same *shape* as `model.predict` today.

- [x] Done — `ml/phase03_classical_ml/rank_with_proba.py`

### Task 3.5 — Compare to v2 heuristic

On the same candidate set, compute v2 scores with the production formula (copy constants; do not import Redis). Compare orderings.

**Verify:** a short table: item_id, v2_score, p_click, ranks. No claim yet that ML is “better” (no ranking metrics until Phase 5).

- [x] Done — `ml/phase03_classical_ml/compare_v2.py`

### Task 3.6 — Decision tree (second model)

Fit `DecisionTreeClassifier(max_depth=3)`. Print the tree (`export_text`) or feature importances.

**Verify:** tree uses at least one of our features; train accuracy is not the only number you report (also check a temporal test split).

- [x] Done — `ml/phase03_classical_ml/train_tree.py`

## Practical Exercises

1. Set all labels to 0; fitting should fail or produce a useless model — you need both classes.
2. Multiply `item_score` by 1000 without scaling; compare coefficients before/after `StandardScaler`.
3. Change `C` (regularization) and watch coefficients shrink.

## Implementation Work

```text
ml/phase03_classical_ml/
  sigmoid.py
  train_logreg.py
  rank_with_proba.py
  compare_v2.py
  train_tree.py
  test_phase03.py
  NOTES.md
```

Do not edit `app/model.py`.

## Tests / Verification

`pytest ml/phase03_classical_ml/test_phase03.py -q`

Include: sigmoid checks; fitted model `predict_proba`; ranker returns unique item ids length ≤ 5.

## Expected Outcome

You can say: *Logistic regression learned weights; v2 guessed them. Ranking means sorting P(click) per candidate. The service will still fetch features and candidates for us later.*

## Interview Questions

1. What does the sigmoid do to `w·x+b`?
2. Why do we rank with `predict_proba` rather than `predict`?
3. What is log loss punishing?
4. Why might an unscaled `click_count` dominate `item_score`?
5. How is this still compatible with `predict(features, candidates)`?

## Completion Checklist

- [x] Tasks 3.1–3.6 verified
- [x] pytest passes
- [x] Hand sigmoid + sklearn fit both exist
- [x] `app/` unchanged
- [x] Index: Phase 3 `COMPLETED`

## What The Next Phase Will Need

- A working probability ranker
- v1/v2 as baselines to name in recsys taxonomy
- Awareness that “click classifier + sort” is one recsys approach, not all of them

## Previous Phase

[`02_DATA_AND_FEATURE_ENGINEERING.md`](02_DATA_AND_FEATURE_ENGINEERING.md)

## Next Phase

[`04_RECOMMENDATION_SYSTEMS.md`](04_RECOMMENDATION_SYSTEMS.md)

## Recommended References

- [scikit-learn Logistic regression](https://scikit-learn.org/stable/modules/linear_model.html#logistic-regression)
- [scikit-learn Decision Trees](https://scikit-learn.org/stable/modules/tree.html)
- [Google ML Crash Course — Logistic Regression](https://developers.google.com/machine-learning/crash-course/logistic-regression)
