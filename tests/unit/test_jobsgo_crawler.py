# -*- coding: utf-8 -*-
"""Unit tests for JobsGO crawler."""

import unittest
from crawlers.sources.jobsgo.crawler import JobsGoCrawler
from crawlers.common.schema import JobRecord


SAMPLE_JOB_HTML = """
<div class="job-detail">
    <h1 class="job-title">Backend Python Engineer</h1>
    <div class="company-name">JobsGO Tech Solutions</div>
    <div class="salary">20,000,000 - 35,000,000 VNĐ</div>
    <div class="job-location">Hồ Chí Minh</div>
    <div class="job-description">
        <p>Phát triển các hệ thống backend chịu tải cao.</p>
    </div>
    <div class="job-requirements">
        <ul>
            <li>Có ít nhất 2 năm kinh nghiệm làm việc với Python.</li>
            <li>Thành thạo FastAPI hoặc Django.</li>
        </ul>
    </div>
    <div class="job-benefits">
        <ul>
            <li>Lương thưởng tháng 13.</li>
            <li>Bảo hiểm sức khỏe.</li>
        </ul>
    </div>
</div>
"""


class TestJobsGoCrawler(unittest.TestCase):
    def setUp(self):
        self.crawler = JobsGoCrawler(max_items=2)

    def test_parse_item_html(self):
        item = {
            "job_id": "test-job-123",
            "url": "https://jobsgo.vn/viec-lam/backend-python-engineer-123.html",
            "html": SAMPLE_JOB_HTML,
        }
        record = self.crawler.parse_item(item)
        self.assertIsNotNone(record)
        self.assertIsInstance(record, JobRecord)
        self.assertEqual(record.meta.source, "jobsgo")
        self.assertEqual(record.meta.source_job_id, "test-job-123")
        self.assertEqual(record.raw.title, "Backend Python Engineer")
        self.assertEqual(record.raw.company, "JobsGO Tech Solutions")
        self.assertEqual(record.raw.location_text, "Hồ Chí Minh")
        self.assertIn("Python", record.raw.requirements_list[0])
        self.assertIn("Lương thưởng tháng 13", record.raw.benefits_list[0])

    def test_two_phase_methods(self):
        self.assertTrue(hasattr(self.crawler, "discover_urls"))
        self.assertTrue(hasattr(self.crawler, "crawl_details"))


if __name__ == "__main__":
    unittest.main()
