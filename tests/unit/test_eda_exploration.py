"""Check statistical behavior independently of file storage and API clients."""

import pandas as pd
import pytest
from app.services.eda_exploration_service import exploration


def test_iqr_preserves_outliers_and_curve_reaches_100_percent():
    frame = pd.DataFrame({"salary_min_vnd": [10e6, 20e6, 30e6, 40e6, 500e6],
                          "exp_min_years": [1, 2, 3, 4, 5], "headcount": [2] * 5,
                          "seniority": ["Junior"] * 5})
    result = exploration(frame, pd.Series(["Hà Nội"] * 5))
    box = result["boxes"][0]
    assert box["q1"] == 20
    assert box["median"] == 30
    assert box["q3"] == 40
    assert box["low"] == 10 and box["high"] == 40
    assert box["outliers"] == 1
    assert result["salary_curve"][-1] == {"salary": 500, "cumulative_pct": 100}
    assert result["scatter_total"] == 5  # outlier was not silently removed
    assert result["heatmap"] == [{"x": "Junior", "y": "Hà Nội", "value": 5}]
    assert all(c["value"] is None for c in result["correlation"] if "Số lượng tuyển" in (c["x"], c["y"]))


def test_missing_numeric_data_does_not_create_zero_points():
    frame = pd.DataFrame({"salary_min_vnd": [0, None, float("inf")]})
    result = exploration(frame, pd.Series([None] * 3, dtype="string"))
    assert result["scatter"] == []
    assert result["salary_curve"] == []
    assert result["boxes"] == []
    assert result["heatmap"] == []
    assert all(c["value"] is None for c in result["correlation"])


def test_pairwise_correlation_uses_only_complete_pairs():
    frame = pd.DataFrame({"salary_min_vnd": [10e6, 20e6, 30e6, None],
                          "exp_min_years": [1, 2, 3, 9]})
    result = exploration(frame, pd.Series([None] * 4, dtype="string"))
    pair = next(c for c in result["correlation"] if c["x"] == "Lương min (triệu VND)" and c["y"] == "Kinh nghiệm min (năm)")
    assert pair["count"] == 3
    assert pair["value"] == pytest.approx(1)
