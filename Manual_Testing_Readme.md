# Manual Testing Guide (QA)

Simple end-to-end checks for a QA intern: **simulate interactions → see Kafka → inspect Postgres/Redis → see how the model ranks**.

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
