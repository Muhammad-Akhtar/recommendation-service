# Phase 4 — recorded experiments

## Popularity vs catalog score

Toy event counts and seeded `score` are not the same ordering. Catalog item `10` is both popular in the seed (0.95) and frequent in the toy log; long-tail catalog items can have **zero** implicit positives.

## Implicit matrix

Cells are `{0, 1}` only — no ratings 1–5. Sparsity is high (most user–item pairs never engaged).

## Exercises

1. **Cold-start user** (no row / all-zero row): item-kNN has nothing to neighbor. Popularity / `POPULAR_RECOMMENDATIONS` is the honest answer — same as our popular fallback.
2. **Cold-start item** (column all zeros): CF cosine is undefined/zero vs everyone; v1 can still rank it by catalog `score`.
3. Duplicating user `123` 100 times inflates that user’s column pattern — naive CF overfits whoever shouts loudest in the matrix.
