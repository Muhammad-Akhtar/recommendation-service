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

Key principle (Task 23):

> **Never send 100% of production traffic to a new version before validating it — run it beside the stable version, then promote or roll back.**

Key principle (Task 24):

> **Task 13 = manually set replicas. Task 24 = measure under load, then let HPA scale automatically.**

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

## Project layout (after Task 24)

```text
recommendation-service/
├── app/
│   ├── main.py                 # /health version; /demo/cpu-burn; soft DB init
│   ├── schemas.py              # HealthResponse.version
│   ├── config.py               # SERVICE_VERSION (deploy identity)
│   └── …
├── k8s/
│   ├── deployment.yaml         # recommendation-service-v1 (3 replicas + resources)
│   ├── deployment-v2.yaml      # canary only — remove before HPA tests
│   ├── service.yaml            # selector: app=recommendation-service
│   └── hpa.yaml                # Task 24 — HPA on v1
├── scripts/
│   └── load_test.py            # Task 24 — RPS / latency / errors
├── tests/
│   ├── test_health_version.py
│   └── test_load_scaling.py
├── implementation_Readme_3.md
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
