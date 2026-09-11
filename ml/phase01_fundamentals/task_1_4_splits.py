"""Task 1.4 — Train / validation / test splits.

We hold data out so we do not grade ourselves on examples the model already saw.

- train: learn parameters
- validation: choose hyperparameters (not used in this tiny demo beyond existing)
- test: one-shot estimate of generalization — look once

If a row is in two splits, the test number is contaminated (practical exercise 3).
"""

from __future__ import annotations

import numpy as np
from sklearn.model_selection import train_test_split


def make_toy_indices(n: int = 30) -> np.ndarray:
    return np.arange(n)


def split_train_val_test(
    indices: np.ndarray,
    *,
    test_size: float = 0.2,
    val_size: float = 0.2,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Split indices into disjoint train / val / test sets."""
    train_val, test = train_test_split(
        indices, test_size=test_size, random_state=seed, shuffle=True
    )
    # val_size is a fraction of the *full* dataset, so convert to fraction of train_val.
    val_fraction_of_remaining = val_size / (1.0 - test_size)
    train, val = train_test_split(
        train_val,
        test_size=val_fraction_of_remaining,
        random_state=seed,
        shuffle=True,
    )
    return train, val, test


def splits_are_disjoint(
    train: np.ndarray, val: np.ndarray, test: np.ndarray
) -> bool:
    t, v, s = set(train.tolist()), set(val.tolist()), set(test.tolist())
    return t.isdisjoint(v) and t.isdisjoint(s) and v.isdisjoint(s)


def contaminated_test_indices(
    train: np.ndarray, test: np.ndarray
) -> np.ndarray:
    """Practical exercise 3: pretend we trained on train+test (test leaked into train)."""
    return np.concatenate([train, test])


def main() -> None:
    indices = make_toy_indices(30)
    train, val, test = split_train_val_test(indices)
    print(f"n=30 -> train={len(train)} val={len(val)} test={len(test)}")
    print("disjoint?", splits_are_disjoint(train, val, test))
    leaked_train = contaminated_test_indices(train, test)
    overlap = set(leaked_train.tolist()) & set(test.tolist())
    print(
        "Exercise 3: after leaking test into train, "
        f"{len(overlap)} test rows also sit in the training pool "
        "(test accuracy is no longer an honest hold-out)."
    )


if __name__ == "__main__":
    main()
