"""Extract experience year bounds and normalize seniority.

Legacy parse_experience()/infer_seniority() APIs remain available. The Duy
handbook uses ordinal seniority levels 0..4; -1 denotes unknown/unclassifiable.
"""
from __future__ import annotations

import math
import numbers
import re
import unicodedata
from dataclasses import dataclass
from typing import Any


def _text(value: Any) -> str:
    if value is None or value.__class__.__name__ in {"NAType", "NaTType"}:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    if isinstance(value, dict):
        return " ".join(_text(v) for v in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_text(v) for v in value)
    return str(value)


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFD", text.casefold().replace("đ", "d"))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", text).strip()


@dataclass(frozen=True)
class ExperienceParseResult:
    exp_min_years: float | None
    exp_max_years: float | None
    seniority_level: int
    experience_parse_status: str


_NUM = r"\d+(?:[.,]\d+)?"
_UNIT = r"(?:years?|yrs?|nam)"
_RANGE = re.compile(rf"(?<!\d)(?P<min>{_NUM})\s*(?:-|–|—|to|den)\s*(?P<max>{_NUM})\s*{_UNIT}\b", re.I)
_AT_LEAST = re.compile(
    rf"(?:at\s+least|minimum(?:\s+of)?|min\.?|from|starting\s+from|"
    rf"it\s+nhat|toi\s+thieu|tren|hon|tu)\s*"
    rf"(?P<min>{_NUM})\s*(?:\+\s*)?{_UNIT}\b",
    re.I,
)
_PLUS = re.compile(rf"(?P<min>{_NUM})\s*\+\s*{_UNIT}\b", re.I)
_UP_TO = re.compile(
    rf"(?:up\s+to|at\s+most|maximum(?:\s+of)?|toi\s+da|"
    rf"khong\s+qua|duoi|len\s+den|len\s+toi)\s*(?P<max>{_NUM})\s*{_UNIT}\b",
    re.I,
)
# N11a-N11e (PH6): chuỗi thật của careerviet, glints, itviec, jobsgo, topcv
_ZERO_ONLY = re.compile(r"^(?:khong\s+yeu\s+cau|khong\s+can|khong\s+doi\s+hoi)$")
_UNDER_ONE_WORD = re.compile(r"\bduoi\s+mot\s+nam\b")
# itviec "3.1 năm (37 tháng)": K4 chốt đọc phần nguyên của số năm (3.1 -> 3, 0.8 -> 0, 5.1 -> 5)
_COMPOUND = re.compile(rf"^(?P<years>{_NUM})\s*{_UNIT}\s*\(\s*(?P<months>\d+)\s*(?:months?|thang)\s*\)$", re.I)
_SINGLE = re.compile(rf"(?P<min>{_NUM})\s*{_UNIT}\s*(?:of\s+)?(?:experience|kinh\s+nghiem)?", re.I)
_MONTHS = re.compile(r"(?P<months>\d+(?:[.,]\d+)?)\s*(?:months?|mos?\.?|thang)\b", re.I)
_NO_EXPERIENCE = re.compile(r"(?:khong\s+yeu\s+cau\s+kinh\s+nghiem|khong\s+can\s+kinh\s+nghiem|khong\s+doi\s+hoi\s+kinh\s+nghiem|no\s+experience\s+(?:required|needed)|without\s+experience|fresh\s+graduate|entry[- ]level\s+no\s+experience)", re.I)

SENIORITY_LEVELS = {"Intern/Fresher": 0, "Junior": 1, "Middle": 2, "Senior": 3, "Lead/Manager": 4}
UNKNOWN_SENIORITY = -1
SENIORITY_TITLE_RULES: tuple[tuple[int, tuple[str, ...]], ...] = (
    (0, (r"\bintern\b", r"\binternship\b", r"thuc tap sinh", r"thuc tap", r"\bfresher\b", r"\bgraduate\b", r"moi tot nghiep")),
    (4, (r"\bteam lead\b", r"\blead\b", r"\bleader\b", r"\bmanager\b", r"\bdirector\b", r"\bhead\s+of\b", r"truong nhom", r"truong phong", r"quan ly", r"giam doc", r"cap cao hon")),
    (3, (r"\bsenior\b", r"\bsr\b", r"chuyen vien cao cap", r"ky su cao cap")),
    (2, (r"\bmiddle\b", r"\bmid[- ]level\b", r"\bmid\b")),
    (1, (r"\bjunior\b", r"\bjr\b")),
)


def _to_float(value: str) -> float:
    return float(value.replace(",", "."))


