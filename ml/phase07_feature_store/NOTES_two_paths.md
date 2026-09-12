# Task 7.1 — Serving DAG vs training DAG

## Serving (online, now)

```text
POST /interactions → Kafka user-interactions
    → kafka_consumer: Postgres user_events (SoR)
    → apply_interaction_event → Redis features:user:{id}
    → RecommendationService.get_user_features  (no COUNT(*))
    → model.predict(UserFeatures, candidates)
```

| Serving field (`UserFeatures`) | Training counterpart | Same recipe? |
| --- | --- | --- |
| `click_count` | `click_count_before` | Only if we replay events **strictly before** t with the same click/+1 rule |
| `purchase_count` | `purchase_count_before` | Same |
| `last_item_id` | `last_item_id_before` / `has_last_item` / `same_as_last_item` | Same last-item assignment on every event type |
| `candidate.score` | `item_score` | Catalog score at serve time vs score copied onto the training row |

## Training (offline, as-of t)

```text
historical events (toy table standing in for user_events)
    → point-in-time features (Phase 2)
    → labels from event_type
    → sklearn Pipeline artifact (Phase 6)
```

**Skew** is when Redis “now” (all events including the label click) is used as if it were `click_count_before`.

`prediction_logged` already stores serving `click_count` / `purchase_count` / `last_item_id` so a later job could train on *logged serving features* (Google Rule #29). We do not require that log as the training source yet.
