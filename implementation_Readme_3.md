# Recommendation Service — Implementation Tutorial (Part 3)

This file continues from [`implementation_Readme_2.md`](implementation_Readme_2.md) (Tasks 9–16).

- Part 1 → Tasks 1–8 → [`implementation_Readme.md`](implementation_Readme.md)
- Part 2 → Tasks 9–16 → [`implementation_Readme_2.md`](implementation_Readme_2.md)
- **Part 3 → Task 17 onward** (Schema Registry, feature store, …)

---

## Overview (Part 3)

| Task | What we implemented |
| --- | --- |
| 17 | Apicurio Registry + Avro schema for `UserInteractionEvent` + compatible evolution (`device_type`) |
| 18 | Feature store: PostgreSQL durable events + Redis online features (via Kafka) |
| 19 | Redis features + Postgres candidates → versioned model ranking (v1/v2) |
| 20 | GitHub Actions CI: pytest + Docker image build on push/PR |

Key principle (Task 17):

> **Schemas are contracts between producers and consumers. Evolve them carefully so systems don't break.**

Key principle (Task 18):

> **PostgreSQL = durable event history. Redis = materialized online features for low-latency inference.**

Key principle (Task 19):

> **Redis provides online features, PostgreSQL provides candidates, the model ranks both — and model versions must be explicit.**

Key principle (Task 20):

> **CI answers “is this change safe to merge?” — run tests and build the image before anyone deploys.**

```text
Pydantic model  (API validation)
      ↓
Avro schema     (distributed contract)
      ↓
Schema Registry (version + compatibility)
      ↓
Kafka topic
      ↓
Consumer (decode with reader schema)
```

---

└── Event Pipeline
    ├── [ Python / API Layer ]
    │   ├── Pydantic Model
    │   └── (Validates application logic)
    │
    ├── [ Serializer Layer ]
    │   ├── Avro / Fastavro
    │   └── (Converts data to binary)
    │
    ├── [ Schema Registry ]
    │   ├── Apicurio / Confluent
    │   └── (Enforces schema rules)
    │
    └── [ Kafka Layer ]
        ├── Raw Binary
        └── (Stores 0s and 1s)



## Project layout (after Task 20)

```text
recommendation-service/
├── .github/
│   └── workflows/
│       └── ci.yml                   # Task 20 — pytest + Docker build
├── app/
│   ├── __init__.py
│   ├── main.py                      # Cache → Model → Postgres → popular
│   ├── schemas.py                   # RecommendationResponse.model_version
│   ├── config.py                    # + model_version (MODEL_VERSION)
│   ├── events.py
│   ├── features.py                  # UserFeatures + UserEventRecord
│   ├── feature_store.py             # Redis online features (materialized)
│   ├── event_store.py               # PostgreSQL user_events (durable history)
│   ├── model.py                     # Model interface; predict(features, candidates)
│   ├── model_registry.py            # get_model("v1"|"v2")
│   ├── recommendation_repository.py # PostgreSQL recommendation_items candidates
│   ├── recommendation_service.py    # features + candidates → model
│   ├── schema_registry.py
│   ├── kafka_producer.py
│   ├── kafka_consumer.py            # PG history → Redis features
│   ├── avro/
│   │   ├── user_interaction_v1.avsc
│   │   └── user_interaction.avsc
│   ├── redis_client.py
│   ├── database.py                  # recommendations + user_events + recommendation_items
│   ├── recommendation_store.py
│   ├── recommender.py               # Task 14 per-user store (fallback path)
│   └── seed.py                      # Seeds recommendations + recommendation_items
├── tests/
│   ├── test_config.py
│   ├── test_events.py
│   ├── test_event_store.py
│   ├── test_feature_store.py
│   ├── test_model.py
│   ├── test_recommendation_repository.py
│   └── test_recommendations.py
├── k8s/
│   ├── deployment.yaml
│   └── service.yaml
├── .gitignore                       # Task 20 — exclude .venv, caches, secrets, *.tar
├── Dockerfile
├── docker-compose.yml               # MODEL_VERSION=v1
├── requirements.txt
├── Readme.md
├── implementation_Readme.md
├── implementation_Readme_2.md
└── implementation_Readme_3.md
```

