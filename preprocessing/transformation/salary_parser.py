"""Parse free-form job salaries into million VND per month.

Accepts plain text, numeric values, dictionaries, and dictionaries serialized as
Python/JSON strings. Negotiable salaries and unsupported periods are never imputed.
"""
from __future__ import annotations

import ast
import json
import math
import numbers
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

# Backward compatibility for existing preprocessing modules.
from .salary_parser_legacy import (
    UniversalSalaryParser as UniversalSalaryParser,
)
from .salary_parser_legacy import (
    parse_salary_cascade as parse_salary_cascade,
)

MONTHLY_MIN_VND = 1_000_000
MONTHLY_MAX_VND = 500_000_000
USD_TO_VND = 25_400.0
VND_PER_MILLION = 1_000_000.0
HOURS_PER_MONTH = 160.0
DAYS_PER_MONTH = 22.0
_NUMBER = (r"(?:\d+(?:[.,]\d+)?[eE][+-]?\d+|"
           r"\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)")
_VALUE_RE = re.compile(
    rf"(?<![\w])(?P<prefix>US\$|\$|USD\s*)?\s*(?P<number>{_NUMBER})"
    r"(?P<scale>\s*(?:k|m|mn|bn|tr(?:iệu)?|triệu|million|billion))?"
    r"(?P<suffix>\s*(?:USD|US\$|VND|VNĐ|đồng|đ))?", re.IGNORECASE,
)
_NEGOTIABLE_RE = re.compile(
    r"\b(?:thoa\s+thuan|canh\s+tranh|negotiable|competitive(?:\s+salary)?|"
    r"salary\s+negotiable|commensurate\s+with\s+experience|deal|thuong\s+luong|"
    r"luong\s+hap\s+dan|trao\s+doi\s+khi\s+phong\s+van)\b", re.IGNORECASE,
)
_RANGE_SEP_RE = re.compile(r"^\s*(?:-|–|—|to|đến)\s*$", re.IGNORECASE)
_UPPER_PREFIX_RE = re.compile(r"(?:up\s+to|max(?:imum)?|at\s+most|khong\s+qua|toi\s+da|len\s+toi|len\s+den)", re.I)
_LOWER_PREFIX_RE = re.compile(r"(?:from|starting\s+(?:at|from)|at\s+least|min(?:imum)?|tu|it\s+nhat|tren|tu\s+tren)", re.I)
_PROJECT_PERIOD_RE = re.compile(r"\b(?:per\s+project|/\s*project|project[- ]based|theo\s+du\s+an)\b", re.I)
_UNSUPPORTED_PERIOD_RE = re.compile(r"(?:/\s*(?:week|weekly|tuan|quarter|shift)|per\s+(?:week|quarter|shift)|weekly|quarterly)", re.I)
_UNSUPPORTED_CURRENCY_RE = re.compile(r"(?:\bEUR\b|\bSGD\b|\bJPY\b|\bAUD\b|\bGBP\b|\bCNY\b|\bCAD\b|€|£|¥)", re.I)


@dataclass(frozen=True)
class SalaryParseResult:
    salary_min: float | None
    salary_max: float | None
    salary_avg: float | None
    is_negotiable: bool
    parse_status: str = "parsed"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _fold_vietnamese(value: str) -> str:
    value = value.casefold().replace("đ", "d")
    value = unicodedata.normalize("NFD", value)
    return "".join(ch for ch in value if unicodedata.category(ch) != "Mn")


