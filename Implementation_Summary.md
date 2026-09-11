# Recommendation Service — Implementation Summary

This file is the **condensed view of what was actually built**. It synthesizes the four implementation tutorials and the final architecture document.

Use this to understand the system. Use the tutorials when you need step-by-step code, commands, or verification.

| Document | Role |
| --- | --- |
| [`Readme.md`](Readme.md) | Original task list (goals) |
| [`implementation_Readme.md`](implementation_Readme.md) | Tutorial — Tasks 1–8 |
| [`implementation_Readme_2.md`](implementation_Readme_2.md) | Tutorial — Tasks 9–16 |
| [`implementation_Readme_3.md`](implementation_Readme_3.md) | Tutorial — Tasks 17–22 |
| [`implementation_Readme_4.md`](implementation_Readme_4.md) | Tutorial — Tasks 23–25 + resilience |
| [`system_architecture.md`](system_architecture.md) | Production architecture (Task 25) |
| **This file** | Cross-cutting implementation summary |

---

## 1. What we built

A **stateless FastAPI recommendation microservice** that:

1. Serves `GET /recommendations/{user_id}` with a versioned in-process model
2. Caches responses and online features in Redis
3. Ranks a PostgreSQL candidate catalog using Redis user features
4. Ingests user interactions via Kafka (Avro + Schema Registry)
5. Materializes durable event history (Postgres) and online features (Redis)
6. Degrades quality instead of going down when dependencies fail
7. Runs locally in Docker Compose and in Kubernetes with probes, canary, and HPA

**One-sentence principle:** the online path stays thin (cache → features + candidates → rank); expensive work happens asynchronously; failures lower recommendation quality, they do not take the API offline.

---

## 2. How the system grew (task map)

The service was built incrementally. Each task added one production concern.

### Phase 1 — API, cache, fallbacks (Tasks 1–8)

| Task | Implemented |
| --- | --- |
| 1 | FastAPI `GET /recommendations/{user_id}` with a hardcoded list |
| 2 | Pydantic schemas + `recommender.py` (HTTP vs domain split) |
| 3 | Dockerfile + `.dockerignore` |
| 4 | Redis cache-aside (`TTL`), Compose app + Redis |
| 5–6 | Fail-open cache: Redis down still returns HTTP 200 |
| 7 | Layered fallback: Redis → recommendation store → popular items |
| 8 | `GET /health` (liveness) and `GET /ready` (readiness) |

### Phase 2 — Config, K8s, Postgres, Kafka (Tasks 9–16)

| Task | Implemented |
| --- | --- |
| 9 | Pydantic Settings — Redis URL, timeout, TTL from env |
| 10 | Stateless app — in-process dict removed; store moved to Redis |
| 11 | Kubernetes Deployment + Service (1 replica, port-forward) |
| 12 | K8s liveness `/health` + readiness `/ready` probes |
| 13 | Manual replica scaling (`kubectl scale`) |
| 14 | PostgreSQL as source of truth; Redis kept as cache only |
| 15 | Kafka `user-interactions` producer + consumer (`POST /interactions`) |
| 16 | 3 partitions, key = `user_id`, consumer-group rebalance |

### Phase 3 — Contracts, ML path, CI, ops (Tasks 17–22)

| Task | Implemented |
| --- | --- |
| 17 | Apicurio Registry + Avro schema; V2 adds optional `device_type` |
| 18 | Feature store: Postgres `user_events` + Redis `features:user:*` |
| 19 | Candidate catalog + model v1/v2 ranking; `model_version` in response |
| 20 | GitHub Actions CI: pytest + Docker image build (no CD yet) |
| 21 | Structured logs, `X-Request-ID`, Prometheus `/metrics`, OTEL spans |
| 22 | Prediction logs, CTR, offline drift helpers, `/monitoring/model-quality` |

### Phase 4 — Release, scale, architecture (Tasks 23–25)

| Task | Implemented |
| --- | --- |
| 23 | Dual K8s Deployments (v1 + v2), shared Service, port-forward validate, rollback = delete v2 |
| 24 | `scripts/load_test.py` + HPA (min 3 / max 10 / CPU 50%) on `recommendation-service-v1` |
| 25 | [`system_architecture.md`](system_architecture.md) — final architecture synthesis |
| 25b | Redis circuit breaker, retry + backoff, Kafka consumer DLQ |

---

## 3. Architecture at a glance

Two paths must stay mentally separate.

### Synchronous serving path (must stay fast)

