# Task 7.5 — Freshness

If the Kafka consumer is down, Redis is not updated. `get_user_features` still
returns **something**: the last materialized JSON, or `UserFeatures` defaults
(`click_count=0`, `purchase_count=0`, `last_item_id=None`) when the key is
missing — the same zeros as a cold-start user.

The v3 ranker will still run on those stale/zero features. Quality may drop
(the model thinks the user is new). If Redis errors enough, the existing
circuit breaker skips Redis entirely and `RecommendationService` never reaches
the ML path — it falls back to stored lists / `POPULAR_RECOMMENDATIONS`. Stale
features are a freshness problem; an open breaker is a availability problem.
Neither is computed with a point-in-time SQL join on the request path.
