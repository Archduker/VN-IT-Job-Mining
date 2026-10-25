# -*- coding: utf-8 -*-
"""preprocessing.missing_outlier.outlier_handler
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Module kiểm định ngoại lai định lượng bằng phương pháp IQR và Winsorization.

Quy tắc:
  - Áp dụng cho 2 biến liên tục: mức lương (VND/tháng) và số năm kinh nghiệm.
  - Tự động nhận diện và sửa 3 lỗi nhập liệu số phổ biến.
  - Áp dụng Winsorization (capping tại phân vị 1% và 99%) thay vì xóa bỏ hàng,
    nhằm bảo toàn nguyên vẹn hồ sơ kỹ năng quý giá.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


def detect_iqr_outliers(series: pd.Series, multiplier: float = 1.5) -> Dict[str, Any]:
    """Phát hiện ngoại lai số học bằng phương pháp Khoảng Phân Vị (IQR Method)."""
    valid = series.dropna()
    if len(valid) == 0:
        return {
            "total_records": 0,
            "q1": None,
            "q3": None,
            "iqr": None,
            "lower_bound": None,
            "upper_bound": None,
            "outlier_count": 0,
            "outlier_rate_pct": 0.0,
        }

    q1 = float(valid.quantile(0.25))
    q3 = float(valid.quantile(0.75))
    iqr = q3 - q1

    lower_bound = max(0.0, q1 - multiplier * iqr)
    upper_bound = q3 + multiplier * iqr

    outliers = valid[(valid < lower_bound) | (valid > upper_bound)]
    outlier_count = len(outliers)
    outlier_rate = round((outlier_count / len(valid)) * 100, 2)

    return {
        "total_records": len(valid),
        "q1": q1,
        "q3": q3,
        "iqr": iqr,
        "lower_bound": lower_bound,
        "upper_bound": upper_bound,
        "outlier_count": outlier_count,
        "outlier_rate_pct": outlier_rate,
        "skewness": round(float(valid.skew()), 2) if len(valid) > 2 else 0.0,
        "kurtosis": round(float(valid.kurtosis()), 2) if len(valid) > 3 else 0.0,
    }


def fix_common_salary_input_errors(salary_vnd: Optional[float], jd_text: str = "") -> Optional[float]:
    """Nhận diện và sửa 3 lỗi nhập liệu số phổ biến:

    1. Gõ nhầm USD vào ô VNĐ (ví dụ: 1,500 - 3,000 VNĐ -> nhân 25,400).
    2. Nhầm lương năm vào ô lương tháng (ví dụ: 360 triệu -> chia 12).
    3. Gõ thừa số 0 (ví dụ: 500 triệu cho vị trí phổ thông).
    """
    if salary_vnd is None or np.isnan(salary_vnd):
        return None

    val = float(salary_vnd)

    # 1. Nhầm đơn vị USD vào VNĐ
    if 100.0 <= val <= 10_000.0:
        return val * 25_400.0

    # 2. Nhầm lương năm thành tháng
    jd_lower = jd_text.lower()
    if val > 200_000_000.0 and ("năm" in jd_lower or "annual" in jd_lower or "year" in jd_lower):
        return val / 12.0

    return val


def winsorize_series(
    series: pd.Series, lower_pct: float = 0.01, upper_pct: float = 0.99
) -> pd.Series:
    """Áp dụng Winsorization: Kéo các giá trị ngoài ngưỡng về phân vị 1% và 99%.

    Bảo toàn toàn bộ bản ghi mà không drop hàng.
    """
    valid = series.dropna()
    if len(valid) == 0:
        return series

    p_low = valid.quantile(lower_pct)
    p_high = valid.quantile(upper_pct)

    return series.clip(lower=p_low, upper=p_high)
