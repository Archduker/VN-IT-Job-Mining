# -*- coding: utf-8 -*-
"""Unit tests for TopDev crawler (Schema v1 compliance)."""

import unittest
from crawlers.sources.topdev.crawler import TopDevCrawler, _make_record
from crawlers.common.schema import JobRecord
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


if __name__ == "__main__":
    unittest.main()
