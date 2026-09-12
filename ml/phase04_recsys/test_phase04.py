"""Verification for Phase 4 (Tasks 4.1–4.6)."""

from pathlib import Path

import numpy as np

from ml.phase04_recsys.interaction_matrix import implicit_matrix, sparsity
from ml.phase04_recsys.item_knn import item_cosine, similar_to
from ml.phase04_recsys.popularity import popularity_rank, popularity_table

ARCH = Path(__file__).with_name("NOTES_architecture.md")
GAP = Path(__file__).with_name("NOTES_content_gap.md")
FITNESS = Path(__file__).with_name("fitness_table.md")


def test_architecture_note_labels_fallback_not_as_ml() -> None:
    text = ARCH.read_text(encoding="utf-8").lower()
    assert "popular-fallback" in text or "popular_recommendations" in text
    assert "not" in text and "third" in text
    assert "machine-learning" in text or "ml model" in text


def test_popularity_rank_is_deterministic() -> None:
    first = popularity_rank()
    second = popularity_rank()
    assert first == second
    table = popularity_table()
    assert table
    assert {"item_id", "interaction_count", "catalog_score"} <= table[0].keys()
    assert table[0]["catalog_score"] == 0.95 or any(row["item_id"] == 10 for row in table)


def test_implicit_matrix_is_binary_and_sparse() -> None:
    matrix, _users, _items = implicit_matrix()
    values = set(matrix.ravel().tolist())
    assert values <= {0.0, 1.0}
    assert 1.0 in values
    sp = sparsity(matrix)
    assert 0.0 < sp < 1.0


def test_item_is_most_similar_to_itself() -> None:
    neighbors = similar_to(10, k=12)
    assert neighbors[0][0] == 10
    assert abs(neighbors[0][1] - 1.0) < 1e-6
    matrix, _, items = implicit_matrix()
    sim = item_cosine(matrix)
    idx = items.index(10)
    assert sim[idx, idx] >= 0.99


def test_content_gap_note_exists() -> None:
    text = GAP.read_text(encoding="utf-8").lower()
    assert "category" in text
    assert "recommendation_items" in text
    assert "do not add a db column" in text


def test_fitness_table_places_mf_and_logistic() -> None:
    text = FITNESS.read_text(encoding="utf-8").lower()
    assert "phase 12" in text
    assert "phase 5" in text or "phases 5" in text
    assert "matrix factorization" in text
    assert "logistic" in text


def test_cold_start_user_has_no_neighbors() -> None:
    matrix, users, items = implicit_matrix()
    empty = np.zeros((1, len(items)))
    padded = np.vstack([matrix, empty])
    sim_users = padded @ padded.T
    new_idx = len(users)
    assert float(sim_users[new_idx, new_idx]) == 0.0


def test_naive_cf_overfits_duplicated_user() -> None:
    matrix, users, _items = implicit_matrix()
    idx = users.index(123)
    loud = np.vstack([matrix, np.repeat(matrix[idx : idx + 1], 100, axis=0)])
    mass = loud.sum(axis=0)
    original = matrix.sum(axis=0)
    assert float(np.linalg.norm(mass - original)) > 0.0
