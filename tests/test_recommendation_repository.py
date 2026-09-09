import pytest

from app.recommendation_repository import (
    RecommendationCandidate,
    get_recommendation_items,
)


class FakeConnection:
    def __init__(self, rows: list[dict] | None = None) -> None:
        self.rows = list(rows or [])

    async def fetch(self, query: str, limit: int):
        active = [r for r in self.rows if r.get("is_active", True)]
        active.sort(key=lambda r: (-r["score"], r["item_id"]))
        return active[:limit]


@pytest.mark.asyncio
async def test_get_recommendation_items_orders_by_score():
    connection = FakeConnection(
        [
            {"item_id": 50, "score": 0.80, "is_active": True},
            {"item_id": 10, "score": 0.95, "is_active": True},
            {"item_id": 20, "score": 0.91, "is_active": True},
            {"item_id": 99, "score": 0.99, "is_active": False},
        ]
    )

    items = await get_recommendation_items(connection, limit=2)

    assert items == [
        RecommendationCandidate(item_id=10, score=0.95),
        RecommendationCandidate(item_id=20, score=0.91),
    ]