def parse_experience_range(*values: Any) -> tuple[float | None, float | None, str]:
    """Return (exp_min_years, exp_max_years, status), without imputation."""
    for value in values:
        if isinstance(value, numbers.Real) and not isinstance(value, bool):
            number = float(value)
            if math.isfinite(number) and number >= 0:
                return number, None, "numeric_input"

    texts = [_text(value).strip() for value in values]
    raw_texts = [value for value in texts if value]
    if not raw_texts:
        return None, None, "missing"
    folded_texts = [_fold(value) for value in raw_texts]
    text = " ".join(folded_texts)

    compound = next((_COMPOUND.match(c) for c in folded_texts if _COMPOUND.match(c)), None)
    if compound:
        return float(int(_to_float(compound.group("years")))), None, "compound_years_months"
    if _UNDER_ONE_WORD.search(text):
        return 0.0, 1.0, "upper_bound"
    if any(_ZERO_ONLY.match(c) for c in folded_texts):
        return 0.0, None, "explicit_zero"

    if (
        _NO_EXPERIENCE.search(text)
        or re.search(r"\bchua\s+co\s+kinh\s+nghiem\b", text)
    ):
        return 0.0, None, "explicit_zero"
    match = _RANGE.search(text)
    if match:
        low, high = _to_float(match.group("min")), _to_float(match.group("max"))
        return min(low, high), max(low, high), "range"
    match = _AT_LEAST.search(text) or _PLUS.search(text)
    if match:
        return _to_float(match.group("min")), None, "lower_bound"
    match = _UP_TO.search(text)
    if match:
        return 0.0, _to_float(match.group("max")), "upper_bound"

    explicit_context = bool(re.search(r"(?:experience|kinh\s+nghiem|years?\s+of\s+experience)", text))
    for candidate in folded_texts:
        standalone = bool(re.fullmatch(rf"\s*{_NUM}\s*{_UNIT}(?:\s+(?:of\s+)?(?:experience|kinh\s+nghiem))?\s*", candidate))
        if standalone or explicit_context:
            match = _SINGLE.search(candidate if standalone else text)
            if match:
                return _to_float(match.group("min")), None, "single_value"

    month_match = _MONTHS.search(text)

    # Cho phép chuỗi kinh nghiệm chỉ chứa số tháng,
    # ví dụ: "24 months", "12 months", "24 thang".
    standalone_month_match = None
    for candidate in folded_texts:
        match = _MONTHS.fullmatch(candidate)
        if match:
                standalone_month_match = match
                break

    if standalone_month_match is not None:
        month_match = standalone_month_match

    if month_match and (
    explicit_context or standalone_month_match is not None
    ):
        return (
            _to_float(month_match.group("months")) / 12.0,
            None,
            "months_converted",
        )
# Không nhận diện được kinh nghiệm thì trả về unparsed.
    return None, None, "unparsed"

def parse_experience(*values: Any) -> tuple[float | None, float | None]:
    """Backward-compatible wrapper: return minimum and maximum experience."""
    minimum, maximum, status = parse_experience_range(*values)

    # Các trường hợp biểu diễn một giá trị đơn:
    # "Không yêu cầu kinh nghiệm" -> (0, 0)
    # "2 năm"                    -> (2, 2)
    # Numeric input              -> (2, 2)
    if status in {
        "explicit_zero",
        "numeric_input",
        "single_value",
        "months_converted",
    }:
        maximum = minimum

    return minimum, maximum


def _seniority_from_text(value: Any) -> int | None:
    text = _fold(_text(value))
    if not text:
        return None
    for level, patterns in SENIORITY_TITLE_RULES:
        if any(re.search(pattern, text) for pattern in patterns):
            return level
    # Generic employee labels do not identify an ordinal level.
    if re.search(r"\b(nhan vien|staff|employee|individual contributor)\b", text):
        return None
    return None


def infer_seniority(job_title: Any = "", exp_min_years: float | None = None,
                    context: Any = "", raw_seniority_text: Any = None) -> str:
    """Return a readable label; explicit title/board seniority wins over years."""
    level = _seniority_from_text(job_title)
    if level is None:
        level = _seniority_from_text(raw_seniority_text)
    if level is not None:
        return next(label for label, ordinal in SENIORITY_LEVELS.items() if ordinal == level)
    if exp_min_years is None:
        return "Chưa rõ"
    if exp_min_years >= 5:
        return "Senior"
    if exp_min_years >= 2:
        return "Middle"
    if exp_min_years > 0:
        return "Junior"
    return "Intern/Fresher"


def normalize_seniority(job_title: Any = "", raw_seniority_text: Any = None,
                        exp_min_years: float | None = None) -> int:
    """Return Duy handbook ordinal 0..4; -1 means no defensible classification."""
    level = _seniority_from_text(job_title)
    if level is None:
        level = _seniority_from_text(raw_seniority_text)
    if level is not None:
        return level
    if exp_min_years is None or not math.isfinite(float(exp_min_years)):
        return UNKNOWN_SENIORITY
    if exp_min_years >= 5:
        return 3
    if exp_min_years >= 2:
        return 2
    if exp_min_years > 0:
        return 1
    return 0


def extract_experience_and_seniority(job_title: Any = "", *text_fields: Any,
                                     raw_seniority_text: Any = None) -> ExperienceParseResult:
    minimum, maximum, status = parse_experience_range(*text_fields)
    level = normalize_seniority(job_title, raw_seniority_text, minimum)
    return ExperienceParseResult(minimum, maximum, level, status)