### Why `app/avro/` instead of `app/schemas/`?

The tutorial suggested `app/schemas/user_interaction.avsc`, but this project already has **`app/schemas.py`** for FastAPI/Pydantic models. A `schemas/` package would shadow that module. We store Avro contracts under **`app/avro/`** instead.

---

## Task 17 — Schema Registry + schema evolution

### Topic / goal

Stop sending ad-hoc JSON to Kafka. Define an **Avro schema** for `UserInteractionEvent`, register it in a **Schema Registry**, and evolve it by adding an optional `device_type` without breaking consumers.

### Problem without schemas

```text
Producer changes event shape
        ↓
Kafka
        ↓
Old consumer  →  💥
```

### Target architecture

```text
Docker Compose

Kafka
Apicurio Registry (:8081 → ccompat /apis/ccompat/v7)

FastAPI producer  →  Avro + schema id  →  Kafka
Kafka consumer    ←  fetch schema by id ←  Apicurio (ccompat API)
```

### Technical concepts

- **Apicurio Registry (mem)** — small image; in-memory store for local learning (schemas reset if container is recreated)
- **Confluent-compatible API (`ccompat`)** — same subject/register/id endpoints under `/apis/ccompat/v7`
- **Avro** — compact binary encoding with explicit field types and defaults
- **Subject** — `user-interactions-value` (Confluent `{topic}-value` convention)
- **Confluent wire format** — `magic(0) + schema_id(4 bytes) + avro_bytes` (works with Apicurio ids)
- **Pydantic stays for HTTP** — API input validation; Avro is the **Kafka contract**
- **Backward / forward / FULL compatibility** — we set **FULL** on the subject so optional-field evolution stays safe both ways
- **Schema evolution** — V2 adds `device_type: ["null","string"]` with `default: null`
- **Old JSON on the topic** — Task 15 messages are skipped by the consumer (not Avro)
### Files touched in Task 17

```text
recommendation-service/
├── app/
│   ├── avro/
│   │   ├── user_interaction_v1.avsc   # ADDED — Schema V1
│   │   └── user_interaction.avsc      # ADDED — Schema V2 (current)
│   ├── schema_registry.py             # ADDED — HTTP client + encode/decode
│   ├── events.py                      # CHANGED — optional device_type
│   ├── config.py                      # CHANGED — SCHEMA_REGISTRY_URL, subject
│   ├── kafka_producer.py              # CHANGED — Avro serialize + register
│   ├── kafka_consumer.py              # CHANGED — Avro deserialize
│   ├── main.py                        # CHANGED — /ready schema_registry
│   └── schemas.py                     # CHANGED — ReadyResponse.schema_registry
├── docker-compose.yml                 # CHANGED — schema-registry service + env
├── requirements.txt                   # CHANGED — fastavro
└── tests/test_events.py               # CHANGED — device_type + Avro tests
```

| File | Action |
| --- | --- |
| `app/avro/user_interaction_v1.avsc` | **Added** — V1 fields only |
| `app/avro/user_interaction.avsc` | **Added** — V2 + optional `device_type` |
| `app/schema_registry.py` | **Added** — Apicurio ccompat client + encode/decode |
| `app/events.py` | Optional `device_type: str \| None = None` |
| `app/config.py` | `schema_registry_url` (ccompat base), `kafka_value_subject` |
| `app/kafka_producer.py` | Register schema; publish Avro |
| `app/kafka_consumer.py` | Decode Avro with V2 reader schema |
| `app/main.py` / `schemas.py` | `/ready` includes `schema_registry` |
| `docker-compose.yml` | `schema-registry` + env for app/consumer |
| `requirements.txt` | `fastavro==1.12.2` |
| `tests/test_events.py` | Evolution / encode smoke tests |

### Schema V1

`app/avro/user_interaction_v1.avsc`:

```json
{
  "type": "record",
  "name": "UserInteractionEvent",
  "namespace": "recommendation.events",
  "fields": [
    { "name": "user_id", "type": "long" },
    { "name": "item_id", "type": "long" },
    { "name": "event_type", "type": "string" },
    { "name": "timestamp", "type": "string" }
  ]
}
```

### Schema V2 (current writer/reader)

