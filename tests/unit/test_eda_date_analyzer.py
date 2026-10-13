# -*- coding: utf-8 -*-
"""Unit tests cho crawlers.preprocessing.eda.date_analyzer."""

import json
import unittest
from crawlers.preprocessing.eda.date_analyzer import DateAnalyzer


class TestDateAnalyzer(unittest.TestCase):
    def test_empty_dataset(self):
        res = DateAnalyzer.analyze([])
        self.assertEqual(res["total_analyzed"], 0)
        self.assertEqual(res["job_duration_analysis"]["valid_duration_count"], 0)
        self.assertEqual(res["temporal_anomalies"]["count"], 0)

    def test_classify_date_string(self):
        self.assertEqual(DateAnalyzer.classify_date_string(None), "EMPTY")
        self.assertEqual(DateAnalyzer.classify_date_string(""), "EMPTY")
        self.assertEqual(DateAnalyzer.classify_date_string("   \n\t"), "EMPTY")

        # ISO
        self.assertEqual(DateAnalyzer.classify_date_string("2026-10-12T10:00:00Z"), "ISO_DATETIME")
        self.assertEqual(DateAnalyzer.classify_date_string("2026-10-12 12:49:22.189334"), "ISO_DATETIME")

        # Chuẩn YMD & DMY
        self.assertEqual(DateAnalyzer.classify_date_string("2026-10-12"), "STANDARD_DATE")
        self.assertEqual(DateAnalyzer.classify_date_string("12/10/2026"), "STANDARD_DATE")
        self.assertEqual(DateAnalyzer.classify_date_string("12-10-2026"), "STANDARD_DATE")

        # Chuỗi tương đối
        self.assertEqual(DateAnalyzer.classify_date_string("3 ngày trước"), "RELATIVE_TEXT")
        self.assertEqual(DateAnalyzer.classify_date_string("1 tuần trước"), "RELATIVE_TEXT")
        self.assertEqual(DateAnalyzer.classify_date_string("hôm qua"), "RELATIVE_TEXT")
        self.assertEqual(DateAnalyzer.classify_date_string("2 hours ago"), "RELATIVE_TEXT")

        # Chuỗi văn bản tự do
        self.assertEqual(DateAnalyzer.classify_date_string("Tuyển gấp đi làm ngay"), "FREE_TEXT")
        self.assertEqual(DateAnalyzer.classify_date_string("Hết hạn khi đủ ứng viên"), "FREE_TEXT")

    def test_resolve_datetime_exact(self):
        dt, is_est, status = DateAnalyzer.resolve_datetime("2026-10-10")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 10)
        self.assertEqual(dt.day, 10)
        self.assertFalse(is_est)
        self.assertEqual(status, "RESOLVED_EXACT")

        # Định dạng DD/MM/YYYY
        dt_dmy, is_est_dmy, status_dmy = DateAnalyzer.resolve_datetime("15/10/2026")
        self.assertIsNotNone(dt_dmy)
        self.assertEqual(dt_dmy.day, 15)
        self.assertEqual(dt_dmy.month, 10)
        self.assertEqual(status_dmy, "RESOLVED_EXACT")

    def test_resolve_datetime_relative_with_reference(self):
        ref_crawl = "2026-10-12T12:00:00Z"

        # 3 ngày trước so với 12/10 -> ước tính là 09/10
        dt, is_est, status = DateAnalyzer.resolve_datetime("3 ngày trước", reference_crawled_at=ref_crawl)
        self.assertIsNotNone(dt)
        self.assertTrue(is_est)
        self.assertEqual(status, "RESOLVED_ESTIMATED")
        self.assertEqual(dt.day, 9)
        self.assertEqual(dt.month, 10)

        # Hôm qua -> 11/10
        dt_y, is_est_y, status_y = DateAnalyzer.resolve_datetime("hôm qua", reference_crawled_at=ref_crawl)
        self.assertIsNotNone(dt_y)
        self.assertTrue(is_est_y)
        self.assertEqual(dt_y.day, 11)

    def test_resolve_datetime_relative_without_reference(self):
        # Không có mốc tham chiếu crawled_at -> Trả về unresolvable, KHÔNG tự đoán qua datetime.now()
        dt, is_est, status = DateAnalyzer.resolve_datetime("3 ngày trước", reference_crawled_at=None)
        self.assertIsNone(dt)
        self.assertFalse(is_est)
        self.assertEqual(status, "UNRESOLVABLE_RELATIVE")

    def test_job_duration_calculation(self):
        records = [
            {
                "_meta": {"source": "topcv"},
                "posted_date_text": "2026-10-01",
                "deadline_text": "2026-10-31",  # 30 ngày
            },
            {
                "_meta": {"source": "topcv"},
                "posted_date_text": "2026-10-05",
                "deadline_text": "2026-10-15",  # 10 ngày
            },
            {
                "_meta": {"source": "topcv"},
                "posted_date_text": "2026-10-10",
                "deadline_text": None,  # Không tính duration
            },
        ]
        res = DateAnalyzer.analyze(records)
        dur = res["job_duration_analysis"]

        self.assertEqual(dur["valid_duration_count"], 2)
        self.assertEqual(dur["min_days"], 10)
        self.assertEqual(dur["max_days"], 30)
        self.assertEqual(dur["median_days"], 30)
        self.assertEqual(dur["mean_days"], 20.0)

        # Kiểm tra phân biệt rõ exact, estimated, unresolvable
        p_sum = res["posted_date_summary"]
        self.assertEqual(p_sum["exact_count"], 3)
        self.assertEqual(p_sum["estimated_count"], 0)
        self.assertEqual(p_sum["unresolvable_count"], 0)

        d_sum = res["deadline_summary"]
        self.assertEqual(d_sum["exact_count"], 2)
        self.assertEqual(d_sum["estimated_count"], 0)
        self.assertEqual(d_sum["unresolvable_count"], 1)  # Bản ghi thứ 3 có deadline là None


    def test_temporal_anomalies_flagging(self):
        records = [
            # 1. Hạn nộp sớm hơn ngày đăng
            {
                "_meta": {"unified_id": "anom_01", "source": "vietnamworks"},
                "posted_date_text": "2026-10-20",
                "deadline_text": "2026-10-10",
            },
            # 2. Ngày đăng trong tương lai so với crawl (crawl 12/10 nhưng posted 25/10)
            {
                "_meta": {"unified_id": "anom_02", "source": "topdev", "crawled_at": "2026-10-12T00:00:00Z"},
                "posted_date_text": "2026-10-25",
                "deadline_text": "2026-11-25",
            },
            # 3. Bản ghi bình thường
            {
                "_meta": {"unified_id": "valid_03", "source": "itviec", "crawled_at": "2026-10-12T00:00:00Z"},
                "posted_date_text": "2026-10-10",
                "deadline_text": "2026-11-10",
            },
        ]
        res = DateAnalyzer.analyze(records)
        anomalies = res["temporal_anomalies"]

        self.assertEqual(anomalies["count"], 2)
        types = [a["anomaly_type"] for a in anomalies["anomalies"]]
        self.assertIn("DEADLINE_BEFORE_POSTED", types)
        self.assertIn("POSTED_IN_FUTURE", types)

    def test_json_serializability(self):
        records = [
            {
                "_meta": {"source": "topcv", "crawled_at": "2026-10-12T12:00:00Z"},
                "posted_date_text": "3 ngày trước",
                "deadline_text": "30/10/2026",
            }
        ]
        res = DateAnalyzer.analyze(records)
        json_str = json.dumps(res, ensure_ascii=False)
        self.assertIsInstance(json_str, str)

    def test_negative_duration_excluded_from_valid_duration_stats(self):
        """Regression test cho Finding 01 (P1): dam bao delta_days < 0 khong bi dua vao valid_duration_count."""
        records = [
            # 1. Hạn nộp sớm hơn ngày đăng 5 ngày (bất thường)
            {
                "_meta": {"unified_id": "anom_neg", "source": "careerviet"},
                "posted_date_text": "2026-10-15",
                "deadline_text": "2026-10-10",
            },
            # 2. Hạn nộp cùng ngày đăng (0 ngày - hợp lệ)
            {
                "_meta": {"unified_id": "same_day", "source": "careerviet"},
                "posted_date_text": "2026-10-10",
                "deadline_text": "2026-10-10",
            },
            # 3. Hạn nộp sau ngày đăng 20 ngày (hợp lệ)
            {
                "_meta": {"unified_id": "normal_job", "source": "careerviet"},
                "posted_date_text": "2026-10-10",
                "deadline_text": "2026-10-30",
            },
        ]
        res = DateAnalyzer.analyze(records)
        dur = res["job_duration_analysis"]
        anom = res["temporal_anomalies"]

        # valid_duration_count chi chua 2 ban ghi hop le (0 va 20 ngay)
        self.assertEqual(dur["valid_duration_count"], 2)
        self.assertEqual(dur["negative_duration_count"], 1)
        self.assertEqual(dur["min_days"], 0)   # Khong con gia tri -5
        self.assertEqual(dur["max_days"], 20)
        self.assertEqual(dur["median_days"], 20)

        # Ban ghi am phai duoc ghi nhan trong temporal_anomalies
        self.assertEqual(anom["count"], 1)
        self.assertEqual(anom["anomalies"][0]["anomaly_type"], "DEADLINE_BEFORE_POSTED")


if __name__ == "__main__":
    unittest.main()
