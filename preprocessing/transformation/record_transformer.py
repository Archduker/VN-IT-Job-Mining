"""Chuyển đổi bản ghi phẳng sang các trường dữ liệu có kiểu và định dạng chuẩn."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

from preprocessing.normalization.text_cleaner import normalize_city
from preprocessing.transformation.salary_parser import parse_salary_cascade

_NUMBER_PATTERN = re.compile(r"[-+]?\d+(?:[.,]\d+)*")


def parse_date_to_iso(value: Any) -> str | None:
    """Chuyển ngày hoặc chuỗi ngày phổ biến về YYYY-MM-DD; giá trị không rõ trả về None."""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if value is None or isinstance(value, bool):
        return None

    text = str(value).strip()
    if not text:
        return None

    iso_text = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    try:
        return datetime.fromisoformat(iso_text).date().isoformat()
    except ValueError:
        pass

    for date_format in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            continue

    return None


def coerce_number(value: Any) -> float | None:
    """Đọc số từ giá trị số hoặc chuỗi có dấu phân cách hàng nghìn/thập phân."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        number = float(value)
        return number if math.isfinite(number) else None

    match = _NUMBER_PATTERN.search(str(value).strip())
    if not match:
        return None

    number_text = match.group()
    if "," in number_text and "." in number_text:
        decimal_separator = "," if number_text.rfind(",") > number_text.rfind(".") else "."
        thousands_separator = "." if decimal_separator == "," else ","
        number_text = number_text.replace(thousands_separator, "")
        number_text = number_text.replace(decimal_separator, ".")
    elif "," in number_text or "." in number_text:
        separator = "," if "," in number_text else "."
        parts = number_text.split(separator)
        if (
            len(parts) > 1
            and len(parts[0].lstrip("+-")) <= 3
            and all(len(part) == 3 for part in parts[1:])
        ):
            number_text = "".join(parts)
        else:
            number_text = parts[0] + "." + "".join(parts[1:])

    try:
        number = float(number_text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _parse_experience_years(value: Any) -> float | None:
    years = coerce_number(value)
    if years is None:
        return None
    if isinstance(value, str) and any(unit in value.lower() for unit in ("tháng", "month")):
        return years / 12.0
    return years


def _parse_headcount(value: Any) -> int | None:
    if isinstance(value, str) and re.search(r"\d\s*[-–—]\s*\d", value):
        return None
    count = coerce_number(value)
    if count is None or not count.is_integer():
        return None
    return int(count)


def _normalize_list(value: Any) -> list[str]:
    values = value if isinstance(value, list | tuple | set) else [value]
    return [str(item).strip() for item in values if item is not None and str(item).strip()]


def normalize_employment_type(value: Any) -> str | None:
    """Chuẩn hóa hình thức tuyển dụng về các nhãn phổ biến, không suy đoán giá trị lạ."""
    if value is None:
        return None
    text = re.sub(r"[_-]+", " ", str(value)).strip().lower()
    if not text:
        return None

    if any(term in text for term in ("full time", "toàn thời gian", "toàn thời")):
        return "Full-time"
    if any(term in text for term in ("part time", "bán thời gian", "bán thời")):
        return "Part-time"
    if any(term in text for term in ("intern", "thực tập", "trainee")):
        return "Internship"
    if any(term in text for term in ("contract", "hợp đồng", "freelance", "cộng tác viên")):
        return "Contract"
    if any(term in text for term in ("temporary", "thời vụ")):
        return "Temporary"
    return None


def normalize_work_mode(value: Any) -> str | None:
    """Chuẩn hóa hình thức làm việc tại văn phòng, từ xa hoặc kết hợp."""
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    if any(term in text for term in ("hybrid", "kết hợp", "linh hoạt")):
        return "Hybrid"
    if any(term in text for term in ("remote", "từ xa", "work from home", "làm tại nhà", "online")):
        return "Remote"
    if any(term in text for term in ("onsite", "on-site", "tại văn phòng", "tại công ty", "trực tiếp")):
        return "Onsite"
    return None


def transform_job_record(
    record: Mapping[str, Any],
    *,
    sgd_to_vnd_rate: float | None = None,
    sgd_fx_rate_date: str | None = None,
) -> dict[str, Any]:
    """Bổ sung các trường chuẩn hóa mà không ghi đè hoặc loại bỏ dữ liệu raw."""
    transformed = dict(record)

    jd_text = " ".join(
        str(record.get(field) or "")
        for field in ("raw_description_text", "raw_requirements_text")
    ).strip()
    salary_result = parse_salary_cascade(
        record.get("raw_salary_text"), jd_text, sgd_to_vnd_rate
    )
    transformed.update(salary_result)
    transformed["salary_currency"] = salary_result["salary_currency_original"]
    if salary_result["salary_currency_original"] == "SGD":
        transformed["salary_fx_rate_to_vnd"] = sgd_to_vnd_rate
        transformed["salary_fx_rate_date"] = sgd_fx_rate_date
        transformed["salary_fx_source"] = (
            "frankfurter_sgd_usd_x_fixed_project_usd_vnd"
            if sgd_to_vnd_rate is not None
            else None
        )
    elif salary_result["salary_currency_original"] == "USD":
        transformed["salary_fx_rate_to_vnd"] = 25_400.0
        transformed["salary_fx_rate_date"] = None
        transformed["salary_fx_source"] = "fixed_project_usd_vnd"
    else:
        transformed["salary_fx_rate_to_vnd"] = 1.0
        transformed["salary_fx_rate_date"] = None
        transformed["salary_fx_source"] = "identity_vnd"
    raw_salary = record.get("raw_salary_text")
    salary_text = str(raw_salary or "").strip()
    declares_zero_salary = bool(
        salary_text
        and re.fullmatch(
            r"0+(?:[.,]0+)?(?:\s*[-–—]\s*0+(?:[.,]0+)?)?"
            r"(?:\s*(?:vnd|vnđ|₫))?",
            salary_text,
            re.IGNORECASE,
        )
    )
    if declares_zero_salary:
        transformed["salary_min_vnd"] = None
        transformed["salary_max_vnd"] = None
        transformed["salary_min_original"] = None
        transformed["salary_max_original"] = None
        transformed["is_negotiable"] = True
        transformed["salary_source"] = "header_negotiable"
    transformed["is_salary_negotiable_declared"] = int(
        bool(salary_text and salary_result.get("is_negotiable")) or declares_zero_salary
    )

    for raw_field, output_field in (
        ("raw_posted_date", "posted_date"),
        ("raw_updated_at", "updated_date"),
        ("raw_deadline", "deadline_date"),
        ("crawled_at", "crawled_at_iso"),
    ):
        transformed[output_field] = parse_date_to_iso(record.get(raw_field))

    location = record.get("raw_location_text")
    if not location:
        locations = _normalize_list(record.get("working_locations"))
        location = locations[0] if locations else None
    transformed["primary_city"] = normalize_city(location)

    transformed["employment_type"] = normalize_employment_type(
        record.get("raw_employment_type")
    )
    transformed["work_mode"] = normalize_work_mode(record.get("raw_work_mode"))
    transformed["min_experience_years"] = _parse_experience_years(
        record.get("raw_experience_text")
    )
    transformed["headcount"] = _parse_headcount(record.get("raw_headcount"))

    for field in ("working_locations", "skills_list", "benefits_list"):
        transformed[field] = _normalize_list(record.get(field))

    return transformed