`app/avro/user_interaction.avsc`:

```json
{
  "type": "record",
  "name": "UserInteractionEvent",
  "namespace": "recommendation.events",
  "fields": [
    { "name": "user_id", "type": "long" },
    { "name": "item_id", "type": "long" },
    { "name": "event_type", "type": "string" },
    { "name": "timestamp", "type": "string" },
    {
      "name": "device_type",
      "type": ["null", "string"],
      "default": null
    }
  ]
}
```

### Pydantic event (API + app model)

```python
class UserInteractionEvent(BaseModel):
    user_id: int
    item_id: int
    event_type: str
    timestamp: str = Field(default_factory=_utc_now)
    device_type: str | None = None  # Schema V2
```

### Producer path

```text
UserInteractionEvent
      ↓ event_to_avro_record()
Avro record dict
      ↓ register schema → schema_id
      ↓ encode_avro_message(schema_id, schema, record)
Kafka value bytes (Confluent wire format)
```

Key code in `app/kafka_producer.py`:

```python
_, writer_schema, schema_id = _ensure_schema_registered()
payload = encode_avro_message(
    schema_id,
    writer_schema,
    event_to_avro_record(event),
)
await producer.send_and_wait(topic, value=payload, key=str(event.user_id).encode())
```

### Consumer path

```text
Kafka message.value
      ↓ magic + schema_id + payload
Schema Registry GET /schemas/ids/{id}
      ↓
fastavro schemaless_reader(writer_schema, reader_schema=V2)
      ↓
UserInteractionEvent.model_validate(record)
```

Old Task 15 JSON messages lack the Avro magic byte → logged and **skipped**.

### Compose: Apicurio Registry

We use **Apicurio** instead of Confluent Schema Registry (much smaller image).  
Avro still uses the Confluent wire format via Apicurio's **ccompat** API.

```yaml
schema-registry:
  image: quay.io/apicurio/apicurio-registry-mem:2.6.5.Final
  ports:
    - "8081:8080"
  environment:
    REGISTRY_CCOMPAT_LEGACY_ID_MODE_ENABLED: "true"
```

App / consumer env:

```text
SCHEMA_REGISTRY_URL=http://schema-registry:8080/apis/ccompat/v7
KAFKA_VALUE_SUBJECT=user-interactions-value
```

From the host (local Python), use:

```text
SCHEMA_REGISTRY_URL=http://localhost:8081/apis/ccompat/v7
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
```

### How to run / verify

```powershell
docker compose up -d --build
docker compose ps
Invoke-RestMethod http://localhost:8081/apis/ccompat/v7/subjects
Invoke-RestMethod http://localhost:8000/ready
```
Expect `/ready` roughly:

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

Publish **without** `device_type` (still valid under V2):

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/interactions `
  -ContentType "application/json" `
  -Body '{"user_id":123,"item_id":42,"event_type":"view"}'
```

Publish **with** V2 field:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/interactions `
  -ContentType "application/json" `
  -Body '{"user_id":123,"item_id":42,"event_type":"view","device_type":"mobile"}'
```

Watch consumer:

```powershell
docker compose logs -f kafka-consumer
```

Expect:

```text
Received Avro event: ... device_type=None ...
Received Avro event: ... device_type=mobile ...
```

List registered subjects / schemas:

```powershell
Invoke-RestMethod http://localhost:8081/apis/ccompat/v7/subjects
Invoke-RestMethod http://localhost:8081/apis/ccompat/v7/subjects/user-interactions-value/versions
```

### Compatibility / evolution check

1. V1 schema file kept at `user_interaction_v1.avsc` for reference.
2. V2 adds optional `device_type` with default `null` → old data still readable; new field is optional for producers.
3. Subject compatibility set to **FULL** after first register.
4. Consumer always uses **V2 as reader schema**, so messages written under older writer schemas still decode (`device_type` → `null`).

### Done checklist

- [x] Apicurio Registry runs in Compose (`:8081`, ccompat `/apis/ccompat/v7`)
- [x] Avro schema for `UserInteractionEvent` (V1 + V2 files)
- [x] Producer serializes with schema / registry id
- [x] Consumer deserializes via Apicurio ccompat API
- [x] Schema V2 adds optional `device_type`
- [x] Events without `device_type` still work
- [x] `/ready` reports `schema_registry`
- [x] Documented in `implementation_Readme_3.md`

