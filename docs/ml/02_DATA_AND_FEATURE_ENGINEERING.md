# Phase 2 — Data and Feature Engineering

## Objective

Connect ML fundamentals to **our** recommendation data: raw events, labels, feature types, missing values, time, and leakage — including point-in-time correctness **conceptually**.

## Why This Phase Exists

A click model is only as honest as its dataset. If we train on future clicks or on Redis features computed *after* the label, the model will look great offline and fail online.

## Relationship To Existing Recommendation Service

Inspect (do not redesign):

| Code / table | Use in this phase |
| --- | --- |
| `app/event_store.py` / `user_events` | Raw interactions |
| `app/features.py` `UserFeatures` | Online feature schema |
| `app/feature_store.py` | How Redis is updated from events |
| `app/recommendation_repository.py` | Item `score` as an item feature |
| `app/events.py` | `event_type`, `timestamp`, `device_type` |

Work lives in `ml/phase02_features/`. Prefer **synthetic tables that look like ours** if Compose is down. Optional: export a few real `user_events` rows for inspection only.

Do **not** build a production feature-store product here (that is Phase 7).

## Prerequisites

- Phase 1 completed
- Concepts: features, labels, leakage, train/test

## Concepts To Learn

- Raw events vs aggregated features vs labels
- Implicit feedback (`click`, `purchase`, `view`) vs explicit ratings (we do not have star ratings)
- Positive examples (clicked/purchased) and negatives (shown or available but not clicked)
- Numerical features: `click_count`, `purchase_count`, `score`
- Categorical features: `event_type`, `device_type`, `user_id` / `item_id` as IDs (usually **not** raw integers as “magnitude”)
- Missing values: new user → counts `0`, `last_item_id` `None`
- Normalization / standardization (why `score` 0.95 and `click_count` 200 are different scales)
- Timestamps and temporal features (recency, hour — optional later)
- Random split vs **time-based** split
- **Point-in-time correctness:** for a training row at time `t`, features may only use events **strictly before** `t`

## Tasks

### Task 2.1 — Inspect existing schemas

Read the files listed above. Write `ml/phase02_features/NOTES_schemas.md` mapping each field to: raw event / online feature / candidate / label / not-for-training.

**Verify:** `clicked` is listed as a **label we will derive**, not a Redis field today.

### Task 2.2 — Build a tiny interaction table

Create ~20–40 rows of fake events with columns:

`user_id, item_id, event_type, timestamp, item_score`  
(and optional `device_type`)

Include known users `123` and unknown-style users.

**Verify:** at least two event types and at least one user with multiple events.

### Task 2.3 — Derive labels

Define a training row as a **user–item pair at a time**:

- Positive: `event_type` in `{click, purchase}` → `clicked = 1` (or `engaged = 1`)
- Negative: `view` without a later click on that item, **or** sampled items the user did not interact with

Start simple: `clicked = 1` if click/purchase else `0` on the event row itself. Document why this is biased (no true “shown but not clicked” impressions yet).

**Verify:** label column is 0/1 only.

### Task 2.4 — Engineer features **as of** an event

For each labeled row, compute:

- `click_count_before`, `purchase_count_before` from **earlier** events of that user
- `last_item_id_before`
- `item_score`
- `same_as_last_item` (bool)

**Verify:** the first event for a user has counts `0`. A later click is **not** included in that same row’s counts (no same-event leakage).

### Task 2.5 — Missing values and types

Encode `last_item_id_before` missing as a flag `has_last_item=0`. Keep IDs out of the numeric matrix or treat them as categorical later. Standardize `item_score` with train-set mean/std only.

**Verify:** scaler fitted on train fold is applied to test fold (no test statistics in the scaler).

### Task 2.6 — Split without time travel

Compare:

1. Random `train_test_split` on rows
2. Sort by `timestamp`, train = earlier 70%, test = later 30%

Find at least one row in (1) where a user’s **future** count leaks into training conceptually.

**Verify:** written explanation of why (2) is the default for our service.

## Practical Exercises

1. Wrong-way feature: add `click_count_including_this_event` and watch it correlate almost perfectly with `clicked`.
2. Drop all negatives; see why a model that always predicts 1 “wins” accuracy.
3. New user at test time: features all zero — same as Redis defaults in `get_user_features`.

## Implementation Work

```text
ml/phase02_features/
  NOTES_schemas.md
  toy_events.py          # data
  labels.py
  point_in_time.py       # counts before timestamp
  splits.py
  test_phase02.py
```

No writes to Redis/Postgres required. Do not change `feature_store.py`.

## Tests / Verification

`pytest ml/phase02_features/test_phase02.py -q`

Must assert: point-in-time counts ignore the current event; temporal split has `max(train_time) <= min(test_time)`.

## Expected Outcome

You can look at Redis `click_count` and say: *this is a serving-time aggregate; a training row needs the aggregate as it would have been before the label event.*

## Interview Questions

1. Why is `clicked` a label and `click_count` a feature?
2. What is implicit feedback in our Kafka events?
3. Why is a random split dangerous with timestamps?
4. What is point-in-time correctness in one sentence?
5. How do our Redis defaults for a new user relate to missing-value handling?

## Completion Checklist

- [ ] Tasks 2.1–2.6 verified
- [ ] pytest passes
- [ ] Leakage anti-pattern documented
- [ ] `app/` unchanged
- [ ] Index: Phase 2 `COMPLETED`

## What The Next Phase Will Need

- A small labeled matrix: features + `clicked`
- Temporal split helper
- Clear feature names that can later match `UserFeatures` + candidate `score`

## Previous Phase

[`01_ML_FUNDAMENTALS.md`](01_ML_FUNDAMENTALS.md)

## Next Phase

[`03_FIRST_CLASSICAL_ML_MODEL.md`](03_FIRST_CLASSICAL_ML_MODEL.md)

## Recommended References

- [scikit-learn Preprocessing](https://scikit-learn.org/stable/modules/preprocessing.html)
- [Google Rules of ML — training-serving skew](https://developers.google.com/machine-learning/guides/rules-of-ml#training-serving_skew)
- [When to transform data (Google MLCC)](https://developers.google.com/machine-learning/crash-course/production-ml-systems/transforming-data)
