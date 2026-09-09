# Manual Testing Guide (QA)

Simple end-to-end checks for a QA intern:

- **Part A** — simulate interactions → Kafka → Postgres/Redis → model ranking  
- **Part B** — observability & model monitoring (Task 21–22): read JSON logs, force miss/hit/Redis-down, CTR

Base URL: `http://localhost:8000`

---

## 1. Big picture (what to verify)

```text
YOU (API call)
   │
   │  POST /interactions
   ▼
Kafka topic: user-interactions
   │
   │  (kafka-consumer background service)
   ▼
┌──────────────────┬─────────────────────────────┐
│ PostgreSQL       │ Redis                       │
│ user_events      │ features:user:{id}          │
│ (raw history)    │ (click/purchase/last_item)  │
└──────────────────┴─────────────────────────────┘
                          │
                          │  GET /recommendations/{user_id}
                          ▼
              Redis features + Postgres candidates
                          │
                          ▼
                    Model v1 / v2 ranking
                          │
                          ▼
              Cache: cache:recommendations:{id}
```

| Store | What it holds | Updated when |
| --- | --- | --- |
| Kafka | Raw interaction events | Immediately on `POST /interactions` |
| Postgres `user_events` | Durable history (every click/purchase/view) | Kafka consumer processes event |
| Redis `features:user:*` | Counts for the model | Same consumer, after Postgres write |
| Postgres `recommendation_items` | Candidate catalog (seeded) | Seed script / startup |
| Redis `cache:recommendations:*` | Cached ranked list | After a recommendations GET |

**Important:** Click/purchase counts are **not** written on `GET /recommendations`. They are written by the **Kafka consumer** after you post interactions.

---

## 2. Start the system

From the project root:

```powershell
docker compose up -d --build
```

Wait ~30–60 seconds, then check:

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/ready
```

**Expect**

```json
{ "status": "ok" }
```

```json
{
  "status": "ready",
  "redis": "up",
  "postgres": "up",
  "kafka": "up",
  "schema_registry": "up",
  "fallback": "available"
}
```

If Kafka/Postgres/Redis show `"down"`, wait and retry `/ready`.

### Seed candidate + fallback data (once)

```powershell
docker compose exec app python -m app.seed
```

This fills:

- `recommendation_items` — catalog the model ranks (items 10, 20, 30, …)
- `recommendations` — per-user fallback rows for users `123`, `456`, `789`

---

## 3. API cheat sheet

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Process alive? |
| GET | `/ready` | Redis / Postgres / Kafka status |
| POST | `/interactions` | Simulate user click / purchase / view → Kafka |
| GET | `/events/{user_id}` | History from **Postgres** |
| GET | `/features/{user_id}` | Online features from **Redis** |
| GET | `/recommendations/{user_id}` | Model ranking (or cache / fallback) |

Swagger UI (optional): open [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 4. Scenario A — Fresh user: interactions → history → features

Use a **new** `user_id` so data is clean (example: `9001`).

### Step A1 — Send a click

```powershell
Invoke-RestMethod -Method POST -Uri http://localhost:8000/interactions `
  -ContentType "application/json" `
  -Body '{"user_id":9001,"item_id":42,"event_type":"click"}'
```

**Expect (HTTP 202)**

```json
{
  "status": "published",
  "topic": "user-interactions",
  "event": {
    "user_id": 9001,
    "item_id": 42,
    "event_type": "click",
    "timestamp": "...",
    "device_type": null
  }
}
```

This only means: **published to Kafka**. Postgres/Redis update a moment later via the consumer.

### Step A2 — Send another click + a purchase

```powershell
Invoke-RestMethod -Method POST -Uri http://localhost:8000/interactions `
  -ContentType "application/json" `
  -Body '{"user_id":9001,"item_id":50,"event_type":"click"}'

Invoke-RestMethod -Method POST -Uri http://localhost:8000/interactions `
  -ContentType "application/json" `
  -Body '{"user_id":9001,"item_id":10,"event_type":"purchase"}'
```

### Step A3 — Wait, then check Postgres history

