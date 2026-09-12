"""Verification for Phase 5 (Tasks 5.1–5.6)."""

import math
from pathlib import Path

from ml.phase05_evaluation.classification_metrics import (
    all_finite,
    evaluate_logreg_and_dummy,
)
from ml.phase05_evaluation.compare_rankers import compare_systems, markdown_table
from ml.phase05_evaluation.ranking_metrics import (
    average_precision_at_k,
    hit_rate_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    unique_top,
)

SAME_ACC = Path(__file__).with_name("NOTES_same_accuracy.md")
RANKING_SRC = Path(__file__).with_name("ranking_metrics.py")


def test_classification_metrics_are_finite_and_not_only_accuracy() -> None:
    reports = evaluate_logreg_and_dummy()
    ml = reports["ml"]
    dummy = reports["dummy_most_frequent"]
    assert all_finite(ml)
    assert all_finite(dummy)
    for key in ("precision", "recall", "f1", "roc_auc", "log_loss", "accuracy"):
        assert key in ml
    # Dummy can win accuracy; record both either way.
    assert "accuracy" in dummy


def test_ndcg_perfect_vs_relevant_at_last_slot() -> None:
    relevant = {10}
    perfect = [10, 20, 30, 40, 50]
    last_slot = [20, 30, 40, 50, 10]
    assert ndcg_at_k(perfect, relevant, k=5) == 1.0
    ndcg_last = ndcg_at_k(last_slot, relevant, k=5)
    assert ndcg_last is not None
    assert ndcg_last < 1.0
    assert abs(ndcg_last - (1.0 / math.log2(6))) < 1e-9


def test_same_accuracy_lists_disagree_on_ndcg() -> None:
    relevant = {10}
    list_a = [10, 20, 30, 40, 50]
    list_b = [20, 30, 40, 50, 10]
    # Both lists contain the same five items → same bag accuracy.
    assert set(list_a) == set(list_b)
    assert ndcg_at_k(list_a, relevant, 5) == 1.0
    assert ndcg_at_k(list_b, relevant, 5) < 1.0
    text = SAME_ACC.read_text(encoding="utf-8")
    assert "1.000" in text
    assert "NDCG" in text


def test_three_system_table_has_all_metrics() -> None:
    summary = compare_systems()
    assert set(summary) == {"popularity_v1", "heuristic_v2", "ml_logreg"}
    for scores in summary.values():
        assert "ndcg@5" in scores
        assert "precision@5" in scores
        assert "map@5" in scores
    table = markdown_table(summary)
    assert "ndcg@5" in table


def test_microsoft_binary_relevance_note_in_code() -> None:
    text = RANKING_SRC.read_text(encoding="utf-8").lower()
    assert "microsoft" in text
    assert "binary" in text
    assert "ndcg_at_k" in text


def test_empty_relevant_is_skipped_not_zero() -> None:
    ranked = [10, 20, 30, 40, 50]
    assert precision_at_k(ranked, set(), 5) is None
    assert ndcg_at_k(ranked, set(), 5) is None
    assert hit_rate_at_k(ranked, set(), 5) is None


def test_relevant_below_k_has_zero_hit_rate() -> None:
    ranked = [20, 30, 40, 50, 60]
    relevant = {10}
    assert hit_rate_at_k(ranked, relevant, k=5) == 0.0
    assert recall_at_k(ranked, relevant, k=5) == 0.0


def test_duplicate_ids_count_once() -> None:
    ranked = [10, 10, 10, 20, 30]
    relevant = {10, 20}
    assert unique_top(ranked, 5) == [10, 20, 30]
    assert precision_at_k(ranked, relevant, k=5) == 2 / 5
    assert average_precision_at_k(ranked, relevant, k=5) is not None
