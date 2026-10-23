# -*- coding: utf-8 -*-
"""Unit tests for TopDev crawler (Schema v1 compliance)."""

import unittest
from crawlers.sources.topdev.crawler import TopDevCrawler, _make_record, extract_raw_envelope_from_html
from crawlers.common.schema import JobRecord, RawJobEnvelope
from datetime import datetime, timezone, timedelta

LOCAL_TZ = timezone(timedelta(hours=7))


SAMPLE_LISTING_JOB = {
    "id": 2137764,
    "title": "Senior Backend Developer",
    "slug": "senior-backend-developer-2137764",
    "company": {
        "id": 999,
        "name": "TopDev Tech Corp",
        "display_name": "TopDev Tech Corp",
    },
    "salary": {
        "min": 25000000,
        "max": 45000000,
        "currency": "VND",
        "value": "25 - 45 triệu",
        "is_negotiable": 0,
    },
    "is_salary_visible": True,
    "skills_arr": ["Python", "FastAPI", "PostgreSQL"],
    "content": "<p>Phát triển các hệ thống API phân tán hiệu năng cao.</p>",
    "requirements_arr": ["3+ năm kinh nghiệm với Python", "Hiểu biết microservices"],
    "benefits_v2": ["Tháng lương 13", "Bảo hiểm sức khỏe"],
    "addresses": {
        "address_region_list": "Thành phố Hồ Chí Minh",
    },
    "contract_types_str": "Fulltime",
    "job_levels_str": "Senior",
}


class TestTopDevCrawler(unittest.TestCase):
    def setUp(self):
        self.crawler = TopDevCrawler(max_items=2)

    def test_parse_item_schema_v1(self):
        record = self.crawler.parse_item(SAMPLE_LISTING_JOB)
        self.assertIsNotNone(record)
        self.assertIsInstance(record, JobRecord)

        # Meta
        self.assertEqual(record.meta.source, "topdev")
        self.assertEqual(record.meta.source_job_id, "2137764")
        self.assertEqual(record.meta.language, "vi")

        # Raw
        raw = record.raw
        self.assertEqual(raw.title, "Senior Backend Developer")
        self.assertEqual(raw.company, "TopDev Tech Corp")
        self.assertEqual(raw.salary.salary_min, 25.0)
        self.assertEqual(raw.salary.salary_max, 45.0)
        self.assertEqual(raw.salary.salary_currency, "VND")
        self.assertFalse(raw.salary.is_negotiable)

        # Lists
        self.assertGreater(len(raw.description_list), 0)
        self.assertFalse(raw.description_list[0].startswith("•"))
        self.assertIn("Python", raw.tags.skills)

    def test_fallback_description_list_when_content_empty(self):
        job_copy = dict(SAMPLE_LISTING_JOB)
        job_copy["content"] = ""
        record = self.crawler.parse_item(job_copy)
        self.assertIsNotNone(record)
        # description_list should fallback to [title], not None
        self.assertIsInstance(record.raw.description_list, list)
        self.assertEqual(record.raw.description_list, ["Senior Backend Developer"])

    def test_extract_raw_envelope_from_html(self):
        sample_html = """
        <div class="job-detail">
          <h1 class="job-title">Chief Accountant</h1>
          <div class="company-name">VCJ WAREHOUSE</div>
          <div class="salary">15.000.000 VND to 23.000.000 VND</div>
          <div class="description"><p>Real Estate</p></div>
          <div class="requirements"><ul><li>2 years exp</li></ul></div>
        </div>
        """
        envelope = extract_raw_envelope_from_html(
            sample_html,
            job_id="2137024",
            url="https://topdev.vn/job/2137024",
        )
        self.assertIsInstance(envelope, RawJobEnvelope)
        self.assertEqual(envelope.metadata["source"], "topdev")
        self.assertEqual(envelope.metadata["crawler_version"], "2.0.0")
        self.assertEqual(envelope.raw_payload["job-title"], "Chief Accountant")
        self.assertEqual(envelope.raw_payload["salary"], "15.000.000 VND to 23.000.000 VND")
        self.assertIn("job-detail", envelope.raw_payload)

    def test_crawler_parse_raw_envelope(self):
        envelope = self.crawler.parse_raw_envelope(SAMPLE_LISTING_JOB)
        self.assertIsInstance(envelope, RawJobEnvelope)
        self.assertEqual(envelope.metadata["source"], "topdev")
        self.assertEqual(envelope.metadata["source_job_id"], "2137764")
        self.assertEqual(envelope.raw_payload["title"], "Senior Backend Developer")
        # Cơ chế hash chỉ có 1 content_hash duy nhất
        self.assertIn("content_hash", envelope.metadata)
        self.assertNotIn("canonical_hash", envelope.metadata)
        self.assertNotIn("field_hashes", envelope.metadata)
        # Kiểm tra trường language
        self.assertEqual(envelope.metadata["language"], "vi")

    def test_extract_raw_envelope_from_real_html_matches_neccessary(self):
        from pathlib import Path
        html_path = Path("crawlers/sources/topdev/.html")
        if not html_path.exists():
            self.skipTest("crawlers/sources/topdev/.html không tồn tại")

        html_content = html_path.read_text(encoding="utf-8")
        envelope = extract_raw_envelope_from_html(
            html_content,
            job_id="2137773",
            url="https://topdev.vn/viec-lam/ky-su-phat-trien-va-van-hanh-devops-tong-cong-ty-ha-tang-mang-vnpt-net-2137773",
        )
        self.assertIsInstance(envelope, RawJobEnvelope)
        meta = envelope.metadata
        raw = envelope.raw_payload

        # Kiểm tra cơ chế hash duy nhất & language
        self.assertIn("content_hash", meta)
        self.assertEqual(len(meta["content_hash"]), 64)
        self.assertNotIn("canonical_hash", meta)
        self.assertNotIn("field_hashes", meta)
        self.assertEqual(meta["language"], "vi")

        # Kiểm tra trích xuất 100% trường bắt buộc theo neccessay.md
        self.assertEqual(raw["title"], "Kỹ Sư Phát Triển Và Vận Hành DevOps")
        self.assertEqual(raw["company"], "Tổng Công Ty Hạ Tầng Mạng (VNPT-Net)")
        self.assertEqual(raw["salary_raw"], "Đăng nhập để xem mức lương")
        self.assertEqual(raw["location"], "Hà Nội")
        self.assertEqual(raw["job_level"], "Chuyên viên")
        self.assertEqual(raw["experience"], "2 năm")
        self.assertEqual(raw["tags"], ["Linux", "DevOps", "Docker", "4+"])
        self.assertIn("Còn 20 ngày", raw["remaining_time"])
        self.assertIn("18 Ứng viên", raw["applicants_count"])
        self.assertEqual(raw["positions_count"], "02")
        self.assertEqual(raw["income_text"], "từ 400 đến 550 triệu đồng/năm (min/max)")
        self.assertEqual(raw["company_industry"], "Viễn Thông")
        self.assertEqual(raw["company_size"], "Hơn 1000 Nhân viên")
        self.assertEqual(raw["company_country"], "Vietnam")
        self.assertEqual(raw["company_active_jobs"], "4 Việc làm đang tuyển")
        self.assertEqual(len(raw["responsibilities"]), 8)
        self.assertGreaterEqual(len(raw["requirements"]), 20)
        self.assertEqual(len(raw["benefits"]), 5)


if __name__ == "__main__":
    unittest.main()
