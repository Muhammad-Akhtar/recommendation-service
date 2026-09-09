# Task 20 implementation details
_Exported on 9/9/2026 at 15:27:42 GMT+5 from Cursor (3.17.19)_

---

**User**

Take reference from @Task16_to_19_cursor_api_recommendations.md 
https://github.com/Muhammad-Akhtar/recommendation-service.git  is the url of github I wanna push the code this would be first push

Implement following Task 20 

@Readme.md (5082-5392) from @Readme.md file. 

Implement it carefully and add the implementation details inside @implementation_Readme_3.md file

---

**Cursor**

I'll implement Task 20 (CI pipeline) carefully, using the Task 16–19 notes as reference, then document it in `implementation_Readme_3.md` and prepare the first push to your GitHub repo.

Next I'll check the Task 16–19 reference style, tests, and Dockerfile so the CI workflow matches the project.

Tests pass. Creating the CI workflow, a root `.gitignore`, and Task 20 docs, then initializing git for the first push.

Updating `implementation_Readme_3.md` with Task 20 details.

Initializing git and preparing the first push to GitHub.

Need approval to merge the remote’s existing LICENSE commit with our local history before the first push.

---

**User**

you forgot to add gitignore file do we neeed it?

---

**Cursor**

We did add a `.gitignore` — I'll confirm it's present and whether the push finished.

Yes — you need it, and it’s already there.

`.gitignore` is in the repo (committed and pushed with the first push). It’s what keeps local junk out of GitHub:

- `.venv/` — virtualenv (huge, machine-specific)
- `.pytest_cache/`, `__pycache__/` — test/Python caches
- `.env` — secrets
- `*.tar` — e.g. the ~60MB `recommendation-service.tar` we excluded

Without it, those would get committed and bloat/break the repo. Task 20 doesn’t require `.gitignore` in the Readme checklist, but it’s standard for any real push — and CI still only installs from `requirements.txt`, so excluding `.venv` is correct.

---

**User**

<timestamp>Wednesday, Sep 9, 2026, 11:12 AM (UTC+5)</timestamp>
<system_notification>
The following task has finished. If you were already aware, ignore this notification and do not restate prior responses.

<task>
kind: shell
status: success
task_id: 932999
title: First push of code to GitHub
tool_call_id: call-a3c44be4-abeb-4613-910d-4e8f959161dd-29
fc_968edd49-8610-9877-b625-4723bfc7c6af_0
output_path: C:\Users\saimh\.cursor\projects\c-Projects-recommendation-service\terminals\932999.txt
</task>
</system_notification>
<user_query>Briefly inform the user about the task result and perform any follow-up actions (if needed). If there's no follow-ups needed, don't explicitly say that.</user_query>

---

**Cursor**