**Task 17 in one sentence:** Kafka events are Avro contracts registered in Apicurio Registry; we evolved them with an optional `device_type` without breaking readers.

---

====================================================================

## Task 18 — Feature store (PostgreSQL history + Redis online)

### Topic / goal

Upgrade the tiny Redis-only feature store into a **production-style split**:

> **PostgreSQL = durable system of record / historical events**  
> **Redis = fast online feature serving / derived state**

We still do **not** install Feast. We own both stores ourselves.

### Architecture

```text
POST /interactions
      ↓
Kafka (Avro)
      ↓
Kafka Consumer (feature pipeline)
      │
      ├──────────────► PostgreSQL user_events
      │                 (durable history / audit / retrain)
      │
      └──────────────► Feature materialization
                         ↓
                       Redis features:user:{id}
                         (online inference)
                         ↓
               GET /features/{user_id}
               GET /recommendations/{user_id} → Model
```

Same Kafka topic can conceptually feed **multiple consumer groups**:

```text
                Kafka
                  │
      ┌───────────┼────────────┐
      ▼           ▼            ▼
 PostgreSQL   Feature Job   Analytics
  (history)       │
                  ▼
                Redis
```

In this learning project **one consumer** does both steps in order (history first, then online features). Production would often split those into separate groups.

### Offline vs online feature store

```text
                FEATURE STORE
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
   Offline Store          Online Store
   PostgreSQL             Redis
   user_events            features:user:*
   historical data        low latency
          │                     │
          ▼                     ▼
       Training             Inference (Task 19 Model)
```

Important correction: Redis does **not** store “important events”.  
It stores **features frequently needed for online prediction**, materialized from events.

```text
purchase event
      ↓
PostgreSQL user_events
      ↓
Feature processor
      ↓
purchase_count += 1
      ↓
Redis
```

### Files touched (Task 18 + upgrade)

```text
recommendation-service/
├── app/
│   ├── features.py          # UserFeatures + UserEventRecord
│   ├── feature_store.py     # Redis online materialization
│   ├── event_store.py       # ADDED — save/list/count user_events
│   ├── database.py          # CHANGED — CREATE TABLE user_events
│   ├── kafka_consumer.py    # CHANGED — PG then Redis
│   └── main.py              # GET /features + GET /events/{user_id}
├── docker-compose.yml       # kafka-consumer gets Postgres + Redis env
└── tests/
    ├── test_feature_store.py
    └── test_event_store.py  # ADDED
```

| File | Action |
| --- | --- |
| `app/event_store.py` | **Added** — durable `user_events` helpers |
| `app/database.py` | Create `user_events` + index |
| `app/feature_store.py` | Clarified: Redis is derived online view |
| `app/kafka_consumer.py` | `save_user_event` → then `apply_interaction_event` |
| `app/main.py` | `GET /events/{user_id}` for history inspection |
| `docker-compose.yml` | Consumer `POSTGRES_*` + `depends_on: postgres` |

### PostgreSQL schema

```sql
CREATE TABLE user_events (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    item_id BIGINT NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Redis online features

```text
features:user:123
```

```json
{
  "user_id": 123,
  "click_count": 2,
  "purchase_count": 1,
  "last_item_id": 99
}
```

Recommendation serving still reads **Redis**, not `COUNT(*)` from Postgres, on every request.

### Consumer pipeline

| Step | Store | Purpose |
| --- | --- | --- |
| 1 | PostgreSQL `user_events` | Durable history (source of truth) |
| 2 | Redis `features:user:*` | Materialized online features |

Feature rules (unchanged):

| `event_type` | Redis feature change |
| --- | --- |
| `click` | `click_count += 1`, `last_item_id = item_id` |
| `purchase` | `purchase_count += 1`, `last_item_id = item_id` |
| other (e.g. `view`) | `last_item_id = item_id` only |

### How to run / verify

```powershell
docker compose up -d --build --force-recreate app kafka-consumer
```

```powershell
# Use a fresh user for a clean demo
Invoke-RestMethod -Method Post -Uri http://localhost:8000/interactions `
  -ContentType "application/json" `
  -Body '{"user_id":321,"item_id":42,"event_type":"click"}'

Invoke-RestMethod -Method Post -Uri http://localhost:8000/interactions `
  -ContentType "application/json" `
  -Body '{"user_id":321,"item_id":50,"event_type":"click"}'

Invoke-RestMethod -Method Post -Uri http://localhost:8000/interactions `
  -ContentType "application/json" `
  -Body '{"user_id":321,"item_id":99,"event_type":"purchase"}'

Start-Sleep -Seconds 2
Invoke-RestMethod http://localhost:8000/features/321
Invoke-RestMethod http://localhost:8000/events/321
```

