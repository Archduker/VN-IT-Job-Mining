# -*- coding: utf-8 -*-
"""Unit tests for VietnamWorks crawler (Schema v1 compliance)."""

import json
import unittest

from crawlers.sources.vietnamworks.crawler import VietnamWorksCrawler
from crawlers.common.schema import JobRecord


SAMPLE_JOB_PAYLOAD = {
    "jobId": 1892837,
    "jobTitle": "Senior Software Engineer (Java/Python)",
    "jobUrl": "https://www.vietnamworks.com/job-1892837-jv",
    "companyName": "Tech Innovation Global",
    "prettySalary": "1,500 - 2,500 USD",
    "salaryMin": 1500,
    "salaryMax": 2500,
    "salaryCurrency": "USD",
    "jobDescription": "<p>We are seeking a talented Senior Software Engineer.</p><ul><li>Develop microservices architectures.</li><li>Collaborate with international teams.</li></ul>",
    "jobRequirement": "<ul><li>At least 4 years experience in Java or Python.</li><li>Experience with AWS and Docker.</li></ul>",
    "skills": [
        {"skillName": "Java"},
        {"skillName": "Python"},
        {"skillName": "Microservices"},
    ],
    "benefits": [
        {"benefitNameVI": "Bảo hiểm sức khỏe", "benefitValue": "Gói cao cấp"},
        {"benefitNameVI": "Máy tính xách tay", "benefitValue": "MacBook Pro M3"},
    ],
    "locations": [{"cityName": "Hồ Chí Minh"}, {"cityName": "Hà Nội"}],
    "expiredOn": "2026-11-20T00:00:00Z",
    "approvedOn": "2026-10-10T12:00:00Z",
    "jobLevelVI": "Trưởng nhóm / Giám sát",
    "yearsOfExperience": 4,
    "typeWorkingId": 1,
}


class TestVietnamWorksCrawler(unittest.TestCase):
    def setUp(self):
        self.crawler = VietnamWorksCrawler(max_items=2)

    def test_parse_item_schema_v1(self):
        record = self.crawler.parse_item(SAMPLE_JOB_PAYLOAD)
        self.assertIsNotNone(record)
        self.assertIsInstance(record, JobRecord)

        # Meta
        self.assertEqual(record.meta.source, "vietnamworks")
        self.assertEqual(record.meta.source_job_id, "1892837")
        self.assertEqual(record.meta.language, "en")

        # Raw data
        raw = record.raw
        self.assertEqual(raw.title, "Senior Software Engineer (Java/Python)")
        self.assertEqual(raw.company, "Tech Innovation Global")

        # Salary parsing
        self.assertEqual(raw.salary.salary_min, 1500.0)
        self.assertEqual(raw.salary.salary_max, 2500.0)
        self.assertEqual(raw.salary.salary_currency, "USD")

        # Text lists without bullets
        self.assertGreater(len(raw.description_list), 0)
        self.assertFalse(raw.description_list[0].startswith("•"))
        self.assertIsNotNone(raw.requirements_list)
        self.assertFalse(raw.requirements_list[0].startswith("•"))
        self.assertIsNotNone(raw.benefits_list)

        # Tags
        self.assertIsNotNone(raw.tags.skills)
        self.assertIn("Java", raw.tags.skills)
        self.assertIsNotNone(raw.tags.benefits)
        self.assertIn("Bảo hiểm sức khỏe", raw.tags.benefits)
        self.assertIsNone(raw.tags.requirements)

        # Locations & metadata
        self.assertIn("Hồ Chí Minh", raw.location_text)
        self.assertEqual(raw.deadline_text, "2026-11-20T00:00:00Z")
        self.assertEqual(raw.seniority_text, "Trưởng nhóm / Giám sát")
        self.assertEqual(raw.extra["experience"], "4 năm kinh nghiệm")


if __name__ == "__main__":
    unittest.main()
