# Phase 10 — ML Monitoring and Drift

## Objective

Learn the ML meaning of the monitoring we already built: feature/data/prediction/concept drift, delayed labels, feedback loops, training-serving skew. Extend **offline** analysis only. Never put expensive drift computation inside `GET /recommendations`.

## Why This Phase Exists

Task 22 added logs, CTR, and a toy `detect_drift(current, baseline, threshold)`. That helper is not a full monitoring system. This phase teaches what to measure in a recommender and how it maps to our files.

## Relationship To Existing Recommendation Service

| Existing | Concept |
| --- | --- |
| `app/prediction_logger.py` | Prediction log (features snapshot + recs + version) |
| `app/model_quality.py` + CTR | Online quality; delayed click labels |
| `app/drift.py` | Relative change vs baseline (feature mean) |
| `DRIFT_*` in `app/config.py` | Baselines for click/purchase means |
| Prometheus histograms | Latency / volume — not concept drift |
| `GET /monitoring/model-quality` | Compare versions by CTR |

Inspect those files. Implementation in this phase: notebooks/scripts under `ml/phase10_monitoring/` that **read logs or fixtures**, not new work in the request handler.

## Prerequisites

- Phases 6–9 conceptually done
- Know that labels (clicks) arrive later via `POST /interactions`

## Concepts To Learn

| Kind | Meaning | Our example |
| --- | --- | --- |
| Data / feature drift | Input distribution changes | mean `click_count` 10 → 100 |
| Prediction drift | Output distribution changes | always item `10` vs diverse lists |
| Concept drift | P(y\|x) changes | clicks no longer follow last_item boost |
| Model degradation | Quality drops while app is “healthy” | CTR 8% → 2%, `/health` still ok |
| Delayed labels | y arrives after the prediction | click hours later; `last_recs` TTL 1h |
| Feedback loops | Model changes future data | popular items get more clicks → more training positives |
| Training-serving skew | Train recipe ≠ serve recipe | Phase 7 |

Preserve: drift analysis is **offline / batch**.

## Tasks

### Task 10.1 — Map concepts to code

`NOTES_map.md`: each concept → file/metric or “not implemented”.

**Verify:** concept drift is **not** claimed as implemented by `detect_drift`.

### Task 10.2 — Use the existing helper correctly

From a fixture list of `click_count` values, call `check_feature_drift`. Include a case below and above threshold 0.5.

**Verify:** pytest can import `app.drift` (project root on `PYTHONPATH`).

### Task 10.3 — Prediction drift fixture

Two windows of recommended item histograms (e.g. item 10 share 20% vs 90%). Document as prediction drift, not feature drift.

**Verify:** a computed share delta in NOTES.

### Task 10.4 — Delayed labels

Timeline: t=0 serve items `[10,20]`; t=+2h click item 10 after TTL. Show CTR undercount.

**Verify:** paragraph tying TTL=3600 to missed attribution.

### Task 10.5 — Feedback loop thought experiment

If v1 always returns top catalog scores, training on resulting clicks reinforces popularity. Write 5–8 lines. No code required.

### Task 10.6 — What we will not do

Checklist of “do not”: NDCG in the request path; `detect_drift` per request; blocking Kafka consumer on a drift job.

**Verify:** listed in NOTES.

### Task 10.7 — Optional batch job sketch

Script that reads a JSONL of fake `prediction_logged` lines and prints mean features vs `DRIFT_CLICK_BASELINE`.

**Verify:** runs on a 10-line fixture.

## Practical Exercises

1. Redis down: fewer prediction logs (model path skipped) — monitoring goes quiet; `/ready` still ready. Interpret carefully.
2. Canary mixed traffic without logging `model_version` would be useless — we **do** log it.
3. Baseline `DRIFT_CLICK_BASELINE=10` is arbitrary; changing it flips alerts — treat as a hyperparameter of monitoring, not of the ranker.

## Implementation Work

```text
ml/phase10_monitoring/
  NOTES_map.md
  fixture_predictions.jsonl
  batch_feature_means.py
  test_phase10.py
```

Do not modify `recommendation_service.py` to call `detect_drift`.

## Tests / Verification

`pytest ml/phase10_monitoring/test_phase10.py tests/test_drift.py -q`

## Expected Outcome

You can tell an interviewer: *we log predictions and CTR online; we estimate feature drift offline against a baseline; concept drift needs labels and is not a single ratio helper; none of this runs inside the recommend handler.*

## Interview Questions

1. Data vs concept vs prediction drift?
2. Why are recsys labels delayed?
3. What is a feedback loop in popularity models?
4. Why keep drift off the request path?
5. How do prediction logs help training-serving skew (Rule #29)?

## Completion Checklist

- [ ] Tasks 10.1–10.7 verified
- [ ] `detect_drift` not added to the hot path
- [ ] pytest passes
- [ ] Index: Phase 10 `COMPLETED`

## What The Next Phase Will Need

- Stable training/eval harness (Phases 3, 5, 6, 8)
- Permission to try stronger **classical** models only if they beat v3 on the same split

## Previous Phase

[`09_MODEL_VERSIONING_AND_DEPLOYMENT.md`](09_MODEL_VERSIONING_AND_DEPLOYMENT.md)

## Next Phase

[`11_PROGRESSIVE_MODEL_IMPROVEMENT.md`](11_PROGRESSIVE_MODEL_IMPROVEMENT.md)

## Recommended References

- [Google MLCC — monitoring pipelines](https://developers.google.com/machine-learning/crash-course/production-ml-systems/monitoring)
- [`app/drift.py`](../../app/drift.py) and [`implementation_Readme_3.md`](../../implementation_Readme_3.md) Task 22
- [Google Rules of ML](https://developers.google.com/machine-learning/guides/rules-of-ml)
