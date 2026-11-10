# -*- coding: utf-8 -*-
"""PH7 M1-M8: luật thiếu và ngoại lai, hàm thuần (không đọc/ghi file, không điền lương, không mean/median/mode)."""

from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd

from preprocessing.common.constants import SALARY_VALID_MAX_VND, SALARY_VALID_MIN_VND
from preprocessing.normalization.text_cleaner import level_by_years


def _has(v: Any) -> bool:
    return v is not None and not (isinstance(v, float) and pd.isna(v))


def salary_status(salary_min: Any, salary_max: Any, negotiable: bool) -> Dict[str, Any]:
    """M1, M2: value | negotiable | not_stated. Có số + thỏa thuận -> value kèm cờ để xem lại."""
    has_num = _has(salary_min) or _has(salary_max)
    status = "value" if has_num else ("negotiable" if negotiable else "not_stated")
    return {"salary_negotiable": bool(negotiable), "salary_status": status,
            "salary_negotiable_with_value": bool(has_num and negotiable)}


def infer_level_from_experience(seniority: Optional[str], exp_min: Any) -> Dict[str, Any]:
    """M3c: chỉ khi cấp bậc trống và có exp_min (ngưỡng X6). Cấp có sẵn (raw/title): level_inferred=False."""
    if seniority:
        return {"seniority": seniority, "level_inferred": False, "from_years": False}
    lv = level_by_years(exp_min) if _has(exp_min) else None
    if lv:
        return {"seniority": lv, "level_inferred": True, "from_years": True}
    return {"seniority": None, "level_inferred": False, "from_years": False}


def infer_experience_from_level(exp_min: Any, seniority: Optional[str], seniority_source: Optional[str]) -> Dict[str, Any]:
    """M4: chỉ Intern/Fresher từ raw/title mới được điền 0 (có cờ). Cấp suy từ số năm bị từ chối (chống vòng)."""
    if _has(exp_min):
        return {"exp_min_years": exp_min, "exp_inferred": False, "exp_source": "given"}
    if seniority == "Intern/Fresher" and seniority_source in ("raw", "title"):
        return {"exp_min_years": 0.0, "exp_inferred": True, "exp_source": "level_intern_fresher"}
    return {"exp_min_years": None, "exp_inferred": False, "exp_source": "unknown"}


def tinh_status(tinh: Optional[str], work_mode: Optional[str], foreign: bool) -> str:
    """M7: ok | remote | foreign | unknown (không điền mode Hà Nội/TP.HCM)."""
    if work_mode == "remote":
        return "remote"
    if foreign and not tinh:
        return "foreign"
    return "ok" if tinh else "unknown"


def range_flags(salary_min: Any, salary_max: Any, exp_min: Any, exp_max: Any) -> Dict[str, bool]:
    """M5, M8: chỉ cờ, không sửa. Khoảng lương hợp lệ 2-100 triệu/tháng (X3)."""
    vals = [float(v) for v in (salary_min, salary_max) if _has(v)]
    out_range = any(v < SALARY_VALID_MIN_VND or v > SALARY_VALID_MAX_VND for v in vals)
    return {
        "salary_out_of_range": out_range,
        "salary_min_gt_max": bool(_has(salary_min) and _has(salary_max) and float(salary_min) > float(salary_max)),
        "exp_out_of_range": bool((_has(exp_min) and float(exp_min) >= 15) or (_has(exp_max) and float(exp_max) > 20)),
    }
