# Phase 7 — Feature Store and Serving

## Objective

Connect training features to the **existing** Redis/PostgreSQL split. Learn freshness, versioning, training-serving skew, and point-in-time correctness in enough depth to extend our store — without installing Feast unless we explicitly decide later.

## Why This Phase Exists

We already have:

```text
PostgreSQL user_events     → durable history
        ↓  Kafka consumer
Redis features:user:{id}   → online inference
        ↓
model inference
```

Training used a different path:

```text
historical events → point-in-time dataset → trained model
```

If those two computations diverge, the v3 model is untrustworthy. Google calls this **training-serving skew**.

## Relationship To Existing Recommendation Service

Inspect:

- `app/feature_store.py` — `apply_interaction_event` rules
- `app/event_store.py` — SoR
- `app/kafka_consumer.py` — history then Redis
- `app/recommendation_service.py` — reads Redis only, not `COUNT(*)`

This phase may add **offline training helpers** under `ml/` that replay `user_events` with the **same rules** as `apply_interaction_event`. Avoid duplicating logic forever — prefer extracting a pure function later if needed.

Do not compute features with SQL in the model. Do not run drift jobs on the request path.

## Prerequisites

- Phase 6 artifact + feature name list
- Phase 2 point-in-time functions

## Concepts To Learn

- Offline features (batch, historical, for training)
- Online features (low-latency, latest, for serving)
- Feature freshness (how stale is Redis vs last event?)
- Feature versioning (schema v1: three fields; later we might add recency)
- Training-serving skew (schema skew vs feature skew)
- Point-in-time correctness (Phase 2, now tied to the real consumer logic)
- Feature pipelines (Kafka → PG → Redis is ours)

Google Rule #29: log serving features when possible so training can reuse them. We do not require a full production log yet; understand why `prediction_logged` already captures `click_count` / `purchase_count` / `last_item_id`.

## Tasks

### Task 7.1 — Document the two DAGs

`ml/phase07_feature_store/NOTES_two_paths.md` — serving DAG vs training DAG, field-by-field.

**Verify:** each serving feature has a training counterpart.

### Task 7.2 — Reuse the same update rules

Extract or copy the click/purchase/`last_item_id` rules into a **pure** function (no Redis). Replay a list of events; compare final state to what Redis would hold.

**Verify:** pytest — three events (click, click, purchase) → counts 2, 1, last_item of purchase.

### Task 7.3 — Point-in-time vs “current Redis”

For a labeled event at time t, compare:

- features from events `< t` (correct train row)
- features from **all** events (wrong — future leakage)

**Verify:** at least one fixture where the two disagree.

### Task 7.4 — Skew experiment

Train a tiny model on leaked (wrong) features; evaluate on correct point-in-time test features (or vice versa). Record metric drop.

**Verify:** NOTES with the two scores. This is the “why we care” experiment.

### Task 7.5 — Freshness

If the consumer is down, Redis is stale. Document: model still runs; quality may drop; circuit breaker may skip Redis entirely (then we never reach the ML path — existing fallback).

**Verify:** paragraph linking `get_user_features` defaults (zeros) to cold start.

### Task 7.6 — Version the feature schema

Add `feature_schema_version: "fs1"` to artifact `meta.json`. Serving ranker refuses to run if schema mismatch.

**Verify:** test mismatch raises.

## Practical Exercises

1. Apply a `view` event: only `last_item_id` changes — same as production.
2. Two consumers in theory (history vs features): we have one group doing both; document the production-vs-learning gap from `system_architecture.md`.
3. Change Redis key JSON without changing training — watch skew.

## Implementation Work

```text
ml/phase07_feature_store/
  NOTES_two_paths.md
  feature_rules.py          # pure event → feature update
  replay.py
  skew_experiment.py
  test_phase07.py
```

Optional small refactor: move pure rules to a module imported by `feature_store.py` **only if** tests in `tests/test_feature_store.py` stay green. Not required to complete the phase.

## Tests / Verification

`pytest ml/phase07_feature_store/test_phase07.py -q`

## Expected Outcome

You can explain: Postgres is history; Redis is a materialized view; training must replay history **as of t**; serving reads the view **now**. Skew is when those recipes differ.

## Interview Questions

1. Offline vs online feature store in our repo?
2. What is training-serving skew?
3. Why not `SELECT COUNT(*)` on every recommend request?
4. Why is point-in-time correctness a leakage issue?
5. What does feature freshness mean if Kafka lags?

## Completion Checklist

- [ ] Tasks 7.1–7.6 verified
- [ ] pytest passes
- [ ] Skew experiment recorded
- [ ] Request path still has no batch PIT joins
- [ ] Index: Phase 7 `COMPLETED`

## What The Next Phase Will Need

- Honest offline metrics (Phase 5) + awareness of skew
- v1 / v2 / v3 as experiment arms
- Existing CTR endpoint for “online” column (even if toy traffic)

## Previous Phase

[`06_TRAINING_SERVING_PIPELINE.md`](06_TRAINING_SERVING_PIPELINE.md)

## Next Phase

[`08_MODEL_EXPERIMENTATION.md`](08_MODEL_EXPERIMENTATION.md)

## Recommended References

- [Google Rules of ML — training-serving skew](https://developers.google.com/machine-learning/guides/rules-of-ml#training-serving_skew)
- [Google MLCC — monitoring / skew](https://developers.google.com/machine-learning/crash-course/production-ml-systems/monitoring)
- [Feast + point-in-time (conceptual; we are not required to install it)](https://cloud.google.com/blog/products/databases/getting-started-with-feast-on-google-cloud)
