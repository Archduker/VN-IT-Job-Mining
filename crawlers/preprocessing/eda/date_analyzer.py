# -*- coding: utf-8 -*-
"""crawlers.preprocessing.eda.date_analyzer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Bộ phân tích mốc thời gian và hạn ứng tuyển cho Hệ thống EDA (VN-IT-Job-Mining).

Nguyên tắc kỹ thuật:
- Phân biệt 3 tầng: Định dạng chuỗi (Format), Khả năng parse (Parseability), và
  Khả năng định vị điểm thời gian cụ thể (Resolvability).
- Chuỗi ngày tương đối (Relative text: "3 ngày trước", "hôm qua") BẮT BUỘC quy đổi
  thông qua mốc tham chiếu `_meta.crawled_at` của chính bài đăng, và đánh dấu là
  thời gian ước tính (is_estimated=True).
- Thời hạn tuyển dụng (Job Duration) chỉ tính khi CẢ HAI mốc đều resolve thành công.
- Chỉ gắn cờ bất thường thời gian khi có đầy đủ dữ liệu xác minh; nếu không ghi nhận unverifiable.
- Toàn bộ kết quả đầu ra có thể tuần tự hóa thành JSON hợp lệ.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple


class DateAnalyzer:
    """Bộ kiểm toán và phân tích mốc thời gian đăng bài và hạn nộp hồ sơ."""

    # Regex nhận diện các định dạng chuẩn
    ISO_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$")
    YMD_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    DMY_REGEX = re.compile(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$")

    # Regex nhận diện chuỗi tương đối tiếng Việt / tiếng Anh
    RELATIVE_REGEX = re.compile(
        r"(\d+)\s*(ngày|ngay|giờ|gio|phút|phut|tuần|tuan|tháng|thang|day|hour|minute|week|month)s?\s*(trước|truoc|ago)",
        re.IGNORECASE,
    )
    YESTERDAY_REGEX = re.compile(r"hôm qua|hom qua|yesterday", re.IGNORECASE)
    TODAY_REGEX = re.compile(r"hôm nay|hom nay|vừa xong|vua xong|today|just now", re.IGNORECASE)

    @staticmethod
    def _parse_iso_string(dt_str: str) -> Optional[datetime]:
        """Parse an toàn chuỗi ISO datetime."""
        clean_str = dt_str.strip()
        if clean_str.endswith("Z"):
            clean_str = clean_str[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(clean_str)
        except (ValueError, TypeError):
            return None

    @classmethod
    def classify_date_string(cls, raw_val: Any) -> str:
        """Phân loại định dạng chuỗi của một trường thời gian.

        Trả về một trong các nhãn:
        - 'EMPTY': None, chuỗi rỗng
        - 'ISO_DATETIME': Định dạng ISO-8601
        - 'STANDARD_DATE': YYYY-MM-DD hoặc DD/MM/YYYY
        - 'RELATIVE_TEXT': Chuỗi tương đối ("3 ngày trước", "hôm qua")
        - 'FREE_TEXT': Văn bản tự do không chứa ngày rõ ràng
        """
        if raw_val is None:
            return "EMPTY"
        text = str(raw_val).strip()
        if not text:
            return "EMPTY"

        if cls.ISO_REGEX.match(text):
            return "ISO_DATETIME"
        if cls.YMD_REGEX.match(text) or cls.DMY_REGEX.match(text):
            return "STANDARD_DATE"
        if cls.RELATIVE_REGEX.search(text) or cls.YESTERDAY_REGEX.search(text) or cls.TODAY_REGEX.search(text):
            return "RELATIVE_TEXT"

        return "FREE_TEXT"

    @classmethod
    def resolve_datetime(
        cls, raw_val: Any, reference_crawled_at: Optional[str] = None
    ) -> Tuple[Optional[datetime], bool, str]:
        """Quy đổi chuỗi thời gian thành đối tượng datetime cụ thể.

        Returns:
            Tuple (resolved_dt: Optional[datetime], is_estimated: bool, status: str)
            - status: 'RESOLVED_EXACT', 'RESOLVED_ESTIMATED', 'UNRESOLVABLE_RELATIVE',
                      'UNPARSEABLE_TEXT', 'EMPTY'
        """
        classification = cls.classify_date_string(raw_val)
        if classification == "EMPTY":
            return None, False, "EMPTY"

        text = str(raw_val).strip()

        # 1. Thử parse ISO
        if classification == "ISO_DATETIME":
            dt = cls._parse_iso_string(text)
            if dt is not None:
                return dt, False, "RESOLVED_EXACT"

        # 2. Thử parse Date chuẩn YYYY-MM-DD
        if cls.YMD_REGEX.match(text):
            try:
                dt = datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                return dt, False, "RESOLVED_EXACT"
            except ValueError:
                pass

        # 3. Thử parse Date chuẩn DD/MM/YYYY
        dmy_match = cls.DMY_REGEX.match(text)
        if dmy_match:
            d, m, y = map(int, dmy_match.groups())
            try:
                dt = datetime(y, m, d, tzinfo=timezone.utc)
                return dt, False, "RESOLVED_EXACT"
            except ValueError:
                pass

        # 4. Thử quy đổi chuỗi tương đối qua mốc crawled_at
        if classification == "RELATIVE_TEXT":
            ref_dt: Optional[datetime] = None
            if reference_crawled_at and isinstance(reference_crawled_at, str):
                ref_dt = cls._parse_iso_string(reference_crawled_at)

            if ref_dt is None:
                # Không có mốc tham chiếu hợp lệ -> Không tự ý đoán qua datetime.now()
                return None, False, "UNRESOLVABLE_RELATIVE"

            # Tính toán độ lệch
            rel_match = cls.RELATIVE_REGEX.search(text)
            if rel_match:
                amount = int(rel_match.group(1))
                unit = rel_match.group(2).lower()
                delta = timedelta()
                if "ngày" in unit or "ngay" in unit or "day" in unit:
                    delta = timedelta(days=amount)
                elif "giờ" in unit or "gio" in unit or "hour" in unit:
                    delta = timedelta(hours=amount)
                elif "phút" in unit or "phut" in unit or "minute" in unit:
                    delta = timedelta(minutes=amount)
                elif "tuần" in unit or "tuan" in unit or "week" in unit:
                    delta = timedelta(weeks=amount)
                elif "tháng" in unit or "thang" in unit or "month" in unit:
                    delta = timedelta(days=amount * 30)

                estimated_dt = ref_dt - delta
                return estimated_dt, True, "RESOLVED_ESTIMATED"

            if cls.YESTERDAY_REGEX.search(text):
                return ref_dt - timedelta(days=1), True, "RESOLVED_ESTIMATED"

            if cls.TODAY_REGEX.search(text):
                return ref_dt, True, "RESOLVED_ESTIMATED"

            return None, False, "UNRESOLVABLE_RELATIVE"

        return None, False, "UNPARSEABLE_TEXT"

    @classmethod
    def analyze(cls, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Phân tích toàn diện mốc thời gian đăng tuyển và hạn ứng tuyển.

        Args:
            records: Danh sách các dict bản ghi tuyển dụng.

        Returns:
            Dict kết quả phân tích định dạng, parseability, resolvability,
            thời hạn tuyển dụng và cảnh báo mốc thời gian dị biệt.
        """
        total_records = len(records)
        if total_records == 0:
            return {
                "total_analyzed": 0,
                "posted_date_summary": {},
                "deadline_summary": {},
                "job_duration_analysis": {"valid_duration_count": 0, "negative_duration_count": 0},
                "temporal_anomalies": {"count": 0, "anomalies": []},
            }

        posted_format_counts: Counter[str] = Counter()
        posted_status_counts: Counter[str] = Counter()
        deadline_format_counts: Counter[str] = Counter()
        deadline_status_counts: Counter[str] = Counter()

        # Nguồn -> {posted_resolved: count, deadline_resolved: count}
        source_date_stats: Dict[str, Counter[str]] = {}

        # Dữ liệu thời hạn tuyển dụng
        duration_days_list: List[int] = []
        negative_duration_count: int = 0

        # Danh sách cảnh báo bất thường
        anomalies_list: List[Dict[str, Any]] = []

        for rec in records:
            if not isinstance(rec, dict):
                continue

            meta = rec.get("_meta") if isinstance(rec.get("_meta"), dict) else {}
            src = str(meta.get("source") or "UNKNOWN").lower().strip()
            crawled_at_str = meta.get("crawled_at")

            if src not in source_date_stats:
                source_date_stats[src] = Counter()

            p_raw = rec.get("posted_date_text")
            d_raw = rec.get("deadline_text")

            # Phân loại format
            p_fmt = cls.classify_date_string(p_raw)
            d_fmt = cls.classify_date_string(d_raw)
            posted_format_counts[p_fmt] += 1
            deadline_format_counts[d_fmt] += 1

            # Resolve ngày
            p_dt, p_est, p_status = cls.resolve_datetime(p_raw, reference_crawled_at=crawled_at_str)
            d_dt, d_est, d_status = cls.resolve_datetime(d_raw, reference_crawled_at=crawled_at_str)
            posted_status_counts[p_status] += 1
            deadline_status_counts[d_status] += 1

            if p_dt is not None:
                source_date_stats[src]["posted_resolved"] += 1
            if d_dt is not None:
                source_date_stats[src]["deadline_resolved"] += 1

            # Tính Job Duration nếu cả 2 đều resolve được
            if p_dt is not None and d_dt is not None:
                delta_days = (d_dt.date() - p_dt.date()).days

                # Kiểm tra bất thường: deadline trước posted_date
                if delta_days < 0:
                    negative_duration_count += 1
                    anomalies_list.append({
                        "unified_id": meta.get("unified_id"),
                        "source": src,
                        "anomaly_type": "DEADLINE_BEFORE_POSTED",
                        "posted_resolved": p_dt.isoformat(),
                        "deadline_resolved": d_dt.isoformat(),
                        "raw_posted": str(p_raw)[:100],
                        "raw_deadline": str(d_raw)[:100],
                        "reason": f"Hạn nộp hồ sơ sớm hơn ngày đăng bài ({delta_days} ngày).",
                    })
                else:
                    # Chỉ đưa thời hạn hợp lệ (>= 0 ngày) vào tập thống kê thời hạn
                    duration_days_list.append(delta_days)

                    if delta_days > 365:
                        anomalies_list.append({
                            "unified_id": meta.get("unified_id"),
                            "source": src,
                            "anomaly_type": "EXCESSIVE_DURATION",
                            "posted_resolved": p_dt.isoformat(),
                            "deadline_resolved": d_dt.isoformat(),
                            "raw_posted": str(p_raw)[:100],
                            "raw_deadline": str(d_raw)[:100],
                            "reason": f"Thời hạn tuyển dụng kéo dài bất thường ({delta_days} ngày > 1 năm).",
                        })

            # Kiểm tra bất thường: posted_date trong tương lai so với crawled_at
            if p_dt is not None and crawled_at_str and isinstance(crawled_at_str, str):
                crawl_dt = cls._parse_iso_string(crawled_at_str)
                if crawl_dt is not None:
                    # Cho phép dung sai 1 ngày để tránh lệch múi giờ UTC/GMT+7
                    if (p_dt.date() - crawl_dt.date()).days > 1:
                        anomalies_list.append({
                            "unified_id": meta.get("unified_id"),
                            "source": src,
                            "anomaly_type": "POSTED_IN_FUTURE",
                            "posted_resolved": p_dt.isoformat(),
                            "crawled_at": crawl_dt.isoformat(),
                            "raw_posted": str(p_raw)[:100],
                            "reason": "Ngày đăng tin muộn hơn ngày crawler thu thập tin.",
                        })

        # Tổng kết posted_date
        p_exact = posted_status_counts.get("RESOLVED_EXACT", 0)
        p_est = posted_status_counts.get("RESOLVED_ESTIMATED", 0)
        p_unres = total_records - (p_exact + p_est)

        posted_summary = {
            "format_breakdown": {
                k: {"count": v, "percentage": round((v / total_records) * 100, 2)}
                for k, v in posted_format_counts.most_common()
            },
            "resolvability_breakdown": {
                k: {"count": v, "percentage": round((v / total_records) * 100, 2)}
                for k, v in posted_status_counts.most_common()
            },
            # 3 nhóm trạng thái phân biệt rõ ràng
            "exact_count": p_exact,
            "exact_rate": round((p_exact / total_records) * 100, 2),
            "estimated_count": p_est,
            "estimated_rate": round((p_est / total_records) * 100, 2),
            "unresolvable_count": p_unres,
            "unresolvable_rate": round((p_unres / total_records) * 100, 2),
            "total_resolved": p_exact + p_est,
        }

        # Tổng kết deadline
        d_exact = deadline_status_counts.get("RESOLVED_EXACT", 0)
        d_est = deadline_status_counts.get("RESOLVED_ESTIMATED", 0)
        d_unres = total_records - (d_exact + d_est)

        deadline_summary = {
            "format_breakdown": {
                k: {"count": v, "percentage": round((v / total_records) * 100, 2)}
                for k, v in deadline_format_counts.most_common()
            },
            "resolvability_breakdown": {
                k: {"count": v, "percentage": round((v / total_records) * 100, 2)}
                for k, v in deadline_status_counts.most_common()
            },
            # 3 nhóm trạng thái phân biệt rõ ràng
            "exact_count": d_exact,
            "exact_rate": round((d_exact / total_records) * 100, 2),
            "estimated_count": d_est,
            "estimated_rate": round((d_est / total_records) * 100, 2),
            "unresolvable_count": d_unres,
            "unresolvable_rate": round((d_unres / total_records) * 100, 2),
            "total_resolved": d_exact + d_est,
        }


        # Tổng kết Job Duration
        duration_summary: Dict[str, Any] = {
            "valid_duration_count": len(duration_days_list),
            "coverage_percentage": round((len(duration_days_list) / total_records) * 100, 2),
            "negative_duration_count": negative_duration_count,
        }
        if duration_days_list:
            duration_days_list.sort()
            n_dur = len(duration_days_list)
            duration_summary.update({
                "min_days": duration_days_list[0],
                "q25_days": duration_days_list[int(0.25 * (n_dur - 1))],
                "median_days": duration_days_list[n_dur // 2],
                "mean_days": round(sum(duration_days_list) / n_dur, 2),
                "q75_days": duration_days_list[int(0.75 * (n_dur - 1))],
                "max_days": duration_days_list[-1],
            })

        return {
            "total_analyzed": total_records,
            "posted_date_summary": posted_summary,
            "deadline_summary": deadline_summary,
            "job_duration_analysis": duration_summary,
            "source_date_parseability": {
                src: dict(stats) for src, stats in source_date_stats.items()
            },
            "temporal_anomalies": {
                "count": len(anomalies_list),
                "percentage": round((len(anomalies_list) / total_records) * 100, 2),
                "anomalies": anomalies_list[:20],  # Lưu mẫu tối đa 20 bản ghi
            },
        }
