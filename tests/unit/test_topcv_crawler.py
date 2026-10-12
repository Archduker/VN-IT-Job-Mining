# -*- coding: utf-8 -*-
"""Unit tests for TopCV crawler (Schema v1 / Data Contract compliance)."""

import unittest
from crawlers.sources.topcv.crawler import TopCVCrawler
from crawlers.common.schema import JobRecord


SAMPLE_TOPCV_HTML = """
<div class="job-detail">
    <h1 class="box-header-job__title">Senior Java Engineer (Spring Boot)</h1>
    <div class="company-name-label"><a>FPT Software</a></div>
    <div class="box-header-job__salary--title">30 - 50 triệu</div>
    <div class="box-applied-cv"><span class="date">31/12/2026</span></div>
    <div class="box-job-information-detail-item">
        <h2 class="box-job-information-detail-item__title--title">Mô tả công việc</h2>
        <div class="box-job-information-detail-item__content">
            <ul>
                <li>Phát triển hệ thống Microservices bằng Java Spring Boot</li>
                <li>Tối ưu truy vấn cơ sở dữ liệu Oracle và PostgreSQL</li>
            </ul>
        </div>
    </div>
    <div class="box-job-information-detail-item">
        <h2 class="box-job-information-detail-item__title--title">Yêu cầu ứng viên</h2>
        <div class="box-job-information-detail-item__content">
            <ul>
                <li>Tối thiểu 3 năm kinh nghiệm với Java Backend</li>
                <li>Hiểu biết về kiến trúc vi dịch vụ và Docker</li>
            </ul>
        </div>
    </div>
    <div class="box-job-information-detail-item">
        <h2 class="box-job-information-detail-item__title--title">Quyền lợi</h2>
        <div class="box-job-information-detail-item__content">
            <ul>
                <li>Lương tháng 13 và thưởng dự án định kỳ</li>
                <li>Gói bảo hiểm sức khỏe FPT Care cho nhân viên và gia đình</li>
            </ul>
        </div>
    </div>
    <div class="job-tags">
        <div class="job-tags__group">
            <span class="job-tags__group-name">Kỹ năng chuyên môn</span>
            <span class="item">Java</span>
            <span class="item">Spring Boot</span>
            <span class="item">Microservices</span>
        </div>
    </div>
    <div class="box-job-information-address-and-time-list__item">
        Địa điểm
        <div class="box-job-information-address-and-time-list__item--content">Hà Nội</div>
    </div>
</div>
"""


class TestTopCVCrawler(unittest.TestCase):
    def setUp(self):
        self.crawler = TopCVCrawler(max_items=2)

    def test_parse_item_schema_v1(self):
        raw_item = {
            "job_id": "1234567",
            "url": "https://www.topcv.vn/viec-lam/1234567.html",
            "html_content": SAMPLE_TOPCV_HTML,
        }
        record = self.crawler.parse_item(raw_item)
        self.assertIsNotNone(record)
        self.assertIsInstance(record, JobRecord)

        # Meta
        self.assertEqual(record.meta.source, "topcv")
        self.assertEqual(record.meta.source_job_id, "1234567")
        self.assertEqual(record.meta.language, "vi")

        # Raw
        raw = record.raw
        self.assertEqual(raw.title, "Senior Java Engineer (Spring Boot)")
        self.assertEqual(raw.company, "FPT Software")
        self.assertEqual(raw.salary.salary_min, 30.0)
        self.assertEqual(raw.salary.salary_max, 50.0)
        self.assertEqual(raw.salary.salary_currency, "VND")
        self.assertEqual(raw.location_text, "Hà Nội")
        self.assertEqual(raw.deadline_text, "31/12/2026")
        self.assertEqual(len(raw.description_list), 2)
        self.assertEqual(len(raw.requirements_list), 2)
        self.assertEqual(len(raw.benefits_list), 2)

        # Tags
        self.assertIsNone(raw.tags.benefits)
        self.assertIn("Java", raw.tags.skills)
        self.assertIn("Spring Boot", raw.tags.skills)
