# Recommendation Service — System Architecture (Task 25)

This document is the **final production architecture view** of the learning project (Tasks 1–24).

It answers:

- What we actually built
- How sync vs async paths work
- What is durable vs cached vs evented
- What is **implemented** vs **conceptual** (interview / next-step production)

Related tutorials:

- Parts 1–4 → `implementation_Readme.md` … `implementation_Readme_4.md`
- Manual QA → `Manual_Testing_Readme.md`

---

## 0. Accuracy check (Tasks 1–25 vs code)

| Area | Status | Notes |
| --- | --- | --- |
| FastAPI + Pydantic + pytest | Implemented | Core API |
| Docker + Compose | Implemented | Full local data plane |
| Redis cache + online features | Implemented | Separate key spaces |
| Graceful degradation | Implemented | Cache → model → PG store → popular |
| Retry / circuit breaker / DLQ | Implemented | `app/resilience.py`; Kafka DLQ topic |
| Health / readiness | Implemented | `/health`, `/ready` |
| Config / env Settings | Implemented | `app/config.py` |
| Stateless app | Implemented | No in-process user SoT |
| Kubernetes Deploy/Service/probes | Implemented | `k8s/` |
| Manual scale + HPA | Implemented | Task 13 + `k8s/hpa.yaml` |
| PostgreSQL | Implemented | candidates, store, `user_events` |
| Kafka + partitions/groups | Implemented | 3 partitions; one consumer group |
| Schema Registry (Avro) | Implemented | Apicurio ccompat |
| Feature store split | Implemented | PG history + Redis online |
| Model v1/v2 serving | Implemented | Service fetches; model ranks only |
| CI (pytest + image build) | Implemented | GitHub Actions; CD conceptual |
| Observability | Implemented | logs, `/metrics`, OTEL (console/none) |
| Model monitoring / CTR / drift | Implemented | logs+metrics+helpers; drift offline |
| Canary / blue-green / rollback | Implemented | v1/v2 Deployments; weighted mesh later |
| Load testing | Implemented | `scripts/load_test.py` |
| Ingress / Prometheus / Grafana / Jaeger | Conceptual | App exposes hooks; backends not deployed |
| Multiple Kafka consumer groups A–D | Conceptual | One group does PG+Redis today |

**Verdict:** The Task 25 diagrams are correct as a **target production story**. This file marks clearly what runs in *this* repo today.

---

## 1. Big-picture architecture

### 1.1 What this project runs locally (Compose)

```text
                         ┌──────────────────────┐
                         │      Clients         │
                         │ curl / Web / tests   │
                         └──────────┬───────────┘
                                    │ :8000
                                    ▼
                         ┌──────────────────────┐
                         │ FastAPI app          │
                         │ (recommendation API) │
                         └──────────┬───────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         ▼                          ▼                          ▼
      Redis                     PostgreSQL                   Kafka
  cache + features           candidates / store /         user-interactions
                              user_events                     │
                                                              ▼
                                                      kafka-consumer
                                                      (same group)
                                                         │
                                              ┌──────────┴──────────┐
                                              ▼                     ▼
                                         user_events            features:user:*
                                         (Postgres)               (Redis)

  Also: Apicurio Schema Registry (Avro contracts)
```

### 1.2 Production-shaped view (K8s + data plane)

