# -*- coding: utf-8 -*-
"""Unit tests for JobsGO crawler."""

import os
from pathlib import Path
import unittest

from crawlers.sources.jobsgo.crawler import JobsGoCrawler, build_raw_envelope
from crawlers.common.schema import RawJobEnvelope

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLE_HTML_PATH = REPO_ROOT / "crawlers" / "sources" / "jobsgo" / ".html"


class TestJobsGoCrawler(unittest.TestCase):
    def setUp(self):
        self.crawler = JobsGoCrawler(max_items=2)
        if SAMPLE_HTML_PATH.is_file():
            self.real_html = SAMPLE_HTML_PATH.read_text(encoding="utf-8")
        else:
            self.real_html = "<html><body><h1 class='job-title'>Test Job</h1></body></html>"

    def test_parse_real_item_full_contract(self):
        """Kiểm tra trích xuất 100% trường dữ liệu theo neccessary.md từ file .html thực tế."""
        if not SAMPLE_HTML_PATH.is_file():
            self.skipTest(f"File mẫu {SAMPLE_HTML_PATH} đã được dọn dẹp khỏi repo")
        item = {
            "job_id": "29185806386",
            "url": "https://jobsgo.vn/viec-lam/ky-su-tich-hop-iot-29185806386.html",
            "html": self.real_html,
        }
        record = self.crawler.parse_item(item)
        self.assertIsNotNone(record)
        self.assertIsInstance(record, RawJobEnvelope)

        # 1. Kiểm tra Metadata chuẩn: duy nhất 1 trường content_hash, có language
        self.assertEqual(record.metadata["source"], "jobsgo")
        self.assertEqual(record.metadata["job_id"], "29185806386")
        self.assertIn("content_hash", record.metadata)
        self.assertEqual(len(record.metadata["content_hash"]), 64)  # SHA-256
        self.assertNotIn("canonical_hash", record.metadata, "Chỉ được có duy nhất 1 trường content_hash")
        self.assertNotIn("field_hashes", record.metadata, "Chỉ được có duy nhất 1 trường content_hash")
        self.assertEqual(record.metadata["language"], "vi")

        # 2. Kiểm tra Payload đối soát với neccessary.md
        payload = record.raw_payload
        self.assertEqual(
            payload["title"],
            "Kỹ Sư Tích Hợp IoT - Lương Cứng Từ 25 - 35 Triệu/Tháng + Thưởng - Đi Làm Ngay - Tại Hà Nội",
        )
        self.assertEqual(payload["salary_raw"], "35 - 40 triệu VNĐ")
        self.assertEqual(payload["location"], "Hà Nội")
        self.assertEqual(payload["experience"], "Trên 3 năm")
        self.assertEqual(payload["education"], "Đại Học trở lên")
        self.assertTrue(payload["deadline_raw"].startswith("04/11/2026"))
        self.assertTrue(payload["working_time"].startswith("Từ Thứ 2 đến Thứ 6"))
        self.assertTrue(len(payload["working_places"]) >= 1)
        self.assertIn("Võ Chí Công", payload["working_places"][0])

        # 3 khối bullets
        self.assertEqual(len(payload["description_bullets"]), 5)
        self.assertEqual(len(payload["requirements_bullets"]), 6)
        self.assertEqual(len(payload["benefits_bullets"]), 7)

        # Ngành nghề
        self.assertEqual(len(payload["occupations"]), 3)
        self.assertIn("Lập Trình - Phát Triển Phần Mềm", payload["occupations"])

        # Công ty
        self.assertEqual(payload["company"], "Công Ty Cổ Phần Fsi Việt Nam")
        self.assertIn("thiết bị điện", payload["company_field"])
        self.assertIn("Võ Chí Công", payload["company_address"])

        # Thông tin chung
        self.assertEqual(payload["general_info"]["employment_type"], "Toàn thời gian")
        self.assertEqual(payload["general_info"]["job_level"], "Nhân Viên/Chuyên Viên")
        self.assertEqual(payload["general_info"]["posted_date"], "05/10/2026")
        self.assertEqual(payload["general_info"]["hiring_quantity"], "2")

    def test_two_phase_methods(self):
        """Kiểm tra có đầy đủ hai pha discover_urls và crawl_details."""
        self.assertTrue(hasattr(self.crawler, "discover_urls"))
        self.assertTrue(hasattr(self.crawler, "crawl_details"))

    def test_nodriver_engine_initialization(self):
        """Kiểm tra khởi tạo crawler với engine nodriver chuẩn xác."""
        crawler = JobsGoCrawler(engine="nodriver")
        self.assertEqual(crawler.engine, "nodriver")
        self.assertTrue(hasattr(crawler, "_crawl_details_nodriver"))
        self.assertEqual(crawler.min_delay, 1.5)
        self.assertEqual(crawler.max_delay, 3.0)


if __name__ == "__main__":
    unittest.main()
