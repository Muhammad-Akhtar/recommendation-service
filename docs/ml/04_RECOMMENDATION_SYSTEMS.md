# Phase 4 — Recommendation System Fundamentals

## Objective

Learn the main families of recommender systems and map every family onto **this** service: what we already have, what Phase 3 started, and what we should not build yet.

## Why This Phase Exists

Without this map it is easy to jump to matrix factorization or neural CF because they are famous. Our architecture is already a **two-stage sketch**: Postgres candidates (generation) + a ranker (v1/v2/future ML). This phase names that pattern.

## Relationship To Existing Recommendation Service

| Approach | In this repo today |
| --- | --- |
| Popularity | v1 + `recommendation_items.score` + popular fallback list |
| Heuristic / hybrid-ish ranker | v2 uses popularity + user activity + last item |
| Content-based | **Not implemented** (no item category/text table) |
| Collaborative filtering | **Not implemented** (no user–item matrix factorization) |
| Classical ML ranking | Phase 3 offline `P(click)` sort — not served yet |
| Two-stage (candidates → rank) | Yes, at small scale: catalog of ~13 items, then top 5 |

Inspect: `app/model.py`, `app/recommendation_repository.py`, `app/recommendation_store.py` (popular fallback), `app/feature_store.py`.

This phase is **mostly conceptual + small matrix exercises**. No FastAPI changes.

## Prerequisites

- Phases 1–3 completed
- Know v1, v2, and the logistic ranker conceptually

## Concepts To Learn

- Popularity recommendation
- Content-based recommendation (item attributes ↔ user profile)
- Collaborative filtering (users who agree on items)
- User–item interaction matrix (sparse)
- Implicit vs explicit feedback (our Kafka events are implicit)
- Similarity and nearest neighbors (user-kNN / item-kNN)
- Matrix factorization and embeddings (vectors; **conceptual**)
- Hybrid systems (combine signals — v2 is a crude hybrid of popularity + behavior)
- Candidate generation vs ranking vs re-ranking ([Google recsys overview](https://developers.google.com/machine-learning/recommendation/overview/types))

Explicit comparison we must write down:

```text
Current v1              popularity rank of catalog
Current v2              hand-tuned hybrid score
Classical ML ranking    learned P(click) then sort  (Phase 3)
Collaborative filtering needs a user–item matrix we do not factorize yet
Hybrid model            mix of the above — later, after metrics (Phase 5)
```

What fits **now**: keep candidate catalog + pointwise click model.  
What is **too heavy now**: ANN retrieval, deep two-tower, full MF serving.

## Tasks

### Task 4.1 — Name our stages

Write `ml/phase04_recsys/NOTES_architecture.md` mapping Google’s three stages (candidate generation, scoring, re-ranking) to our code paths and fallbacks.

**Verify:** fallback popular list is labeled as a degraded candidate/score path, not a third ML model.

- [x] Done — `ml/phase04_recsys/NOTES_architecture.md`

### Task 4.2 — Popularity baseline

From the toy events, rank items by interaction count. Compare to seeded Postgres scores (`10 → 0.95`, …).

**Verify:** a table of item_id, interaction_count, catalog_score.

- [x] Done — `ml/phase04_recsys/popularity.py`

### Task 4.3 — Implicit feedback matrix

Build a tiny user–item matrix: `1` if the user clicked/purchased the item else `0`. Print sparsity (`zeros / cells`).

**Verify:** matrix is mostly zeros; no ratings 1–5.

- [x] Done — `ml/phase04_recsys/interaction_matrix.py`

### Task 4.4 — Item similarity (beginner CF)

Cosine similarity between two item columns (or two user rows) using numpy only or sklearn `cosine_similarity`. Recommend items similar to `last_item_id`.

**Verify:** an item is most similar to itself (~1.0).

- [x] Done — `ml/phase04_recsys/item_knn.py`

### Task 4.5 — Where content-based would plug in

Invent 3 fake item categories. Document why v2 cannot do true content-based today (`recommendation_items` has no category column).

**Verify:** a one-paragraph “gap” note — do not add a DB column yet unless we explicitly decide later.

- [x] Done — `ml/phase04_recsys/NOTES_content_gap.md`

### Task 4.6 — Fitness ranking

Fill a markdown table: approach × (fits now / later / skip) × reason tied to data we actually have.

**Verify:** matrix factorization is “later / Phase 12”; logistic ranking is “next to evaluate / Phase 5–6”.

- [x] Done — `ml/phase04_recsys/fitness_table.md`

## Practical Exercises

1. Cold-start user (no rows in the matrix): popularity is the only honest answer — same as our popular fallback.
2. Cold-start item (never interacted): CF cannot recommend it; catalog `score` still can (v1).
3. Duplicate the same user 100 times in the matrix; note how naive CF overfits that user.

## Implementation Work

```text
ml/phase04_recsys/
  NOTES_architecture.md
  popularity.py
  interaction_matrix.py
  item_knn.py
  NOTES_content_gap.md
  fitness_table.md
  test_phase04.py
  NOTES.md
```

## Tests / Verification

`pytest ml/phase04_recsys/test_phase04.py -q`

Assert: diagonal similarity ~1; sparsity in `(0, 1)`; popularity rank is deterministic for a fixture.

## Expected Outcome

You can explain in an interview: *We already do candidate generation + scoring. v1 is popularity. v2 is a heuristic hybrid. A logistic model is a learned scorer. Collaborative filtering is a different family that needs a matrix we have only as events, not as a production ranker yet.*

## Interview Questions

1. Implicit vs explicit feedback — what do we log?
2. Why do large recsys use two stages?
3. Why is accuracy on a click classifier not the same as “good recommendations”?
4. What happens to CF for a brand-new user?
5. How is v2 a hybrid without being ML?

## Completion Checklist

- [x] Tasks 4.1–4.6 verified
- [x] pytest passes
- [x] Fitness table completed
- [x] `app/` unchanged
- [x] Index: Phase 4 `COMPLETED`

## What The Next Phase Will Need

- Named baselines: popularity (v1), heuristic (v2), ML scorer (Phase 3)
- Toy interaction matrix + ranked lists of length K=5
- Motivation: we must measure **ranking**, not only classification accuracy

## Previous Phase

[`03_FIRST_CLASSICAL_ML_MODEL.md`](03_FIRST_CLASSICAL_ML_MODEL.md)

## Next Phase

[`05_RANKING_AND_EVALUATION.md`](05_RANKING_AND_EVALUATION.md)

## Recommended References

- [Google — Recommendation systems (course)](https://developers.google.com/machine-learning/recommendation)
- [Google — Recsys types / three stages](https://developers.google.com/machine-learning/recommendation/overview/types)
- [Google — Collaborative filtering basics](https://developers.google.com/machine-learning/recommendation/collaborative/basics)
- [Microsoft Recommenders README](https://github.com/microsoft/recommenders)
