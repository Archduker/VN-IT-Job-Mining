# -*- coding: utf-8 -*-
"""Unit tests cho crawlers.preprocessing.eda.text_analyzer."""

import json
import unittest
from typing import Any

from crawlers.preprocessing.eda.text_analyzer import TextAnalyzer


class TestTextAnalyzer(unittest.TestCase):
    def test_empty_dataset(self):
        res = TextAnalyzer.analyze([])
        self.assertEqual(res["total_analyzed"], 0)
        self.assertEqual(res["skills_analysis"]["skills_coverage_rate_total"], 0.0)

    def test_title_length_and_word_counts(self):
        records = [
            {"title": "Senior Python Developer"},  # 23 ký tự, 3 từ
            {"title": "Frontend ReactJS"},          # 16 ký tự, 2 từ
            {"title": ""},                          # 0 ký tự, 0 từ
            {"title": None},                        # 0 ký tự, 0 từ
        ]
        res = TextAnalyzer.analyze(records)
        t_summary = res["title_analysis"]

        self.assertEqual(t_summary["total_analyzed"], 4)
        char_stats = t_summary["char_length_stats"]
        self.assertEqual(char_stats["count"], 4)
        self.assertEqual(char_stats["min"], 0.0)
        self.assertEqual(char_stats["max"], 23.0)

        word_stats = t_summary["word_count_stats"]
        self.assertEqual(word_stats["min"], 0.0)
        self.assertEqual(word_stats["max"], 3.0)

    def test_sections_analysis_and_thin_content_flagging(self):
        records = [
            # Bài 1: Nội dung đầy đủ (3 bullets, 30 từ) -> is_thin = False
            {
                "description_list": [
                    "Phát triển hệ thống microservices sử dụng Python và FastAPI với hiệu năng cao.",
                    "Thiết kế cơ sở dữ liệu phân tán PostgreSQL và Redis cache.",
                    "Tham gia xây dựng kiến trúc CI/CD tự động hóa trên nền tảng Kubernetes.",
                ],
                "requirements_list": ["Yêu cầu 1", "Yêu cầu 2"],
                "benefits_list": [],
            },
            # Bài 2: Nội dung mỏng do ít hơn 2 bullet (1 bullet, 5 từ) -> is_thin = True
            {
                "description_list": ["Làm việc theo phân công."],
                "requirements_list": [],
                "benefits_list": None,
            },
            # Bài 3: Nội dung mỏng do ít hơn 20 từ (2 bullets nhưng mỗi bullet chỉ 2 từ = 4 từ) -> is_thin = True
            {
                "description_list": ["Lập trình.", "Bảo trì."],
                "requirements_list": None,
                "benefits_list": None,
            },
            # Bài 4: Rỗng -> is_empty = True, is_thin = True
            {
                "description_list": [],
                "requirements_list": None,
                "benefits_list": None,
            },
        ]
        res = TextAnalyzer.analyze(records)
        desc_sum = res["sections_analysis"]["description"]

        # 4 bài phân tích
        self.assertEqual(desc_sum["bullet_count_stats"]["count"], 4)
        # 3 bài bị đánh dấu là nội dung mỏng (Bài 2, Bài 3, Bài 4)
        self.assertEqual(desc_sum["thin_content_summary"]["count"], 3)
        self.assertEqual(desc_sum["thin_content_summary"]["percentage"], 75.0)
        # 1 bài rỗng (Bài 4)
        self.assertEqual(desc_sum["empty_content_summary"]["count"], 1)

    def test_skills_normalization_and_coverage(self):
        records = [
            # Bài 1 có 3 kỹ năng (trong đó có trùng lặp chữ hoa/thường trong cùng bài)
            {
                "_meta": {"source": "topcv"},
                "tags": {"skills": ["Python", " python ", "PYTHON", "FastAPI", "Docker"]},
            },
            # Bài 2 có 2 kỹ năng
            {
                "_meta": {"source": "topcv"},
                "tags": {"skills": ["docker", "Kubernetes"]},
            },
            # Bài 3 không có kỹ năng
            {
                "_meta": {"source": "itviec"},
                "tags": {"skills": []},
            },
            # Bài 4 tags là None
            {
                "_meta": {"source": "itviec"},
                "tags": None,
            },
        ]
        res = TextAnalyzer.analyze(records)
        s_sum = res["skills_analysis"]

        self.assertEqual(s_sum["total_records_analyzed"], 4)
        # Chỉ có 2 bài có kỹ năng
        self.assertEqual(s_sum["records_with_skills_count"], 2)
        # Tỷ lệ bao phủ trên toàn bộ tập dữ liệu (2 / 4 = 50%)
        self.assertEqual(s_sum["skills_coverage_rate_total"], 50.0)

        # Số kỹ năng khác nhau: python, fastapi, docker, kubernetes = 4
        self.assertEqual(s_sum["distinct_skills_count"], 4)

        # Kiểm tra Top kỹ năng
        top_skills = {item["skill_normalized"]: item for item in s_sum["top_30_skills"]}
        self.assertIn("python", top_skills)
        self.assertIn("docker", top_skills)

        # Docker xuất hiện ở cả Bài 1 và Bài 2 -> frequency = 2
        self.assertEqual(top_skills["docker"]["frequency"], 2)
        self.assertEqual(top_skills["docker"]["coverage_pct_of_skills_jobs"], 100.0)  # 2/2 bài có kỹ năng
        self.assertEqual(top_skills["docker"]["coverage_pct_of_total_jobs"], 50.0)    # 2/4 bài tổng thể

        # Python chỉ xuất hiện ở Bài 1 (dù trong bài lặp 3 lần vẫn chỉ tính 1) -> frequency = 1
        self.assertEqual(top_skills["python"]["frequency"], 1)

        # Phân bố độ phủ theo nguồn
        src_cov = s_sum["source_skills_coverage"]
        self.assertEqual(src_cov["topcv"]["total_records"], 2)
        self.assertEqual(src_cov["topcv"]["records_with_skills"], 2)
        self.assertEqual(src_cov["topcv"]["coverage_percentage"], 100.0)

        self.assertEqual(src_cov["itviec"]["total_records"], 2)
        self.assertEqual(src_cov["itviec"]["records_with_skills"], 0)
        self.assertEqual(src_cov["itviec"]["coverage_percentage"], 0.0)

    def test_crash_safety_and_json_serializability(self):
        # Dữ liệu bất thường: None, kiểu số, chuỗi thay vì list
        records: list[Any] = [
            None,
            "not a dict",
            {"title": 12345, "description_list": "Chuỗi văn bản thay vì danh sách gạch đầu dòng"},
            {"tags": {"skills": [None, 999, ""]}},
        ]
        res = TextAnalyzer.analyze(records)  # type: ignore[arg-type]  # Co y truyen du lieu bat thuong (None, str) de kiem thu crash-safety
        self.assertEqual(res["total_analyzed"], 4)

        # Đảm bảo tuần tự hóa JSON an toàn 100%
        json_output = json.dumps(res, ensure_ascii=False)
        self.assertIsInstance(json_output, str)


if __name__ == "__main__":
    unittest.main()
