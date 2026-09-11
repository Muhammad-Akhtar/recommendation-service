# Phase 1 — ML Fundamentals

## Objective

Understand what a trained model actually is — features, labels, parameters, training vs inference — using tiny Python datasets. Do **not** use recommendation-service data yet.

## Why This Phase Exists

The current `app/model.py` classes look like models but are handwritten scoring rules. Before replacing them, we need the vocabulary and a felt sense of `.fit()` vs a formula we typed ourselves.

## Relationship To Existing Recommendation Service

Read-only context:

- `app/model.py` — heuristics we will later replace
- `app/recommendation_service.py` — already separates I/O from ranking

This phase does **not** modify `app/`. All work goes under `ml/phase01_fundamentals/` (create that folder when Task 1.1 starts).

## Prerequisites

- Python 3.12 and the existing project venv
- Ability to run pytest
- [`00_ML_PLAN_INDEX.md`](00_ML_PLAN_INDEX.md) and [`ML_CONTEXT.md`](ML_CONTEXT.md)

Install **only when this phase starts** (not before): `scikit-learn` (and keep using pytest already in the project). Prefer adding it to a later `ml` extra or documenting the pip command in Task 1.1 — do not change production `requirements.txt` unless we decide to in Phase 6.

## Concepts To Learn

| Concept | Plain meaning |
| --- | --- |
| Machine learning | A program whose behavior is set by **data**, not only by rules we write |
| Model | A function with **parameters** that maps features → prediction |
| Features (`X`) | Inputs the model is allowed to see |
| Labels / target (`y`) | The answer we want it to predict during training |
| Parameters | Values **learned** (e.g. weights, intercept) |
| Hyperparameters | Values **we choose** (e.g. tree depth, regularization `C`) |
| Training | Searching for parameters that fit labeled examples |
| Validation | Tuning hyperparameters without touching the final test set |
| Testing | One-shot estimate of generalization |
| Inference | Using a fitted model on new features (no labels required) |
| Supervised vs unsupervised | Labels present vs finding structure without labels |
| Regression / classification / ranking | Number vs class vs ordered list |
| Overfitting / underfitting | Memorize noise vs too simple to capture the pattern |
| Bias / variance | Systematic error vs sensitivity to the particular sample |
| Data leakage | Training with information you would not have at prediction time |

## Tasks

### Task 1.1 — What is a model?

Write a tiny script that predicts `y = 2x + 1` **without** scikit-learn: a loop over `x` values using hardcoded `w, b`. Then print predictions.

**Verify:** for `x=3`, prediction is `7`.

- [x] Done — `ml/phase01_fundamentals/task_1_1_what_is_a_model.py`

### Task 1.2 — Features vs labels

Same data as a table: columns `x` (feature) and `y` (label). Write a function `split_xy(rows) -> (X, y)`.

**Verify:** lengths match; `X` does not contain `y`.

- [x] Done — `ml/phase01_fundamentals/task_1_2_features_labels.py`

### Task 1.3 — Parameters vs hyperparameters

Fit `sklearn.linear_model.LinearRegression` on `y ≈ 2x+1` plus tiny noise. Print `coef_` and `intercept_` (parameters). Note that `fit_intercept=True` is a hyperparameter.

**Verify:** learned slope is near `2` (e.g. between 1.5 and 2.5).

- [x] Done — `ml/phase01_fundamentals/task_1_3_parameters.py`

### Task 1.4 — Train / validation / test

Use `train_test_split` twice (or train/val/test slices) on a 30-row toy set. Print sizes.

**Verify:** no row index appears in more than one split.

- [x] Done — `ml/phase01_fundamentals/task_1_4_splits.py`

### Task 1.5 — Supervised families

In comments or a short markdown note in the phase folder, classify: our future click model (classification), candidate `score` prediction (regression), “order these 20 items” (ranking), k-means on users (unsupervised).

**Verify:** the note exists and maps each family to one sentence.

- [x] Done — `ml/phase01_fundamentals/task_1_5_supervised_families.md`

### Task 1.6 — Overfitting experiment

Fit a high-degree polynomial (or a deep decision tree) on 8 noisy points; evaluate train vs held-out error. Then fit a line.

**Verify:** complex model train error < simple model, but held-out error is **worse** (overfit). Record the numbers.

- [x] Done — `ml/phase01_fundamentals/task_1_6_overfit.py`

### Task 1.7 — Leakage toy example

Create a feature `leaky = y`. Train a classifier that “perfectly” predicts. Then remove that column and retrain.

**Verify:** accuracy collapses without the leaky column. Write one sentence: *this is why we must not train on data unavailable at serving time*.

- [x] Done — `ml/phase01_fundamentals/task_1_7_leakage.py`

## Practical Exercises

1. Change the true slope from 2 to 5; confirm Task 1.3 recovers ~5.
2. Shuffle labels randomly in Task 1.6; both models should look bad on test — you cannot learn a nonexistent pattern.
3. Intentionally put the test set into training and watch test accuracy become meaningless.

## Implementation Work

When this phase starts, create:

```text
ml/phase01_fundamentals/
  task_1_1_what_is_a_model.py
  task_1_2_features_labels.py
  task_1_3_parameters.py
  task_1_4_splits.py
  task_1_6_overfit.py
  task_1_7_leakage.py
  test_phase01.py
```

Keep each file small. Comment *why*, not only *what*.

## Tests / Verification

`pytest ml/phase01_fundamentals/test_phase01.py -q`

Tests should cover: prediction `2*3+1==7`, split disjointness, leakage accuracy drop.

## Expected Outcome

You can explain, without looking at `app/model.py`:

- v1/v2 have **no learned parameters**
- training needs labels we do not yet build
- inference is what `predict()` does today — but today’s scores are not learned

## Interview Questions

1. What is the difference between a parameter and a hyperparameter?
2. Why do we hold out a test set?
3. Why can 100% training accuracy be a bad sign?
4. Give an example of data leakage in a recommendation system.
5. Is our current v2 an ML model? Why or why not?

## Completion Checklist

- [x] Tasks 1.1–1.7 done and verified
- [x] pytest for this phase passes
- [x] Overfit and leakage experiments recorded (numbers in comments or a short `NOTES.md`)
- [x] No changes to `app/`
- [x] Index status for Phase 1 set to `COMPLETED`

## What The Next Phase Will Need

- The idea of features/labels/leakage
- Comfort with train/test splits
- Awareness that serving-time features must match training-time features

Phase 2 will apply this to `user_events`, `click_count`, and candidate scores.

## Previous Phase

None — this is the first phase. Existing service is context only.

## Next Phase

[`02_DATA_AND_FEATURE_ENGINEERING.md`](02_DATA_AND_FEATURE_ENGINEERING.md)

## Recommended References

- [Google Machine Learning Crash Course](https://developers.google.com/machine-learning/crash-course)
- [scikit-learn Getting Started](https://scikit-learn.org/stable/getting_started.html) — estimators, `fit` / `predict`
- [scikit-learn User Guide: model selection](https://scikit-learn.org/stable/model_selection.html)
