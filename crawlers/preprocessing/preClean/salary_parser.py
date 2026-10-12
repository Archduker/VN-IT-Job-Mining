# -*- coding: utf-8 -*-
"""crawlers.preprocessing.preClean.salary_parser
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Bộ phân tích và chuẩn hóa mức lương:
- Chuẩn hóa đơn vị tiền tệ (VND / USD).
- Quy đổi giá trị triệu (VD: 10 - 20 triệu -> 10,000,000 - 20,000,000 VND).
- Nhận diện phân loại lương: RANGE, MIN_ONLY, MAX_ONLY, FIXED, NEGOTIABLE.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

NEGOTIABLE_KEYWORDS = [
    "thỏa thuận",
    "thoả thuận",
    "thương lượng",
    "cạnh tranh",
    "đăng nhập để xem",
    "negotiable",
    "competitive",
    "up to",
    "tới",
]


def parse_salary_to_numbers(raw_salary: Any) -> Dict[str, Any]:
    """Phân tích và chuẩn hóa lương thành các trường số rõ ràng.

    Args:
        raw_salary: Có thể là dict (từ raw.salary) hoặc str (chuỗi text).

    Returns:
        Dict:
            - salary_min: float | None
            - salary_max: float | None
            - salary_currency: 'VND' | 'USD' | None
            - salary_type: 'RANGE' | 'MIN_ONLY' | 'MAX_ONLY' | 'FIXED' | 'NEGOTIABLE'
            - salary_raw_text: str | None
    """
    raw_text = ""
    s_min: Optional[float] = None
    s_max: Optional[float] = None
    currency: Optional[str] = None
    is_negotiable = False

    if isinstance(raw_salary, dict):
        raw_text = str(raw_salary.get("salary_text") or "").strip()
        s_min = raw_salary.get("salary_min")
        s_max = raw_salary.get("salary_max")
        currency = raw_salary.get("salary_currency")
        is_negotiable = bool(raw_salary.get("is_negotiable", False))
    elif isinstance(raw_salary, str):
        raw_text = raw_salary.strip()

    text_lower = raw_text.lower()

    # Xác định tiền tệ nếu chưa có
    if not currency:
        if "$" in raw_text or "usd" in text_lower:
            currency = "USD"
        elif any(k in text_lower for k in ["vnd", "vnđ", "₫", "triệu", "tr"]):
            currency = "VND"

    # 1. Kiểm tra trường hợp Thỏa thuận / Thương lượng
    if (s_min is None and s_max is None) and (
        is_negotiable or any(kw in text_lower for kw in NEGOTIABLE_KEYWORDS) or not raw_text
    ):
        return {
            "salary_min": None,
            "salary_max": None,
            "salary_currency": currency,
            "salary_type": "NEGOTIABLE",
            "salary_raw_text": raw_text or "Thoả thuận",
        }

    # 2. Nếu đã có số từ raw dict
    if s_min is not None or s_max is not None:
        val_min = float(s_min) if s_min is not None else None
        val_max = float(s_max) if s_max is not None else None

        # Xử lý trường hợp VND ghi dạng số triệu (ví dụ 10 hoặc 27.6 triệu VND)
        if currency == "VND":
            if val_min is not None and val_min < 1000:
                val_min = round(val_min * 1_000_000)
            if val_max is not None and val_max < 1000:
                val_max = round(val_max * 1_000_000)

        sal_type = _determine_salary_type(val_min, val_max)
        return {
            "salary_min": val_min,
            "salary_max": val_max,
            "salary_currency": currency or "VND",
            "salary_type": sal_type,
            "salary_raw_text": raw_text,
        }

    # 3. Phân tích chuỗi text nếu s_min và s_max đều None
    parsed_min, parsed_max, parsed_curr = _parse_from_text(raw_text)
    if parsed_curr:
        currency = parsed_curr

    sal_type = _determine_salary_type(parsed_min, parsed_max)
    return {
        "salary_min": parsed_min,
        "salary_max": parsed_max,
        "salary_currency": currency,
        "salary_type": sal_type,
        "salary_raw_text": raw_text,
    }


def _determine_salary_type(val_min: Optional[float], val_max: Optional[float]) -> str:
    """Xác định loại cấu trúc lương."""
    if val_min is not None and val_max is not None:
        if val_min == val_max:
            return "FIXED"
        return "RANGE"
    elif val_min is not None:
        return "MIN_ONLY"
    elif val_max is not None:
        return "MAX_ONLY"
    return "NEGOTIABLE"


def _parse_from_text(text: str) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """Regex bóc tách min, max, currency từ chuỗi tự do."""
    text_clean = text.lower().replace(",", "")

    # Mẫu USD: $ 700 - 2000 hoặc 700 - 2000 usd
    usd_range = re.search(r"\$?\s*(\d+(?:\.\d+)?)\s*(?:-|đến|to)\s*\$?\s*(\d+(?:\.\d+)?)\s*(?:usd|\$)?", text_clean)
    if usd_range and ("$" in text_clean or "usd" in text_clean):
        v1, v2 = float(usd_range.group(1)), float(usd_range.group(2))
        return v1, v2, "USD"

    # Mẫu triệu VND: 10 - 20 triệu hoặc 10tr - 20tr
    vnd_range = re.search(r"(\d+(?:\.\d+)?)\s*(?:-|đến|to)\s*(\d+(?:\.\d+)?)\s*(?:triệu|tr|m)", text_clean)
    if vnd_range:
        v1 = round(float(vnd_range.group(1)) * 1_000_000)
        v2 = round(float(vnd_range.group(2)) * 1_000_000)
        return v1, v2, "VND"

    # Mẫu số nguyên lớn VND: 10000000 - 20000000
    big_range = re.search(r"(\d{6,})\s*(?:-|đến|to)\s*(\d{6,})", text_clean)
    if big_range:
        return float(big_range.group(1)), float(big_range.group(2)), "VND"

    # Mẫu lên tới X triệu
    max_match = re.search(r"(?:lên tới|upto|tới|dưới|<)\s*(\d+(?:\.\d+)?)\s*(?:triệu|tr|m)", text_clean)
    if max_match:
        return None, round(float(max_match.group(1)) * 1_000_000), "VND"

    # Mẫu từ X triệu
    min_match = re.search(r"(?:từ|trên|>)\s*(\d+(?:\.\d+)?)\s*(?:triệu|tr|m)", text_clean)
    if min_match:
        return round(float(min_match.group(1)) * 1_000_000), None, "VND"

    return None, None, None
