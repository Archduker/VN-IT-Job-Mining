# -*- coding: utf-8 -*-
"""preprocessing.transformation.experience_parser
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Bóc tách số năm kinh nghiệm yêu cầu (exp_min_years, exp_max_years) theo luật T4.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

NO_EXP_KEYWORDS = (
    "không yêu cầu", "không cần", "chưa có kinh nghiệm", "chua co kinh nghiem",
    "no experience", "fresher", "intern", "thực tập sinh", "không đòi hỏi"
)


def parse_experience(raw_exp: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
    """Phân tích chuỗi kinh nghiệm thô thành (exp_min_years, exp_max_years)."""
    if not raw_exp or not str(raw_exp).strip():
        return None, None

    s = str(raw_exp).strip()
    s_lower = s.lower()

    # TH 1: Không yêu cầu kinh nghiệm
    if any(k in s_lower for k in NO_EXP_KEYWORDS):
        return 0.0, 0.0

    # Kiểm tra đơn vị tháng hay năm
    is_month = "tháng" in s_lower or "month" in s_lower
    unit_scale = 1.0 / 12.0 if is_month else 1.0

    # TH 2: Dưới X năm / tháng (< X, <= X)
    under_match = re.search(r"(?:dưới|duoi|<|<=|ít hơn|tối đa)\s*(\d+(?:[.,]\d+)?)\s*(?:năm|nam|year|tháng|thang|month)?", s_lower)
    if under_match and not re.search(r"[-–—]|(?:\bto\b)|(?:\bđến\b)", s_lower):
        v = float(under_match.group(1).replace(",", ".")) * unit_scale
        return 0.0, round(v, 2)

    # TH 3: Trên X năm / Từ X năm trở lên (> X, >= X, X+)
    over_match = re.search(r"(?:trên|tren|từ|tu|>|>=|tối thiểu|ít nhất)\s*(\d+(?:[.,]\d+)?)\s*(?:năm|nam|year|tháng|thang|month)?", s_lower)
    if over_match and not re.search(r"[-–—]|(?:\bto\b)|(?:\bđến\b)", s_lower):
        v = float(over_match.group(1).replace(",", ".")) * unit_scale
        return round(v, 2), None

    plus_match = re.search(r"(\d+(?:[.,]\d+)?)\s*\+\s*(?:năm|nam|year|tháng|thang|month)?", s_lower)
    if plus_match and not re.search(r"[-–—]|(?:\bto\b)|(?:\bđến\b)", s_lower):
        v = float(plus_match.group(1).replace(",", ".")) * unit_scale
        return round(v, 2), None

    # TH 4: Khoảng X - Y năm / tháng
    range_match = re.search(r"(\d+(?:[.,]\d+)?)\s*[-–—tođến]+\s*(\d+(?:[.,]\d+)?)\s*(?:năm|nam|year|tháng|thang|month)?", s_lower)
    if range_match:
        v1 = float(range_match.group(1).replace(",", ".")) * unit_scale
        v2 = float(range_match.group(2).replace(",", ".")) * unit_scale
        return round(v1, 2), round(v2, 2)

    # TH 5: Số đơn X năm / tháng (ví dụ: "2 năm", "24 months")
    single_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:năm|nam|year|tháng|thang|month)", s_lower)
    if single_match:
        v = float(single_match.group(1).replace(",", ".")) * unit_scale
        return round(v, 2), round(v, 2)

    # Fallback số thuần túy
    pure_num = re.search(r"^\s*(\d+(?:[.,]\d+)?)\s*$", s)
    if pure_num:
        v = float(pure_num.group(1).replace(",", "."))
        return round(v, 2), round(v, 2)

    return None, None
