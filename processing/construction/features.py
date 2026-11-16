# -*- coding: utf-8 -*-
"""Bước 10c (PH8): đặc trưng xây mới từ cột đã có. Thiếu thì NaN, không điền."""

from __future__ import annotations

import numpy as np
import pandas as pd


def salary_ref_m(df: pd.DataFrame) -> pd.Series:
    """Lương tham chiếu (triệu/tháng): trung bình các cận có số; NaN nếu cả hai cận trống."""
    return pd.concat([df["salary_min_vnd"], df["salary_max_vnd"]], axis=1).mean(axis=1) / 1e6


def construct(df: pd.DataFrame, skills: pd.DataFrame, tokens: pd.DataFrame) -> pd.DataFrame:
    """skills: bảng 08 (job_id_global, slug, level); tokens: bảng 09 (job_id_global, n_tokens)."""
    g = skills.groupby("job_id_global")
    out = pd.DataFrame({"job_id_global": df["job_id_global"].values})
    out["n_skills"] = out["job_id_global"].map(g["slug"].nunique()).fillna(0).astype(int)
    out["n_required"] = out["job_id_global"].map(skills[skills["level"] == "required"].groupby("job_id_global")["slug"].nunique()).fillna(0).astype(int)
    out["required_ratio"] = (out["n_required"] / out["n_skills"].where(out["n_skills"] > 0)).astype(float)
    out["n_tokens"] = out["job_id_global"].map(tokens.set_index("job_id_global")["n_tokens"]).astype(float)
    out["n_benefits"] = [0 if b is None else len(b) for b in df["benefits_std"]]
    lo, hi = df["salary_min_vnd"].values / 1e6, df["salary_max_vnd"].values / 1e6
    both = ~np.isnan(lo) & ~np.isnan(hi)
    mid = np.where(both, (lo + hi) / 2, np.nan)
    out["salary_mid"] = mid
    out["salary_range_ratio"] = np.where(both & (mid > 0), (hi - lo) / np.where(mid > 0, mid, 1), np.nan)
    return out
