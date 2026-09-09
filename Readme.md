Yes. And I recommend **not trying to implement everything at once**. We can turn everything we discussed into one small project and build it incrementally.

The concepts we covered map nicely to this progression:

1. **Basic recommendation API**
2. **Model packaging**
3. **Docker**
4. **Kubernetes**
5. **Caching with Redis**
6. **Fallback/graceful degradation**
7. **Kafka event pipeline**
8. **Feature store**
9. **Model/version management**
10. **CI/CD**
11. **Monitoring**
12. **Canary/rollback**
13. **Scaling and fault tolerance**

There are good official tutorials for the foundations: FastAPI's Docker deployment guide covers containerizing an API, while Kubernetes' official Basics tutorial walks through deploying, exposing, scaling, updating, and debugging a containerized application. ([FastAPI][1])

## Task 1 — Build a very simple Recommendation API

**Don't use Kubernetes, Kafka, Redis, ML, or anything complicated yet.**

We'll first create this:

```text
Client
   ↓
FastAPI
   ↓
Recommendation function
   ↓
JSON response
```

### Goal

Create:

```text
GET /recommendations/{user_id}
```

and return something like:

```json
{
  "user_id": 123,
  "recommendations": [
    10,
    25,
    42,
    81,
    99
  ]
}
```

### Project structure

```text
recommendation-service/
│
├── app/
│   ├── __init__.py
│   └── main.py
│
├── tests/
│   └── test_recommendations.py
│
└── requirements.txt
```

### Step 1

Create the project and install:

```bash
pip install fastapi uvicorn pytest
```

### Step 2

Create `app/main.py` with one endpoint.

Don't worry about a real recommendation model yet. Just return a hardcoded list.

### Step 3

Run it locally:

```bash
uvicorn app.main:app --reload
```

Then open:

```text
http://127.0.0.1:8000/docs
```

FastAPI provides interactive API documentation automatically. ([FastAPI][1])

### Step 4

Write **one pytest test** that verifies:

* endpoint returns HTTP `200`
* response contains `user_id`
* response contains `recommendations`

---

### That's all for Task 1.

**Do not move to Docker yet.**

Once you have this working, tell me **"Task 1 done"** and we'll do **Task 2: turn this into a proper production-style service with Pydantic schemas, separation of concerns, and tests**.

We'll build it exactly like this—**one task at a time**, and I'll explain why we're adding each piece.

[1]: https://fastapi.tiangolo.com/deployment/docker/?utm_source=chatgpt.com "FastAPI in Containers - Docker - FastAPI"


=========================================================================================


Great. **Task 2 — Make the service production-style**

Now we'll introduce the first concepts that matter for maintainability:

* **Pydantic request/response schemas**
* Separate **API layer** from recommendation logic
* Basic **error handling**
* Unit testing the recommendation logic

### Target structure

```text
recommendation-service/
│
├── app/
│   ├── main.py
│   ├── schemas.py
│   └── recommender.py
│
├── tests/
│   ├── test_api.py
│   └── test_recommender.py
│
└── requirements.txt
```

### Your task

Move the recommendation logic out of `main.py` into:

```text
app/recommender.py
```

Create a function such as:

```python
def get_recommendations(user_id: int) -> list[int]:
    ...
```

Then create Pydantic models in:

```text
app/schemas.py
```

for the API response.

Your endpoint should use those schemas rather than returning an unstructured dictionary.

Finally, write tests for **both**:

1. `get_recommendations()` directly
2. `GET /recommendations/{user_id}` through the FastAPI test client

Run:

```bash
pytest
```

### The important idea

We're establishing this separation:

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

**Don't add Redis, Docker, Kafka, ML, or Kubernetes yet.**

Once this is working, say **"Task 2 done"** and we'll move to **Task 3: Dockerize the service**.


========================================================================================

Excellent. **Task 3 — Dockerize the Recommendation Service**

Now we’ll package your FastAPI service so it can run consistently anywhere. This is the foundation for Kubernetes later.

### Goal

You should be able to run:

```bash
docker build -t recommendation-service .
docker run -p 8000:8000 recommendation-service
```

and access the same API at:

```text
http://localhost:8000/docs
```

### Step 1 — Create `Dockerfile`

At the project root:

```text
recommendation-service/
├── app/
├── tests/
├── requirements.txt
└── Dockerfile
```

Use:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Step 2 — Build the image

From the project directory:

```bash
docker build -t recommendation-service .

-- or
docker build --no-cache -t recommendation-service .
```

Check:

```bash
docker images
```

You should see your image.

### Step 3 — Run the container

```bash
docker run -p 8000:8000 recommendation-service
```

Then test:

```text
http://localhost:8000/docs
```

Your API should work exactly as it did locally.

### Step 4 — Test that the container is actually isolated

Stop your local Uvicorn server if it's running.

Then access the API **only through Docker**.

This is important because we want to verify that the application doesn't accidentally depend on your local Python environment.

### Step 5 — Add `.dockerignore`

Create:

```text
.dockerignore
```

with:

```text
__pycache__
*.pyc
.pytest_cache
.venv
venv
.git
.gitignore
tests
```

We don't need tests inside the production image for now.

---

### What you just learned

Your architecture has now become:

```text
                  Docker Container
                 ┌─────────────────┐
Client ─────────►│ FastAPI         │
                 │                 │
                 │ Recommendation  │
                 │ Logic           │
                 └─────────────────┘
```

This container will later become the **Kubernetes workload**.

**Don't add Kubernetes yet.** First make sure you can build and run this Docker image successfully.

When you're done, say **"Task 3 done"** and we'll move to **Task 4: introduce Redis caching and cache-failure fallback**.

#### Run file inside docker

```bash
docker compose exec app python -m app.seed
```


=========================================================================================

Great. **Task 4 — Add Redis caching**

Now we'll introduce an important production concept: **don't calculate/fetch recommendations every time**.

### Goal

Change the flow to:

```text
Request
   ↓
FastAPI
   ↓
Check Redis
   ↓
Cache HIT ─────────► Return recommendations
   │
   └── Cache MISS
          ↓
   Recommendation logic
          ↓
       Redis SET
          ↓
       Return results
```

### Why containers need a shared network

Redis and the FastAPI app run as **separate containers**.

- From inside the app container, `localhost` means the app container itself — **not** your Windows host, and **not** Redis.
- Containers can only talk by hostname when they share a Docker network.
- Use the Redis **container name** as the hostname, e.g. `redis://recommendation-redis:6379`.

`docker-compose` creates that shared network for you. Prefer it over manual `docker run` + `docker network create`.

---

### Quick start (future setup — copy/paste)

From the project root:


```bash
docker compose up -d --build
```

Check both containers are running:

```bash
docker ps
```

You should see:

```text
recommendation-service
recommendation-redis
```

Hit the API:

```text
http://localhost:8000/recommendations/123
```

Or open Swagger:

```text
http://localhost:8000/docs
```

Expected response:

```json
{
  "user_id": 123,
  "recommendations": [10, 25, 42, 81, 99]
}
```

Stop everything:

```bash
docker compose down
```

---


### Inital Setup Step 1 — Install the Redis Python client

Add `redis` to `requirements.txt` (already done if you followed along), then:

```bash
pip install redis
```

Because we're using FastAPI, use Redis' **async** client (`redis.asyncio`).

You do **not** need to install Redis Server on Windows — Redis runs in Docker.

If the Redis image is missing the first time, Docker will pull it automatically. Optional manual pull:

```bash
docker pull redis:7
```

---

### Step 2 — Create `docker-compose.yml`

At the project root:

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

What this gives you:

| Piece | Purpose |
| --- | --- |
| `recommendation-redis` | Redis container hostname used by the app |
| `REDIS_URL` | App connects to Redis over the compose network |
| `depends_on` | Starts Redis before the app |
| Shared default network | Containers can resolve each other by name |

Rebuild after code changes:

```bash
docker compose up -d --build
```

---

### Step 3 — Connect FastAPI to Redis

Project layout:

```text
app/
├── __init__.py
├── main.py
├── schemas.py
├── recommender.py
└── redis_client.py
```

`app/redis_client.py`:

```python
import os

import redis.asyncio as redis

REDIS_URL = os.getenv("REDIS_URL", "redis://recommendation-redis:6379")

redis_client = redis.from_url(
    REDIS_URL,
    decode_responses=True,
)
```

Notes:

- In Docker: use `redis://recommendation-redis:6379` (container name).
- Local uvicorn only (Redis still in Docker, port published): use `redis://localhost:6379`.
- Prefer `REDIS_URL` so you can switch without editing code.

---

### Step 4 — Cache recommendations in the endpoint

When `GET /recommendations/{user_id}` is called:

1. Build a cache key: `recommendations:{user_id}` (example: `recommendations:123`)
2. `GET` from Redis
3. **Cache HIT** → parse JSON and return
4. **Cache MISS** → call `get_recommendations(user_id)`
5. `SET` the result in Redis with TTL **60 seconds** (`ex=60`)
6. Return the response

Log temporarily so you can see behavior:

```text
Cache HIT
Cache MISS
```

Response shape (Pydantic):

```json
{
  "user_id": 123,
  "recommendations": [10, 25, 42, 81, 99]
}
```

---

### Step 5 — Verify cache HIT / MISS

1. Start stack: `docker compose up -d --build`
2. Call once:

```bash
curl http://localhost:8000/recommendations/123
```

3. Call again with the same `user_id`.
4. Check app logs:

```bash
docker logs recommendation-service
```

You should see:

```text
Cache MISS
Running recommendation logic...
...
Cache HIT
```

First request computes + stores. Second request is served from Redis (until TTL expires).

---

### Step 6 — Manual Docker alternative (optional)

Only if you are not using compose:

```bash
docker network create recommendation-network

docker run -d --name recommendation-redis --network recommendation-network -p 6379:6379 redis:7

docker build -t recommendation-service .

docker run -d --name recommendation-service --network recommendation-network -p 8000:8000 -e REDIS_URL=redis://recommendation-redis:6379 recommendation-service
```

Both containers **must** use the same network, and the app must use the Redis container name — not `localhost`.

---

### Step 7 — Update tests

Add tests for:

* Cache hit → recommendations come from Redis
* Cache miss → recommendation logic is called
* New recommendations → stored in Redis

For now, **don't implement cache failure handling yet**.

That's Task 5 (Redis failure + graceful degradation).

### Your architecture now

```text
             ┌─────────────┐
             │   FastAPI   │
             └──────┬──────┘
                    │
                    ▼
              ┌───────────┐
              │   Redis   │
              └─────┬─────┘
                    │
              Cache MISS
                    │
                    ▼
             Recommendation
                 Logic
```

**Task 4 is complete when Redis is working and you can demonstrate a cache HIT and MISS.**

Don't worry about Kubernetes or Kafka yet.

When you're done, say **"Task 4 done"** and we'll implement **Task 5: Redis failure + graceful degradation**.


=======================================================================================


Great. **Task 5 & 6 — Handle Redis failure gracefully**

Now we'll implement the fault-tolerance principle we discussed.

The goal is:

> **If Redis goes down, the Recommendation API should still work.**

### Current flow

```text
Request
   ↓
Redis
   ↓
Cache HIT → return
   ↓
Cache MISS
   ↓
Recommendation logic
```

But currently, if Redis itself is unavailable, your API may fail.

We want:

```text
Request
   ↓
Redis
   │
   ├── Available → use cache
   │
   └── Unavailable
          ↓
   Recommendation logic
          ↓
       Return result
```

### Your task

Modify your Redis integration so that:

1. Redis errors **do not crash the API**.
2. If Redis is unavailable, call your existing `get_recommendations()`.
3. Return the recommendations normally.
4. Don't try to save to Redis if Redis is unavailable.
5. Log that Redis is unavailable.

Use a short Redis timeout so your API doesn't wait indefinitely.

### Test it

First verify normal behavior:

```text
Redis running
     ↓
GET /recommendations/123
     ↓
200 OK
```

Then stop Redis:

```bash
docker stop recommendation-redis
```

Call your API again:

```text
GET /recommendations/123
```

You should **still get HTTP 200** and recommendations.

Then start Redis again:

```powershell
docker start recommendation-redis
```

Your normal cache behavior should return.

### Important

Don't implement circuit breakers, retries, fallback recommendation stores, or Kubernetes yet.

We're deliberately doing this in small steps.

**Task 5 = Redis can completely disappear and your API still works.**

**Task 5 = Docker compose for shared services**



When that's working, tell me **"Task 5 done"** and we'll move to **Task 6 — Docker Compose**, because now we have two services and it's time to manage them together.


             Docker Compose
                  │
          ┌───────┴───────┐
          ▼               ▼
       FastAPI           Redis


======================================================================


Great. **Task 7 — Add a fallback recommendation source**

Now we'll implement the second part of the fault-tolerance strategy we discussed:

> If **Redis is unavailable**, the service should still provide recommendations.

You've already done this by falling back to your recommendation logic. Now we'll make that fallback more realistic by introducing a separate **recommendation store**.

