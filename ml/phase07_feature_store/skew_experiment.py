"""Task 7.4 — Train on leaked Redis-now features; evaluate on honest PIT rows."""

from __future__ import annotations

from typing import Any

from sklearn.metrics import log_loss, roc_auc_score

from ml.phase02_features.splits import temporal_split
from ml.phase02_features.toy_events import TOY_EVENTS
from ml.phase03_classical_ml.train_logreg import labeled_matrix, prepared_rows
from ml.phase06_train_serve.train import build_pipeline
from ml.phase07_feature_store.replay import replay


def leak_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Replace PIT counts with the user's *final* Redis-like state (future included)."""
    final = replay(list(TOY_EVENTS))
    leaked = []
    for row in rows:
        state = final[int(row["user_id"])]
        updated = dict(row)
        updated["click_count_before"] = state.click_count
        updated["purchase_count_before"] = state.purchase_count
        updated["last_item_id_before"] = state.last_item_id
        updated["has_last_item"] = 0 if state.last_item_id is None else 1
        updated["same_as_last_item"] = int(
            state.last_item_id is not None
            and int(state.last_item_id) == int(row["item_id"])
        )
        leaked.append(updated)
    return leaked


def run_skew_experiment() -> dict[str, float]:
    rows = prepared_rows()
    train, test = temporal_split(rows)
    honest_model = build_pipeline()
    Xh, yh = labeled_matrix(train)
    honest_model.fit(Xh, yh)
    Xt, yt = labeled_matrix(test)
    honest_proba = honest_model.predict_proba(Xt)[:, 1]

    leaked_train = leak_rows(train)
    leaked_model = build_pipeline()
    Xl, yl = labeled_matrix(leaked_train)
    leaked_model.fit(Xl, yl)
    # Evaluate leaked model on *honest* PIT test features (serve-like).
    leaked_on_honest = leaked_model.predict_proba(Xt)[:, 1]

    return {
        "honest_log_loss": float(log_loss(yt, honest_proba, labels=[0, 1])),
        "honest_roc_auc": float(roc_auc_score(yt, honest_proba)),
        "leaked_on_pit_log_loss": float(log_loss(yt, leaked_on_honest, labels=[0, 1])),
        "leaked_on_pit_roc_auc": float(roc_auc_score(yt, leaked_on_honest)),
    }


def main() -> None:
    scores = run_skew_experiment()
    print(scores)


if __name__ == "__main__":
    main()
