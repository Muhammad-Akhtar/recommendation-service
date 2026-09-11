"""Task 1.3 — Parameters vs hyperparameters.

Parameters: values the training algorithm *learns* (coef_, intercept_).
Hyperparameters: values *we* choose before fit (e.g. fit_intercept=True).

Unlike Task 1.1, we do not type w and b. LinearRegression searches for them.
"""

from __future__ import annotations

import numpy as np
from sklearn.linear_model import LinearRegression


def make_line_data(
    true_slope: float = 2.0,
    true_intercept: float = 1.0,
    n: int = 40,
    noise: float = 0.05,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    X = np.linspace(0, 10, n).reshape(-1, 1)
    y = true_slope * X[:, 0] + true_intercept + rng.normal(0, noise, n)
    return X, y


def fit_line(
    true_slope: float = 2.0,
    *,
    fit_intercept: bool = True,
    seed: int = 0,
) -> LinearRegression:
    """fit_intercept is a hyperparameter; coef_ / intercept_ are parameters."""
    X, y = make_line_data(true_slope=true_slope, seed=seed)
    model = LinearRegression(fit_intercept=fit_intercept)
    model.fit(X, y)
    return model


def main() -> None:
    model = fit_line(true_slope=2.0)
    slope = float(model.coef_[0])
    intercept = float(model.intercept_)
    print("Hyperparameter: fit_intercept=True (we chose it)")
    print(f"Learned parameters: slope={slope:.4f}  intercept={intercept:.4f}")
    print("Expected near slope=2, intercept=1")

    model5 = fit_line(true_slope=5.0)
    print(f"Exercise: true slope 5 -> learned slope={float(model5.coef_[0]):.4f}")


if __name__ == "__main__":
    main()