### Goal

Our flow becomes:

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
            ├── available ──► Return + cache
            │
            └── unavailable
                    ↓
              Popular Items
                    ↓
                  Return
```

### Step 1 — Create a recommendation store

Create:

```text
app/recommendation_store.py
```

For now, **don't introduce PostgreSQL yet**.

We'll simulate the persistent recommendation store with a Python dictionary.

The store should have a function like:

```python
get_recommendations(user_id)
```

and return recommendations for known users.

### Step 2 — Change your service flow

Your recommendation service should now follow this order:

1. Try Redis.
2. If Redis has recommendations → return them.
3. If Redis misses or fails → query the recommendation store.
4. If the store returns recommendations → optionally put them into Redis.
5. If the store fails or has no recommendations → return popular recommendations.

### Step 3 — Create a popular fallback

Create something like:

```text
POPULAR_RECOMMENDATIONS
```

This represents recommendations that are useful to **any user**, such as popular/trending content.

So even if:

```text
Redis ❌
Recommendation Store ❌
```

you still return:

```text
Popular recommendations ✅
```

### Step 4 — Test the failure scenarios

You should now be able to demonstrate:

| Redis | Recommendation Store | Result                       |
| ----- | -------------------- | ---------------------------- |
| ✅     | —                    | Cached recommendations       |
| ❌     | ✅                    | Personalized recommendations |
| ❌     | ❌                    | Popular recommendations      |

This is the **graceful degradation** pattern we discussed.

### Important

We're still deliberately keeping this simple.

Don't add:

* PostgreSQL
* Kafka
* Circuit breakers
* Kubernetes
* ML models

yet.

We're building the architecture one layer at a time.

**Task 7 is complete when your API still returns useful recommendations even after both Redis and your recommendation store are unavailable.**

When you're done, say **"Task 7 done"** and we'll move to **Task 8 — add proper health checks and dependency failure detection**, which prepares the service for Kubernetes.

========================================================================

Excellent. **Task 8 — Add health checks**

Now we'll make the service **Kubernetes-ready**.

The important distinction is between:

* **Liveness:** Is my application alive, or is it stuck/broken?
* **Readiness:** Can my application currently serve requests?

### Step 1 — Add a liveness endpoint

Add:

```text
GET /health
```

It should simply return something like:

```json
{
  "status": "ok"
}
```

This endpoint should **not depend on Redis or the recommendation store**.

### Step 2 — Add a readiness endpoint

Add:

```text
GET /ready
```

For now, check whether the application can reach its important dependencies.

Conceptually:

```text
/ready
   ↓
Can service operate?
   │
   ├── Yes → 200
   │
   └── No → 503
```

Since your service has graceful fallbacks, **don't automatically mark the entire service unavailable just because Redis is down**. Redis is an optional dependency because you already designed the service to function without it.

So think carefully about what your service *actually requires* to serve a reasonable response.

### Step 3 — Test them

With everything running:

```text
GET /health → 200
GET /ready  → 200
```

Stop Redis:

```powershell
docker stop recommendation-redis
```

Then test again.

Your:

```text
/health → 200
```

should remain healthy.

Your `/ready` behavior should reflect whether the service can still serve requests using its fallback path.

### Why we're doing this

Later Kubernetes will use these endpoints:

```text
Kubernetes
    │
    ├── Liveness probe
    │      ↓
    │   /health
    │
    └── Readiness probe
           ↓
         /ready
```

If a container becomes genuinely unhealthy, Kubernetes can restart it. If it's temporarily unable to serve traffic, Kubernetes can remove it from the load balancer without necessarily restarting it.

**Task 8 = implement and test `/health` and `/ready`.**

Once done, say **"Task 8 done"** and we'll move to **Task 9 — add proper configuration management with environment variables**, which we'll need before Kubernetes.


=======================================================================


Exactly. And that detail matters: you already have **Docker Compose + FastAPI + Redis + graceful degradation + recommendation-store fallback**, so we should use that setup to make the readiness behavior realistic rather than just returning a hardcoded `"ready"`.

Great. **Task 9 — Configuration Management**

Now we'll make the service configurable without changing the code.

### Goal

Move things like:

* Redis URL
* Redis timeout
* Cache TTL

out of your Python code and into **environment variables**.

For example:

```text
REDIS_URL=redis://redis:6379
REDIS_TIMEOUT=0.05
CACHE_TTL=60
```

### Step 1 — Create configuration module

Create:

```text
app/config.py
```

Use **Pydantic Settings** to load configuration from environment variables.

You'll need:

```bash
pip install pydantic-settings
```

### Step 2 — Define your settings

Create settings for:

```text
REDIS_URL
REDIS_TIMEOUT
CACHE_TTL
```

Give them sensible development defaults.

The important idea is that your application code should do something like:

```text
settings.redis_url
settings.cache_ttl
```

rather than:

```python
"redis://localhost:6379"
```

or hardcoded TTL values throughout the code.

### Step 3 — Use the settings

Update your Redis client and recommendation service to use the configuration object.

Your architecture becomes:

```text
Environment Variables
        ↓
     Settings
        ↓
Application
        ↓
Redis / Recommendation Service
```

### Step 4 — Test locally

Run your application with your normal environment.

Then override one setting temporarily, for example:

```powershell
$env:CACHE_TTL="120"
```

Start the application and verify it uses `120` instead of the default.

### Step 5 — Update Docker Compose

Instead of hardcoding configuration inside Python, Compose should provide the configuration:

```yaml
environment:
  - REDIS_URL=redis://redis:6379
  - REDIS_TIMEOUT=0.05
  - CACHE_TTL=60
```

Now the **same Docker image** can run with different configurations in development, staging, and production.

### Key principle

> **Configuration belongs outside the application code.**

This becomes particularly important with Kubernetes, where we'll eventually use **ConfigMaps and Secrets**.

**Task 9 = configuration is loaded through Pydantic Settings and works through Docker Compose.**

Once done, tell me **"Task 9 done"**. Then we'll move to **Task 10 — prepare the application for Kubernetes**.


=========================================================================


Great. **Task 9 — Configuration Management is done.** ✅

## Task 10 — Prepare the App for Kubernetes

Before actually writing Kubernetes manifests, we’ll make one small production-oriented change:

### Goal

Make sure the FastAPI container can be safely run as **multiple replicas**.

For example:

```text
                ┌── FastAPI instance 1
Client ── K8s ──┼── FastAPI instance 2
                └── FastAPI instance 3
                         │
                         └── Redis
```

The important requirement is:

> **FastAPI instances should be stateless.**

Your recommendation data should **not depend on a Python dictionary inside one particular container**, because another replica won't have that data.

### Your Task 10

Look at your current:

```text
app/recommendation_store.py
```

You currently have the simulated recommendation store using a Python dictionary.

**Don't replace it with PostgreSQL yet.**

Instead, answer this question in your own words:

> If Kubernetes runs 3 replicas of our FastAPI application, what problem could a Python dictionary inside `recommendation_store.py` cause?

Just answer that first. **Don't write code yet.**

This is intentional—we're going to understand the problem before solving it.


No problem — that's exactly what we're learning. 🙂

The problem is **each FastAPI container has its own separate Python memory**.

Imagine Kubernetes starts 3 replicas:

```text
Replica 1 → Python dictionary A
Replica 2 → Python dictionary B
Replica 3 → Python dictionary C
```

If a recommendation is stored in **Replica 1's dictionary**, Replica 2 doesn't know about it.

So:

```text
Request 1 → Replica 1 → stores data
Request 2 → Replica 2 → can't see that data
```

That's why production applications keep shared/persistent data in something external, such as **Redis or PostgreSQL**, rather than an in-memory Python dictionary.

### Your Task 10

Now that you know the problem, tell me:

**Why shouldn't we keep important shared data in a Python dictionary when running multiple replicas?**


Exactly. ✅

More precisely:

> **Each replica has its own memory, so changes made to Replica A's dictionary are not visible to Replica B or C.**

That's the key concept.


# Task 10 — Make the Application Stateless

### Goal

Prepare the application so it can eventually run with **multiple Kubernetes replicas**.

The problem with the current code is:

```python
RECOMMENDATION_STORE = {
    123: [10, 25, 42, 81, 99],
    ...
}
```

This data lives inside the memory of one FastAPI container.

Instead, for Task 10 we'll make the application **stateless** by moving the recommendation-store responsibility to Redis.

> Redis is currently serving as our cache. For this task, we'll also use it as a temporary shared recommendation store. Later, Task 14 will replace this with PostgreSQL as the persistent store.

---

## 1. Change `recommendation_store.py`

Remove the Python dictionary.

Your file should become something along these lines:

```python
import json

import redis.asyncio as redis

from app.config import settings


async def get_recommendations(
    user_id: int,
    redis_client: redis.Redis,
) -> list[int]:
    key = f"recommendations:{user_id}"

    data = await redis_client.get(key)

    if data is None:
        raise KeyError(f"No recommendations found for user {user_id}")

    return json.loads(data)


async def save_recommendations(
    user_id: int,
    recommendations: list[int],
    redis_client: redis.Redis,
) -> None:
    key = f"recommendations:{user_id}"

    await redis_client.set(
        key,
        json.dumps(recommendations),
    )
```

### Why?

Now:

```text
FastAPI Replica A ─┐
FastAPI Replica B ─┼──→ Redis
FastAPI Replica C ─┘
```

All replicas access the **same recommendation data**.

---

# 2. Add some initial recommendation data

We need a way to put our existing test data into Redis.

For development, you can create:

```text
app/seed.py
```

with:

```python
import asyncio
import json

import redis.asyncio as redis

from app.config import settings


RECOMMENDATIONS = {
    123: [10, 25, 42, 81, 99],
    456: [12, 33, 47, 58, 72],
    789: [5, 18, 29, 61, 94],
}


async def main():
    client = redis.from_url(settings.redis_url)

    for user_id, recommendations in RECOMMENDATIONS.items():
        await client.set(
            f"recommendations:{user_id}",
            json.dumps(recommendations),
        )

    await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
```

Run it from your project directory:

```powershell
python -m app.seed
```

---

# 3. Update your recommendation service

Your existing recommendation flow currently looks approximately like:

```text
Request
   ↓
Redis Cache
   ↓
Recommendation Store
   ↓
Popular Recommendations
```

Now the **Recommendation Store** is also backed by shared Redis.

So conceptually:

```text
Request
   ↓
Cache lookup
   ↓
Cache miss
   ↓
Recommendation Store (Redis)
   ↓
Found? ── Yes → return
   │
   No
   ↓
Popular Recommendations
```

Update the place where you currently call:

```python
get_recommendations(user_id)
```

so it passes your Redis client:

```python
await get_recommendations(user_id, redis_client)
```

---

# 4. Keep the popular fallback

Keep:

```python
POPULAR_RECOMMENDATIONS = [10, 20, 30, 40, 50]
```

If the recommendation store doesn't contain the user, your service should still return:

```text
[10, 20, 30, 40, 50]
```

instead of crashing.

This preserves the graceful-degradation behavior we built earlier.

---

# 5. Important distinction

After this task, we have:

```text
                   ┌── Cache
                   │
FastAPI ───────── Redis
                   │
                   └── Recommendation Store
```

But **Redis is not our final persistent database**.

That's intentional.

Later:

```text
FastAPI
   │
   ├── Redis → Cache
   │
   └── PostgreSQL → Recommendation Store
```

PostgreSQL will become the durable source of truth.

---

# 6. Update your tests

You should update/add tests for these cases:

### Case 1 — User exists

User `123` should return:

```python
[10, 25, 42, 81, 99]
```

### Case 2 — User doesn't exist

An unknown user should eventually get:

```python
[10, 20, 30, 40, 50]
```

### Case 3 — Multiple replicas conceptually

The important architectural property is:

```text
Replica A → Redis ← Replica B
```

Both should see the same recommendation data.

---

# Task 10 Definition of Done

Don't move to Task 11 until all of these work:

* [ ] Removed `RECOMMENDATION_STORE` Python dictionary.
* [ ] Recommendation store uses Redis.
* [ ] Added `save_recommendations()`.
* [ ] Seeded users `123`, `456`, and `789`.
* [ ] API still returns recommendations for those users.
* [ ] Unknown users receive popular recommendations.
* [ ] Existing Redis cache behavior still works.
* [ ] Redis failure still follows our graceful-degradation behavior.
* [ ] `pytest` passes.
* [ ] `docker compose up --build` works.

### One important learning point

The purpose of Task 10 isn't really "use Redis again."

It's this:

> **A Kubernetes replica should not depend on local application memory for shared state.**

Once you've implemented and tested everything above, tell me **"Task 10 done"**, and we'll move to **Task 11 — Kubernetes Deployment + Service**.


============================================================




Excellent. ✅ **Task 10 is complete.**

You now have:

```text
FastAPI
   │
   ├── Redis → Cache
   │
   └── Redis → Temporary shared recommendation store
