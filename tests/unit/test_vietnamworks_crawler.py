# -*- coding: utf-8 -*-
"""Unit tests for VietnamWorks crawler (Schema v1 compliance)."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from crawlers.sources.vietnamworks.crawler import (
    VietnamWorksCrawler,
    extract_raw_envelope_from_html,
    is_it_job,
)
from crawlers.common.schema import JobRecord, RawJobEnvelope


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
        assert record is not None
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

    def test_fetch_items_preserves_original_payload_for_checkpointed_jobs(self):
        raw_payload = {**SAMPLE_JOB_PAYLOAD, "unmappedApiField": {"keep": [1, 2]}}
        second_payload = {
            **SAMPLE_JOB_PAYLOAD,
            "jobId": 1892838,
            "jobTitle": "Backend Developer",
            "unmappedApiField": {"keep": [3, 4]},
        }
        http_client = Mock()
        http_client.post.return_value.json.return_value = {
            "data": [raw_payload, second_payload]
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            crawler = VietnamWorksCrawler(
                output_dir=temp_dir,
                checkpoint_dir=str(Path(temp_dir) / "checkpoint"),
                max_items=1,
                http_client=http_client,
                queries=["backend"],
            )
            crawler.checkpoint.mark_seen(str(raw_payload["jobId"]))

            self.assertEqual(list(crawler.fetch_items()), [second_payload])
            self.assertEqual(len(crawler.raw_payload_files), 1)

            saved_records = json.loads(
                crawler.raw_payload_files[0].read_text(encoding="utf-8")
            )
            self.assertEqual(len(saved_records), 2)
            by_id = {record["metadata"]["job_id"]: record for record in saved_records}
            self.assertEqual(by_id[str(raw_payload["jobId"])]["raw_payload"], raw_payload)
            self.assertEqual(
                by_id[str(second_payload["jobId"])]["raw_payload"],
                second_payload,
            )

    def test_it_classifier_uses_industry_and_technical_signals(self):
        garment_qa = {
            "jobTitle": "QA in Garment Field for Office",
            "skills": [{"skillName": "Quality"}, {"skillName": "Garment Knowledge"}],
            "industriesV3": [{"industryV3NameVI": "Dệt may/May mặc/Giày dép"}],
        }
        it_product_manager = {
            "jobTitle": "Product Manager",
            "industriesV3": [{"industryV3NameVI": "Phần Mềm CNTT/Dịch vụ Phần mềm"}],
        }
        software_qa = {
            "jobTitle": "QA Automation Engineer",
            "skills": [{"skillName": "Selenium"}, {"skillName": "API Testing"}],
        }

        self.assertFalse(is_it_job(garment_qa))
        self.assertTrue(is_it_job(it_product_manager))
        self.assertTrue(is_it_job(software_qa))

    def test_fetch_items_filters_non_it_before_saving_raw_payload(self):
        garment_qa = {
            "jobId": 550649,
            "jobTitle": "QA in Garment Field for Office",
            "industriesV3": [{"industryV3NameVI": "Dệt may/May mặc/Giày dép"}],
            "skills": [{"skillName": "Garment Knowledge"}],
        }
        http_client = Mock()
        http_client.post.return_value.json.return_value = {"data": [garment_qa]}

        with tempfile.TemporaryDirectory() as temp_dir:
            crawler = VietnamWorksCrawler(
                output_dir=temp_dir,
                checkpoint_dir=str(Path(temp_dir) / "checkpoint"),
                max_items=1,
                http_client=http_client,
                queries=["QA automation"],
            )

            self.assertEqual(list(crawler.fetch_items()), [])
            self.assertEqual(crawler.filtered_non_it_count, 1)
            self.assertEqual(crawler.raw_payload_files, [])

    def test_extract_raw_envelope_from_html(self):
        sample_html = """
        <div class="job-details-container">
          <h1 class="job-title">Senior Software Engineer (Java/python/Go)</h1>
          <div class="company-name">VINSMART FUTURE</div>
          <div class="salary">Thương lượng</div>
          <div class="description"><p>Backend services</p></div>
          <div class="requirements"><ul><li>4 years experience</li></ul></div>
        </div>
        """
        envelope = extract_raw_envelope_from_html(
            sample_html,
            job_id="2109463",
            url="https://www.vietnamworks.com/job-2109463-jv",
        )
        self.assertIsInstance(envelope, RawJobEnvelope)
        self.assertEqual(envelope.metadata["source"], "vietnamworks")
        self.assertEqual(envelope.metadata["crawler_version"], "2.0.0")
        self.assertEqual(envelope.raw_payload["job-title"], "Senior Software Engineer (Java/python/Go)")
        self.assertEqual(envelope.raw_payload["salary"], "Thương lượng")
        self.assertIn("job-details-container", envelope.raw_payload)

    def test_crawler_parse_raw_envelope(self):
        envelope = self.crawler.parse_raw_envelope(SAMPLE_JOB_PAYLOAD)
        self.assertIsInstance(envelope, RawJobEnvelope)
        self.assertEqual(envelope.metadata["source"], "vietnamworks")
        self.assertEqual(envelope.metadata["source_job_id"], "1892837")
        self.assertEqual(envelope.raw_payload["jobTitle"], "Senior Software Engineer (Java/Python)")


if __name__ == "__main__":
    unittest.main()
