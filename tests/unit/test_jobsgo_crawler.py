# -*- coding: utf-8 -*-
"""Unit tests for JobsGO crawler (Schema v1 / Data Contract compliance)."""

import unittest
from crawlers.sources.jobsgo.crawler import JobsGOCrawler
from crawlers.common.schema import JobRecord


SAMPLE_JOBSGO_HTML = """
<div class="job-detail-card">
    <h1 class="job-title">Senior Python Engineer</h1>
    <div class="card-company"><h6>VNG Corporation</h6></div>
    <ul class="job-info-list">
        <li><span>Mức lương:</span> <strong>25 - 40 triệu VNĐ</strong></li>
        <li><span>Địa điểm:</span> <strong>Hồ Chí Minh</strong></li>
        <li><span>Kinh nghiệm:</span> <strong>3 - 5 năm</strong></li>
        <li><span>Bằng cấp:</span> <strong>Đại Học trở lên</strong></li>
    </ul>
    <p><span class="text-muted">Hạn nộp hồ sơ:</span> <strong>30/11/2026 (Còn 45 ngày)</strong></p>
    <div class="card-company">
        <span class="text-muted">Lĩnh vực:</span> <span class="fw-500">Công nghệ thông tin</span>
        <span class="text-muted">Địa chỉ:</span> <span class="fw-500">Z06 Đường số 13, Quận 7, TP.HCM</span>
    </div>
    <div class="job-detail-card">
        <h3 class="section-title">Mô tả công việc:</h3>
        <div><ul><li>Phát triển các dịch vụ backend hiệu năng cao bằng Python FastAPI</li><li>Thiết kế cơ sở dữ liệu PostgreSQL</li></ul></div>
        <h3 class="section-title">Yêu cầu công việc:</h3>
        <div><ul><li>Từ 3 năm kinh nghiệm Python</li><li>Nắm vững Docker, Kubernetes</li></ul></div>
        <h3 class="section-title">Quyền lợi được hưởng:</h3>
        <div><ul><li>Lương tháng 13 + thưởng hiệu quả công việc</li><li>Bảo hiểm sức khỏe cao cấp</li></ul></div>
        <div><strong>Kỹ năng:</strong> <strong><span>Python</span> , <span>FastAPI</span> , <span>PostgreSQL</span></strong></div>
        <div><strong>Ngành nghề:</strong> <strong>Lập Trình Viên</strong></div>
    </div>
</div>
"""


class TestJobsGOCrawler(unittest.TestCase):
    def setUp(self):
        self.crawler = JobsGOCrawler(max_items=2)

    def test_parse_item_schema_v1(self):
        raw_item = {
            "job_id": "99988877",
            "url": "https://jobsgo.vn/viec-lam/senior-python-engineer-99988877.html",
            "html_content": SAMPLE_JOBSGO_HTML,
        }
        record = self.crawler.parse_item(raw_item)
        self.assertIsNotNone(record)
        self.assertIsInstance(record, JobRecord)

        # Meta validation
        self.assertEqual(record.meta.source, "jobsgo")
        self.assertEqual(record.meta.source_job_id, "99988877")
        self.assertEqual(record.meta.language, "vi")

        # Raw validation
        raw = record.raw
        self.assertEqual(raw.title, "Senior Python Engineer")
        self.assertEqual(raw.company, "VNG Corporation")
        self.assertEqual(raw.salary.salary_min, 25.0)
        self.assertEqual(raw.salary.salary_max, 40.0)
        self.assertEqual(raw.salary.salary_currency, "VND")
        self.assertEqual(raw.location_text, "Hồ Chí Minh")
        self.assertEqual(raw.deadline_text, "30/11/2026")
        self.assertEqual(len(raw.description_list), 2)
        self.assertEqual(len(raw.requirements_list), 2)
        self.assertEqual(len(raw.benefits_list), 2)

        # Tags rule validation (benefits must be None if no badge container)
        self.assertIsNone(raw.tags.benefits)
        self.assertIn("Python", raw.tags.skills)
        self.assertIn("FastAPI", raw.tags.skills)

        # Extra validation
        self.assertEqual(raw.extra.get("education"), "Đại Học trở lên")
        self.assertEqual(raw.extra.get("experience"), "3 - 5 năm")
        self.assertEqual(raw.extra.get("industry"), "Công nghệ thông tin")
        self.assertEqual(raw.extra.get("company_address"), "Z06 Đường số 13, Quận 7, TP.HCM")