```

And importantly, your application is no longer dependent on a local Python dictionary, so multiple replicas can share the same data.

# Task 11 — Kubernetes Deployment + Service

Now we're going to actually run your FastAPI application in **Kubernetes**.

### Goal

Create two Kubernetes resources:

1. **Deployment** — runs your FastAPI container.
2. **Service** — gives the application a stable internal network endpoint.

The architecture will become:

```text
                    Kubernetes
                        │
                 ┌──────┴──────┐
                 │   Service    │
                 └──────┬──────┘
                        │
              ┌─────────┼─────────┐
              ↓         ↓         ↓
           FastAPI   FastAPI   FastAPI
           Replica   Replica   Replica
```

For now, we'll start with **1 replica**. Scaling comes later.

---

## Step 1 — Check Kubernetes

If you're using Docker Desktop:

Go to:

**Docker Desktop → Settings → Kubernetes**

Enable Kubernetes and wait until it says it's running.

Then run:

```powershell
kubectl version --client
```

and:

```powershell
kubectl get nodes
```

You should see your Kubernetes node.

---

## Step 2 — Create a Kubernetes directory

Inside your project:

```text
recommendation-service/
│
├── app/
├── tests/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
│
└── k8s/
```

Create:

```text
k8s/deployment.yaml
```

---

## Step 3 — Create the Deployment

Put this in `deployment.yaml`:

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

          ports:
            - containerPort: 8000
```

### Understand the important parts

```yaml
replicas: 1
```

means Kubernetes runs one application container.

Later we'll change it to:

```yaml
replicas: 3
```

and Kubernetes will run three.

---

## Step 4 — Build the Docker image

Kubernetes needs access to your image.

Build your image:

```powershell
docker build -t recommendation-service:latest .
```

Because you're using Docker Desktop's Kubernetes, the local Docker image should be available to the cluster.

---

## Step 5 — Deploy it

Run:

```powershell
kubectl apply -f k8s/deployment.yaml
```

Then:

```powershell
kubectl get deployments
```

You should see something like:

```text
NAME                     READY   UP-TO-DATE   AVAILABLE
recommendation-service   1/1     1            1
```

Then:

```powershell
kubectl get pods
```

You should see:

```text
recommendation-service-xxxxx   1/1   Running
```

---

# Step 6 — Create the Kubernetes Service

Create:

```text
k8s/service.yaml
```

Put:

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

Apply it:

```powershell
kubectl apply -f k8s/service.yaml
```

Check:

```powershell
kubectl get services
```

You should see:

```text
recommendation-service   ClusterIP   ...   8000/TCP
```

---

# Step 7 — Access your application

The Service is currently `ClusterIP`, meaning it's accessible **inside Kubernetes**, not directly from your Windows host.

For testing, use:

```powershell
kubectl port-forward service/recommendation-service 8000:8000
```

Keep that terminal running.

Then open:

```text
http://localhost:8000/docs
```

or test your endpoint:

```text
http://localhost:8000/recommendations/123
```

You should get your recommendations.

---

## Step 8 — Check the architecture

At this point:

```text
             localhost:8000
                    │
                    ↓
          Kubernetes Service
                    │
                    ↓
       recommendation-service
             Deployment
                    │
                    ↓
             FastAPI Pod
                    │
                    ↓
                  Redis
```

**One complication:** your current Kubernetes Deployment doesn't provide Redis yet. That's intentional—we'll handle Kubernetes configuration and dependencies properly in the next steps rather than mixing everything together.

### Task 11 — Done when:

* [ ] Kubernetes is running.
* [ ] `kubectl get nodes` works.
* [ ] `deployment.yaml` created.
* [ ] Docker image built.
* [ ] Deployment successfully created.
* [ ] FastAPI Pod is `Running`.
* [ ] `service.yaml` created.
* [ ] Kubernetes Service is created.
* [ ] `kubectl port-forward` works.
* [ ] `/docs` or your recommendations endpoint responds.

**Don't change to 3 replicas yet.** That's Task 13.

When all of this works, tell me **Task 11 done**.


=====================================================

Absolutely. Let's **reset Task 12** and do it properly, considering that we have **both `deployment.yaml` and `service.yaml`**, and that you already have `/health` and `/ready` from Task 8.

# Task 12 — Kubernetes Health Probes

### Goal

Teach Kubernetes how to determine:

1. **Is the FastAPI container alive?** → Liveness
2. **Is the FastAPI container ready to receive traffic?** → Readiness

Our architecture is now:

```text
                    Kubernetes
                        │
                        ↓
                 Service.yaml
                        │
                        ↓
                Deployment.yaml
                        │
              ┌─────────┴─────────┐
              ↓                   ↓
         FastAPI Pod          FastAPI Pod
              │
       ┌──────┴──────┐
       ↓             ↓
   /health        /ready
   liveness       readiness
```

---

## Step 1 — Don't change `service.yaml`

Your existing:

```text
k8s/service.yaml
```

should remain responsible for **network routing**.

Something like:

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

We **do not put liveness/readiness probes here**.

Why?

Because the Service doesn't run your application. The **Pod** does.

The Service simply routes traffic to Pods matching:

```yaml
selector:
  app: recommendation-service
```

---

# Step 2 — Modify `deployment.yaml`

Open:

```text
k8s/deployment.yaml
```

You should have something approximately like:

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

          ports:
            - containerPort: 8000
```

Now add the probes **inside the container**:

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

So the complete Deployment should look like:

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

# Step 3 — Apply the Deployment

Run:

```powershell
kubectl apply -f k8s/deployment.yaml
```

Then:

```powershell
kubectl rollout status deployment/recommendation-service
```

You want:

```text
deployment "recommendation-service" successfully rolled out
```

---

# Step 4 — Check the Pods

Run:

```powershell
kubectl get pods
```

You should eventually see:

```text
NAME                                      READY   STATUS    RESTARTS
recommendation-service-xxxxx              1/1     Running   0
```

The important part is:

```text
1/1
```

That means the Pod is considered **Ready**.

---

# Step 5 — Verify the probes

Run:

```powershell
kubectl describe pod <pod-name>
```

For example:

```powershell
kubectl describe pod recommendation-service-xxxxx
```

Look under the container information.

You should find:

```text
Liveness:   http-get http://:8000/health
Readiness:  http-get http://:8000/ready
```

You may also see events such as:

```text
Liveness probe succeeded
Readiness probe succeeded
```

---

# Step 6 — Understand the `Unhealthy` situation you encountered

You previously saw:

```text
recommendation-service-5c6c9695c5-hdt9h   0/1   Running
```

and `kubectl describe pod` showed `Unhealthy`.

**That is not necessarily a Kubernetes problem.**

It means Kubernetes is performing the probe and the probe is failing.

For example:

```text
/ready → HTTP 500
```

would cause:

```text
READY = 0/1
```

while the container could still be:

```text
STATUS = Running
```

That's an important distinction:

```text
Running ≠ Ready
```

A container can be running while Kubernetes refuses to send it traffic.

If you encounter `Unhealthy` again during this task, **don't immediately delete the Pod or change random settings**. We'll inspect the probe failure.

---

# Step 7 — Check your Service

After the Pod becomes ready:

```powershell
kubectl get service recommendation-service
```

Then:

```powershell
kubectl get endpoints recommendation-service
```

You should see an endpoint similar to:

```text
NAME                    ENDPOINTS
recommendation-service  10.x.x.x:8000
```

This is useful because it demonstrates the relationship:

```text
Service
   │
   ├── finds Pods using selector
   │
   └── only sends traffic to Ready Pods
```

---

# Step 8 — Test through the Service

If your port-forward is no longer running, run:

```powershell
docker build -t recommendation-service:latest .
kubectl rollout restart deployment recommendation-service
kubectl get pods
kubectl port-forward service/recommendation-service 8000:8000
```

Then test:

```text
http://localhost:8000/health
```

and:

```text
http://localhost:8000/ready
```

You should get successful responses.

Also test:

```text
http://localhost:8000/recommendations/123
```

---

# What you should understand after Task 12

### Deployment

Controls your application Pods:

```text
Deployment
    ↓
Pod
    ↓
FastAPI
```

### Service

Provides stable networking:

```text
Service
    ↓
Ready Pods
```

### Liveness

Answers:

> "Is this application/container alive?"

If it repeatedly fails, Kubernetes can restart the container.

### Readiness

Answers:

> "Should this Pod receive traffic right now?"

If it fails, Kubernetes can keep the Pod running but remove it from Service traffic.

---

## Task 12 checklist

* [ ] Keep `service.yaml` unchanged.
* [ ] Add `livenessProbe` to `deployment.yaml`.
* [ ] Liveness uses `/health`.
* [ ] Add `readinessProbe` to `deployment.yaml`.
* [ ] Readiness uses `/ready`.
* [ ] Apply Deployment.
* [ ] `rollout status` succeeds.
* [ ] Pod becomes `1/1 Running`.
* [ ] `kubectl describe pod` shows both probes.
* [ ] Service still exists.
* [ ] `kubectl get endpoints recommendation-service` shows the ready Pod.
* [ ] `/health`, `/ready`, and `/recommendations/123` work through the Service.

**Don't change `replicas` to 3 yet.** We'll specifically learn Kubernetes scaling in **Task 13**.

When all of this works, tell me **Task 12 done**.


===========================================================

Absolutely. Since you want **Tasks 13, 14, and 15 all at once**, I'll give you the complete roadmap and implementation steps, but keep each task independently testable.

We currently have:

```text
Task 10 → Stateless application                    ✅
Task 11 → Kubernetes Deployment + Service          ✅
Task 12 → Kubernetes health probes                 ✅
```

Now:

```text
Task 13 → Kubernetes Scaling
Task 14 → PostgreSQL as persistent recommendation store
Task 15 → Kafka event-driven architecture
```

---

# Task 13 — Kubernetes Scaling

### Goal

Run multiple FastAPI replicas and understand how Kubernetes distributes traffic.

Current:

```text
Service
   │
   ↓
FastAPI Pod
```

After Task 13:

```text
                 Service
                    │
          ┌─────────┼─────────┐
          ↓         ↓         ↓
        Pod 1     Pod 2     Pod 3
```

## Step 13.1 — Change replicas

Open:

```text
k8s/deployment.yaml
```

Change:

```yaml
replicas: 1
```

to:

```yaml
replicas: 3
```

Don't change anything else yet.

---

## Step 13.2 — Apply

```powershell
kubectl apply -f k8s/deployment.yaml
```

Then:

```powershell
kubectl get pods
```

You should eventually see:

```text
recommendation-service-xxxxx   1/1   Running
recommendation-service-yyyyy   1/1   Running
recommendation-service-zzzzz   1/1   Running
```

---

## Step 13.3 — Check Deployment

```powershell
kubectl get deployment recommendation-service
```

You want:

```text
READY   UP-TO-DATE   AVAILABLE
3/3     3            3
```

---

## Step 13.4 — Check the Service

Run:

```powershell
kubectl get endpoints recommendation-service
```

You should see **three Pod IPs**.

This demonstrates:

```text
Service
   │
   ├── Pod 1
   ├── Pod 2
   └── Pod 3
```

The Service provides a stable endpoint while Kubernetes manages the individual Pods.

---

## Step 13.5 — Test

Your existing:

```powershell
kubectl port-forward service/recommendation-service 8000:8000
```

should still work.

Test:

```text
/recommendations/123
```

The important learning here is:

> The client doesn't need to know which Pod handles the request.

---

## Step 13.6 — Test failure

This is an important part.

Get the Pods:

```powershell
kubectl get pods
```

Delete one:

```powershell
kubectl delete pod <pod-name>
```

Immediately check:

```powershell
kubectl get pods
```

You should see Kubernetes create a replacement.

Something like:

```text
Pod 1 → Running
Pod 2 → Running
Pod 3 → deleted

Kubernetes
     ↓
creates Pod 4
```

This demonstrates the **self-healing behavior of a Deployment**.

### Task 13 complete when:

* [ ] 3 replicas running
* [ ] Service has 3 endpoints
* [ ] API still works
* [ ] Deleting one Pod causes Kubernetes to create a replacement

---

=====================================================================

# Task 14 — PostgreSQL Persistent Recommendation Store

Now we're going to fix something temporary from Task 10.

Currently:

```text
Redis
 ├── Cache
 └── Recommendation Store
```

That's not how we ultimately want the architecture.

Redis should primarily be our **fast cache**.

PostgreSQL becomes our **persistent source of truth**:

```text
                    FastAPI
                       │
             ┌─────────┴─────────┐
             ↓                   ↓
           Redis             PostgreSQL
           Cache             Persistent Store
```

---

## Step 14.1 — Add PostgreSQL to Docker Compose

Open:

```text
docker-compose.yml
```

Add:

```yaml
postgres:
  image: postgres:16
  environment:
    POSTGRES_DB: recommendations
    POSTGRES_USER: recommendation_user
    POSTGRES_PASSWORD: recommendation_password
  ports:
    - "5432:5432"
  volumes:
    - postgres_data:/var/lib/postgresql/data
