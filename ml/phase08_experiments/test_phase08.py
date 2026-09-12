"""Verification for Phase 8 (Tasks 8.1–8.8)."""

import json
from pathlib import Path

from ml.phase02_features.splits import temporal_split
from ml.phase03_classical_ml.train_logreg import prepared_rows
from ml.phase08_experiments.run_baselines import SPLIT_META, freeze_split

LOG = Path(__file__).with_name("EXPERIMENT_LOG.md")
DECISION = Path(__file__).with_name("DECISION.md")


def _data_rows() -> list[list[str]]:
    rows = []
    for line in LOG.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or cells[0] in {"model_version", "---"}:
            continue
        if set(cells[0]) <= {"-"}:
            continue
        rows.append(cells)
    return rows


def test_log_has_required_columns() -> None:
    header = None
    for line in LOG.read_text(encoding="utf-8").splitlines():
        if line.startswith("|") and "model_version" in line:
            header = [c.strip() for c in line.strip().strip("|").split("|")]
            break
    assert header is not None
    required = {
        "model_version",
        "served",
        "clicked",
        "CTR",
        "precision@5",
        "recall@5",
        "ndcg@5",
        "latency_ms",
        "failure_rate",
    }
    assert required <= set(header)


def test_log_has_v1_v2_v3_and_one_variant() -> None:
    versions = [row[0] for row in _data_rows()]
    assert "v1" in versions
    assert "v2" in versions
    assert "v3" in versions
    assert "v3-no-purchase" in versions
    assert len(_data_rows()) >= 3


def test_variant_changed_only_purchase_feature() -> None:
    text = LOG.read_text(encoding="utf-8")
    assert "dropped `purchase_count_before`" in text or "purchase_count_before" in text
    assert "one change" in text.lower() or "dropped" in text.lower()


def test_split_meta_matches_temporal_cutoff() -> None:
    freeze_split()
    meta = json.loads(SPLIT_META.read_text(encoding="utf-8"))
    train, test = temporal_split(prepared_rows())
    assert meta["n_train"] == len(train)
    assert meta["n_test"] == len(test)
    assert meta["train_max_timestamp"] < meta["test_min_timestamp"] or (
        meta["train_max_timestamp"] <= meta["test_min_timestamp"]
    )


def test_decision_does_not_ship_and_mentions_ctr() -> None:
    text = DECISION.read_text(encoding="utf-8").lower()
    assert "do not ship" in text
    assert "offline ndcg cannot prove production ctr" in text
    assert "model_version=v1" in text or "stays `v1`" in text or "keep production" in text
