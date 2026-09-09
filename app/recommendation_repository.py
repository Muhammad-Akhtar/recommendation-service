"""PostgreSQL access for recommendation *candidates* (Task 19).

Distinct from Task 14's `recommendations` table (persisted per-user results).
This table is the candidate-generation source the model ranks.
"""

from __future__ import annotations

from pydantic import BaseModel
import asyncpg


class RecommendationCandidate(BaseModel):
    item_id: int
    score: float


async def ensure_recommendation_items_table(connection: asyncpg.Connection) -> None:
    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS recommendation_items (
            id BIGSERIAL PRIMARY KEY,
            item_id BIGINT NOT NULL UNIQUE,
            score DOUBLE PRECISION NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT TRUE
        )
        """
    )


async def get_recommendation_items(
    connection: asyncpg.Connection,
    *,
    limit: int = 20,
) -> list[RecommendationCandidate]:
    """Fetch active candidates ordered by base popularity score."""
    rows = await connection.fetch(
        """
        SELECT item_id, score
        FROM recommendation_items
        WHERE is_active = TRUE
        ORDER BY score DESC, item_id ASC
        LIMIT $1
        """,
        limit,
    )
    return [
        RecommendationCandidate(item_id=int(row["item_id"]), score=float(row["score"]))
        for row in rows
    ]
