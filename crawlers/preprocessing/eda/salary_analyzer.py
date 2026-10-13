# -*- coding: utf-8 -*-
"""crawlers.preprocessing.eda.salary_analyzer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Bộ phân tích mức lương chuyên sâu cho Hệ thống EDA (VN-IT-Job-Mining).

Nguyên tắc kỹ thuật:
- Tách bạch tuyệt đối các loại tiền tệ (VND, USD, UNKNOWN_CURRENCY), không cộng gộp.
- Tách bạch kỳ trả lương (MONTHLY, YEARLY, HOURLY, DAILY, UNDETERMINED_PERIOD),
  chỉ so sánh khi cùng đơn vị tiền tệ và cùng kỳ trả lương.
- Ghi nhận salary_type == 'NEGOTIABLE' là Null hợp lệ theo nghiệp vụ (business_valid_null).
- Chỉ phân tích cờ has_commission / is_negotiable khi trường tồn tại trong dữ liệu.
- Toàn bộ kết quả có thể chuyển đổi thành JSON hợp lệ (không chứa NaN, numpy types).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple


class SalaryAnalyzer:
    """Bộ phân tích lương theo loại hình tuyển dụng, tiền tệ và kỳ trả lương."""

    # Từ khóa nhận diện kỳ trả lương từ salary_raw_text (chỉ khi có tiền tố xác định chu kỳ)
    PERIOD_PATTERNS = [
        (re.compile(r"(?:/\s*|\bmỗi\s+|\btrên\s+|\bhàng\s+|per\s+)(?:tháng|thang|month)\b|\bmonthly\b", re.IGNORECASE), "MONTHLY"),
        (re.compile(r"(?:/\s*|\bmỗi\s+|\btrên\s+|\bhàng\s+|per\s+)(?:năm|nam|year)\b|\byearly\b|\bannual\b", re.IGNORECASE), "YEARLY"),
        (re.compile(r"(?:/\s*|\bmỗi\s+|\btrên\s+|\bhàng\s+|per\s+)(?:giờ|gio|hour)\b|\bhourly\b", re.IGNORECASE), "HOURLY"),
        (re.compile(r"(?:/\s*|\bmỗi\s+|\btrên\s+|\bhàng\s+|per\s+)(?:ngày|ngay|day)\b|\bdaily\b", re.IGNORECASE), "DAILY"),
    ]

    @classmethod
    def detect_pay_period(cls, salary_obj: Optional[Dict[str, Any]]) -> str:
        """Xác định kỳ trả lương từ salary dict hoặc salary_raw_text.

        Chỉ xác định khi có căn cứ rõ ràng từ dữ liệu; nếu không xác định được
        thì phân loại thành 'UNKNOWN', tuyệt đối không tự suy đoán.
        """
        if not isinstance(salary_obj, dict):
            return "UNKNOWN"

        # Nếu schema có trường pay_period hoặc period
        explicit_period = salary_obj.get("pay_period") or salary_obj.get("period")
        if isinstance(explicit_period, str) and explicit_period.strip():
            return explicit_period.upper().strip()

        raw_text = str(salary_obj.get("salary_raw_text") or "").strip()
        if not raw_text:
            return "UNKNOWN"

        for pattern, period_name in cls.PERIOD_PATTERNS:
            if pattern.search(raw_text):
                return period_name

        return "UNKNOWN"

    # Duy trì tương thích ngược với các lời gọi private cũ
    _detect_pay_period = detect_pay_period


    @staticmethod
    def _calculate_descriptive_stats(values: List[float]) -> Optional[Dict[str, float]]:
        """Tính toán các chỉ số thống kê mô tả thuần túy Python (an toàn JSON)."""
        clean_vals = [float(v) for v in values if v is not None and not math.isnan(float(v))]
        if not clean_vals:
            return None

        clean_vals.sort()
        n = len(clean_vals)
        mean_val = sum(clean_vals) / n

        # Phương sai & Độ lệch chuẩn
        if n > 1:
            variance = sum((x - mean_val) ** 2 for x in clean_vals) / (n - 1)
            std_val = math.sqrt(variance)
        else:
            std_val = 0.0

        def quantile(p: float) -> float:
            if n == 1:
                return clean_vals[0]
            pos = p * (n - 1)
            idx = int(pos)
            diff = pos - idx
            if idx + 1 < n:
                return clean_vals[idx] + diff * (clean_vals[idx + 1] - clean_vals[idx])
            return clean_vals[idx]

        return {
            "count": n,
            "min": round(clean_vals[0], 2),
            "q25": round(quantile(0.25), 2),
            "median": round(quantile(0.50), 2),
            "mean": round(mean_val, 2),
            "q75": round(quantile(0.75), 2),
            "max": round(clean_vals[-1], 2),
            "std": round(std_val, 2),
        }

    @classmethod
    def analyze(cls, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Thực hiện phân tích toàn diện trường lương trên danh sách bản ghi hợp lệ.

        Args:
            records: Danh sách các dict bản ghi tuyển dụng hợp lệ.

        Returns:
            Dict chứa đầy đủ các chỉ số thống kê lương có cấu trúc, tương thích JSON.
        """
        total_records = len(records)
        if total_records == 0:
            return {
                "total_analyzed": 0,
                "salary_type_distribution": {},
                "negotiable_summary": {"count": 0, "percentage": 0.0, "is_business_valid_null": True},
                "numeric_salary_summary": {"count": 0, "percentage": 0.0},
                "currency_distribution": {},
                "pay_period_distribution": {},
                "stats_by_currency_and_period": {},
                "source_salary_overview": {},
                "auxiliary_flags": {
                    "has_commission": {"true_count": 0, "false_count": 0, "missing_count": 0},
                    "is_negotiable": {"true_count": 0, "false_count": 0, "missing_count": 0},
                },
            }

        # Bộ đếm phân loại
        salary_type_counter: Counter[str] = Counter()
        currency_counter: Counter[str] = Counter()
        period_counter: Counter[str] = Counter()

        # Cờ phụ trợ
        comm_counts: Counter[str] = Counter()
        nego_counts: Counter[str] = Counter()

        # Dữ liệu số phân tách theo: (currency, period) -> {"min": [...], "max": [...]}
        numeric_buckets: Dict[Tuple[str, str], Dict[str, List[float]]] = {}

        # Thống kê theo nguồn
        source_records_count: Counter[str] = Counter()
        source_numeric_count: Counter[str] = Counter()
        source_vnd_monthly_medians: Dict[str, List[float]] = {}

        for rec in records:
            if not isinstance(rec, dict):
                continue

            meta = rec.get("_meta") if isinstance(rec.get("_meta"), dict) else {}
            src = str(meta.get("source") or "UNKNOWN").lower().strip()
            source_records_count[src] += 1

            salary = rec.get("salary")
            if not isinstance(salary, dict):
                salary = {}

            stype = str(salary.get("salary_type") or "UNDETERMINED_TYPE").upper().strip()
            salary_type_counter[stype] += 1

            # Cờ has_commission
            has_comm = salary.get("has_commission")
            if has_comm is True:
                comm_counts["true"] += 1
            elif has_comm is False:
                comm_counts["false"] += 1
            else:
                comm_counts["missing"] += 1

            # Cờ is_negotiable
            is_nego = salary.get("is_negotiable")
            if is_nego is True:
                nego_counts["true"] += 1
            elif is_nego is False:
                nego_counts["false"] += 1
            else:
                nego_counts["missing"] += 1

            # Kiểm tra giá trị số
            s_min = salary.get("salary_min")
            s_max = salary.get("salary_max")
            num_min: Optional[float] = None
            num_max: Optional[float] = None

            try:
                if s_min is not None and not math.isnan(float(s_min)):
                    num_min = float(s_min)
            except (ValueError, TypeError):
                pass

            try:
                if s_max is not None and not math.isnan(float(s_max)):
                    num_max = float(s_max)
            except (ValueError, TypeError):
                pass

            has_numeric = (num_min is not None) or (num_max is not None)

            if has_numeric:
                source_numeric_count[src] += 1
                curr_raw = salary.get("salary_currency")
                curr = str(curr_raw).upper().strip() if curr_raw else "UNKNOWN_CURRENCY"
                currency_counter[curr] += 1

                period = cls._detect_pay_period(salary)
                period_counter[period] += 1

                bucket_key = (curr, period)
                if bucket_key not in numeric_buckets:
                    numeric_buckets[bucket_key] = {"min": [], "max": []}

                if num_min is not None:
                    numeric_buckets[bucket_key]["min"].append(num_min)
                if num_max is not None:
                    numeric_buckets[bucket_key]["max"].append(num_max)

                # Thu thập để so sánh theo nguồn (CHỈ chọn khi xác định đúng VND và MONTHLY)
                if curr == "VND" and period == "MONTHLY":
                    val_to_use = num_min if num_min is not None else num_max
                    if val_to_use is not None:
                        if src not in source_vnd_monthly_medians:
                            source_vnd_monthly_medians[src] = []
                        source_vnd_monthly_medians[src].append(val_to_use)

        # 1. Phân bố loại lương
        type_summary: Dict[str, Dict[str, Any]] = {}
        for stype, cnt in salary_type_counter.most_common():
            type_summary[stype] = {
                "count": cnt,
                "percentage": round((cnt / total_records) * 100, 2),
            }

        # 2. Tổng kết Lương Thỏa Thuận (Business-valid Null)
        nego_count = salary_type_counter.get("NEGOTIABLE", 0)
        nego_summary = {
            "count": nego_count,
            "percentage": round((nego_count / total_records) * 100, 2),
            "is_business_valid_null": True,
            "note": "Lương thỏa thuận là giá trị null hợp lệ theo nghiệp vụ, không phải lỗi thu thập.",
        }

        # 3. Tổng kết bài có lương số cụ thể
        total_numeric = sum(source_numeric_count.values())
        numeric_summary = {
            "count": total_numeric,
            "percentage": round((total_numeric / total_records) * 100, 2),
        }

        # 4. Thống kê mô tả theo từng cặp (currency, period)
        stats_by_bucket: Dict[str, Any] = {}
        for (curr, period), vals in sorted(numeric_buckets.items()):
            bucket_name = f"{curr}_{period}"
            stats_by_bucket[bucket_name] = {
                "currency": curr,
                "period": period,
                "salary_min_stats": cls._calculate_descriptive_stats(vals["min"]),
                "salary_max_stats": cls._calculate_descriptive_stats(vals["max"]),
            }

        # 5. Phân bố tiền tệ và kỳ trả lương
        currency_summary: Dict[str, Any] = {}
        for curr, cnt in currency_counter.most_common():
            currency_summary[curr] = {
                "count": cnt,
                "percentage_of_numeric": round((cnt / total_numeric) * 100, 2) if total_numeric > 0 else 0.0,
            }

        period_summary: Dict[str, Any] = {}
        for per, cnt in period_counter.most_common():
            period_summary[per] = {
                "count": cnt,
                "percentage_of_numeric": round((cnt / total_numeric) * 100, 2) if total_numeric > 0 else 0.0,
            }

        # 6. Tổng quan lương theo 8 nguồn
        source_overview: Dict[str, Any] = {}
        for src, total_src in source_records_count.most_common():
            num_src = source_numeric_count.get(src, 0)
            vnd_vals = source_vnd_monthly_medians.get(src, [])
            vnd_vals.sort()
            median_vnd = round(vnd_vals[len(vnd_vals) // 2], 2) if vnd_vals else None

            source_overview[src] = {
                "total_records": total_src,
                "numeric_salary_count": num_src,
                "numeric_salary_percentage": round((num_src / total_src) * 100, 2) if total_src > 0 else 0.0,
                "representative_vnd_median": median_vnd,
            }

        return {
            "total_analyzed": total_records,
            "salary_type_distribution": type_summary,
            "negotiable_summary": nego_summary,
            "numeric_salary_summary": numeric_summary,
            "currency_distribution": currency_summary,
            "pay_period_distribution": period_summary,
            "stats_by_currency_and_period": stats_by_bucket,
            "source_salary_overview": source_overview,
            "auxiliary_flags": {
                "has_commission": {
                    "true_count": comm_counts["true"],
                    "false_count": comm_counts["false"],
                    "none_count": comm_counts["missing"],
                    "missing_count": comm_counts["missing"],
                    "true_rate": round((comm_counts["true"] / total_records) * 100, 2),
                },
                "is_negotiable": {
                    "true_count": nego_counts["true"],
                    "false_count": nego_counts["false"],
                    "none_count": nego_counts["missing"],
                    "missing_count": nego_counts["missing"],
                    "true_rate": round((nego_counts["true"] / total_records) * 100, 2),
                },
            },
        }
