# -*- coding: utf-8 -*-
"""Unit tests for ViecLam24h crawler (Schema v1 compliance & offline replay)."""

import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta

from crawlers.sources.vieclam24h.crawler import ViecLam24hCrawler, _make_record
from crawlers.common.schema import JobRecord
from crawlers.common.data_quality import DataQualityChecker

LOCAL_TZ = timezone(timedelta(hours=7))

SAMPLE_JOB_DETAIL = {
    "id": 1001,
    "title": "Senior Frontend Developer (ReactJS / TypeScript)",
    "title_slug": "senior-frontend-developer-reactjs-typescript",
    "employer_info": {"name": "Công ty Cổ phần Công nghệ ABC"},
    "salary_min": 25000000,
    "salary_max": 45000000,
    "salary_range_text": "25 - 45 triệu",
    "description_html": "<p>Phát triển hệ thống web app chất lượng cao</p><ul><li>Thiết kế component React</li><li>Tối ưu hóa hiệu năng web</li></ul>",
    "other_requirement_html": "<p>Yêu cầu:</p><ul><li>Ít nhất 4 năm kinh nghiệm với ReactJS</li><li>Thành thạo TypeScript, Redux Toolkit</li><li>Có tư duy Clean Architecture</li></ul>",
    "benefit_html": "<p>Quyền lợi:</p><ul><li>Lương tháng 13 + thưởng hiệu quả</li><li>Bảo hiểm sức khỏe toàn diện</li><li>Phụ cấp ăn trưa và gửi xe</li></ul>",
    "experience_range": "4",
    "skills": [{"name": "ReactJS"}, {"name": "TypeScript"}, {"name": "Redux"}],
    "places": [{"address": "Tầng 5, Tòa nhà Landmark", "city_name": "Hồ Chí Minh"}],
    "resume_apply_expired": 1767225600,
    "created_at": 1735689600,
    "vacancy_quantity": 2,
    "type_working_text": "Toàn thời gian",
    "position_text": "Senior",
    "education": "Đại học",
}


class TestViecLam24hCrawler(unittest.TestCase):
    def setUp(self):
        self.crawler = ViecLam24hCrawler(max_items=2)

    def test_parse_item_schema_v1(self):
        raw_item = {
            "job_detail": SAMPLE_JOB_DETAIL,
            "url": "https://vieclam24h.vn/sample-job.html",
        }
        record = self.crawler.parse_item(raw_item)
        self.assertIsNotNone(record)
        self.assertIsInstance(record, JobRecord)

        # Meta validation
        self.assertEqual(record.meta.source, "vieclam24h")
        self.assertEqual(record.meta.source_job_id, "1001")
        self.assertEqual(record.meta.language, "vi")

        # Raw validation
        raw = record.raw
        self.assertEqual(raw.title, "Senior Frontend Developer (ReactJS / TypeScript)")
        self.assertEqual(raw.company, "Công ty Cổ phần Công nghệ ABC")
        self.assertEqual(raw.salary.salary_min, 25.0)
        self.assertEqual(raw.salary.salary_max, 45.0)
        self.assertEqual(raw.salary.salary_currency, "VND")
        self.assertEqual(raw.salary.pay_period, "month")
        self.assertFalse(raw.salary.is_negotiable)

        # Tags: 3-group tags rule
        self.assertIsNone(raw.tags.requirements)
        self.assertIsNone(raw.tags.benefits)
        self.assertEqual(raw.tags.skills, ["ReactJS", "TypeScript", "Redux"])

        # Lists cleaned
        self.assertIn("Thiết kế component React", raw.description_list)
        self.assertIn("Ít nhất 4 năm kinh nghiệm với ReactJS", raw.requirements_list)
        self.assertIn("Lương tháng 13 + thưởng hiệu quả", raw.benefits_list)

        # Extra
        self.assertEqual(raw.extra.get("hiring_quantity"), "2 người")
        self.assertEqual(raw.seniority_text, "Senior")
        self.assertEqual(raw.employment_type_text, "Toàn thời gian")

    def test_offline_run_with_local_json(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            sample_file = tmp_path / "offline_sample.json"
            sample_file.write_text(json.dumps([SAMPLE_JOB_DETAIL]), encoding="utf-8")

            crawler = ViecLam24hCrawler(
                checkpoint_dir=str(tmp_path / "ckpt"),
                output_dir=tmp_path / "output",
                max_items=1,
                local_json_file=sample_file,
            )
            stats = crawler.run()
            self.assertEqual(stats["source"], "vieclam24h")
            self.assertEqual(stats["crawled"], 1)
            self.assertEqual(stats["errors"], 0)


    def test_dom_ground_truth_payload(self):
        """Test build_raw_payload on crawlers/sources/vieclam24h/.html against neccessary.md."""
        html_path = Path(__file__).resolve().parents[2] / "crawlers" / "sources" / "vieclam24h" / ".html"
        if not html_path.exists():
            self.skipTest(f"Sample DOM file {html_path} not found")

        html_content = html_path.read_text(encoding="utf-8")
        from crawlers.sources.vieclam24h.crawler import build_raw_payload

        payload = build_raw_payload(html=html_content)

        # 1. SD1 Zero Information Loss & Schema purity
        self.assertNotIn("salary_min", payload, "Raw payload must NOT have artificial salary_min")
        self.assertNotIn("salary_max", payload, "Raw payload must NOT have artificial salary_max")
        self.assertEqual(payload["salary"], "10 - 25 triệu")

        # 2. Key fields from neccessary.md
        self.assertEqual(payload["title"], "Nhân Viên Kinh Doanh Phần Mềm | Nghỉ T7 - Chủ Nhật")
        self.assertEqual(payload["deadline"], "05/11/2026")
        self.assertEqual(payload["location_summary"], "Hà Nội")
        self.assertEqual(payload["experience_summary"], "1 năm")
        self.assertIn("Tiếp nhận data từ hệ thống, liên hệ tư vấn giới thiệu sản phẩm phần mềm đến khách hàng.", payload["description"])
        self.assertIn("Tốt nghiệp Cao đẳng/Đại học.", payload["requirements"])
        self.assertIn("Lương cứng 7-9 triệu + % Doanh số + Thưởng Hiệu quả CV", payload["benefits"])
        self.assertEqual(payload["company"]["name"], "Công Ty TNHH Đầu Tư Nghiên Cứu Và Phát Triển Phần Mềm Việt Nam")
        self.assertEqual(payload["company"]["size"], "10 - 150 nhân viên")

        # 3. Verify transformation into JobRecord (Staging tier handles min/max)
        raw_item = {
            "job_detail": payload,
            "url": "https://vieclam24h.vn/ban-hang-kinh-doanh/nhan-vien-kinh-doanh-phan-mem-nghi-t7-chu-nhat-c13p210000160id200966027.html"
        }
        record = self.crawler.parse_item(raw_item)
        self.assertIsNotNone(record)
        self.assertEqual(record.raw.salary.salary_min, 10.0)
        self.assertEqual(record.raw.salary.salary_max, 25.0)
        self.assertEqual(record.raw.salary.salary_text, "10 - 25 triệu")


if __name__ == "__main__":
    unittest.main()
