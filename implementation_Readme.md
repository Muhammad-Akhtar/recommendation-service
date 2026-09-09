# Recommendation Service — Implementation Tutorial (Tasks 1–8)

This document walks through **how we actually built** the service, task by task.

- [`Readme.md`](Readme.md) = high-level goals (“do this, then that”)
- **This file** = implementation tutorial (concepts + focused code for what was new at each step)

---

## Overview

We built a Recommendation API incrementally:

| Task | What we implemented |
| --- | --- |
| 1 | Simple FastAPI endpoint with hardcoded recommendations |
| 2 | Pydantic schemas + separated recommendation logic |
| 3 | Docker image for the API |
| 4 | Redis caching |
| 5 | Docker Compose (app + Redis on a shared network) |
| 6 | Graceful degradation when Redis is down |
| 7 | Recommendation store + popular-items fallback |
| 8 | Health checks (`/health` liveness, `/ready` readiness) |

Final response shape:

```json
{
  "user_id": 123,
  "recommendations": [10, 25, 42, 81, 99]
}
```

---

## Project layout (final)

```text
recommendation-service/
├── app/
│   ├── __init__.py
│   ├── main.py                 # Routes, cache, fallbacks, health checks
│   ├── schemas.py              # Pydantic models (incl. health/ready)
│   ├── recommender.py          # Calls the recommendation store
│   ├── recommendation_store.py # Simulated store + popular list
│   └── redis_client.py         # Async Redis connection
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── requirements.txt
├── Readme.md
└── implementation_Readme.md
```

> Note: In this tutorial, Task 4 covers Redis caching concepts and Task 5–6 cover Compose + Redis failure handling (see those sections above). Task 7 adds the next fallback layer. Task 8 adds Kubernetes-oriented probes.

## Task 1 — Basic Recommendation API

### Topic / goal

Expose `GET /recommendations/{user_id}` and return a hardcoded list of item IDs. No Redis, Docker, or ML yet.

### Technical concepts

- **FastAPI** — Python web framework for APIs
- **Path parameter** — `{user_id}` taken from the URL
- **Uvicorn** — ASGI server that runs the FastAPI app
- **OpenAPI docs** — automatic interactive UI at `/docs`

### What changed

| File | Action |
| --- | --- |
| `app/__init__.py` | Added (marks `app` as a package) |
| `app/main.py` | Added (endpoint + hardcoded response) |
| `requirements.txt` | Added (`fastapi`, `uvicorn`, `pytest`) |

### Code examples (new)

Minimal endpoint idea:

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/recommendations/{user_id}")
async def read_recommendations(user_id: int):
    return {
        "user_id": user_id,
        "recommendations": [10, 25, 42, 81, 99],
    }
```

### How to verify

```bash
pip install fastapi uvicorn pytest
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

Call:

```text
GET /recommendations/123
```

Expect HTTP `200` and JSON containing `user_id` and `recommendations`.

---

## Task 2 — Production-style structure

### Topic / goal

Separate HTTP handling from recommendation logic, and validate responses with Pydantic models.

### Technical concepts

- **Pydantic `BaseModel`** — typed request/response schemas
- **Separation of concerns** — API layer (`main.py`) vs domain logic (`recommender.py`)
- **`response_model`** — FastAPI validates/serializes the return value against a schema

### Request flow

```text
HTTP Request
     ↓
FastAPI endpoint
     ↓
Pydantic validation
     ↓
Recommendation logic
     ↓
Pydantic response
     ↓
HTTP Response
```

### What changed

| File | Action |
| --- | --- |
| `app/schemas.py` | Added |
| `app/recommender.py` | Added |
| `app/main.py` | Updated to call recommender + use schemas |

### Code examples (new)

**Schemas** (`app/schemas.py`):

```python
from pydantic import BaseModel


class RecommendationData(BaseModel):
    user_id: int
    recommendations: list[int]


class RecommendationResponse(BaseModel):
    user_id: int
    recommendations: list[int]
```

**Recommender** (`app/recommender.py`):

```python
from .schemas import RecommendationData


def get_recommendations(user_id: int) -> RecommendationData:
    return RecommendationData(
        user_id=user_id,
        recommendations=[10, 25, 42, 81, 99],
    )
```

**Endpoint wiring** (concept):

```python
@app.get("/recommendations/{user_id}", response_model=RecommendationResponse)
async def read_recommendations(user_id: int) -> RecommendationResponse:
    data = get_recommendations(user_id)
    return RecommendationResponse(
        user_id=data.user_id,
        recommendations=data.recommendations,
    )
```

### How to verify

```bash
uvicorn app.main:app --reload
```

Response shape stays the same, but now it comes from typed models + a dedicated function.