def _parse_number(raw: str) -> float:
    """Parse grouping/decimal separators and scientific notation."""
    value = raw.strip().replace("\u00a0", "").replace(" ", "")
    if re.search(r"[eE][+-]?\d+$", value):
        mantissa, exponent = re.split(r"[eE]", value)
        if "." in mantissa and "," in mantissa:
            decimal = "." if mantissa.rfind(".") > mantissa.rfind(",") else ","
            grouping = "," if decimal == "." else "."
            mantissa = mantissa.replace(grouping, "").replace(decimal, ".")
        elif "," in mantissa:
            mantissa = mantissa.replace(",", ".")
        result = float(f"{mantissa}e{exponent}")
    elif "." in value and "," in value:
        decimal = "." if value.rfind(".") > value.rfind(",") else ","
        grouping = "," if decimal == "." else "."
        result = float(value.replace(grouping, "").replace(decimal, "."))
    elif "," in value or "." in value:
        separator = "," if "," in value else "."
        pieces = value.split(separator)
        if len(pieces) > 2 and all(len(piece) == 3 for piece in pieces[1:]):
            value = "".join(pieces)
        elif len(pieces) == 2 and len(pieces[1]) == 3 and len(pieces[0]) <= 3:
            value = "".join(pieces)
        else:
            value = value.replace(separator, ".")
        result = float(value)
    else:
        result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"Non-finite salary number: {raw!r}")
    return result


def _scale_multiplier(scale: str) -> float:
    value = (scale or "").strip().casefold()
    if value == "k":
        return 1_000.0
    if value in {"m", "mn", "tr", "triệu", "million"}:
        return 1_000_000.0
    if value in {"bn", "billion"}:
        return 1_000_000_000.0
    return 1.0


def _period_factor(text: str, period_hint: Any = None) -> tuple[float, str]:
    period = str(period_hint or "").strip().casefold()
    normalized = re.sub(r"[^a-z]+", "", period)
    combined = f"{text} {period}".casefold()
    if normalized in {"project", "perproject", "duan"} or _PROJECT_PERIOD_RE.search(combined):
        return 1.0, "project"
    if normalized in {"year", "yearly", "annual", "annually", "peryear"} or re.search(
        r"(?:/\s*(?:năm|nam|year)|per\s+year|per\s+annum|annually|yearly|hằng\s+năm|hang\s+nam)", combined
    ):
        return 1.0 / 12.0, "year"
    if normalized in {"hour", "hourly", "perhour"} or re.search(r"(?:/\s*(?:giờ|gio|hour)|per\s+hour|hourly)", combined):
        return float(HOURS_PER_MONTH), "hour"
    if normalized in {"day", "daily", "perday"} or re.search(r"(?:/\s*(?:ngày|ngay|day)|per\s+day|daily)", combined):
        return float(DAYS_PER_MONTH), "day"
    if normalized in {"month", "monthly", "permonth", "thang"} or re.search(
        r"(?:/\s*(?:tháng|thang|month)|per\s+month|monthly)", combined
    ):
        return 1.0, "month"
    if _UNSUPPORTED_PERIOD_RE.search(combined) or normalized in {"week", "weekly", "perweek", "quarter", "quarterly", "shift"}:
        return 1.0, "unsupported"
    return 1.0, "unspecified"


def _currency_is_usd(text: str, matches: list[re.Match[str]], currency_hint: Any = None) -> bool:
    hint = str(currency_hint or "").strip().upper()
    if hint in {"USD", "US$", "$", "US DOLLAR"}:
        return True
    if hint in {"VND", "VNĐ", "DONG"}:
        return False
    if re.search(r"US\$|\$|\bUSD\b|\bU\.S\.\s*dollars?\b|đô\s*la", text, re.I):
        return True
    return any((m.group("prefix") or "").strip().upper() in {"$", "US$", "USD"}
               or (m.group("suffix") or "").strip().upper() in {"USD", "US$"} for m in matches)


def _explicit_vnd(text: str, currency_hint: Any = None) -> bool:
    hint = str(currency_hint or "").strip().upper()
    return hint in {"VND", "VNĐ", "DONG"} or bool(re.search(r"\b(?:VND|VNĐ|đồng|đ)\b|₫", text, re.I))


