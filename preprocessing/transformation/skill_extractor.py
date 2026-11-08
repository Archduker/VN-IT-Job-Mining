# -*- coding: utf-8 -*-
"""preprocessing.transformation.skill_extractor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Rút trích kỹ năng và phúc lợi theo luật T7:
- T7a: Làm sạch skills_list từ trường metadata (bỏ tag > 4 từ, tag ngành/việc làm, trùng công ty).
- T7b: Rút kỹ năng từ văn bản JD gốc bằng từ điển song ngữ skills.json (khớp từ nguyên vẹn).
- T7c: Rút phúc lợi bằng từ điển song ngữ benefits.json.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Set

from preprocessing.common import REPO_ROOT

SKILLS_DICT_PATH = REPO_ROOT / "preprocessing" / "dictionaries" / "skills.json"
BENEFITS_DICT_PATH = REPO_ROOT / "preprocessing" / "dictionaries" / "benefits.json"

CATEGORY_STOP_PATTERNS = [
    re.compile(r"^việc làm", re.IGNORECASE),
    re.compile(r"^it\s*-\s*phần mềm", re.IGNORECASE),
    re.compile(r"^công nghệ thông tin", re.IGNORECASE),
    re.compile(r"^lập trình viên$", re.IGNORECASE),
    re.compile(r"^nhân viên", re.IGNORECASE),
    re.compile(r"^chuyên viên", re.IGNORECASE),
]


def load_skills_dict() -> Dict[str, List[str]]:
    if not SKILLS_DICT_PATH.exists():
        return {}
    return json.loads(SKILLS_DICT_PATH.read_text(encoding="utf-8"))


def load_benefits_dict() -> Dict[str, List[str]]:
    if not BENEFITS_DICT_PATH.exists():
        return {}
    return json.loads(BENEFITS_DICT_PATH.read_text(encoding="utf-8"))


def filter_metadata_skills(skills_list: Any, company_name: Optional[str] = None) -> List[str]:
    """T7a: Làm sạch kỹ năng từ trường metadata."""
    if skills_list is None:
        return []
    if isinstance(skills_list, (list, tuple)):
        items = skills_list
    elif hasattr(skills_list, "tolist"):
        items = skills_list.tolist()
    else:
        return []
    if len(items) == 0:
        return []

    c_norm = str(company_name or "").strip().lower()
    cleaned = []
    seen = set()

    for item in items:
        if not item:
            continue
        tag = str(item).strip()
        tag_lower = tag.lower()

        # Bỏ tag > 4 từ
        if len(tag.split()) > 4:
            continue

        # Bỏ tag là danh mục ngành nghề hoặc "Việc làm ..."
        if any(pat.search(tag) for pat in CATEGORY_STOP_PATTERNS):
            continue

        # Bỏ tag trùng tên công ty
        if c_norm and len(c_norm) > 3 and c_norm in tag_lower:
            continue

        if tag_lower not in seen:
            seen.add(tag_lower)
            cleaned.append(tag)

    return cleaned


def extract_skills_from_text(text: str, skills_dict: Optional[Dict[str, List[str]]] = None) -> List[str]:
    """T7b: Khớp từ nguyên vẹn trên văn bản JD gốc bằng từ điển song ngữ."""
    if not text or not text.strip():
        return []

    skills_dict = skills_dict or load_skills_dict()
    text_lower = f" {text.lower()} "
    found_canonical: Set[str] = set()

    for canonical, variants in skills_dict.items():
        for var in variants:
            var_l = var.lower()
            # So khớp từ nguyên vẹn (không bị dính chữ số hoặc ký tự tech đặc thù)
            pattern = rf"(?<![a-zA-Z0-9_#+]){re.escape(var_l)}(?![a-zA-Z0-9_#+])"
            if re.search(pattern, text_lower):
                found_canonical.add(canonical)
                break

    return sorted(found_canonical)


def extract_skills(
    skills_list: Optional[List[str]],
    jd_text: str,
    company_name: Optional[str] = None
) -> List[str]:
    """Gộp T7a và T7b thành skills_clean hoàn chỉnh."""
    skills_field = filter_metadata_skills(skills_list, company_name)
    skills_jd = extract_skills_from_text(jd_text)

    # Gộp không phân biệt hoa thường, giữ tên hiển thị đẹp
    seen = set()
    result = []
    for s in skills_jd + skills_field:
        s_clean = s.strip()
        if s_clean.lower() not in seen:
            seen.add(s_clean.lower())
            result.append(s_clean)

    return result


def extract_benefits(
    benefits_list: Any,
    jd_text: str,
    benefits_dict: Optional[Dict[str, List[str]]] = None
) -> List[str]:
    """T7c: Rút phúc lợi từ benefits_list và văn bản JD gốc."""
    benefits_dict = benefits_dict or load_benefits_dict()
    b_items: List[str] = []
    if benefits_list is not None:
        if isinstance(benefits_list, (list, tuple)):
            b_items = [str(x) for x in benefits_list if str(x).strip()]
        elif hasattr(benefits_list, "tolist"):
            b_items = [str(x) for x in benefits_list.tolist() if str(x).strip()]
    combined_text = " ".join([*b_items, jd_text]).lower()

    matched: List[str] = []
    for std_name, patterns in benefits_dict.items():
        for pat in patterns:
            pat_l = pat.lower()
            if pat_l in combined_text:
                matched.append(std_name)
                break

    return matched
