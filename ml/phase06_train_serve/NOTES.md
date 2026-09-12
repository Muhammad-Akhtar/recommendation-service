# Phase 6 — recorded notes

Production default remains `MODEL_VERSION=v1`. `get_model("v3")` is intentionally unknown until sklearn is a production dependency.

## Artifact

`ml/artifacts/click_logreg_v3.joblib` + `.meta.json`. Pipeline = StandardScaler + LogisticRegression. joblib round-trip `predict_proba` matches.

Temporal test metrics (n_test=10): accuracy 0.600, ROC-AUC 0.560, log_loss 1.065.

## Exercises

1. Shuffled feature names vs `meta.json` → `FeatureSchemaError` (named columns, not positional).
2. Retrain with a subset of features → a different artifact / version id (Phase 8 `v3-no-purchase`).
3. `predict(..., [])` raises `ValueError("candidates must not be empty")`.
