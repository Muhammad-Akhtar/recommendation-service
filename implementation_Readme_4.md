# Recommendation Service — Implementation Tutorial (Part 4)

This file continues from [`implementation_Readme_3.md`](implementation_Readme_3.md) (Tasks 17–22).

- Part 1 → Tasks 1–8 → [`implementation_Readme.md`](implementation_Readme.md)
- Part 2 → Tasks 9–16 → [`implementation_Readme_2.md`](implementation_Readme_2.md)
- Part 3 → Tasks 17–22 → [`implementation_Readme_3.md`](implementation_Readme_3.md)
- **Part 4 → Task 23 onward** (canary / blue-green, load testing + HPA, …)

---

## Overview (Part 4)

| Task | What we implemented |
| --- | --- |
| 23 | Canary / blue-green practice on Kubernetes: dual Deployments (v1 + v2), shared Service, independent validate, rollback |
| 24 | Load testing + Horizontal Pod Autoscaler (HPA) on stable v1; prove need for scaling under load |
| 25 | Final production architecture synthesis → [`system_architecture.md`](system_architecture.md) |
| 25b | Resilience hardening: Redis circuit breaker, retries with backoff, consumer DLQ |

Key principle (Task 23):

> **Never send 100% of production traffic to a new version before validating it — run it beside the stable version, then promote or roll back.**

Key principle (Task 24):

> **Task 13 = manually set replicas. Task 24 = measure under load, then let HPA scale automatically.**

Key principle (resilience):

> **Degrade quality when dependencies fail — and don’t wait forever on a dead Redis, transient blips, or poison Kafka messages.**

```text
v1 — currently serving
        ↓
deploy v2
        ↓
test v2 independently
        ↓
Service can reach both (app label)
        ↓
monitor
        ↓
healthy → keep / grow v2
unhealthy → delete v2 (rollback to v1)
```

---

## Project layout (after Task 25 + resilience)

```text
recommendation-service/
├── app/
│   ├── main.py                 # /health; circuit-wrapped Redis cache
│   ├── recommendation_service.py  # circuit on features; retry on PG candidates
│   ├── kafka_producer.py       # retry on publish; DLQ helper
│   ├── kafka_consumer.py       # retry durable write → DLQ
│   ├── resilience.py           # CircuitBreaker + retry_async
│   ├── metrics.py              # retries / circuit / dlq counters
│   ├── config.py               # attempts, thresholds, dlq topic
│   └── …
├── k8s/
│   ├── deployment.yaml
│   ├── deployment-v2.yaml
│   ├── service.yaml
│   └── hpa.yaml
├── scripts/
│   └── load_test.py
├── tests/
│   ├── test_health_version.py
│   ├── test_load_scaling.py
│   └── test_resilience.py
├── system_architecture.md
└── implementation_Readme_4.md
```

---

## Task 23 — Canary / Blue-Green Deployment & Rollback

### Topic / goal

Learn how production systems **safely release** a new version without flipping all traffic at once.

This task is about **deploy identity** (`SERVICE_VERSION` on `/health`), **not** ML `MODEL_VERSION` (Task 19). Ranking logic is unchanged.

### Part 1 — Two strategies (concepts)

#### Canary

Both versions run at once; traffic is exposed gradually:

```text
                 ┌──→ v1 (most traffic)
Load Balancer ──┤
                 └──→ v2 (small share)
```

Progression idea: `90/10 → 75/25 → 50/50 → 0/100`.

We do **not** implement weighted percentages yet (no Istio / Ingress weights). Locally, both pods sit behind one Service; kube-proxy will round-robin when both are Ready.

#### Blue-Green

Two full environments; switch all traffic when Green is validated:

```text
             Load Balancer
                  │
          ┌───────┴───────┐
          ↓               ↓
       Blue v1         Green v2
       ACTIVE          STANDBY → then ACTIVE
```

Rollback = point traffic back at Blue.

**For this exercise:** v1 = stable Deployment, v2 = new Deployment, rollback = `kubectl delete deployment recommendation-service-v2`.

### Architecture we implemented

