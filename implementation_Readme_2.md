# Recommendation Service — Implementation Tutorial (Part 2)

This file continues from [`implementation_Readme.md`](implementation_Readme.md) (Tasks 1–8).

- Part 1 → Tasks 1–8
- **Part 2 → Tasks 9–16** (configuration → Kubernetes → Postgres → Kafka partitions / consumer groups)

---

## Overview (Part 2)

| Task | What we implemented |
| --- | --- |
| 9 | Configuration via environment variables + Pydantic Settings |
| 10 | Stateless app — recommendation store moved to shared Redis |
| 11 | First Kubernetes Deployment + Service (1 replica) |
| 12 | Kubernetes liveness (`/health`) + readiness (`/ready`) probes |
| 13 | Scale replicas / Kubernetes scaling (completed separately) |
| 14 | PostgreSQL persistent store; Redis kept as cache only |
| 15 | Kafka event-driven user-interactions (producer + consumer) |
| 16 | Kafka topic partitions + consumer-group scaling / rebalance |

Key principle (Task 9):

> **Configuration belongs outside the application code.**

Key principle (Task 10):

> **A Kubernetes replica should not depend on local application memory for shared state.**

Key principle (Task 11):

> **Deployment runs pods; Service gives them a stable network name.**

Key principle (Task 12):

> **Liveness = is the app alive? Readiness = should it receive traffic?**

Key principle (Task 14):

> **Redis = fast cache. PostgreSQL = persistent source of truth.**

Key principle (Task 15):

> **Publish events to Kafka so many consumers can react without coupling to FastAPI.**

Key principle (Task 16):

> **Partitions provide parallelism. Consumer groups provide coordinated consumption.**

```text
Environment Variables
        ↓
     Settings
        ↓
Application
        ↓
Redis / PostgreSQL / Kafka
```

---

## Project layout (after Task 16)

```text
recommendation-service/
├── app/
│   ├── __init__.py
│   ├── main.py                 # API + lifespan; POST /interactions; /health /ready
│   ├── schemas.py              # Pydantic API models (incl. ready.kafka)
│   ├── config.py               # Settings (Redis, Postgres, Kafka topic/group)
│   ├── redis_client.py         # Async Redis (cache only after Task 14)
│   ├── database.py             # asyncpg pool + schema (Task 14)
│   ├── recommendation_store.py # Postgres store + popular fallback
│   ├── recommender.py          # Store lookup helper
│   ├── seed.py                 # Seed Postgres recommendations
│   ├── events.py               # UserInteractionEvent (Task 15)
│   ├── kafka_producer.py       # Publish events; Task 16: key=user_id
│   └── kafka_consumer.py       # Consumer group; Task 16: partitions + rebalance logs
├── tests/
│   ├── test_config.py
│   ├── test_events.py
│   └── test_recommendations.py
├── k8s/
│   ├── deployment.yaml         # Task 11+ (probes in Task 12)
│   └── service.yaml
├── Dockerfile
├── docker-compose.yml          # redis, postgres, kafka, kafka-init, app, kafka-consumer
├── requirements.txt            # + asyncpg, aiokafka, …
├── Readme.md
├── implementation_Readme.md    # Tasks 1–8
└── implementation_Readme_2.md  # Tasks 9–16 (this file)
```

### Files touched in Task 16

```text
recommendation-service/
├── app/
│   ├── kafka_producer.py   # CHANGED — partition key = str(user_id); log partition/offset
│   └── kafka_consumer.py   # CHANGED — rebalance listener; log instance/partition/key
└── docker-compose.yml      # CHANGED — KAFKA_NUM_PARTITIONS=3; kafka-init (3 partitions);
                            #           scalable kafka-consumer (no fixed container_name)
```

`app/config.py` already had `kafka_consumer_group` from Task 15 — no Task 16 change required.

---

## Task 9 — Configuration management

### Topic / goal

Move Redis URL, Redis timeout, and cache TTL out of hard-coded Python values into **environment variables**, loaded through **Pydantic Settings**, and supplied by Docker Compose.

### Technical concepts

- **Externalized configuration** — same image, different env per development / staging / production
- **Pydantic Settings (`BaseSettings`)** — typed settings from env vars (and optional `.env`)
- **Attribute access** — use `settings.redis_url`, `settings.redis_timeout`, `settings.cache_ttl` instead of string literals
- **Sensible defaults** — app boots even if env vars are missing
- **Env override** — e.g. `$env:CACHE_TTL="120"` changes TTL without editing code
- **Compose as config injector** — Compose `environment:` passes values into the container
- **Compose service hostname** — `REDIS_URL=redis://redis:6379` uses the Compose **service name** `redis`