First push succeeded: `master` is on [github.com/Muhammad-Akhtar/recommendation-service](https://github.com/Muhammad-Akhtar/recommendation-service.git) (`dc99627..7d79440`).

CI should be running under **Actions** — open that tab to confirm pytest and the Docker build pass.

---

**User**

Just asking
Ok so model get data from redis + postgres, where is that code? and after ranking is it setting to redis for fast availability

where these line of code exists. can you tell me in this chat only

---

**Cursor**

I'll point you to the exact spots in the serving path—Redis features, Postgres candidates, ranking, and any cache write-back.

**Where Redis + Postgres feed the model**

Orchestration is in `app/recommendation_service.py`:

```27:37:app/recommendation_service.py
    features = await get_user_features(user_id, redis_client)

    pool = get_pool()
    async with pool.acquire() as connection:
        candidates = await get_recommendation_items(connection, limit=20)
    ...
    model = get_model(model_version)
    recommendations = model.predict(features, candidates)
```

| Input | Where | What |
| --- | --- | --- |
| Redis features | `get_user_features` in `app/feature_store.py` (~lines 23–31) | key `features:user:{id}` |
| Postgres candidates | `get_recommendation_items` in `app/recommendation_repository.py` (~lines 31+) | table `recommendation_items` |
| Ranking | `model.predict(...)` in `app/model.py` | v1/v2 ranking |

That service is called from `app/main.py` on cache miss (~lines 196–203).

---

**After ranking — is it written back to Redis?**

Yes — as a **response cache**, not as features.

In `app/main.py` after `generate_recommendations`:

```205:209:app/main.py
                await redis_client.set(
                    cache_key,
                    response.model_dump_json(),
                    ex=settings.cache_ttl,
                )
```

Key is `cache:recommendations:{user_id}` (see `_cache_key` ~line 46). Next request hits cache first (~lines 182–189) and skips Redis features + Postgres + model until TTL expires.

**Not** the same as feature Redis: features stay at `features:user:*` (updated by the Kafka consumer), while ranked results go to `cache:recommendations:*`.

---

**User**

Perfect so orchestration is in Separate file that's good now, the click and purchases and last_item these count are stored in redis, are these through a background job or just on hit of api call these are stored? 

---

**Cursor**

Confirming the write path for those Redis feature counters.

**Neither on the recommendations GET, nor synchronously inside that API.** They’re updated by the **Kafka consumer** (a background-style service).

Flow:

1. **`POST /interactions`** — API validates and publishes the event to Kafka (does not bump Redis counters itself).
2. **`kafka-consumer`** (separate process in Compose) reads the topic and:
   - writes history to Postgres (`save_user_event`)
   - then updates Redis features (`apply_interaction_event` in `feature_store.py`) — click/purchase/`last_item_id`

So those counts land in Redis **asynchronously after the interaction event**, via the consumer pipeline — not when someone hits `GET /recommendations/{user_id}`. That GET only **reads** `features:user:*` (and may cache the ranked list under `cache:recommendations:*`).

---

**User**

this manual testing workflow is helpful can you add it into a readme.md file I
Like how history, interactions and other things can be simulated and tested manually, by doing what action. 

give different api calls payload and possible results as well. as a QA Intern I have to verify it against some data as well. through manual testing understand the system. 

keep it simple and easy to understand, I want to understand and test kafka and  database schemas and data coming and going into it and at the  end how model is predicting 

---

**Cursor**

I'll pull the live API routes, payloads, and store schemas so the QA manual-test guide matches what the system actually does.

Fixing the v2 switch instructions — the Compose `-e` example was incorrect.

Created **`Manual_Testing_Readme.md`** at the project root — a QA-oriented manual test guide.

It covers:

1. **Flow diagram** — API → Kafka → Postgres history + Redis features → model → cache  
2. **Start / seed / `/ready` checks**  
3. **API cheat sheet** with payloads and expected JSON  
4. **Scenarios** — fresh user interactions, v1 ranking, v2 last-item boost, cache hit, validation 422  
5. **Direct checks** — Redis keys, Postgres SQL, consumer logs  
6. **Copy-paste happy-path script** + checklist  

Use a fresh `user_id` (e.g. `9001`) each run so results stay easy to verify.

---

**User**

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


do it, and add the implementation details inside @implementation_Readme_3.md file as well.

---

**Cursor**

I'll implement Task 21 observability step by step—checking the Readme for specifics, then wiring structured logging, request IDs, metrics, and tracing.

Implementing observability modules and wiring them into the recommendation path without changing ranking logic.

Removing duplicate `event=` kwargs that conflict with structlog's positional event argument.

All tests passed. Updating `implementation_Readme_3.md` and adding optional observability env vars to Compose.

PowerShell mangled the insert — writing the Task 21 section via a file instead.

**Task 21 done.**

Observability is wired in without changing recommendation logic. Summary:

| Piece | What |
| --- | --- |
| Structured logs | `structlog` JSON (`cache_hit`, `redis_unavailable`, `recommendation_served`, …) |
| Correlation ID | `X-Request-ID` middleware → bound into every log line |
| Metrics | Prometheus counters/histogram + `GET /metrics` |
| Tracing | OpenTelemetry spans (Redis / Postgres / model); exporter `none` by default, `console` optional |
| Tests | `tests/test_observability.py` — **35 passed** total |

New modules: `app/logging_config.py`, `app/middleware.py`, `app/metrics.py`, `app/tracing.py`.

Details are in `implementation_Readme_3.md` (Task 21 section), including how to debug with a request ID and how to stop Redis to watch failure logs/metrics.

---

**User**

Perfect now Task 22 
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


all of it, kindly carefully  implement it. also update our @implementation_Readme_3.md file as well after those.



---

**Cursor**

I'll implement Task 22 carefully—prediction logging, model metrics, drift detection off the request path, and CTR quality signals—then document it in `implementation_Readme_3.md`.

Implementing prediction logging, drift utilities, CTR quality tracking, and wiring them into the service path.

All 48 tests passed. Updating `implementation_Readme_3.md` with Task 22 documentation.

**Task 22 done.**

Model monitoring is in place without putting drift on the hot path. What’s included:

| Area | Implementation |
| --- | --- |
| Prediction log | `app/prediction_logger.py` → `PredictionLog` + structured `prediction_logged` |
| Metrics | latency, errors, `recommendation_count`, served/clicked counters (by `model_version`) |
| Drift (offline) | `app/drift.py` → `detect_drift(12,10)=False`, `detect_drift(20,10)=True` |
| CTR quality | impressions in Redis `last_recs:{user}`, clicks attributed on `POST /interactions` |
| Compare v1/v2 | `GET /monitoring/model-quality` |
| Tests | `test_drift.py`, `test_model_monitoring.py` — **48 passed** |

Docs updated in `implementation_Readme_3.md` (overview, layout, full Task 22 section).

---

**User**

Perfect now the Task 21 and Task 22 how can i see the logs and regenerate the cases to see the logs for application and model both. 
Analyze the @Manual_Testing_Readme.md file it is perfect just append similar guide for this qa intern how can he analyze the logs and different cases to handle inside logs. In short real world simulation so that these features seems useful.

---

**Cursor**

Appending a Task 21–22 log-analysis and simulation section to `Manual_Testing_Readme.md`, matching the existing QA style.

Appended **Part B (Task 21 + 22)** to [`Manual_Testing_Readme.md`](Manual_Testing_Readme.md).

It covers how to:

1. **Watch logs** — `docker compose logs -f app` + search by `X-Request-ID`
2. **Event cheat sheet** — application (`cache_hit`, `redis_unavailable`, …) vs model (`prediction_logged`, `recommendation_clicked`)
3. **Real cases** — miss→model→hit, features in prediction logs, Redis down + fallback, metrics, CTR attribution, offline drift
4. **Copy-paste demo script** + checklist

Fastest path for a QA intern: open logs in one terminal, run **§23 Mini script**, then search the printed `request_id`s.

---

**User**

@Readme.md (6027-6052) in @Readme.md file, need to implement task 23 now already we have covered graceful degratation at some level but now for the whole app we have to do it. 

Kindly carefully follow the insturctions and implement it in code without breaking any existing functionality. 

After completing the implementation add Analyze the @implementation_Readme_3.md file and create a new file named implementation_Readme_4.md and similar mannner add the implementation details in that file as well. 

---

**Cursor**

I'll read Task 23 in `Readme.md` and the current serving path so we can add timeouts, retries, circuit breakers, and bulkheads without changing recommendation behavior.

Task 23 is high-level: apply timeouts, retries, circuit breakers, degradation, and bulkheads across Redis, Postgres, Kafka, and the model. I'll inspect those call sites next.

---

**User**

You're right — I mixed up the roadmap. **Task 23 is Canary / Blue-Green Deployment and Rollback.** We should continue from there.

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




---

**Cursor**

I'll inspect the current Kubernetes manifests and health endpoint so the Task 23 canary/blue-green plan matches what you already have.

Current K8s setup is a single unlabeled Deployment + Service selecting `app: recommendation-service`. Planning Task 23 as canary/blue-green with a visible v2 health marker and dual Deployments.

---

**User**

Implement the plan as specified, it is attached for your reference. Do NOT edit the plan file itself.

To-do's from the plan have already been created. Do not create them again. Mark them as in_progress as you work, starting with the first one. Don't stop until you have completed all the to-dos.

---

**Cursor**

Implementing Task 23 per the plan—starting with the service version on `/health`.

**Task 23 done.** Canary / blue-green mechanics are in place without changing recommendation logic.

| Change | Detail |
| --- | --- |
| Deploy identity | `SERVICE_VERSION` → `/health` returns `{status, version}` |
| K8s v1 | [`k8s/deployment.yaml`](k8s/deployment.yaml) → `recommendation-service-v1` |
| K8s v2 | [`k8s/deployment-v2.yaml`](k8s/deployment-v2.yaml) added |
| Service | Still selects `app: recommendation-service` only |
| Docs | [`implementation_Readme_4.md`](implementation_Readme_4.md) + Part 3 cross-link |
| Tests | **50 passed** |

Quick exercise: build `:v1` / `:v2`, apply both Deployments, port-forward v2 on `8001` to confirm `version=v2`, then `kubectl delete deployment recommendation-service-v2` to roll back.

---

**User**

@Readme.md (6621-6846) 

Also previous for the sake of understanding we create v2 deployment k8s files, if those cause any isssue fix those as well and add implementation details inside @implementation_Readme_4.md file

---

**Cursor**

I'll implement Task 24 (load testing + HPA), fix any Task 23 v2 Deployment issues, and document it in `implementation_Readme_4.md`.

Updating K8s manifests for HPA (resources + stable v1 baseline), adding a load-test script and HPA config, and documenting Task 24.

**Task 24 done**, and the Task 23 v2 Deployments are cleaned up for load/HPA use.

### Fixes for v2 / canary vs scaling
- **v2 is canary-only** — comments in `deployment-v2.yaml`; delete it before HPA so the Service doesn’t split traffic
- **v1 baseline** — 3 replicas + CPU/memory requests/limits (required for HPA)
- **Faster probes** + `REDIS_TIMEOUT=0.2`
- **Soft Postgres init** — pods still start if DB isn’t in-cluster

### Task 24 additions
| Piece | Path |
| --- | --- |
| HPA | [`k8s/hpa.yaml`](k8s/hpa.yaml) → scales `recommendation-service-v1` (3–10, CPU 50%) |
| Load test | [`scripts/load_test.py`](scripts/load_test.py) → RPS / avg / p95 / errors |
| CPU demo | `GET /demo/cpu-burn` (for HPA demos; `/health` alone is too cheap) |
| Docs | [`implementation_Readme_4.md`](implementation_Readme_4.md) |

### Tests
**52 passed**

Before HPA practice:

```powershell
kubectl delete deployment recommendation-service-v2 --ignore-not-found
kubectl apply -f k8s/deployment.yaml -f k8s/service.yaml -f k8s/hpa.yaml
```

---

**User**

Perfect, 

now analyze my application that we have implemented, 

does it contain all below features and mentioned are represented the correct flow and architecture, if any change needed then do it and create a new file name system_architecture.md and paste everything into it the flows and architectures 

Yes — **Task 25 is the final production architecture**, not Resource Management.

You have completed the individual building blocks, so this task is about putting everything together and being able to **explain the architecture like a senior backend engineer/system designer**.

# Task 25 — Final Production Architecture

### 🎯 Goal

Take everything you've built from Tasks 1–24 and understand the complete production system:

```text
                         ┌──────────────────────┐
                         │      Clients         │
                         │ Web / Mobile / APIs  │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ Load Balancer /      │
                         │ Ingress              │
                         └──────────┬───────────┘
                                    │
                                    ▼
                 ┌─────────────────────────────────────┐
                 │       Kubernetes Cluster             │
                 │                                     │
                 │   Recommendation Service             │
                 │                                     │
                 │  ┌────────┐ ┌────────┐ ┌────────┐  │
                 │  │FastAPI │ │FastAPI │ │FastAPI │  │
                 │  │ Pod 1  │ │ Pod 2  │ │ Pod 3  │  │
                 │  └───┬────┘ └───┬────┘ └───┬────┘  │
                 │      │          │          │        │
                 │      └──────────┼──────────┘        │
                 │                 │                   │
                 │              Service                │
                 │                 │                   │
                 │              HPA                    │
                 └─────────────────┼───────────────────┘
                                   │
              ┌────────────────────┼─────────────────────┐
              │                    │                     │
              ▼                    ▼                     ▼
           Redis              PostgreSQL              Kafka
              │                    │                     │
              │                    │              ┌──────┴──────┐
              │                    │              │             │
              │                    │              ▼             ▼
              │                    │        Feature       Event
              │                    │        Processor     Consumers
              │                    │
              │                    ▼
              │              Candidate Data
              │              Predictions
              │              Event History
              │
              ▼
       Online Features /
       Recommendation Cache

                         ┌───────────────────────┐
                         │ ML Model              │
                         │ v1 / v2 / v3          │
                         └───────────┬───────────┘
                                     │
                                     ▼
                              Ranked Results
```

---

# 1. Request flow

You should now be able to explain this flow without looking at your code:

```text
GET /recommendations/123
        ↓
Kubernetes Service
        ↓
FastAPI Pod
        ↓
RecommendationService
        ↓
Redis
   ├── recommendation cache HIT
   │       ↓
   │     return
   │
   └── MISS
        ↓
     Redis Features
        ↓
     PostgreSQL Candidates
        ↓
     ML Model
        ↓
     Ranked recommendations
        ↓
     Redis result cache
        ↓
     Response
```

If Redis fails:

```text
Redis
  ↓
failure
  ↓
PostgreSQL / fallback
  ↓
recommendations
```

If deeper dependencies fail:

```text
Personalized recommendations
          ↓
      unavailable
          ↓
Popular recommendations
          ↓
       Response
```

The fundamental production principle you've implemented is:

> **A dependency failure should degrade recommendation quality rather than take down the API.**

---

# 2. Event flow

Your Kafka architecture should be understood separately from the synchronous request path.

```text
User
 ↓
view / click / purchase
 ↓
Kafka
 ↓
user-interactions
 ↓
 ┌───────────────────────┐
 │                       │
 ▼                       ▼
PostgreSQL          Feature Processor
 │                       │
 ▼                       ▼
Event History           Redis
                         │
                         ▼
                  Online Features
```

Kafka allows these consumers to operate independently.

For example:

```text
Consumer Group A → PostgreSQL
Consumer Group B → Feature Store
Consumer Group C → Analytics
Consumer Group D → Model monitoring
```

A new consumer shouldn't require changing the producer.

---

# 3. Data responsibilities

This is particularly important for interviews.

### PostgreSQL

**Durable/system of record**

Stores things such as:

* recommendation candidates
* recommendation history
* user event history
* prediction history
* durable application data

### Redis

**Low-latency online data**

Used for:

* recommendation result cache
* online user features
* frequently accessed data

### Kafka

**Event backbone**

Used for:

* user interactions
* asynchronous processing
* decoupling services
* event-driven architecture

### ML model

**Ranking logic**

It should not directly access:

```text
Redis
PostgreSQL
Kafka
```

Instead:

```text
Service
 ├── gets features
 ├── gets candidates
 └── calls model
          ↓
      ranked results
```

That's a very important separation of responsibilities.

---

# 4. Scaling architecture

You've already implemented manual replicas and HPA.

So your production scaling story is:

```text
                    Traffic
                       ↓
                 Load Balancer
                       ↓
                Kubernetes Service
                       ↓
          ┌────────────┼────────────┐
          ▼            ▼            ▼
        Pod 1        Pod 2        Pod 3
          │            │            │
          └────────────┼────────────┘
                       │
                      HPA
                       │
              Traffic increases
                       ↓
             3 → 5 → 8 → 10 pods
```

The FastAPI service is **stateless**, so any pod can handle any request.

State lives outside the application process.

That's one of the biggest architectural decisions you've made.

---

# 5. Deployment architecture

You've also covered safe deployments.

```text
Git
 ↓
CI
 ├── pytest
 ├── validation
 └── Docker build
 ↓
Container Registry
 ↓
Kubernetes
 ↓
New version
 ↓
Canary / Blue-Green
 ↓
Health checks
 ↓
Metrics
 ↓
Healthy?
 ├── YES → increase traffic
 └── NO  → rollback
```

Your deployment should not depend on manually creating:

```text
deployment-v2.yaml
deployment-v3.yaml
deployment-v4.yaml
```

Instead:

```text
recommendation-service:v1
recommendation-service:v2
recommendation-service:v3
```

and deployment automation handles the release.

---

# 6. Observability

Your production architecture also needs:

```text
FastAPI
   │
   ├── Structured Logs ──────→ Log system
   │
   ├── Metrics ──────────────→ Prometheus → Grafana
   │
   └── Traces ───────────────→ OpenTelemetry backend
```

You should be able to answer:

> Why is this request slow?

Using:

```text
Request
 ↓
FastAPI
 ↓
Redis        5ms
 ↓
PostgreSQL  20ms
 ↓
Model       35ms
 ↓
Response
```

Instead of simply knowing:

```text
Request took 60ms
```

---

# 7. Model monitoring

Your model pipeline becomes:

```text
Prediction
    ↓
Model version
    ↓
Prediction logging
    ↓
Metrics
    ↓
CTR / latency / errors
    ↓
Drift detection
    ↓
Model evaluation
```

And because you track model versions:

```text
v1 → CTR 4.1%
v2 → CTR 5.3%
v3 → CTR 3.8%
```

you can make an informed deployment decision.

---

# 8. Fault tolerance

Your final architecture should have multiple levels of protection:

```text
Redis failure
    ↓
PostgreSQL / alternative source

PostgreSQL failure
    ↓
Cached recommendations

Model failure
    ↓
Previous/precomputed recommendations

Multiple dependencies unavailable
    ↓
Popular/trending recommendations

Kubernetes pod failure
    ↓
New pod

Traffic increases
    ↓
HPA

Bad deployment
    ↓
Rollback
```

The goal isn't:

> "Nothing ever fails."

The goal is:

> **"When something fails, the system continues providing the best possible service."**

---

# 9. Your complete project

At this point, your learning project has covered:

| Task   | Concept                              | Status         |
| ------ | ------------------------------------ | -------------- |
| 1      | FastAPI API                          | ✅              |
| 2      | Production structure/Pydantic/pytest | ✅              |
| 3      | Docker                               | ✅              |
| 4      | Redis caching                        | ✅              |
| 5      | Graceful Redis degradation           | ✅              |
| 6      | Docker Compose                       | ✅              |
| 7      | Recommendation fallback              | ✅              |
| 8      | Health/readiness                     | ✅              |
| 9      | Configuration                        | ✅              |
| 10     | Stateless architecture               | ✅              |
| 11     | Kubernetes                           | ✅              |
| 12     | Kubernetes probes                    | ✅              |
| 13     | Kubernetes scaling                   | ✅              |
| 14     | PostgreSQL                           | ✅              |
| 15     | Kafka                                | ✅              |
| 16     | Kafka partitions/groups              | ✅              |
| 17     | Schema Registry                      | ✅              |
| 18     | Feature Store                        | ✅              |
| 19     | Model serving/versioning             | ✅              |
| 20     | CI                                   | ✅              |
| 21     | Observability                        | ✅              |
| 22     | Model monitoring/drift               | ✅              |
| 23     | Canary/Blue-Green/Rollback           | ✅              |
| 24     | Load testing/HPA                     | ✅              |
| **25** | **Final production architecture**    | **🎯 CURRENT** |

## Your Task 25 exercise

Don't write new code initially.

I want you to **draw the architecture yourself** using paper, draw.io, Excalidraw, or whatever you prefer.

Include these components:

```text
Client
  ↓
Load Balancer
  ↓
Kubernetes
  ↓
FastAPI replicas
  ↓
Redis
PostgreSQL
Kafka
Feature Store
ML Model
Monitoring
CI/CD
```

Then draw **two flows**:

**Synchronous:**

```text
Request → Recommendation → Response
```

**Asynchronous:**

```text
User Event → Kafka → Consumers → PostgreSQL/Redis/Monitoring
```

Finally, explain these five questions in your own words:

1. **Why is FastAPI stateless?**
2. **Why do we use Redis if PostgreSQL exists?**
3. **Why do we need Kafka?**
4. **What happens if Redis goes down?**
5. **How do we safely deploy model v2 and roll it back?**

If you can explain those five clearly, **Task 25 is complete** — and more importantly, you'll have a coherent story for the entire project in a senior backend/system-design interview.


---

**Cursor**

I'll compare the implemented system against Task 25's architecture, fix any real gaps, then write `system_architecture.md` with the accurate flows.

Flows match the codebase. I'll correct outdated docs (`Goal.md`, endpoint docstring) and add an accurate `system_architecture.md` that separates implemented vs conceptual pieces.

**Task 25 analysis:** The claimed architecture matches what you built. No redesign was required.

### Verified as correct
- Sync path: cache → features + candidates → model → cache; fallbacks PG store → popular  
- Model has no direct Redis/Postgres/Kafka I/O  
- Async path: interactions → Kafka → one consumer → PG history + Redis features  
- Stateless FastAPI, K8s Service/HPA, CI, observability, canary, CTR/drift helpers  

### Clarified (not bugs)
- Multiple Kafka groups A–D = **production/interview target**; today **one group** does PG + Redis  
- Ingress / Prometheus / Grafana / Jaeger = **conceptual**; app already exposes logs/metrics/traces  
- Prediction history is logs/metrics, not a Postgres predictions table  

### Small updates made
- [`Goal.md`](Goal.md) — replaced outdated Client→Redis-only sketch  
- [`app/main.py`](app/main.py) — recommendations docstring matches full degrade chain  
- [`implementation_Readme_4.md`](implementation_Readme_4.md) — Task 25 row + link  

### New deliverable
**[`system_architecture.md`](system_architecture.md)** — full diagrams, sync/async flows, data roles, scaling, deploy, observability, monitoring, fault tolerance, implemented-vs-conceptual table, and the five interview answers.

---

**User**

Is there any retry circuit-breakers thing needed, we did not make any background job i guess so this might not be needed?

---

**Cursor**

You’re right that you don’t *need* them for this learning project — but not because of “no background job.”

### What you already have
Graceful **degradation** on the request path:

```text
Redis fail → Postgres store → popular list → still 200
```

That’s the main resilience story you’ve been building (Tasks 5–7, 25).

### Retries / circuit breakers — when they matter

| Pattern | Useful when | Your app today |
| --- | --- | --- |
| **Retry** | Transient blips (timeout, brief network glitch) on Redis/PG/Kafka | Not wired; Redis already has short timeouts + fallback |
| **Circuit breaker** | A dependency is *persistently* bad; stop hammering it | Not wired; you skip Redis/model and fall back instead |
| **Background job** | Async work that must eventually succeed (outbox, reprocess) | Kafka consumer *is* a long-running worker, but it already loops/reconnects simply |

So: **no background “job framework” ≠ “retries/breakers never apply.”** They usually protect **outbound calls** (Redis, Postgres, Kafka, HTTP), on both API pods and consumers.

### Do you need them now?
**No — not required for Task 25 completeness.** Your architecture is coherent without them:

- Fail open to lower-quality recommendations  
- Kafka consumer reconnects with a sleep loop  
- HPA / canary / observability cover other production concerns  

### When you’d add them later (senior next step)
- Retries with backoff on **Kafka publish** or **Postgres candidate fetch** (1–2 tries, only on timeout)  
- Circuit breaker around Redis so a slow Redis doesn’t burn request latency before fallback  
- Consumer: retry durable write, then DLQ — not infinite retry on poison messages  

**Bottom line:** You didn’t miss a required piece. Retries/circuit breakers are an optional hardening layer on top of degradation; your project already teaches the more important idea — *keep serving when dependencies fail.*

---

**User**

Retries with backoff on Kafka publish or Postgres candidate fetch (1–2 tries, only on timeout)

Circuit breaker around Redis so a slow Redis doesn’t burn request latency before fallback

Consumer: retry durable write, then DLQ — not infinite retry on poison messages


Kindly implement these if feasible in current implementations

---

**Cursor**

I'll add focused resilience: Redis circuit breaker, short retries on Kafka publish and Postgres candidate fetch, and consumer retry-then-DLQ for durable writes.

Implementing shared resilience helpers and wiring them into Redis, Kafka publish, Postgres fetches, and the consumer DLQ path.

Implemented all three patterns on top of your existing degrade path. **58 tests passed.**

### What was added

| Pattern | Where | Behavior |
| --- | --- | --- |
| **Redis circuit breaker** | Serve path (`main` + features) | After 3 failures → open; later calls fail fast → PG store / popular (no long Redis waits) |
| **Retry + backoff** | Kafka publish, PG candidates, consumer PG save | 2–3 attempts on **transient** errors only (timeouts/connections) |
| **Consumer DLQ** | `kafka_consumer` after durable-write retries | Publish Avro event to `user-interactions-dlq`, then continue (no infinite retry). Poison messages still skipped |

### New / updated files
- [`app/resilience.py`](app/resilience.py) — breaker + `retry_async`
- Wired in [`app/main.py`](app/main.py), [`app/recommendation_service.py`](app/recommendation_service.py), [`app/kafka_producer.py`](app/kafka_producer.py), [`app/kafka_consumer.py`](app/kafka_consumer.py)
- DLQ topic created in Compose `kafka-init`
- Tests: [`tests/test_resilience.py`](tests/test_resilience.py)
- Noted in [`system_architecture.md`](system_architecture.md)

Redis feature materialization after a successful PG write still soft-fails (history is durable; features can catch up later).

---

**User**

Now regarding this new implementation we did, have you updated the @implementation_Readme_4.md file as well, with simple and easy to understand what we did and how retry, or circuit thing and other behave. so have clear idea of system

---

**Cursor**

I updated `system_architecture.md` but not `implementation_Readme_4.md` yet — adding a clear resilience section there now.

Correct — it wasn’t in `implementation_Readme_4.md` before; it is now.

Added a full **“Resilience hardening — retry, circuit breaker, DLQ”** section covering:

- Why each tool exists (simple table)
- Circuit states (CLOSED → OPEN → HALF-OPEN) and how the API falls back
- Retry rules (transient only) + default attempts/env vars
- Consumer flow: retry PG → DLQ → continue; poison messages skipped
- How this sits **above** the existing degrade chain
- How to verify with pytest / Redis stop / metrics

Also updated the Part 4 overview table and project layout. Full diagrams stay in `system_architecture.md`; the tutorial-style walkthrough is in `implementation_Readme_4.md`.