```text
                 Service
           selector: app=recommendation-service
                    │
          ┌─────────┴─────────┐
          ↓                   ↓
   Deployment v1         Deployment v2
   version=v1            version=v2
   SERVICE_VERSION=v1    SERVICE_VERSION=v2
   image:…:v1            image:…:v2
```

**Important:** Service selects **`app` only**, not `version`. That way both Deployments can receive traffic. Pinning `version: v2` on the Service would lock you to one release and break canary.

Independent validation (before trusting shared traffic):

```text
kubectl port-forward deployment/recommendation-service-v2 8001:8000
        →
http://localhost:8001/health  →  {"status":"ok","version":"v2"}
```

### Files touched (Task 23)

| File | Action |
| --- | --- |
| `app/config.py` | `service_version: str = "v1"` (env `SERVICE_VERSION`) |
| `app/schemas.py` | `HealthResponse.version` optional field |
| `app/main.py` | `/health` returns deploy version |
| `k8s/deployment.yaml` | Renamed to **v1** Deployment + labels + env |
| `k8s/deployment-v2.yaml` | **Added** v2 Deployment |
| `k8s/service.yaml` | Still `selector.app: recommendation-service` |
| `tests/test_health_version.py` | Default + env override |

### Visible v2 change

`/health` returns deploy identity:

```json
{
  "status": "ok",
  "version": "v2"
}
```

Set per pod via Kubernetes env:

```yaml
env:
  - name: SERVICE_VERSION
    value: "v2"
```

### How to run / verify (Docker Desktop Kubernetes)

```powershell
docker build -t recommendation-service:v1 .
docker build -t recommendation-service:v2 .

kubectl delete deployment recommendation-service --ignore-not-found
kubectl apply -f k8s/deployment.yaml -f k8s/deployment-v2.yaml -f k8s/service.yaml
kubectl get pods --show-labels

kubectl port-forward deployment/recommendation-service-v2 8001:8000
# other terminal:
Invoke-RestMethod http://localhost:8001/health
# → version=v2

# Rollback
kubectl delete deployment recommendation-service-v2
kubectl get pods --show-labels
```

### Why we do **not** keep forever `deployment-v3.yaml`, `deployment-v4.yaml`, …

Canary files are for **learning simultaneous versions**. Day-to-day you usually update the **same** Deployment’s image tag. `deployment-v2.yaml` is a teaching artifact — remove it (or leave unused) after the canary exercise.

### Done checklist (Task 23)

- [x] Visible v2 change (`/health` deploy `version`)
- [x] Separate Kubernetes v2 Deployment
- [x] v1 + v2 simultaneously behind shared Service
- [x] Independent port-forward validation
- [x] Rollback by deleting v2
- [x] Documented in this file

**Task 23 in one sentence:** We run labeled v1 and v2 Deployments behind one Service, validate v2 alone via port-forward, and roll back by removing v2 — without changing recommendation logic.

---

## Task 23 follow-up — fixes before load testing (important)

Running **v1 + v2 forever** causes real problems for Task 24:

| Issue | Why it hurts | Fix |
| --- | --- | --- |
| Shared Service selector | Traffic splits across versions; latency/CPU metrics mix v1+v2 | Delete v2 before HPA/load tests |
| HPA target | HPA must scale **one** Deployment (`recommendation-service-v1`) | `k8s/hpa.yaml` → `scaleTargetRef.name: recommendation-service-v1` |
| No CPU requests | CPU HPA cannot compute utilization without `resources.requests.cpu` | Added requests/limits on v1 (and v2 for consistency) |
| Slow readiness | `initialDelaySeconds: 30` delayed Ready pods | Lowered for `/ready` (fallback still works without Redis/Postgres) |
| Postgres init crash | `init_db()` failure used to block app startup in K8s | Lifespan now logs and continues (graceful degradation) |

**Before Task 24:**

```powershell
kubectl delete deployment recommendation-service-v2 --ignore-not-found
kubectl apply -f k8s/deployment.yaml -f k8s/service.yaml -f k8s/hpa.yaml
kubectl get pods --show-labels
# expect only version=v1 pods (3 replicas)
```

