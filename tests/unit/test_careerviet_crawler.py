# -*- coding: utf-8 -*-
"""Unit tests for CareerViet crawler (Schema v1 compliance)."""

import os
import unittest
from unittest.mock import MagicMock, patch

from crawlers.sources.careerviet.crawler import CareerVietCrawler, extract_job_id
from crawlers.common.schema import JobRecord


SAMPLE_DETAIL_HTML = """
<!DOCTYPE html>
<html>
<head><title>Senior Python Developer - ABC Corp | CareerViet.vn</title></head>
<body>
<div class="job-detail-page">
    <h1 class="title">Senior Python Developer</h1>
    <a class="employer job-company-name" href="/nha-tuyen-dung/abc">ABC Tech Solutions</a>
    <ul class="detail-box">
        <li><strong>Lương</strong><p>25 - 45 Triệu VND</p></li>
        <li><strong>Địa điểm</strong><p>Hồ Chí Minh</p></li>
        <li><strong>Kinh nghiệm</strong><p>3 - 5 Năm</p></li>
        <li><strong>Cấp bậc</strong><p>Nhân viên</p></li>
        <li><strong>Hình thức</strong><p>Nhân viên chính thức</p></li>
        <li><strong>Ngày cập nhật</strong><p>10/10/2026</p></li>
        <li><strong>Hết hạn nộp</strong><p>30/11/2026</p></li>
    </ul>
    <div class="detail-row">
        <h2>Mô tả Công việc</h2>
        <ul>
            <li>• Phát triển backend APIs bằng Python FastAPI và Django.</li>
            <li>• Thiết kế kiến trúc cơ sở dữ liệu PostgreSQL và Redis caching.</li>
        </ul>
    </div>
    <div class="detail-row">
        <h2>Yêu Cầu Công Việc</h2>
        <ul>
            <li>- Có ít nhất 3 năm kinh nghiệm lập trình Python.</li>
            <li>- Thành thạo Docker, Kubernetes, CI/CD pipelines.</li>
        </ul>
    </div>
    <div class="detail-row">
        <h2>Phúc lợi</h2>
        <ul>
            <li>* Thưởng tháng 13 và KPI hấp dẫn.</li>
            <li>* Bảo hiểm y tế cao cấp cho nhân viên và người thân.</li>
        </ul>
    </div>
    <div class="job-tags">
        <a class="tag-item">Python</a>
        <a class="tag-item">FastAPI</a>
        <a class="tag-item">PostgreSQL</a>
    </div>
</div>
</body>
</html>
"""


class TestCareerVietCrawler(unittest.TestCase):
    def setUp(self):
        self.crawler = CareerVietCrawler(max_items=2)

    def test_extract_job_id(self):
        url1 = "https://careerviet.vn/vi/tim-viec-lam/senior-dev.35C89996.html"
        self.assertEqual(extract_job_id(url1), "35C89996")
        url2 = "https://careerviet.vn/viec-lam/dev/1234567.html"
        self.assertEqual(extract_job_id(url2), "1234567")

    def test_parse_item_schema_v1(self):
        item = {
            "job_id": "35C89996",
            "url": "https://careerviet.vn/vi/tim-viec-lam/senior-dev.35C89996.html",
            "html": SAMPLE_DETAIL_HTML,
        }
        record = self.crawler.parse_item(item)
        self.assertIsNotNone(record)
        self.assertIsInstance(record, JobRecord)

        # Meta
        self.assertEqual(record.meta.source, "careerviet")
        self.assertEqual(record.meta.source_job_id, "35C89996")
        self.assertEqual(record.meta.language, "vi")

        # Raw
        raw = record.raw
        self.assertEqual(raw.title, "Senior Python Developer")
        self.assertEqual(raw.company, "ABC Tech Solutions")
        self.assertEqual(raw.salary.salary_min, 25.0)
        self.assertEqual(raw.salary.salary_max, 45.0)
        self.assertEqual(raw.salary.salary_currency, "VND")
        self.assertFalse(raw.salary.is_negotiable)

        # Lists without bullets
        self.assertGreater(len(raw.description_list), 0)
        self.assertFalse(raw.description_list[0].startswith("•"))
        self.assertFalse(raw.requirements_list[0].startswith("-"))
        self.assertFalse(raw.benefits_list[0].startswith("*"))

        # Tags
        self.assertIsNotNone(raw.tags.skills)
        self.assertIn("Python", raw.tags.skills)

        # Metadata
        self.assertEqual(raw.location_text, "Hồ Chí Minh")
        self.assertEqual(raw.deadline_text, "30/11/2026")
        self.assertEqual(raw.seniority_text, "Nhân viên")


if __name__ == "__main__":
    unittest.main()
