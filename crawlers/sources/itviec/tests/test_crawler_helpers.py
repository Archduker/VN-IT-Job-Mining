# -*- coding: utf-8 -*-
"""Test helper và kiến trúc ItviecCrawler (BaseCrawler v0.5.0).

Không gọi mạng trong test (HttpClient chỉ dùng ở integration test).
Chạy:  python -m pytest crawlers/sources/itviec/tests/test_crawler_helpers.py -q
"""

import json
import os
import sys
import tempfile
import unittest

_itviec_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_repo_root = os.path.abspath(os.path.join(_itviec_dir, "..", "..", ".."))
sys.path.insert(0, _repo_root)
sys.path.insert(0, _itviec_dir)

from crawlers.sources.itviec.crawler import ItviecCrawler  # noqa: E402
import parser as job_parser  # noqa: E402


class TestItviecCrawlerInit(unittest.TestCase):
    """ItviecCrawler khởi tạo đúng qua BaseCrawler."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.crawler = ItviecCrawler(
            checkpoint_dir=os.path.join(self.tmp, "ckpt"),
            output_dir=os.path.join(self.tmp, "out"),
            max_items=5,
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_source_name(self):
        self.assertEqual(self.crawler.source_name, "itviec")

    def test_crawler_version(self):
        self.assertEqual(self.crawler.crawler_version, "0.5.0")

    def test_max_items(self):
        self.assertEqual(self.crawler.max_items, 5)

    def test_batch_id_format(self):
        """batch_id do BaseCrawler sinh: YYYY-MM-DD_itviec_NNN."""
        self.assertRegex(self.crawler.batch_id,
                         r"\d{4}-\d{2}-\d{2}_itviec_\d{3}")

    def test_has_checkpoint(self):
        self.assertIsNotNone(self.crawler.checkpoint)

    def test_has_writer(self):
        self.assertIsNotNone(self.crawler.writer)


class TestListingUrlBuilding(unittest.TestCase):
    def test_page_1_has_no_query(self):
        self.assertEqual(
            ItviecCrawler._listing_url("/viec-lam-it", 1),
            "https://itviec.com/viec-lam-it")

    def test_page_n_has_page_param(self):
        url = ItviecCrawler._listing_url("/viec-lam-it", 3)
        self.assertEqual(url, "https://itviec.com/viec-lam-it?page=3")

    def test_page_param_survives_normalize(self):
        url = ItviecCrawler._listing_url("/viec-lam-it", 3)
        self.assertEqual(
            job_parser.normalize_url(url),
            "https://itviec.com/viec-lam-it?page=3")


class TestListingDedup(unittest.TestCase):
    """Checkpoint khử trùng tin đã thấy trên listing."""

    def test_seen_filter_skips_old_jobs(self):
        seen = {"senior-backend-java-fpt-0123"}
        jobs = job_parser.parse_listing(
            '<div class="job-card" '
            'data-search--job-selection-job-slug-value="senior-backend-java-fpt-0123"></div>'
            '<div class="job-card" '
            'data-search--job-selection-job-slug-value="new-job-9999"></div>'
        )
        new = [j for j in jobs if j["source_job_id"] not in seen]
        self.assertEqual([j["source_job_id"] for j in new], ["new-job-9999"])


class TestParseItem(unittest.TestCase):
    """parse_item() với HTML mẫu (không gọi mạng)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.crawler = ItviecCrawler(
            checkpoint_dir=os.path.join(self.tmp, "ckpt"),
            output_dir=os.path.join(self.tmp, "out"),
            max_items=5,
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_parse_item_returns_job_record(self):
        import json as _json
        jp = {
            "@context": "http://schema.org", "@type": "JobPosting",
            "title": "Python Developer",
            "datePosted": "2026-10-01",
            "validThrough": "2026-10-30",
            "skills": "Python, Django",
            "description": "<p>Xây dựng hệ thống backend bằng Python.</p>",
            "employmentType": "FULL_TIME",
            "hiringOrganization": {
                "@type": "Organization", "name": "Tech Corp"},
            "jobLocation": [],
        }
        html = (
            "<html><body>"
            f"<script type='application/ld+json'>{_json.dumps(jp)}</script>"
            "<h1>Python Developer</h1>"
            "</body></html>"
        )
        item = {
            "url": "https://itviec.com/viec-lam-it/python-dev-001",
            "source_job_id": "python-dev-001",
            "html": html,
        }
        record = self.crawler.parse_item(item)

        self.assertIsNotNone(record)
        self.assertEqual(record.meta.source, "itviec")
        self.assertEqual(record.meta.source_job_id, "python-dev-001")
        self.assertEqual(record.meta.crawler_version, "0.5.0")
        self.assertEqual(record.meta.language, "vi")
        self.assertEqual(record.raw.title, "Python Developer")
        self.assertEqual(record.raw.company, "Tech Corp")
        self.assertIsInstance(record.raw.description_list, list)
        self.assertTrue(len(record.raw.description_list) > 0)

    def test_parse_item_salary_is_nested(self):
        """Salary trong record là object lồng, không phẳng ở root."""
        import json as _json
        jp = {
            "@type": "JobPosting",
            "title": "Dev",
            "description": "<p>Làm việc với Python.</p>",
            "hiringOrganization": {"name": "ACME"},
        }
        html = (
            "<html><body>"
            f"<script type='application/ld+json'>{_json.dumps(jp)}</script>"
            "<h1>Dev</h1>"
            '<div class="salary">Thương lượng</div>'
            "</body></html>"
        )
        item = {
            "url": "https://itviec.com/viec-lam-it/dev-002",
            "source_job_id": "dev-002",
            "html": html,
        }
        record = self.crawler.parse_item(item)
        self.assertIsNotNone(record)
        # salary là object lồng
        self.assertIsNotNone(record.raw.salary)
        self.assertTrue(record.raw.salary.is_negotiable)
        # KHÔNG có salary_min phẳng ở root raw
        raw_dict = record.raw.model_dump()
        self.assertNotIn("salary_min", raw_dict)


if __name__ == "__main__":
    unittest.main()
