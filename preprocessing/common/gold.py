# -*- coding: utf-8 -*-
"""Đọc và kiểm nhãn bộ gold 100 JD (docs/spec/preprocessing/spec/PH1_gold_va_profiling.md).

Nhãn do `scripts/gold_labeler.html` xuất. Trường vắng hoặc null = "chưa gán"; "not_stated"/"unknown"/"none" = đã gán là JD không ghi.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from preprocessing.common import REPO_ROOT

SENIORITY = ("Intern/Fresher", "Junior", "Middle", "Senior", "Lead/Manager", "unknown")
SECTIONS = ("mo_ta", "yeu_cau", "uu_tien", "phuc_loi", "khac")
WORK_MODES = ("onsite", "remote", "hybrid", "unknown")
SALARY_KINDS = ("negotiable", "not_stated", "value")
FIELDS = ("it", "salary", "experience_years", "seniority", "location", "sections", "skills", "benefits")


def _province_keys() -> set:
    data = json.loads((REPO_ROOT / "preprocessing" / "dictionaries" / "provinces_34.json").read_text(encoding="utf-8"))
    return {p["key"] for p in data["provinces"]}


def _bad(job_id: str, field: str, why: str) -> ValueError:
    return ValueError(f"nhãn gold {job_id}: trường {field} {why}")


def validate_label(job_id: str, lab: Dict[str, Any], provinces: set | None = None) -> None:
    provinces = provinces if provinces is not None else _province_keys()
    for f in lab:
        if f not in FIELDS:
            raise _bad(job_id, f, "không có trong schema")
    if lab.get("it") not in (None, "it", "non_it"):
        raise _bad(job_id, "it", f"giá trị lạ {lab['it']!r}")
    if lab.get("seniority") not in (None, *SENIORITY):
        raise _bad(job_id, "seniority", f"giá trị lạ {lab['seniority']!r}")
    exp = lab.get("experience_years")
    if exp not in (None, "not_stated") and not (isinstance(exp, (int, float)) and not isinstance(exp, bool) and exp >= 0):
        raise _bad(job_id, "experience_years", f"phải là số >= 0 hoặc not_stated, nhận {exp!r}")
    sal = lab.get("salary")
    if sal is not None:
        if sal.get("kind") not in SALARY_KINDS:
            raise _bad(job_id, "salary", f"kind lạ {sal.get('kind')!r}")
        if sal["kind"] == "value":
            lo, hi = sal.get("min"), sal.get("max")
            if lo is None and hi is None:
                raise _bad(job_id, "salary", "kind=value cần min hoặc max")
            if lo is not None and hi is not None and lo > hi:
                raise _bad(job_id, "salary", "min > max")
            if sal.get("currency") not in ("VND", "USD") or sal.get("period") not in ("month", "year", "hour"):
                raise _bad(job_id, "salary", "thiếu currency (VND|USD) hoặc period (month|year|hour)")
    loc = lab.get("location")
    if loc is not None:
        if loc.get("work_mode") not in (None, *WORK_MODES):
            raise _bad(job_id, "location", f"work_mode lạ {loc.get('work_mode')!r}")
        provs = loc.get("provinces")
        if provs not in (None, "not_stated"):
            unknown = [p for p in provs if p not in provinces]
            if unknown:
                raise _bad(job_id, "location", f"tỉnh không thuộc 34 tỉnh: {unknown}")
    secs = lab.get("sections")
    if secs not in (None, "none"):
        for s in secs:
            if s.get("section") not in SECTIONS or not (0 <= s.get("start", -1) < s.get("end", -1)):
                raise _bad(job_id, "sections", f"đoạn sai {s!r}")
    ben = lab.get("benefits")
    if ben not in (None, "none") and not (isinstance(ben, list) and all(isinstance(b, str) and b.strip() for b in ben)):
        raise _bad(job_id, "benefits", f"phải là danh sách tên phúc lợi hoặc none, nhận {ben!r}")
    skills = lab.get("skills")
    if skills not in (None, "none"):
        for s in skills:
            if not str(s.get("name") or "").strip() or s.get("level") not in ("required", "preferred"):
                raise _bad(job_id, "skills", f"kỹ năng sai {s!r}")


def load_gold(path: Path | str) -> Dict[str, Dict[str, Any]]:
    """Đọc file nhãn xuất từ gold_labeler.html, kiểm schema, trả {job_id: nhãn}."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("version") != 1 or not isinstance(data.get("labels"), dict):
        raise ValueError("file nhãn gold sai định dạng (cần version=1 và labels)")
    provinces = _province_keys()
    for job_id, lab in data["labels"].items():
        validate_label(job_id, lab, provinces)
    return data["labels"]


def coverage(labels: Dict[str, Dict[str, Any]]) -> Dict[str, int]:
    """Số JD đã gán từng trường."""
    return {f: sum(1 for lab in labels.values() if lab.get(f) is not None) for f in FIELDS}