def _to_million_vnd(number: float, scale: str, is_usd: bool,
                    explicit_vnd: bool, explicit_scale: bool) -> float:
    amount = number * _scale_multiplier(scale)
    if is_usd:
        return amount * USD_TO_VND / VND_PER_MILLION
    if explicit_scale or number >= 1_000 or explicit_vnd:
        return amount / VND_PER_MILLION
    # Vietnam salary-box heuristic for bare values such as 15 or 25 (million VND).
    return amount


def _convert_match(match: re.Match[str], is_usd: bool, text: str,
                   common_scale: str = "", currency_hint: Any = None,
                   period_multiplier: float = 1.0) -> float:
    number = _parse_number(match.group("number"))
    local_scale = (match.group("scale") or "").strip()
    scale = local_scale or common_scale
    amount = _to_million_vnd(number, scale, is_usd,
                            _explicit_vnd(text, currency_hint), bool(local_scale or common_scale))
    return amount * period_multiplier


def _normalize_salary_input(raw_salary: Any) -> tuple[str, Any, Any, bool, Mapping[str, Any] | None]:
    """Unwrap salary payloads safely; never execute the serialized string."""
    if isinstance(raw_salary, Mapping):
        payload: Mapping[str, Any] | None = raw_salary
    elif isinstance(raw_salary, str):
        candidate = raw_salary.strip()
        payload = None
        if candidate.startswith("{") and candidate.endswith("}"):
            parsed: Any = None
            try:
                parsed = json.loads(candidate)
            except (json.JSONDecodeError, TypeError):
                try:
                    parsed = ast.literal_eval(candidate)
                except (ValueError, SyntaxError):
                    parsed = None
            if isinstance(parsed, Mapping):
                payload = parsed
        if payload is None:
            return candidate, None, None, False, None
    else:
        return (str(raw_salary).strip() if raw_salary is not None else ""), None, None, False, None

    text = payload.get("salary_text") or payload.get("raw_salary_text") or payload.get("text") or ""
    return (str(text).strip(), payload.get("salary_currency") or payload.get("currency"),
            payload.get("pay_period") or payload.get("period"),
            bool(payload.get("is_negotiable", False)), payload)


def _is_negotiable(text: str, declared_flag: bool = False) -> bool:
    """Correct crawler False flags when the actual text says negotiable."""
    return bool(declared_flag or _NEGOTIABLE_RE.search(_fold_vietnamese(text)))


def _average(low: float | None, high: float | None) -> float | None:
    if low is not None and high is not None:
        return (low + high) / 2.0
    return low if low is not None else high


def _structured_numeric_fallback(payload: Mapping[str, Any], currency: Any,
                                 period: Any) -> SalaryParseResult | None:
    raw_min, raw_max = payload.get("salary_min"), payload.get("salary_max")
    if raw_min is None and raw_max is None:
        return None
    period_multiplier, period_name = _period_factor("", period)
    if period_name in {"project", "unsupported"}:
        return SalaryParseResult(None, None, None, False, "unsupported_period")
    currency_code = str(currency or "").strip().upper()
    is_usd = currency_code in {"USD", "US$", "$"}
    is_vnd = currency_code in {"VND", "VNĐ", "DONG"}
    if currency_code and not (is_usd or is_vnd):
        return SalaryParseResult(None, None, None, False, "unsupported_currency")

    def convert(value: Any) -> float | None:
        if value is None:
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(number):
            return None
        if is_usd:
            return number * USD_TO_VND / VND_PER_MILLION * period_multiplier
        if is_vnd or abs(number) >= 1_000:
            return number / VND_PER_MILLION * period_multiplier
        return number * period_multiplier

    low, high = convert(raw_min), convert(raw_max)
    if low is None and high is None:
        return None
    if low is not None and high is not None and high < low:
        low, high = high, low
    return SalaryParseResult(low, high, _average(low, high), False, "structured_numeric")