```

At the bottom of your Compose file add:

```yaml
volumes:
  postgres_data:
```

So conceptually:

```text
services:
  redis:
    ...

  postgres:
    ...

  app:
    ...

volumes:
  postgres_data:
```

---

## Step 14.2 — Add PostgreSQL dependency

Add:

```text
asyncpg
```

to `requirements.txt`.

Then rebuild:

```powershell
docker compose up --build
```

Check:

```powershell
docker compose ps
```

You should have:

```text
app        running
redis      running
postgres   running
```

---

## Step 14.3 — Add database configuration

Your existing `app/config.py` should now have PostgreSQL configuration.

For example:

```python
POSTGRES_HOST: str = "postgres"
POSTGRES_PORT: int = 5432
POSTGRES_DB: str = "recommendations"
POSTGRES_USER: str = "recommendation_user"
POSTGRES_PASSWORD: str = "recommendation_password"
```

However, because you already completed Task 9, **don't hardcode production credentials if your existing settings pattern supports environment variables**.

Prefer:

```text
POSTGRES_HOST
POSTGRES_PORT
POSTGRES_DB
POSTGRES_USER
POSTGRES_PASSWORD
```

as environment variables.

---

## Step 14.4 — Create the recommendation table

Create:

```text
app/database.py
```

For this learning task, use a simple connection pool with `asyncpg`.

Then create a table:

```sql
CREATE TABLE recommendations (
    user_id BIGINT PRIMARY KEY,
    recommendations JSONB NOT NULL
);
```

We deliberately keep the schema simple.

Example:

```text
user_id | recommendations
--------+-----------------------
123     | [10,25,42,81,99]
456     | [12,33,47,58,72]
789     | [5,18,29,61,94]
```

---

## Step 14.5 — Move Recommendation Store to PostgreSQL

Your architecture should now become:

```text
Request
   │
   ↓
Redis
   │
   ├── HIT ─────────────→ return
   │
   └── MISS
        │
        ↓
    PostgreSQL
        │
        ├── found → return + cache in Redis
        │
        └── not found → popular recommendations
```

Your `recommendation_store.py` should now use PostgreSQL rather than Redis.

For example, conceptually:

```python
async def get_recommendations(user_id: int, connection):
    ...
```

and:

```python
async def save_recommendations(user_id: int, recommendations, connection):
    ...
```

Don't put PostgreSQL connection logic directly into your FastAPI route.

Keep the separation:

```text
main.py
   ↓
recommendation service
   ↓
recommendation_store.py
   ↓
PostgreSQL
```

---

## Step 14.6 — Seed PostgreSQL

Move your existing data:

```python
123 → [10, 25, 42, 81, 99]
456 → [12, 33, 47, 58, 72]
789 → [5, 18, 29, 61, 94]
```

into PostgreSQL.

You can create a small seed script similar to Task 10.

---

## Step 14.7 — Test PostgreSQL

Test:

### User exists

```text
/recommendations/123
```

should return:

```text
[10, 25, 42, 81, 99]
```

### Redis cache hit

First request:

```text
Redis MISS
    ↓
PostgreSQL
    ↓
Redis SET
```

Second request:

```text
Redis HIT
    ↓
return
```

### Unknown user

```text
Redis MISS
    ↓
PostgreSQL MISS
    ↓
Popular recommendations
```

---

## Step 14.8 — Test PostgreSQL failure

This is important because we previously built graceful degradation.

Stop PostgreSQL:

```powershell
docker compose stop postgres
```

Then request recommendations.

Your application should **not crash**.

The fallback should eventually be:

```text
Redis
 ↓
PostgreSQL unavailable
 ↓
Popular recommendations
```

Depending on whether the recommendation is still cached, you may get the cached result first.

Restart:

```powershell
docker compose start postgres
```

### Task 14 complete when:

* [ ] PostgreSQL runs through Compose
* [ ] Recommendation table created
* [ ] Recommendation data stored in PostgreSQL
* [ ] Redis is used as cache
* [ ] PostgreSQL is the persistent store
* [ ] Cache miss reaches PostgreSQL
* [ ] PostgreSQL miss reaches popular fallback
* [ ] PostgreSQL failure doesn't crash API
* [ ] Tests pass

---



=========================================================================


# Task 15 — Kafka Event-Driven Architecture

Now we're moving from **request/response architecture** toward an event-driven system.

Currently:

```text
User
 ↓
FastAPI
 ↓
Recommendation
```

But a real recommendation platform has events such as:

```text
user viewed item
user clicked item
user purchased item
user liked item
user searched
```

We don't want every downstream system tightly coupled to the FastAPI request.

Instead:

```text
                    Kafka
                      │
        ┌─────────────┼─────────────┐
        ↓             ↓             ↓
 Recommendation   Analytics    Feature Pipeline
   Consumer        Consumer        Consumer
```

---

## Step 15.1 — Add Kafka to Docker Compose

Add Kafka using a current Kafka image/configuration appropriate for your local environment.

For this task, use a **single-node Kafka setup**.

The important thing is that your Compose stack becomes:

```text
FastAPI
Redis
PostgreSQL
Kafka
```

Don't worry about Kafka clustering yet.

We're learning the concept first.

---

## Step 15.2 — Create an event schema

Create:

```text
app/events.py
```

Define a simple event:

```python
from pydantic import BaseModel


class UserInteractionEvent(BaseModel):
    user_id: int
    item_id: int
    event_type: str
    timestamp: str
```

Example event:

```json
{
  "user_id": 123,
  "item_id": 42,
  "event_type": "view",
  "timestamp": "2026-09-08T12:00:00Z"
}
```

---

## Step 15.3 — Create a Kafka topic

Create:

```text
user-interactions
```

Think of the topic as the stream of user behavior events:

```text
user-interactions
│
├── event 1
├── event 2
├── event 3
├── event 4
└── ...
```

---

## Step 15.4 — Create a producer

Create:

```text
app/kafka_producer.py
```

Its job:

```text
FastAPI
   ↓
Kafka Producer
   ↓
user-interactions topic
```

When a user interaction occurs, publish:

```json
{
  "user_id": 123,
  "item_id": 42,
  "event_type": "view",
  "timestamp": "..."
}
```

For this first implementation, don't integrate it into every endpoint.

Create a simple function:

```python
async def publish_user_interaction(event):
    ...
```

---

## Step 15.5 — Create a consumer

Create:

```text
app/kafka_consumer.py
```

The consumer reads:

```text
user-interactions
       ↓
Kafka Consumer
       ↓
process event
```

For now, simply log:

```text
Received event:
user=123
item=42
type=view
```

Don't build feature stores or ML pipelines yet.

---

## Step 15.6 — Use a consumer group

Give the consumer group a name such as:

```text
recommendation-service
```

Conceptually:

```text
Topic: user-interactions

Consumer Group:
recommendation-service

        ┌── Consumer 1
Kafka ──┼── Consumer 2
        └── Consumer 3
```

This becomes important when we later scale consumers.

---

## Step 15.7 — Test the flow

The final flow for Task 15:

```text
FastAPI
   │
   │ publish
   ↓
Kafka
   │
   │ consume
   ↓
Kafka Consumer
   │
   ↓
log event
```

Send an interaction and verify that the consumer receives it.

---

# Task 15 Definition of Done

* [ ] Kafka runs locally.
* [ ] `user-interactions` topic exists.
* [ ] Pydantic event schema exists.
* [ ] Kafka producer exists.
* [ ] Kafka consumer exists.
* [ ] Consumer group configured.
* [ ] Producer can publish an event.
* [ ] Consumer receives the event.
* [ ] Consumer logs/processes the event.

---

# Where we're going

After Tasks 13–15, your architecture will have evolved significantly:

```text
                         Kubernetes
                             │
                       ┌─────┴─────┐
                       │  Service   │
                       └─────┬─────┘
                             │
                 ┌───────────┼───────────┐
                 ↓           ↓           ↓
              FastAPI     FastAPI     FastAPI
                 │           │           │
                 └───────────┼───────────┘
                             │
             ┌───────────────┼────────────────┐
             ↓               ↓                ↓
           Redis         PostgreSQL         Kafka
          (Cache)        (Source of        (Events)
                           Truth)
```

Then we'll move into the more interesting distributed-system pieces:

```text
16 → Kafka partitions + consumer groups
17 → Schema Registry + schema evolution
18 → Feature Store
19 → Model serving + model versioning
20 → CI/CD
21 → Observability
22 → Model monitoring/drift
23 → Canary/Blue-Green + rollback
24 → Load testing
25 → Final production architecture
```

Final command to test  if it is working
```bash
docker compose up -d --build
Invoke-RestMethod -Method Post -Uri http://localhost:8000/interactions `
  -ContentType "application/json" `
  -Body '{"user_id":123,"item_id":42,"event_type":"view"}'
docker logs -f recommendation-kafka-consumer
```


===================================================================

YET TO DO

Yes. Since you want to **learn Kubernetes later**, we'll leave that aside for now and continue with the application architecture.

You completed:

```text
13 → Kubernetes scaling        ✅
14 → PostgreSQL store         ✅
15 → Kafka producer/consumer   ✅
```

Now we'll build the next three concepts:

```text
16 → Kafka partitions + consumer groups
17 → Schema Registry + schema evolution
18 → Feature Store
```

I'll keep each task independent and give you the **complete task at once**.

---

# Task 16 — Kafka Partitions + Consumer Groups

## Goal

Understand how Kafka scales event processing.

Currently you have:

```text
user-interactions
        │
        ↓
   Kafka Consumer
```

We want:

```text
                 user-interactions
                        │
              ┌─────────┼─────────┐
              ↓         ↓         ↓
          Partition 0 Partition 1 Partition 2
              │         │         │
              ↓         ↓         ↓
          Consumer 1 Consumer 2 Consumer 3
```

The key concept:

> **Partitions provide parallelism. Consumer groups provide coordinated consumption.**

---

## Step 16.1 — Create 3 partitions

Check your existing topic:

```powershell
docker exec -it <kafka-container> kafka-topics.sh --describe --topic user-interactions --bootstrap-server localhost:9092
```

You want to configure the topic with **3 partitions**.

If you're recreating it, create it with:

```powershell
docker exec -it <kafka-container> kafka-topics.sh --create --topic user-interactions --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1
```

If it already exists, increase its partitions:

```powershell
docker exec -it <kafka-container> kafka-topics.sh --alter --topic user-interactions --bootstrap-server localhost:9092 --partitions 3
```

Then verify:

```powershell
docker exec -it <kafka-container> kafka-topics.sh --describe --topic user-interactions --bootstrap-server localhost:9092
```

You should see:

```text
PartitionCount: 3
```

---

## Step 16.2 — Understand partitioning

Send events with different users:

```text
user 123
user 456
user 789
user 123
user 456
```

Kafka can distribute them across partitions.

For recommendation systems, a good partition key is usually:

```text
user_id
```

Conceptually:

```text
user_id 123 → same partition
user_id 123 → same partition
user_id 123 → same partition
```

This is useful because events for the same user maintain ordering within that partition.

---

## Step 16.3 — Run two consumers

Start your consumer twice.

For example:

```powershell
python -m app.kafka_consumer
```

Open another terminal and run:

```powershell
python -m app.kafka_consumer
```

Both should use the same:

```text
recommendation-service
```

consumer group.

Conceptually:

```text
             Kafka
               │
       ┌───────┴───────┐
       ↓               ↓
 Consumer A        Consumer B
       │               │
       └──── same group┘
```

Kafka will distribute partitions between them.

---

## Step 16.4 — Scale consumers

Try three consumers:

```text
Consumer A
Consumer B
Consumer C
```

with:

```text
3 partitions
```

Ideally:

```text
Partition 0 → Consumer A
Partition 1 → Consumer B
Partition 2 → Consumer C
```

If you run **4 consumers with only 3 partitions**:

```text
Consumer A → Partition 0
Consumer B → Partition 1
Consumer C → Partition 2
Consumer D → nothing
```

This is an important interview concept:

> A consumer group cannot actively process more partitions in parallel than the topic has partitions.

---

## Step 16.5 — Test consumer failure

Run 3 consumers.

Then stop one.

Kafka should rebalance the partitions among the remaining consumers.

```text
Before:

P0 → C1
P1 → C2
P2 → C3

C2 dies

After:

P0 → C1
P1 → C3
P2 → C1
```

You don't manually redistribute anything.

Kafka handles the consumer-group rebalancing.

---

## Step 16.6 — Task 16 Done

Verify:

* [ ] Topic has 3 partitions.
* [ ] Producer can send events.
* [ ] Multiple consumers use the same consumer group.
* [ ] Events are distributed among consumers.
* [ ] Consumer failure causes rebalance.
* [ ] You understand why partitions provide parallelism.
* [ ] You understand why consumer groups provide coordinated consumption.

---

<hr/>
==========================================================================

# Task 17 — Schema Registry + Schema Evolution

Now we're going to solve a common production problem.

Your event currently looks like:

