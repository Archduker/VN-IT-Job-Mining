# -*- coding: utf-8 -*-
"""Unit tests cho crawlers.preprocessing.eda.loader."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
import pandas as pd

from crawlers.preprocessing.eda.loader import (
    EDALoader,
    EDALoaderError,
    InvalidJSONStructureError,
)


class TestEDALoader(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_load_non_existent_file(self):
        non_existent = self.temp_dir / "does_not_exist.json"
        with self.assertRaises(FileNotFoundError):
            EDALoader.load_raw_records(non_existent)

    def test_load_empty_file_zero_bytes(self):
        empty_file = self.temp_dir / "empty.json"
        empty_file.write_text("", encoding="utf-8")
        with self.assertRaises(EDALoaderError):
            EDALoader.load_raw_records(empty_file)

    def test_load_empty_file_whitespace_only(self):
        whitespace_file = self.temp_dir / "whitespace.json"
        whitespace_file.write_text("   \n\t  ", encoding="utf-8")
        with self.assertRaises(EDALoaderError):
            EDALoader.load_raw_records(whitespace_file)

    def test_load_malformed_syntax_json(self):
        bad_json = self.temp_dir / "malformed.json"
        bad_json.write_text("[{'key': 'single_quote_invalid'}]", encoding="utf-8")
        with self.assertRaises(json.JSONDecodeError):
            EDALoader.load_raw_records(bad_json)

    def test_load_non_array_json_dict(self):
        dict_file = self.temp_dir / "dict.json"
        dict_file.write_text('{"title": "Software Engineer"}', encoding="utf-8")
        with self.assertRaises(InvalidJSONStructureError):
            EDALoader.load_raw_records(dict_file)

    def test_load_valid_records_with_vietnamese(self):
        valid_file = self.temp_dir / "valid.json"
        sample_data = [
            {
                "_meta": {
                    "unified_id": "topcv_123",
                    "source": "topcv",
                    "source_job_id": "123",
                    "url": "https://topcv.vn/job/123",
                    "crawled_at": "2026-10-12T10:00:00Z",
                    "language": "vi",
                },
                "title": "Lập trình viên Backend Python (Lương cao)",
                "company": "Công ty Cổ phần Công nghệ ABC",
                "salary": {
                    "salary_min": 15000000.0,
                    "salary_max": 25000000.0,
                    "salary_currency": "VND",
                    "salary_type": "RANGE",
                    "is_negotiable": False,
                    "has_commission": False,
                    "salary_raw_text": "15 - 25 triệu",
                },
                "description_list": ["Phát triển API microservices", "Tối ưu hóa CSDL MySQL"],
                "requirements_list": ["Ít nhất 2 năm kinh nghiệm Python"],
                "benefits_list": ["Bảo hiểm đầy đủ", "Thưởng tháng 13"],
                "tags": {
                    "skills": ["Python", "FastAPI", "MySQL"],
                    "requirements": None,
                    "benefits": None,
                },
                "locations": ["Hồ Chí Minh"],
                "location_text": "Quận 1, Hồ Chí Minh",
                "employment_type_text": "Toàn thời gian",
                "seniority_text": "Middle",
                "posted_date_text": "10/10/2026",
                "deadline_text": "30/10/2026",
                "extra": {"experience": "2 năm", "education": "Đại học"},
            }
        ]
        valid_file.write_text(json.dumps(sample_data, ensure_ascii=False, indent=2), encoding="utf-8")

        loaded = EDALoader.load_raw_records(valid_file)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["title"], "Lập trình viên Backend Python (Lương cao)")
        self.assertEqual(loaded[0]["company"], "Công ty Cổ phần Công nghệ ABC")

    def test_records_to_dataframe_flattening(self):
        records = [
            {
                "_meta": {"unified_id": "itviec_456", "source": "itviec"},
                "title": "Data Engineer",
                "company": "Tech Corp",
                "salary": {"salary_min": "20000000", "salary_max": "30000000"},
                "tags": {"skills": ["Spark", "Airflow"]},
                "extra": {"experience": {"min": 3}},
            }
        ]
        df = EDALoader.records_to_dataframe(records)
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.loc[0, "unified_id"], "itviec_456")
        self.assertEqual(df.loc[0, "source"], "itviec")
        self.assertEqual(df.loc[0, "title"], "Data Engineer")
        # Kiểm tra chuyển đổi kiểu số cho lương
        self.assertEqual(df.loc[0, "salary_min"], 20000000.0)
        self.assertEqual(df.loc[0, "salary_max"], 30000000.0)
        self.assertEqual(df.loc[0, "skills"], ["Spark", "Airflow"])
        self.assertEqual(df.loc[0, "extra"], {"experience": {"min": 3}})

    def test_records_to_dataframe_empty_list(self):
        df = EDALoader.records_to_dataframe([])
        self.assertIsInstance(df, pd.DataFrame)
        self.assertTrue(df.empty)

    def test_stream_records(self):
        file_path = self.temp_dir / "stream.json"
        data = [{"title": f"Job {i}"} for i in range(5)]
        file_path.write_text(json.dumps(data), encoding="utf-8")

        streamed = list(EDALoader.stream_records(file_path))
        self.assertEqual(len(streamed), 5)
        self.assertEqual(streamed[2]["title"], "Job 2")

    def test_load_records_with_malformed_elements(self):
        file_path = self.temp_dir / "malformed_elements.json"
        data = [
            {"title": "Valid Job 1"},
            None,
            12345,
            "just_a_string_not_dict",
            {"title": "Valid Job 2"},
        ]
        file_path.write_text(json.dumps(data), encoding="utf-8")

        # 1. load_raw_records lọc an toàn và bảo toàn thứ tự
        recs = EDALoader.load_raw_records(file_path)
        self.assertEqual(len(recs), 2)
        self.assertEqual(recs[0]["title"], "Valid Job 1")
        self.assertEqual(recs[1]["title"], "Valid Job 2")

        # 2. load_raw_records_with_report ghi nhận chi tiết không bỏ sót
        valid_recs, report = EDALoader.load_raw_records_with_report(file_path)
        self.assertEqual(len(valid_recs), 2)
        self.assertEqual(report["total_raw_elements"], 5)
        self.assertEqual(report["valid_record_count"], 2)
        self.assertEqual(report["invalid_element_count"], 3)
        self.assertEqual(len(report["invalid_elements"]), 3)
        self.assertEqual(report["invalid_elements"][0]["index"], 1)
        self.assertEqual(report["invalid_elements"][0]["element_type"], "NoneType")
        self.assertEqual(report["invalid_elements"][1]["index"], 2)
        self.assertEqual(report["invalid_elements"][1]["element_type"], "int")
        self.assertEqual(report["invalid_elements"][2]["index"], 3)
        self.assertEqual(report["invalid_elements"][2]["element_type"], "str")

    def test_load_dataframe_helper(self):
        file_path = self.temp_dir / "df_helper.json"
        data = [{"_meta": {"unified_id": "test_1"}, "title": "Software Engineer"}]
        file_path.write_text(json.dumps(data), encoding="utf-8")

        df = EDALoader.load_dataframe(file_path)
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.loc[0, "title"], "Software Engineer")

    def test_type_hints_resolution_for_load_raw_records_with_report(self):
        """Regression test cho Finding 02 (P2): dam bao typing.get_type_hints khong loi NameError Tuple."""
        import typing
        hints = typing.get_type_hints(EDALoader.load_raw_records_with_report)
        self.assertIn("return", hints)
        self.assertIn("file_path", hints)


if __name__ == "__main__":
    unittest.main()
