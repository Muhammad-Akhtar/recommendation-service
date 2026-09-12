# Phase 2 — recorded experiments

Synthetic table: 32 events, users `123`/`456`/`789` (known) and `999`/`1001` (unknown-style). No Redis/Postgres writes. `app/` unchanged.

## Task 2.3 — label bias

Event-row `clicked` is 1 for click/purchase, 0 for view. There is no “shown but not clicked” impression, so this is **not** CTR. Exercise 2: drop all negatives → always-predict-1 accuracy = **1.000**.

## Task 2.4 — point-in-time

User `123` first event (`2026-01-01T10:00:00Z` view): `click_count_before=0`, `purchase_count_before=0`, `last_item_id_before=None`.

That user’s first click one minute later still has `click_count_before=0` — the click is the label, not a feature on the same row.

Exercise 1 (wrong-way count includes this event’s click): Pearson corr with `clicked` is **0.304** vs honest `click_count_before` **0.022**.

## Task 2.5 — missing values and scaling

`has_last_item=0` when `last_item_id_before` is missing. Numeric matrix columns: `click_count_before`, `purchase_count_before`, `item_score`, `same_as_last_item`, `has_last_item`. IDs stay out.

`StandardScaler` is fitted on the **train** fold of a temporal split only, then applied to test (test mean of `item_score_std` is not forced to 0).

Exercise 3: user `1001`’s only row is a first view — counts 0, `has_last_item=0` — same shape as Redis `get_user_features` for a user with no key.

## Task 2.6 — split without time travel

Random `train_test_split` (seed=0) example: user `999` has `train_ts=2026-01-08T08:00:00Z` and `test_ts=2026-01-02T11:30:00Z` — future in train.

Temporal 70/30: `max(train)=2026-01-10T08:00:00Z` <= `min(test)=2026-01-10T08:01:00Z`.

Default for this service is (2): production Redis features are causal; a random row split trains on the future.