```json
{
  "user_id": 123,
  "item_id": 42,
  "event_type": "view",
  "timestamp": "2026-09-08T12:00:00Z"
}
```

But imagine six months later we need:

```json
{
  "user_id": 123,
  "item_id": 42,
  "event_type": "view",
  "timestamp": "...",
  "device_type": "mobile"
}
```

We need to make sure producers and consumers don't suddenly break.

---

## Step 17.1 — Understand the problem

Without schema management:

```text
Producer
   ↓
changes event
   ↓
Kafka
   ↓
old consumer
   ↓
💥
```

We want:

```text
Producer
   ↓
Schema Registry
   ↓
Kafka
   ↓
Consumer
```

The Schema Registry keeps track of event schemas and compatibility.

---

## Step 17.2 — Add a schema registry

For local development, add a Schema Registry service alongside Kafka.

Your architecture becomes:

```text
Docker Compose

Kafka
  │
  └── Schema Registry
```

Use a local Schema Registry compatible with your Kafka setup.

If you're using Confluent Kafka, use the corresponding Confluent Schema Registry version matching your Kafka stack.

---

## Step 17.3 — Define a schema

Instead of sending arbitrary JSON, define a schema for:

```text
UserInteractionEvent
```

For example, using Avro:

```json
{
  "type": "record",
  "name": "UserInteractionEvent",
  "fields": [
    {
      "name": "user_id",
      "type": "long"
    },
    {
      "name": "item_id",
      "type": "long"
    },
    {
      "name": "event_type",
      "type": "string"
    },
    {
      "name": "timestamp",
      "type": "string"
    }
  ]
}
```

Create:

```text
app/schemas/user_interaction.avsc
```

---

## Step 17.4 — Producer uses schema

Your producer should serialize the event according to this schema.

The important architecture becomes:

```text
Pydantic model
      ↓
Avro schema
      ↓
Schema Registry
      ↓
Kafka
```

You don't need to replace Pydantic.

Pydantic remains useful for validating your application input.

The Kafka schema provides a **contract between distributed systems**.

---

## Step 17.5 — Evolve the schema

Now add:

```text
device_type
```

But make it optional/defaulted.

For example:

```json
{
  "name": "device_type",
  "type": ["null", "string"],
  "default": null
}
```

This means old consumers can still read the event.

That's the concept of **backward-compatible schema evolution**.

---

## Step 17.6 — Test compatibility

Test:

```text
Schema V1
   ↓
old consumer
```

Then:

```text
Schema V2
   ↓
old consumer
```

The old consumer should continue working.

Then test:

```text
Schema V2
   ↓
new consumer
```

The new consumer should understand both the old and new events where your compatibility policy requires it.

---

## Step 17.7 — Task 17 Done

Verify:

* [ ] Schema Registry is running.
* [ ] `UserInteractionEvent` has a defined schema.
* [ ] Producer uses the schema.
* [ ] Consumer understands the schema.
* [ ] Schema V2 adds an optional field.
* [ ] Old events remain readable.
* [ ] You understand why schemas are contracts between services.

---

==========================================================================================================================================

# Task 18 — Feature Store

Now we're getting into the **actual recommendation-system architecture**.

So far:

```text
User interactions
       ↓
Kafka
       ↓
Consumer
```

But recommendations need features.

Examples:

```text
user_id = 123

features:

recent_categories = ["electronics", "books"]
click_count_7d = 42
purchase_count_30d = 5
last_active_minutes = 12
preferred_price_range = 50-100
```

These are **features** used by recommendation models.

---

# Step 18.1 — Understand the Feature Store

A feature store provides a consistent way to store and retrieve ML features.

Conceptually:

```text
Kafka
  │
  ↓
Feature Processing
  │
  ↓
Feature Store
  │
  ├── Online Store
  │       ↓
  │   low latency
  │
  └── Offline Store
          ↓
      model training
```

The online store is optimized for serving predictions.

The offline store is optimized for historical/training data.

---

# Step 18.2 — Don't install a complicated feature-store platform yet

For this learning project, we're going to **build a tiny feature store ourselves**.

Use Redis as the online feature store.

Later you can learn Feast or another production feature-store technology.

Our architecture:

```text
Kafka
  ↓
Feature Consumer
  ↓
Redis
  ↓
User Features
```

---

# Step 18.3 — Create feature model

Create:

```text
app/features.py
```

Define:

```python
from pydantic import BaseModel


class UserFeatures(BaseModel):
    user_id: int
    click_count: int = 0
    purchase_count: int = 0
    last_item_id: int | None = None
```

---

# Step 18.4 — Create feature store

Create:

```text
app/feature_store.py
```

Implement two basic operations:

```text
get_user_features(user_id)
```

and:

```text
update_user_features(user_id, ...)
```

Store the features in Redis.

For example:

```text
features:user:123
```

could contain:

```json
{
  "user_id": 123,
  "click_count": 42,
  "purchase_count": 5,
  "last_item_id": 99
}
```

---

# Step 18.5 — Connect Kafka to Feature Store

Now modify your Kafka consumer.

Previously:

```text
Kafka
 ↓
Consumer
 ↓
log event
```

Now:

```text
Kafka
 ↓
Consumer
 ↓
Feature Processor
 ↓
Redis Feature Store
```

When this event arrives:

```json
{
  "user_id": 123,
  "item_id": 42,
  "event_type": "click"
}
```

update:

```text
click_count += 1
last_item_id = 42
```

If:

```json
{
  "user_id": 123,
  "item_id": 50,
  "event_type": "purchase"
}
```

then:

```text
purchase_count += 1
last_item_id = 50
```

---

# Step 18.6 — Test it

Start Redis.

Start Kafka.

Start your consumer.

Publish:

```text
user 123 → click item 42
```

Then retrieve:

```text
features:user:123
```

You should see:

```json
{
  "user_id": 123,
  "click_count": 1,
  "purchase_count": 0,
  "last_item_id": 42
}
```

Publish another click:

```text
user 123 → click item 50
```

Now:

```json
{
  "user_id": 123,
  "click_count": 2,
  "purchase_count": 0,
  "last_item_id": 50
}
```

Publish a purchase:

```text
user 123 → purchase item 99
```

Now:

```json
{
  "user_id": 123,
  "click_count": 2,
  "purchase_count": 1,
  "last_item_id": 99
}
```

---

# Step 18.7 — Use features in recommendations

Finally, expose a simple function:

```text
get_user_features(user_id)
```

Your recommendation flow can eventually become:

```text
Request
   ↓
Redis recommendation cache
   ↓
PostgreSQL
   ↓
Feature Store
   ↓
Recommendation Model
   ↓
Recommendations
```

We're **not building the actual ML model yet**.

That comes in Task 19.

---

# Task 18 Done When

* [ ] `UserFeatures` model created.
* [ ] Redis feature store created.
* [ ] `get_user_features()` works.
* [ ] `update_user_features()` works.
* [ ] Kafka consumer updates features.
* [ ] Click events increment `click_count`.
* [ ] Purchase events increment `purchase_count`.
* [ ] `last_item_id` updates.
* [ ] Features can be retrieved by user ID.

---

# What you've built after 16–18

You'll have a much more realistic architecture:

```text
                       ┌───────────────┐
                       │    FastAPI    │
                       └───────┬───────┘
                               │
                    Recommendation Request
                               │
                               ↓
                         Redis Cache
                               │
                               ↓
                         PostgreSQL
                               │
                               ↓
                        Recommendation
                           Pipeline


User Events
     │
     ↓
   Kafka
     │
     ↓
Feature Consumer
     │
     ↓
 Feature Store
    Redis
```

And the three major concepts are:

| Task   | Concept                      | Why                                |
| ------ | ---------------------------- | ---------------------------------- |
| **16** | Partitions + Consumer Groups | Scale event processing             |
| **17** | Schema Registry              | Safely evolve event contracts      |
| **18** | Feature Store                | Serve ML features with low latency |

**Do them in order: 16 → 17 → 18.** Don't implement all three simultaneously; each one teaches a separate distributed-system concept.


### Implementation in TAsk 18 are pre-requisite for a machine learning model. It will use these metrics to predict the top choices of user. 



=============

Task 18 Improved:


Yes — **your understanding is basically correct**, and actually this is a much more realistic architecture than the tiny Redis-only feature store we built in Task 18.

The key distinction is:

> **PostgreSQL = durable system of record / historical data**
> **Redis = fast online feature serving / derived state**

### A realistic architecture

```text
User
 │
 │ clicks / purchases
 ▼
FastAPI / Event Producer
 │
 ▼
Kafka
 │
 ├──────────────► PostgreSQL
 │                 │
 │                 │ Historical events
 │                 │ Analytics
 │                 │ Retraining
 │                 │ Auditing
 │                 ▼
 │              user_events
 │
 └──────────────► Feature Processing Job
                    │
                    │ aggregate / calculate
                    ▼
                 Redis
                    │
                    │ "Give me features for user 123"
                    ▼
              Recommendation API
                    │
                    ▼
                  Model
```

And this is much closer to how I'd want **our learning project** to evolve.

### PostgreSQL could store the raw events

For example:

```sql
CREATE TABLE user_events (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    item_id BIGINT NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

Data:

| id | user_id | item_id | event_type | created_at |
| -: | ------: | ------: | ---------- | ---------- |
|  1 |     123 |      42 | click      | ...        |
|  2 |     123 |      55 | click      | ...        |
|  3 |     123 |      55 | purchase   | ...        |
|  4 |     456 |      10 | click      | ...        |

Now you have the **complete history**.

You can calculate:

```text
User 123

click_count      = 2
purchase_count   = 1
last_item_id     = 55
last_click_at    = ...
total_spend      = ...
clicks_7d        = 10
purchases_30d    = 3
```

Those are **features**.

### Then Redis holds the features needed for online inference

Something like:

```text
features:user:123
```

```json
{
    "click_count": 2,
    "purchase_count": 1,
    "last_item_id": 55,
    "clicks_7d": 10,
    "purchases_30d": 3
}
```

Then when:

```http
GET /recommendations/123
```

we don't want to run:

```sql
SELECT COUNT(*)
FROM user_events
WHERE user_id = 123;
```

for every request.

Instead:

```text
API
 ↓
Redis
 ↓
User features
 ↓
Model
 ↓
Recommendations
```

That's why Redis is valuable.

---

## One important correction

You said:

> "the important ones goes to redis"

I'd slightly change that.

It's not necessarily that **important events** go to Redis.

Rather:

> **Features that are frequently needed for low-latency online prediction are materialized into Redis.**

For example, a purchase event is important, but we might store the **purchase event in PostgreSQL** and then update a derived feature in Redis:

```text
purchase event
      ↓
PostgreSQL
      ↓
Feature processor
      ↓
purchase_count += 1
      ↓
Redis
```

So Redis isn't necessarily the source of truth.

---

# And Kafka fits beautifully here

This is where our previous Tasks 15–18 start making more sense.

Instead of:

```text
Kafka
 ↓
Redis feature store
```

we can build:

```text
                    ┌───────────────┐
                    │  PostgreSQL   │
                    │ raw events    │
                    └───────▲───────┘
                            │
                            │
User → Kafka → event ───────┤
                            │
                            ▼
                    Feature Processor
                            │
                            ▼
                    ┌───────────────┐
                    │     Redis     │
                    │ online        │
                    │ features      │
                    └───────▲───────┘
                            │
                            │
                     Recommendation API
                            │
                            ▼
                          Model
```

And **different Kafka consumer groups** can consume the same event:

```text
                    Kafka
                      │
          ┌───────────┼────────────┐
          ▼           ▼            ▼
     PostgreSQL   Feature Job   Analytics
                    │
                    ▼
                  Redis
```

This is an excellent interview architecture because you can explain why each component exists.

---

## What I would change in our project

I actually think we should **upgrade Task 18** rather than blindly continue with the tiny Redis feature store.

Our progression should become:

### Current

```text
Kafka
 ↓
Feature consumer
 ↓
Redis
```

### Better production-style version

```text
Kafka
 ↓
 ├── PostgreSQL → durable event history
 │
 └── Feature Processor
          ↓
        Redis
          ↓
   Recommendation API
          ↓
        Model
```

Then later we can add:

```text
PostgreSQL
     ↓
Offline feature computation
     ↓
Training dataset
     ↓
ML model
```

So we get the important **offline vs online feature-store concept**:

```text
                FEATURE STORE
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
   Offline Store          Online Store
   PostgreSQL             Redis
   historical data        low latency
          │                     │
          ▼                     ▼
       Training             Inference
```

That's much more representative of a real recommendation system.

**So yes: your thinking is correct.** I'd modify our project to use PostgreSQL for the durable click/purchase event history and Redis as the low-latency **online feature store**, with Kafka connecting the two. This is a better architecture for what you're trying to learn.







=========================================================================



Excellent. ✅ **Task 18 — Feature Store is complete.**

Your architecture now has the core data/ML foundation:

```text
User Events
    ↓
  Kafka
    ↓
Feature Consumer
    ↓