```text
                         ┌──────────────────────┐
                         │      Clients         │
                         │ Web / Mobile / APIs  │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ Load Balancer /      │
                         │ Ingress (*)          │
                         └──────────┬───────────┘
                                    │
                                    ▼
                 ┌─────────────────────────────────────┐
                 │       Kubernetes Cluster             │
                 │                                     │
                 │   Recommendation Service (stateless) │
                 │  ┌────────┐ ┌────────┐ ┌────────┐  │
                 │  │FastAPI │ │FastAPI │ │FastAPI │  │
                 │  │ Pod 1  │ │ Pod 2  │ │ Pod 3  │  │
                 │  └───┬────┘ └───┬────┘ └───┬────┘  │
                 │      └──────────┼──────────┘        │
                 │              Service                 │
                 │                 │                   │
                 │              HPA (v1)               │
                 └─────────────────┼───────────────────┘
                                   │
              ┌────────────────────┼─────────────────────┐
              ▼                    ▼                     ▼
           Redis              PostgreSQL              Kafka
              │                    │                     │
              │                    │              Consumer(s)
              │                    │                     │
              │                    ▼                     ▼
              │            candidates / history    features + events
              ▼
       Online Features /
       Recommendation Cache

                         ┌───────────────────────┐
                         │ ML Model (in-process) │
                         │ v1 / v2               │
                         └───────────┬───────────┘
                                     │
                                     ▼
                              Ranked Results

(*) Ingress / mesh weighted canary = next step; local K8s uses Service + port-forward.
```

---

## 2. Synchronous request flow

### 2.1 Happy path

```text
GET /recommendations/{user_id}
        ↓
Kubernetes Service  (or Compose `app`)
        ↓
FastAPI Pod
        ↓
Redis GET  cache:recommendations:{user_id}
   ├── HIT  → return cached RecommendationResponse
   │
   └── MISS
        ↓
     Redis GET  features:user:{user_id}   (defaults if missing)
        ↓
     PostgreSQL  recommendation_items     (candidates)
        ↓
     Model v1 / v2  .predict(features, candidates)
        ↓
     Structured prediction log + CTR “served” counters
        ↓
     Redis SET  cache:recommendations:{user_id}  (TTL)
     Redis SET  last_recs:{user_id}              (impression, Task 22)
        ↓
     HTTP 200 Response  { recommendations, model_version }
```

**Separation of responsibilities (critical):**

```text
RecommendationService
  ├── loads features (Redis)
  ├── loads candidates (PostgreSQL)
  └── calls Model.predict(...)     ← model never opens Redis/PG/Kafka
```

### 2.2 Degradation path (fault tolerance)

```text
Redis unavailable (cache GET fails)
        ↓
skip model path (needs Redis features)
        ↓
PostgreSQL table `recommendations` (per-user store)
        ↓
  hit  → optional cache write if Redis recovered
  miss / PG error
        ↓
Popular / trending list  (in-code fallback)
        ↓
Response still 200   (best effort quality)
```

Also:

```text
Model / candidates failure
        ↓
same PG store → popular chain
```

**Principle:** dependency failure **degrades recommendation quality**, it does **not** take down the API.

| Failure | Behavior |
| --- | --- |
| Redis down | PG store → popular |
| Model / empty candidates | PG store → popular |
| PostgreSQL store down | popular |
| Pod dies | K8s starts another; Service routes elsewhere |
| Traffic spike | HPA scales `recommendation-service-v1` |
| Bad release | delete canary v2 / roll back image |

---

## 3. Asynchronous event flow

### 3.1 Implemented today

```text
User / client
 ↓
POST /interactions   { user_id, item_id, event_type, … }
 ↓
FastAPI validates (Pydantic)
 ↓
Avro encode + Schema Registry id
 ↓
Kafka topic: user-interactions   (key = user_id, 3 partitions)
 ↓
Consumer group: recommendation-service
 ↓
 ┌────────────────────────────┐
 │ 1) PostgreSQL user_events  │  durable history (SoR)
 │ 2) Redis features:user:*   │  online features
 └────────────────────────────┘
```

Click attribution for CTR (Task 22) also happens on `POST /interactions` when `event_type=click` and `item_id` was in `last_recs:{user}` — that is **API-side feedback**, not a separate Kafka monitoring consumer.

### 3.2 Conceptual fan-out (production / interview)

Same topic, **independent consumer groups**:

```text
                Kafka  user-interactions
                           │
      ┌───────────┬────────┼────────┬──────────┐
      ▼           ▼        ▼        ▼          ▼
 Group A      Group B   Group C  Group D   …
 → Postgres   → Feature → Analytics → Model
   history      store                monitoring
```