```powershell
Start-Sleep -Seconds 2
Invoke-RestMethod http://localhost:8000/events/9001
```

**Expect** — 3 rows (order may vary by `id`):

| user_id | item_id | event_type |
| --- | --- | --- |
| 9001 | 42 | click |
| 9001 | 50 | click |
| 9001 | 10 | purchase |

### Step A4 — Check Redis online features

```powershell
Invoke-RestMethod http://localhost:8000/features/9001
```

**Expect**

```json
{
  "user_id": 9001,
  "click_count": 2,
  "purchase_count": 1,
  "last_item_id": 10
}
```

Feature rules:

| `event_type` | What changes in Redis |
| --- | --- |
| `click` | `click_count += 1`, `last_item_id = item_id` |
| `purchase` | `purchase_count += 1`, `last_item_id = item_id` |
| `view` (or other) | only `last_item_id = item_id` (counts unchanged) |

### Step A5 — Optional: inspect stores directly

**Redis features**

```powershell
docker exec recommendation-redis redis-cli GET features:user:9001
```

**Postgres history**

```powershell
docker exec recommendation-postgres psql -U recommendation_user -d recommendations `
  -c "SELECT id, user_id, item_id, event_type, created_at FROM user_events WHERE user_id = 9001 ORDER BY id;"
```

**Kafka consumer logs** (see processing)

```powershell
docker compose logs --tail=50 kafka-consumer
```

---

## 5. Scenario B — Model prediction (v1)

Default `MODEL_VERSION` is **v1** (popularity only — uses candidate scores, ignores user clicks for ranking order).

### Clear recommendation cache first

Otherwise you may see an old cached answer:

```powershell
docker exec recommendation-redis redis-cli DEL cache:recommendations:9001
```

### Call recommendations

```powershell
Invoke-RestMethod http://localhost:8000/recommendations/9001
```

**Expect (v1)** — top 5 candidates by Postgres score:

```json
{
  "user_id": 9001,
  "recommendations": [10, 20, 30, 40, 50],
  "model_version": "v1"
}
```

Seeded candidate scores (highest first):

| item_id | score |
| --- | ---: |
| 10 | 0.95 |
| 20 | 0.91 |
| 30 | 0.88 |
| 40 | 0.84 |
| 50 | 0.80 |
| 60 | 0.76 |
| … | … |

### Call again (cache)

```powershell
Invoke-RestMethod http://localhost:8000/recommendations/9001
```

Same JSON. App log / behavior: **Cache HIT** (served from `cache:recommendations:9001`, model not re-run). TTL is ~120 seconds.

Check cache key:

```powershell
docker exec recommendation-redis redis-cli GET cache:recommendations:9001
```

---

## 6. Scenario C — Model prediction (v2) with personalization

v2 formula (simple):

```text
final_score =
    candidate_score
  + click_count * 0.01
  + purchase_count * 0.05
  + 0.5   if item_id == last_item_id
```

Then take top 5.

### Switch app to v2

In `docker-compose.yml`, under the `app` service `environment`, change:

```yaml
- MODEL_VERSION=v1
```

to:

```yaml
- MODEL_VERSION=v2
```

Then recreate the app:

```powershell
docker compose up -d --force-recreate app
```

### Make last_item something in the catalog

User `9001` already has `last_item_id: 10` from the purchase. Item **10** is also the top candidate — so v2 still puts **10** first (boost + high base score).

To see a clearer boost effect, interact with a **lower-ranked** catalog item, e.g. `90`:

```powershell
Invoke-RestMethod -Method POST -Uri http://localhost:8000/interactions `
  -ContentType "application/json" `
  -Body '{"user_id":9001,"item_id":90,"event_type":"click"}'

Start-Sleep -Seconds 2
Invoke-RestMethod http://localhost:8000/features/9001
```

**Expect** `last_item_id` = `90`, `click_count` increased by 1.

Clear cache and recommend:

```powershell
docker exec recommendation-redis redis-cli DEL cache:recommendations:9001
Invoke-RestMethod http://localhost:8000/recommendations/9001
```

