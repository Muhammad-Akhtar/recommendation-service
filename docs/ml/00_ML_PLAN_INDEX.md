# ML Learning Plan — Index

**This is the entry point for every new Cursor context window.**

Read this file first. Then read [`ML_CONTEXT.md`](ML_CONTEXT.md). Then open the next incomplete phase.

Source plans:

- [`ML_Implementation_Plan.md`](../../ML_Implementation_Plan.md) — original learning goals
- This folder — executable multi-phase plan

Existing production docs (do not reteach):

- [`Implementation_Summary.md`](../../Implementation_Summary.md)
- [`system_architecture.md`](../../system_architecture.md)

---

## Project objective

Take the existing **rule-based** recommendation models (`v1` popularity, `v2` heuristic formula) and progressively **learn and implement genuine machine learning** while preserving the production architecture already in this repo.

We are **not** rebuilding FastAPI, Redis, Kafka, Kubernetes, or the model I/O boundary.

Target end state:

```text
data → features → train → validate → evaluate → artifact → version
     → deploy → online inference → ranking → feedback → monitor → retrain
```

…wired into the existing:

```text
RecommendationService → model.predict(features, candidates) → ranked item ids
```

---

## Current state (as of plan creation)

Status of **this ML plan**: all phases `NOT STARTED`. No ML code, datasets, or libraries have been added yet.

### What is already implemented (production service)

| Area | Where |
| --- | --- |
| FastAPI serving + cache + fallbacks | `app/main.py` |
| Redis online features | `app/feature_store.py` — `features:user:{id}` |
| Postgres event history | `app/event_store.py` — `user_events` |
| Candidate catalog | `app/recommendation_repository.py` — `recommendation_items` |
| Service orchestration | `app/recommendation_service.py` |
| Model interface | `app/model.py` — `predict(features, candidates) -> list[int]` |
| In-process registry | `app/model_registry.py` — `get_model("v1"\|"v2")` |
| Prediction logs | `app/prediction_logger.py` |
| CTR / impressions | `app/model_quality.py` + `GET /monitoring/model-quality` |
| Offline drift helpers | `app/drift.py` |
| Prometheus / OTEL | `app/metrics.py`, `app/tracing.py` |
| Canary / HPA | `k8s/deployment.yaml`, `deployment-v2.yaml`, `hpa.yaml` |
| `MODEL_VERSION` vs `SERVICE_VERSION` | `app/config.py` |

### Current models (not ML)

**v1** (`SimpleRecommendationModel`): take the first 5 candidates already ordered by Postgres `score`. Ignores user features except type-checking them.

**v2** (`SimpleRecommendationModelV2`):

```text
final_score = candidate.score
            + click_count * 0.01
            + purchase_count * 0.05
            + 0.5  if item_id == last_item_id
```

Then top 5. Weights are **hand-written**, not learned.

These are **heuristics**. Calling the file `model.py` does not make them machine-learning models.

### Current feature store

- **Offline / durable:** PostgreSQL `user_events` (`user_id`, `item_id`, `event_type`, `created_at`)
- **Online:** Redis `features:user:{id}` → `{user_id, click_count, purchase_count, last_item_id}`
- Kafka consumer writes Postgres first, then materializes Redis
- No point-in-time training set, no feature versioning, no Feast

### Current event data

`UserInteractionEvent`: `user_id`, `item_id`, `event_type` (`view` / `click` / `purchase`), `timestamp`, optional `device_type`. Avro + Schema Registry.

There is **no training table** and **no `clicked` label column** used for `.fit()`.

### Current evaluation / CTR

- Online: `recommendations_served_total` / `recommendations_clicked_total` → CTR per `model_version`
- Click attribution: Redis `last_recs:{user_id}` (TTL 1h)
- **Missing:** Precision@K, Recall@K, Hit Rate@K, MAP@K, NDCG@K, ROC-AUC, log loss, train/val/test evaluation

### Current model registry / versioning

- Dict of live Python objects, not saved artifacts
- No `joblib` / pickle files
- Switching version = `MODEL_VERSION` env, not loading a trained file
- K8s canary is **service** identity (`SERVICE_VERSION`), not an ML artifact canary

---

## Gap analysis

| | Status | Notes |
| --- | --- | --- |
| **A. Already implemented** | MLOps shell | Model interface, registry hook, features, candidates, prediction logs, CTR, drift helper, canary, metrics |
| **B. Partially implemented** | Feature store, monitoring, versioning | Online/offline split exists; no training-time features, no artifact registry, drift is a toy threshold |
| **C. Not implemented** | Actual ML | No labels, splits, training, learned weights, ranking metrics, artifacts, retraining |
| **D. Learn next** | Phases 1–6 | Fundamentals → data → logistic regression → recsys concepts → ranking eval → train/serve |
| **E. Postpone** | Phase 12 | Matrix factorization, embeddings, ANN, LTR, NCF, deep rec models — conceptual first |

---

