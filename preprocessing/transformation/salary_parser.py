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

NEGATIVE_JD_PATTERNS = [
    re.compile(r"\b1[3-5](?:th)?\s*[-–\s]*(?:month|tháng|salary|lương|base)\b", re.IGNORECASE),
    re.compile(r"(?:tháng\s+)?lương\s+(?:thứ\s+)?1[3-5]\b", re.IGNORECASE),
    re.compile(r"\b[tT]1[3-5]\b"),
    re.compile(r"\b\d+\s*tháng\s+lương\b", re.IGNORECASE),
    re.compile(r"\b\d+\s*months?\b", re.IGNORECASE),
    re.compile(r"\d+\s*ngày\s+(?:nghỉ|phép)", re.IGNORECASE),
    re.compile(r"(?:annual\s+)?leave", re.IGNORECASE),
    re.compile(r"probation|thử\s*việc", re.IGNORECASE),
    re.compile(r"bảo\s*hiểm|insurance", re.IGNORECASE),
    re.compile(r"bình\s*quân|trung\s*bình", re.IGNORECASE),
    re.compile(r"review\s+every|xét\s+tăng\s+lương", re.IGNORECASE),
    re.compile(r"(?:tăng|review|xét)\s+lương\s+\d+\s*[-–]\s*\d+\s*lần", re.IGNORECASE),
    re.compile(r"100%|85%", re.IGNORECASE),
    re.compile(r"30\s*/\s*4\s*[-–—]\s*1\s*/\s*5", re.IGNORECASE),
    re.compile(r"(?:hỗ\s*trợ|kinh\s*phí|phụ\s*cấp)\s+(?:ăn|trông\s*trẻ|gửi\s*xe)", re.IGNORECASE),
]


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

        # Nhận diện chu kỳ (chỉ xét khi có chỉ báo chu kỳ rõ ràng, không bắt nhầm year-end bonus)
        period = "month"
        if re.search(r"/\s*(?:năm|year)|per\s+year|annually|lương\s+năm|annual\s+salary|\btrên\s+năm\b", s_lower):
            period = "year"
        elif re.search(r"/\s*(?:giờ|hour)|per\s+hour|hourly", s_lower):
            period = "hour"
        elif re.search(r"/\s*(?:ngày|day)|per\s+day|daily", s_lower):
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
            re.search(r"triệu|trđ|\btr\b|\d\s*m\b|millions?", s_lower)
        )
        has_thousand_unit = bool(
            re.search(r"\b\d+\s*k\b", s_lower)
        )

        # TH 1: Định dạng số đầy đủ có dấu chấm/phẩy (ví dụ: 10.000.000 - 30.000.000)
        full_num_match = re.search(r"(\d{1,3}(?:[.,]\d{3}){1,3})\s*(?:[-–—]|\b(?:to|đến)\b)+\s*(\d{1,3}(?:[.,]\d{3}){1,3})", clean)
        if full_num_match:
            min_raw = float(full_num_match.group(1).replace(".", "").replace(",", ""))
            max_raw = float(full_num_match.group(2).replace(".", "").replace(",", ""))
            return cls._apply_standardization(
                res, min_raw, max_raw, curr, period, sgd_to_vnd_rate
            )

        # TH 2: Định dạng Triệu / M / Tr / K / Millions (ví dụ: 12 - 20 triệu, 15-25M, 10 - 15 tr, 500k - 800k, 35 - 45 millions)
        trieu_range = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:triệu|tr|m|trđ|k|millions?)?\s*(?:[-–—]|\b(?:to|đến)\b)+\s*(\d+(?:[.,]\d+)?)\s*(?:triệu|tr|m|trđ|k|millions?)?", clean, re.IGNORECASE)
        if trieu_range and (has_million_unit or has_thousand_unit or curr == "VND"):
            v1 = float(trieu_range.group(1).replace(",", "."))
            v2 = float(trieu_range.group(2).replace(",", "."))
            if has_thousand_unit:
                min_raw = v1 * 1_000
                max_raw = v2 * 1_000
            else:
                min_raw = v1 * 1_000_000 if v1 < 1000 else v1
                max_raw = v2 * 1_000_000 if v2 < 1000 else v2
            return cls._apply_standardization(
                res, min_raw, max_raw, curr, period, sgd_to_vnd_rate
            )

        # TH 3: Định dạng USD range (ví dụ: 800 - 1,500 hoặc 1000-2000)
        usd_range = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:[-–—]|\b(?:to|đến)\b)+\s*(\d+(?:[.,]\d+)?)", clean)
        if usd_range:
            v1 = float(usd_range.group(1).replace(",", ""))
            v2 = float(usd_range.group(2).replace(",", ""))
            # Nếu tiền tệ USD hoặc số nằm trong khoảng lương USD (100 - 10000)
            if curr in ("USD", "SGD") or (
                curr == "VND" and v1 >= 100 and v2 <= 10000 and "triệu" not in s_lower and not has_thousand_unit
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

        # TH 3.5: Cận dưới: Từ / Trên / Tối thiểu / >= / From (ví dụ: Từ 15 triệu, Trên 20 triệu, Tối thiểu $1000)
        from_match = re.search(
            r"(?:từ|trên|tối\s*thiểu|>=|>|from|at\s*least)\s*(\d+(?:[.,]\d+)?)\s*(?:triệu|tr|m|trđ|k)?",
            clean,
            re.IGNORECASE,
        )
        if from_match and not re.search(r"[-–—]|\b(?:to|đến)\b", clean, re.IGNORECASE):
            num_str = from_match.group(1)
            if curr in ("USD", "SGD"):
                num_str = num_str.replace(",", "")
            else:
                num_str = num_str.replace(",", ".")
            v = float(num_str)
            if has_thousand_unit:
                v = v * 1_000
            elif has_million_unit or (v < 200 and curr == "VND"):
                v = v * 1_000_000
            return cls._apply_standardization(
                res, v, None, curr, period, sgd_to_vnd_rate
            )

        # TH 4: Up to / Lên đến / Tối đa (ví dụ: Up to $2000, Tới 30 triệu)
        upto_match = re.search(r"(?:up\s*to|tới|lên\s*đến|tối\s*đa|<|<=)\s*(\d+(?:[.,]\d+)?)\s*(?:triệu|tr|m|trđ|k)?", clean, re.IGNORECASE)
        if upto_match:
            num_str = upto_match.group(1)
            if curr in ("USD", "SGD"):
                num_str = num_str.replace(",", "")
            else:
                num_str = num_str.replace(",", ".")
            v = float(num_str)
            if has_thousand_unit:
                v = v * 1_000
            elif has_million_unit or (v < 200 and curr == "VND"):
                v = v * 1_000_000
            return cls._apply_standardization(
                res, None, v, curr, period, sgd_to_vnd_rate
            )

        # TH 5: Số đơn (ví dụ: 400 triệu / năm, lương 15 triệu)
        single_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:triệu|tr|m|trđ|k)?", clean, re.IGNORECASE)
        if single_match and single_match.group(1):
            single_number = single_match.group(1)
            if curr in ("USD", "SGD"):
                single_number = single_number.replace(",", "")
            else:
                single_number = single_number.replace(",", ".")
            v = float(single_number)
            if v > 0:
                if has_thousand_unit:
                    v = v * 1_000
                elif has_million_unit or (v < 1000 and curr == "VND"):
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

        # Xử lý số 0 là null marker trá hình (sneaky null):
        if min_raw == 0.0 and max_raw == 0.0:
            min_raw = None
            max_raw = None
            res["is_negotiable"] = True
        else:
            if min_raw == 0.0:
                min_raw = None
            if max_raw == 0.0:
                max_raw = None

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
    jd_text: Optional[str],
    sgd_to_vnd_rate: Optional[float] = None,
    source_label: str = "jd_regex",
) -> Optional[Dict[str, Any]]:
    """Quét các câu trong JD hoặc Benefits để bóc tách mức lương ẩn khi header là Thỏa thuận."""
    if not jd_text or not str(jd_text).strip():
        return None

    # Tìm các câu hoặc dòng có từ khóa mức lương: ngắt câu an toàn không cắt số chấm thập phân/nghìn
    lines = [
        line.strip()
        for line in re.split(r"[\n\r;•\*\t▪▫➢]+|(?<=[a-zA-Z\d\)])\.\s+", str(jd_text))
        if line.strip()
    ]
    salary_keywords = ("lương", "thu nhập", "salary", "package", "up to", "lên đến", "upto")

    for line in lines:
        line_lower = line.lower()
        if any(kw in line_lower for kw in salary_keywords):
            # Bộ lọc Negative Patterns: loại bỏ bẫy phúc lợi (lương tháng 13, tăng lương, thử việc...)
            if any(p.search(line) for p in NEGATIVE_JD_PATTERNS):
                continue

            # Phải có đơn vị rõ ràng hoặc định dạng số nghìn/triệu/ngoại tệ, tránh bắt nhầm số đếm ngày/tháng/lần
            has_explicit_unit = bool(
                re.search(r"(\d+(?:[.,]\d+)?)\s*(?:triệu|trđ|\btr\b|\d\s*m\b|millions?|\$|usd|sgd|\bk\b)", line_lower) or
                re.search(r"\b\d{1,3}(?:[.,]\d{3}){1,3}\b", line)
            )
            if not has_explicit_unit:
                continue

            parsed = UniversalSalaryParser.parse_text(line, sgd_to_vnd_rate)
            min_v = parsed.get("salary_min_vnd")
            max_v = parsed.get("salary_max_vnd")
            if min_v is None and max_v is None:
                continue

            # Kiểm tra tính hợp lệ số học: min > max
            if min_v is not None and max_v is not None and min_v > max_v:
                continue

            # Ngưỡng sàn an toàn cho lương quét: nếu < 1,000,000 VNĐ thì bỏ qua (tránh bắt nhầm đếm lần/ngày)
            check_v = max_v if max_v is not None else min_v
            if check_v is not None and check_v < 1_000_000.0:
                continue

            parsed["salary_source"] = source_label
            parsed["extracted_line"] = line[:120]
            return parsed

    return None