**Expect (v2):** item **90** moves up (often near the top) because of the **+0.5** last-item boost, even though its base score is only 0.65.

`model_version` in the response should be `"v2"`.

Reset to v1 when done:

```powershell
# set MODEL_VERSION=v1 again, then:
docker compose up -d --force-recreate app
```

---

## 7. Scenario D — Fallback paths (optional QA)

### Seeded Postgres store users

Users `123`, `456`, `789` have rows in table `recommendations` (Task 14 fallback). If the **model path fails** (e.g. Redis down / no candidates), API may return those lists with `model_version: "postgres-store"`.

Normal healthy stack usually hits the **model** path first, not this store.

### Popular fallback

If model and Postgres store both fail: `model_version: "popular-fallback"`.

---

## 8. Scenario E — Bad payload (validation)

```powershell
# Missing fields / wrong types → HTTP 422
try {
  Invoke-RestMethod -Method POST -Uri http://localhost:8000/interactions `
    -ContentType "application/json" `
    -Body '{"user_id":"abc","item_id":1}'
} catch {
  $_.Exception.Response.StatusCode.value__
}
```

**Expect:** `422` (Pydantic validation).

Optional field that is allowed:

```powershell
Invoke-RestMethod -Method POST -Uri http://localhost:8000/interactions `
  -ContentType "application/json" `
  -Body '{"user_id":9002,"item_id":20,"event_type":"view","device_type":"mobile"}'
```

---

## 9. Database schemas (what to query)

### `user_events` (history — written by Kafka consumer)

```sql
SELECT * FROM user_events WHERE user_id = 9001 ORDER BY id;
```

Columns: `id`, `user_id`, `item_id`, `event_type`, `created_at`

### `recommendation_items` (candidates for the model)

```sql
SELECT item_id, score, is_active
FROM recommendation_items
WHERE is_active
ORDER BY score DESC;
```

### `recommendations` (per-user fallback store — seeded)

```sql
SELECT user_id, recommendations FROM recommendations;
```

Example row: user `123` → `[10, 25, 42, 81, 99]`

---

## 10. Redis keys (quick mental model)

| Key | Meaning | Who writes it |
| --- | --- | --- |
| `features:user:9001` | Online features for model | Kafka consumer |
| `cache:recommendations:9001` | Cached API response | Recommendations endpoint after ranking |

```powershell
docker exec recommendation-redis redis-cli KEYS "features:user:*"
docker exec recommendation-redis redis-cli KEYS "cache:recommendations:*"
```

---

## 11. Suggested QA checklist

Use a notepad and tick as you go:

- [ ] `/health` → `ok`
- [ ] `/ready` → redis/postgres/kafka up
- [ ] Seed ran successfully
- [ ] `POST /interactions` returns `published` + topic `user-interactions`
- [ ] After ~2s, `GET /events/{id}` shows the same events (Postgres)
- [ ] `GET /features/{id}` shows correct click/purchase/last_item (Redis)
- [ ] Direct Redis/Postgres checks match the APIs
- [ ] Consumer logs show the event processed
- [ ] `GET /recommendations/{id}` returns top-5 + `model_version`
- [ ] Second GET is cache hit (same data; cache key exists)
- [ ] After `DEL` cache + new interaction, features/ranking update
- [ ] (Optional) v2 boosts `last_item_id` into the top list
- [ ] Bad JSON → 422

---

## 12. Mini script — full happy path (copy/paste)

```powershell
$user = 9003

# 1) Interactions → Kafka
Invoke-RestMethod -Method POST -Uri http://localhost:8000/interactions -ContentType "application/json" -Body "{`"user_id`":$user,`"item_id`":42,`"event_type`":`"click`"}"
Invoke-RestMethod -Method POST -Uri http://localhost:8000/interactions -ContentType "application/json" -Body "{`"user_id`":$user,`"item_id`":50,`"event_type`":`"click`"}"
Invoke-RestMethod -Method POST -Uri http://localhost:8000/interactions -ContentType "application/json" -Body "{`"user_id`":$user,`"item_id`":10,`"event_type`":`"purchase`"}"

