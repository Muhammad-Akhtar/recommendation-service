"""Durable raw event history in PostgreSQL (Task 18 upgrade).

PostgreSQL = system of record for clicks/purchases (offline / audit / retrain).
Redis online features are derived separately — not the source of truth.
"""

from __future__ import annotations

from datetime import datetime, timezone

import asyncpg

from .events import UserInteractionEvent


def _parse_event_time(timestamp: str) -> datetime | None:
    """Best-effort parse of ISO timestamps like 2026-09-09T12:00:00Z."""
    try:
        normalized = timestamp.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except Exception:
        return None


async def save_user_event(
    event: UserInteractionEvent,
    connection: asyncpg.Connection,
) -> int:
    """Insert one interaction into user_events; returns the new row id."""
    created_at = _parse_event_time(event.timestamp) or datetime.now(timezone.utc)
    row = await connection.fetchrow(
        """
        INSERT INTO user_events (user_id, item_id, event_type, created_at)
        VALUES ($1, $2, $3, $4)
        RETURNING id
        """,
        event.user_id,
        event.item_id,
        event.event_type,
        created_at,
    )
    return int(row["id"])


async def list_user_events(
    user_id: int,
    connection: asyncpg.Connection,
    *,
    limit: int = 50,
) -> list[dict]:
    """Return recent durable events for a user (newest first)."""
    rows = await connection.fetch(
        """
        SELECT id, user_id, item_id, event_type, created_at
        FROM user_events
        WHERE user_id = $1
        ORDER BY created_at DESC, id DESC
        LIMIT $2
        """,
        user_id,
        limit,
    )
    return [dict(row) for row in rows]


async def count_user_events(
    user_id: int,
    connection: asyncpg.Connection,
    event_type: str | None = None,
) -> int:
    """Optional helper for offline-style aggregations from history."""
    if event_type is None:
        value = await connection.fetchval(
            "SELECT COUNT(*) FROM user_events WHERE user_id = $1",
            user_id,
        )
    else:
        value = await connection.fetchval(
            """
            SELECT COUNT(*)
            FROM user_events
            WHERE user_id = $1 AND lower(event_type) = lower($2)
            """,
            user_id,
            event_type,
        )
    return int(value or 0)