def parse_salary(raw_salary: Any) -> SalaryParseResult:
    """Parse salary into million VND/month; negotiable/missing remain None."""
    if raw_salary is None or raw_salary.__class__.__name__ in {"NAType", "NaTType"}:
        return SalaryParseResult(None, None, None, False, "missing")
    if isinstance(raw_salary, numbers.Real) and not isinstance(raw_salary, bool):
        value = float(raw_salary)
        if not math.isfinite(value):
            return SalaryParseResult(None, None, None, False, "missing")
        value = value if abs(value) < 1_000 else value / VND_PER_MILLION
        return SalaryParseResult(value, value, value, False, "numeric_input")

    text, currency_hint, period_hint, declared_negotiable, payload = _normalize_salary_input(raw_salary)
    if _is_negotiable(text, declared_negotiable):
        return SalaryParseResult(None, None, None, True, "negotiable")
    period_multiplier, period_name = _period_factor(text, period_hint)
    if period_name in {"project", "unsupported"}:
        return SalaryParseResult(None, None, None, False, "unsupported_period")
    currency_code = str(currency_hint or "").strip().upper()
    if currency_code and currency_code not in {"USD", "US$", "$", "VND", "VNĐ", "DONG"}:
        return SalaryParseResult(None, None, None, False, "unsupported_currency")
    if not currency_code and _UNSUPPORTED_CURRENCY_RE.search(text):
        return SalaryParseResult(None, None, None, False, "unsupported_currency")
    if not text and payload is not None:
        return (_structured_numeric_fallback(payload, currency_hint, period_hint)
                or SalaryParseResult(None, None, None, False, "missing"))
    if not text:
        return SalaryParseResult(None, None, None, False, "missing")

    matches = list(_VALUE_RE.finditer(text))
    if not matches:
        if payload is not None:
            return (_structured_numeric_fallback(payload, currency_hint, period_hint)
                    or SalaryParseResult(None, None, None, False, "unparsed"))
        return SalaryParseResult(None, None, None, False, "unparsed")

    is_usd = _currency_is_usd(text, matches, currency_hint)
    first = matches[0]
    second = matches[1] if len(matches) > 1 else None
    between = text[first.end():second.start()] if second is not None else ""
    if second is not None and _RANGE_SEP_RE.fullmatch(between):
        trailing = text[second.end():]
        shared_match = re.match(r"\s*(k|m|mn|bn|tr(?:iệu)?|triệu|million|billion)\b", trailing, re.I)
        shared_scale = (second.group("scale") or "").strip()
        if not shared_scale and shared_match:
            shared_scale = shared_match.group(1)
        low = _convert_match(first, is_usd, text, shared_scale, currency_hint, period_multiplier)
        high = _convert_match(second, is_usd, text, shared_scale, currency_hint, period_multiplier)
        if high < low:
            low, high = high, low
        return SalaryParseResult(low, high, _average(low, high), False, "range")

    value = _convert_match(first, is_usd, text, currency_hint=currency_hint,
                           period_multiplier=period_multiplier)
    prefix = _fold_vietnamese(text[:first.start()])
    if _UPPER_PREFIX_RE.search(prefix):
        return SalaryParseResult(None, value, value, False, "upper_bound")
    if _LOWER_PREFIX_RE.search(prefix):
        return SalaryParseResult(value, None, value, False, "lower_bound")
    suffix = _fold_vietnamese(text[first.end():])
    if re.search(r"(?:tro\s+len|and\s+above|or\s+more|\+\s*$)", suffix):
        return SalaryParseResult(value, None, value, False, "lower_bound")
    if re.search(r"(?:tro\s+xuong|or\s+less|at\s+most)", suffix):
        return SalaryParseResult(None, value, value, False, "upper_bound")
    return SalaryParseResult(value, value, value, False, "single_value")


def parse_salary_dict(raw_salary: Any) -> dict[str, Any]:
    """Dictionary-returning wrapper kept for existing callers."""
    return parse_salary(raw_salary).to_dict()
