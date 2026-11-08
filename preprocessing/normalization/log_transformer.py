# -*- coding: utf-8 -*-
"""preprocessing.normalization.log_transformer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Biến đổi phân phối số học Log-Transformation và co giãn thang đo Robust Scaling.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def log_transform_salary(series: pd.Series) -> pd.Series:
    """Biến đổi Log-Transformation y = log(1 + x) cho mức lương.

    Giúp nén phân phối lệch phải (Right-Skewed) về dạng gần chuẩn (Gaussian-like).
    """
    return np.log1p(series)


def robust_scale_series(series: pd.Series) -> pd.Series:
    """Co giãn thang đo RobustScaler sử dụng Median và IQR (kháng ngoại lai).

    Công thức: x_scaled = (x - median) / IQR
    """
    valid = series.dropna()
    if len(valid) == 0:
        return series

    med = valid.median()
    q1 = valid.quantile(0.25)
    q3 = valid.quantile(0.75)
    iqr = q3 - q1

    if iqr == 0:
        return series - med

    return (series - med) / iqr