```text
GET /recommendations/{user_id}
        ↓
Redis cache  cache:recommendations:{user_id}
   ├── HIT  → return
   └── MISS
        ↓
     Redis features:user:{id}  +  Postgres recommendation_items
        ↓
     Model v1 / v2  .predict(features, candidates)
        ↓
     Cache write + impression (last_recs) + prediction log
        ↓
     HTTP 200  { user_id, recommendations, model_version }
```

The model **never** opens Redis, PostgreSQL, or Kafka. `RecommendationService` loads data; the model only ranks.

### Asynchronous event path (updates future requests)

```text
POST /interactions
        ↓
Pydantic validate → Avro + Schema Registry id
        ↓
Kafka topic user-interactions  (key = user_id, 3 partitions)
        ↓
Consumer group recommendation-service
        ↓
  1) PostgreSQL user_events     (durable history)
  2) Redis features:user:*      (online features)
```

Click CTR attribution also happens on `POST /interactions` when `event_type=click` and the item was in `last_recs:{user}`. That is API-side feedback, not a separate monitoring consumer.

Local Compose data plane:

```text
Clients → FastAPI :8000
              ├── Redis     (cache + online features)
              ├── PostgreSQL (candidates, fallback store, user_events)
              └── Kafka → kafka-consumer → PG history + Redis features
                    + Apicurio Schema Registry (Avro contracts)
```

---

## 4. Serving order and fallbacks

Every recommendation request walks this chain. Each step is optional except the last.

| Order | Source | When it runs | `model_version` |
| --- | --- | --- | --- |
| 1 | Redis response cache | Key present and Redis healthy | cached value |
| 2 | Model path | Cache miss; features + candidates available | `v1` or `v2` (`MODEL_VERSION`) |
| 3 | Postgres `recommendations` table | Model path failed | `postgres-store` |
| 4 | In-code popular list | Everything else failed | `popular-fallback` |

**Rule:** Redis, Postgres, Kafka, and Schema Registry are **optional** for readiness. `/ready` stays HTTP 200 while popular fallback exists. Only a missing fallback returns `503`.

`/health` is process liveness only — no Redis, Postgres, or Kafka I/O.

---

## 5. Data responsibilities

### PostgreSQL — durable / system of record

| Table | Role |
| --- | --- |
| `recommendation_items` | Candidate catalog the model ranks |
| `recommendations` | Per-user fallback store (Task 14) |
| `user_events` | Durable interaction history |

Predictions are **not** stored as a Postgres table; they go to structured logs and Prometheus metrics.

### Redis — low-latency online data

| Key | Role |
| --- | --- |
| `cache:recommendations:{user_id}` | Full response JSON + TTL |
| `features:user:{user_id}` | Online features (`click_count`, `purchase_count`, `last_item_id`) |
| `store:recommendations:{user_id}` | Used in Task 10 only; replaced by Postgres in Task 14 |
| `last_recs:{user_id}` | Last served list + version for CTR attribution (TTL 1h) |

### Kafka — event backbone

- Topic `user-interactions` (3 partitions, key = `user_id` for per-user ordering)
- Consumer group `recommendation-service`
- Avro wire format via Apicurio ccompat (`user-interactions-value` subject, FULL compatibility)
- DLQ topic `user-interactions-dlq` after durable-write retries fail
- Poison / pre-Avro JSON messages are skipped, not retried forever

### In-process ML model — ranking only

| Version | Rule |
| --- | --- |
| **v1** | Top 5 candidates by Postgres `score` (popularity) |
| **v2** | `score + click_count×0.01 + purchase_count×0.05 + 0.5` if item = `last_item_id` |

Deploy identity (`SERVICE_VERSION` on `/health`) is **not** the same as ML `MODEL_VERSION`.

---