Keep `k8s/deployment-v2.yaml` in the repo for the canary lesson; do not apply it during HPA demos.

---

## Task 24 — Load Testing + Kubernetes HPA

### Topic / goal

```text
Task 13  → you manually set replicas
Task 24  → load test proves pressure, HPA scales automatically
```

```text
                Load Test
                   ↓
             Kubernetes Service
                   ↓
        ┌──────────┼──────────┐
        ↓          ↓          ↓
      Pod 1      Pod 2      Pod 3   (v1)
        │          │          │
        └──────────┼──────────┘
                   ↓
             Measure RPS / latency / errors / CPU
                   ↓
                  HPA
             3 → 4 → 5 … → 10
```

### Files touched (Task 24)

```text
recommendation-service/
├── app/main.py                 # soft postgres init; GET /demo/cpu-burn
├── k8s/
│   ├── deployment.yaml         # replicas: 3 + resources + faster probes
│   ├── deployment-v2.yaml      # comments: canary-only; same resources
│   └── hpa.yaml                # ADDED — min 3 / max 10 / CPU 50%
├── scripts/load_test.py        # ADDED — concurrent HTTP load generator
└── tests/test_load_scaling.py  # ADDED
```

### Part A — Load test tool

[`scripts/load_test.py`](scripts/load_test.py) uses `httpx` (already in `requirements.txt`) and prints:

- requests / sec (RPS)
- average latency
- p95 latency
- error count / status codes

```powershell
# Terminal 1 — expose the Service
kubectl port-forward service/recommendation-service 8000:8000

# Terminal 2 — baseline (cheap endpoint)
.\.venv\Scripts\python scripts/load_test.py `
  --url http://localhost:8000/health `
  --concurrency 20 `
  --requests 500
```

Example output shape:

```text
=== Load test results ===
requests:     500
concurrency:  20
rps:          …
avg_ms:       …
p95_ms:       …
ok:           500
errors:       0
```

### Part B — Baseline with 3 pods

v1 Deployment baseline (Task 24):

```yaml
replicas: 3
resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "500m"
    memory: "256Mi"
```

Record a baseline row for yourself:

```text
3 pods
URL: /health or /demo/cpu-burn
RPS / avg / p95 / errors
kubectl top pods   # if metrics-server is up
```

### Part C — HPA

[`k8s/hpa.yaml`](k8s/hpa.yaml):

```yaml
scaleTargetRef:
  kind: Deployment
  name: recommendation-service-v1
minReplicas: 3
maxReplicas: 10
averageUtilization: 50   # CPU % of requests
```

Apply:

```powershell
kubectl apply -f k8s/hpa.yaml
kubectl get hpa
kubectl describe hpa recommendation-service-hpa
```

Check metrics-server (required):

```powershell
kubectl get deployment -n kube-system metrics-server
kubectl top nodes
kubectl top pods
```

If `kubectl top` fails, enable metrics-server / wait until it is Ready (Docker Desktop usually ships it).

### Part D — Generate enough CPU to scale

`/health` is often **too cheap** to push CPU to the HPA target. For demos we added:

```text
GET /demo/cpu-burn?duration_ms=80
```

Busy-waits briefly (clamped 1–500 ms). **Not** for product logic — only load/HPA practice.

```powershell
# Watch pods + HPA
kubectl get hpa -w
# other terminal:
kubectl get pods -l app=recommendation-service,version=v1 -w

# Generate load (do NOT manually kubectl scale during this test)
.\.venv\Scripts\python scripts/load_test.py `
  --url "http://localhost:8000/demo/cpu-burn?duration_ms=80" `
  --concurrency 40 `
  --requests 3000
