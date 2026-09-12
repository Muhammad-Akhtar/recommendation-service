"""Task 2.3 — Derive a 0/1 engagement label from implicit feedback.

We do **not** have star ratings. Kafka `event_type` is implicit feedback:
view / click / purchase.

Simple rule (event-row label):
  clicked = 1  if event_type in {click, purchase}
  clicked = 0  otherwise (view)

This is biased: we have no impression log of “shown but not clicked”. A view
is not a true negative (the user may never have been shown the item as a
recommendation). Purchases counted as `clicked=1` also collapse two different
engagement strengths into one bit. Later phases can sample unclicked
candidates as negatives; this phase keeps the label on the event row itself.
"""

from __future__ import annotations

from typing import Any

POSITIVE_EVENT_TYPES = frozenset({"click", "purchase"})


def clicked_from_event_type(event_type: str) -> int:
    return 1 if event_type.lower() in POSITIVE_EVENT_TYPES else 0


def add_clicked_labels(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Copy each event and add `clicked` in {0, 1}."""
    labeled: list[dict[str, Any]] = []
    for event in events:
        row = dict(event)
        row["clicked"] = clicked_from_event_type(str(event["event_type"]))
        labeled.append(row)
    return labeled


def always_predict_positive_accuracy(rows: list[dict[str, Any]]) -> float:
    """Practical exercise 2: drop negatives, then “always 1” looks perfect."""
    positives = [row for row in rows if row["clicked"] == 1]
    if not positives:
        return 0.0
    return 1.0


def main() -> None:
    from ml.phase02_features.toy_events import TOY_EVENTS

    rows = add_clicked_labels(list(TOY_EVENTS))
    labels = {row["clicked"] for row in rows}
    n_pos = sum(row["clicked"] for row in rows)
    print(f"n={len(rows)} label_values={labels} positives={n_pos} negatives={len(rows) - n_pos}")
    print(
        "Bias: labels sit on the event row. We never saw items that were "
        "recommended and ignored, so accuracy on this table is not CTR."
    )
    print(
        "Exercise 2: after dropping negatives, always-predict-1 accuracy = "
        f"{always_predict_positive_accuracy(rows):.3f}"
    )


if __name__ == "__main__":
    main()
