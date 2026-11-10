# -*- coding: utf-8 -*-
"""preprocessing.missing_outlier.outlier_handler
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Module kiểm định ngoại lai định lượng bằng phương pháp IQR và Winsorization.

Quy tắc:
  - Áp dụng cho 2 biến liên tục: mức lương (VND/tháng) và số năm kinh nghiệm.
  - Không sửa số lương (PH6 N10b): chỉ gắn cờ ngoại lai (PH7).
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
    """Trả đúng số lương vào (chữ ký giữ để không vỡ caller).

    PH6 N10b: bỏ hai nhánh sai. Chia 12 khi JD có chữ "năm" làm hỏng `8000 - 9000 USD`
    (203,2-228,6 triệu/tháng thành 16,9-19,1 triệu): chữ "năm" có trong gần như mọi JD ("2 năm kinh nghiệm").
    Nhân 25.400 khi 100..10.000 coi số VND nhỏ là USD một cách mù quáng. Đơn vị tiền và chu kỳ do bước 03
    (salary_parser: salary_currency_raw, salary_period_raw, bằng chứng trong chính tin) quyết, không sửa ở đây.
    """
    if salary_vnd is None or np.isnan(salary_vnd):
        return None
    return float(salary_vnd)


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


def iqr_flags_by_group(
    values: pd.Series, groups: pd.Series, min_n: int = 30, multiplier: float = 1.5
) -> pd.DataFrame:
    """PH7 M6: cờ ngoại lai IQR theo nhóm (cấp bậc), dùng `detect_iqr_outliers`; không sửa số.

    Cột: `outlier` (bool), `scope` in {level, pooled, not_enough_data} và cận dưới/trên đã dùng.
    Nhóm có < min_n giá trị: not_enough_data (không cờ). Tin nhóm null: dùng IQR gộp (pooled) nếu gộp đủ min_n.
    """
    out = pd.DataFrame(
        {"outlier": False, "scope": "not_enough_data", "lower": np.nan, "upper": np.nan}, index=values.index
    )
    pooled = detect_iqr_outliers(values, multiplier)
    pooled_ok = pooled["total_records"] >= min_n
    labels = groups.where(groups.notna(), None)
    for key in labels.dropna().unique():
        idx = labels.index[labels == key]
        res = detect_iqr_outliers(values.loc[idx], multiplier)
        if res["total_records"] >= min_n:
            out.loc[idx, ["scope", "lower", "upper"]] = ["level", res["lower_bound"], res["upper_bound"]]
    need_pooled = labels.isna()  # chỉ tin chưa có cấp mới dùng IQR gộp; cấp có < min_n tin: not_enough_data
    if pooled_ok:
        out.loc[need_pooled, ["scope", "lower", "upper"]] = ["pooled", pooled["lower_bound"], pooled["upper_bound"]]
    has_bounds = out["scope"] != "not_enough_data"
    out.loc[has_bounds, "outlier"] = (
        (values[has_bounds] < out.loc[has_bounds, "lower"]) | (values[has_bounds] > out.loc[has_bounds, "upper"])
    ).fillna(False)
    out["outlier"] = out["outlier"].astype(bool)
    return out
