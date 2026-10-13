# -*- coding: utf-8 -*-
"""Unit tests cho crawlers.preprocessing.eda.profiler."""

import unittest
from crawlers.preprocessing.eda.profiler import EDAProfiler


class TestEDAProfiler(unittest.TestCase):
    def test_analyze_field_status_missing_key(self):
        rec = {"title": "Python Dev"}
        self.assertEqual(EDAProfiler.analyze_field_status(rec, "company"), "missing_key")
        self.assertEqual(EDAProfiler.analyze_field_status(rec, "salary.salary_min"), "missing_key")

    def test_analyze_field_status_null(self):
        rec = {"salary": {"salary_min": None}, "title": None}
        self.assertEqual(EDAProfiler.analyze_field_status(rec, "title"), "null")
        self.assertEqual(EDAProfiler.analyze_field_status(rec, "salary.salary_min"), "null")

    def test_analyze_field_status_empty_string(self):
        rec = {"title": "   \n\t", "location_text": ""}
        self.assertEqual(EDAProfiler.analyze_field_status(rec, "title"), "empty_string")
        self.assertEqual(EDAProfiler.analyze_field_status(rec, "location_text"), "empty_string")

    def test_analyze_field_status_empty_list(self):
        rec = {"description_list": [], "tags": {"skills": []}}
        self.assertEqual(EDAProfiler.analyze_field_status(rec, "description_list"), "empty_list")
        self.assertEqual(EDAProfiler.analyze_field_status(rec, "tags.skills"), "empty_list")

    def test_analyze_field_status_empty_dict(self):
        rec = {"extra": {}, "salary": {}}
        self.assertEqual(EDAProfiler.analyze_field_status(rec, "extra"), "empty_dict")
        self.assertEqual(EDAProfiler.analyze_field_status(rec, "salary"), "empty_dict")


    def test_analyze_field_status_valid(self):
        rec = {
            "title": "Senior Frontend Developer",
            "description_list": ["Xây dựng UI", "Tối ưu React"],
            "salary": {"salary_min": 25000000},
            "tags": {"skills": ["React", "TypeScript"]},
        }
        self.assertEqual(EDAProfiler.analyze_field_status(rec, "title"), "valid")
        self.assertEqual(EDAProfiler.analyze_field_status(rec, "description_list"), "valid")
        self.assertEqual(EDAProfiler.analyze_field_status(rec, "salary.salary_min"), "valid")
        self.assertEqual(EDAProfiler.analyze_field_status(rec, "tags.skills"), "valid")

    def test_profile_empty_dataset(self):
        res = EDAProfiler.profile_dataset([])
        self.assertEqual(res["total_records"], 0)
        self.assertEqual(res["sources_distribution"], {})
        self.assertEqual(res["missingness_summary"], {})

    def test_profile_dataset_sources_and_uniqueness(self):
        records = [
            {
                "_meta": {
                    "unified_id": "topcv_001",
                    "source": "topcv",
                    "source_job_id": "001",
                    "url": "https://topcv.vn/1",
                },
                "title": "Backend Dev",
                "company": "VNG",
                "salary": {"salary_type": "RANGE", "salary_min": 10000000},
                "extra": {"experience": "1 năm", "education": "Đại học"},
            },
            {
                "_meta": {
                    "unified_id": "topcv_002",
                    "source": "topcv",
                    "source_job_id": "002",
                    "url": "https://topcv.vn/2",
                },
                "title": "Backend Dev",
                "company": "VNG",  # Cùng công ty + title để test duplicate estimate
                "salary": {"salary_type": "NEGOTIABLE"},
                "extra": {"experience": {"min": 2, "max": 4}},  # Dict heterogenous
            },
            {
                "_meta": {
                    "unified_id": "itviec_100",
                    "source": "itviec",
                    "source_job_id": "100",
                    "url": "https://itviec.com/100",
                },
                "title": "Frontend Dev",
                "company": "FPT",
                "salary": {"salary_type": "RANGE", "salary_min": 15000000},
                "extra": {"experience": None},
            },
        ]

        res = EDAProfiler.profile_dataset(records)
        self.assertEqual(res["total_records"], 3)

        # Nguồn
        sources = res["sources_distribution"]
        self.assertEqual(sources["topcv"]["count"], 2)
        self.assertAlmostEqual(sources["topcv"]["percentage"], 66.67, delta=0.01)
        self.assertEqual(sources["itviec"]["count"], 1)
        self.assertAlmostEqual(sources["itviec"]["percentage"], 33.33, delta=0.01)

        # Tính duy nhất
        uniq = res["uniqueness_summary"]
        self.assertEqual(uniq["unique_unified_ids"], 3)
        self.assertTrue(uniq["is_unified_id_strictly_unique"])
        # Có 1 cặp trùng (vng, backend dev)
        self.assertEqual(uniq["company_title_duplicates_estimate"], 1)

        # Dị biệt kiểu dữ liệu
        het = res["heterogeneous_types"]
        self.assertIn("str", het["extra_experience_types"])
        self.assertIn("dict", het["extra_experience_types"])
        self.assertIn("NoneType", het["extra_experience_types"])
        self.assertEqual(het["salary_types_distribution"]["RANGE"], 2)
        self.assertEqual(het["salary_types_distribution"]["NEGOTIABLE"], 1)

    def test_missingness_summary_breakdown(self):
        records = [
            {"title": "Dev 1", "salary": {"salary_min": 10000000}, "description_list": ["Mô tả"]},
            {"title": "Dev 2", "salary": {"salary_min": None}, "description_list": []},
            {"title": "", "salary": {}, "description_list": None},
        ]
        res = EDAProfiler.profile_dataset(records)
        miss = res["missingness_summary"]

        # Title: 2 valid, 1 empty_string
        self.assertEqual(miss["title"]["valid_count"], 2)
        self.assertEqual(miss["title"]["breakdown"]["empty_string"], 1)

        # salary_min: 1 valid, 1 null, 1 missing_key (salary dict không có key salary_min)
        self.assertEqual(miss["salary_min"]["valid_count"], 1)
        self.assertEqual(miss["salary_min"]["breakdown"]["null"], 1)
        self.assertEqual(miss["salary_min"]["breakdown"]["missing_key"], 1)

        # description_list: 1 valid, 1 empty_list, 1 null
        self.assertEqual(miss["description_list"]["valid_count"], 1)
        self.assertEqual(miss["description_list"]["breakdown"]["empty_list"], 1)
        self.assertEqual(miss["description_list"]["breakdown"]["null"], 1)

    def test_profile_dataset_with_unified_id_collisions(self):
        records = [
            {"_meta": {"unified_id": "dup_01", "source": "src1"}, "title": "Dev 1", "company": "C1"},
            {"_meta": {"unified_id": "dup_01", "source": "src1"}, "title": "Dev 2", "company": "C2"},
            {"_meta": {"unified_id": "dup_01", "source": "src1"}, "title": "Dev 3", "company": "C3"},
            {"_meta": {"unified_id": "dup_02", "source": "src2"}, "title": "Dev 4", "company": "C4"},
            {"_meta": {"unified_id": "dup_02", "source": "src2"}, "title": "Dev 5", "company": "C5"},
            {"_meta": {"unified_id": "uniq_03", "source": "src3"}, "title": "Dev 6", "company": "C6"},
        ]
        res = EDAProfiler.profile_dataset(records)
        uniq = res["uniqueness_summary"]

        self.assertEqual(uniq["total_records"], 6)
        self.assertEqual(uniq["unique_unified_ids"], 3)  # dup_01, dup_02, uniq_03
        self.assertFalse(uniq["is_unified_id_strictly_unique"])

        # 2 nhóm bị xung đột: dup_01 và dup_02
        self.assertEqual(uniq["colliding_id_count"], 2)
        # 5 bản ghi thuộc 2 nhóm xung đột này (3 + 2)
        self.assertEqual(uniq["records_in_colliding_ids"], 5)
        # Số bản ghi dư vượt mức: (3 - 1) + (2 - 1) = 3
        self.assertEqual(uniq["excess_records_in_colliding_ids"], 3)
        self.assertEqual(uniq["unified_id_collision_count"], 3)

    def test_source_field_completeness_calculation(self):
        records = [
            {"_meta": {"source": "topcv"}, "title": "Dev 1", "salary": {"salary_min": 10000000}},
            {"_meta": {"source": "topcv"}, "title": "Dev 2", "salary": {}},
            {"_meta": {"source": "itviec"}, "title": "Dev 3", "salary": {"salary_min": 20000000}},
        ]
        res = EDAProfiler.profile_dataset(records)
        comp = res["source_field_completeness"]

        self.assertIn("topcv", comp)
        self.assertIn("itviec", comp)
        # topcv có 2 bài, cả 2 đều có title (100%), nhưng chỉ 1 có salary_min (50%)
        self.assertEqual(comp["topcv"]["title"], 100.0)
        self.assertEqual(comp["topcv"]["salary_min"], 50.0)
        # itviec có 1 bài, có cả title và salary_min (100%)
        self.assertEqual(comp["itviec"]["title"], 100.0)
        self.assertEqual(comp["itviec"]["salary_min"], 100.0)

    def test_profile_dataset_missing_and_empty_unified_id(self):
        records = [
            {"_meta": {"unified_id": "valid_01", "source": "src1"}, "title": "Dev 1"},
            {"_meta": {"unified_id": None, "source": "src1"}, "title": "Dev 2"},
            {"_meta": {"unified_id": "", "source": "src1"}, "title": "Dev 3"},
            {"_meta": {"unified_id": "   \n\t", "source": "src1"}, "title": "Dev 4"},
            {"_meta": {"source": "src1"}, "title": "Dev 5"},  # missing key unified_id
        ]
        res = EDAProfiler.profile_dataset(records)
        uniq = res["uniqueness_summary"]

        self.assertEqual(uniq["total_records"], 5)
        self.assertEqual(uniq["records_with_valid_unified_id"], 1)
        self.assertEqual(uniq["missing_or_empty_unified_id_count"], 4)
        self.assertEqual(uniq["unique_unified_ids"], 1)

        # Tuyệt đối không coi các ID rỗng/None là trùng lặp với nhau
        self.assertEqual(uniq["colliding_id_count"], 0)
        self.assertEqual(uniq["records_in_colliding_ids"], 0)
        self.assertEqual(uniq["excess_records_in_colliding_ids"], 0)
        self.assertFalse(uniq["is_unified_id_strictly_unique"])  # False vì có ID bị thiếu

    def test_company_title_normalization_consistency_with_risk_detector(self):
        """Regression test cho Finding 04 (P3): dam bao EDAProfiler va RiskDetector chuan hoa nhat quan."""
        from crawlers.preprocessing.eda.risk_detector import RiskDetector

        # 1. 'FPT Software' va 'FPT   Software' duoc chuan hoa giong het nhau
        self.assertEqual(EDAProfiler.normalize_text("FPT Software"), "fpt software")
        self.assertEqual(EDAProfiler.normalize_text("FPT   Software"), "fpt software")
        self.assertEqual(EDAProfiler.normalize_text("FPT Software"), RiskDetector.normalize_text("FPT   Software"))

        # 2. Khac biet chu hoa/thuong va khoang trang dau/cuoi
        self.assertEqual(
            EDAProfiler.normalize_text("  FPT Software  \n\t"),
            RiskDetector.normalize_text("fpt software"),
        )

        # 3. Dau tieng Viet duoc bao toan, khong bi xoa dau
        self.assertEqual(
            EDAProfiler.normalize_text("Lập Trình   Viên Python"),
            "lập trình viên python",
        )

        # 4. Cac ten thuc su khac nhau khong bi gop
        self.assertNotEqual(
            EDAProfiler.normalize_text("FPT Software"),
            EDAProfiler.normalize_text("FPT Telecom"),
        )

        # 5. profile_dataset nhan dien dung nhom trung lap khi co khoang trang kep
        records = [
            {"_meta": {"unified_id": "1", "source": "src"}, "company": "FPT   Software", "title": "Java Developer"},
            {"_meta": {"unified_id": "2", "source": "src"}, "company": "FPT Software", "title": "Java   Developer"},
        ]
        res = EDAProfiler.profile_dataset(records)
        uniq = res["uniqueness_summary"]
        self.assertEqual(uniq["company_title_duplicate_groups_count"], 1)
        self.assertEqual(uniq["company_title_records_in_groups"], 2)
        self.assertEqual(uniq["company_title_excess_records"], 1)


if __name__ == "__main__":
    unittest.main()