Start-Sleep -Seconds 2

# 2) History (Postgres) + Features (Redis)
Invoke-RestMethod "http://localhost:8000/events/$user"
Invoke-RestMethod "http://localhost:8000/features/$user"

# 3) Clear cache + model ranking
docker exec recommendation-redis redis-cli DEL "cache:recommendations:$user"
Invoke-RestMethod "http://localhost:8000/recommendations/$user"

# 4) Cache hit
Invoke-RestMethod "http://localhost:8000/recommendations/$user"
```

**Typical happy-path results for user `9003`**

| Check | Expected |
| --- | --- |
| Events | 2 clicks + 1 purchase |
| Features | `click_count=2`, `purchase_count=1`, `last_item_id=10` |
| Recommendations (v1) | `[10, 20, 30, 40, 50]`, `model_version=v1` |

---

## 13. Troubleshooting

| Symptom | What to check |
| --- | --- |
| Events/features empty after POST | `docker compose logs kafka-consumer` — is consumer running? |
| `/ready` kafka down | `docker compose ps` — wait for kafka healthy |
| Recommendations always same after new clicks | Delete `cache:recommendations:{user_id}` |
| Empty / error on model path | Run seed: `docker compose exec app python -m app.seed` |
| Wrong model version | Check `MODEL_VERSION` on app container / compose |

---

**One-line summary for QA:** Post interactions → wait → confirm Postgres history and Redis features → clear cache → call recommendations → confirm the ranked list and `model_version`.

---

# Part B — Observability & Model Monitoring (Task 21 + 22)

Use this when a “bug” is really: *slow API*, *wrong fallback*, *model not running*, or *CTR looks bad*.  
You will **regenerate cases on purpose**, then **follow JSON logs + metrics** like production on-call.

```text
API call  ──►  X-Request-ID (correlation)
                 │
                 ├── Application logs (cache / redis / fallback)
                 ├── Model logs (prediction_logged)
                 └── Metrics (/metrics, /monitoring/model-quality)
```

---

## 14. How to watch logs (always start here)

Open a **second terminal** and stream the API container:

```powershell
docker compose logs -f app
```

Optional: only JSON-looking lines, or a known request id later:

```powershell
docker compose logs -f app | Select-String "event|request_id|prediction"
```

Each useful line is **one JSON object**. Important fields:

| Field | Meaning |
| --- | --- |
| `event` | What happened (`cache_hit`, `prediction_logged`, …) |
| `request_id` | Ties every log line of **one** HTTP request together |
| `user_id` | Which user |
| `level` | `info` / `warning` |
| `source` | Where the recommendation came from (`cache`, `model`, `postgres-store`, `popular-fallback`) |
| `model_version` | `v1` / `v2` / fallback labels |
| `latency_seconds` | How long that request took |

**Tip:** Always send your own request id so you can search it:

```powershell
$rid = "qa-case-$(Get-Date -Format 'HHmmss')"
Invoke-WebRequest "http://localhost:8000/recommendations/9101" `
  -Headers @{ "X-Request-ID" = $rid } | Out-Null
Write-Host "Search logs for: $rid"
docker compose logs app --tail=200 | Select-String $rid
```

Response header should echo the same id:

```powershell
(Invoke-WebRequest "http://localhost:8000/health" -Headers @{ "X-Request-ID" = "qa-fixed-1" }).Headers["X-Request-ID"]
# → qa-fixed-1
```

---

## 15. Log event cheat sheet (what to expect)

### Application path (Task 21)

| `event` | When you see it | Level |
| --- | --- | --- |
| `cache_miss` | First recs call (or after cache delete) | info |
| `cache_hit` | Second call within TTL (~120s) | info |
| `redis_unavailable` | Redis stopped / broken | warning |
| `model_path_unavailable` | Model/features/candidates failed | warning |
| `postgres_store_hit` | Fell back to Task-14 `recommendations` table | info |
| `postgres_unavailable` | Postgres store also failed | warning |
| `popular_fallback` | Last resort hardcoded list | info |
| `recommendation_served` | **Always** at end of recs request (source + latency) | info |
| `interaction_published` | After `POST /interactions` | info |