Feature Store (Redis)
    ↓
Recommendation System
```

And separately:

```text
FastAPI
   ↓
Redis Cache
   ↓
PostgreSQL
```

# Task 19 — Model Serving & Model Versioning

Now we'll introduce the **ML model** into the recommendation pipeline.

### Goal

Learn how a production recommendation service separates:

* recommendation API
* feature retrieval
* model inference
* model versions

We'll start with a **very simple fake recommendation model**. No real ML training yet.

---

## Step 19.1 — Create the model interface

Create:

```text
app/model.py
```

Add:

```python
from pydantic import BaseModel


class RecommendationModel:
    def __init__(self, version: str):
        self.version = version

    def predict(self, features: BaseModel) -> list[int]:
        raise NotImplementedError
```

The important idea is that the rest of the application shouldn't care how the model works.

---

## Step 19.2 — Create a simple model

In the same file, add:

```python
class SimpleRecommendationModel(RecommendationModel):
    def predict(self, features: BaseModel) -> list[int]:
        if features.purchase_count > 0:
            return [90, 91, 92, 93, 94]

        if features.click_count > 0:
            return [50, 51, 52, 53, 54]

        return [10, 20, 30, 40, 50]
```

This isn't ML yet.

We're simply simulating:

```text
Features
   ↓
Model
   ↓
Recommendations
```

---

## Step 19.3 — Add model version

Create the model like:

```python
model = SimpleRecommendationModel(version="v1")
```

Now the model has an explicit version:

```text
v1
```

This matters because eventually you'll have:

```text
v1
v2
v3
```

and need to know which model generated a recommendation.

---

## Step 19.4 — Create a model registry

Create:

```text
app/model_registry.py
```

Add:

```python
from app.model import SimpleRecommendationModel


MODELS = {
    "v1": SimpleRecommendationModel(version="v1"),
}


def get_model(version: str):
    model = MODELS.get(version)

    if model is None:
        raise ValueError(f"Unknown model version: {version}")

    return model
```

Now your application can explicitly request:

```python
model = get_model("v1")
```

---

## Step 19.5 — Test the model

Create:

```text
tests/test_model.py
```

Test:

### User with purchases

```text
purchase_count = 2
```

Expected:

```text
[90, 91, 92, 93, 94]
```

### User with clicks

```text
click_count = 5
purchase_count = 0
```

Expected:

```text
[50, 51, 52, 53, 54]
```

### New user

```text
click_count = 0
purchase_count = 0
```

Expected:

```text
[10, 20, 30, 40, 50]
```

---

# Step 19.6 — Connect Model → Feature Store

The conceptual flow becomes:

```text
Request
   ↓
Feature Store
   ↓
User Features
   ↓
Model
   ↓
Recommendations
```

For example:

```text
user 123
   ↓
Feature Store
   ↓
click_count = 20
purchase_count = 2
   ↓
Model v1
   ↓
[90, 91, 92, 93, 94]
```

Create a small service layer rather than putting this directly inside your FastAPI route.

For example:

```text
app/
├── model.py
├── model_registry.py
├── feature_store.py
└── recommendation_service.py
```

---

# Step 19.7 — Add model version to the response

Your recommendation response should eventually expose which model generated the result.

For example:

```json
{
  "user_id": 123,
  "recommendations": [90, 91, 92, 93, 94],
  "model_version": "v1"
}
```

Update your Pydantic response schema accordingly.

This is extremely useful for debugging and monitoring.

You can later answer:

> "Did recommendations generated by v2 perform better than v1?"

---

# Step 19.8 — Add model version to logs

When generating recommendations, log:

```text
user_id=123
model_version=v1
recommendations=[90,91,92,93,94]
```

Don't log sensitive user information unnecessarily in a real production system; we're keeping this simple for learning.

---

# Step 19.9 — Test model versioning

Add:

```python
MODELS = {
    "v1": SimpleRecommendationModel(version="v1"),
    "v2": SimpleRecommendationModel(version="v2"),
}
```

Make `v2` return a different recommendation set.

Then verify:

```text
get_model("v1") → v1
get_model("v2") → v2
```

and:

```text
get_model("v999")
```

raises an appropriate error.

---

# Step 19.10 — Important production concept

Eventually, you don't want:

```text
FastAPI
   ↓
load huge model
   ↓
predict
```

inside every request if the model is large.

A production architecture may look like:

```text
FastAPI
   ↓
Model Serving API
   ↓
Model
```

or:

```text
FastAPI
   ↓
Dedicated Model Server
   ↓
GPU / CPU
```

We'll learn that distinction later.

For now, our model is intentionally tiny and runs inside the application.

---

# Task 19 — Definition of Done

* [ ] `model.py` created.
* [ ] Model interface created.
* [ ] Simple model implemented.
* [ ] Model version exists.
* [ ] Model registry created.
* [ ] `v1` works.
* [ ] `v2` works.
* [ ] Unknown model version handled.
* [ ] Model uses Feature Store data.
* [ ] Recommendation response includes `model_version`.
* [ ] Model tests pass.
* [ ] Existing API behavior still works.
* [ ] Existing fallback behavior still works.

### The architecture after Task 19

```text
                         FastAPI
                            │
                            ↓
                      Recommendation
                         Service
                            │
                  ┌─────────┴─────────┐
                  ↓                   ↓
             Redis Cache         Feature Store
                  │                   │
                  ↓                   ↓
             PostgreSQL             Model
                                  Registry
                                     │
                                  Model v1
                                  Model v2
```


=========================================================================

## Task 19 Updated

Yes — **you are thinking straight**. In fact, I would update Task 19 before you continue.

The only thing I'd clarify is that PostgreSQL shouldn't directly be the "model." PostgreSQL should contain the **candidate/recommendation data**, while the model uses the **features from Redis** to decide/rank what to return.

So Task 19 can become our first proper **data + feature + model** pipeline.

### Updated Task 19 architecture

```text
                    User Request
                         │
                         ▼
                 Recommendation API
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
        Redis Features        PostgreSQL
        user:123              candidate data
              │                     │
              └──────────┬──────────┘
                         ▼
                    Model v1
                         │
                         ▼
                 Recommendations
```

And PostgreSQL gets seeded by `seed.py`.

---

# Task 19 — Real Recommendation Data + Model Versioning

We'll do this in small steps.

## Step 1 — Create a recommendation candidates table

We already have:

```sql
recommendations
```

from Task 14.

But I would **not reuse that table** for this task because Task 14 represents the persisted recommendation result.

Let's introduce a separate table:

```sql
CREATE TABLE recommendation_items (
    id BIGSERIAL PRIMARY KEY,
    item_id BIGINT NOT NULL,
    score DOUBLE PRECISION NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);
```

Seed it with something like:

```text
item_id    score
----------------
10         0.95
20         0.91
30         0.88
40         0.84
50         0.80
60         0.76
70         0.72
80         0.68
90         0.65
91         0.63
92         0.61
93         0.59
94         0.57
```

This gives us **real data coming from PostgreSQL** instead of:

```python
return [90, 91, 92, 93, 94]
```

---

# Step 2 — Update `seed.py`

Your `seed.py` can now insert the predefined recommendation items.

Conceptually:

```python
RECOMMENDATION_ITEMS = [
    (10, 0.95),
    (20, 0.91),
    (30, 0.88),
    (40, 0.84),
    (50, 0.80),
    (60, 0.76),
    (70, 0.72),
    (80, 0.68),
    (90, 0.65),
    (91, 0.63),
    (92, 0.61),
    (93, 0.59),
    (94, 0.57),
]
```

Then insert them into PostgreSQL.

**Don't worry about making the seed script sophisticated yet.** The purpose is simply:

```text
docker compose up
       ↓
PostgreSQL
       ↓
seed.py
       ↓
predefined recommendation data
```

---

# Step 3 — Create a PostgreSQL repository

Don't let your model directly execute SQL.

Create something like:

```text
app/
├── main.py
├── model.py
├── model_registry.py
├── features.py
├── feature_store.py
├── recommendation_repository.py   ← new
└── seed.py
```

The repository is responsible for PostgreSQL.

For example:

```python
async def get_recommendation_items(limit: int = 5):
    ...
```

It executes:

```sql
SELECT item_id, score
FROM recommendation_items
WHERE is_active = TRUE
ORDER BY score DESC
LIMIT $1;
```

So now:

```text
Model
  ↓
Recommendation Repository
  ↓
PostgreSQL
```

rather than the model knowing anything about SQL.

That's an important architectural lesson.

---

# Step 4 — Now use the feature store

This is where Task 18 connects with Task 19.

Suppose Redis contains:

```json
{
    "user_id": 123,
    "click_count": 10,
    "purchase_count": 2,
    "last_item_id": 55
}
```

The model receives those features.

For example:

```python
features = await get_user_features(user_id)

model = get_model("v1")

recommendations = await model.predict(
    features,
    recommendation_repository
)
```

But there is one architectural improvement I'd make.

### Don't make the model responsible for fetching PostgreSQL data.

Instead:

```text
API
 │
 ├── Get features from Redis
 │
 ├── Get candidate items from PostgreSQL
 │
 └── Give both to model
             │
             ▼
           Model
             │
             ▼
       ranked recommendations
```

So the model becomes:

```python
model.predict(features, candidates)
```

That's much cleaner.

---

# Step 5 — Your first actual "model"

We don't need machine learning yet.

We can make a deterministic scoring model.

For example:

```python
class SimpleRecommendationModel:

    def __init__(self, version: str):
        self.version = version

    def predict(self, features, candidates):

        if features.purchase_count > 0:
            candidates = candidates[:5]

        elif features.click_count > 0:
            candidates = candidates[:5]

        else:
            candidates = candidates[:5]

        return [item.item_id for item in candidates]
```

At this stage, it may look almost too simple.

**That's intentional.**

We're separating the architecture first.

Later we can replace the logic with an actual ML model.

---

# But let's make v2 actually different

This is where model versioning becomes meaningful.

### v1

Rank primarily by PostgreSQL's candidate score.

```text
candidate score
      ↓
ranking
```

### v2

Take user activity into account.

For example:

```text
final_score =
    candidate_score
    + click_count × 0.01
    + purchase_count × 0.05
```

Then:

```text
v1 → popularity-based
v2 → popularity + user features
```

Now model versioning actually has a purpose.

---

# The resulting Task 19 flow

This is what I'd like you to implement:

```text
                    GET /recommendations/123
                              │
                              ▼
                    ┌──────────────────┐
                    │   FastAPI API    │
                    └────────┬─────────┘
                             │
                    Get user features
                             │
                             ▼
                    ┌──────────────────┐
                    │      Redis       │
                    │ Online Features  │
                    └────────┬─────────┘
                             │
                             ▼
                     UserFeatures
                             │
                             │
              Get candidate recommendations
                             │
                             ▼
                    ┌──────────────────┐
                    │   PostgreSQL     │
                    │ recommendation_  │
                    │      items       │
                    └────────┬─────────┘
                             │
                             ▼
                         Candidates
                             │
                  ┌──────────┴──────────┐
                  │                     │
                  ▼                     ▼
             User Features        Candidates
                  │                     │
                  └──────────┬──────────┘
                             ▼
                        Model v1/v2
                             │
                             ▼
                    Recommendation IDs
```

And your response can be:

```json
{
    "user_id": 123,
    "recommendations": [10, 20, 30, 40, 50],
    "model_version": "v1"
}
```

---

## One important thing: don't mix Task 14's table with this

We currently have:

```text
recommendations
```

which represents the **persisted recommendations for a user**.

Now we're introducing:

```text
recommendation_items
```

which represents **candidate items available to the recommendation system**.

That's actually useful for learning the distinction:

**Candidate generation**

```text
PostgreSQL
   ↓
[10,20,30,40,50,60,70,80,90...]
```

**Ranking**

```text
Model
   ↓
[30,10,50,20,90]
```

**Final result**

```text
API
   ↓
[30,10,50,20,90]
```

Later, we can make candidate generation much more sophisticated.

---

### So yes: I recommend we revise Task 19.

And I would **not jump directly into the code yet**. Since you're using this project to rebuild your ability to code independently, implement it in this order:

1. Create `recommendation_items` table.
2. Update `seed.py`.
3. Verify PostgreSQL contains the seeded records.
4. Create `recommendation_repository.py`.
5. Verify Python can retrieve candidates from PostgreSQL.
6. Update `model.py` to accept `features + candidates`.
7. Implement v1.
8. Implement v2.
9. Add `model_registry.py`.
10. Connect everything through the service layer.
11. Add/update pytest tests.
12. Verify existing Redis/PostgreSQL/Kafka failure behavior still works.

**That would be a much stronger Task 19 than the original static-data version.** It also sets us up naturally for the next tasks: real feature processing, model training, model registry/deployment, monitoring, and eventually a proper offline/online feature-store architecture.




After this, **Task 20 will be CI/CD**—where we'll take everything we've built and create a pipeline that automatically tests and builds the application before deployment.

=========================



Excellent. **Task 19 is done.** ✅

You've now reached an important point in the architecture:

```text
Kafka
  ↓
