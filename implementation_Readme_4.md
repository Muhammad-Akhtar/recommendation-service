# Recommendation Service — Implementation Tutorial (Part 4)

This file continues from [`implementation_Readme_3.md`](implementation_Readme_3.md) (Tasks 17–22).

- Part 1 → Tasks 1–8 → [`implementation_Readme.md`](implementation_Readme.md)
- Part 2 → Tasks 9–16 → [`implementation_Readme_2.md`](implementation_Readme_2.md)
- Part 3 → Tasks 17–22 → [`implementation_Readme_3.md`](implementation_Readme_3.md)
- **Part 4 → Task 23 onward** (canary / blue-green / rollback, …)

---

## Overview (Part 4)

| Task | What we implemented |
| --- | --- |
| 23 | Canary / blue-green practice on Kubernetes: dual Deployments (v1 + v2), shared Service, independent validate, rollback |

Key principle (Task 23):

> **Never send 100% of production traffic to a new version before validating it — run it beside the stable version, then promote or roll back.**

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

## Project layout (after Task 23)

```text
recommendation-service/
├── app/
│   ├── main.py                 # /health returns status + deploy version
│   ├── schemas.py              # HealthResponse.version
│   ├── config.py               # SERVICE_VERSION (deploy identity)
│   └── …                       # (unchanged recommendation / model path)
├── k8s/
│   ├── deployment.yaml         # recommendation-service-v1
│   ├── deployment-v2.yaml      # recommendation-service-v2  (ADDED)
│   └── service.yaml            # selector: app=recommendation-service only
├── tests/
│   └── test_health_version.py  # ADDED
├── implementation_Readme_3.md
└── implementation_Readme_4.md  # this file
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

```text
recommendation-service/
├── app/
│   ├── config.py              # CHANGED — service_version / SERVICE_VERSION
│   ├── schemas.py             # CHANGED — HealthResponse.version
│   └── main.py                # CHANGED — /health includes version
├── k8s/
│   ├── deployment.yaml        # CHANGED — recommendation-service-v1 + labels
│   ├── deployment-v2.yaml     # ADDED
│   └── service.yaml           # unchanged selector (app only)
├── tests/
│   └── test_health_version.py # ADDED
└── implementation_Readme_4.md # ADDED
```

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

`/health` (liveness) now returns deploy identity:

```json
{
  "status": "ok",
  "version": "v2"
}
```

Set per pod via Kubernetes env (not baked into the image code path for ranking):

```yaml
env:
  - name: SERVICE_VERSION
    value: "v2"
```

Same Docker image bits can be tagged `:v1` and `:v2`; **env** makes the versions distinguishable.

### Kubernetes manifests (summary)

**v1** (`k8s/deployment.yaml`):

- name: `recommendation-service-v1`
- labels: `app=recommendation-service`, `version=v1`
- image: `recommendation-service:v1`
- `SERVICE_VERSION=v1`
- replicas: `1`

**v2** (`k8s/deployment-v2.yaml`):

- name: `recommendation-service-v2`
- labels: `app=recommendation-service`, `version=v2`
- image: `recommendation-service:v2`
- `SERVICE_VERSION=v2`
- replicas: `1`

**Service** (`k8s/service.yaml`):

```yaml
selector:
  app: recommendation-service
```

### How to run / verify (Docker Desktop Kubernetes)

#### 1) Build images

```powershell
docker build -t recommendation-service:v1 .
docker build -t recommendation-service:v2 .
docker images recommendation-service
```

#### 2) Load images into the cluster (if `ErrImageNeverPull`)

Same pattern as Task 11:

```powershell
docker save recommendation-service:v1 -o recommendation-service-v1.tar
docker save recommendation-service:v2 -o recommendation-service-v2.tar
docker exec desktop-control-plane ctr -n k8s.io images import /recommendation-service-v1.tar
docker exec desktop-control-plane ctr -n k8s.io images import /recommendation-service-v2.tar
```

(Adjust node name / import path to match your Desktop setup if needed.)

#### 3) Apply manifests

If an **old** Deployment named `recommendation-service` still exists from Task 11–13, remove it so labels do not collide:

```powershell
kubectl delete deployment recommendation-service --ignore-not-found
kubectl apply -f k8s/deployment.yaml -f k8s/deployment-v2.yaml -f k8s/service.yaml
kubectl get deployments
kubectl get pods --show-labels
```

Expect pods like:

```text
…   app=recommendation-service,version=v1
…   app=recommendation-service,version=v2
```

#### 4) Test v2 independently (before trusting shared traffic)

```powershell
kubectl port-forward deployment/recommendation-service-v2 8001:8000
```

In another terminal:

```powershell
Invoke-RestMethod http://localhost:8001/health
# → status=ok, version=v2
```

Production practice:

> **Never expose a new version to production traffic before validating it independently.**

#### 5) Shared Service traffic (both versions)

```powershell
kubectl port-forward service/recommendation-service 8000:8000
Invoke-RestMethod http://localhost:8000/health
```

You may see `version=v1` or `version=v2` depending on which Ready endpoint kube-proxy picks (simple load balancing — not weighted canary yet).

#### 6) Rollback (v2 unhealthy)

Simulate “v2 has a serious problem” by removing it:

```powershell
kubectl delete deployment recommendation-service-v2
kubectl get pods --show-labels
```

Only **v1** remains; Service still selects `app=recommendation-service` → traffic stays on v1.

That is our first **basic rollback**.

### Production concept (what comes later)

Real pipelines rarely “delete v2” as the only tool. They combine:

```text
Git Push
   ↓
Tests (Task 20 CI)
   ↓
Docker Build
   ↓
Deploy v2 (canary)
   ↓
Health checks + monitoring (Tasks 21–22)
   ↓
Healthy → increase traffic → 100% v2
Unhealthy → rollback → v1
```

Weighted 10%/90% splitting (Ingress / service mesh) is a later refinement. Task 23 first locks the **mechanics**: dual Deployments, shared Service selector, independent port-forward validation, rollback.

### Tests

```powershell
.\.venv\Scripts\python -m pytest tests/test_health_version.py -q
.\.venv\Scripts\python -m pytest -q
```

`tests/test_health_version.py` checks:

- Default `/health` → `version=v1`
- `SERVICE_VERSION=v2` → `/health` reports `v2`

### Done checklist

- [x] Visible v2 change (`/health` deploy `version`)
- [x] Build tags documented (`recommendation-service:v1` / `:v2`)
- [x] Separate Kubernetes v2 Deployment (`k8s/deployment-v2.yaml`)
- [x] v1 Deployment labeled (`k8s/deployment.yaml`)
- [x] Run v1 and v2 simultaneously (shared Service `app` selector)
- [x] Test v2 independently (port-forward docs)
- [x] Understand Service selectors (app only, not version)
- [x] Rollback = delete v2; v1 continues
- [x] Documented in `implementation_Readme_4.md`

**Task 23 in one sentence:** We run labeled v1 and v2 Deployments behind one Service, validate v2 alone via port-forward, and roll back by removing v2 — without changing recommendation logic.