### Model path (Task 22)

| `event` | When you see it | Level |
| --- | --- | --- |
| `prediction_logged` | Model actually ran (`predict`) | info |
| `recommendation_clicked` | Click matched a previously recommended item | info |

`prediction_logged` typically includes: `user_id`, `model_version`, `recommendation_count`, `click_count`, `purchase_count`, `last_item_id`, `recommendations`, `timestamp`.

**Rule of thumb**

- Cache hit → you should **not** see `prediction_logged` for that request.  
- Cache miss + healthy stack → `cache_miss` → `prediction_logged` → `recommendation_served` with `source=model`.

---

## 16. Case A — Happy path: miss → model → hit (application + model)

**Goal:** See both application and model logs for one user.

```powershell
$user = 9101
$rid1 = "qa-miss-$user"
$rid2 = "qa-hit-$user"

# Force model path
docker exec recommendation-redis redis-cli DEL "cache:recommendations:$user"

# 1) Cache MISS + MODEL
Invoke-WebRequest "http://localhost:8000/recommendations/$user" `
  -Headers @{ "X-Request-ID" = $rid1 } | Select-Object -ExpandProperty Content

# 2) Cache HIT (no model)
Invoke-WebRequest "http://localhost:8000/recommendations/$user" `
  -Headers @{ "X-Request-ID" = $rid2 } | Select-Object -ExpandProperty Content

docker compose logs app --tail=300 | Select-String "$rid1|$rid2|prediction_logged"
```

**Expect for `$rid1` (miss)**

```text
cache_miss
prediction_logged          ← MODEL ran
recommendation_served      source=model, model_version=v1
```

Example `prediction_logged` shape:

```json
{
  "event": "prediction_logged",
  "user_id": 9101,
  "model_version": "v1",
  "recommendation_count": 5,
  "click_count": 0,
  "purchase_count": 0,
  "recommendations": [10, 20, 30, 40, 50],
  "request_id": "qa-miss-9101",
  "level": "info"
}
```

**Expect for `$rid2` (hit)**

```text
cache_hit
recommendation_served      source=cache
```

No new `prediction_logged` on the hit request.

---

## 17. Case B — User with features: prove model saw real inputs

**Goal:** Show that prediction logs reflect Redis features (useful when “model ignores user”).

```powershell
$user = 9102

Invoke-RestMethod -Method POST -Uri http://localhost:8000/interactions -ContentType "application/json" `
  -Body "{`"user_id`":$user,`"item_id`":42,`"event_type`":`"click`"}"
Invoke-RestMethod -Method POST -Uri http://localhost:8000/interactions -ContentType "application/json" `
  -Body "{`"user_id`":$user,`"item_id`":10,`"event_type`":`"purchase`"}"

Start-Sleep -Seconds 2
Invoke-RestMethod "http://localhost:8000/features/$user"
# Expect click_count=1, purchase_count=1, last_item_id=10

docker exec recommendation-redis redis-cli DEL "cache:recommendations:$user"
$rid = "qa-features-$user"
Invoke-WebRequest "http://localhost:8000/recommendations/$user" -Headers @{ "X-Request-ID" = $rid } | Out-Null

docker compose logs app --tail=200 | Select-String $rid
```

**Expect in `prediction_logged`:** `click_count` / `purchase_count` / `last_item_id` match `/features/{user}`.

That is how QA proves: **feature store → model input → logged prediction**.

---

## 18. Case C — Real-world: “API was slow / something failed” (Redis down)

**Goal:** Simulate production Redis outage and read warnings + fallback.

```powershell
$user = 9103
$rid = "qa-redis-down-$user"

docker compose stop redis
Start-Sleep -Seconds 2

try {
  Invoke-WebRequest "http://localhost:8000/recommendations/$user" `
    -Headers @{ "X-Request-ID" = $rid } | Select-Object StatusCode, Content
} catch {
  $_.Exception.Message
}

docker compose logs app --tail=150 | Select-String $rid