**In this repo:** Groups A+B are **one** consumer that writes PG then Redis in order. C/D are not separate services yet. Scaling `kafka-consumer` replicas = more members of the **same** group (partition parallelism), not independent fan-out.

---

## 4. Data responsibilities

### PostgreSQL — durable / system of record

| Table / data | Role |
| --- | --- |
| `recommendation_items` | Candidate catalog the model ranks |
| `recommendations` | Per-user fallback store (Task 14) |
| `user_events` | Durable interaction history |

Not stored in PG today: full prediction history table (predictions go to **logs + metrics**).

### Redis — low-latency online data

| Key | Role |
| --- | --- |
| `cache:recommendations:{user_id}` | Response cache |
| `features:user:{user_id}` | Online features for inference |
| `last_recs:{user_id}` | Last served list for CTR attribution |

### Kafka — event backbone

- Topic `user-interactions`
- Decouples producers from consumers
- Avro + Schema Registry contract
- Partitions for parallelism; consumer group for coordinated consumption

### ML model — ranking only

```text
Service → features + candidates → model.predict → item ids
```

Model does **not** query Redis, PostgreSQL, or Kafka.

---

## 5. Scaling architecture

```text
                    Traffic
                       ↓
              Service / port-forward
                       ↓
          ┌────────────┼────────────┐
          ▼            ▼            ▼
        Pod 1        Pod 2        Pod 3   (v1)
          │            │            │
          └────────────┼────────────┘
                       │
                      HPA
               min=3 max=10 CPU~50%
                       │
              load ↑ → more pods
              load ↓ → scale down
```

Why this works:

- FastAPI is **stateless** — any pod can serve any user
- Shared state lives in Redis / PostgreSQL / Kafka
- Task 13 = manual `kubectl scale`
- Task 24 = prove need with load test, then **HPA** decides

**Canary note:** Before HPA demos, remove `recommendation-service-v2` so traffic and CPU metrics are not split across versions.

---

## 6. Deployment architecture

```text
Git push
 ↓
CI (GitHub Actions)
 ├── pytest
 └── docker build
 ↓
Image tags   recommendation-service:v1 / :v2 / :sha
 ↓
Kubernetes
 ├── Deployment v1 (stable)
 └── Deployment v2 (canary, optional)
 ↓
Service (selector: app=recommendation-service)
 ↓
Independent validate (port-forward v2 /health)
 ↓
Healthy → keep / promote
Unhealthy → delete v2 (rollback)
```

Do **not** invent `deployment-v3.yaml`, `deployment-v4.yaml` forever. Teaching used dual Deployments; production usually updates **image tags** on the stable Deployment (or temporary canary) via automation.

CD (push to registry + auto-deploy) is the natural next step after Task 20 CI.

---

## 7. Observability architecture

```text
FastAPI
   │
   ├── Structured JSON logs ──→ stdout (Compose/K8s logs)
   │     + X-Request-ID correlation
   │
   ├── Prometheus metrics ────→ GET /metrics  (scrape target)
   │
   ├── OTEL spans ────────────→ console / none (backend optional)
   │
   └── Model quality ─────────→ GET /monitoring/model-quality
```

Answer “why was this request slow?” with spans / logs:

```text
Request
 ↓
redis_cache_lookup     ~few ms
 ↓
redis_get_features
 ↓
postgres_get_candidates
 ↓
model_predict
 ↓
redis_cache_write
 ↓
recommendation_served  (latency_seconds in log)
```

Prometheus / Grafana / Jaeger **backends** are not in Compose yet; the **instrumentation** is in the app.

---

## 8. Model monitoring architecture

```text
Model predict
    ↓
model_version (v1 / v2)
    ↓
prediction_logged  (structured log)
    ↓
metrics: predictions, latency, recommendation_count
    ↓
impressions (recommendations_served) + last_recs
    ↓
click on recommended item → recommendations_clicked
    ↓
CTR = clicked / served   (/monitoring/model-quality)
    ↓
drift helpers (app/drift.py) — offline / batch, NOT in request path
```

