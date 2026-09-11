# Phase 9 — Model Versioning and Deployment

## Objective

Connect **ML artifacts** to the deployment machinery we already have. Distinguish `SERVICE_VERSION` from `MODEL_VERSION`. Practice champion/challenger, shadow, canary, A/B, and rollback **without** inventing `deployment-v3.yaml` forever.

## Why This Phase Exists

Task 23 taught canary for **the service process**. A new ranker can ship inside the same image by changing env, or as a new image tag. Mixing those ideas causes bad rollbacks.

## Relationship To Existing Recommendation Service

| Existing | ML analogue |
| --- | --- |
| `SERVICE_VERSION` on `/health` | Deploy identity of the pod |
| `MODEL_VERSION` in config + response | Which ranker/artifact |
| `k8s/deployment.yaml` vs `deployment-v2.yaml` | Two **service** fleets; Service selector is `app` only |
| Rollback = delete v2 Deployment | Rollback model = point env back at `v1` / previous artifact |
| `get_model()` dict | Stub registry; later load by artifact id |

Inspect: `app/config.py`, `app/model_registry.py`, `app/schemas.py` (`model_version` on recommendations, `version` on health), `k8s/`.

## Prerequisites

- Phase 6 artifact loader
- Phase 8 decision note
- Read [`implementation_Readme_4.md`](../../implementation_Readme_4.md) Task 23 summary

## Concepts To Learn

- Model artifacts + `meta.json`
- Model schema compatibility (feature_schema_version from Phase 7)
- Model registry (ours: dict + files; production: MLflow/SageMaker-like — conceptual)
- Champion / challenger
- Shadow testing (challenger scores, user still sees champion)
- Canary (small % traffic) — we do **not** have Istio weights; local K8s round-robins Ready pods
- A/B testing (assign users, compare CTR)
- Rollback
- How to deploy model v3 **without** rebuilding the whole ML pipeline: new artifact + registry entry + env, same FastAPI code path

Clearly:

```text
SERVICE_VERSION  = which binary / image / pod fleet
MODEL_VERSION    = which ranking function / artifact
```

A pod can be service `v1` serving model `v3`.

## Tasks

### Task 9.1 — Write the distinction

`ml/phase09_deploy/NOTES_versions.md` with examples of four combinations (service × model).

**Verify:** `/health` vs recommendation JSON fields named correctly.

### Task 9.2 — Registry design

Propose (markdown) `get_model("v3")` → load artifact once at startup. Include failure mode: missing file → do not crash liveness if we keep v1 default.

**Verify:** matches model boundary (no Redis in loader except path string).

### Task 9.3 — Shadow scoring (offline)

For each test user, compute champion list and challenger list; log both; user-facing list stays champion.

**Verify:** script prints two lists; asserts they can differ.

### Task 9.4 — Canary plan on existing K8s

Document a **safe** experiment: do **not** run v1+v2 service Deployments during HPA. Options:

1. Same Deployment, `MODEL_VERSION=v3` on a **second** Deployment labeled `version=model-canary` still `app=recommendation-service` — traffic splits randomly (not 10%).
2. Or port-forward the canary Deployment for independent `/health` + `/recommendations` checks (how we validated service v2).

**Verify:** written steps; no requirement to apply YAML in this task if cluster is off — the doc is the deliverable.

### Task 9.5 — Rollback drill (documented)

Champion `MODEL_VERSION=v1`. Challenger misbehaves → set env back / delete canary Deployment. CTR and NDCG from Phase 8 tell you **after** the fact.

**Verify:** checklist of commands in NOTES (kubectl/compose).

### Task 9.6 — Compatibility

If v3 artifact expects 4 features and serving sends 3, refuse and fall back to v1 inside service **or** fail the model path so existing Postgres/popular fallback runs.

**Verify:** unit test of “bad artifact schema → raise” in `ml/` (production fallback already exists).

## Practical Exercises

1. Trace a request: cache hit returns **cached** `model_version` — canary analysis can be wrong if TTL is long. Document cache as a gotcha.
2. Two pods, different `MODEL_VERSION`, one Service: users get mixed models (uncontrolled A/B). Why weighted mesh is a next step.
3. Bump service image without changing model artifact — `/health` version changes, ranking does not.

## Implementation Work

```text
ml/phase09_deploy/
  NOTES_versions.md
  shadow.py
  rollback_checklist.md
  test_phase09.py
```

Optional: register `v3` if not done in Phase 6. Default env remains `v1`.

## Tests / Verification

`pytest ml/phase09_deploy/test_phase09.py -q`

Existing `tests/test_health_version.py` must still pass if we touch health schemas.

## Expected Outcome

You can ship a new ranker as an artifact + version string, validate it beside the champion, and roll back without deleting Kafka or Postgres.

## Interview Questions

1. Champion vs challenger?
2. Shadow vs canary vs A/B?
3. Why not pin the Service selector to `version` during canary?
4. How do we deploy model v3 without retraining the pipeline from scratch?
5. How does Redis response cache interfere with experiments?

## Completion Checklist

- [ ] Tasks 9.1–9.6 verified
- [ ] Version NOTES complete
- [ ] Shadow script works
- [ ] Production default still safe (v1)
- [ ] Index: Phase 9 `COMPLETED`

## What The Next Phase Will Need

- Prediction logs + CTR already in the app
- Offline drift helper `app/drift.py`
- Discipline: no heavy monitoring on the sync path

## Previous Phase

[`08_MODEL_EXPERIMENTATION.md`](08_MODEL_EXPERIMENTATION.md)

## Next Phase

[`10_ML_MONITORING_AND_DRIFT.md`](10_ML_MONITORING_AND_DRIFT.md)

## Recommended References

- [`implementation_Readme_4.md`](../../implementation_Readme_4.md) Task 23
- [`system_architecture.md`](../../system_architecture.md) §6 deployment
- [Google Rules of ML](https://developers.google.com/machine-learning/guides/rules-of-ml) — launch and iterate
