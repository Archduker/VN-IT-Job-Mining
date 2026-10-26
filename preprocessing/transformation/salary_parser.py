# -*- coding: utf-8 -*-
"""preprocessing.transformation.salary_parser
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Universal Salary Parser & Cascade Salary Extractor cho VN-IT-Job-Mining.

Tính năng:
  - Bóc tách dải số lương (min, max, currency, period) từ mọi định dạng text sàn VN.
  - Quy đổi USD sang VND theo tỷ giá chuẩn 25,400.
  - Quy đổi chu kỳ trả (năm -> tháng bằng /12, giờ -> tháng bằng * 160).
  - Cascade Extractor: Khi header là 'Thỏa thuận', tự động quét thân JD tìm lương ẩn.
  - Bảo toàn cờ gốc: is_salary_negotiable_declared = 1.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

USD_VND_EXCHANGE_RATE = 25_400.0

NEGOTIABLE_KEYWORDS = {
    "thỏa thuận", "thoả thuận", "cạnh tranh", "thương lượng",
    "đăng nhập để xem mức lương", "công ty không công khai thông tin này",
    "negotiable", "competitive", "confidential", "open", "trao đổi khi phỏng vấn"
}


class UniversalSalaryParser:
    """Bộ bóc tách dải lương vạn năng từ chuỗi văn bản."""

    @classmethod
    def parse_text(
        cls, text: Optional[str], sgd_to_vnd_rate: Optional[float] = None
    ) -> Dict[str, Any]:
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
        }

        if not text or not str(text).strip():
            res["is_negotiable"] = True
            return res

        s = str(text).strip()
        s_lower = s.lower()

        # Kiểm tra thỏa thuận
        for kw in NEGOTIABLE_KEYWORDS:
            if kw in s_lower:
                res["is_negotiable"] = True
                # Nếu chỉ thuần túy thỏa thuận không kèm số
                if not re.search(r"\d+", s):
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
        if "sgd" in s_lower or "s$" in s_lower:
            curr = "SGD"
        elif "usd" in s_lower or "$" in s:
            curr = "USD"
        res["salary_currency_original"] = curr

        # Làm sạch chuỗi trước khi regex: bỏ dấu ₫, VNĐ, VND, USD, SGD, $
        clean = re.sub(r"s\$|[₫$]|vnđ|vnd|usd|sgd", "", s, flags=re.IGNORECASE).strip()
        has_million_unit = bool(
            re.search(r"triệu|trđ|\btr\b|\d\s*m\b", s_lower)
        )

        # TH 1: Định dạng số đầy đủ có dấu chấm/phẩy (ví dụ: 10.000.000 - 30.000.000)
        full_num_match = re.search(r"(\d{1,3}(?:[.,]\d{3}){1,3})\s*[-–—tođến]+\s*(\d{1,3}(?:[.,]\d{3}){1,3})", clean)
        if full_num_match:
            min_raw = float(full_num_match.group(1).replace(".", "").replace(",", ""))
            max_raw = float(full_num_match.group(2).replace(".", "").replace(",", ""))
            return cls._apply_standardization(
                res, min_raw, max_raw, curr, period, sgd_to_vnd_rate
            )

        # TH 2: Định dạng Triệu / M / Tr (ví dụ: 12 - 20 triệu, 15-25M, 10 - 15 tr)
        trieu_range = re.search(r"(\d+(?:[.,]\d+)?)\s*[-–—tođến]+\s*(\d+(?:[.,]\d+)?)\s*(?:triệu|tr|m|trđ)?", clean, re.IGNORECASE)
        if trieu_range and (has_million_unit or curr == "VND"):
            v1 = float(trieu_range.group(1).replace(",", "."))
            v2 = float(trieu_range.group(2).replace(",", "."))
            # Nếu giá trị < 1000 thì nhân với 1,000,000 (đơn vị triệu)
            min_raw = v1 * 1_000_000 if v1 < 1000 else v1
            max_raw = v2 * 1_000_000 if v2 < 1000 else v2
            return cls._apply_standardization(
                res, min_raw, max_raw, curr, period, sgd_to_vnd_rate
            )

        # TH 3: Định dạng USD range (ví dụ: 800 - 1,500 hoặc 1000-2000)
        usd_range = re.search(r"(\d+(?:[.,]\d+)?)\s*[-–—tođến]+\s*(\d+(?:[.,]\d+)?)", clean)
        if usd_range:
            v1 = float(usd_range.group(1).replace(",", ""))
            v2 = float(usd_range.group(2).replace(",", ""))
            # Nếu tiền tệ USD hoặc số nằm trong khoảng lương USD (100 - 10000)
            if curr in ("USD", "SGD") or (
                curr == "VND" and v1 >= 100 and v2 <= 10000 and "triệu" not in s_lower
            ):
                if curr == "VND":
                    curr = "USD"
                    res["salary_currency_original"] = "USD"
                return cls._apply_standardization(
                    res, v1, v2, curr, period, sgd_to_vnd_rate
                )
            elif "triệu" in s_lower or "tr" in s_lower:
                return cls._apply_standardization(
                    res, v1 * 1_000_000, v2 * 1_000_000, curr, period, sgd_to_vnd_rate
                )

        # TH 4: Up to / Lên đến / Tối đa (ví dụ: Up to $2000, Tới 30 triệu)
        upto_match = re.search(r"(?:up\s*to|tới|lên\s*đến|tối\s*đa|<|<=)\s*(\d+(?:[.,]\d+)?)", clean, re.IGNORECASE)
        if upto_match:
            v = float(upto_match.group(1).replace(",", "."))
            if has_million_unit or (v < 200 and curr == "VND"):
                v = v * 1_000_000
            return cls._apply_standardization(
                res, None, v, curr, period, sgd_to_vnd_rate
            )

        # TH 5: Số đơn (ví dụ: 400 triệu / năm, lương 15 triệu)
        single_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:triệu|tr|m|trđ)?", clean, re.IGNORECASE)
        if single_match and single_match.group(1):
            single_number = single_match.group(1)
            if curr in ("USD", "SGD"):
                single_number = single_number.replace(",", "")
            else:
                single_number = single_number.replace(",", ".")
            v = float(single_number)
            if v > 0:
                if has_million_unit or (v < 1000 and curr == "VND"):
                    v = v * 1_000_000
                elif curr == "USD":
                    pass
                return cls._apply_standardization(
                    res, v, v, curr, period, sgd_to_vnd_rate
                )

        return res

    @classmethod
    def _apply_standardization(
        cls,
        res: Dict[str, Any],
        min_raw: Optional[float],
        max_raw: Optional[float],
        curr: str,
        period: str,
        sgd_to_vnd_rate: Optional[float] = None,
    ) -> Dict[str, Any]:
        res["salary_min_original"] = min_raw
        res["salary_max_original"] = max_raw

        # 1. Quy đổi tỷ giá về VND
        rate = (
            USD_VND_EXCHANGE_RATE
            if curr == "USD"
            else 1.0
            if curr == "VND"
            else sgd_to_vnd_rate
            if curr == "SGD"
            else None
        )
        min_vnd = min_raw * rate if min_raw is not None and rate is not None else None
        max_vnd = max_raw * rate if max_raw is not None and rate is not None else None

        # 2. Quy đổi chu kỳ về tháng
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
        return res


def scan_salary_in_jd_text(
    jd_text: Optional[str], sgd_to_vnd_rate: Optional[float] = None
) -> Optional[Dict[str, Any]]:
    """Quét các câu trong JD để bóc tách mức lương ẩn khi header là Thỏa thuận."""
    if not jd_text or not str(jd_text).strip():
        return None

    # Tìm các câu hoặc dòng có từ khóa mức lương
    lines = [line.strip() for line in re.split(r"[\n\r;.]+", str(jd_text)) if line.strip()]
    salary_keywords = ("lương", "thu nhập", "salary", "package", "up to", "lên đến", "upto")

    for line in lines:
        line_lower = line.lower()
        if any(kw in line_lower for kw in salary_keywords):
            parsed = UniversalSalaryParser.parse_text(line, sgd_to_vnd_rate)
            if parsed.get("salary_min_vnd") is not None or parsed.get("salary_max_vnd") is not None:
                parsed["salary_source"] = "jd_regex"
                parsed["extracted_line"] = line[:120]
                return parsed

    return None


def parse_salary_cascade(
    raw_salary_text: Optional[str],
    jd_text: Optional[str],
    sgd_to_vnd_rate: Optional[float] = None,
) -> Dict[str, Any]:
    """Quy trình bóc tách Cascade hoàn chỉnh:

    1. Thử bóc tách từ raw_salary_text (Header).
    2. Nếu không có số hoặc thỏa thuận, thử quét trong JD text.
    3. Trả về kết quả tổng hợp.
    """
    # Bước 1: Parse header
    header_res = UniversalSalaryParser.parse_text(raw_salary_text, sgd_to_vnd_rate)

    # Nếu header đã có dải số hợp lệ -> Sử dụng ngay
    if header_res.get("salary_min_vnd") is not None or header_res.get("salary_max_vnd") is not None:
        header_res["salary_source"] = "header"
        return header_res

    # Bước 2: Quét lương ẩn trong JD
    jd_res = scan_salary_in_jd_text(jd_text, sgd_to_vnd_rate)
    if jd_res:
        # Giữ lại thông báo thỏa thuận gốc
        jd_res["is_salary_negotiable_declared"] = True
        return jd_res

    # Bước 3: Không tìm thấy số -> Giữ nguyên cờ thỏa thuận
    header_res["salary_source"] = "header_negotiable"
    return header_res