### Settings we expose

| Env variable | Settings field | Default | Meaning |
| --- | --- | --- | --- |
| `REDIS_URL` | `settings.redis_url` | `redis://redis:6379` | Redis connection URL |
| `REDIS_TIMEOUT` | `settings.redis_timeout` | `0.05` | Socket connect/read timeout (seconds) |
| `CACHE_TTL` | `settings.cache_ttl` | `60` | Cache entry TTL (seconds) |

Removed from the earlier mistaken Task 9 attempt: `APP_ENV`, `REDIS_TTL` naming.

### What changed (Task 9 only)

| File | Action |
| --- | --- |
| `app/config.py` | Settings: `redis_url`, `redis_timeout`, `cache_ttl` |
| `app/redis_client.py` | Uses `settings.redis_url` + `settings.redis_timeout` |
| `app/main.py` | Cache write uses `settings.cache_ttl` |
| `docker-compose.yml` | Provides `REDIS_URL`, `REDIS_TIMEOUT`, `CACHE_TTL` |
| `tests/test_config.py` | Covers defaults, overrides, URL/timeout, `CACHE_TTL` |
| `requirements.txt` | Includes `pydantic-settings` (and test helpers) |

Tasks 1–8 behavior (API, Redis cache, fallbacks, `/health`, `/ready`) is unchanged aside from reading config through Settings.

### Code examples

**`app/config.py`:**

```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    redis_url: str = "redis://redis:6379"
    redis_timeout: float = 0.05
    cache_ttl: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

**`app/redis_client.py`:**

```python
from .config import get_settings

settings = get_settings()

redis_client = redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=settings.redis_timeout,
    socket_timeout=settings.redis_timeout,
)
```

**Cache TTL in `app/main.py`:**

```python
settings = get_settings()
await redis_client.set(
    cache_key,
    response.model_dump_json(),
    ex=settings.cache_ttl,
)
```

**`docker-compose.yml` environment:**

```yaml
app:
  environment:
    - REDIS_URL=redis://redis:6379
    - REDIS_TIMEOUT=0.05
    - CACHE_TTL=60
```

### How to verify

#### 1. Install dependency (if needed)

```powershell
pip install pydantic-settings
# or with project venv:
.\.venv\Scripts\pip install pydantic-settings==2.10.1 -q
```

#### 2. Unit tests

```powershell
.\.venv\Scripts\python -m pytest tests\test_config.py -v
```

#### 3. Override one setting locally (Task Step 4)

```powershell
$env:CACHE_TTL="120"
# then run uvicorn / rebuild container so the process sees the env
```

App should use TTL `120` instead of default `60`.

#### 4. Run via Docker Compose

```powershell
docker compose up -d --build
Invoke-RestMethod http://localhost:8000/health | ConvertTo-Json
Invoke-RestMethod http://localhost:8000/recommendations/123 | ConvertTo-Json
```

Same Docker image; configuration comes from Compose env vars.

### Clean architecture reminder

```text
config.py + application code  → same
environment variables         → change per environment
Compose / K8s                 → inject those variables
```

**Task 9 = configuration is loaded through Pydantic Settings and works through Docker Compose.**

---

==========================================================================

## Task 10 — Make the application stateless

### Topic / goal

Remove the in-process `RECOMMENDATION_STORE` dictionary so recommendation data is shared in Redis. That way multiple FastAPI replicas all see the same data (Kubernetes-ready).

### Why not keep shared data in a Python dict?

```text
Replica A memory  ≠  Replica B memory  ≠  Replica C memory
```

Each replica has its **own** memory. A change in Replica A’s dictionary is invisible to B and C.

```text
FastAPI Replica A ─┐
FastAPI Replica B ─┼──→ Redis (shared)
FastAPI Replica C ─┘
```

### Technical concepts

- **Stateless application** — request handling does not rely on local process memory for shared business data
- **Shared state externalized** — Redis holds the recommendation store (temporary; PostgreSQL comes later)
- **Separate Redis key spaces** — cache vs store must not overwrite each other:
  - Cache: `cache:recommendations:{user_id}` (full response JSON + TTL)
  - Store: `store:recommendations:{user_id}` (list JSON, no TTL)
- **Seeding** — `app/seed.py` loads users `123`, `456`, `789` into the store for development
- **Graceful degradation preserved** — unknown user / Redis failure → `POPULAR_RECOMMENDATIONS`
- **Async store API** — `await get_recommendations(user_id, redis_client)`

### Flow after Task 10

```text
Request
   ↓
