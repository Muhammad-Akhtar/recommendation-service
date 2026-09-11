# ML Context (stable)

Compact context for every Cursor window. Do not treat this as a tutorial.

Full architecture: [`system_architecture.md`](../../system_architecture.md).  
Plan index: [`00_ML_PLAN_INDEX.md`](00_ML_PLAN_INDEX.md).

---

## Existing architecture

```text
Client
  ↓
FastAPI  (app/main.py)
  ↓
RecommendationService  (app/recommendation_service.py)
  ↓
Redis features + PostgreSQL candidates
  ↓
model.predict(features, candidates)
  ↓
ranked recommendations  (list[int], top 5)
```

Fallbacks if the model path fails: Postgres `recommendations` table → in-code popular list.

Async path (does not rank):

```text
POST /interactions → Avro → Kafka user-interactions
  → consumer → PostgreSQL user_events → Redis features:user:*
```

---

## Model boundary

```text
RecommendationService = data access / orchestration

Model = mathematical prediction / ranking

Model must NOT:
- access Redis
- access PostgreSQL
- access Kafka
- perform HTTP calls
- know infrastructure details
```

Interface today (`app/model.py`):

```python
def predict(self, features: BaseModel, candidates: list[RecommendationCandidate]) -> list[int]
```

`UserFeatures`: `user_id`, `click_count`, `purchase_count`, `last_item_id`.  
`RecommendationCandidate`: `item_id`, `score`.

---

## Current models

| Version | Class | What it actually is |
| --- | --- | --- |
| `v1` | `SimpleRecommendationModel` | Popularity: first 5 candidates by Postgres `score` |
| `v2` | `SimpleRecommendationModelV2` | Heuristic: `score + 0.01*click_count + 0.05*purchase_count + 0.5 if last_item` |

Weights are constants. Nothing is trained. `get_model(version)` returns in-process objects from `MODELS` in `app/model_registry.py`.

Config:

- `MODEL_VERSION` → which ranking logic to call (`v1` / `v2`)
- `SERVICE_VERSION` → which Kubernetes deploy identity `/health` reports

These are **not** the same thing.

---

## Existing data

| Store | Contents | Role |
| --- | --- | --- |
| Postgres `user_events` | `user_id`, `item_id`, `event_type`, `created_at` | Durable history |
| Postgres `recommendation_items` | `item_id`, `score`, `is_active` | Candidate catalog |
| Postgres `recommendations` | per-user JSON lists | Fallback store, not training data |
| Redis `features:user:{id}` | click/purchase counts, `last_item_id` | Online inference features |
| Redis `cache:recommendations:{id}` | cached API response | Not features |
| Redis `last_recs:{id}` | last served items + model_version | CTR attribution |
| Kafka `user-interactions` | Avro events | Feature pipeline input |

Seeded candidates (examples): item `10` score `0.95` … item `94` score `0.57`.  
Seeded fallback users: `123`, `456`, `789`.

Online feature updates from events:

| `event_type` | Redis change |
| --- | --- |
| `click` | `click_count += 1`, `last_item_id = item_id` |
| `purchase` | `purchase_count += 1`, `last_item_id = item_id` |
| other (e.g. `view`) | `last_item_id` only |

---

## Existing ML/MLOps infrastructure

| Piece | Reality |
| --- | --- |
| Model registry | In-memory dict, not an artifact store |
| Model version | Env string selecting a Python class |
| Prediction logs | Structured `prediction_logged` events |
| CTR | Prometheus counters + `/monitoring/model-quality` |
| Drift helper | `detect_drift(current, baseline, threshold=0.5)` — offline only |
| Metrics | predictions, latency, served, clicked, errors |
| Canary | Dual K8s Deployments for **service** versions |
| Rollback | Delete canary Deployment / revert image |

Drift and ranking-metric jobs must stay **off** the `GET /recommendations` path.

---

## Important project rules

1. Do not replace the production architecture.
2. Heuristic ≠ classical ML ≠ deep learning ≠ LLMs.
3. Classical ML first (scikit-learn). No PyTorch/LLMs until Phase 12 says so.
4. Tiny datasets before service data; service data before “big” data.
5. Evaluation before claiming a model is better.
6. One phase, one task, then verify.
7. Learning scripts live under `ml/` once Phase 1 starts. Production stays in `app/`.
8. When a trained model is integrated (Phase 6+), it still only implements `predict(features, candidates)`.