---

## Task 3 — Dockerize the service

### Topic / goal

Package the FastAPI app so it runs the same way on any machine via Docker.

### Technical concepts

- **Image vs container** — image is the blueprint; container is a running instance
- **Dockerfile layers** — each instruction builds a reusable layer
- **Port mapping** — `-p 8000:8000` exposes container port 8000 on the host
- **`.dockerignore`** — keeps local junk (`.venv`, tests, caches) out of the image

### What changed

| File | Action |
| --- | --- |
| `Dockerfile` | Added |
| `.dockerignore` | Added |

### Code examples (new)

**Dockerfile**:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`--host 0.0.0.0` is required so the API is reachable from outside the container.

### How to verify

```bash
docker build -t recommendation-service .
docker run -p 8000:8000 recommendation-service
```

Then open:

```text
http://localhost:8000/docs
```

Stop any local Uvicorn process first so you know the response is coming from Docker.

---

## Task 4 — Redis caching

### Topic / goal

Cache recommendations in Redis so repeated requests for the same user skip recomputation (within a TTL).

### Technical concepts

- **Cache HIT / Cache MISS** — key found vs not found
- **TTL** — cache entry expires after N seconds (`ex=60`)
- **Async Redis client** — `redis.asyncio` fits FastAPI’s async endpoints
- **Docker networking** — inside a container, `localhost` is *that* container, not Redis
- **Service hostname** — use container name `recommendation-redis`
- **`REDIS_URL` env var** — configure Redis address without hardcoding for every environment
- **Docker Compose** — start app + Redis on one shared network

### Cache flow

```text
Request
   ↓
Check Redis
   ↓
Cache HIT ─────────► Return recommendations
   │
   └── Cache MISS
          ↓
   Recommendation logic
          ↓
       Redis SET (TTL 60s)
          ↓
       Return results
```

### What changed

| File | Action |
| --- | --- |
| `app/redis_client.py` | Added |
| `app/main.py` | Updated with cache get/set |
| `docker-compose.yml` | Added (app + Redis) |
| `requirements.txt` | Added `redis` |

### Code examples (new)

**Redis client** (`app/redis_client.py` — connection part):

```python
import os
import redis.asyncio as redis

REDIS_URL = os.getenv("REDIS_URL", "redis://recommendation-redis:6379")

redis_client = redis.from_url(
    REDIS_URL,
    decode_responses=True,
)
```

**Cache key + get/set** (concept from `app/main.py`):

```python
cache_key = f"recommendations:{user_id}"

cached = await redis_client.get(cache_key)
if cached:
    print("Cache HIT")
    return RecommendationResponse(**json.loads(cached))

print("Cache MISS")
# compute recommendations...
await redis_client.set(cache_key, response.model_dump_json(), ex=60)
```

**Compose excerpt** (`docker-compose.yml`):

```yaml
services:
  redis:
    image: redis:7
    container_name: recommendation-redis
    ports:
      - "6379:6379"

  app:
    build: .
    container_name: recommendation-service
    ports:
      - "8000:8000"
    depends_on:
      - redis
    environment:
      - REDIS_URL=redis://recommendation-redis:6379
```

Important: from the app container use `redis://recommendation-redis:6379`, **not** `redis://localhost:6379`.

### How to verify

```bash
docker compose up -d --build
```

Call twice:

```text
GET http://localhost:8000/recommendations/123
```

Check logs:

```bash
docker logs recommendation-service
```

Expect:

```text
Cache MISS
Running recommendation logic...
...
Cache HIT
```

---

## Task 5 & 6 — Graceful degradation when Redis fails & Docker-compose

### Topic / goal

If Redis is down or unreachable, the API still returns recommendations with HTTP `200` instead of crashing with `500`.

### Technical concepts

- **Fault tolerance** — dependency failure should not take down the whole API
- **Graceful degradation** — lose caching, keep core behavior
- **Fail-open cache** — treat Redis as optional acceleration, not a hard requirement
- **`try` / `except`** — catch Redis errors on read and write
- **Short socket timeouts** — fail fast instead of hanging on a dead Redis
- **Rebuild after code changes** — `docker compose up -d --build` so the container picks up new Python code

### Failure flow

```text
Request
   ↓
Redis
   │
   ├── Available → use cache (HIT/MISS as usual)
   │
   └── Unavailable
          ↓
   get_recommendations()
          ↓
   Skip Redis SET
          ↓
   Return 200 OK
```

### What changed

| File | Action |
| --- | --- |
| `app/main.py` | Wrapped Redis read/write in `try/except`; skip SET when Redis already failed |
| `app/redis_client.py` | Added short connect/read timeouts |

