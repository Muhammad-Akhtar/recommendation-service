"""Simple drift detection helpers (Task 22).

IMPORTANT: call these from monitoring / offline jobs — never inside the
recommendation request path (adds latency without helping the user).
"""

from __future__ import annotations

from pydantic import BaseModel


def detect_drift(
    current_average: float,
    baseline_average: float,
    threshold: float = 0.5,
) -> bool:
    """
    Return True when |current - baseline| / baseline exceeds threshold.

    Examples:
      detect_drift(12, 10) → False  (20% change)
      detect_drift(20, 10) → True   (100% change)
    """
    if baseline_average == 0:
        return False

    difference = abs(current_average - baseline_average)
    change = difference / baseline_average
    return change > threshold


def average(values: list[float] | list[int]) -> float:
    """Mean of a numeric sample; 0.0 for an empty list."""
    if not values:
        return 0.0
    return float(sum(values)) / len(values)


class DriftCheckResult(BaseModel):
    feature: str
    current_average: float
    baseline_average: float
    relative_change: float
    threshold: float
    drifted: bool


def check_feature_drift(
    feature: str,
    current_values: list[float] | list[int],
    baseline_average: float,
    threshold: float = 0.5,
) -> DriftCheckResult:
    """
    Offline / batch helper: compare a sample mean to a known baseline.

    Data drift example: historical avg click_count=10, recent window avg=100.
    """
    current_avg = average(current_values)
    if baseline_average == 0:
        relative = 0.0
        drifted = False
    else:
        relative = abs(current_avg - baseline_average) / baseline_average
        drifted = relative > threshold

    return DriftCheckResult(
        feature=feature,
        current_average=current_avg,
        baseline_average=baseline_average,
        relative_change=relative,
        threshold=threshold,
        drifted=drifted,
    )