def parse_salary_cascade(
    raw_salary_text: Optional[str],
    jd_text: Optional[str],
    sgd_to_vnd_rate: Optional[float] = None,
    benefits: Optional[Any] = None,
) -> Dict[str, Any]:
    """Quy trình bóc tách Cascade hoàn chỉnh:

    1. Thử bóc tách từ raw_salary_text (Header).
    2. Nếu không có số hoặc thỏa thuận, thử quét trong JD text.
    3. Nếu vẫn chưa có số, thử quét trong mảng Benefits (Phúc lợi).
    4. Trả về kết quả tổng hợp.
    """
    # Bước 1: Parse header
    header_res = UniversalSalaryParser.parse_text(raw_salary_text, sgd_to_vnd_rate)

    # Nếu header đã có dải số hợp lệ -> Sử dụng ngay
    if header_res.get("salary_min_vnd") is not None or header_res.get("salary_max_vnd") is not None:
        header_res["salary_source"] = "header"
        return header_res

    # Bước 2: Quét lương ẩn trong JD
    jd_res = scan_salary_in_jd_text(jd_text, sgd_to_vnd_rate, source_label="jd_regex")
    if jd_res:
        # Giữ lại thông báo thỏa thuận gốc
        jd_res["is_salary_negotiable_declared"] = True
        return jd_res

    # Bước 3: Quét lương ẩn trong Benefits
    if benefits:
        benefits_text = (
            "\n".join(str(b) for b in benefits)
            if isinstance(benefits, (list, tuple, set))
            else str(benefits)
        )
        benefits_res = scan_salary_in_jd_text(
            benefits_text, sgd_to_vnd_rate, source_label="benefits_regex"
        )
        if benefits_res:
            benefits_res["is_salary_negotiable_declared"] = True
            return benefits_res

    # Bước 4: Không tìm thấy số -> Giữ nguyên cờ thỏa thuận
    header_res["salary_source"] = "header_negotiable"
    return header_res