# Recover
docker compose start redis
Start-Sleep -Seconds 3
Invoke-RestMethod http://localhost:8000/ready
```

**Expect log sequence (approx.)**

```text
redis_unavailable          operation=cache_get   (warning)
… fallback path …
recommendation_served      source=postgres-store  OR  popular-fallback
```

You usually will **not** see `prediction_logged` (model path needs Redis features).

**Also check metrics after recovery:**

```powershell
(Invoke-RestMethod http://localhost:8000/metrics) -split "`n" |
  Select-String "redis_failures_total|recommendation_requests_total"
```

`redis_failures_total{operation="cache_get"}` should have increased.

**QA story you can write in a bug/ticket:**  
“With Redis stopped, request `qa-redis-down-9103` logged `redis_unavailable` and served fallback `source=…` instead of hanging.”

---

## 19. Case D — Metrics dashboard lite (no Grafana needed)

```powershell
# After a few recommendation calls:
(Invoke-RestMethod http://localhost:8000/metrics) -split "`n" |
  Select-String "redis_hits_total|redis_misses_total|model_predictions_total|model_prediction_latency|recommendations_served|recommendations_clicked|recommendation_requests_total"
```

| Metric | What QA learns |
| --- | --- |
| `redis_hits_total` vs `redis_misses_total` | Cache effectiveness |
| `model_predictions_total{model_version="v1"}` | How often model actually ran |
| `model_prediction_latency_seconds` | Model speed (histogram buckets) |
| `recommendations_served_total` | Items shown (impressions) |
| `recommendations_clicked_total` | Attributed clicks on those items |
| `recommendation_requests_total{source=...}` | Mix of cache / model / fallbacks |

---

## 20. Case E — Model quality / CTR (Task 22) end-to-end

**Goal:** Serve recommendations → click a recommended item → see CTR move.

```powershell
$user = 9104
docker exec recommendation-redis redis-cli DEL "cache:recommendations:$user"

# Serve (creates impressions + last_recs in Redis)
$recs = Invoke-RestMethod "http://localhost:8000/recommendations/$user"
$recs
# Pick first recommended id, e.g. 10
$item = $recs.recommendations[0]

# Click that recommended item (attributed)
Invoke-RestMethod -Method POST -Uri http://localhost:8000/interactions `
  -ContentType "application/json" `
  -Body "{`"user_id`":$user,`"item_id`":$item,`"event_type`":`"click`"}"

# Click something NOT recommended (should NOT count as recommendation click)
Invoke-RestMethod -Method POST -Uri http://localhost:8000/interactions `
  -ContentType "application/json" `
  -Body "{`"user_id`":$user,`"item_id`":99999,`"event_type`":`"click`"}"

