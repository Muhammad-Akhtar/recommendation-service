# Task 4.6 — What fits this service now

| Approach | Fits | Reason (data we actually have) |
| --- | --- | --- |
| Popularity (v1 / catalog `score` / popular fallback list) | **now** | `recommendation_items.score` and `POPULAR_RECOMMENDATIONS` already ship |
| Heuristic hybrid (v2) | **now** | Uses online `click_count`, `purchase_count`, `last_item_id` — still guessed weights |
| Classical ML pointwise ranking (logistic `P(click)` then sort) | **next to evaluate** (Phases 5–6) | Phase 3 trained offline; needs ranking metrics then `predict()` serving |
| Content-based | **later** | No item category/text table — see `NOTES_content_gap.md` |
| User/item kNN on implicit matrix | **later** (learning only) | We can build a toy matrix from events; not a production ranker |
| Matrix factorization / embeddings | **later / Phase 12** | Famous, but we have no serving embedding store and the catalog is ~13 items |
| Two-tower / ANN retrieval | **skip for now** | Candidate set is already the tiny Postgres catalog |
| Hybrid of ML + CF + content | **later** | After Phase 5 metrics; mixing families without NDCG is guesswork |

Logistic ranking is the line we evaluate next. MF waits for Phase 12.
