# -*- coding: utf-8 -*-
"""Test các helper của crawler: checkpoint, JSONL writer, build_record, dedup.

Không gọi mạng trong test (HttpClient chỉ được dùng ở test crawl Level 1 trở đi).
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import crawler  # noqa: E402
import parser as job_parser  # noqa: E402


class TestCheckpoint(unittest.TestCase):
    def test_roundtrip_and_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "checkpoint.json")
            # chưa có file → rỗng, không crash
            self.assertEqual(crawler.load_checkpoint(path),
                             {"seen_ids": [], "sources": {}, "updated_at": None})
            crawler.save_checkpoint(path, {"job-b", "job-a"})
            data = crawler.load_checkpoint(path)
            self.assertEqual(data["seen_ids"], ["job-a", "job-b"])  # sorted, ổn định
            self.assertTrue(data["updated_at"])

    def test_corrupt_checkpoint_not_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "checkpoint.json")
            with open(path, "w") as fh:
                fh.write("{not json")
            data = crawler.load_checkpoint(path)  # phải chạy tiếp từ đầu
            self.assertEqual(data["seen_ids"], [])

    def test_seen_filter_skips_old_jobs(self):
        """Chạy lại không cào lại tin đã có trong checkpoint."""
        seen = {"senior-backend-java-fpt-0123"}
        jobs = job_parser.parse_listing(
            '<div class="job-card" '
            'data-search--job-selection-job-slug-value="senior-backend-java-fpt-0123"></div>'
            '<div class="job-card" '
            'data-search--job-selection-job-slug-value="new-job-9999"></div>')
        new = [j for j in jobs if j["source_job_id"] not in seen]
        self.assertEqual([j["source_job_id"] for j in new], ["new-job-9999"])


class TestJsonlWriter(unittest.TestCase):
    def test_append_unicode_and_one_record_per_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            crawler.open_jsonl  # kiểm tra hàm tồn tại
            path = os.path.join(tmp, "batch_001.jsonl")
            rec = {"_meta": {"source": "itviec"},
                   "raw": {"title": "Kỹ sư iOS — TP. Hồ Chí Minh", "x": 1}}
            with open(path, "a", encoding="utf-8") as fh:
                crawler.write_record(fh, rec)
                crawler.write_record(fh, rec)
            with open(path, encoding="utf-8") as fh:
                lines = fh.read().splitlines()
            self.assertEqual(len(lines), 2)
            for line in lines:
                self.assertEqual(json.loads(line)["raw"]["title"],
                                 "Kỹ sư iOS — TP. Hồ Chí Minh")  # không bị escape \u
            self.assertNotIn("\\u", lines[0])

    def test_open_json_writes_json_array(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_data_dir = crawler.config.DATA_DIR
            crawler.config.DATA_DIR = os.path.join(tmp, "itviec")
            try:
                writer = crawler.open_json("2026-10-08", "2026-10-08_itviec_001")
                rec = {"_meta": {"source": "itviec"},
                       "raw": {"title": "Kỹ sư iOS — TP. Hồ Chí Minh", "x": 1}}
                crawler.write_record(writer, rec)
                writer.close()

                self.assertTrue(os.path.exists(writer.file_path))
                with open(writer.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.assertIsInstance(data, list)
                self.assertEqual(len(data), 1)
                self.assertEqual(data[0]["raw"]["title"], "Kỹ sư iOS — TP. Hồ Chí Minh")
            finally:
                crawler.config.DATA_DIR = old_data_dir


class TestBuildRecord(unittest.TestCase):
    def test_meta_follows_data_contract(self):
        raw = {"title": "A", "description_html": "<p>x</p>"}
        rec = crawler.build_record(raw, "https://itviec.com/viec-lam-it/abc-1",
                                   "abc-1", "2026-10-05_itviec_001")
        meta = rec["_meta"]
        self.assertEqual(meta["source"], "itviec")
        self.assertEqual(meta["source_job_id"], "abc-1")
        self.assertEqual(meta["dedup_key"], "itviec:abc-1")
        self.assertTrue(meta["crawled_at"].endswith("+07:00"))
        self.assertEqual(rec["raw"], raw)  # raw không bị sửa
        self.assertEqual(job_parser.validate_record(rec), [])

    def test_batch_id_format(self):
        self.assertEqual(crawler.make_batch_id("2026-10-05", 7),
                         "2026-10-05_itviec_007")


class TestListingUrlBuilding(unittest.TestCase):
    def test_page_1_has_no_query(self):
        self.assertEqual(crawler.listing_page_url("/viec-lam-it", 1),
                         "https://itviec.com/viec-lam-it")

    def test_page_n_keeps_page_param_after_normalize(self):
        url = crawler.listing_page_url("/viec-lam-it", 3)
        self.assertEqual(job_parser.normalize_url(url),
                         "https://itviec.com/viec-lam-it?page=3")


if __name__ == "__main__":
    unittest.main()
