# Phase 6 — Training / Serving Pipeline

## Objective

Separate **offline training** from **online inference**. Save a model artifact. Load it behind the existing `predict(features, candidates)` interface without the model touching Redis, Postgres, or Kafka.

## Why This Phase Exists

Phase 3 trained in a script. Production `get_model("v1")` returns a hardcoded class. We need the real lifecycle:

```text
Training data
    ↓
Feature engineering
    ↓
Training
    ↓
Validation
    ↓
Model artifact
    ↓
Model version
    ↓
Inference service
```

## Relationship To Existing Recommendation Service

Today:

- `app/model_registry.py` — in-memory dict of heuristic classes
- `app/recommendation_service.py` — loads features/candidates, calls `model.predict`
- `MODEL_VERSION` env selects the class

This phase **may** add a new class e.g. `LogisticRankingModel` (`v3`) that loads `ml/artifacts/...joblib` at init, **or** keep the loader entirely under `ml/` first and only then register `v3`.

Prefer: implement the wrapper + artifact **in `ml/` first**, then a **minimal** registry change to add `v3` without changing v1/v2 behavior. Default `MODEL_VERSION` stays `v1`.

Offline vs online:

| Offline | Online |
| --- | --- |
| Batch over `user_events` history | Per request, current Redis features + current candidates |
| Has labels | No labels |
| Can be slow | Must be fast |
| Writes artifact | Reads artifact |

## Prerequisites

- Phases 1–5 completed
- Logistic ranker + evaluation numbers exist

## Concepts To Learn

- Training pipeline vs inference path
- Artifact: fitted sklearn `Pipeline` (scaler + logistic regression)
- [Model persistence](https://scikit-learn.org/stable/model_persistence.html) (`joblib`) — same sklearn version to load
- Feature order must be identical at train and serve
- `RecommendationService` still owns I/O
- Version string `v3` means “this artifact + this feature schema”, not Kubernetes `SERVICE_VERSION`

## Tasks

### Task 6.1 — Draw the pipeline

Add `ml/phase06_train_serve/NOTES_pipeline.md` with the diagram above mapped to files.

**Verify:** a line that says the model does not import `redis` or `asyncpg`.

### Task 6.2 — Train script writes artifact

`ml/phase06_train_serve/train.py` fits a `Pipeline`, writes:

`ml/artifacts/click_logreg_v3.joblib`  
plus `ml/artifacts/click_logreg_v3.meta.json` (feature names, trained_at, metrics from Phase 5).

**Verify:** file exists; `joblib.load` round-trips `predict_proba`.

### Task 6.3 — Pure ranker class

Class with `__init__(self, artifact_path)` and `predict(features, candidates) -> list[int]`. Build one row per candidate from `UserFeatures`-shaped fields + `candidate.score`. No I/O.

**Verify:** unit test with a fake `UserFeatures` and 3 candidates; returns 3 or fewer ids.

### Task 6.4 — Feature alignment check

If extra/missing columns, fail clearly.

**Verify:** test that wrong feature order is caught (compare to `meta.json` names).

### Task 6.5 — Optional registry hook

If we touch production: add `"v3"` to `MODELS` **without** changing default config. Document `MODEL_VERSION=v3`.

**Verify:** `get_model("v1")` still returns popularity; pytest `tests/test_recommendations.py` still passes.

If artifact loading in Docker is awkward, keep v3 loader only in `ml/` and document the follow-up — do not break Compose.

### Task 6.6 — Smoke inference

Script: load artifact, rank seeded candidate ids for a synthetic user with `click_count=2`.

**Verify:** prints `model_version` conceptually `v3` and five or fewer item ids.

## Practical Exercises

1. Train, then change feature order in the ranker only — should fail or scramble; fix by using named columns.
2. Retrain with fewer features; old artifact vs new artifact are different versions.
3. Call `predict` with empty candidates — define behavior (raise, like service already does if catalog empty).

## Implementation Work

```text
ml/phase06_train_serve/
  train.py
  ranker.py
  NOTES_pipeline.md
  test_phase06.py
ml/artifacts/                 # gitignore large binaries if needed; meta.json can be committed
```

Production edits only if Task 6.5 is in scope and tests stay green.

## Tests / Verification

`pytest ml/phase06_train_serve/test_phase06.py -q`  
`pytest tests/test_recommendations.py -q` if `app/` changed.

## Expected Outcome

A trained artifact can rank candidates through the same function signature the service already uses. v1/v2 remain the default.

## Interview Questions

1. What is train/serve separation?
2. Why save a Pipeline (scaler + model) together?
3. Why must the model not query Redis?
4. `MODEL_VERSION` vs `SERVICE_VERSION`?
5. What happens if serving feature code diverges from training code? (preview of Phase 7)

## Completion Checklist

- [ ] Tasks 6.1–6.6 verified
- [ ] Artifact load + rank tests pass
- [ ] Production default still v1
- [ ] Model still has no infrastructure I/O
- [ ] Index: Phase 6 `COMPLETED`

## What The Next Phase Will Need

- Exact serving feature names
- Redis/Postgres as the **online** source of those names
- The skew question: training used point-in-time counts; serving uses Redis aggregates **now**

## Previous Phase

[`05_RANKING_AND_EVALUATION.md`](05_RANKING_AND_EVALUATION.md)

## Next Phase

[`07_FEATURE_STORE_AND_SERVING.md`](07_FEATURE_STORE_AND_SERVING.md)

## Recommended References

- [scikit-learn model persistence](https://scikit-learn.org/stable/model_persistence.html)
- [Google Rules of ML — train like you serve](https://developers.google.com/machine-learning/guides/rules-of-ml#training-serving_skew)
- [Google MLCC — transforming data](https://developers.google.com/machine-learning/crash-course/production-ml-systems/transforming-data)