Expect Redis features:

```json
{"user_id":321,"click_count":2,"purchase_count":1,"last_item_id":99}
```

Expect Postgres history (via API) to list the three raw events.

Direct checks:

```powershell
docker exec recommendation-redis redis-cli GET features:user:321
docker exec recommendation-postgres psql -U recommendation_user -d recommendations `
  -c "SELECT * FROM user_events WHERE user_id = 321 ORDER BY id;"
```

### Done checklist

- [x] `UserFeatures` model
- [x] Redis online feature store (`get` / `update` / apply)
- [x] PostgreSQL `user_events` durable history
- [x] Kafka consumer writes PG then Redis
- [x] Click / purchase / `last_item_id` behavior
- [x] `GET /features/{user_id}` (online)
- [x] `GET /events/{user_id}` (history)
- [x] Documented offline vs online split in this file

**Task 18 in one sentence:** Kafka events are persisted in PostgreSQL as durable history and materialized into Redis as online features for low-latency model inference.

---

## Task 19 — Real recommendation data + model versioning

### Topic / goal

Upgrade Task 19 from hardcoded recommendation lists into a proper **data + feature + model** pipeline:

```text
GET /recommendations/{user_id}
        │
        ▼
   Redis online features
        │
        ▼
 PostgreSQL recommendation_items (candidates)
        │
        ▼
   Model v1 / v2  (rank features + candidates)
        │
        ▼
 Recommendations + model_version
```

Important distinction:

| Table | Meaning |
| --- | --- |
| `recommendations` (Task 14) | Persisted **per-user results** (fallback store) |
| `recommendation_items` (Task 19) | **Candidate catalog** the model ranks |

### Architecture

```text
                 User Request
                      │
                      ▼
              Recommendation API
                      │
           ┌──────────┴──────────┐
           ▼                     ▼
     Redis Features        PostgreSQL
     features:user:*     recommendation_items
           │                     │
           └──────────┬──────────┘
                      ▼
                 Model v1 / v2
                      │
                      ▼
              Recommendations
```

The model does **not** run SQL. The service layer fetches features + candidates and calls:

```python
model.predict(features, candidates)
```

### Technical concepts

- **Candidate generation** — Postgres provides ranked item catalog
- **Ranking** — model reorders/selects from candidates using features
- **v1** — popularity-based (candidate `score` order)
- **v2** — popularity + user features (`click_count`, `purchase_count`, `last_item_id` boost)
- **Model registry** — `get_model("v1"|"v2")`
- **Fallbacks unchanged** — Task 14 `recommendations` table, then popular list

### Files touched (Task 19 revised)

```text
recommendation-service/
├── app/
│   ├── recommendation_repository.py  # ADDED — candidates from PG
│   ├── model.py                      # CHANGED — predict(features, candidates)
│   ├── model_registry.py             # v1 / v2 registry
│   ├── recommendation_service.py     # CHANGED — features + candidates → model
│   ├── database.py                   # CHANGED — recommendation_items table
│   ├── seed.py                       # CHANGED — seed candidate catalog
│   ├── schemas.py                    # model_version on response
│   ├── config.py                     # MODEL_VERSION
│   └── main.py                       # Cache → model path → fallbacks
└── tests/
    ├── test_model.py
    ├── test_recommendation_repository.py
    └── test_recommendations.py
```

### PostgreSQL candidates

```sql
CREATE TABLE recommendation_items (
    id BIGSERIAL PRIMARY KEY,
    item_id BIGINT NOT NULL UNIQUE,
    score DOUBLE PRECISION NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);
