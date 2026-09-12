# Task 2.1 — Schema map (our service vs training)

Inspected (read-only): `app/events.py`, `app/event_store.py`, `app/database.py`,
`app/features.py`, `app/feature_store.py`, `app/recommendation_repository.py`.

`clicked` is **not** stored in Redis, Postgres, or Kafka. It is a **label we
derive** from `event_type` (Task 2.3). Redis today only keeps serving-time
aggregates (`click_count`, `purchase_count`, `last_item_id`).

| Field | Where it lives | Role |
| --- | --- | --- |
| `user_events.id` | Postgres PK | not-for-training |
| `user_id` | Kafka event, `user_events`, Redis `UserFeatures` | raw event / online identity. Categorical ID — **not** a numeric magnitude |
| `item_id` | Kafka event, `user_events`, candidate row | raw event / candidate id. Categorical ID — **not** a numeric magnitude |
| `event_type` | Kafka `UserInteractionEvent`, `user_events` | raw event. Values: `view` / `click` / `purchase`. Used to **derive the label**, not fed as a count |
| `timestamp` | Kafka event (`timestamp`) | raw event. Ordering + temporal split. Not a model feature in this phase |
| `created_at` | Postgres `user_events` | durable copy of event time. Same role as `timestamp` |
| `device_type` | Kafka event only (optional). **Not** in `user_events` | raw event / optional categorical. Durable table does not persist it |
| `click_count` | Redis `features:user:{id}` (`UserFeatures`) | **online feature** (serving-time aggregate). Training needs `click_count_before` (events strictly before `t`) |
| `purchase_count` | Redis `UserFeatures` | online feature. Training: `purchase_count_before` |
| `last_item_id` | Redis `UserFeatures` | online feature. New user → `None` (same as `UserFeatures` defaults). Training: `last_item_id_before` |
| `RecommendationCandidate.item_id` | `recommendation_items` | candidate identity |
| `RecommendationCandidate.score` | `recommendation_items.score` | **item feature** (`item_score`). Popularity prior, not a label |
| `recommendations` JSON list | Postgres fallback store | not-for-training (cached output, not events) |
| `cache:recommendations:*` | Redis | not-for-training |
| `last_recs:*` | Redis CTR attribution | not-for-training (Phase 2) |
| **`clicked`** | **nowhere in prod today** | **label we will derive** (`1` if click/purchase else `0`). Not a Redis field |

Redis update rules (`apply_interaction_event`): click increments `click_count`;
purchase increments `purchase_count`; **every** event type sets `last_item_id`.
A training row at time `t` must reconstruct those fields from events **strictly
before** `t`, otherwise the label event leaks into the features.