Example decision data:

```text
v1 → CTR 4.1%
v2 → CTR 5.3%   ← prefer for canary promotion
```

---

## 9. Two flows to memorize (interview)

### Synchronous

```text
Request → Service → FastAPI → Redis/PG/Model → Response
```

### Asynchronous

```text
Interaction → Kafka → Consumer → PostgreSQL + Redis features
```

Keep them mentally separate: **serving path** must stay fast; **event path** updates features for *future* requests.

---

## 10. Interview answers (Task 25 exercise)

### 1. Why is FastAPI stateless?

So any replica can handle any request. User-specific or shared state lives in Redis/PostgreSQL/Kafka. That enables horizontal scale, rolling deploys, and pod restarts without losing “the” store in process memory.

### 2. Why Redis if PostgreSQL exists?

Postgres is durable and flexible but higher latency. Redis holds **hot** data: response cache and online features for sub-millisecond reads on the serve path. Postgres remains the durable history and candidate catalog.

### 3. Why Kafka?

To decouple “user did something” from “many systems react.” Producers don’t call feature jobs, analytics, or warehouses directly. New consumers can join the topic without changing the API. It also absorbs spikes and enables replay.

### 4. What happens if Redis goes down?

The API still responds. After a few failures the **Redis circuit breaker opens**, so later requests skip Redis immediately (no long timeouts), try PostgreSQL per-user store, then popular fallback. Quality drops; availability stays.

### 5. How do we safely deploy model/service v2 and roll back?

Ship a distinguishable version (`SERVICE_VERSION` / image tag). Run it beside v1 (canary Deployment). Validate independently (port-forward `/health`). Let shared Service see both only when ready. Watch metrics/CTR/errors. If unhealthy, remove v2 so v1 takes all traffic again. (Weighted 10%/90% is the mesh/Ingress next step.)

---

## 11. Task map (complete)

| Task | Concept | Status |
| --- | --- | --- |
| 1 | FastAPI API | Done |
| 2 | Structure / Pydantic / pytest | Done |
| 3 | Docker | Done |
| 4 | Redis caching | Done |
| 5–6 | Graceful degradation + Compose | Done |
| 7 | Recommendation fallback | Done |
| 8 | Health / readiness | Done |
| 9 | Configuration | Done |
| 10 | Stateless architecture | Done |
| 11–13 | Kubernetes + probes + scale | Done |
| 14 | PostgreSQL | Done |
| 15–16 | Kafka + partitions/groups | Done |
| 17 | Schema Registry | Done |
| 18 | Feature store | Done |
| 19 | Model serving / versioning | Done |
| 20 | CI | Done |
| 21 | Observability | Done |
| 22 | Model monitoring / drift | Done |
| 23 | Canary / blue-green / rollback | Done |
| 24 | Load testing / HPA | Done |
| **25** | **Final architecture (this file)** | **Done** |

---

## 12. One-sentence summary

**A stateless FastAPI fleet serves recommendations through Redis cache → online features + Postgres candidates → versioned models, with Kafka-driven feature materialization, layered fallbacks (plus Redis circuit breaker, short retries, and consumer DLQ), CI, observability, canary releases, and HPA — so failures degrade quality instead of taking the API offline.**

---

## 13. Resilience add-on (post–Task 25 hardening)

| Pattern | Implementation |
| --- | --- |
| Redis circuit breaker | `app/resilience.py` + serve path; opens after N failures, recovers after timeout |
| Retry + backoff | Kafka publish (`kafka_publish_attempts`), PG candidates (`postgres_fetch_attempts`), consumer PG save (`consumer_pg_attempts`) — **transient errors only** |
| Consumer DLQ | After durable-write retries fail → Avro publish to `user-interactions-dlq`; poison messages still skipped |
| Metrics | `resilience_retries_total`, `circuit_breaker_opened_total`, `kafka_dlq_messages_total` |