```

Seeded scores (via `seed.py`): `10→0.95 … 94→0.57`.

### Model rules

**v1 — popularity**

```text
return top 5 candidates by PostgreSQL score
→ [10, 20, 30, 40, 50]
```

**v2 — popularity + features**

```text
final_score =
    candidate_score
    + click_count × 0.01
    + purchase_count × 0.05
    + 0.5 if item_id == last_item_id
```

Then return top 5 by `final_score`.

### Serving order in `main.py`

```text
1. Redis cache HIT
2. Redis features + Postgres candidates → Model (MODEL_VERSION)
3. PostgreSQL `recommendations` table → model_version="postgres-store"
4. Popular fallback → model_version="popular-fallback"
```

Example response:

```json
{
  "user_id": 123,
  "recommendations": [10, 20, 30, 40, 50],
  "model_version": "v1"
}
```

### How to verify

```powershell
.\.venv\Scripts\python -m pytest tests -q
docker compose up -d --build --force-recreate app
docker compose exec app python -m app.seed
```

```powershell
# Clear cache, then request
docker exec recommendation-redis redis-cli DEL cache:recommendations:999
Invoke-RestMethod http://localhost:8000/recommendations/999
# → [10,20,30,40,50], model_version v1

# With features (last_item boost matters for v2)
Invoke-RestMethod http://localhost:8000/features/321
# Set MODEL_VERSION=v2 and recreate app to compare ranking
```

Inspect candidates:

```powershell
docker exec recommendation-postgres psql -U recommendation_user -d recommendations `
  -c "SELECT item_id, score FROM recommendation_items WHERE is_active ORDER BY score DESC;"
```

### Done checklist

- [x] `recommendation_items` table (separate from Task 14 `recommendations`)
- [x] `seed.py` seeds candidate catalog
- [x] `recommendation_repository.py` (no SQL inside the model)
- [x] Model accepts `features + candidates`
- [x] v1 popularity ranking
- [x] v2 feature-aware ranking
- [x] Model registry + `model_version` in response
- [x] Cache / Task-14 store / popular fallbacks still work
- [x] Documented in this file

**Task 19 in one sentence:** The API loads Redis features and Postgres candidates, then a versioned model ranks them — without hardcoding recommendation IDs.

---

## Task 20 — CI/CD (Continuous Integration)

### Topic / goal

Automate quality checks on every push / pull request so we do **not** rely on manual local testing alone.

This task is **CI only** (tests + Docker build). We are **not** deploying to production yet — that is CD, covered later.

```text
Developer
   │
   ▼
git push
   │
   ▼
GitHub
   │
   ▼
GitHub Actions
   │
   ├── Install Python 3.12
   ├── Install dependencies
   ├── Run pytest
   └── Build Docker image
          │
          ▼
       PASS / FAIL
```

Why this matters now: the stack includes FastAPI, Pydantic, Redis, PostgreSQL, Kafka, feature store, model versions, and Docker. Manual verification after every change does not scale.

### CI vs CD (interview concepts)

| | CI — Continuous Integration | CD — Continuous Delivery/Deployment |
| --- | --- | --- |
| Question | “Is this change safe to merge?” | “Can this validated version be released?” |
| Typical steps | Code → tests → build → quality checks | Code → tests → build image → push image → deploy → health checks |

We start with **CI**. Deployment comes later so the first Actions file stays readable.

### Architecture (CI pipeline)

```text
Python code
    ↓
pytest
    ↓
PASS
    ↓
Docker build
    ↓
PASS
```

### Files touched (Task 20)

```text
recommendation-service/
├── .github/
│   └── workflows/
│       └── ci.yml       # ADDED — GitHub Actions workflow
├── .gitignore           # ADDED — keep secrets/venv/artifacts out of git
└── implementation_Readme_3.md
```

| File | Action |
| --- | --- |
| `.github/workflows/ci.yml` | **Added** — checkout, Python 3.12, `pip install`, `pytest`, `docker build` |
| `.gitignore` | **Added** — `.venv/`, caches, `.env`, `*.tar`, IDE junk |

### Workflow details (`.github/workflows/ci.yml`)

**Triggers**

| Event | Branches |
| --- | --- |
| `push` | `main`, `master`, `develop` |
| `pull_request` | `main`, `master` |

