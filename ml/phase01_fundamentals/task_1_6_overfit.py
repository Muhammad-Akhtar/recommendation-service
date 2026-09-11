"""Task 1.6 — Overfitting vs a simple line.

True pattern: y ≈ 2x + 1 plus noise.
Complex model: polynomial of degree 7 (can pass through all 8 train points).
Simple model: a straight line.

Overfitting = low train error, *worse* held-out error than the simple model
(held-out = new x, scored against the true line).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures
from sklearn.tree import DecisionTreeRegressor


@dataclass(frozen=True)
class OverfitResult:
    complex_train_mse: float
    complex_test_mse: float
    simple_train_mse: float
    simple_test_mse: float


def _true_y(x: np.ndarray) -> np.ndarray:
    return 2.0 * x + 1.0


def run_overfit_experiment(seed: int = 0) -> OverfitResult:
    rng = np.random.default_rng(seed)
    x_train = np.linspace(0.0, 1.0, 8)
    y_train = _true_y(x_train) + rng.normal(0, 0.45, size=8)
    # Held-out x values, scored against the *true* line (the pattern we care about).
    x_test = np.linspace(0.0, 1.0, 50)
    y_test = _true_y(x_test)

    X_train = x_train.reshape(-1, 1)
    X_test = x_test.reshape(-1, 1)

    # Degree-7 polynomial can pass through all 8 noisy train points (train MSE ~ 0)
    # and then wiggle away from the true line on new x.
    complex_model = make_pipeline(
        PolynomialFeatures(degree=7, include_bias=True),
        LinearRegression(),
    )
    simple_model = LinearRegression()
    complex_model.fit(X_train, y_train)
    simple_model.fit(X_train, y_train)

    return OverfitResult(
        complex_train_mse=float(mean_squared_error(y_train, complex_model.predict(X_train))),
        complex_test_mse=float(mean_squared_error(y_test, complex_model.predict(X_test))),
        simple_train_mse=float(mean_squared_error(y_train, simple_model.predict(X_train))),
        simple_test_mse=float(mean_squared_error(y_test, simple_model.predict(X_test))),
    )


def run_shuffled_label_experiment(seed: int = 0) -> OverfitResult:
    """Practical exercise 2: destroy the pattern. Both models should fail on test."""
    rng = np.random.default_rng(seed)
    x_train = np.linspace(0.0, 1.0, 8)
    y_train = rng.normal(0, 1.0, size=8)  # unrelated to x
    x_test = np.linspace(0.0, 1.0, 40)
    y_test = 2.0 * x_test + 1.0

    X_train = x_train.reshape(-1, 1)
    X_test = x_test.reshape(-1, 1)
    complex_model = make_pipeline(PolynomialFeatures(degree=7), LinearRegression())
    simple_model = LinearRegression()
    # A deep tree also memorizes shuffled labels.
    tree = DecisionTreeRegressor(max_depth=None, random_state=seed)
    complex_model.fit(X_train, y_train)
    simple_model.fit(X_train, y_train)
    tree.fit(X_train, y_train)

    return OverfitResult(
        complex_train_mse=float(mean_squared_error(y_train, complex_model.predict(X_train))),
        complex_test_mse=float(
            min(
                mean_squared_error(y_test, complex_model.predict(X_test)),
                mean_squared_error(y_test, tree.predict(X_test)),
            )
        ),
        simple_train_mse=float(mean_squared_error(y_train, simple_model.predict(X_train))),
        simple_test_mse=float(mean_squared_error(y_test, simple_model.predict(X_test))),
    )


def main() -> None:
    r = run_overfit_experiment()
    print("Overfit experiment (true line + noise, n_train=8; test = true line)")
    print(f"  polynomial-7  train MSE={r.complex_train_mse:.4f}  test MSE={r.complex_test_mse:.4f}")
    print(f"  line          train MSE={r.simple_train_mse:.4f}  test MSE={r.simple_test_mse:.4f}")
    print(
        "  complex train < simple train:",
        r.complex_train_mse < r.simple_train_mse,
    )
    print(
        "  complex test  > simple test :",
        r.complex_test_mse > r.simple_test_mse,
    )

    s = run_shuffled_label_experiment()
    print("Exercise 2: shuffled train labels (no real pattern)")
    print(f"  complex test MSE={s.complex_test_mse:.4f}  simple test MSE={s.simple_test_mse:.4f}")


if __name__ == "__main__":
    main()
