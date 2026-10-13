# -*- coding: utf-8 -*-
"""crawlers.preprocessing.eda.text_analyzer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Bộ phân tích độ dài văn bản, nội dung mỏng và thẻ kỹ năng (VN-IT-Job-Mining).

Nguyên tắc kỹ thuật:
- Đo lường độ dài ký tự và số từ cho tiêu đề (title).
- Thống kê bullet points và số từ riêng biệt cho description, requirements, benefits.
- Đánh dấu nội dung mỏng (Thin Content) theo ngưỡng: < 2 bullet HOẶC < 20 từ.
- Báo cáo độ phủ kỹ năng theo cả N_valid (tổng bản ghi) và N_has_skills (bài có kỹ năng).
- Chuẩn hóa kỹ năng bằng cách trim khoảng trắng thừa và lower-case, giữ lại tên gốc.
- Thống kê Top 30 kỹ năng và độ phủ theo 8 nguồn.
- An toàn tuyệt đối với dữ liệu rác, null, không làm crash pipeline.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple


class TextAnalyzer:
    """Bộ phân tích văn bản tuyển dụng và thẻ kỹ năng công nghệ."""

    @staticmethod
    def _count_words(text: Any) -> int:
        """Đếm số từ của một chuỗi văn bản an toàn."""
        if text is None:
            return 0
        s = str(text).strip()
        if not s:
            return 0
        return len(s.split())

    @classmethod
    def _analyze_section_items(cls, items: Any) -> Dict[str, Any]:
        """Phân tích danh sách gạch đầu dòng (bullet points) của một phần văn bản.

        Returns:
            Dict chứa: bullet_count, word_count, is_thin, is_empty.
        """
        if items is None:
            return {"bullet_count": 0, "word_count": 0, "is_thin": True, "is_empty": True}

        if not isinstance(items, (list, tuple, set)):
            # Trường hợp nguồn lưu chuỗi văn bản thay vì mảng
            s = str(items).strip()
            if not s:
                return {"bullet_count": 0, "word_count": 0, "is_thin": True, "is_empty": True}
            w_cnt = cls._count_words(s)
            return {
                "bullet_count": 1,
                "word_count": w_cnt,
                "is_thin": (1 < 2 or w_cnt < 20),
                "is_empty": False,
            }

        clean_bullets = [str(x).strip() for x in items if x is not None and str(x).strip()]
        b_cnt = len(clean_bullets)
        if b_cnt == 0:
            return {"bullet_count": 0, "word_count": 0, "is_thin": True, "is_empty": True}

        w_cnt = sum(cls._count_words(x) for x in clean_bullets)
        is_thin = (b_cnt < 2 or w_cnt < 20)
        return {
            "bullet_count": b_cnt,
            "word_count": w_cnt,
            "is_thin": is_thin,
            "is_empty": False,
        }

    @staticmethod
    def _calculate_descriptive_stats(values: List[int]) -> Optional[Dict[str, float]]:
        """Tính toán thống kê phân vị và trung bình cho danh sách số nguyên."""
        if not values:
            return None
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        mean_val = sum(sorted_vals) / n

        def quantile(p: float) -> float:
            if n == 1:
                return float(sorted_vals[0])
            pos = p * (n - 1)
            idx = int(pos)
            diff = pos - idx
            if idx + 1 < n:
                return round(sorted_vals[idx] + diff * (sorted_vals[idx + 1] - sorted_vals[idx]), 2)
            return float(sorted_vals[idx])

        return {
            "count": n,
            "min": float(sorted_vals[0]),
            "q25": quantile(0.25),
            "median": quantile(0.50),
            "mean": round(mean_val, 2),
            "q75": quantile(0.75),
            "max": float(sorted_vals[-1]),
        }

    @classmethod
    def analyze(cls, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Phân tích văn bản toàn diện trên danh sách bản ghi tuyển dụng hợp lệ.

        Args:
            records: Danh sách dict bài đăng tuyển dụng.

        Returns:
            Dict chứa kết quả độ dài tiêu đề, các phần văn bản, nội dung mỏng,
            và xếp hạng kỹ năng.
        """
        total_records = len(records)
        if total_records == 0:
            return {
                "total_analyzed": 0,
                "title_analysis": {},
                "sections_analysis": {},
                "skills_analysis": {"skills_coverage_rate_total": 0.0, "top_30_skills": []},
            }

        # Thu thập dữ liệu tiêu đề
        title_char_lens: List[int] = []
        title_word_counts: List[int] = []

        # Thu thập dữ liệu từng phần
        section_data: Dict[str, Dict[str, List[int]]] = {
            "description": {"bullets": [], "words": []},
            "requirements": {"bullets": [], "words": []},
            "benefits": {"bullets": [], "words": []},
        }
        thin_counts: Counter[str] = Counter()
        empty_counts: Counter[str] = Counter()

        # Thu thập kỹ năng
        skill_counter: Counter[str] = Counter()
        canonical_skill_name: Dict[str, str] = {}
        skills_per_job_list: List[int] = []
        records_with_skills_count = 0

        # Phân bố kỹ năng theo nguồn
        source_records_counter: Counter[str] = Counter()
        source_skills_counter: Counter[str] = Counter()

        for rec in records:
            if not isinstance(rec, dict):
                continue

            meta = rec.get("_meta") if isinstance(rec.get("_meta"), dict) else {}
            src = str(meta.get("source") or "UNKNOWN").lower().strip()
            source_records_counter[src] += 1

            # 1. Tiêu đề
            raw_title = str(rec.get("title") or "").strip()
            t_char = len(raw_title)
            t_word = cls._count_words(raw_title)
            title_char_lens.append(t_char)
            title_word_counts.append(t_word)

            # 2. Các phần văn bản
            sections_map = {
                "description": rec.get("description_list"),
                "requirements": rec.get("requirements_list"),
                "benefits": rec.get("benefits_list"),
            }

            for sec_name, raw_content in sections_map.items():
                sec_stat = cls._analyze_section_items(raw_content)
                section_data[sec_name]["bullets"].append(sec_stat["bullet_count"])
                section_data[sec_name]["words"].append(sec_stat["word_count"])

                if sec_stat["is_thin"]:
                    thin_counts[sec_name] += 1
                if sec_stat["is_empty"]:
                    empty_counts[sec_name] += 1

            # 3. Kỹ năng (tags.skills)
            tags = rec.get("tags") if isinstance(rec.get("tags"), dict) else {}
            raw_skills_list = tags.get("skills")

            job_skills_norm: List[str] = []
            if isinstance(raw_skills_list, (list, tuple, set)):
                for s in raw_skills_list:
                    if s is None:
                        continue
                    s_str = str(s).strip()
                    if not s_str:
                        continue
                    norm_s = re.sub(r"\s+", " ", s_str.lower())
                    job_skills_norm.append(norm_s)
                    if norm_s not in canonical_skill_name:
                        canonical_skill_name[norm_s] = s_str

            # Khử trùng lặp kỹ năng trong cùng một bài đăng
            unique_job_skills = list(set(job_skills_norm))
            if unique_job_skills:
                records_with_skills_count += 1
                source_skills_counter[src] += 1
                skills_per_job_list.append(len(unique_job_skills))
                for s in unique_job_skills:
                    skill_counter[s] += 1

        # Tổng hợp báo cáo Tiêu đề
        title_summary = {
            "total_analyzed": total_records,
            "char_length_stats": cls._calculate_descriptive_stats(title_char_lens),
            "word_count_stats": cls._calculate_descriptive_stats(title_word_counts),
        }

        # Tổng hợp báo cáo 3 phần văn bản
        sections_summary: Dict[str, Any] = {}
        for sec_name in ("description", "requirements", "benefits"):
            thin_c = thin_counts[sec_name]
            empty_c = empty_counts[sec_name]
            sections_summary[sec_name] = {
                "bullet_count_stats": cls._calculate_descriptive_stats(section_data[sec_name]["bullets"]),
                "word_count_stats": cls._calculate_descriptive_stats(section_data[sec_name]["words"]),
                "thin_content_summary": {
                    "count": thin_c,
                    "percentage": round((thin_c / total_records) * 100, 2),
                    "criteria": "< 2 bullets hoặc < 20 từ",
                },
                "empty_content_summary": {
                    "count": empty_c,
                    "percentage": round((empty_c / total_records) * 100, 2),
                },
            }

        # Tổng hợp Top 30 kỹ năng
        top_30_list: List[Dict[str, Any]] = []
        for norm_s, count in skill_counter.most_common(30):
            top_30_list.append({
                "skill_normalized": norm_s,
                "canonical_name": canonical_skill_name.get(norm_s, norm_s),
                "frequency": count,
                "coverage_pct_of_skills_jobs": (
                    round((count / records_with_skills_count) * 100, 2)
                    if records_with_skills_count > 0
                    else 0.0
                ),
                "coverage_pct_of_total_jobs": round((count / total_records) * 100, 2),
            })

        # Phân bố độ phủ kỹ năng theo nguồn
        source_skills_breakdown: Dict[str, Any] = {}
        for src, total_src in source_records_counter.most_common():
            has_skills = source_skills_counter.get(src, 0)
            source_skills_breakdown[src] = {
                "total_records": total_src,
                "records_with_skills": has_skills,
                "coverage_percentage": round((has_skills / total_src) * 100, 2) if total_src > 0 else 0.0,
            }

        skills_summary = {
            "total_records_analyzed": total_records,
            "records_with_skills_count": records_with_skills_count,
            "skills_coverage_rate_total": round((records_with_skills_count / total_records) * 100, 2),
            "distinct_skills_count": len(skill_counter),
            "skills_per_job_stats": cls._calculate_descriptive_stats(skills_per_job_list),
            "top_30_skills": top_30_list,
            "source_skills_coverage": source_skills_breakdown,
        }

        return {
            "total_analyzed": total_records,
            "title_analysis": title_summary,
            "sections_analysis": sections_summary,
            "skills_analysis": skills_summary,
        }
