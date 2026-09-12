# Task 6.1 — Train / serve pipeline mapped to this repo

```text
Training data          ml/phase02_features toy events → PIT rows
    ↓
Feature engineering    NUMERIC_FEATURE_NAMES (click_count_before, …)
    ↓
Training               ml/phase06_train_serve/train.py
                       sklearn Pipeline(StandardScaler + LogisticRegression)
    ↓
Validation             temporal test split (Phase 2 / 5 metrics)
    ↓
Model artifact         ml/artifacts/click_logreg_v3.joblib
                       ml/artifacts/click_logreg_v3.meta.json
    ↓
Model version          conceptual `v3` = this artifact + this feature schema
                       (not Kubernetes SERVICE_VERSION)
    ↓
Inference              ml/phase06_train_serve/ranker.py
                       predict(features, candidates) -> list[int]
```

Online path stays in `RecommendationService`: Redis features + Postgres candidates,
then `model.predict`. The ranker never opens those stores.

**The model does not import `redis` or `asyncpg`.**

`v3` is implemented under `ml/` only. Production `app/model_registry.py` still
exposes `v1` / `v2`. Default `MODEL_VERSION` stays `v1` because production
`requirements.txt` has no scikit-learn — registering a joblib loader at FastAPI
import time would break Docker Compose. Follow-up: add an sklearn extra and a
lazy `v3` entry in Phase 9.

Serving name map (Redis `UserFeatures` → training columns):

| Serving now | Training as-of-t |
| --- | --- |
| `click_count` | `click_count_before` |
| `purchase_count` | `purchase_count_before` |
| `candidate.score` | `item_score` |
| `item_id == last_item_id` | `same_as_last_item` |
| `last_item_id is not None` | `has_last_item` |

That map is a skew risk (Phase 7): Redis is “counts **now**”, training was
“counts **before** the label event”.
