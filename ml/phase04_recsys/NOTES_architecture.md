# Task 4.1 — Candidate generation, scoring, re-ranking in *this* service

Google’s three-stage recsys sketch ([overview](https://developers.google.com/machine-learning/recommendation/overview/types)):

1. **Candidate generation** — cheap retrieval of items that *might* be relevant
2. **Scoring** — a model (or heuristic) scores those candidates
3. **Re-ranking** — business rules, diversity, freshness (optional)

| Stage | Our code path | What it actually is |
| --- | --- | --- |
| Candidate generation | `app/recommendation_repository.py` `get_recommendation_items` → `recommendation_items` (~13 seeded rows, `score` DESC) | Small catalog, not ANN / two-tower retrieval |
| Scoring (v1) | `SimpleRecommendationModel.predict` | Take the first 5 candidates already ordered by catalog `score` — **popularity** |
| Scoring (v2) | `SimpleRecommendationModelV2.predict` | Hand-tuned hybrid: `score + 0.01*clicks + 0.05*purchases + 0.5 if last_item` |
| Scoring (ML, offline) | Phase 3 `rank_with_proba` | Learned `P(click)` sort — **not served** yet (Phase 6) |
| Re-ranking | **Not implemented** | No diversity / exploration layer |

## Fallbacks (not a third ML model)

When Redis/Postgres/the ranker fail, `app/main.py` returns `POPULAR_RECOMMENDATIONS` from `app/recommendation_store.py`: `[10, 20, 30, 40, 50]`.

That list is a **degraded candidate + score path** (hardcoded popularity). It is **not** a third machine-learning model. `model_version="popular-fallback"` is an observability label, not a trained artifact.

Per-user JSON in Postgres `recommendations` (`app/seed.py` users 123/456/789) is another fallback store of **cached lists**, not a ranker.

Online features (`app/feature_store.py`) feed v2 scoring only. They are not candidate generation.