Cache lookup  (cache:recommendations:{user_id})
   ↓
Cache miss / Redis cache error
   ↓
Recommendation Store (store:recommendations:{user_id} in Redis)
   ↓
Found? ── Yes → return (+ optional cache write-through)
   │
   No / Redis down
   ↓
Popular Recommendations
```

Redis is **not** the final database. Later:

```text
FastAPI
   ├── Redis → Cache
   └── PostgreSQL → Recommendation Store
```

### What changed

| File | Action |
| --- | --- |
| `app/recommendation_store.py` | Removed dict; Redis `get_recommendations` / `save_recommendations`; kept popular list |
| `app/recommender.py` | Async; passes `redis_client` into the store |
| `app/seed.py` | **Added** — seeds users 123 / 456 / 789 |
| `app/main.py` | Uses cache key prefix; `await get_recommendations(user_id, redis_client)` |
| `tests/test_recommendations.py` | **Added** — known user, unknown → popular, cache hit, shared store |
| `tests/test_config.py` | Updated for async recommender + cache key prefix |

### Code examples (new)

**Store** (`app/recommendation_store.py`):

```python
async def get_recommendations(user_id: int, redis_client: redis.Redis) -> list[int]:
    data = await redis_client.get(f"store:recommendations:{user_id}")
    if data is None:
        raise KeyError(f"No recommendations found for user {user_id}")
    return json.loads(data)


async def save_recommendations(
    user_id: int,
    recommendations: list[int],
    redis_client: redis.Redis,
) -> None:
    await redis_client.set(
        f"store:recommendations:{user_id}",
        json.dumps(recommendations),
    )
```

**Seed** (run inside Compose network):

```powershell
docker compose up -d --build
docker compose exec app python -m app.seed
```

**Endpoint call:**

```python
recommendations = await get_recommendations(user_id, redis_client)
```

### How to verify

```powershell
.\.venv\Scripts\python -m pytest tests -v
docker compose up -d --build
docker compose exec app python -m app.seed
Invoke-RestMethod http://localhost:8000/recommendations/123 | ConvertTo-Json
Invoke-RestMethod http://localhost:8000/recommendations/999 | ConvertTo-Json
```

| Call | Expected |
| --- | --- |
| `/recommendations/123` | `[10, 25, 42, 81, 99]` (from store, then cache) |
| `/recommendations/999` | `[10, 20, 30, 40, 50]` (popular) |

### Definition of done

- [x] Removed `RECOMMENDATION_STORE` Python dictionary
- [x] Recommendation store uses Redis
- [x] Added `save_recommendations()`
- [x] Seeded users `123`, `456`, `789`
- [x] API returns recommendations for those users
- [x] Unknown users receive popular recommendations
- [x] Cache behavior still works (separate key prefix + TTL)
- [x] Redis failure still falls through to popular
- [x] `pytest` passes
- [x] `docker compose up --build` works

**Task 10 = the app is stateless: shared recommendation data lives in Redis, not in replica memory.**

---

## Task 11 — Run the app on Kubernetes (beginner guide)

### What are we doing?

So far the app ran with Docker Compose.  
Now we run the **same FastAPI container** inside **Kubernetes**, with **1 copy** only.

We create two small YAML files:

| File | Simple meaning |
| --- | --- |
| `k8s/deployment.yaml` | “Please run my app container” |
| `k8s/service.yaml` | “Give my app a stable network name inside Kubernetes” |

Then we open a temporary tunnel so Windows can open the API in the browser.

### Tiny vocabulary (only what you need)

| Word | Meaning in plain English |
| --- | --- |
| **Pod** | One running copy of your container |
| **Deployment** | Kubernetes recipe that creates/keeps that Pod running |
| **Service** | A fixed address inside the cluster that points to your Pod |
| **port-forward** | A temporary bridge: your PC → Kubernetes → your app |

Picture:

```text
Your browser (localhost:8000)
        ↓  port-forward
Kubernetes Service
        ↓