Invoke-RestMethod http://localhost:8000/monitoring/model-quality
docker compose logs app --tail=100 | Select-String "prediction_logged|recommendation_clicked"
```

**Expect**

- One `prediction_logged` on the GET (if cache was empty).
- One `recommendation_clicked` for `$item` (matched).
- No click attribution for `99999`.
- `/monitoring/model-quality` shows `recommendations_served` ≥ 5 (v1), `recommendations_clicked` ≥ 1, `ctr` = clicked/served.

Example quality response shape:

```json
{
  "versions": [
    {
      "model_version": "v1",
      "recommendations_served": 5,
      "recommendations_clicked": 1,
      "ctr": 0.2
    },
    {
      "model_version": "v2",
      "recommendations_served": 0,
      "recommendations_clicked": 0,
      "ctr": 0
    }
  ],
  "best_by_ctr": "v1"
}
```

**Why this matters:** In canary later (Task 23), QA compares **v1 vs v2 CTR** the same way.

---

## 21. Case F — Offline drift check (not in the API request)

Drift is **not** calculated during `GET /recommendations` (by design — keeps latency low).

QA / monitoring simulation in Python:

```powershell
docker compose exec app python -c "from app.drift import detect_drift, check_feature_drift; print('20% change', detect_drift(12, 10)); print('100% change', detect_drift(20, 10)); print(check_feature_drift('click_count', [40,80,100,60,90], 10.0))"
```

**Expect**

```text
20% change False
100% change True
feature=click_count drifted=True ...
```

**How to connect to logs:** Export `click_count` values from many `prediction_logged` lines over time. If the average jumps vs baseline (config default `DRIFT_CLICK_BASELINE=10`), that is **data drift** — raise it to engineering even if the API still returns 200.

---

## 22. Case G — Compare application vs model responsibility

| Symptom | Look for in logs | Likely layer |
| --- | --- | --- |
| Same answer twice, very fast | `cache_hit` only | Application cache |
| Fresh ranking after DEL cache | `cache_miss` + `prediction_logged` | Model ran |
| 200 but weird list + `popular-fallback` | `redis_unavailable` / `postgres_unavailable` | Infra / fallbacks |
| Features wrong in prediction log | Check `/features` + Kafka consumer | Feature pipeline |
| CTR stuck at 0 | No `recommendation_clicked` — clicks not on recommended ids | QA scenario / attribution |
| High `latency_seconds` on `recommendation_served` | Check spans if `OTEL_TRACES_EXPORTER=console` | Performance |

Enable console traces temporarily (optional):

```yaml
# docker-compose.yml → app environment
- OTEL_TRACES_EXPORTER=console
```

```powershell
docker compose up -d --force-recreate app
docker compose logs -f app
# Call recommendations — look for span names: redis_cache_lookup, model_predict, …
```

Set back to `none` when done (less noisy logs).

---

## 23. Mini script — regenerate observability demo (copy/paste)

```powershell
$user = 9110
$ridMiss = "demo-miss-$user"
$ridHit  = "demo-hit-$user"

Write-Host "=== Prepare features ==="
Invoke-RestMethod -Method POST -Uri http://localhost:8000/interactions -ContentType "application/json" -Body "{`"user_id`":$user,`"item_id`":20,`"event_type`":`"click`"}" | Out-Null
Start-Sleep -Seconds 2

Write-Host "=== MISS + MODEL (request_id=$ridMiss) ==="
docker exec recommendation-redis redis-cli DEL "cache:recommendations:$user" | Out-Null
Invoke-WebRequest "http://localhost:8000/recommendations/$user" -Headers @{ "X-Request-ID" = $ridMiss } | Out-Null

Write-Host "=== HIT (request_id=$ridHit) ==="
Invoke-WebRequest "http://localhost:8000/recommendations/$user" -Headers @{ "X-Request-ID" = $ridHit } | Out-Null

Write-Host "=== Click recommended item ==="
$recs = Invoke-RestMethod "http://localhost:8000/recommendations/$user"
Invoke-RestMethod -Method POST -Uri http://localhost:8000/interactions -ContentType "application/json" -Body "{`"user_id`":$user,`"item_id`":$($recs.recommendations[0]),`"event_type`":`"click`"}" | Out-Null

Write-Host "=== Logs ==="
docker compose logs app --tail=250 | Select-String "$ridMiss|$ridHit|prediction_logged|recommendation_clicked"

Write-Host "=== Quality ==="
Invoke-RestMethod http://localhost:8000/monitoring/model-quality
```

---

## 24. Observability QA checklist

- [ ] Can find one request by `X-Request-ID` across multiple log lines
- [ ] Cache miss shows `prediction_logged`; cache hit does not
- [ ] `recommendation_served` always appears with `source` + `latency_seconds`
- [ ] Redis stop → `redis_unavailable` warning + fallback source
- [ ] `/metrics` shows hits/misses/predictions moving after calls
- [ ] Click on recommended item → `recommendation_clicked` + CTR updates
- [ ] Click on random item → no recommendation click attribution
- [ ] Offline `detect_drift(20, 10)` is True; `detect_drift(12, 10)` is False
- [ ] Can explain: application logs vs model (`prediction_logged`) vs quality (`/monitoring/model-quality`)

---

**One-line summary (Task 21/22 QA):** Stamp every call with `X-Request-ID`, force miss/hit/Redis-down cases, then read JSON `event`s — application path for serving/fallbacks, `prediction_logged` for the model, metrics/CTR for whether the model is still “good.”
