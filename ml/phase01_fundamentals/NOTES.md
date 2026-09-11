# Phase 1 — recorded experiments

Learning env: `scikit-learn 1.7.2` (already installed for this Python). Not added to production `requirements.txt`.

## Task 1.3 — learned parameters

| True slope | Learned slope | Learned intercept |
| --- | --- | --- |
| 2 | 2.0015 | 0.9892 |
| 5 (exercise 1) | 5.0015 | (same intercept setup) |

Hyperparameter we chose: `fit_intercept=True`. Parameters the algorithm learned: `coef_`, `intercept_`.

## Task 1.4 — splits (n=30)

train=18, val=6, test=6, disjoint. Exercise 3: leaking test into train overlaps all 6 test rows — a “test” score after that is not a hold-out.

## Task 1.6 — overfitting (seed=0)

True pattern `y = 2x+1`. Complex = polynomial degree 7. Simple = line. Test = new x scored on the true line.

| Model | Train MSE | Test MSE |
| --- | --- | --- |
| polynomial-7 | 0.0000 | 0.0835 |
| line | 0.0430 | 0.0411 |

Complex train error < simple, but held-out error is worse → overfit.

Exercise 2 (shuffled train labels): complex test MSE=3.16, simple test MSE=2.81 — both bad; there is no pattern to learn.

## Task 1.7 — leakage

| Features | Test accuracy |
| --- | --- |
| `x` plus `leaky=y` | 1.000 |
| `x` only | 0.792 |

this is why we must not train on data unavailable at serving time