(`master` is included because the GitHub remote default branch may be `master` on first push.)

**Job `test` (ubuntu-latest)**

| Step | What it does |
| --- | --- |
| Checkout code | `actions/checkout@v4` |
| Setup Python | `actions/setup-python@v5` → **3.12** (matches `Dockerfile`) |
| Install dependencies | `pip install -r requirements.txt` |
| Run tests | `pytest` (unit tests; no Redis/Postgres/Kafka required) |
| Build Docker image | `docker build -t recommendation-service:test .` |

GitHub-hosted runners already provide Docker, so the image build step needs no extra setup.

### Local verification (before first push)

```powershell
.\.venv\Scripts\python -m pytest -q
# → 29 passed

docker build -t recommendation-service:test .
# → image builds successfully
```

### Deliberate break / fix (how to prove CI works)

Do this once after the workflow is live on GitHub:

1. Temporarily change an assertion (e.g. `assert result == [999]` when the real result differs).
2. Push → Actions → **Run tests ❌ FAILED**.
3. Revert the assertion and push again → **Run tests ✓**.

That is the point of CI: broken code fails in the cloud before merge, not only on your laptop.

### How to view results on GitHub

After the first push:

**GitHub → [Muhammad-Akhtar/recommendation-service](https://github.com/Muhammad-Akhtar/recommendation-service) → Actions**

Expect:

```text
CI
 └── test
      ├── Checkout code        ✓
      ├── Setup Python         ✓
      ├── Install dependencies ✓
      ├── Run tests            ✓
      └── Build Docker image   ✓
```

### Done checklist

- [x] `.github/workflows/ci.yml` created
- [x] Push triggers CI (`main` / `master` / `develop`)
- [x] Pull request triggers CI (`main` / `master`)
- [x] Python 3.12 installed in the workflow
- [x] Dependencies install from `requirements.txt`
- [x] All pytest tests pass locally (29) — CI runs the same command
- [x] Docker image builds successfully (verified locally + CI step)
- [ ] Deliberately broken test causes CI failure *(do once in Actions after push)*
- [ ] Fixed test causes CI to pass again *(same)*
- [x] Documented in this file

### Concepts you should be able to explain

> **What is CI?** Automated checks (tests/build) on every change so broken code is caught before merge.

> **Why should tests run before building/deploying?** Fail fast — don’t package or ship code that already fails unit tests.

> **What is the difference between CI and CD?** CI validates merge safety; CD releases a validated artifact to an environment.

> **Why build the Docker image in CI?** Confirms the Dockerfile and app still package cleanly (deps, copy paths, base image), not only that Python tests pass.

> **What happens when a developer pushes broken code?** The Actions job fails; the PR/push shows a red X so the team knows not to merge until it’s fixed.

**Task 20 in one sentence:** Every push/PR runs pytest and a Docker build on GitHub Actions so we know the recommendation service is still merge-safe — without deploying yet.


└── Event Pipeline Flow
    ├── 1. [ Python / API Layer ]
    │   └── Pydantic Model
    │       ├── Validation: Checks request format, types, and logic (HTTP level)
    │       ├── Error Handling: Rejects bad client requests with HTTP 422
    │       └── Output: Returns clean, validated Python dict / JSON object
    │
    ├── 2. [ Serializer Layer ]
    │   └── Avro / Fastavro
    │       ├── Mapping: Filters dict keys against loaded .avsc schema
    │       ├── Conversion: Compresses clean data into compact binary bytes
    │       └── Side Effect: Silently drops fields not declared in the .avsc file
    │
    ├── 3. [ Schema Registry ]
    │   └── Apicurio / Confluent
    │       ├── Enforcement: Central source of truth for message contracts
    │       ├── Governance: Verifies schema compatibility rules (v1, v2, etc.)
    │       └── Identification: Prepends a unique 4-byte Schema ID to the binary payload
    │
    └── 4. [ Kafka Layer ]
        └── Raw Binary Storage
            ├── Immutability: Stores untyped binary streams (0s and 1s) on disk
            ├── Partitioning: Distributes data across partitions for parallel processing
            └── Delivery: Streams exact bytes out to downstream Consumers