"""Replay events through the same rules Redis uses."""

from __future__ import annotations

from typing import Any

from ml.phase07_feature_store.feature_rules import OnlineState, apply_event, empty_state


def sort_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        events,
        key=lambda row: (row["timestamp"], int(row["user_id"]), int(row["item_id"])),
    )


def replay(events: list[dict[str, Any]], user_id: int | None = None) -> dict[int, OnlineState]:
    states: dict[int, OnlineState] = {}
    for event in sort_events(events):
        uid = int(event["user_id"])
        if user_id is not None and uid != user_id:
            continue
        states[uid] = apply_event(states.get(uid) or empty_state(uid), event)
    return states


def replay_before(
    events: list[dict[str, Any]],
    user_id: int,
    timestamp: str,
) -> OnlineState:
    """State Redis *would* have had strictly before `timestamp`."""
    prior = [
        event
        for event in events
        if int(event["user_id"]) == user_id and event["timestamp"] < timestamp
    ]
    states = replay(prior, user_id=user_id)
    return states.get(user_id) or empty_state(user_id)
