# Phase 12 — Advanced Recommendation Systems

## Objective

After the classical pipeline is understood, **introduce** advanced recsys ideas, labeled by difficulty. Implement **at most one small beginner exercise** (e.g. tiny matrix factorization with numpy **or** a pairwise ranking sketch). Do **not** implement the full list.

## Why This Phase Exists

Production systems (YouTube-scale) use candidate generation + scoring + re-ranking, embeddings, and ANN search. Our catalog has ~13 items — ANN is unnecessary. Knowing the names prevents cargo-culting PyTorch.

## Relationship To Existing Recommendation Service

We already have a **toy two-stage** system: `recommendation_items` (candidates) + ranker. Advanced methods would replace either stage:

| Stage | Today | Advanced replacement |
| --- | --- | --- |
| Candidate generation | SQL top-N by `score` | CF / two-tower / ANN over embeddings |
| Scoring | v1 / v2 / classical ML | LTR (XGBoost ranker), NCF |
| Re-ranking | none | diversity, freshness rules |

Do not add new Docker services for vector DBs in this phase.

## Prerequisites

- Phases 1–11 completed (classical loop works)
- Phase 4 taxonomy

## Concepts To Learn

Label every concept:

| Concept | Level | Implement now? |
| --- | --- | --- |
| Matrix factorization | INTERMEDIATE | Optional tiny numpy SVD/dot-product demo |
| Embeddings | INTERMEDIATE | Conceptual (user/item vectors) |
| ANN (approximate nearest neighbors) | ADVANCED | No — catalog too small |
| Two-stage recommendation | BEGINNER (we have it) | Document only |
| Candidate generation at scale | INTERMEDIATE | Conceptual |
| Learning-to-rank (pairwise/listwise) | INTERMEDIATE | Optional sklearn-free ranking loss sketch |
| XGBoost / LightGBM ranking | INTERMEDIATE | Read docs; do not require install |
| Neural collaborative filtering | ADVANCED | Conceptual |
| Deep recommendation / two-tower | ADVANCED | Conceptual |
| LLMs as recommenders | ADVANCED | **Out of scope** unless a future plan says otherwise |

## Tasks

### Task 12.1 — Reading map

`NOTES_advanced.md`: 5–10 sentences per concept in the table, each ending with “fits our service? yes/no/later”.

**Verify:** ANN = later/no; two-stage = yes already.

### Task 12.2 — Matrix factorization sketch (optional but recommended)

Tiny implicit matrix from Phase 4. Factor with `numpy.linalg.svd` **or** a few SGD steps. Reconstruct scores; recommend top items for one user.

**Verify:** output list of item ids. Not wired to FastAPI.

### Task 12.3 — Two-tower in words

Draw query tower (user features) vs item tower (item id/score). Contrast with our **concat features → logistic**.

**Verify:** diagram in NOTES.

### Task 12.4 — LTR vs pointwise

Write why NDCG-oriented training differs from log loss on clicks. No need to train LambdaMART.

**Verify:** half-page NOTES.

### Task 12.5 — Explicit non-goals

List: no PyTorch, no TFRS training, no LLM ranking, no new K8s vector service.

## Practical Exercises

1. Compute how many pairwise comparisons 13 items need vs 1M items — why ANN appears at scale.
2. Cold-start item in MF (no row) vs our catalog `score` still ranking it.
3. Read [XGBoost learning to rank](https://xgboost.readthedocs.io/en/stable/tutorials/learning_to_rank.html) intro; note `rank:ndcg` — do not install unless you choose to later.

## Implementation Work

```text
ml/phase12_advanced/
  NOTES_advanced.md
  tiny_mf.py              # optional
  test_phase12.py         # optional if MF implemented; else skip with docstring
```

## Tests / Verification

If `tiny_mf.py` exists: `pytest ml/phase12_advanced/test_phase12.py -q`.  
Phase can complete on NOTES alone if MF is skipped — checklist must say which path was taken.

## Expected Outcome

You can talk about MF, embeddings, two-tower, LTR, and NCF at interview level, and you know **none of them are required** to replace v1 until data and metrics justify it.

## Interview Questions

1. What problem does ANN solve that our 13-item catalog does not have?
2. Pointwise vs pairwise vs listwise LTR?
3. Why two-tower models help candidate generation?
4. Why might MF fail for new items we can still score with v1?
5. How does Google’s three-stage recsys map to our repo?

## Completion Checklist

- [ ] Task 12.1 NOTES complete for every table row
- [ ] Tasks 12.3–12.5 written
- [ ] Optional MF: done or explicitly skipped
- [ ] No LLM / no unjustified Docker
- [ ] Index: Phase 12 `COMPLETED`

## What The Next Phase Will Need

None — this is the last planned phase. Further work would be a **new** plan (real item metadata, more events, true LTR, etc.).

## Previous Phase

[`11_PROGRESSIVE_MODEL_IMPROVEMENT.md`](11_PROGRESSIVE_MODEL_IMPROVEMENT.md)

## Next Phase

None. Return to [`00_ML_PLAN_INDEX.md`](00_ML_PLAN_INDEX.md) and mark the program complete.

## Recommended References

- [Google — Recommendation systems course](https://developers.google.com/machine-learning/recommendation)
- [Google — Matrix factorization](https://developers.google.com/machine-learning/recommendation/collaborative/matrix)
- [Google — Deep models / two-tower](https://developers.google.com/machine-learning/recommendation/dnn/softmax)
- [TensorFlow Recommenders](https://www.tensorflow.org/recommenders) — read later, do not adopt now
- [XGBoost — learning to rank](https://xgboost.readthedocs.io/en/stable/tutorials/learning_to_rank.html)
- [Microsoft Recommenders](https://github.com/microsoft/recommenders)