FastAPI Pod (1 replica)
```

**Note:** Redis is not in Kubernetes yet. That is OK for Task 11.  
If Redis is missing, the API still returns **popular** recommendations (our fallback).

---

### Step 1 — Make sure Kubernetes is on

In Docker Desktop: **Settings → Kubernetes → Enable Kubernetes**.

Then check:

```powershell
kubectl get nodes
```

You should see one node with status `Ready`.

---

### Step 2 — Create the `k8s` folder and two files

Project layout:

```text
recommendation-service/
└── k8s/
    ├── deployment.yaml
    └── service.yaml
```

**`k8s/deployment.yaml`** (run 1 copy of the app):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: recommendation-service
spec:
  replicas: 1
  selector:
    matchLabels:
      app: recommendation-service
  template:
    metadata:
      labels:
        app: recommendation-service
    spec:
      containers:
        - name: recommendation-service
          image: recommendation-service:latest
          imagePullPolicy: Never
          ports:
            - containerPort: 8000
```

**`k8s/service.yaml`** (stable port 8000 inside the cluster):

```yaml
apiVersion: v1
kind: Service
metadata:
  name: recommendation-service
spec:
  selector:
    app: recommendation-service
  ports:
    - protocol: TCP
      port: 8000
      targetPort: 8000
```

`imagePullPolicy: Never` means: use the image we built on this machine (do not download from the internet).

---

### Step 3 — Build the Docker image

From the project root:

```powershell
docker build -t recommendation-service:latest .
```

---

### Step 4 — Tell Kubernetes to create the app

```powershell
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

Check that things exist:

```powershell
kubectl get deployments
kubectl get pods
kubectl get services
```

What “good” looks like:

- Deployment: `1/1`
- Pod: `Running`
- Service: port `8000`

---

### Step 5 — If the Pod is stuck (common on Docker Desktop)

If `kubectl get pods` shows `ErrImageNeverPull`, Kubernetes cannot see your local image yet.

Fix it once with these commands:

```powershell
docker save recommendation-service:latest -o recommendation-service.tar
docker cp recommendation-service.tar desktop-control-plane:/recommendation-service.tar
docker exec desktop-control-plane ctr -n k8s.io images import /recommendation-service.tar
kubectl delete pod -l app=recommendation-service
```

Then check again:

```powershell
kubectl get pods
```

Wait until the Pod is `Running`.

---

### Step 6 — Open the app from your PC

Kubernetes Services are internal by default.  
Use port-forward to reach the app:

```powershell
kubectl port-forward service/recommendation-service 8000:8000
```

**Keep that terminal open.**

In a **second** terminal (or browser):

```text
http://localhost:8000/docs
http://localhost:8000/health
http://localhost:8000/recommendations/123
```

Or in PowerShell:

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/recommendations/123
```

You should get JSON back.  
`/recommendations/123` may show popular items `[10, 20, 30, 40, 50]` until we add Redis to Kubernetes later.

---

### Step 7 — Done checklist

- [x] Kubernetes node is Ready
- [x] `deployment.yaml` and `service.yaml` exist
- [x] Image built
- [x] Pod is Running
- [x] Service exists
- [x] port-forward works
- [x] `/health` responds

Do **not** change `replicas` to 3 yet. That comes later.

**Task 11 in one sentence:** FastAPI runs in Kubernetes, and we can open it on `localhost:8000` with port-forward.

---

## Task 12 — Kubernetes health probes (beginner guide)

### What are we doing?

In Task 8 we already built two HTTP endpoints:

| Endpoint | Meaning |
| --- | --- |
| `GET /health` | “Is the app process alive?” (liveness) |
| `GET /ready` | “Can this app take traffic right now?” (readiness) |

In Task 12 we **tell Kubernetes to call those endpoints** automatically.

We only change **`k8s/deployment.yaml`**.  
We do **not** change **`k8s/service.yaml`**.

Why? The Service only routes traffic. The **Pod** runs the app, so probes belong on the Pod (inside the Deployment).

```text
Service.yaml     → networking only (unchanged)
Deployment.yaml  → runs Pod + probes (we edit this)
        ↓
   FastAPI Pod
     /health  ← liveness
     /ready   ← readiness
```

### Tiny vocabulary

| Word | Plain English |
| --- | --- |
| **Liveness probe** | Kubernetes checks `/health`. If it keeps failing → restart the container |
| **Readiness probe** | Kubernetes checks `/ready`. If it fails → keep Pod running, but **stop sending traffic** |
| **Running vs Ready** | Pod can be `Running` but `0/1` Ready if `/ready` fails |
| **Endpoints** | List of Ready Pod IPs the Service will send traffic to |

