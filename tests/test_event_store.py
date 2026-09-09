from datetime import datetime, timezone

import pytest

from app.event_store import count_user_events, list_user_events, save_user_event
from app.events import UserInteractionEvent


class FakeConnection:
    def __init__(self) -> None:
        self.rows: list[dict] = []
        self._next_id = 1

    async def fetchrow(self, query: str, *args):
        user_id, item_id, event_type, created_at = args
        row = {
            "id": self._next_id,
            "user_id": user_id,
            "item_id": item_id,
            "event_type": event_type,
            "created_at": created_at,
        }
        self._next_id += 1
        self.rows.append(row)
        return {"id": row["id"]}

    async def fetch(self, query: str, user_id: int, limit: int):
        matched = [r for r in self.rows if r["user_id"] == user_id]
        matched.sort(key=lambda r: (r["created_at"], r["id"]), reverse=True)
        return matched[:limit]

    async def fetchval(self, query: str, *args):
        user_id = args[0]
        matched = [r for r in self.rows if r["user_id"] == user_id]
        if "lower(event_type)" in query.lower() or "event_type" in query:
            event_type = args[1]
            matched = [
                r for r in matched if r["event_type"].lower() == event_type.lower()
            ]
        return len(matched)


@pytest.mark.asyncio
async def test_save_and_list_user_events():
    connection = FakeConnection()
    event = UserInteractionEvent(
        user_id=123,
        item_id=42,
        event_type="click",
        timestamp="2026-09-09T12:00:00Z",
    )

    event_id = await save_user_event(event, connection)
    assert event_id == 1

    rows = await list_user_events(123, connection)
    assert len(rows) == 1
    assert rows[0]["item_id"] == 42
    assert rows[0]["event_type"] == "click"


@pytest.mark.asyncio
async def test_count_user_events_by_type():
    connection = FakeConnection()
    now = datetime.now(timezone.utc)

    for item_id, event_type in [(42, "click"), (50, "click"), (99, "purchase")]:
        await save_user_event(
            UserInteractionEvent(
                user_id=123,
                item_id=item_id,
                event_type=event_type,
                timestamp=now.isoformat().replace("+00:00", "Z"),
            ),
            connection,
        )

    assert await count_user_events(123, connection) == 3
    assert await count_user_events(123, connection, event_type="click") == 2
    assert await count_user_events(123, connection, event_type="purchase") == 1
