# -*- coding: utf-8 -*-
"""Bước 10 (PH8): rời rạc hóa lương và kinh nghiệm. Thiếu giá trị = -1 (không điền mean/median)."""

from __future__ import annotations

import numpy as np
import pandas as pd

SALARY_EDGES_M = (10, 20, 35, 60)  # triệu VND/tháng [ĐỀ XUẤT]: <10, 10-20, 20-35, 35-60, >=60


def exp_bin(x) -> int:
    """0 = dưới 1 năm, 1 = 1-2, 2 = 3-5, 3 = trên 5; -1 = không có."""
    if x is None or x != x:
        return -1
    return 0 if x < 1 else 1 if x < 3 else 2 if x <= 5 else 3


def discretize(df: pd.DataFrame, salary_ref_m: pd.Series) -> pd.DataFrame:
    """salary_ref_m: lương tham chiếu (triệu/tháng), NaN nếu tin không có lương."""
    has = salary_ref_m.notna()
    out = pd.DataFrame(index=df.index)
    out["salary_bin_range"] = np.where(has, np.searchsorted(SALARY_EDGES_M, salary_ref_m.fillna(0), side="right"), -1)
    eq = pd.Series(-1, index=df.index)
    if has.sum() >= 5:
        eq[has] = pd.qcut(salary_ref_m[has], 5, labels=False, duplicates="drop")
    out["salary_bin_eqfreq5"] = eq.astype(int)
    out["exp_bin"] = df["exp_min_years"].map(exp_bin).astype(int)
    return out