PostgreSQL ──→ historical/event data
  ↓
Feature processing
  ↓
Redis ───────→ online user features
  ↓
Recommendation API
  ↓
Candidate data from PostgreSQL
  ↓
Model v1 / v2
  ↓
Recommendations
```

## Task 20 — CI/CD

Now we're going to make sure the project is **automatically tested whenever you push code**.

The goal is not to deploy to production yet. First we'll build a proper CI pipeline.

### What you'll learn

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
   ├── Install Python
   ├── Install dependencies
   ├── Run pytest
   └── Build Docker image
          │
          ▼
       PASS / FAIL
```

This is important because our project now has:

* FastAPI
* Pydantic
* Redis
* PostgreSQL
* Kafka
* feature store
* model versions
* Docker
* multiple services

Manually testing all of this after every change isn't sustainable.

---

# Step 1 — Create GitHub Actions directory

At your project root:

```text
.github/
└── workflows/
    └── ci.yml
```

---

# Step 2 — Create `ci.yml`

Start with a simple Python test pipeline.

```yaml
name: CI

on:
  push:
    branches:
      - main
      - develop

  pull_request:
    branches:
      - main

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run tests
        run: |
          pytest
```

Commit and push this.

Then go to:

**GitHub → Your repository → Actions**

You should see:

```text
CI
 └── test
      ├── Checkout code       ✓
      ├── Setup Python        ✓
      ├── Install dependencies ✓
      └── Run tests           ✓
```

---

# Step 3 — Deliberately break a test

This is important.

Don't just verify that CI passes.

Temporarily change one expected value in a test.

For example:

```python
assert result == [999]
```

when the actual result is something else.

Push it.

GitHub Actions should show:

```text
Run tests
   ❌ FAILED
```

Then fix the test and push again.

You should get:

```text
CI
 └── test
      └── Run tests ✓
```

This teaches you the actual purpose of CI.

---

# Step 4 — Add Docker build validation

Once the Python tests are passing, add another job/step to make sure the application can actually be packaged.

Add:

```yaml
      - name: Build Docker image
        run: |
          docker build -t recommendation-service:test .
```

Your job becomes:

```yaml
jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run tests
        run: |
          pytest

      - name: Build Docker image
        run: |
          docker build -t recommendation-service:test .
```

Now CI verifies two things:

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

---

# Step 5 — Understand CI vs CD

This distinction is important for interviews.

### CI — Continuous Integration

```text
Code
 ↓
Tests
 ↓
Build
 ↓
Quality checks
```

CI answers:

> "Is this change safe to merge?"

### CD — Continuous Delivery/Deployment

```text
Code
 ↓
Tests
 ↓
Build image
 ↓
Push image
 ↓
Deploy
 ↓
Health checks
```

CD answers:

> "Can this validated version be released?"

We're initially doing **CI**.

We'll introduce the deployment portion later because I don't want to hide the important concepts behind a giant GitHub Actions file.

---

# Step 6 — Your Task 20 checklist

Don't move on until these work:

### GitHub

* [ ] `.github/workflows/ci.yml` created
* [ ] Push triggers CI
* [ ] Pull request triggers CI
* [ ] Python 3.12 installed
* [ ] Dependencies install successfully
* [ ] All pytest tests pass
* [ ] Docker image builds successfully
* [ ] Deliberately broken test causes CI failure
* [ ] Fixed test causes CI to pass again

### Concepts you should understand

You should be able to explain:

> **What is CI?**

> **Why should tests run before building/deploying?**

> **What is the difference between CI and CD?**

> **Why build the Docker image in CI?**

> **What happens when a developer pushes broken code?**


================================================================================================


Excellent. **Task 20 — CI/CD is done.** ✅

We're now at the point where the project has the core data and serving pieces:

```text
Kafka
  ↓
PostgreSQL ── historical data / candidates
  ↓
Feature processing
  ↓
Redis ── online features
  ↓
Recommendation Service
  ↓
Model v1 / v2
  ↓
Redis ── recommendation-result cache
  ↓
FastAPI response
```

## Task 21 — Production Observability

Now we'll focus on something very important for a **senior backend/system-design engineer**:

> **How do we know what the system is doing in production, and why a request was slow or failed?**

We'll implement this progressively.

### What we're going to add

#### 1. Structured logging

Instead of:

```python
print("Redis failed")
```

we'll have useful structured logs such as:

```json
{
  "level": "WARNING",
  "event": "redis_unavailable",
  "user_id": 123,
  "request_id": "abc-123"
}
```

---

#### 2. Request ID / correlation ID

Every request gets an ID:

```text
GET /recommendations/123
        │
        │ request_id = abc123
        ▼
Recommendation Service
        │
        ├── Redis
        │
        ├── PostgreSQL
        │
        └── Model
```

All logs related to that request contain:

```text
request_id=abc123
```

So if a user reports:

> "Recommendation API was slow."

you can search logs for `abc123` and follow the entire request.

---

#### 3. Basic metrics

We'll eventually track things like:

```text
recommendation_requests_total
recommendation_latency_seconds
redis_hits_total
redis_misses_total
redis_failures_total
postgres_failures_total
model_predictions_total
```

This lets you answer questions such as:

> Are Redis failures increasing?

> What's our p95 recommendation latency?

> What percentage of requests are cache hits?

---

#### 4. OpenTelemetry

Then we'll introduce tracing:

```text
Request
 │
 └── Trace
      │
      ├── Redis lookup       4ms
      ├── PostgreSQL query   12ms
      ├── Model inference    8ms
      └── Redis cache write  2ms
```

This is particularly useful because our architecture now has several components.

---

### Task 21 progression

Don't implement everything at once.

We'll do:

```text
Step 1 → structured logging
Step 2 → request/correlation ID
Step 3 → useful application events
Step 4 → metrics
Step 5 → OpenTelemetry tracing
Step 6 → inspect/debug a real request
Step 7 → tests
```

And we'll deliberately create a Redis failure and observe what the logs/metrics show.

**Task 21 is about observability, not changing recommendation logic.**

Once you've completed it, tell me **"Task 21 done"**, and we'll move to **Task 22 — ML model monitoring, regression detection, and data/model drift**.


================================================================================================

Great. **Task 21 — Observability is done.** ✅

Now we have enough infrastructure to start treating the recommendation system like a real ML-backed production service.

# Task 22 — Model Monitoring & Drift Detection

The goal of Task 22 is to answer:

> **"How do we know if our recommendation model is still performing correctly after deployment?"**

We're going to start with **model-quality monitoring**, not complicated ML mathematics.

---

## What we're adding

Our current flow is roughly:

```text
User
 ↓
FastAPI
 ↓
Redis Features ──────┐
                     │
PostgreSQL Candidates│
                     │
                     ▼
                  Model v1/v2
                     │
                     ▼
              Recommendations
```

Now we'll capture information about each prediction:

```text
Model prediction
      │
      ├── model_version
      ├── user_id
      ├── features used
      ├── recommendations returned
      └── timestamp
```

This gives us the foundation for monitoring.

---

# Step 1 — Create a prediction log

Create something like:

```text
app/
├── model.py
├── model_registry.py
├── service.py
├── prediction_logger.py   ← new
└── ...
```

Create a Pydantic model:

```python
class PredictionLog(BaseModel):
    user_id: int
    model_version: str
    recommendation_count: int
    click_count: int
    purchase_count: int
    timestamp: datetime
```

Don't store the entire feature object blindly. Start with the important fields.

---

# Step 2 — Log every prediction

After the model produces recommendations:

```python
recommendations = model.predict(
    features,
    candidates
)
```

create a prediction log:

```python
prediction = PredictionLog(
    user_id=user_id,
    model_version=model.version,
    recommendation_count=len(recommendations),
    click_count=features.click_count,
    purchase_count=features.purchase_count,
    timestamp=datetime.utcnow(),
)
```

Then send it through your logger.

Because you completed Task 21, you should already have structured logging available.

You want logs that allow you to answer:

```text
How many predictions did v1 make?
How many did v2 make?
How many recommendations were returned?
What kind of users were being served?
```

---

# Step 3 — Add model metrics

Now add counters for:

```text
model_predictions_total
```

with a model-version label:

```text
model_predictions_total{model_version="v1"}
model_predictions_total{model_version="v2"}
```

Also add:

```text
recommendation_count
```

and preferably:

```text
model_prediction_latency
```

So your monitoring becomes:

```text
             Model Monitoring

        ┌───────────────────────┐
        │ Predictions            │
        │ v1 = 10,000            │
        │ v2 = 12,000            │
        ├───────────────────────┤
        │ Latency                │
        │ p50 = 8ms              │
        │ p95 = 20ms             │
        ├───────────────────────┤
        │ Errors                 │
        │ v1 = 0.1%              │
        │ v2 = 0.3%              │
        └───────────────────────┘
```

---

# Step 4 — Introduce a simple drift detector

Don't build a complicated statistical ML system yet.

We'll start with a very simple detector.

Suppose historically we normally see:

```text
average click_count = 10
```

But suddenly:

```text
average click_count = 100
```

Something may have changed.

Create:

```text
app/
└── drift.py
```

Implement a simple function:

```python
def detect_drift(
    current_average: float,
    baseline_average: float,
    threshold: float = 0.5,
) -> bool:
    if baseline_average == 0:
        return False

    difference = abs(current_average - baseline_average)
    change = difference / baseline_average

    return change > threshold
```

Example:

```python
detect_drift(12, 10)
```

returns:

```text
False
```

because the change is only 20%.

But:

```python
detect_drift(20, 10)
```

returns:

```text
True
```

because the change is 100%.

---

# Step 5 — Understand what "drift" means

There are actually several different concepts.

### Data drift

Input data changes.

```text
Before:

click_count
5
7
10
8
6

After:

click_count
40
80
100
60
90
```

The distribution changed.

---

### Concept drift

The relationship between inputs and desired outcomes changes.

For example:

```text
Previously:

lots of clicks → likely purchase
```

Later:

```text
lots of clicks → no longer predicts purchase
```

The model's assumptions become less accurate.

---

### Model drift / performance degradation

The model itself may continue running perfectly but its results become worse.

For example:

```text
v2

CTR:
Before → 8%
After  → 2%
```

The application isn't technically broken.

But the model isn't performing well anymore.

---

# Step 6 — Add a model-quality signal

We don't have real CTR/purchase feedback yet, so we'll simulate the feedback.

When a user clicks a recommended item, we'll eventually have:

```text
recommendation shown
       ↓
user clicked
       ↓
feedback event
```

For this task, track:

```text
recommendations_served
recommendations_clicked
```

Then calculate:

```text
CTR = clicks / recommendations_served
```

For example:

```text
10,000 recommendations
500 clicks

CTR = 500 / 10,000
    = 5%
```

This becomes a basic model-quality metric.

---

# Step 7 — Compare model versions

Now our model versioning becomes much more meaningful.

Imagine:

```text
Model    Requests    CTR

v1       50,000      4.2%
v2       50,000      6.1%
```

You can now say:

> "v2 performs better than v1 based on observed recommendation CTR."

This will become extremely important when we eventually introduce **canary deployment**.

---

# Task 22 checklist

### Prediction monitoring

* [ ] Create `PredictionLog`
* [ ] Log every prediction
* [ ] Record model version
* [ ] Record useful feature information
* [ ] Record recommendation count
* [ ] Add prediction metrics
* [ ] Track model latency

### Drift

* [ ] Create `drift.py`
* [ ] Implement simple baseline comparison
* [ ] Test normal change
* [ ] Test significant change
* [ ] Understand data drift
* [ ] Understand concept drift
* [ ] Understand model performance degradation

### Model quality

* [ ] Track recommendations served
* [ ] Track recommendation clicks
* [ ] Calculate CTR
* [ ] Compare v1 vs v2

---

## One important architectural point

Don't put drift detection **inside the request path**.

Don't do:

```text
User Request
 ↓
Model
 ↓
Calculate drift
 ↓
Response
```

That adds unnecessary latency.

Instead:

```text
                    Request
                       │
                       ▼
                     Model
                       │
                       ▼
                    Response
                       │
                       └──────► Metrics / Logs
                                      │
                                      ▼
                              Monitoring process
                                      │
                                      ▼
                                Drift detection
```

The recommendation API should remain focused on serving recommendations quickly.

---

### What comes next

After Task 22, we'll have:

```text
Task 19 → Model serving/versioning
Task 20 → CI/CD
Task 21 → Observability
Task 22 → Model monitoring/drift
```

Then **Task 23 — Canary / Blue-Green Deployment + Rollback** becomes much more interesting, because we'll have the monitoring needed to safely introduce a new model version.

Once you've implemented and tested everything above, tell me **"Task 22 done."**

```


========================================================================


## Task 23 — Canary / Blue-Green Deployment & Rollback

### 🎯 Goal

Learn how production systems safely release a new version without immediately sending 100% of traffic to it.

Your deployment progression will be:

```text
v1 — currently serving traffic
        ↓
