"""Task 1.1 — What is a model?

A model is a function with **parameters** that maps features to a prediction.

This file is NOT machine learning yet. `w` and `b` are hardcoded, the same way
`app/model.py` v1/v2 hardcode ranking formulas. Later tasks will *learn*
parameters from labeled data (`.fit()`). Inference (this function) does not
need labels — it only needs features and the current parameters.
"""

# Parameters: values that define the model's behavior.
# Here we typed them ourselves. In ML they would be found by training.
W = 2.0
B = 1.0


def predict(x: float, w: float = W, b: float = B) -> float:
    """Return y_hat = w * x + b (inference)."""
    return w * x + b


def main() -> None:
    xs = [0, 1, 2, 3, 4, 5]
    print(f"Model: y = {W}*x + {B}  (parameters are hardcoded, not learned)")
    for x in xs:
        print(f"  x={x}  ->  prediction={predict(x)}")


if __name__ == "__main__":
    main()
