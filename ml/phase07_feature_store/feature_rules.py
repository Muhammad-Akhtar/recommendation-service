"""Task 7.2 — Pure Redis update rules (no Redis).

Copied from `app/feature_store.py` `apply_interaction_event`:
click → click_count += 1; purchase → purchase_count += 1; every type sets last_item_id.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class OnlineState:
    user_id: int
    click_count: int = 0
    purchase_count: int = 0
    last_item_id: int | None = None


def empty_state(user_id: int) -> OnlineState:
    """Same defaults as `get_user_features` when Redis has no key."""
    return OnlineState(user_id=user_id)


def apply_event(state: OnlineState, event: dict[str, Any]) -> OnlineState:
    event_type = str(event["event_type"]).lower()
    item_id = int(event["item_id"])
    click_count = state.click_count
    purchase_count = state.purchase_count
    if event_type == "click":
        click_count += 1
    elif event_type == "purchase":
        purchase_count += 1
    return OnlineState(
        user_id=state.user_id,
        click_count=click_count,
        purchase_count=purchase_count,
        last_item_id=item_id,
    )
