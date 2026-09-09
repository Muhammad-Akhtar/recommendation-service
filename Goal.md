I am continuing a step-by-step project from another ChatGPT conversation. Please continue from exactly where we stopped and do NOT restart or skip ahead.

## Goal

I am learning how to build a production-ready, scalable Python recommendation microservice and understand these concepts practically:

* FastAPI
* Pydantic
* Testing with pytest
* Docker
* Docker Compose
* Redis caching
* Graceful degradation / fault tolerance
* Recommendation store fallback
* Health/readiness checks
* Configuration management
* Kubernetes
* Kafka/event-driven architecture
* Feature store
* Model deployment/versioning
* CI/CD
* Monitoring/observability
* Canary/blue-green deployment
* Scaling and fault tolerance

The original discussion was based on system-design/interview questions around scaling a recommendation service to billions of users, low latency, fault tolerance, Kafka decoupling, schema evolution, GenAI API quality, CI/CD, monitoring, and graceful degradation.

## How I want to learn

Teach me ONE TASK AT A TIME.

For each task:

1. Explain the goal simply.
2. Tell me exactly what to implement.
3. Give only the necessary code/instructions.
4. Let me implement it myself.
5. I will reply "Task X done".
6. Then give me the next task.

Do NOT dump the entire project at once.

Keep the implementation simple first, then gradually make it production-like.

## Progress completed

### Task 1 — Basic FastAPI recommendation API

DONE.

Created a basic:
GET /recommendations/{user_id}

Returning recommendation IDs.

### Task 2 — Production-style structure

DONE.

Separated:

* FastAPI/API layer
* Pydantic schemas
* recommendation logic

Added pytest tests.

Current conceptual flow:

HTTP Request
→ FastAPI
→ Pydantic validation
→ Recommendation logic
→ Pydantic response

### Task 3 — Docker

DONE.

Created Dockerfile and successfully built/ran the FastAPI service in Docker.

### Task 4 — Redis caching

DONE.

Added Redis 7 and implemented:

* cache lookup
* cache hit
* cache miss
* storing recommendations
* TTL

### Task 5 — Redis graceful failure

DONE.

If Redis becomes unavailable:

* API does not crash
* recommendation logic is used
* response still succeeds
* Redis write is skipped when unavailable
* Redis failure is logged

### Task 6 — Docker Compose

DONE.

Current Compose setup has:

* FastAPI app
* Redis

Important Docker networking detail:
The FastAPI container connects to Redis using the Compose service name, e.g.:

REDIS_URL=redis://redis:6379

rather than localhost.

We discussed that different Compose projects can have their own `redis` service because Compose networks isolate them.

### Task 7 — Recommendation store fallback

DONE.

Current graceful degradation concept:

Request
→ Redis
→ if cache hit: return

If Redis misses/fails:
→ Recommendation Store
→ if available: return recommendations and optionally cache

If both fail:
→ Popular/Trending recommendations
→ return useful result

So the service continues providing a reasonable user experience even when personalization infrastructure fails.

### Task 8 — CURRENT TASK

I am currently implementing health checks.

The task is:

* GET /health
* GET /ready

/health should indicate the application process is alive and should NOT depend on Redis.

/ready should indicate whether the service can currently serve requests.

Important: Redis is an optional dependency because the service has graceful fallback behavior. Therefore Redis being down should NOT automatically mean the entire service is unavailable.

We have NOT completed Task 8 yet.

## Next planned tasks

Task 1 — Build a very simple Recommendation API

Task 2 — Make the service production-style

Task 3 — Dockerize the Recommendation Service

Task 4 — Add Redis caching

Task 5 — Handle Redis failure gracefully

Task 6 — Docker Compose

Task 7 — Add a fallback recommendation source

Task 8 — Add health checks

Task 9 — Configuration management with environment variables

Then progressively:

Task 10 — Kubernetes deployment

Task 11 — Kubernetes Services/configuration

Task 12 — Kubernetes liveness/readiness probes

Task 13 — Kubernetes scaling

Task 14 — PostgreSQL/persistent recommendation store

Task 15 — Kafka event-driven pipeline

Task 16 — Kafka topics, partitions and consumer groups

Task 17 — Schema Registry and schema evolution

Task 18 — Feature store

Task 19 — Model serving/versioning

Task 20 — CI/CD

Task 21 — Monitoring/observability

Task 22 — Model regression/drift monitoring

Task 23 — Canary/blue-green deployment and rollback

Task 24 — Load testing and performance

Task 25 — Final production architecture

## Current project architecture

```text
Client
  → Load Balancer / port-forward (local)
  → Kubernetes Service + HPA (optional)  OR  Docker Compose `app`
  → FastAPI (stateless replicas)
       ├── Redis — response cache + online features
       ├── PostgreSQL — candidates, per-user store, user_events
       ├── Kafka + Schema Registry — interactions → consumer → PG + Redis features
       └── Model v1/v2 — ranking only (no direct DB/Redis I/O)
  → Observability: structured logs, /metrics, OTEL spans, model CTR/drift helpers
  → CI: GitHub Actions (pytest + Docker build)
```

Full diagrams, sync/async flows, and interview Q&A: [`system_architecture.md`](system_architecture.md).

Continue from **Task 8**, not Task 1. (Roadmap above lists Tasks 9–25.)
