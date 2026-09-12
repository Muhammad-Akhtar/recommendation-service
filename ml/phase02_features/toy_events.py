"""Task 2.2 — Tiny interaction table that looks like our Kafka / user_events rows.

Synthetic on purpose: Compose / Postgres is not required. Item scores match the
seeded `recommendation_items` catalog in `app/seed.py`. Users `123` / `456` /
`789` are the seeded fallback users; `999` and `1001` are unknown-style ids
(no Redis row yet → counts start at 0, like `get_user_features` defaults).
"""

from __future__ import annotations

from typing import TypedDict


class Event(TypedDict):
    user_id: int
    item_id: int
    event_type: str
    timestamp: str
    item_score: float
    device_type: str | None


# Seeded catalog scores (app/seed.py). Unknown items would be missing at serve time.
ITEM_SCORES: dict[int, float] = {
    10: 0.95,
    20: 0.91,
    30: 0.88,
    40: 0.84,
    50: 0.80,
    60: 0.76,
    70: 0.72,
    80: 0.68,
    90: 0.65,
    91: 0.63,
    94: 0.57,
}


def _event(
    user_id: int,
    item_id: int,
    event_type: str,
    timestamp: str,
    device_type: str | None = None,
) -> Event:
    return {
        "user_id": user_id,
        "item_id": item_id,
        "event_type": event_type,
        "timestamp": timestamp,
        "item_score": ITEM_SCORES[item_id],
        "device_type": device_type,
    }


# ~32 rows. Timestamps are unique so a 70/30 time split has a clean cut.
TOY_EVENTS: list[Event] = [
    _event(123, 10, "view", "2026-01-01T10:00:00Z", "mobile"),
    _event(123, 10, "click", "2026-01-01T10:01:00Z", "mobile"),
    _event(123, 20, "view", "2026-01-01T10:05:00Z", "mobile"),
    _event(123, 20, "click", "2026-01-01T10:06:00Z", "mobile"),
    _event(456, 50, "view", "2026-01-01T12:00:00Z", "desktop"),
    _event(456, 50, "click", "2026-01-01T12:02:00Z", "desktop"),
    _event(789, 94, "view", "2026-01-01T15:00:00Z", "mobile"),
    _event(123, 20, "purchase", "2026-01-01T16:00:00Z", "mobile"),
    _event(123, 30, "view", "2026-01-02T09:00:00Z", "desktop"),
    _event(999, 10, "view", "2026-01-02T11:00:00Z", None),
    _event(999, 10, "click", "2026-01-02T11:30:00Z", None),
    _event(456, 60, "view", "2026-01-02T14:00:00Z", "desktop"),
    _event(123, 30, "click", "2026-01-03T12:00:00Z", "desktop"),
    _event(789, 94, "click", "2026-01-04T16:00:00Z", "mobile"),
    _event(456, 10, "purchase", "2026-01-05T10:00:00Z", "mobile"),
    _event(123, 40, "view", "2026-01-06T08:00:00Z", "mobile"),
    _event(456, 50, "view", "2026-01-06T13:00:00Z", "desktop"),
    _event(999, 80, "view", "2026-01-08T08:00:00Z", "mobile"),
    _event(123, 40, "click", "2026-01-08T09:00:00Z", "mobile"),
    _event(789, 91, "view", "2026-01-08T18:00:00Z", "mobile"),
    _event(456, 70, "click", "2026-01-09T09:00:00Z", "desktop"),
    _event(123, 40, "view", "2026-01-10T08:00:00Z", "mobile"),
    _event(123, 70, "click", "2026-01-10T08:01:00Z", "mobile"),
    _event(456, 70, "view", "2026-01-11T09:00:00Z", "desktop"),
    _event(1001, 90, "view", "2026-01-11T18:00:00Z", "desktop"),
    _event(789, 91, "click", "2026-01-12T10:00:00Z", "mobile"),
    _event(999, 80, "click", "2026-01-12T11:00:00Z", "mobile"),
    _event(123, 10, "view", "2026-01-12T15:00:00Z", "mobile"),
    _event(456, 20, "view", "2026-01-13T09:00:00Z", "desktop"),
    _event(789, 10, "view", "2026-01-13T12:00:00Z", "mobile"),
    _event(123, 50, "click", "2026-01-14T08:00:00Z", "desktop"),
    _event(456, 30, "click", "2026-01-14T10:00:00Z", "desktop"),
]


def event_types(events: list[Event] | None = None) -> set[str]:
    rows = events if events is not None else TOY_EVENTS
    return {row["event_type"] for row in rows}


def users_with_multiple_events(events: list[Event] | None = None) -> set[int]:
    rows = events if events is not None else TOY_EVENTS
    counts: dict[int, int] = {}
    for row in rows:
        counts[row["user_id"]] = counts.get(row["user_id"], 0) + 1
    return {user_id for user_id, n in counts.items() if n > 1}


def main() -> None:
    print(f"n={len(TOY_EVENTS)} events, types={sorted(event_types())}")
    print(f"users with >1 event: {sorted(users_with_multiple_events())}")
    print("sample:", TOY_EVENTS[0])


if __name__ == "__main__":
    main()