### Code examples (new)

**Timeouts** (`app/redis_client.py`):

```python
redis_client = redis.from_url(
    REDIS_URL,
    decode_responses=True,
    socket_connect_timeout=1,
    socket_timeout=1,
)
```

**Fault-tolerant endpoint core** (`app/main.py`):

```python
cache_key = f"recommendations:{user_id}"
redis_available = True

try:
    cached = await redis_client.get(cache_key)
    if cached:
        print("Cache HIT")
        return RecommendationResponse(**json.loads(cached))
    print("Cache MISS")
except Exception as e:
    redis_available = False
    print(f"Redis unavailable while reading cache: {e}")

recommendations = get_recommendations(user_id)
response = RecommendationResponse(
    user_id=recommendations.user_id,
    recommendations=recommendations.recommendations,
)

if redis_available:
    try:
        await redis_client.set(
            cache_key,
            response.model_dump_json(),
            ex=60,
        )
    except Exception as e:
        print(f"Redis unavailable while writing cache: {e}")

return response
```

What this buys you:

1. Redis errors do **not** crash the API
2. Fallback always calls `get_recommendations()`
3. Normal JSON response is still returned
4. We skip `SET` when Redis already failed on read
5. Logs show that Redis was unavailable

### How to verify

Rebuild so the container has the new code:

```bash
docker compose up -d --build
```

Normal path (Redis up):

```text
GET /recommendations/123  →  200 OK
```

Stop Redis:

```bash
docker stop recommendation-redis
```

Call again:

```text
GET /recommendations/123  →  still 200 OK + recommendations
```

Start Redis again:

```bash
docker start recommendation-redis
```

Cache behavior returns once Redis is healthy.

---

## Task 7 — Fallback recommendation source

### Topic / goal

Make fallbacks more realistic: after Redis miss/failure, try a **recommendation store**; if that also fails (or has no user data), return **popular recommendations** so the API always returns something useful.

### Technical concepts

- **Layered graceful degradation** — multiple fallback levels instead of one:
  1. Redis cache
  2. Recommendation store (personalized)
  3. Popular / trending items (global)
- **Recommendation store** — simulated persistent source (dict for now; later this becomes a DB)
- **Store miss vs store failure** — unknown user (`KeyError`) and real outages both fall through to popular items
- **Popular recommendations** — a safe default list useful for *any* user when personalization is unavailable
- **Cache-aside after store HIT** — when the store succeeds, optionally write back into Redis for the next request
- **Separation of concerns** — store data lives in `recommendation_store.py`; `recommender.py` stays a thin service layer; `main.py` owns the fallback order

### Fallback flow

```text
Request
   ↓
Redis
   │
   ├── HIT ──────────────► Return
   │
   └── unavailable/miss
            ↓
     Recommendation Store
            │
            ├── available ──► Return + cache in Redis
            │
            └── unavailable / unknown user
                    ↓
              Popular Items
                    ↓
                  Return
```

### What changed

| File | Action |
| --- | --- |
| `app/recommendation_store.py` | Added (in-memory store + `POPULAR_RECOMMENDATIONS`) |
| `app/recommender.py` | Updated to call the store and return `list[int]` |
| `app/main.py` | Updated flow: Redis → store → popular |

### Code examples (new)

**Recommendation store** (`app/recommendation_store.py`):

```python
RECOMMENDATION_STORE = {
    123: [10, 25, 42, 81, 99],
    456: [12, 33, 47, 58, 72],
    789: [5, 18, 29, 61, 94],
}

POPULAR_RECOMMENDATIONS = [10, 20, 30, 40, 50]


def get_recommendations(user_id: int) -> list[int]:
    recommendations = RECOMMENDATION_STORE.get(user_id)

    if recommendations is None:
        raise KeyError(f"No recommendations found for user {user_id}")

    return recommendations
```

**Thin recommender layer** (`app/recommender.py`):

```python
from .recommendation_store import get_recommendations as get_recommendations_for_user


def get_recommendations(user_id: int) -> list[int]:
    print("Running recommendation logic...")
    return get_recommendations_for_user(user_id)
```

**Layered fallback in the endpoint** (core of `app/main.py`):

```python
# After Redis miss/fail...
try:
    recommendations = get_recommendations(user_id)
    response = RecommendationResponse(
        user_id=user_id,
        recommendations=recommendations,
    )
    # optionally cache in Redis if redis_available
    return response
except Exception as e:
    print(f"Recommendation store unavailable: {e}")

# Store miss/fail → popular recommendations
return RecommendationResponse(
    user_id=user_id,
    recommendations=POPULAR_RECOMMENDATIONS,
)
```

