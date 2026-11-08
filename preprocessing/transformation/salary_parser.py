# -*- coding: utf-8 -*-
"""preprocessing.transformation.salary_parser
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Universal Salary Parser & Cascade Salary Extractor cho VN-IT-Job-Mining.

Tính năng:
  - Bóc tách dải số lương (min, max, currency, period) từ mọi định dạng text sàn VN.
  - T2a: Dấu phân cách hàng nghìn (2,000 -> 2000, 8.5 -> 8.5).
  - T2b: "Từ X" chỉ gán min = X, max = None (khắc phục D3).
  - T2c: "Up to X", "Tới X" chỉ gán max = X, min = None (khắc phục D4).
  - T2d: Quy đổi USD sang VND tỷ giá chuẩn 25,400; chu kỳ /năm (/12), /giờ (*160), /ngày (*22).
  - T2e: Cascade 3 tầng: header -> title -> jd -> none; bảo toàn cờ thỏa thuận.
  - T2f: Gắn cờ salary_under_1m cho lương < 1 triệu VND.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

USD_VND_EXCHANGE_RATE = 25_400.0

NEGOTIABLE_KEYWORDS = {
    "thỏa thuận", "thoả thuận", "cạnh tranh", "thương lượng",
    "đăng nhập để xem mức lương", "công ty không công khai thông tin này",
    "negotiable", "competitive", "confidential", "open", "trao đổi khi phỏng vấn",
    "thương lượng khi phỏng vấn", "deal"
}


def parse_number(num_str: str) -> float:
    """T2a: Phân biệt dấu phân cách hàng nghìn (2,000 -> 2000) và số thập phân (8.5 -> 8.5)."""
    s = str(num_str).strip()
    # Dấu hàng nghìn: ví dụ 2,000 hoặc 2.000 hoặc 20,000,000 hoặc 20.000.000
    if re.match(r"^\d{1,3}(?:[.,]\d{3})+$", s):
        return float(re.sub(r"[.,]", "", s))
    # Số thập phân: 8.5 hoặc 8,5
    return float(s.replace(",", "."))


# Đơn vị triệu phải đứng sát sau số: tránh "m" trong "from", "tr" trong "trưởng"
_MILLION = re.compile(r"\d\s*(?:triệu|trieu|trđ|tr|m)(?![a-zà-ỹ])")


class UniversalSalaryParser:
    """Bộ bóc tách dải lương vạn năng từ chuỗi văn bản."""

    @classmethod
    def parse_text(cls, text: Optional[str]) -> Dict[str, Any]:
        """Phân tích chuỗi lương thô ra cấu trúc số học."""
        res: Dict[str, Any] = {
            "salary_text_raw": text,
            "salary_min_vnd": None,
            "salary_max_vnd": None,
            "salary_min_original": None,
            "salary_max_original": None,
            "salary_currency_original": "VND",
            "pay_period": "month",
            "is_negotiable": False,
            "has_commission": False,
            "salary_under_1m": False,
        }

        if not text or not str(text).strip():
            res["is_negotiable"] = True
            return res

        s = str(text).strip()
        s_lower = s.lower()

        # Kiểm tra thỏa thuận
        is_neg = False
        for kw in NEGOTIABLE_KEYWORDS:
            if kw in s_lower:
                is_neg = True
                break
        res["is_negotiable"] = is_neg

        # Nếu chỉ thuần túy thỏa thuận không kèm số
        if is_neg and not re.search(r"\d+", s):
            return res

        # Kiểm tra hoa hồng
        if any(w in s_lower for w in ["hoa hồng", "thưởng", "kpi", "commission", "bonus"]):
            res["has_commission"] = True

        # Nhận diện chu kỳ
        period = "month"
        if "năm" in s_lower or "year" in s_lower or "annual" in s_lower:
            period = "year"
        elif "giờ" in s_lower or "hour" in s_lower:
            period = "hour"
        elif "ngày" in s_lower or "day" in s_lower:
            period = "day"
        res["pay_period"] = period

        # Nhận diện tiền tệ
        curr = "VND"
        if "usd" in s_lower or "$" in s:
            curr = "USD"
        res["salary_currency_original"] = curr

        # Làm sạch chuỗi trước khi regex: bỏ ký hiệu tiền tệ
        clean = re.sub(r"[₫$]|vnđ|vnd|usd", "", s, flags=re.IGNORECASE).strip()

        # TH 1: Định dạng số đầy đủ có dấu phân cách hàng nghìn (ví dụ: 10.000.000 - 30.000.000)
        full_num_match = re.search(
            r"(\d{1,3}(?:[.,]\d{3}){1,3})\s*[-–—tođến]+\s*(\d{1,3}(?:[.,]\d{3}){1,3})", clean
        )
        if full_num_match:
            min_raw = parse_number(full_num_match.group(1))
            max_raw = parse_number(full_num_match.group(2))
            return cls._apply_standardization(res, min_raw, max_raw, curr, period)

        # TH 2: Dải số "Từ X đến Y" hoặc "X - Y"
        range_match = re.search(
            r"(\d{1,3}(?:[.,]\d{3})+(?![.,]?\d)|\d+(?:[.,]\d+)?)\s*[-–—tođến]+\s*(\d{1,3}(?:[.,]\d{3})+(?![.,]?\d)|\d+(?:[.,]\d+)?)\s*(?:triệu|tr|m|trđ)?", clean, re.IGNORECASE
        )
        if range_match:
            v1 = parse_number(range_match.group(1))
            v2 = parse_number(range_match.group(2))
            if _MILLION.search(s_lower) or (curr == "VND" and v2 < 1000):
                v1 = v1 * 1_000_000 if v1 < 1000 else v1
                v2 = v2 * 1_000_000 if v2 < 1000 else v2
            elif curr == "USD" or (v1 >= 100 and v2 <= 10000):
                curr = "USD"
                res["salary_currency_original"] = "USD"
            return cls._apply_standardization(res, v1, v2, curr, period)

        # TH 3: T2b - "Từ X" (không có cận trên)
        from_match = re.search(r"(?:từ|tu|from|>=|>)\s*(\d{1,3}(?:[.,]\d{3})+(?![.,]?\d)|\d+(?:[.,]\d+)?)\s*(?:triệu|tr|m|trđ)?", clean, re.IGNORECASE)
        if from_match and not re.search(r"[-–—]|(?:\bto\b)|(?:\bđến\b)", clean, re.IGNORECASE):
            v = parse_number(from_match.group(1))
            if _MILLION.search(s_lower) or (curr == "VND" and v < 1000):
                v = v * 1_000_000
            return cls._apply_standardization(res, v, None, curr, period)

        # TH 4: T2c - "Up to X", "Tới X", "Lên đến X", "<= X" (không có cận dưới)
        upto_match = re.search(r"(?:up\s*to|upto|tới|toi|lên\s*đến|đến|tối\s*đa|<|<=)\s*(\d{1,3}(?:[.,]\d{3})+(?![.,]?\d)|\d+(?:[.,]\d+)?)\s*(?:triệu|tr|m|trđ)?", clean, re.IGNORECASE)
        if upto_match and not re.search(r"\d+\s*[-–—tođến]+\s*\d+", clean):
            v = parse_number(upto_match.group(1))
            if _MILLION.search(s_lower) or (curr == "VND" and v < 200):
                v = v * 1_000_000
            return cls._apply_standardization(res, None, v, curr, period)

        # TH 5: Số đơn (ví dụ: 15 triệu, 400 triệu / năm)
        single_match = re.search(r"(\d{1,3}(?:[.,]\d{3})+(?![.,]?\d)|\d+(?:[.,]\d+)?)\s*(?:triệu|tr|m|trđ)?", clean, re.IGNORECASE)
        if single_match and single_match.group(1):
            v = parse_number(single_match.group(1))
            if v > 0:
                if _MILLION.search(s_lower) or (curr == "VND" and v < 1000):
                    v = v * 1_000_000
                return cls._apply_standardization(res, v, v, curr, period)

        return res

    @classmethod
    def _apply_standardization(
        cls, res: Dict[str, Any], min_raw: Optional[float], max_raw: Optional[float], curr: str, period: str
    ) -> Dict[str, Any]:
        res["salary_min_original"] = min_raw
        res["salary_max_original"] = max_raw

        # 1. T2d: Quy đổi tỷ giá về VND (USD -> VND theo tỷ giá 25.400)
        rate = USD_VND_EXCHANGE_RATE if curr == "USD" else 1.0
        min_vnd = min_raw * rate if min_raw is not None else None
        max_vnd = max_raw * rate if max_raw is not None else None

        # 2. T2d: Quy đổi chu kỳ về tháng
        if period == "year":
            min_vnd = min_vnd / 12.0 if min_vnd else None
            max_vnd = max_vnd / 12.0 if max_vnd else None
        elif period == "hour":
            min_vnd = min_vnd * 160.0 if min_vnd else None
            max_vnd = max_vnd * 160.0 if max_vnd else None
        elif period == "day":
            min_vnd = min_vnd * 22.0 if min_vnd else None
            max_vnd = max_vnd * 22.0 if max_vnd else None

        res["salary_min_vnd"] = min_vnd
        res["salary_max_vnd"] = max_vnd

        # 3. T2f: Gắn cờ salary_under_1m nếu lương < 1.000.000 VND (loại trừ None)
        under_1m = False
        if min_vnd is not None and 0 < min_vnd < 1_000_000:
            under_1m = True
        if max_vnd is not None and 0 < max_vnd < 1_000_000:
            under_1m = True
        res["salary_under_1m"] = under_1m

        return res


_NUM = r"\d+(?:[.,]\d+)*"
_UNIT = r"(?:triệu|trieu|trđ|tr|m|k|usd|vnđ|vnd|đ)(?![a-zà-ỹ])"
_PREFIX = r"(?:(?:từ|from|up\s*to|upto|lên\s*(?:đến|tới)|tới|đến|tối\s*đa)\s*)?"
# Chỉ nhận số có đơn vị tiền hoặc ký hiệu $: chặn mã tin "2026TD450981", "Microsoft 365", "Bậc 1"
MONEY_RE = re.compile(
    rf"{_PREFIX}(?:\$\s*{_NUM}(?:\s*{_UNIT})?(?:\s*(?:[-–—~]|to|đến)\s*\$?\s*{_NUM}(?:\s*{_UNIT})?)?"
    rf"|{_NUM}\s*(?:{_UNIT}\s*)?(?:[-–—~]|to|đến)\s*{_NUM}\s*{_UNIT}"
    rf"|{_NUM}\s*{_UNIT})",
    re.IGNORECASE,
)
_PERIOD_AFTER = re.compile(r"^\s*(?:/|per|mỗi|một)\s*(?:năm|year|tháng|month|giờ|hour|ngày|day)", re.IGNORECASE)
MONTHLY_MIN_VND, MONTHLY_MAX_VND = 1_000_000, 500_000_000


def find_money_span(text: Optional[str]) -> Optional[str]:
    """Cắt đúng cụm tiền trong câu (kèm '/năm' ngay sau nếu có) để parse_text không đọc nhầm số khác."""
    if not text:
        return None
    m = MONEY_RE.search(str(text))
    if not m:
        return None
    rest = str(text)[m.end():]
    period = _PERIOD_AFTER.match(rest)
    return m.group(0) + (period.group(0) if period else "")


def _has_value(res: Dict[str, Any]) -> bool:
    return res.get("salary_min_vnd") is not None or res.get("salary_max_vnd") is not None


def _apply_bounds(res: Dict[str, Any]) -> Dict[str, Any]:
    """Lương tháng ngoài 1–500 triệu là đọc sai: bỏ số, gắn cờ salary_suspect. Số 0 ("0 - 30 triệu") là cận trống."""
    for k in ("salary_min_vnd", "salary_max_vnd"):
        if res.get(k) == 0:
            res[k] = None
    vals = [v for v in (res.get("salary_min_vnd"), res.get("salary_max_vnd")) if v is not None]
    res["salary_suspect"] = any(v < MONTHLY_MIN_VND or v > MONTHLY_MAX_VND for v in vals)
    if res["salary_suspect"]:
        res["salary_min_vnd"] = res["salary_max_vnd"] = None
    return res


def scan_salary_in_jd_text(jd_text: Optional[str]) -> Optional[Dict[str, Any]]:
    """Quét các câu trong JD có từ khóa lương; chỉ nhận cụm số có đơn vị tiền."""
    if not jd_text or not str(jd_text).strip():
        return None

    lines = [line.strip() for line in re.split(r"[\n\r;]+|\.(?!\d)", str(jd_text)) if line.strip()]
    salary_keywords = ("lương", "thu nhập", "salary", "package", "up to", "lên đến", "upto", "đãi ngộ")

    for line in lines:
        if any(kw in line.lower() for kw in salary_keywords):
            span = find_money_span(line)
            parsed = UniversalSalaryParser.parse_text(span) if span else {}
            if _has_value(parsed):
                parsed["salary_source"] = "jd"
                parsed["extracted_line"] = line[:120]
                return parsed

    return None


def parse_salary_cascade(
    raw_salary_text: Optional[str],
    title: Optional[str] = None,
    jd_text: Optional[str] = None
) -> Dict[str, Any]:
    """T2e: header → tiêu đề → JD → none. Tiêu đề và JD chỉ nhận cụm có đơn vị tiền; mọi tầng qua ngưỡng 1–500 triệu/tháng."""
    # Tương thích ngược: parse_salary_cascade(header, jd_text)
    if jd_text is None and title and ("\n" in title or len(title) > 50 or "chúng tôi" in title.lower() or "mức thu nhập" in title.lower()):
        jd_text = title
        title = None

    header_res = UniversalSalaryParser.parse_text(raw_salary_text)
    if _has_value(header_res):
        header_res["salary_source"] = "header"
        return _apply_bounds(header_res)

    span = find_money_span(title) if title else None
    if span:
        title_res = UniversalSalaryParser.parse_text(span)
        if _has_value(title_res):
            title_res["salary_source"] = "title"
            title_res["is_negotiable"] = header_res.get("is_negotiable", False)
            return _apply_bounds(title_res)

    jd_res = scan_salary_in_jd_text(jd_text)
    if jd_res:
        jd_res["salary_source"] = "jd_regex"
        jd_res["is_negotiable"] = header_res.get("is_negotiable", False)
        jd_res["is_salary_negotiable_declared"] = True
        return _apply_bounds(jd_res)

    header_res["salary_source"] = "none"
    header_res["is_negotiable"] = True
    header_res["salary_suspect"] = False
    return header_res
