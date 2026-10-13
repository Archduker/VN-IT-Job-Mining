# -*- coding: utf-8 -*-
"""Unit tests cho crawlers.preprocessing.eda.salary_analyzer."""

import json
import unittest
from typing import Any

from crawlers.preprocessing.eda.salary_analyzer import SalaryAnalyzer


class TestSalaryAnalyzer(unittest.TestCase):
    def test_empty_dataset(self):
        res = SalaryAnalyzer.analyze([])
        self.assertEqual(res["total_analyzed"], 0)
        self.assertEqual(res["negotiable_summary"]["count"], 0)
        self.assertEqual(res["numeric_salary_summary"]["count"], 0)
        self.assertEqual(res["stats_by_currency_and_period"], {})

    def test_negotiable_is_business_valid_null(self):
        records = [
            {"salary": {"salary_type": "NEGOTIABLE", "salary_min": None, "salary_max": None}},
            {"salary": {"salary_type": "NEGOTIABLE", "salary_raw_text": "Thoả thuận"}},
            {"salary": {"salary_type": "RANGE", "salary_min": 20000000, "salary_max": 30000000, "salary_currency": "VND"}},
        ]
        res = SalaryAnalyzer.analyze(records)
        self.assertEqual(res["total_analyzed"], 3)
        self.assertEqual(res["negotiable_summary"]["count"], 2)
        self.assertAlmostEqual(res["negotiable_summary"]["percentage"], 66.67, delta=0.01)
        self.assertTrue(res["negotiable_summary"]["is_business_valid_null"])
        self.assertEqual(res["numeric_salary_summary"]["count"], 1)

    def test_currency_separation_vnd_usd(self):
        records = [
            # 2 bài VND
            {
                "_meta": {"source": "topcv"},
                "salary": {
                    "salary_type": "RANGE",
                    "salary_min": 10000000,
                    "salary_max": 20000000,
                    "salary_currency": "VND",
                    "salary_raw_text": "10 - 20 triệu/tháng",
                },
            },
            {
                "_meta": {"source": "topcv"},
                "salary": {
                    "salary_type": "RANGE",
                    "salary_min": 20000000,
                    "salary_max": 30000000,
                    "salary_currency": "VND",
                    "salary_raw_text": "20 - 30 triệu/tháng",
                },
            },
            # 1 bài USD
            {
                "_meta": {"source": "itviec"},
                "salary": {
                    "salary_type": "RANGE",
                    "salary_min": 1000,
                    "salary_max": 2000,
                    "salary_currency": "USD",
                    "salary_raw_text": "1,000 - 2,000 USD/month",
                },
            },
        ]
        res = SalaryAnalyzer.analyze(records)
        buckets = res["stats_by_currency_and_period"]

        # Tuyệt đối tách biệt VND và USD thành 2 bucket khác nhau
        self.assertIn("VND_MONTHLY", buckets)
        self.assertIn("USD_MONTHLY", buckets)

        vnd_stats = buckets["VND_MONTHLY"]["salary_min_stats"]
        self.assertEqual(vnd_stats["count"], 2)
        self.assertEqual(vnd_stats["min"], 10000000.0)
        self.assertEqual(vnd_stats["max"], 20000000.0)
        self.assertEqual(vnd_stats["median"], 15000000.0)

        usd_stats = buckets["USD_MONTHLY"]["salary_min_stats"]
        self.assertEqual(usd_stats["count"], 1)
        self.assertEqual(usd_stats["min"], 1000.0)
        self.assertEqual(usd_stats["median"], 1000.0)

    def test_unknown_currency_and_period(self):
        records = [
            {
                "salary": {
                    "salary_type": "FIXED",
                    "salary_min": 15000000,
                    "salary_currency": None,  # Không có tiền tệ
                    "salary_raw_text": "15 triệu",  # Không rõ kỳ trả lương
                }
            }
        ]
        res = SalaryAnalyzer.analyze(records)
        buckets = res["stats_by_currency_and_period"]
        self.assertIn("UNKNOWN_CURRENCY_UNKNOWN", buckets)
        self.assertEqual(buckets["UNKNOWN_CURRENCY_UNKNOWN"]["currency"], "UNKNOWN_CURRENCY")
        self.assertEqual(buckets["UNKNOWN_CURRENCY_UNKNOWN"]["period"], "UNKNOWN")

    def test_auxiliary_flags(self):
        records = [
            {"salary": {"has_commission": True, "is_negotiable": False}},
            {"salary": {"has_commission": False, "is_negotiable": True}},
            {"salary": {}},  # missing cả 2 cờ -> None
        ]
        res = SalaryAnalyzer.analyze(records)
        comm = res["auxiliary_flags"]["has_commission"]
        nego = res["auxiliary_flags"]["is_negotiable"]

        self.assertEqual(comm["true_count"], 1)
        self.assertEqual(comm["false_count"], 1)
        self.assertEqual(comm["none_count"], 1)
        self.assertEqual(comm["missing_count"], 1)

        self.assertEqual(nego["true_count"], 1)
        self.assertEqual(nego["false_count"], 1)
        self.assertEqual(nego["none_count"], 1)
        self.assertEqual(nego["missing_count"], 1)

    def test_crash_safety_and_json_serializability(self):
        # Kiểm thử dữ liệu dị tật, chuỗi không convert được, phần tử rác
        records: list[Any] = [
            None,
            "not a dict",
            {"salary": None},
            {"salary": {"salary_min": "invalid_number_string", "salary_max": float("nan")}},
            {"salary": {"salary_min": 25000000, "salary_currency": "VND"}},
        ]
        res = SalaryAnalyzer.analyze(records)  # type: ignore[arg-type]  # Co y truyen du lieu bat thuong (None, str) de kiem thu crash-safety
        self.assertEqual(res["total_analyzed"], 5)
        # Chỉ có bản ghi cuối là có số hợp lệ
        self.assertEqual(res["numeric_salary_summary"]["count"], 1)

        # Đảm bảo kết quả tuần tự hóa JSON 100% không văng lỗi
        json_output = json.dumps(res, ensure_ascii=False)
        self.assertIsInstance(json_output, str)


if __name__ == "__main__":
    unittest.main()
