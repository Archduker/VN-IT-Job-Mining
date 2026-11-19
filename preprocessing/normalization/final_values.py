# -*- coding: utf-8 -*-
"""Bước 04, luật mới 2.2 (docs/spec/preprocessing/04_normalization.md, người dùng duyệt 19/11/2026).

Chọn giá trị cuối từ các cột T9 mà bước 03 đã trích (bước 04 không đọc lại JD), theo các quyết định ghi trong
`preprocessing/dictionaries/jd_extraction.json` → `decisions`:

- N14: `work_mode` = ô của sàn → (JD thắng khi lệch và tín hiệu mạnh) → JD → luật địa điểm cũ → unknown.
- N19: `employment_type` = tiêu đề có Intern (mẫu EI1) → ô của sàn → JD → null.
- M4: `exp_min_years` = itviec lấy JD trước, JSON-LD dự phòng; 7 nguồn còn lại lấy ô của sàn trước, JD bù.
- Q1: tin còn dịch hỏng thì cách ly (không vào `all.parquet`).

Hàm thuần: không đọc hay ghi file ngoài từ điển đã duyệt, không gọi model.
"""
from __future__ import annotations

import math
import re
from functools import lru_cache
from typing import Any, Dict, Optional, Tuple

from preprocessing.transformation.jd_extractor import load_rules, norm

EXP_CONFLICT_YEARS = 1.0  # ô và JD lệch từ 1 năm thì gắn exp_conflict (đặc tả 04 M4)


def _has(v: Any) -> bool:
    return v is not None and not (isinstance(v, float) and math.isnan(v))


def _truthy(v: Any) -> bool:
    return bool(v) and _has(v)


# ---------------------------------------------------------------- N14
def final_work_mode(rec: Dict[str, Any], old_rule_mode: str) -> Tuple[str, str]:
    """(work_mode, work_mode_source). `old_rule_mode` là kết quả luật N14 cũ (địa điểm, tiêu đề)."""
    raw, jd = rec.get("work_mode_raw"), rec.get("work_mode_jd")
    if _has(raw):
        if _has(jd) and _truthy(rec.get("work_mode_conflict")) and _truthy(rec.get("work_mode_jd_strong")):
            return jd, "jd_over_raw"
        return raw, "raw"
    if _has(jd):
        return jd, "jd"
    if old_rule_mode and old_rule_mode != "unknown":
        return old_rule_mode, "location"
    return "unknown", "unknown"


# ---------------------------------------------------------------- N19
@lru_cache(maxsize=1)
def _intern_title_re() -> re.Pattern:
    """Mẫu EI1 trong từ điển đã duyệt (`jd_extraction.json`), để N19 và bước 03 dùng cùng một định nghĩa."""
    rules = load_rules()
    for p in rules.employment_type.patterns:
        if p.id == "EI1":
            return p.rx
    raise ValueError("jd_extraction.json thiếu mẫu EI1 (tiêu đề Intern)")


def title_is_intern(title: Any) -> bool:
    return bool(title) and bool(_intern_title_re().search(norm(title)))


def final_employment_type(rec: Dict[str, Any]) -> Tuple[Optional[str], str]:
    """(employment_type, employment_type_source): title | raw | jd | unknown."""
    if title_is_intern(rec.get("job_title_clean") or rec.get("job_title")):
        return "internship", "title"
    if _has(rec.get("employment_type_raw")):
        return rec["employment_type_raw"], "raw"
    if _has(rec.get("employment_type_jd")):
        return rec["employment_type_jd"], "jd"
    return None, "unknown"


# ---------------------------------------------------------------- M4
def select_experience(source: str, rec: Dict[str, Any]) -> Dict[str, Any]:
    """Chọn `exp_min_years` trước khi điền theo cấp bậc. `exp_source` None nghĩa là cả ô và JD đều trống."""
    raw, jd = rec.get("exp_min_years"), rec.get("exp_min_years_jd")
    raw = float(raw) if _has(raw) else None
    jd = float(jd) if _has(jd) else None
    jd_src = "jd_zero" if rec.get("exp_jd_kind") == "jd_zero" else "jd"
    if source == "itviec":
        val, src = (jd, jd_src) if jd is not None else ((raw, "itviec_jsonld") if raw is not None else (None, None))
    else:
        val, src = (raw, "raw") if raw is not None else ((jd, jd_src) if jd is not None else (None, None))
    return {"exp_min_years": val, "exp_source": src,
            "exp_conflict": raw is not None and jd is not None and abs(raw - jd) >= EXP_CONFLICT_YEARS,
            "exp_min_years_parsed": raw}


# ---------------------------------------------------------------- Q1
QUARANTINE_REASONS = {"TRANSLATION_FAILED": "Dịch EN→VI vẫn hỏng sau khi dịch lại (bước 03 T6b)"}


def quarantine_reason(rec: Dict[str, Any]) -> Optional[str]:
    """Q1: lý do cách ly, hoặc None nếu tin được vào `all.parquet`."""
    return "TRANSLATION_FAILED" if rec.get("translation_status") == "failed" else None
