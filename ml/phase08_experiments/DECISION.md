# Decision — do not ship v3 as production default

Offline ranking on the frozen toy split (4 test users with positives):

- **v1** has the highest NDCG@5 (0.184). v2 and v3 tie at 0.167.
- Dropping `purchase_count` (`v3-no-purchase`) did not move NDCG — the catalog is tiny and lists already match v2.
- v3 `predict()` is slower than v2 on this microbench (~0.8 ms vs ~0.01 ms per call). Acceptable to know; not a K8s load test.
- Phase 7: a leaked “Redis now” trainer collapsed ROC-AUC (0.56 → 0.28). Serving features are not PIT.

**Ship / keep experimenting / do not ship:** **do not ship.** Keep production `MODEL_VERSION=v1`. Keep experimenting on a larger labeled window after Phase 2-style PIT is applied to real `user_events`.

**Offline NDCG cannot prove production CTR.** Position bias, delayed clicks, and training-serving skew are invisible in this table. `GET /monitoring/model-quality` is the online complement once traffic exists. Canary rollout is Phase 9.
