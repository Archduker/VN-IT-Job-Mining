# -*- coding: utf-8 -*-
"""preprocessing.missing_outlier.quality_rules
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Module luật kiểm tra toàn vẹn logic & tính điểm chất lượng bản ghi (quality_score).

Cơ sở: TASKS.md mục 6.3.5 và reports/quality/outlier_spec.md mục 5 (QR1-QR5).
Nguyên tắc: KHÔNG sửa dữ liệu, KHÔNG drop dòng — chỉ gắn cờ vi phạm và trừ điểm;
mọi vết can thiệp số học đã do `outlier_handler.apply_outlier_pipeline()` ghi lại.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

# Trọng số trừ quality_score (khởi điểm mỗi bản ghi = 1.0)
PENALTY_SALARY_RANGE = 0.25      # QR1: salary_min > salary_max
PENALTY_EXPERIENCE = 0.20        # QR2: min_experience_years ngoài [0, 30]
PENALTY_DATE_ORDER = 0.20        # QR3: deadline < posted_date
PENALTY_NEGATIVE_SALARY = 0.30   # QR4: lương âm
PENALTY_MULTIPLE_FIXES = 0.35    # QR5: cả hai cột lương đều bị sửa lỗi số
PENALTY_SINGLE_FIX = 0.10        # Một cột lương bị sửa lỗi số (R1/R2/R3)
PENALTY_OUTLIER_CAPPED = 0.05    # Hàng từng bị Winsorization capping
PENALTY_GENAI_IMPUTED = 0.05     # Hàng được GenAI bù khuyết (minh bạch kiểm toán)

MIN_EXPERIENCE_YEARS = 0.0
MAX_EXPERIENCE_YEARS = 30.0


def _has_num_col(df: pd.DataFrame, col: str) -> bool:
    return col in df.columns


def _is_fixed(v: Any) -> bool:
    """Nhãn vết sửa lỗi số chỉ hợp lệ khi là chuỗi không rỗng.

    Bẫy pandas: `None` gán vào cột DataFrame bị biến thành `NaN` (float), nên
    không thể dùng `v is not None` — phải kiểm tra kiểu chuỗi tường minh.
    """
    return isinstance(v, str) and len(v) > 0


def add_quality_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Gắn cờ vi phạm 5 luật toàn vẹn logic QR1-QR5 lên bản sao DataFrame.

    Cột sinh ra (chỉ khi cột nguồn tồn tại):
      - violation_salary_range      (QR1)
      - violation_negative_salary   (QR4)
      - violation_experience_range  (QR2)
      - violation_date_order        (QR3)
      - violation_multiple_fixes    (QR5)
    """
    out = df.copy()

    smin = (pd.to_numeric(out["salary_min_vnd"], errors="coerce")
            if _has_num_col(out, "salary_min_vnd") else None)
    smax = (pd.to_numeric(out["salary_max_vnd"], errors="coerce")
            if _has_num_col(out, "salary_max_vnd") else None)

    if smin is not None and smax is not None:
        both = smin.notna() & smax.notna()
        out["violation_salary_range"] = (both & (smin > smax)).fillna(False)
        out["violation_negative_salary"] = ((smin < 0) | (smax < 0)).fillna(False)
    elif smax is not None:
        out["violation_negative_salary"] = (smax < 0).fillna(False)
    elif smin is not None:
        # Trường hợp hiếm: chỉ có một cột lương trong bảng vẫn phải bắt được lương âm
        out["violation_negative_salary"] = (smin < 0).fillna(False)

    if _has_num_col(out, "min_experience_years"):
        exp = pd.to_numeric(out["min_experience_years"], errors="coerce")
        out["violation_experience_range"] = (
            (exp < MIN_EXPERIENCE_YEARS) | (exp > MAX_EXPERIENCE_YEARS)
        ).fillna(False)

    if "raw_posted_date" in out.columns and "raw_deadline" in out.columns:
        # Ngày nguồn VN mang dạng dd/mm/YYYY -> bắt buộc dayfirst để không lật ngược ngày/tháng
        posted = pd.to_datetime(out["raw_posted_date"], errors="coerce", dayfirst=True)
        deadline = pd.to_datetime(out["raw_deadline"], errors="coerce", dayfirst=True)
        both = posted.notna() & deadline.notna()
        out["violation_date_order"] = (both & (deadline < posted)).fillna(False)

    # QR5: đếm số cột lương từng bị sửa lỗi số (vết `_fix` từ outlier_handler)
    fix_masks: List[pd.Series] = []
    for fix_col in ("salary_min_vnd_fix", "salary_max_vnd_fix"):
        if fix_col in out.columns:
            fix_masks.append(out[fix_col].apply(_is_fixed))
    if len(fix_masks) == 2:
        out["violation_multiple_fixes"] = fix_masks[0] & fix_masks[1]

    return out


def compute_quality_score(df: pd.DataFrame) -> pd.DataFrame:
    """Tính cột `quality_score` (0.0 - 1.0) cho từng bản ghi theo trọng số trừ dần.

    Khởi điểm 1.0; trừ điểm theo từng luật QR vi phạm, mỗi vết sửa lỗi số,
    hàng bị cap ngoại lai và hàng được GenAI bù khuyết. Clip về [0, 1].
    """
    out = add_quality_flags(df)
    score = pd.Series(1.0, index=out.index)

    penalty_map = [
        ("violation_salary_range", PENALTY_SALARY_RANGE),
        ("violation_experience_range", PENALTY_EXPERIENCE),
        ("violation_date_order", PENALTY_DATE_ORDER),
        ("violation_negative_salary", PENALTY_NEGATIVE_SALARY),
        ("violation_multiple_fixes", PENALTY_MULTIPLE_FIXES),
        ("is_outlier_capped", PENALTY_OUTLIER_CAPPED),
        ("is_imputed_by_genai", PENALTY_GENAI_IMPUTED),
    ]
    for col, penalty in penalty_map:
        if col in out.columns:
            score -= out[col].astype(bool).fillna(False).astype(float) * penalty

    # Trừ theo từng cột lương bị sửa lỗi số (tránh cộng dồn trùng với QR5)
    for fix_col in ("salary_min_vnd_fix", "salary_max_vnd_fix"):
        if fix_col in out.columns:
            score -= out[fix_col].apply(_is_fixed).astype(float) * PENALTY_SINGLE_FIX

    out["quality_score"] = score.clip(0.0, 1.0).round(3)
    return out


def summarize_quality(df: pd.DataFrame) -> Dict[str, Any]:
    """Thống kê phục vụ báo cáo audit `reports/quality/outlier_and_quality_audit_report.md`."""
    scored = compute_quality_score(df)
    summary: Dict[str, Any] = {
        "total_records": int(len(scored)),
        "quality_score_mean": round(float(scored["quality_score"].mean()), 3)
        if len(scored) else None,
        "quality_score_min": round(float(scored["quality_score"].min()), 3)
        if len(scored) else None,
        "records_below_0_5": int((scored["quality_score"] < 0.5).sum()),
        "violation_counts": {},
    }
    for col in ("violation_salary_range", "violation_experience_range",
                "violation_date_order", "violation_negative_salary",
                "violation_multiple_fixes"):
        if col in scored.columns:
            summary["violation_counts"][col] = int(scored[col].sum())
    if "is_outlier_capped" in scored.columns:
        summary["violation_counts"]["is_outlier_capped"] = int(scored["is_outlier_capped"].sum())
    return summary
