# Phase 8 — Model Experimentation

## Objective

Run structured comparisons: **v1 popularity vs v2 heuristic vs ML v3**. Record offline ranking metrics plus serving-oriented columns (latency, failure). Learn why offline wins do not automatically mean ship it.

## Why This Phase Exists

Google’s Rules of ML: start with a solid baseline, change one thing at a time, and measure. We already have CTR machinery for **online** comparison once traffic exists. This phase builds the experiment log.

## Relationship To Existing Recommendation Service

| Tool | Role |
| --- | --- |
| `GET /monitoring/model-quality` | Online CTR by `model_version` |
| `app/metrics.py` | latency histograms, prediction counts |
| Phase 5 evaluator | Offline Precision@K / NDCG@K |
| Canary (Phase 9) | How we would ship a winner |

Do not A/B in Kubernetes yet. Do not declare v3 production default from this phase alone.

## Prerequisites

- Phases 5–7 completed
- Three ways to produce a top-5 list for the same toy users

## Concepts To Learn

Experiment dimensions:

- Feature changes
- Algorithms
- Hyperparameters
- Training datasets (time window, negative sampling)

Record for each run:

| Field | Source |
| --- | --- |
| `model_version` | v1 / v2 / v3 / v3-depth3 / … |
| served / clicked / CTR | online, if we have traffic; else `n/a` |
| Precision@K, Recall@K, NDCG@K | offline evaluator, K=5 |
| latency | time `predict()` on toy batch; optionally `/metrics` |
| failure rate | exceptions / empty lists |

Offline vs online evaluation:

- Offline: fast, reproducible, can leak or not match UI
- Online: CTR, real users, delayed labels, position bias

## Tasks

### Task 8.1 — Experiment log format

`ml/phase08_experiments/EXPERIMENT_LOG.md` with a table (one row per run). Empty except headers first.

**Verify:** columns listed above exist.

### Task 8.2 — Freeze a dataset snapshot

Save the toy train/test split used for all comparisons (`ml/phase08_experiments/split_meta.json`: row counts, time cutoff).

**Verify:** three rankers evaluated on **that** test split only.

### Task 8.3 — Baseline row: v1

Fill the log for popularity.

### Task 8.4 — Baseline row: v2

Same split, production formula.

### Task 8.5 — ML row: v3 default hyperparameters

Log NDCG@5 etc.

### Task 8.6 — One-at-a-time change

Pick **one**: add `same_as_last_item` if missing, **or** change `C`, **or** drop `purchase_count`. New `model_version` id e.g. `v3-no-purchase`. New log row.

**Verify:** only one factor changed vs Task 8.5.

### Task 8.7 — Latency microbench

Time 100 `predict` calls locally for v2 vs v3. Record p50-style average. Not a K8s load test (that is `scripts/load_test.py` / Task 24).

**Verify:** numbers in the log; v3 may be slower — that is acceptable to know.

### Task 8.8 — Write the decision note

`DECISION.md`: ship / keep experimenting / do not ship, based on **offline** metrics + skew awareness. Explicit sentence: *offline NDCG cannot prove production CTR*.

## Practical Exercises

1. Two random seeds for train/test — if winner flips, the dataset is too small (likely). Document that limitation.
2. Optimize accuracy only; show it can disagree with NDCG@5 (reuse Phase 5 insight).
3. “Improve” v3 by leaking future counts — NDCG jumps; reject the run in the log as invalid.

## Implementation Work

```text
ml/phase08_experiments/
  EXPERIMENT_LOG.md
  split_meta.json
  run_baselines.py
  DECISION.md
  test_phase08.py          # log file has ≥3 data rows
```

## Tests / Verification

`pytest ml/phase08_experiments/test_phase08.py -q` — parse the markdown table, assert v1/v2/v3 rows.

## Expected Outcome

A paper trail of experiments. Habit: one change per run. Humility: online CTR still required before trusting v3.

## Interview Questions

1. Why keep a popularity baseline forever?
2. Offline vs online evaluation?
3. Why change one variable at a time?
4. How does our CTR endpoint complement NDCG?
5. Why might a better NDCG model lose CTR?

## Completion Checklist

- [ ] Tasks 8.1–8.8 verified
- [ ] Log has v1, v2, v3, and one variant
- [ ] DECISION.md written
- [ ] Default production model unchanged unless DECISION says otherwise (default: unchanged)
- [ ] Index: Phase 8 `COMPLETED`

## What The Next Phase Will Need

- A candidate champion (probably still v1 in prod) and challenger (v3)
- Artifact + version string
- Existing K8s canary as the **service** analog to model rollout

## Previous Phase

[`07_FEATURE_STORE_AND_SERVING.md`](07_FEATURE_STORE_AND_SERVING.md)

## Next Phase

[`09_MODEL_VERSIONING_AND_DEPLOYMENT.md`](09_MODEL_VERSIONING_AND_DEPLOYMENT.md)

## Recommended References

- [Google Rules of ML](https://developers.google.com/machine-learning/guides/rules-of-ml) — baselines, iterate on features
- [Microsoft Recommenders evaluation](https://microsoft-recommenders.readthedocs.io/en/latest/evaluation.html)
- [`system_architecture.md`](../../system_architecture.md) §8 model monitoring
