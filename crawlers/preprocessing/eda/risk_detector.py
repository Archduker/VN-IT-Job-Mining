# -*- coding: utf-8 -*-
"""crawlers.preprocessing.eda.risk_detector
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Bộ cảnh báo rủi ro, ứng viên cần rà soát thủ công và dị biệt dữ liệu (VN-IT-Job-Mining).

Nguyên tắc kỹ thuật:
- Cảnh báo bài đăng ngoài ngành IT dưới dạng "Ứng viên cần rà soát thủ công"
  (Candidates for Manual Review); tuyệt đối không tự ý xóa, lọc bỏ dữ liệu.
- Lưu trữ đầy đủ: unified_id, source, title, company, matched_rule, field_matched.
  Nếu thiếu trường, biểu diễn rõ ràng là 'UNKNOWN' hoặc None.
- Chuẩn hóa company và title bằng CÙNG một quy tắc trước khi nhóm.
- Phân biệt tuyệt đối giữa nhóm lặp thuần nội bộ 1 nguồn và nhóm lặp chéo nhiều nguồn;
  hai loại nhóm loại trừ lẫn nhau và có kiểm toán đối soát số học.
- Phân biệt rành mạch giữa lỗi logic lương (min > max) và giá trị cực đoan cần kiểm tra thêm.
- Toàn bộ kết quả đầu ra có thể tuần tự hóa thành JSON hợp lệ.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Set, Tuple

from crawlers.preprocessing.eda.salary_analyzer import SalaryAnalyzer


class RiskDetector:
    """Bộ nhận diện rủi ro chất lượng, ứng viên lặp và bài đăng dị biệt."""

    # Từ khóa bảo vệ: Nếu tiêu đề chứa các từ khóa IT mạnh, không gắn cờ ngoài ngành IT
    IT_SAFEGUARD_REGEX = re.compile(
        r"\b(?:it|cntt|software|phần mềm|developer|lập trình|programmer|engineer|"
        r"kỹ sư|system|hệ thống|data|dữ liệu|ai|network|mạng|cyber|an ninh mạng|"
        r"tester|qa|qc|cloud|devops|backend|frontend|fullstack|ui/?ux|scada)\b",
        re.IGNORECASE,
    )

    # Các luật phát hiện ứng viên nghi vấn phi IT
    OUT_OF_IT_RULES: List[Tuple[str, re.Pattern[str]]] = [
        ("CHEMISTRY", re.compile(r"\b(?:hóa chất|hóa học|thí nghiệm hóa|phân tích hóa)\b", re.IGNORECASE)),
        ("TEXTILE_GARMENT", re.compile(r"\b(?:may mặc|cắt may|dệt nhuộm|công nhân may|thợ may)\b", re.IGNORECASE)),
        ("HEALTHCARE_MEDICAL", re.compile(r"\b(?:y tế|điều dưỡng|bác sĩ|dược sĩ|y tá|nha sĩ)\b", re.IGNORECASE)),
        ("HOSPITALITY_SECURITY", re.compile(r"\b(?:lễ tân|phục vụ bàn|tạp vụ|buồng phòng|bảo vệ|pha chế|barista)\b", re.IGNORECASE)),
        ("REAL_ESTATE", re.compile(r"\b(?:bất động sản|môi giới nhà đất|đất nền)\b", re.IGNORECASE)),
        ("LOGISTICS_DRIVER", re.compile(r"\b(?:lái xe|tài xế|giao hàng|shipper|bốc xếp)\b", re.IGNORECASE)),
        ("EARLY_EDUCATION", re.compile(r"\b(?:giáo viên mầm non|bảo mẫu|gia sư tiểu học)\b", re.IGNORECASE)),
        ("PURE_ACCOUNTING", re.compile(r"\b(?:kế toán thuế|kế toán kho|kế toán công nợ|thu ngân)\b", re.IGNORECASE)),
    ]

    @staticmethod
    def normalize_text(text: Any) -> str:
        """Quy tắc chuẩn hóa thống nhất dùng chung cho cả company và title."""
        if text is None:
            return ""
        s = str(text).strip().lower()
        return re.sub(r"\s+", " ", s)

    @staticmethod
    def detect_pay_period(salary_obj: Optional[Dict[str, Any]]) -> str:
        """Quy tắc xác định kỳ lương dùng chung thống nhất với SalaryAnalyzer (sửa BUG-01)."""
        return SalaryAnalyzer.detect_pay_period(salary_obj)

    @classmethod
    def _check_out_of_it(cls, title: str) -> Optional[Tuple[str, str]]:
        """Kiểm tra dấu hiệu ngoài ngành IT trên tiêu đề.

        Returns:
            Tuple (rule_name, matched_word) hoặc None nếu không vi phạm hoặc có IT safeguard.
        """
        if not title:
            return None

        # Nếu có từ khóa IT bảo vệ, bỏ qua
        if cls.IT_SAFEGUARD_REGEX.search(title):
            return None

        for rule_name, pattern in cls.OUT_OF_IT_RULES:
            match = pattern.search(title)
            if match:
                return rule_name, match.group(0)

        return None

    @classmethod
    def analyze(cls, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Thực hiện quét và nhận diện các rủi ro dữ liệu trên danh sách bài đăng.

        Args:
            records: Danh sách dict bản ghi tuyển dụng.

        Returns:
            Dict chứa ứng viên cần rà soát phi IT, nhóm ứng viên lặp và bất thường lương.
        """
        total_records = len(records)
        if total_records == 0:
            return {
                "total_analyzed": 0,
                "out_of_it_candidates_summary": {"candidate_count": 0, "candidate_rate": 0.0, "candidates": []},
                "duplicate_candidates_summary": {
                    "total_duplicate_groups": 0,
                    "pure_intra_source_groups": {"group_count": 0, "records_count": 0, "excess_records_count": 0},
                    "cross_source_groups": {"group_count": 0, "records_count": 0, "excess_records_count": 0},
                },
                "salary_anomalies_summary": {
                    "logic_errors_count": 0,
                    "extreme_outliers_count": 0,
                    "unknown_period_anomalies_count": 0,
                    "logic_errors": [],
                    "extreme_outliers_sample": [],
                    "unknown_period_anomalies_sample": [],
                },
            }

        # 1. Quét ứng viên ngoài ngành IT
        out_of_it_candidates: List[Dict[str, Any]] = []
        out_of_it_source_counter: Counter[str] = Counter()
        out_of_it_rule_counter: Counter[str] = Counter()

        # 2. Thu thập nhóm (company, title)
        company_title_groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}

        # 3. Thu thập bất thường lương
        salary_logic_errors: List[Dict[str, Any]] = []
        salary_extreme_outliers: List[Dict[str, Any]] = []
        salary_unknown_period_anomalies: List[Dict[str, Any]] = []

        for rec in records:
            if not isinstance(rec, dict):
                continue

            meta = rec.get("_meta") if isinstance(rec.get("_meta"), dict) else {}
            src = str(meta.get("source") or "UNKNOWN").lower().strip()
            uid = meta.get("unified_id") or "UNKNOWN"
            raw_title = rec.get("title")
            raw_comp = rec.get("company")

            # --- Rà soát ngoài ngành IT ---
            title_str = str(raw_title or "").strip()
            rule_hit = cls._check_out_of_it(title_str)
            if rule_hit:
                rule_name, matched_kw = rule_hit
                out_of_it_source_counter[src] += 1
                out_of_it_rule_counter[rule_name] += 1
                out_of_it_candidates.append({
                    "unified_id": uid,
                    "source": src,
                    "title": raw_title if raw_title is not None else "UNKNOWN",
                    "company": raw_comp if raw_comp is not None else "UNKNOWN",
                    "matched_rule": rule_name,
                    "matched_keyword": matched_kw,
                    "field_matched": "title",
                    "status": "CANDIDATE_FOR_MANUAL_REVIEW",
                })

            # --- Thu thập nhóm (company, title) chuẩn hóa ---
            norm_c = cls.normalize_text(raw_comp)
            norm_t = cls.normalize_text(raw_title)
            if norm_c and norm_t:
                group_key = (norm_c, norm_t)
                if group_key not in company_title_groups:
                    company_title_groups[group_key] = []
                company_title_groups[group_key].append(rec)

            # --- Rà soát bất thường mức lương ---
            sal_obj = rec.get("salary")
            if isinstance(sal_obj, dict):
                s_min = sal_obj.get("salary_min")
                s_max = sal_obj.get("salary_max")
                curr = str(sal_obj.get("salary_currency") or "UNKNOWN").upper().strip()
                raw_text = str(sal_obj.get("salary_raw_text") or "")

                # Nhận diện chu kỳ trả lương dùng chung thống nhất với SalaryAnalyzer (sửa BUG-01)
                period = cls.detect_pay_period(sal_obj)

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

                # a. Lỗi logic rõ ràng: salary_min > salary_max
                if num_min is not None and num_max is not None:
                    if num_min > num_max:
                        salary_logic_errors.append({
                            "unified_id": uid,
                            "source": src,
                            "anomaly_type": "LOGIC_ERROR_MIN_GREATER_THAN_MAX",
                            "salary_min": num_min,
                            "salary_max": num_max,
                            "currency": curr,
                            "pay_period": period,
                            "raw_text": raw_text[:100],
                            "reason": f"Lương tối thiểu ({num_min:,.0f}) lớn hơn lương tối đa ({num_max:,.0f}).",
                        })

                # b. Giá trị cực đoan cần kiểm tra thêm (Extreme Outliers)
                vals_to_check = [v for v in (num_min, num_max) if v is not None]
                for v in vals_to_check:
                    if curr == "VND" and period == "MONTHLY":
                        if v < 500_000:
                            salary_extreme_outliers.append({
                                "unified_id": uid,
                                "source": src,
                                "anomaly_type": "EXTREME_LOW_SALARY",
                                "value": v,
                                "currency": curr,
                                "pay_period": period,
                                "raw_text": raw_text[:100],
                                "reason": f"Mức lương VND/tháng cực thấp ({v:,.0f} VND), cần kiểm tra đơn vị.",
                            })
                        elif v > 500_000_000:
                            salary_extreme_outliers.append({
                                "unified_id": uid,
                                "source": src,
                                "anomaly_type": "EXTREME_HIGH_SALARY",
                                "value": v,
                                "currency": curr,
                                "pay_period": period,
                                "raw_text": raw_text[:100],
                                "reason": f"Mức lương VND/tháng cực cao ({v:,.0f} VND > 500 triệu/tháng).",
                            })
                    elif curr == "USD" and period == "MONTHLY":
                        if v < 50:
                            salary_extreme_outliers.append({
                                "unified_id": uid,
                                "source": src,
                                "anomaly_type": "EXTREME_LOW_SALARY",
                                "value": v,
                                "currency": curr,
                                "pay_period": period,
                                "raw_text": raw_text[:100],
                                "reason": f"Mức lương USD/tháng cực thấp ({v:,.2f} USD).",
                            })
                        elif v > 30_000:
                            salary_extreme_outliers.append({
                                "unified_id": uid,
                                "source": src,
                                "anomaly_type": "EXTREME_HIGH_SALARY",
                                "value": v,
                                "currency": curr,
                                "pay_period": period,
                                "raw_text": raw_text[:100],
                                "reason": f"Mức lương USD/tháng cực cao ({v:,.2f} USD > 30,000 USD/tháng).",
                            })
                    elif period == "UNKNOWN":
                        if v <= 0:
                            salary_unknown_period_anomalies.append({
                                "unified_id": uid,
                                "source": src,
                                "anomaly_type": "ZERO_OR_NEGATIVE_SALARY",
                                "value": v,
                                "currency": curr,
                                "pay_period": "UNKNOWN",
                                "raw_text": raw_text[:100],
                                "reason": f"Mức lương ({v:,.0f} {curr}) <= 0 bất thường đối với mọi kỳ trả lương.",
                            })
                        elif curr == "VND" and v < 20_000:
                            salary_unknown_period_anomalies.append({
                                "unified_id": uid,
                                "source": src,
                                "anomaly_type": "EXTREME_LOW_SALARY_UNKNOWN_PERIOD",
                                "value": v,
                                "currency": curr,
                                "pay_period": "UNKNOWN",
                                "raw_text": raw_text[:100],
                                "reason": f"Mức lương VND cực thấp ({v:,.0f} VND < 20,000 VND) ngay cả khi xét theo kỳ trả theo giờ, nghi ngờ lỗi bóc tách số liệu.",
                            })
                        elif curr == "USD" and v < 5:
                            salary_unknown_period_anomalies.append({
                                "unified_id": uid,
                                "source": src,
                                "anomaly_type": "EXTREME_LOW_SALARY_UNKNOWN_PERIOD",
                                "value": v,
                                "currency": curr,
                                "pay_period": "UNKNOWN",
                                "raw_text": raw_text[:100],
                                "reason": f"Mức lương USD cực thấp ({v:,.2f} USD < 5 USD), dấu hiệu điển hình của lỗi nhầm dấu phân cách hàng nghìn hoặc dữ liệu giả định.",
                            })

        # --- Phân loại nhóm lặp (company, title) ---
        pure_intra_groups = []
        cross_source_groups = []
        pure_intra_by_source: Counter[str] = Counter()

        for (comp_key, title_key), group_recs in company_title_groups.items():
            cnt = len(group_recs)
            if cnt <= 1:
                continue

            sources_in_group = set(
                str(r.get("_meta", {}).get("source") or "UNKNOWN").lower().strip()
                for r in group_recs
            )

            group_info = {
                "company": comp_key,
                "title": title_key,
                "record_count": cnt,
                "excess_count": cnt - 1,
                "sources": list(sources_in_group),
                "sample_unified_ids": [
                    r.get("_meta", {}).get("unified_id")
                    for r in group_recs[:5]
                    if isinstance(r.get("_meta"), dict)
                ],
            }

            if len(sources_in_group) == 1:
                src_name = list(sources_in_group)[0]
                pure_intra_by_source[src_name] += 1
                group_info["single_source"] = src_name
                pure_intra_groups.append(group_info)
            else:
                cross_source_groups.append(group_info)

        # Sắp xếp top nhóm lặp nhiều nhất
        all_duplicate_groups = pure_intra_groups + cross_source_groups
        all_duplicate_groups.sort(key=lambda x: x["record_count"], reverse=True)

        intra_recs_count = sum(g["record_count"] for g in pure_intra_groups)
        intra_excess_count = sum(g["excess_count"] for g in pure_intra_groups)
        cross_recs_count = sum(g["record_count"] for g in cross_source_groups)
        cross_excess_count = sum(g["excess_count"] for g in cross_source_groups)

        total_dup_groups = len(pure_intra_groups) + len(cross_source_groups)
        total_dup_recs = intra_recs_count + cross_recs_count
        total_excess_recs = intra_excess_count + cross_excess_count

        duplicate_summary = {
            "total_duplicate_groups": total_dup_groups,
            "total_records_in_groups": total_dup_recs,
            "total_excess_records": total_excess_recs,
            "reconciliation": {
                "groups_equation_valid": total_dup_groups == (len(pure_intra_groups) + len(cross_source_groups)),
                "records_equation_valid": total_dup_recs == (intra_recs_count + cross_recs_count),
                "excess_equation_valid": total_excess_recs == (intra_excess_count + cross_excess_count),
            },
            "pure_intra_source_groups": {
                "group_count": len(pure_intra_groups),
                "records_count": intra_recs_count,
                "excess_records_count": intra_excess_count,
                "breakdown_by_source": dict(pure_intra_by_source),
            },
            "cross_source_groups": {
                "group_count": len(cross_source_groups),
                "records_count": cross_recs_count,
                "excess_records_count": cross_excess_count,
            },
            "top_10_recurring_groups": all_duplicate_groups[:10],
        }

        return {
            "total_analyzed": total_records,
            "out_of_it_candidates_summary": {
                "candidate_count": len(out_of_it_candidates),
                "candidate_rate": round((len(out_of_it_candidates) / total_records) * 100, 2),
                "rule_breakdown": dict(out_of_it_rule_counter),
                "source_breakdown": dict(out_of_it_source_counter),
                "candidates_sample": out_of_it_candidates[:25],  # Mẫu 25 bài để rà soát
            },
            "duplicate_candidates_summary": duplicate_summary,
            "salary_anomalies_summary": {
                "logic_errors_count": len(salary_logic_errors),
                "extreme_outliers_count": len(salary_extreme_outliers),
                "unknown_period_anomalies_count": len(salary_unknown_period_anomalies),
                "logic_errors": salary_logic_errors,
                "extreme_outliers_sample": salary_extreme_outliers[:20],
                "unknown_period_anomalies_sample": salary_unknown_period_anomalies[:20],
            },
        }
