# -*- coding: utf-8 -*-
"""Bước 10c (PH8): đặc trưng xây mới từ cột đã có. Thiếu thì NaN, không điền."""

from __future__ import annotations

import numpy as np
import pandas as pd


def salary_ref_m(df: pd.DataFrame) -> pd.Series:
    """Lương tham chiếu (triệu/tháng): trung bình các cận có số; NaN nếu cả hai cận trống."""
    return pd.concat([df["salary_min_vnd"], df["salary_max_vnd"]], axis=1).mean(axis=1) / 1e6


def salary_target_m(df: pd.DataFrame) -> pd.Series:
    """Mục tiêu lương SD4 (quyết định 4, 19/11): trung bình các cận có số của lương đã cap (như Silver), triệu/tháng.
    Một cận thì lấy cận đó; không cận nào thì NaN. Chỉ để tham chiếu: tên chứa "salary" nên `assert_no_leakage` chặn."""
    return pd.concat([df["salary_min_vnd_capped"], df["salary_max_vnd_capped"]], axis=1).mean(axis=1) / 1e6


def word_count(df: pd.DataFrame) -> pd.Series:
    """Số từ (tách theo khoảng trắng) của mô tả + yêu cầu; thay `n_tokens` của bước 09 (đã bỏ khỏi chuỗi, 19/11)."""
    def n(v) -> int:
        return len(str(v).split()) if isinstance(v, str) else 0
    return pd.Series([n(a) + n(b) for a, b in zip(df["description_clean"], df["requirements_clean"])], index=df.index)


def construct(df: pd.DataFrame, skills: pd.DataFrame) -> pd.DataFrame:
    """skills: bảng 08 (job_id_global, slug, level, kind, type). Đếm theo ba góc nhìn của `skill_view`."""
    from processing.extraction.skills import skill_view
    g = skills.groupby("job_id_global")
    out = pd.DataFrame({"job_id_global": df["job_id_global"].values})
    out["n_skills"] = out["job_id_global"].map(g["slug"].nunique()).fillna(0).astype(int)
    req = skills[skills["level"] == "required"].groupby("job_id_global")["slug"].nunique()
    out["n_required"] = out["job_id_global"].map(req).fillna(0).astype(int)
    out["required_ratio"] = (out["n_required"] / out["n_skills"].where(out["n_skills"] > 0)).astype(float)
    for col, view in (("n_tools", "tool"), ("n_concepts", "concept"), ("n_soft", "soft")):
        v = skill_view(skills, view)
        out[col] = out["job_id_global"].map(v.groupby("job_id_global")["slug"].nunique()).fillna(0).astype(int)
    out["n_tokens"] = word_count(df).astype(float).values
    out["n_benefits"] = [0 if b is None else len(b) for b in df["benefits_std"]]
    lo, hi = df["salary_min_vnd"].values / 1e6, df["salary_max_vnd"].values / 1e6
    both = ~np.isnan(lo) & ~np.isnan(hi)
    mid = np.where(both, (lo + hi) / 2, np.nan)
    out["salary_mid"] = mid
    out["salary_range_ratio"] = np.where(both & (mid > 0), (hi - lo) / np.where(mid > 0, mid, 1), np.nan)
    out["salary_target_m"] = salary_target_m(df).values
    return out