## Phase table

| Phase | File | Topic | Status | Depends On |
| --- | --- | --- | --- | --- |
| 1 | [`01_ML_FUNDAMENTALS.md`](01_ML_FUNDAMENTALS.md) | ML fundamentals | COMPLETED | Existing project (read-only) |
| 2 | [`02_DATA_AND_FEATURE_ENGINEERING.md`](02_DATA_AND_FEATURE_ENGINEERING.md) | Data and features | NOT STARTED | Phase 1 |
| 3 | [`03_FIRST_CLASSICAL_ML_MODEL.md`](03_FIRST_CLASSICAL_ML_MODEL.md) | Logistic regression (then trees) | NOT STARTED | Phases 1–2 |
| 4 | [`04_RECOMMENDATION_SYSTEMS.md`](04_RECOMMENDATION_SYSTEMS.md) | Recsys fundamentals | NOT STARTED | Phases 1–3 |
| 5 | [`05_RANKING_AND_EVALUATION.md`](05_RANKING_AND_EVALUATION.md) | Classification + ranking metrics | NOT STARTED | Phases 1–4 |
| 6 | [`06_TRAINING_SERVING_PIPELINE.md`](06_TRAINING_SERVING_PIPELINE.md) | Train/serve + `predict()` integration | NOT STARTED | Phases 1–5 |
| 7 | [`07_FEATURE_STORE_AND_SERVING.md`](07_FEATURE_STORE_AND_SERVING.md) | Online/offline features, skew | NOT STARTED | Phases 1–6 |
| 8 | [`08_MODEL_EXPERIMENTATION.md`](08_MODEL_EXPERIMENTATION.md) | v1 vs v2 vs ML v3 experiments | NOT STARTED | Phases 1–7 |
| 9 | [`09_MODEL_VERSIONING_AND_DEPLOYMENT.md`](09_MODEL_VERSIONING_AND_DEPLOYMENT.md) | Artifacts, champion/challenger, canary | NOT STARTED | Phases 1–8 |
| 10 | [`10_ML_MONITORING_AND_DRIFT.md`](10_ML_MONITORING_AND_DRIFT.md) | Drift types vs existing helpers | NOT STARTED | Phases 1–9 |
| 11 | [`11_PROGRESSIVE_MODEL_IMPROVEMENT.md`](11_PROGRESSIVE_MODEL_IMPROVEMENT.md) | LR → tree → RF → boosting | NOT STARTED | Phases 1–10 |
| 12 | [`12_ADVANCED_RECOMMENDATION_SYSTEMS.md`](12_ADVANCED_RECOMMENDATION_SYSTEMS.md) | Advanced concepts (mostly conceptual) | NOT STARTED | Phases 1–11 |

When a phase finishes, change its row to `COMPLETED` and set the next row to `IN PROGRESS`.

---

## Execution rules

1. Work on **exactly one phase** at a time.
2. Within a phase, work on **one task** at a time.
3. Do not jump ahead.
4. Do not implement future phases prematurely.
5. Before starting a phase, read the previous completed phase.
6. Before coding, inspect the existing project code relevant to that phase.
7. Do not rewrite working infrastructure unless the phase explicitly requires a small, justified change.
8. Every phase must contain **theory + implementation + experiment + verification**.
9. Every completed task must have a verification step.
10. Update **this index** when a phase is completed.
11. Do not mark a phase complete until its exercises/tests pass.
12. Prefer understanding over abstraction.
13. Start with classical ML before deep learning.
14. Do not introduce LLMs just because this is an AI/ML project.
15. Preserve the model boundary: models must not access Redis, PostgreSQL, Kafka, or HTTP.
16. Do not pretend v1/v2 are ML models.

When executing a phase, put learning code under `ml/` (created in Phase 1). Keep production code in `app/` unless a later phase explicitly integrates a trained model through `model.py` / `model_registry.py`.

---

## Context recovery instructions

```text
WHEN STARTING A NEW CONTEXT WINDOW:

1. Read docs/ml/00_ML_PLAN_INDEX.md.
2. Read docs/ml/ML_CONTEXT.md.
3. Determine the current IN PROGRESS / next NOT STARTED phase.
4. Read that phase file.
5. Read the immediately previous completed phase (if any).
6. Inspect the relevant existing source code listed in the phase.
7. Continue from the first incomplete task.
8. Do not restart completed work.
9. Do not implement later phases.
10. After finishing a phase: update this index Status column, then stop.
```

**Right now:** Phase 1 is COMPLETED. Next phase is NOT STARTED.

**NEXT ACTION: Start Phase 2, Task 2.1**

---

## Planned learning code layout (created when phases execute)

```text
ml/                          # NOT created until Phase 1 starts
├── phase01_fundamentals/
├── phase02_features/
├── phase03_classical_ml/
├── phase05_evaluation/
├── artifacts/               # trained models, later phases
└── README.md
```

Do not create this tree until Phase 1 implementation begins.