Remember from Task 8: Redis down does **not** make `/ready` fail, because popular fallback still works.

---

### Step 1 — Leave `service.yaml` alone

No edits. It still only does routing:

```yaml
selector:
  app: recommendation-service
ports:
  - port: 8000
    targetPort: 8000
```

---

### Step 2 — Add probes inside `deployment.yaml`

Open `k8s/deployment.yaml` and add these blocks **under the container** (same level as `ports:`):

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
```

What the numbers mean:

- `initialDelaySeconds: 5` → wait 5 seconds after start before first check
- `periodSeconds: 10` → check again every 10 seconds

Full file we use now:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: recommendation-service
spec:
  replicas: 1
  selector:
    matchLabels:
      app: recommendation-service
  template:
    metadata:
      labels:
        app: recommendation-service
    spec:
      containers:
        - name: recommendation-service
          image: recommendation-service:latest
          imagePullPolicy: Never
          ports:
            - containerPort: 8000
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /ready
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
```

---

### Step 3 — Apply the Deployment (needs your OK to run)

```powershell
kubectl apply -f k8s/deployment.yaml
kubectl rollout status deployment/recommendation-service
```

Want: `deployment "recommendation-service" successfully rolled out`

---

### Step 4 — Check the Pod is Ready

```powershell
kubectl get pods
```

Want something like:

```text
NAME                       READY   STATUS    RESTARTS
recommendation-service-…   1/1     Running   0
```

`1/1` = Ready (readiness probe is succeeding).

If you see `0/1 Running` + Unhealthy: the container is up, but a probe (usually `/ready`) is failing. Inspect before deleting anything:

```powershell
kubectl describe pod <pod-name>
kubectl logs <pod-name>
```

---

### Step 5 — Confirm probes are configured

```powershell
kubectl get pods
kubectl describe pod <pod-name>
```

Look for:

```text
Liveness:   http-get http://:8000/health
Readiness:  http-get http://:8000/ready
```

---

### Step 6 — Confirm the Service has an endpoint

```powershell
kubectl get service recommendation-service
kubectl get endpoints recommendation-service
```

Want an endpoint like `10.x.x.x:8000`.  
That means: Service found a **Ready** Pod and can send it traffic.

---

### Step 7 — Test through port-forward

```powershell
kubectl port-forward service/recommendation-service 8000:8000
```

Keep that terminal open. In another terminal:

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/ready
Invoke-RestMethod http://localhost:8000/recommendations/123
```

All should return successfully.

---

### What you should remember

| Piece | Job |
| --- | --- |
| Deployment | Creates/manages Pods |
| Service | Sends traffic only to **Ready** Pods |
| `/health` | Alive? (restart if not) |
| `/ready` | Take traffic? (remove from Service if not) |

---

### Done checklist

- [x] `service.yaml` unchanged
- [x] `livenessProbe` → `/health` added to Deployment
- [x] `readinessProbe` → `/ready` added to Deployment
- [ ] Apply Deployment + rollout succeeds *(run after you approve)*
- [ ] Pod is `1/1 Running`
- [ ] `describe pod` shows both probes
- [ ] Service endpoints show the Ready Pod
- [ ] `/health`, `/ready`, `/recommendations/123` work via port-forward

Do **not** set `replicas: 3` yet (Task 13).

**Task 12 in one sentence:** Kubernetes uses our `/health` and `/ready` endpoints to decide restarts and traffic.

---

## Task 14 — PostgreSQL persistent recommendation store

### What are we doing?

In Task 10, Redis was used for **both** cache and recommendation store. That was temporary.

Now we split responsibilities:

```text
FastAPI
   │
   ├── Redis        → fast cache only
   └── PostgreSQL   → persistent recommendation store (source of truth)
```

Flow:

```text
Request
   ↓
Redis cache
   ├── HIT  → return
   └── MISS
        ↓
     PostgreSQL
        ├── found     → return + write Redis cache
        └── not found / error → popular recommendations
