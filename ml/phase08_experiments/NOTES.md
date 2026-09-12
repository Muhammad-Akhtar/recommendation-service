# Phase 8 — notes

Dataset is **too small** (22/10 rows, 4 users with test positives). Two random
seeds for a shuffled split would likely flip the NDCG winner — the temporal
split is frozen in `split_meta.json` so we do not pretend otherwise.

Accuracy-only optimization is rejected: Phase 5 already showed identical bag
accuracy with different NDCG@5.

A leaked-future run is in the log as `v3-leaked-INVALID` and is not a candidate.