```

Expect something like:

```text
3 pods → 4 → 5 → … (up to maxReplicas 10)
```

Stop the load and wait for scale-down (stabilization window ~60s in our HPA).

**Do not** run `kubectl scale` during the HPA demo — that defeats the lesson.

### Manual scale reminder (Task 13 — not Task 24)

When you **know** you need capacity (no HPA yet):

```powershell
kubectl scale deployment recommendation-service-v1 --replicas=5
```

Note the name is **`recommendation-service-v1`**, not the old Task 11 name `recommendation-service`.

### App changes that support K8s-only demos

1. **Soft `init_db`** — if Postgres is unreachable from the cluster, the process still starts; `/ready` can stay Ready via popular fallback.
2. **`REDIS_TIMEOUT=0.2`** on Deployments — Redis ping fails fast when Compose Redis is not in-cluster.
3. **`/demo/cpu-burn`** — controllable CPU for HPA.

Recommendation ranking / Kafka / feature-store paths are unchanged.

### Tests

```powershell
.\.venv\Scripts\python -m pytest -q
```

Includes:

- `tests/test_load_scaling.py` — cpu-burn response + lifespan survives DB init failure
- existing suite still green

### Done checklist

- [x] Understood Task 13 manual scale vs Task 24 HPA
- [x] Load test script (RPS / avg / p95 / errors)
- [x] v1 baseline: 3 replicas + CPU/memory requests & limits
- [x] HPA manifest (min 3, max 10, CPU target)
- [x] Documented: remove canary v2 before HPA
- [x] Watch commands (`kubectl get hpa`, `kubectl get pods -w`)
- [x] Soft DB init + demo CPU endpoint for realistic HPA demos
- [x] Documented in this file

**Task 24 in one sentence:** We load-test the Service, then let an HPA scale `recommendation-service-v1` by CPU — after removing the canary v2 Deployment so traffic and metrics stay on one target.

---

## Resilience hardening — retry, circuit breaker, DLQ

We already had **graceful degradation** (Redis down → Postgres store → popular).  
That is still the outer story. This section adds three small tools so the system fails **faster and cleaner**.

```text
                    BEFORE (degrade only)
Request → try Redis → (wait / error) → fallback

                    AFTER (+ circuit + retries)
Request → Redis breaker
            ├── CLOSED  → try Redis (normal)
            ├── OPEN    → skip Redis immediately → fallback
            └── failures count → OPEN after threshold

Kafka publish / PG candidates
            └── timeout? → retry 1–2 times with short backoff → then fail

Kafka consumer durable write
            └── retry a few times → still fail? → DLQ topic → continue
```

### 1) What problem each tool solves

| Tool | Everyday meaning | Where we use it |
| --- | --- | --- |
| **Retry + backoff** | “Maybe it was a blip — try once more, wait a tiny bit.” | Kafka publish, Postgres candidate fetch, consumer Postgres save |
| **Circuit breaker** | “Redis has been dying — stop calling it for a while so requests don’t stall.” | Redis cache get/set + online features on the API |
| **DLQ** | “This event couldn’t be saved — park it for humans/replay; don’t block the whole consumer.” | After consumer durable-write retries fail |

**Important:** Retries only run for **transient** errors (timeouts, connection resets). Logic bugs (`ValueError`, bad data) are **not** retried.

### 2) Files

| File | Role |
| --- | --- |
| `app/resilience.py` | `CircuitBreaker`, `retry_async`, `call_with_circuit`, Redis breaker singleton |
| `app/main.py` | Redis cache reads/writes go through the breaker |
| `app/recommendation_service.py` | Features via breaker; candidates via retry |
| `app/kafka_producer.py` | Publish with retry; `publish_to_dlq(...)` |
| `app/kafka_consumer.py` | Retry PG save → DLQ → return; Redis features soft-fail |
| `app/config.py` | Tunables (attempts, thresholds, DLQ topic name) |
| `app/metrics.py` | `resilience_retries_total`, `circuit_breaker_opened_total`, `kafka_dlq_messages_total` |
| `docker-compose.yml` | `kafka-init` also creates `user-interactions-dlq` |
| `tests/test_resilience.py` | Unit + serve-path + consumer DLQ tests |

### 3) Redis circuit breaker — how it behaves

States:

```text
CLOSED  →  calls Redis normally
             │
             │  too many failures (default 3)
             ▼