```

### Technical concepts

- **Source of truth** — durable data lives in PostgreSQL, not Redis
- **Cache-aside** — read Redis first; on miss, read Postgres; then fill Redis with TTL
- **`asyncpg` pool** — async Postgres connections shared by the app
- **JSONB column** — store recommendation lists as JSON in Postgres
- **Graceful degradation** — if Postgres is down, API still returns popular items (and may still serve Redis cache hits)
- **Compose volumes** — `postgres_data` keeps DB files across restarts
- **Optional dependency status on `/ready`** — report Redis + Postgres up/down, but stay HTTP 200 ready while popular fallback exists

### What changed

| File | Action |
| --- | --- |
| `docker-compose.yml` | Postgres service + app env (`POSTGRES_*`); fixed credentials to match DB |
| `requirements.txt` | Added `asyncpg` |
| `app/config.py` | Added `postgres_host/port/db/user/password` |
| `app/database.py` | **Added** — pool + `CREATE TABLE IF NOT EXISTS` |
| `app/recommendation_store.py` | Reads/writes Postgres (no longer Redis store keys) |
| `app/recommender.py` | Passes Postgres connection |
| `app/main.py` | Lifespan init/close DB; cache → Postgres → popular; `/ready` checks Postgres |
| `app/schemas.py` | `ReadyResponse` includes `postgres` status field |
| `app/seed.py` | Seeds users into Postgres |
| `tests/*` | Updated fakes for Postgres pool/connection |

### `/ready` after Task 14

`GET /ready` now reports three dependency signals:

```json
{
  "status": "ready",
  "redis": "up",
  "postgres": "up",
  "fallback": "available"
}
```

Rules:

- Redis and Postgres are **optional** (informational only)
- If either is down → still `status: "ready"` as long as `fallback` is available
- Only missing popular fallback → `503` / `not_ready`

Example check in `main.py`:

```python
postgres_status = "up"
try:
    pool = get_pool()
    async with pool.acquire() as connection:
        await connection.fetchval("SELECT 1")
except Exception:
    postgres_status = "down"
```

### Compose shape

```yaml
services:
  redis: ...
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: recommendations
      POSTGRES_USER: recommendation_user
      POSTGRES_PASSWORD: recommendation_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
  app:
    depends_on: [redis, postgres]
    environment:
      - REDIS_URL=redis://redis:6379
      - CACHE_TTL=60
      - POSTGRES_HOST=postgres
      - POSTGRES_PORT=5432
      - POSTGRES_DB=recommendations
      - POSTGRES_USER=recommendation_user
      - POSTGRES_PASSWORD=recommendation_password

volumes:
  postgres_data:
```

### How to run / verify

```powershell
docker compose up -d --build
docker compose ps
docker compose exec app python -m app.seed

Invoke-RestMethod http://localhost:8000/recommendations/123
Invoke-RestMethod http://localhost:8000/recommendations/123   # expect Cache HIT
Invoke-RestMethod http://localhost:8000/recommendations/999   # popular
Invoke-RestMethod http://localhost:8000/ready                 # redis + postgres + fallback

# Postgres failure should not crash API (and /ready stays ready)
docker compose stop postgres
Invoke-RestMethod http://localhost:8000/recommendations/456
Invoke-RestMethod http://localhost:8000/ready                 # postgres: down, status: ready
docker compose start postgres

.\.venv\Scripts\python -m pytest tests -v
```

| Scenario | Expected |
| --- | --- |
| Known user, cold cache | Postgres HIT → `[10, 25, 42, 81, 99]` + Redis SET |
| Same user again | Cache HIT |
| Unknown user | Popular `[10, 20, 30, 40, 50]` |
| Postgres stopped | No crash → popular (unless still cached) |
| `/ready` (all up) | `redis: up`, `postgres: up`, `fallback: available` |
| `/ready` (Postgres down) | still `status: ready`, `postgres: down` |

### Done checklist

- [x] PostgreSQL in Compose
- [x] Recommendations table
- [x] Seed data in Postgres
- [x] Redis = cache only
- [x] Postgres = persistent store
- [x] Cache miss → Postgres
- [x] Postgres miss → popular
- [x] Postgres failure does not crash API
- [x] `/ready` reports Redis + Postgres + fallback (Postgres optional)
- [x] Tests updated

**Task 14 in one sentence:** Redis caches; PostgreSQL stores the real recommendations.

---

## Task 15 — Kafka event-driven architecture

### What are we doing?

Move from pure request/response toward **events**.

User behavior (view / click / purchase) is published to Kafka.  
Other systems can subscribe later without calling FastAPI directly.

```text
FastAPI  --publish-->  Kafka topic: user-interactions
                              │
                              ↓
                     Kafka Consumer
                     (group: recommendation-service)
                              │
                              ↓
                          log event
```

Stack after Task 15:

```text
FastAPI + Redis + PostgreSQL + Kafka
```

### Technical concepts

- **Event-driven architecture** — producers emit facts; consumers react asynchronously
- **Topic** — named stream of events (`user-interactions`)
- **Producer** — writes events to a topic (`app/kafka_producer.py`)
- **Consumer** — reads events from a topic (`app/kafka_consumer.py`)
- **Consumer group** — `recommendation-service` (scaling consumers later shares partitions)
- **Event schema (Pydantic)** — `UserInteractionEvent` in `app/events.py`
- **aiokafka** — async Kafka client for FastAPI
- **Dual Kafka listeners** — containers use `kafka:9092` (Compose service hostname)
- **Kafka healthcheck + `depends_on: service_healthy`** — app/consumer wait until broker is actually up
- **Consumer retry loop** — if Kafka is briefly unavailable, consumer waits and reconnects
- **Optional Kafka on `/ready`** — report `kafka: up|down` without failing readiness

### What changed

| File | Action |
| --- | --- |
| `docker-compose.yml` | Added `kafka` + `kafka-consumer` services |
| `requirements.txt` | Added `aiokafka` |
| `app/config.py` | `kafka_bootstrap_servers`, `kafka_topic`, `kafka_consumer_group` |
| `app/events.py` | **Added** — `UserInteractionEvent` |
| `app/kafka_producer.py` | **Added** — `publish_user_interaction()` |
| `app/kafka_consumer.py` | **Added** — consumer loop (logs events) |
| `app/main.py` | Starts producer on lifespan; `POST /interactions`; `/ready` includes optional `kafka` |
| `app/schemas.py` | `InteractionPublishResponse`; `ReadyResponse.kafka` |
| `tests/test_events.py` | Event schema tests |

### Event schema

```python
class UserInteractionEvent(BaseModel):
    user_id: int
    item_id: int
    event_type: str
    timestamp: str  # default UTC now
```

Example:

```json
{
  "user_id": 123,
  "item_id": 42,
  "event_type": "view",
  "timestamp": "2026-09-08T12:00:00Z"
}
```

### How to run / verify

```powershell
docker compose up -d --build
docker compose ps
```

You should see `app`, `redis`, `postgres`, `kafka`, `kafka-consumer`.

Publish an event:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/interactions `
  -ContentType "application/json" `
  -Body '{"user_id":123,"item_id":42,"event_type":"view"}'
```

Watch the consumer:

```powershell
docker logs -f recommendation-kafka-consumer
```

Expect:

```text
Received event:
user=123
item=42
type=view
```

Check readiness (Kafka optional):

```powershell
Invoke-RestMethod http://localhost:8000/ready
```

Example:

```json
{
  "status": "ready",
  "redis": "up",
  "postgres": "up",
  "kafka": "up",
  "fallback": "available"
}
```

If Kafka is down, `/ready` still returns `status: "ready"` with `"kafka": "down"`.

### Done checklist

- [x] Kafka runs in Compose (single-node KRaft)
- [x] Topic `user-interactions`
- [x] Pydantic event schema
- [x] Producer (`publish_user_interaction`)
- [x] Consumer with group `recommendation-service`
- [x] Publish via `POST /interactions`
- [x] Consumer logs the event
- [x] `/ready` reports optional Kafka status
- [x] Documented in this file

**Task 15 in one sentence:** FastAPI publishes user interactions to Kafka; a consumer group reads and logs them.

---

## Task 16 — Kafka partitions + consumer groups

### What are we doing?

Task 15 had **one topic → one consumer**.  
Task 16 makes that production-like: **partitions for parallelism**, **consumer group for coordinated scaling**.

```text
                 user-interactions
                        │
              ┌─────────┼─────────┐
              ↓         ↓         ↓
          Partition 0 Partition 1 Partition 2
              │         │         │
              ↓         ↓         ↓
          Consumer 1 Consumer 2 Consumer 3
          (same group: recommendation-service)
```

Key idea:

> **Partitions provide parallelism. Consumer groups provide coordinated consumption.**

### Technical concepts

- **Partitions** — a topic is split into N ordered logs; consumers in a group share them
- **Partition key (`user_id`)** — same user always lands in the same partition (per-user ordering)
- **Consumer group** — already `recommendation-service` from Task 15; multiple instances join the same group
- **Rebalance** — when a consumer joins/leaves, Kafka redistributes partitions automatically
- **Scale limit** — more consumers than partitions → idle consumers (no extra parallelism)
- **`kafka-init`** — one-shot Compose job that creates/alters `user-interactions` to **3 partitions**
- **Compose `--scale`** — run N consumer replicas without fixed `container_name`

### What changed

```text
recommendation-service/
├── app/
│   ├── kafka_producer.py   # CHANGED — key events by user_id; log partition + offset
│   └── kafka_consumer.py   # CHANGED — ConsumerRebalanceListener; log instance/partition/key
└── docker-compose.yml      # CHANGED
    ├── kafka               # KAFKA_NUM_PARTITIONS=3 (auto-create default)
    ├── kafka-init          # ADDED — create/alter user-interactions → 3 partitions
    ├── app                 # waits for kafka-init completed
    └── kafka-consumer      # removable container_name → docker compose --scale N
```

| File | Action |
| --- | --- |
| `docker-compose.yml` | `KAFKA_NUM_PARTITIONS=3`; added `kafka-init`; removed fixed `container_name` on `kafka-consumer` so it can scale; app/consumer wait for `kafka-init` |
| `app/kafka_producer.py` | Publish with **key = `user_id`**; log `partition` + `offset` |
| `app/kafka_consumer.py` | Rebalance listener; log instance id, partition, offset, key |
| `app/config.py` | Unchanged — `kafka_consumer_group` already set |

### Producer: partition by `user_id`

```python
key = str(event.user_id).encode("utf-8")
await producer.send_and_wait(
    settings.kafka_topic,
    value=payload,
    key=key,
)
```

Conceptually:

```text
user_id 123 → same partition (every time)
user_id 456 → (usually) another partition
```

### Consumer: same group + visible rebalance

All replicas use:

```text
group_id = recommendation-service
```

Logs look like:

```text
[edc855f21359] partitions assigned: ['user-interactions:2']
[edc855f21359] Received event: partition=2 offset=0 key=123 user=123 ...
```

### How to run / verify

**Yes — start Compose first.** Kafka must be up before topic alter, multi-consumer rebalance, or publish/consume checks.

```powershell
# Start stack with 3 consumers (one per partition ideally)
docker compose up -d --build --scale kafka-consumer=3
docker compose ps
```

You should see `app`, `redis`, `postgres`, `kafka`, `kafka-init` (exited 0), and **3** `kafka-consumer` replicas.

Verify topic partitions:

```powershell
docker exec recommendation-kafka /opt/kafka/bin/kafka-topics.sh `
  --describe --topic user-interactions --bootstrap-server localhost:9092
```

Expect:

```text
PartitionCount: 3
```

Publish events with different users:

```powershell
$users = @(123,456,789,123,456,999,111,222)
foreach ($u in $users) {
  $body = @{ user_id = $u; item_id = 42; event_type = "view" } | ConvertTo-Json
  Invoke-RestMethod -Method POST -Uri http://localhost:8000/interactions `
    -ContentType "application/json" -Body $body | Out-Null
}
```

Watch distribution:

```powershell
docker compose logs -f kafka-consumer
```

Expect:

- Events spread across consumers / partitions
- Same `user_id` always same `partition=`
- Each consumer in the group owns a subset of partitions

### Scale / failure experiments (Task 16.4–16.5)

Three consumers + three partitions (ideal):

```text
P0 → Consumer A
P1 → Consumer B
P2 → Consumer C
```

Four consumers + three partitions → one consumer idle.

Stop one consumer and watch rebalance:

```powershell
docker compose stop kafka-consumer-2
docker compose logs -f kafka-consumer
```

Kafka redistributes the dead consumer’s partitions among the remaining members — no manual remap.

### Done checklist

- [x] Topic `user-interactions` has **3 partitions** (`kafka-init` + `KAFKA_NUM_PARTITIONS`)
- [x] Producer keys events by `user_id`
- [x] Multiple consumers share group `recommendation-service`
- [x] Events distributed across consumers
- [x] Consumer failure causes rebalance (visible in logs)
- [x] Compose supports `--scale kafka-consumer=N`
- [x] Documented in this file

**Task 16 in one sentence:** The topic has 3 partitions keyed by `user_id`; consumers in `recommendation-service` share those partitions and rebalance when members change.