Important: `recommendations` must be a `list[int]`, matching `RecommendationResponse`. Do not wrap a whole response object inside `recommendations=...`.

### How to verify

Rebuild:

```bash
docker compose up -d --build
```

| Redis | Store | Call | Expected result |
| --- | --- | --- | --- |
| ✅ / miss | ✅ known user | `GET /recommendations/123` | Personalized `[10, 25, 42, 81, 99]` |
| ✅ | ✅ (2nd call) | `GET /recommendations/123` | Cache HIT (same list) |
| ✅ / miss | ❌ unknown user | `GET /recommendations/999` | Popular `[10, 20, 30, 40, 50]` |
| ❌ stopped | ✅ known user | `GET /recommendations/123` | Personalized from store |
| ❌ stopped | ❌ unknown user | `GET /recommendations/999` | Popular recommendations |

Check logs:

```bash
docker logs recommendation-service
```

You should see messages like:

```text
Cache MISS
Running recommendation logic...
Recommendation store HIT for user_id: 123
```

or:

```text
Recommendation store unavailable: 'No recommendations found for user 999'
Using popular recommendations
```

**Task 7 is complete when the API still returns useful recommendations even after both Redis and the recommendation store cannot provide personalized data.**

---

## Task 8 — Health checks (liveness & readiness)

### Topic / goal

Add Kubernetes-ready probe endpoints so orchestrators can tell whether the process is alive and whether it can currently serve traffic.

### Technical concepts

- **Liveness** — “Is the process stuck or dead?” Used later by Kubernetes to **restart** a broken container. Must stay simple and independent of optional dependencies.
- **Readiness** — “Can this instance receive traffic right now?” Used later by Kubernetes to **remove** an instance from the load balancer without necessarily restarting it.
- **Optional vs required dependencies** — Redis is optional (Tasks 6–7 fallbacks). Do **not** mark `/ready` as `503` just because Redis is down.
- **HTTP `503 Service Unavailable`** — return this from `/ready` only when the service cannot serve a useful response at all.
- **Probe-friendly responses** — small JSON payloads; liveness has no external I/O; readiness may inspect dependencies but should match real serving ability.
- **Observability in readiness body** — report Redis up/down for operators, while still returning `200` if fallbacks work.

### Probe model (why both exist)

```text
Kubernetes
    │
    ├── Liveness probe  →  GET /health
    │                      restart container if failing
    │
    └── Readiness probe →  GET /ready
                           stop sending traffic if failing
```

### What changed

| File | Action |
| --- | --- |
| `app/schemas.py` | Added `HealthResponse`, `ReadyResponse` |
| `app/main.py` | Added `GET /health` and `GET /ready` |

### Code examples (new)

**Schemas** (`app/schemas.py`):

```python
class HealthResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    status: str
    redis: str
    fallback: str
```

**Liveness** — no Redis, no store:

```python
@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")
```

**Readiness** — Redis status is informational; ready if popular fallback exists:

```python
@app.get("/ready", response_model=ReadyResponse)
async def ready(response: Response) -> ReadyResponse:
    redis_status = "up"
    try:
        await redis_client.ping()
    except Exception:
        redis_status = "down"

    fallback_ok = bool(POPULAR_RECOMMENDATIONS)

    if not fallback_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadyResponse(
            status="not_ready",
            redis=redis_status,
            fallback="unavailable",
        )

    return ReadyResponse(
        status="ready",
        redis=redis_status,
        fallback="available",
    )
```

### How to verify

Rebuild:

```bash
docker compose up -d --build
```

With Redis running:

```text
GET /health  →  200  {"status":"ok"}
GET /ready   →  200  {"status":"ready","redis":"up","fallback":"available"}
```

Stop Redis:

```bash
docker stop recommendation-redis
```

Then:

```text
GET /health  →  200  {"status":"ok"}
GET /ready   →  200  {"status":"ready","redis":"down","fallback":"available"}
```

`/health` stays healthy. `/ready` stays ready because the service can still answer via store/popular fallback. Redis down is reported in the body, not as a hard failure.

Start Redis again:

```bash
docker start recommendation-redis
```

**Task 8 is complete when `/health` and `/ready` are implemented and tested with Redis up and down.**

---

## How to run the finished stack

From the project root:

```bash
docker compose up -d --build
```

Check containers:

```bash
docker ps
```

You should see `recommendation-service` and `recommendation-redis`.

Try:

```text
http://localhost:8000/recommendations/123
http://localhost:8000/docs
```

Stop everything:

```bash
docker compose down
```

After any Python code change, rebuild:

```bash
docker compose up -d --build
```

Without `--build`, Docker keeps the old image and you will debug “fixed” code that never deployed.