OPEN    →  do NOT call Redis; raise CircuitOpenError immediately
             │
             │  wait recovery window (default 30s)
             ▼
HALF-OPEN → allow one probe
             ├── success → CLOSED
             └── failure → OPEN again
```

On the recommendation API:

```text
GET /recommendations/{id}
        │
        ▼
Redis cache (via breaker)
   ├── HIT → return
   ├── MISS → model path (features also via breaker)
   └── OPEN / error
            ▼
     Postgres recommendations store
            ▼
     Popular fallback
```

So a **slow or dead Redis** no longer burns request latency on every call once the breaker is open — we fall back right away.

Defaults (`app/config.py` / env):

| Setting | Default | Meaning |
| --- | --- | --- |
| `REDIS_CIRCUIT_FAILURE_THRESHOLD` | `3` | Failures before OPEN |
| `REDIS_CIRCUIT_RECOVERY_SECONDS` | `30` | How long to stay OPEN |

### 4) Retry with backoff — how it behaves

```text
attempt 1 → fail (timeout)
     wait 0.05s
attempt 2 → success  ✓

or

attempt 1 → fail
     wait 0.05s
attempt 2 → fail → give up (caller handles fallback / error)
```

| Operation | Attempts (default) | Env |
| --- | --- | --- |
| Kafka publish | 2 | `KAFKA_PUBLISH_ATTEMPTS` |
| Postgres candidates | 2 | `POSTGRES_FETCH_ATTEMPTS` |
| Consumer PG `user_events` save | 3 | `CONSUMER_PG_ATTEMPTS` |
| Base delay | 0.05s | `RETRY_BASE_DELAY_SECONDS` |

Each retry increments metric `resilience_retries_total{operation=...}`.

### 5) Consumer DLQ — how it behaves

```text
Kafka message (valid Avro)
        ↓
Save to PostgreSQL user_events
   ├── success → materialize Redis features (best effort)
   │              └── Redis fail? log warning; history already saved
   └── fail after retries
            ↓
       Publish same Avro payload to  user-interactions-dlq
            ↓
       Continue (offset can advance — partition not stuck)

Invalid / poison message (not Avro)
        ↓
Skip + continue   (already existed — not infinite retry)
```

DLQ topic is created by Compose `kafka-init` as `user-interactions-dlq` (override with `KAFKA_DLQ_TOPIC`).

Operators can later inspect / replay DLQ messages. The learning point: **don’t block the main consumer forever on one bad durable write.**

### 6) How this fits with graceful degradation

Think in layers:

```text
Layer A — Circuit / retry     (fail fast or absorb blips)
Layer B — Fallback chain      (cache → model → PG store → popular)
Layer C — Platform            (HPA, canary rollback, probes)
```

Degradation (Layer B) was already there. Resilience (Layer A) makes Layer B kick in **sooner and more predictably**.

### 7) How to verify quickly

```powershell
# Unit / integration tests for breaker, retry, DLQ path
.\.venv\Scripts\python -m pytest tests/test_resilience.py -q

# Full suite
.\.venv\Scripts\python -m pytest -q

# With Compose up: watch metrics after Redis stop
docker compose stop redis
Invoke-RestMethod http://localhost:8000/recommendations/123
# after a few calls: logs may show redis_circuit_open; still get a response
Invoke-RestMethod http://localhost:8000/metrics | Select-String "circuit_breaker|resilience_retries|kafka_dlq"
docker compose start redis
```

### Done checklist (resilience)

- [x] Redis circuit breaker on serve path
- [x] Retry + backoff on Kafka publish + PG candidates
- [x] Consumer: limited PG retries → DLQ
- [x] Poison messages still skipped (no infinite loop)
- [x] Metrics for retries / breaker / DLQ
- [x] Tests in `test_resilience.py`
- [x] Documented in this file (+ summary in `system_architecture.md`)

**Resilience in one sentence:** We still degrade recommendation quality when dependencies fail — but Redis failures trip a circuit (fail fast), transient Kafka/Postgres blips get a short retry, and stuck durable writes go to a DLQ instead of blocking the consumer forever.
