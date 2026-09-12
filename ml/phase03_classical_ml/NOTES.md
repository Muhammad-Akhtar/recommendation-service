# Phase 3 — recorded experiments

Offline only. `app/model.py` was not edited. n_train=22, n_test=10 (temporal split from Phase 2).

## Task 3.1–3.2

`sigmoid(0)=0.500`, `sigmoid(2)=0.881`, `sigmoid(-2)=0.119`.

Worked example: z = 2.0*0.95 + 0.01*2 + 0.05*1 + 0.5*1 - 1.2 = **1.27**, p=**0.781**.

## Task 3.3 — learned weights (C=1)

intercept=-1.36

| feature | coef |
| --- | --- |
| click_count_before | -0.41 |
| purchase_count_before | +0.12 |
| item_score | +0.17 |
| same_as_last_item | +1.71 |
| has_last_item | +0.91 |

`predict_proba` shape (10, 2), values in [0, 1]. Tiny toy table: signs can look odd (clicks slightly negative) — that is why Phase 5 exists before we serve this.

## Task 3.4

Held-out user `123` → top 5 item ids `[10, 20, 30, 40, 50]` (`list[int]`, unique, K=5).

## Task 3.5 vs v2 (user 123)

| item | v2_score | p_click | v2_rank | ml_top5 |
| --- | --- | --- | --- | --- |
| 10 | 1.550 | 0.299 | 1 | 1 |
| 20 | 1.010 | 0.127 | 2 | 2 |
| 30 | 0.980 | 0.126 | 3 | 3 |

Same top-5 order on this catalog because both still lean on `item_score` / last-item. Not a quality claim.

## Task 3.6 tree (max_depth=3)

Importances: same_as_last_item 0.63, click_count_before 0.19, item_score 0.15. train_acc=0.955, **temporal test_acc=0.400** — train is not the number that matters.

## Exercises

1. All labels 0 → LogisticRegression raises (needs two classes).
2. `item_score * 1000` without scaling changes coefficient magnitude vs `StandardScaler`.
3. Smaller `C` shrinks `||w||`.