## 6. API surface

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/recommendations/{user_id}` | Ranked recommendations |
| `POST` | `/interactions` | Publish user event to Kafka; click CTR hook |
| `GET` | `/features/{user_id}` | Online features from Redis |
| `GET` | `/events/{user_id}` | Durable event history from Postgres |
| `GET` | `/health` | Liveness (`status`, deploy `version`) |
| `GET` | `/ready` | Readiness + optional dependency status |
| `GET` | `/metrics` | Prometheus scrape |
| `GET` | `/monitoring/model-quality` | Per-version served / clicked / CTR |
| `GET` | `/docs` | OpenAPI UI |
| `GET` | `/demo/cpu-burn` | Demo-only CPU load for HPA (not product logic) |

Typical recommendation response:

```json
{
  "user_id": 123,
  "recommendations": [10, 20, 30, 40, 50],
  "model_version": "v1"
}
```

`/ready` reports Redis, Postgres, Kafka, Schema Registry, and fallback. Down dependencies are informational; the instance stays ready if fallback works.

---

## 7. Key implementation decisions

These are the choices that shaped the code, not just the tutorials.

| Decision | Why |
| --- | --- |
| **Stateless FastAPI** | Any replica can serve any user. Shared state lives in Redis / Postgres / Kafka. Enables HPA, rolling deploys, and restarts. |
| **Config outside code** | Same image, different env via Pydantic Settings + Compose / K8s. |
| **Redis ≠ source of truth** | Task 10 used Redis as a temporary store so replicas could share data. Task 14 split: Redis = cache/features, Postgres = durable SoT. |
| **Cache-aside** | Read Redis first; on miss, compute; write back with TTL. Separate key prefixes so cache never overwrites features or store. |
| **Fail-open cache / optional deps** | Caching accelerates; it is not required to serve. `/ready` does not fail when Redis is down. |
| **Model does not own I/O** | Service fetches features + candidates; `model.predict(...)` only ranks. Keeps ranking testable and version-swappable. |
| **Two Postgres tables for recs** | `recommendation_items` = candidate catalog. `recommendations` = per-user fallback store. Different jobs. |
| **One Kafka consumer does two writes** | History first, then online features. Production would often split those into independent consumer groups. |
| **Avro under `app/avro/`** | Project already had `app/schemas.py` for Pydantic. A `schemas/` package would shadow it. |
| **Apicurio instead of Confluent Registry** | Smaller local image; Confluent-compatible API (`/apis/ccompat/v7`) still used for wire format. |
| **FULL schema compatibility** | V2 adds optional `device_type` with default `null` so old and new readers both work. |
| **Drift off the request path** | Prediction logs + metrics on serve; `detect_drift` is offline/batch only. |
| **Canary via two Deployments** | Teaching artifact. Service selector is `app` only (not `version`) so both can receive traffic. Weighted 90/10 needs a mesh later. |
| **Delete v2 before HPA demos** | Shared Service would mix v1+v2 CPU/latency; HPA must target one Deployment. |
| **Soft DB init in K8s** | `init_db()` failure logs and continues so pods still become Ready via popular fallback. |

---

## 8. Resilience layers

Graceful degradation (Tasks 6–7, 14) was the outer story. Hardening (Task 25b) makes it fail faster and cleaner.

```text
Layer A — Circuit / retry     fail fast or absorb blips
Layer B — Fallback chain      cache → model → PG store → popular
Layer C — Platform            probes, canary rollback, HPA
```

| Tool | Where | Behavior |
| --- | --- | --- |
| **Redis circuit breaker** | Cache get/set + online features | CLOSED → try Redis; after N failures OPEN → skip immediately; HALF-OPEN probe after recovery window |
| **Retry + backoff** | Kafka publish, PG candidate fetch, consumer PG save | Transient errors only (timeouts, connection resets). Logic bugs are not retried. |
| **DLQ** | Consumer durable write | After PG save retries fail → publish Avro payload to `user-interactions-dlq` → continue (partition not stuck) |

Defaults (env-overridable): breaker opens after 3 Redis failures, recovers after 30s; Kafka publish / PG fetch 2 attempts; consumer PG save 3 attempts; base delay 0.05s.

Metrics: `resilience_retries_total`, `circuit_breaker_opened_total`, `kafka_dlq_messages_total`.

---

## 9. Kubernetes, CI, and observability

### Kubernetes (`k8s/`)

| Manifest | Role |
| --- | --- |
| `deployment.yaml` | Stable **v1** Deployment (`recommendation-service-v1`), probes, resources, `SERVICE_VERSION=v1` |
| `deployment-v2.yaml` | Canary **v2** (apply only for Task 23; remove before HPA) |
| `service.yaml` | Selector `app=recommendation-service` only — both versions can share it |
| `hpa.yaml` | CPU 50%, min 3 / max 10, target `recommendation-service-v1` |

Liveness → restart if `/health` fails. Readiness → Service sends traffic only to Ready pods. Manual scale (Task 13) vs HPA (Task 24): HPA decides replica count from measured CPU after a load test.

`imagePullPolicy: Never` — local Docker Desktop image, not pulled from a registry.

### CI (Task 20) — not CD

GitHub Actions (`.github/workflows/ci.yml`) on push/PR: Python 3.12 → `pytest` → `docker build`. Image push and auto-deploy are **not** implemented.

### Observability (Task 21–22)

| Signal | Mechanism |
| --- | --- |
| Logs | `structlog` JSON on stdout; events like `cache_hit`, `recommendation_served`, `prediction_logged` |
| Correlation | `X-Request-ID` middleware (echo inbound or generate UUID) |
| Metrics | Prometheus text at `GET /metrics` (requests, latency, Redis/PG failures, model CTR, resilience) |
| Traces | OpenTelemetry spans around Redis / Postgres / model; exporter `console` or `none` |
| Model quality | Impressions + attributed clicks → CTR per `model_version` |

Prometheus, Grafana, and Jaeger **backends** are not in Compose. The app exposes the hooks.

---

## 10. Final application layout

```text
recommendation-service/
├── app/
│   ├── main.py                      # Routes, lifespan, cache, probes, CTR hook
│   ├── schemas.py                   # Pydantic API models
│   ├── config.py                    # Env Settings
│   ├── recommendation_service.py    # Features + candidates → model
│   ├── recommendation_store.py      # Postgres fallback store + popular list
│   ├── recommendation_repository.py # Candidate catalog from Postgres
│   ├── recommender.py               # Thin store helper
│   ├── model.py / model_registry.py # v1 / v2 ranking
│   ├── features.py / feature_store.py
│   ├── event_store.py / events.py
│   ├── database.py / redis_client.py / seed.py
│   ├── kafka_producer.py / kafka_consumer.py
│   ├── schema_registry.py + avro/*.avsc
│   ├── resilience.py                # Circuit breaker + retry_async
│   ├── logging_config.py / middleware.py / metrics.py / tracing.py
│   ├── prediction_logger.py / drift.py / model_quality.py
│   └── …
├── k8s/          deployment.yaml, deployment-v2.yaml, service.yaml, hpa.yaml
├── tests/        pytest (no live Redis/Postgres/Kafka required)
├── scripts/      load_test.py
├── .github/workflows/ci.yml
├── Dockerfile / docker-compose.yml / requirements.txt
└── docs          this file, implementation_Readme*.md, system_architecture.md
```

Compose stack: `app`, `redis`, `postgres`, `kafka`, `kafka-init`, `kafka-consumer` (scalable), `schema-registry`.

---

## 11. Implemented vs conceptual

| Area | In this repo |
| --- | --- |
| FastAPI, Pydantic, pytest, Docker, Compose | Implemented |
| Redis cache + online features, Postgres SoT | Implemented |
| Kafka + 3 partitions + one consumer group | Implemented |
| Avro + Apicurio Schema Registry | Implemented |
| Model v1/v2, feature store, graceful degradation | Implemented |
| Circuit breaker, retries, DLQ | Implemented |
| K8s Deploy/Service/probes, canary, HPA, load test | Implemented |
| CI (pytest + image build) | Implemented |
| CD (registry push + auto-deploy) | Conceptual |
| Ingress / weighted canary (Istio) | Conceptual |
| Prometheus / Grafana / Jaeger backends | Conceptual (app already instrumented) |
| Independent Kafka consumer groups (history vs features vs analytics vs monitoring) | Conceptual — one group does PG then Redis today |

---

## 12. How to run the finished local stack

```powershell
docker compose up -d --build
docker compose exec app python -m app.seed
```

Then:

```text
http://localhost:8000/docs
http://localhost:8000/recommendations/123
http://localhost:8000/health
http://localhost:8000/ready
```

After Python changes, rebuild with `--build` or the container keeps the old image.

Kubernetes (Docker Desktop): build the image, `kubectl apply -f k8s/`, port-forward the Service. For HPA demos, do **not** apply `deployment-v2.yaml`.

Full verification steps live in the part tutorials and [`Manual_Testing_Readme.md`](Manual_Testing_Readme.md).

---

## 13. Interview anchors

These map directly to the implementation, not to a hypothetical design.

1. **Why stateless?** Replicas share Redis/Postgres/Kafka, not process memory — required for HPA and rolling deploys.
2. **Why Redis and Postgres?** Postgres is durable (candidates, history, fallback store). Redis is hot path (response cache, online features).
3. **Why Kafka?** Decouple “user did X” from “several systems react.” New consumers can join without changing FastAPI. Partitions parallelize; groups coordinate.
4. **What if Redis dies?** Circuit opens after repeated failures; API skips Redis immediately, then Postgres store, then popular list. Quality drops; availability stays.
5. **How do we ship v2 safely?** Distinct `SERVICE_VERSION` / image tag, second Deployment, validate via port-forward, share Service only when Ready, delete v2 to roll back. Weighted traffic is the next mesh step.
6. **How do we know the model is healthy?** Prediction logs + Prometheus CTR per version; drift helpers run offline, never inside `GET /recommendations`.
