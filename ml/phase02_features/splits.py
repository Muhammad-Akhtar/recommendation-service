"""Task 2.6 — Random split vs time-based split.

A random `train_test_split` on interaction *rows* can put a user's later
click in train and an earlier view in test. The model then trains on the
future of that user. That is time travel.

Our events are a stream (`timestamp` / `created_at`). Serving-time Redis
counts only know the past. The default split for this service is therefore
**temporal**: train = earlier 70%, test = later 30%.
"""

from __future__ import annotations

from typing import Any

from sklearn.model_selection import train_test_split

WHY_TEMPORAL_SPLIT = (
    "Time-based split is the default because production features are causal: "
    "Redis click_count at request time can only include events that already "
    "happened. A random row split lets a user's future interactions into "
    "training while scoring their past, which we cannot do online."
)


def random_split(
    rows: list[dict[str, Any]],
    *,
    test_size: float = 0.3,
    seed: int = 0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    train, test = train_test_split(rows, test_size=test_size, random_state=seed, shuffle=True)
    return list(train), list(test)


def temporal_split(
    rows: list[dict[str, Any]],
    *,
    train_fraction: float = 0.7,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ordered = sorted(rows, key=lambda row: (row["timestamp"], row["user_id"]))
    cut = int(len(ordered) * train_fraction)
    if cut <= 0 or cut >= len(ordered):
        raise ValueError("train_fraction must leave both train and test non-empty")
    return ordered[:cut], ordered[cut:]


def max_timestamp(rows: list[dict[str, Any]]) -> str:
    return max(row["timestamp"] for row in rows)


def min_timestamp(rows: list[dict[str, Any]]) -> str:
    return min(row["timestamp"] for row in rows)


def find_time_travel_pairs(
    train: list[dict[str, Any]],
    test: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Train row is *later* than a test row for the same user (future in train)."""
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for train_row in train:
        for test_row in test:
            if train_row["user_id"] != test_row["user_id"]:
                continue
            if train_row["timestamp"] > test_row["timestamp"]:
                pairs.append((train_row, test_row))
    return pairs


def main() -> None:
    from ml.phase02_features.encode import add_missing_value_flags
    from ml.phase02_features.point_in_time import build_training_rows

    rows = add_missing_value_flags(build_training_rows())
    rand_train, rand_test = random_split(rows, seed=0)
    leaks = find_time_travel_pairs(rand_train, rand_test)
    example = leaks[0]
    print(
        "random split time-travel example: "
        f"user={example[0]['user_id']} train_ts={example[0]['timestamp']} "
        f"test_ts={example[1]['timestamp']}"
    )
    t_train, t_test = temporal_split(rows)
    print(
        "temporal: max(train)="
        f"{max_timestamp(t_train)} min(test)={min_timestamp(t_test)} "
        f"ok={max_timestamp(t_train) <= min_timestamp(t_test)}"
    )
    print(WHY_TEMPORAL_SPLIT)


if __name__ == "__main__":
    main()