deploy v2
        ↓
test v2
        ↓
send small amount of traffic to v2
        ↓
monitor
        ↓
healthy → increase traffic
        ↓
100% v2
```

If v2 has problems:

```text
v2 unhealthy
   ↓
rollback
   ↓
v1 receives traffic again
```

---

### Part 1 — Understand the two strategies

#### Canary

Both versions run simultaneously:

```text
                 ┌──→ v1 (90%)
Load Balancer ──┤
                 └──→ v2 (10%)
```

Gradually:

```text
90/10
  ↓
75/25
  ↓
50/50
  ↓
10/90
  ↓
0/100
```

The exact percentages aren't important for our local exercise. The important concept is **gradual exposure**.

#### Blue-Green

Two complete environments:

```text
             Load Balancer
                  │
          ┌───────┴───────┐
          ↓               ↓
       Blue v1         Green v2
       ACTIVE          STANDBY
```

Initially:

```text
100% → Blue
```

After validating Green:

```text
100% → Green
```

Rollback:

```text
100% → Blue
```

**Blue-green is essentially a traffic switch between two environments.**

---

# Part 2 — Our Kubernetes implementation

Since you're already using Kubernetes for the FastAPI service, we'll practice this there.

First, check your current deployment:

```bash
kubectl get deployments
kubectl get pods
kubectl get service
```

You should have something similar to:

```text
recommendation-service
```

Now we're going to create a **v2 image**.

---

## Part 3 — Create model/service v2

Make a small visible change so we can tell v1 and v2 apart.

For example, temporarily change your health endpoint:

```python
@app.get("/health")
def health():
    return {
        "status": "healthy",
        "version": "v2"
    }
```

Don't change your actual recommendation logic yet.

Build a separate image:

```bash
docker build -t recommendation-service:v2 .
```

Verify:

```bash
docker images
```

You should see:

```text
recommendation-service   v2
recommendation-service   latest
```

---

# Part 4 — Create a v2 Kubernetes Deployment

Create:

```text
k8s/deployment-v2.yaml
```

The important difference is the labels.

Your existing v1 might have:

```yaml
labels:
  app: recommendation-service
  version: v1
```

For v2:

```yaml
labels:
  app: recommendation-service
  version: v2
```

And:

```yaml
spec:
  replicas: 1
```

Use:

```yaml
image: recommendation-service:v2
```

### Important concept

The Kubernetes Service should select:

```yaml
selector:
  app: recommendation-service
```

**not:**

```yaml
selector:
  app: recommendation-service
  version: v2
```

Why?

Because eventually we want the Service to be able to route to both versions.

---

# Part 5 — Deploy v2

Apply:

```bash
kubectl apply -f k8s/deployment-v2.yaml
```

Then:

```bash
kubectl get pods --show-labels
```

You should now see something like:

```text
recommendation-service-v1   Running   app=recommendation-service,version=v1
recommendation-service-v2   Running   app=recommendation-service,version=v2
```

Now you have:

```text
                 Service
                    │
          ┌─────────┴─────────┐
          ↓                   ↓
        v1 pods             v2 pods
```

---

# Part 6 — Test v2 independently

Before allowing normal traffic to v2, test it directly.

We'll use port forwarding to the v2 deployment:

```bash
kubectl port-forward deployment/recommendation-service-v2 8001:8000
```

Then open:

```text
http://localhost:8001/health
```

You should see:

```json
{
  "status": "healthy",
  "version": "v2"
}
```

This demonstrates an important production practice:

> **Never expose a new version to production traffic before validating it independently.**

---

# Part 7 — Rollback

Now imagine v2 has a serious problem.

For example:

```text
v2 → high latency
v2 → errors
v2 → incorrect recommendations
```

We want to immediately return to v1.

For our exercise, remove v2:

```bash
kubectl delete deployment recommendation-service-v2
```

Check:

```bash
kubectl get pods
```

v1 remains running.

That's our first basic rollback.

---

# Part 8 — The production concept

In a real deployment pipeline, rollback usually isn't:

```text
delete v2
```

Instead, we have:

```text
                    Deployment
                        │
             ┌──────────┴──────────┐
             ↓                     ↓
           v1.4                  v1.5
          stable                 canary
             │                     │
             └────── monitoring ───┘
                        │
                 error rate ↑
                        ↓
                     ROLLBACK
                        ↓
                     v1.4
```

And your **CI/CD pipeline** from Task 20 eventually becomes:

```text
Git Push
   ↓
Tests
   ↓
Docker Build
   ↓
Image Registry
   ↓
Deploy v2
   ↓
Health Checks
   ↓
Canary
   ↓
Monitor
   ↓
 ┌───────────────┐
 │               │
Healthy       Unhealthy
 │               │
 ↓               ↓
Increase       Rollback
Traffic          ↓
 │              v1
 ↓
100% v2
```

### Task 23 checklist

For now, implement these:

* [ ] Create a visible v2 change
* [ ] Build `recommendation-service:v2`
* [ ] Create separate Kubernetes v2 Deployment
* [ ] Run v1 and v2 simultaneously
* [ ] Test v2 independently
* [ ] Understand Service selectors
* [ ] Remove/rollback v2
* [ ] Verify v1 continues serving

**Don't worry about implementing sophisticated 10%/90% traffic splitting yet.** We'll first make sure you understand the deployment mechanics.


```bash

docker build -t recommendation-service:v1 .
# with SERVICE_VERSION baked via K8s env is enough; rebuild same Dockerfile for :v2 tag
docker build -t recommendation-service:v2 .
kubectl apply -f k8s/deployment.yaml -f k8s/deployment-v2.yaml -f k8s/service.yaml
kubectl get pods --show-labels
kubectl port-forward deployment/recommendation-service-v2 8001:8000
# GET http://localhost:8001/health → version v2
kubectl delete deployment recommendation-service-v2
kubectl get pods   # only v1 remains
.\.venv\Scripts\python -m pytest -q
```


=======================================================

## Task 23 Clarification


Exactly — **in a real production setup, you should NOT create `deployment-v2.yaml`, then `deployment-v3.yaml`, then `deployment-v4.yaml` manually every time.**

That was only an educational exercise to help you understand what a second version looks like.

### What happens in real life?

You normally have **one Deployment definition**:

```text
k8s/
├── deployment.yaml
└── service.yaml
```

The version changes through the **container image tag**.

For example:

```yaml
image: recommendation-service:v1
```

Then v2:

```yaml
image: recommendation-service:v2
```

Then v3:

```yaml
image: recommendation-service:v3
```

You don't create a new YAML file for every version.

---

## But how does Kubernetes release v3 safely?

This is where **rolling deployments, canary deployments, and blue-green deployments** come in.

### Normal Kubernetes rolling deployment

Suppose you're running:

```text
3 × v1 pods
```

You change the image:

```text
v1 → v2
```

Kubernetes gradually replaces the pods:

```text
v1  v1  v1
 ↓
v2  v1  v1
 ↓
v2  v2  v1
 ↓
v2  v2  v2
```

Then when v3 comes:

```text
v2  v2  v2
 ↓
v3  v2  v2
 ↓
v3  v3  v2
 ↓
v3  v3  v3
```

Same Deployment.

---

## So why did I ask you to create `deployment-v2.yaml`?

Because we're **learning the concept manually first**.

I wanted you to physically see:

```text
v1 Deployment
       +
v2 Deployment
       ↓
two versions running
```

That's useful for understanding blue-green/canary architecture.

But **we should not continue creating one YAML file per version.**

---

# How this eventually works with CI/CD

Your workflow from Task 20 will eventually look more like:

```text
Developer
   ↓
git push
   ↓
CI
 ├── pytest
 ├── lint
 └── Docker build
       ↓
recommendation-service:v3
       ↓
Container Registry
       ↓
CD
       ↓
Kubernetes Deployment
       ↓
Canary / Rolling / Blue-Green
       ↓
Monitor
       ↓
Healthy?
  ┌───────┴───────┐
 YES              NO
  ↓                ↓
100% v3         Rollback
                   ↓
                  v2
```

And rollback can be extremely convenient with Kubernetes:

```bash
kubectl rollout undo deployment recommendation-service
```

You can inspect rollout history:

```bash
kubectl rollout history deployment recommendation-service
```

And check status:

```bash
kubectl rollout status deployment recommendation-service
```

---

### One important distinction

**Rolling deployment ≠ Canary ≠ Blue-Green**

They're different strategies:

| Strategy   | Basic idea                                            |
| ---------- | ----------------------------------------------------- |
| Rolling    | Gradually replace old pods with new pods              |
| Canary     | Send a small percentage of traffic to new version     |
| Blue-Green | Keep two environments and switch traffic between them |

For **Task 23**, we're learning Canary/Blue-Green, so I had you create v2 separately to make the concept visible.

But after we finish Task 23, your normal Kubernetes workflow should be **one Deployment manifest + new image versions**, not a new YAML file for every release.

So your question is absolutely correct — **you should not have to manually create `deployment-v3.yaml` every time.**



======================================================


Excellent. **Task 23 — Canary / Blue-Green Deployment & Rollback: ✅ DONE**

You now understand:

* Rolling vs Canary vs Blue-Green deployments
* Running multiple application versions
* Kubernetes Deployment vs Service
* Safe release of a new version
* Independent validation of a new version
* Rollback using Kubernetes
* Why you don't create `deployment-v3.yaml`, `deployment-v4.yaml`, etc. for every release
* How CI/CD eventually automates the whole process

### 🚀 Next: Task 24 — Horizontal Scaling & Load Testing

We'll make the recommendation service behave more like a real production service:

```text
                 Load
                  ↓
          Kubernetes Service
                  ↓
       ┌──────────┼──────────┐
       ↓          ↓          ↓
     FastAPI    FastAPI    FastAPI
      Pod 1      Pod 2      Pod 3
       │          │          │
       └──────────┼──────────┘
                  ↓
          Redis / PostgreSQL
```

We'll cover:

1. Why horizontal scaling works
2. Load testing the API
3. Identifying bottlenecks
4. Kubernetes replica scaling
5. CPU/memory resource requests and limits
6. Horizontal Pod Autoscaler (HPA)
7. Understanding when **3 replicas aren't enough**
8. Basic throughput and latency measurements

This will connect your Kubernetes knowledge with the **billion-user scalability** concepts we're building toward.


=================


Yes — **you already implemented the basic horizontal scaling in Task 13** when you changed:

```yaml
replicas: 1
```

to:

```yaml
replicas: 3
```

So Task 24 shouldn't repeat that. Your understanding is correct: **the purpose now is to test the application under load and observe when/how scaling should happen.**

### What Task 24 should actually teach

Think of it as:

```text
                Load Test
                   ↓
             Kubernetes Service
                   ↓
        ┌──────────┼──────────┐
        ↓          ↓          ↓
      Pod 1      Pod 2      Pod 3
        │          │          │
        └──────────┼──────────┘
                   ↓
             Measure:
          ├── Requests/sec
          ├── Latency
          ├── Errors
          └── CPU / Memory
```

Then we ask:

> **What happens when 3 pods aren't enough?**

There are two different things:

### 1. Manual scaling

You already did this:

```bash
kubectl scale deployment recommendation-service --replicas=5
```

Now Kubernetes runs 5 pods.

This is useful when **you know** you need more capacity.

### 2. Automatic scaling — HPA

This is the important new part.

Instead of you doing:

```text
Load increases
     ↓
You notice it
     ↓
You manually increase replicas
```

we want:

```text
Load increases
     ↓
CPU increases
     ↓
HPA detects threshold
     ↓
3 pods → 5 pods
     ↓
Load decreases
     ↓
5 pods → 3 pods
```

That's **Horizontal Pod Autoscaling**.

---

## So I would modify Task 24

Rather than spending the task re-learning replicas, we'll do:

**Task 24 — Load Testing + Kubernetes HPA**

### Part A — Load test

Generate traffic against your FastAPI service.

We'll measure:

* requests per second
* average latency
* p95 latency
* errors
* CPU utilization

### Part B — Establish baseline

For example:

```text
3 pods
100 requests/sec
CPU: 35%
p95: 80ms
```

Then increase traffic.

### Part C — HPA

Configure something like:

```text
minReplicas: 3
maxReplicas: 10
targetCPUUtilization: 70%
```

Then generate enough traffic to push CPU above the target.

Kubernetes should automatically increase the pods.

### Part D — Watch it happen

You'll use:

```bash
kubectl get hpa
```

and:

```bash
kubectl get pods -w
```

So you'll actually see:

```text
3 pods
 ↓
4 pods
 ↓
5 pods
 ↓
...
```

Then stop the load and observe scale-down.

---

### One important thing

**Don't manually increase replicas during the HPA test.**

The point is to let Kubernetes make the decision.

So yes, your intuition was right:

> **Task 13 = manually scale replicas.**
> **Task 24 = prove the need for scaling with load testing, then automate scaling with HPA.**

That's a much better progression for your project.

