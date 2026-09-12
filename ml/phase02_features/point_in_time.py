"""Task 2.4 — Point-in-time features as of an event.

Redis `click_count` is a *serving-time* aggregate: it already includes every
click that has happened when we call `get_user_features`. A training row at
time `t` must only use that user's events **strictly before** `t`.

Otherwise the label event (this click) leaks into `click_count` and the model
cheats the same way Task 1.7 cheated with `leaky = y`.
"""

from __future__ import annotations

from typing import Any

from ml.phase02_features.labels import add_clicked_labels
from ml.phase02_features.toy_events import TOY_EVENTS


def add_pit_features(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add counts / last item from earlier events of the same user only."""
    ordered = sorted(
        enumerate(rows),
        key=lambda item: (item[1]["timestamp"], item[1]["user_id"], item[0]),
    )
    history: dict[int, list[dict[str, Any]]] = {}
    attached: dict[int, dict[str, Any]] = {}

    for original_index, row in ordered:
        user_id = int(row["user_id"])
        prior = history.get(user_id, [])
        click_before = sum(1 for event in prior if event["event_type"] == "click")
        purchase_before = sum(1 for event in prior if event["event_type"] == "purchase")
        last_item = int(prior[-1]["item_id"]) if prior else None
        item_id = int(row["item_id"])

        enriched = dict(row)
        enriched["click_count_before"] = click_before
        enriched["purchase_count_before"] = purchase_before
        enriched["last_item_id_before"] = last_item
        enriched["same_as_last_item"] = bool(last_item is not None and last_item == item_id)
        attached[original_index] = enriched

        history.setdefault(user_id, []).append(row)

    return [attached[i] for i in range(len(rows))]


def build_training_rows(
    events: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Labeled event rows with honest (strictly-before) user aggregates."""
    source = list(events) if events is not None else list(TOY_EVENTS)
    return add_pit_features(add_clicked_labels(source))


def leaky_click_count(row: dict[str, Any]) -> int:
    """Practical exercise 1: include this event in the click count (wrong)."""
    extra = 1 if str(row["event_type"]).lower() == "click" else 0
    return int(row["click_count_before"]) + extra


def pearson(xs: list[float], ys: list[float]) -> float:
    import numpy as np

    if len(xs) < 2:
        return 0.0
    corr = np.corrcoef(np.asarray(xs, dtype=float), np.asarray(ys, dtype=float))[0, 1]
    if np.isnan(corr):
        return 0.0
    return float(corr)


def leaky_vs_honest_correlation(rows: list[dict[str, Any]]) -> tuple[float, float]:
    clicked = [float(row["clicked"]) for row in rows]
    honest = [float(row["click_count_before"]) for row in rows]
    leaky = [float(leaky_click_count(row)) for row in rows]
    return pearson(leaky, clicked), pearson(honest, clicked)


def main() -> None:
    rows = build_training_rows()
    first_123 = next(row for row in rows if row["user_id"] == 123)
    later_click = next(
        row
        for row in rows
        if row["user_id"] == 123 and row["event_type"] == "click" and row["click_count_before"] > 0
    )
    print("first 123:", {k: first_123[k] for k in ("timestamp", "click_count_before", "purchase_count_before", "last_item_id_before")})
    print("later click:", {k: later_click[k] for k in ("timestamp", "event_type", "click_count_before", "clicked")})
    leaky_r, honest_r = leaky_vs_honest_correlation(rows)
    print(f"Exercise 1: corr(leaky_count, clicked)={leaky_r:.3f} vs honest={honest_r:.3f}")


if __name__ == "__main__":
    main()
