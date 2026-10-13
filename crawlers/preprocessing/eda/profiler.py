# -*- coding: utf-8 -*-
"""crawlers.preprocessing.eda.profiler
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Module Profiling cơ bản cho Hệ thống EDA (VN-IT-Job-Mining).

Chức năng:
- Thống kê quy mô tập dữ liệu và phân bố theo 8 nguồn tuyển dụng.
- Phân tích chi tiết mức độ khuyết thiếu (Missingness Analysis):
  + Phân biệt rõ: Missing Key, None/Null, Chuỗi rỗng (""), Danh sách rỗng ([]).
- Kiểm toán kiểu dữ liệu thực tế và các trường hợp dị biệt (Heterogeneous types).
- Khảo sát tính duy nhất của các khóa định danh (unified_id, url, dedup_key).
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional, Set, Tuple

from crawlers.preprocessing.eda.risk_detector import RiskDetector


class EDAProfiler:
    """Bộ kiểm toán và phân tích hồ sơ dữ liệu (Data Profiler)."""

    @staticmethod
    def normalize_text(text: Any) -> str:
        """Quy tắc chuẩn hóa thống nhất dùng chung cho cả company và title (đồng bộ với RiskDetector)."""
        return RiskDetector.normalize_text(text)

    # Danh sách các trường cốt lõi theo dõi missingness
    CORE_FIELDS: List[Tuple[str, str]] = [
        ("_meta.unified_id", "unified_id"),
        ("_meta.source", "source"),
        ("_meta.source_job_id", "source_job_id"),
        ("_meta.url", "url"),
        ("_meta.crawled_at", "crawled_at"),
        ("_meta.language", "language"),
        ("title", "title"),
        ("company", "company"),
        ("salary.salary_type", "salary_type"),
        ("salary.salary_min", "salary_min"),
        ("salary.salary_max", "salary_max"),
        ("salary.salary_currency", "salary_currency"),
        ("description_list", "description_list"),
        ("requirements_list", "requirements_list"),
        ("benefits_list", "benefits_list"),
        ("tags.skills", "skills"),
        ("tags.requirements", "tag_requirements"),
        ("tags.benefits", "tag_benefits"),
        ("locations", "locations"),
        ("location_text", "location_text"),
        ("employment_type_text", "employment_type_text"),
        ("seniority_text", "seniority_text"),
        ("posted_date_text", "posted_date_text"),
        ("deadline_text", "deadline_text"),
        ("extra", "extra"),
    ]

    @staticmethod
    def _extract_nested_value(record: Dict[str, Any], path: str) -> Tuple[bool, Any]:
        """Truy xuất giá trị từ đường dẫn nested (ví dụ: 'salary.salary_min').

        Returns:
            Tuple (key_exists: bool, value: Any)
        """
        parts = path.split(".")
        current = record
        for p in parts:
            if not isinstance(current, dict) or p not in current:
                return False, None
            current = current[p]
        return True, current

    @classmethod
    def analyze_field_status(cls, record: Dict[str, Any], path: str) -> str:
        """Phân loại trạng thái giá trị của một trường trong bản ghi.

        Trả về một trong các nhãn:
        - 'missing_key': Khóa không tồn tại trong dict
        - 'null': Giá trị là None
        - 'empty_string': Giá trị là chuỗi rỗng hoặc chỉ có khoảng trắng
        - 'empty_list': Giá trị là danh sách rỗng ([])
        - 'valid': Giá trị có dữ liệu hợp lệ
        """
        key_exists, val = cls._extract_nested_value(record, path)
        if not key_exists:
            return "missing_key"
        if val is None:
            return "null"
        if isinstance(val, str) and not val.strip():
            return "empty_string"
        if isinstance(val, (list, tuple, set)) and len(val) == 0:
            return "empty_list"
        if isinstance(val, dict) and len(val) == 0:
            return "empty_dict"
        return "valid"

    @classmethod
    def profile_dataset(cls, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Thực hiện profiling toàn diện trên danh sách bản ghi raw records.

        Args:
            records: Danh sách dict bài đăng tuyển dụng.

        Returns:
            Dict chứa toàn bộ các chỉ số thống kê tổng quan, missingness và uniqueness.
        """
        total_records = len(records)
        if total_records == 0:
            return {
                "total_records": 0,
                "sources_distribution": {},
                "missingness_summary": {},
                "uniqueness_summary": {},
                "heterogeneous_types": {},
            }

        # 1. Thống kê theo nguồn (Sources Distribution)
        sources_counter: Counter[str] = Counter()
        unified_ids_counter: Counter[str] = Counter()
        urls_counter: Counter[str] = Counter()
        missing_uid_count: int = 0
        missing_url_count: int = 0
        source_job_pairs: Set[Tuple[str, str]] = set()
        company_title_pairs: Counter[Tuple[str, str]] = Counter()

        # 2. Thống kê missingness tổng thể và theo từng nguồn
        # Cấu trúc: field_path -> status -> count
        missingness_counts: Dict[str, Counter[str]] = {
            fpath: Counter() for fpath, _ in cls.CORE_FIELDS
        }
        # Cấu trúc: source -> field_path -> valid_count
        source_field_valid: Dict[str, Counter[str]] = {}

        # 3. Theo dõi kiểu dữ liệu dị biệt
        extra_experience_types: Counter[str] = Counter()
        extra_education_types: Counter[str] = Counter()
        salary_types_counter: Counter[str] = Counter()

        for rec in records:
            if not isinstance(rec, dict):
                continue

            meta = rec.get("_meta") if isinstance(rec.get("_meta"), dict) else {}
            src = str(meta.get("source") or "UNKNOWN").lower().strip()
            sources_counter[src] += 1

            if src not in source_field_valid:
                source_field_valid[src] = Counter()

            # Đánh giá Uniqueness (loại trừ None, rỗng và khoảng trắng)
            raw_uid = meta.get("unified_id")
            uid = str(raw_uid).strip() if raw_uid is not None else ""
            if uid:
                unified_ids_counter[uid] += 1
            else:
                missing_uid_count += 1

            raw_url = meta.get("url")
            url = str(raw_url).strip() if raw_url is not None else ""
            if url:
                urls_counter[url] += 1
            else:
                missing_url_count += 1



            s_jid = str(meta.get("source_job_id") or "")
            if src and s_jid:
                source_job_pairs.add((src, s_jid))

            comp = cls.normalize_text(rec.get("company"))
            title = cls.normalize_text(rec.get("title"))
            if comp and title:
                company_title_pairs[(comp, title)] += 1

            # Đánh giá Missingness cho từng trường
            for fpath, fname in cls.CORE_FIELDS:
                status = cls.analyze_field_status(rec, fpath)
                missingness_counts[fpath][status] += 1
                if status == "valid":
                    source_field_valid[src][fname] += 1

            # Khảo sát dị biệt trong extra & salary
            extra = rec.get("extra") if isinstance(rec.get("extra"), dict) else {}
            exp_val = extra.get("experience")
            extra_experience_types[type(exp_val).__name__] += 1

            edu_val = extra.get("education")
            extra_education_types[type(edu_val).__name__] += 1

            sal_obj = rec.get("salary") if isinstance(rec.get("salary"), dict) else {}
            sal_type = str(sal_obj.get("salary_type") or "NULL")
            salary_types_counter[sal_type] += 1

        # Tổng hợp báo cáo Phân bố Nguồn
        sources_summary: Dict[str, Dict[str, Any]] = {}
        for src, count in sources_counter.most_common():
            sources_summary[src] = {
                "count": count,
                "percentage": round((count / total_records) * 100, 2),
            }

        # Tổng hợp báo cáo Missingness
        missingness_summary: Dict[str, Dict[str, Any]] = {}
        for fpath, label in cls.CORE_FIELDS:
            c = missingness_counts[fpath]
            valid_c = c.get("valid", 0)
            missing_c = total_records - valid_c
            missingness_summary[label] = {
                "field_path": fpath,
                "valid_count": valid_c,
                "valid_rate": round((valid_c / total_records) * 100, 2),
                "missing_total": missing_c,
                "missing_rate": round((missing_c / total_records) * 100, 2),
                "breakdown": {
                    "missing_key": c.get("missing_key", 0),
                    "null": c.get("null", 0),
                    "empty_string": c.get("empty_string", 0),
                    "empty_list": c.get("empty_list", 0),
                    "empty_dict": c.get("empty_dict", 0),
                },
            }

        # Tổng hợp tỷ lệ đầy đủ theo từng nguồn (Source Field Completeness)
        source_completeness: Dict[str, Dict[str, float]] = {}
        for src, src_total in sources_counter.items():
            source_completeness[src] = {}
            for _, fname in cls.CORE_FIELDS:
                val_c = source_field_valid[src].get(fname, 0)
                source_completeness[src][fname] = round((val_c / src_total) * 100, 2)

        # Tổng hợp tính Duy nhất (Uniqueness)
        colliding_ids = {uid: cnt for uid, cnt in unified_ids_counter.items() if cnt > 1}
        colliding_urls = {u: cnt for u, cnt in urls_counter.items() if cnt > 1}
        comp_title_dup_groups = {pair: cnt for pair, cnt in company_title_pairs.items() if cnt > 1}

        uniqueness_summary = {
            "total_records": total_records,
            # Chỉ số chi tiết cho unified_id
            "records_with_valid_unified_id": sum(unified_ids_counter.values()),
            "missing_or_empty_unified_id_count": missing_uid_count,
            "unique_unified_ids": len(unified_ids_counter),
            "colliding_id_count": len(colliding_ids),  # Số ID bị xung đột (số nhóm ID trùng)
            "records_in_colliding_ids": sum(colliding_ids.values()),  # Số bản ghi thuộc nhóm xung đột
            "excess_records_in_colliding_ids": sum(cnt - 1 for cnt in colliding_ids.values()),  # Số bản ghi dư vượt mức
            "is_unified_id_strictly_unique": (
                len(colliding_ids) == 0
                and missing_uid_count == 0
                and len(unified_ids_counter) == total_records
            ),
            "unified_id_collision_count": sum(cnt - 1 for cnt in colliding_ids.values()),  # Tương thích ngược

            # Chỉ số URL
            "records_with_valid_url": sum(urls_counter.values()),
            "missing_or_empty_url_count": missing_url_count,
            "unique_urls": len(urls_counter),
            "colliding_url_count": len(colliding_urls),
            "unique_source_job_pairs": len(source_job_pairs),

            # Chỉ số cho cặp (company, title)
            "company_title_duplicate_groups_count": len(comp_title_dup_groups),
            "company_title_records_in_groups": sum(comp_title_dup_groups.values()),
            "company_title_excess_records": sum(cnt - 1 for cnt in comp_title_dup_groups.values()),
            "company_title_duplicates_estimate": sum(cnt - 1 for cnt in comp_title_dup_groups.values()),  # Tương thích ngược
        }



        # Dị biệt kiểu dữ liệu
        heterogeneous_summary = {
            "extra_experience_types": dict(extra_experience_types),
            "extra_education_types": dict(extra_education_types),
            "salary_types_distribution": dict(salary_types_counter),
        }

        return {
            "total_records": total_records,
            "sources_distribution": sources_summary,
            "uniqueness_summary": uniqueness_summary,
            "missingness_summary": missingness_summary,
            "source_field_completeness": source_completeness,
            "heterogeneous_types": heterogeneous_summary,
        }

    @classmethod
    def print_text_summary(cls, profile_result: Dict[str, Any]) -> None:
        """In báo cáo profiling tóm tắt rõ ràng ra terminal chuẩn ASCII."""
        total = profile_result.get("total_records", 0)
        print("=" * 80)
        print(f"        BÁO CÁO PROFILING DỮ LIỆU EDA (TỔNG SỐ: {total:,} BẢN GHI)")
        print("=" * 80)

        # 1. Phân bố nguồn
        print("\n1. PHÂN BỐ THEO NGUỒN TUYỂN DỤNG (8 NGUỒN):")
        print(f"{'Source':<18} | {'Số lượng':<12} | {'Tỷ lệ (%)':<10}")
        print("-" * 46)
        for src, info in profile_result.get("sources_distribution", {}).items():
            print(f"{src:<18} | {info['count']:<12,d} | {info['percentage']:<10.2f}%")

        # 2. Khóa định danh & Tính duy nhất
        uniq = profile_result.get("uniqueness_summary", {})
        print("\n2. KIỂM TOÁN TÍNH DUY NHẤT (UNIQUENESS):")
        print(f"  - Số unified_id duy nhất         : {uniq.get('unique_unified_ids', 0):,}")
        print(f"  - Số ID bị xung đột (nhóm trùng) : {uniq.get('colliding_id_count', 0):,}")
        print(f"  - Số bản ghi thuộc ID xung đột   : {uniq.get('records_in_colliding_ids', 0):,}")
        print(f"  - Số bản ghi ID dư vượt mức      : {uniq.get('excess_records_in_colliding_ids', 0):,}")
        print(f"  - Số URL duy nhất                : {uniq.get('unique_urls', 0):,}")
        print(f"  - Nhóm lặp (công ty, tiêu đề)    : {uniq.get('company_title_duplicate_groups_count', 0):,} nhóm ({uniq.get('company_title_records_in_groups', 0):,} bài, {uniq.get('company_title_excess_records', 0):,} bài dư)")


        # 3. Mức độ khuyết thiếu của các trường cốt lõi
        print("\n3. TỶ LỆ ĐẦY ĐỦ CỦA CÁC TRƯỜNG CỐT LÕI (COMPLETENESS):")
        print(f"{'Trường dữ liệu':<22} | {'Có giá trị':<12} | {'Tỷ lệ (%)':<10} | {'Chi tiết khuyết thiếu':<30}")
        print("-" * 80)
        for fname, info in profile_result.get("missingness_summary", {}).items():
            b = info["breakdown"]
            detail = f"null:{b['null']} | empty_str:{b['empty_string']} | empty_list:{b['empty_list']}"
            print(f"{fname:<22} | {info['valid_count']:<12,d} | {info['valid_rate']:<10.2f}% | {detail}")

        # 4. Kiểu dữ liệu dị biệt
        het = profile_result.get("heterogeneous_types", {})
        print("\n4. KHẢO SÁT KIỂU DỮ LIỆU DỊ BIỆT (HETEROGENEOUS TYPES):")
        print(f"  - extra.experience types : {het.get('extra_experience_types')}")
        print(f"  - extra.education types  : {het.get('extra_education_types')}")
        print(f"  - salary_type phân bố    : {het.get('salary_types_distribution')}")
        print("=" * 80)


if __name__ == "__main__":
    import sys
    from pathlib import Path

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    project_root = Path(__file__).resolve().parents[3]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from crawlers.preprocessing.eda.loader import EDALoader

    default_path = Path("data/processed/preClean/merged_jobs_clean.json")
    target_path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_path

    print(f"[*] Đang nạp dữ liệu từ: {target_path} ...")
    raw_records = EDALoader.load_raw_records(target_path)
    print(f"[*] Đã nạp thành công {len(raw_records):,} bản ghi. Đang phân tích profiling...")
    result = EDAProfiler.profile_dataset(raw_records)
    EDAProfiler.print_text_summary(result)
