# Experiment log

Frozen split: `split_meta.json` (n_train=22, n_test=10, cutoff `2026-01-10T08:00:00Z` / `2026-01-10T08:01:00Z`). K=5. Online CTR is `n/a` (no live traffic in this learning slice).

| model_version | served | clicked | CTR | precision@5 | recall@5 | ndcg@5 | latency_ms | failure_rate | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v1 | n/a | n/a | n/a | 0.100 | 0.375 | 0.184 | n/a | 0 | popularity / catalog score |
| v2 | n/a | n/a | n/a | 0.100 | 0.375 | 0.167 | 0.012 | 0 | production heuristic formula |
| v3 | n/a | n/a | n/a | 0.100 | 0.375 | 0.167 | 0.83 | 0 | Pipeline scaler+logreg, C=1, all FEATURE_NAMES |
| v3-no-purchase | n/a | n/a | n/a | 0.100 | 0.375 | 0.167 | n/a | 0 | **one change vs v3:** dropped `purchase_count_before` only |
| v3-leaked-INVALID | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | rejected: trained on future Redis-now counts (Phase 7 skew) |
