"""Task 22 — drift detection (offline helpers only)."""

from app.config import get_settings
from app.drift import average, check_feature_drift, detect_drift


def test_detect_drift_normal_change_is_false():
    assert detect_drift(12, 10) is False  # 20% < 50%


def test_detect_drift_significant_change_is_true():
    assert detect_drift(20, 10) is True  # 100% > 50%


def test_detect_drift_zero_baseline_is_safe():
    assert detect_drift(5, 0) is False


def test_detect_drift_custom_threshold():
    assert detect_drift(12, 10, threshold=0.1) is True
    assert detect_drift(12, 10, threshold=0.5) is False


def test_average_empty_and_values():
    assert average([]) == 0.0
    assert average([10, 20, 30]) == 20.0


def test_check_feature_drift_data_drift_example():
    # Historical baseline ~10; sudden spike → data drift
    result = check_feature_drift(
        "click_count",
        current_values=[40, 80, 100, 60, 90],
        baseline_average=10.0,
        threshold=0.5,
    )
    assert result.drifted is True
    assert result.current_average == 74.0
    assert result.relative_change > 0.5


def test_check_feature_drift_stable_window():
    result = check_feature_drift(
        "click_count",
        current_values=[9, 10, 11, 10, 10],
        baseline_average=10.0,
        threshold=0.5,
    )
    assert result.drifted is False


def test_settings_expose_drift_baselines():
    settings = get_settings()
    assert settings.drift_click_baseline == 10.0
    assert settings.drift_purchase_baseline == 2.0
    assert settings.drift_threshold == 0.5
