# -*- coding: utf-8 -*-
"""Unit tests cho crawlers.preprocessing.eda.risk_detector."""

import json
import unittest
from typing import Any

from crawlers.preprocessing.eda.risk_detector import RiskDetector


class TestRiskDetector(unittest.TestCase):
    def test_empty_dataset(self):
        res = RiskDetector.analyze([])
        self.assertEqual(res["total_analyzed"], 0)
        self.assertEqual(res["out_of_it_candidates_summary"]["candidate_count"], 0)
        self.assertEqual(res["duplicate_candidates_summary"]["total_duplicate_groups"], 0)
        self.assertEqual(res["salary_anomalies_summary"]["logic_errors_count"], 0)

    def test_out_of_it_candidates_detection_and_safeguard(self):
        records = [
            # 1. Bài nghi vấn ngoài ngành IT (hóa chất)
            {
                "_meta": {"unified_id": "job_chem_01", "source": "careerviet"},
                "title": "Nhân viên phân tích hóa chất phòng thí nghiệm",
                "company": "Công ty Hóa Chất ABC",
            },
            # 2. Bài nghi vấn ngoài ngành IT (may mặc)
            {
                "_meta": {"unified_id": "job_garment_02", "source": "vieclam24h"},
                "title": "Công nhân may mặc xưởng dệt",
                "company": "Công ty May Nam Định",
            },
            # 3. Bài có từ khóa "hóa chất" NHƯNG là IT nhờ safeguard ("Kỹ sư phần mềm")
            {
                "_meta": {"unified_id": "job_it_safeguard_03", "source": "topdev"},
                "title": "Kỹ sư phần mềm phân tích hóa chất công nghiệp",
                "company": "Tech Corp",
            },
            # 4. Bài IT chuẩn
            {
                "_meta": {"unified_id": "job_it_04", "source": "itviec"},
                "title": "Senior Backend Developer (Golang/Python)",
                "company": "VNG",
            },
        ]
        res = RiskDetector.analyze(records)
        out_summary = res["out_of_it_candidates_summary"]

        # Chỉ có 2 bài bị gắn cờ ứng viên cần rà soát (job 1 và job 2)
        self.assertEqual(out_summary["candidate_count"], 2)
        flagged_ids = [c["unified_id"] for c in out_summary["candidates_sample"]]
        self.assertIn("job_chem_01", flagged_ids)
        self.assertIn("job_garment_02", flagged_ids)
        self.assertNotIn("job_it_safeguard_03", flagged_ids)  # Được bảo vệ
        self.assertNotIn("job_it_04", flagged_ids)

        # Kiểm tra chi tiết ứng viên
        cand1 = next(c for c in out_summary["candidates_sample"] if c["unified_id"] == "job_chem_01")
        self.assertEqual(cand1["matched_rule"], "CHEMISTRY")
        self.assertEqual(cand1["status"], "CANDIDATE_FOR_MANUAL_REVIEW")
        self.assertEqual(cand1["field_matched"], "title")

    def test_company_title_duplicate_groups_intra_vs_cross(self):
        records = [
            # Nhóm 1: Thuần nội bộ 1 nguồn (topcv, 2 bài)
            {
                "_meta": {"unified_id": "intra_1", "source": "topcv"},
                "company": " Công ty TNHH Phần Mềm ABC  ",  # Thử nghiệm khoảng trắng
                "title": "Lập Trình Viên Python",
            },
            {
                "_meta": {"unified_id": "intra_2", "source": "topcv"},
                "company": "công ty tnhh phần mềm abc",
                "title": "lập trình viên python",
            },
            # Nhóm 2: Chéo nhiều nguồn (1 bài topcv, 2 bài vietnamworks = 3 bài)
            {
                "_meta": {"unified_id": "cross_1", "source": "topcv"},
                "company": "FPT Software",
                "title": "Java Middle Developer",
            },
            {
                "_meta": {"unified_id": "cross_2", "source": "vietnamworks"},
                "company": "FPT Software",
                "title": "Java Middle Developer",
            },
            {
                "_meta": {"unified_id": "cross_3", "source": "vietnamworks"},
                "company": "fpt software",
                "title": "java middle developer",
            },
            # Bài đơn lẻ (không trùng)
            {
                "_meta": {"unified_id": "single_1", "source": "itviec"},
                "company": "VNG",
                "title": "Product Owner",
            },
        ]
        res = RiskDetector.analyze(records)
        dup = res["duplicate_candidates_summary"]

        # Tổng số nhóm trùng: 2 nhóm
        self.assertEqual(dup["total_duplicate_groups"], 2)
        # Tổng số bài thuộc các nhóm: 2 + 3 = 5 bài
        self.assertEqual(dup["total_records_in_groups"], 5)
        # Tổng số bài dư: (2 - 1) + (3 - 1) = 3 bài
        self.assertEqual(dup["total_excess_records"], 3)

        # Nhóm thuần nội bộ
        intra = dup["pure_intra_source_groups"]
        self.assertEqual(intra["group_count"], 1)
        self.assertEqual(intra["records_count"], 2)
        self.assertEqual(intra["excess_records_count"], 1)
        self.assertEqual(intra["breakdown_by_source"]["topcv"], 1)

        # Nhóm chéo nguồn
        cross = dup["cross_source_groups"]
        self.assertEqual(cross["group_count"], 1)
        self.assertEqual(cross["records_count"], 3)
        self.assertEqual(cross["excess_records_count"], 2)

        # Kiểm toán đối soát số học
        recon = dup["reconciliation"]
        self.assertTrue(recon["groups_equation_valid"])
        self.assertTrue(recon["records_equation_valid"])
        self.assertTrue(recon["excess_equation_valid"])

    def test_salary_anomalies_logic_errors_vs_extreme_outliers(self):
        records = [
            # 1. Lỗi logic: salary_min > salary_max
            {
                "_meta": {"unified_id": "sal_err_01", "source": "topcv"},
                "salary": {
                    "salary_min": 35000000,
                    "salary_max": 25000000,
                    "salary_currency": "VND",
                    "salary_raw_text": "35 - 25 triệu/tháng",
                },
            },
            # 2. Giá trị cực đoan: Lương quá thấp (< 500k VND)
            {
                "_meta": {"unified_id": "sal_outlier_02", "source": "vieclam24h"},
                "salary": {
                    "salary_min": 200000,
                    "salary_max": 300000,
                    "salary_currency": "VND",
                    "salary_raw_text": "200k - 300k/tháng",
                },
            },
            # 3. Giá trị cực đoan: Lương quá cao (> 500 triệu VND)
            {
                "_meta": {"unified_id": "sal_outlier_03", "source": "vietnamworks"},
                "salary": {
                    "salary_min": 600000000,
                    "salary_max": 800000000,
                    "salary_currency": "VND",
                    "salary_raw_text": "600 - 800 triệu/tháng",
                },
            },
            # 4. Lương bình thường hợp lệ
            {
                "_meta": {"unified_id": "sal_valid_04", "source": "itviec"},
                "salary": {
                    "salary_min": 20000000,
                    "salary_max": 30000000,
                    "salary_currency": "VND",
                    "salary_raw_text": "20 - 30 triệu/tháng",
                },
            },
        ]
        res = RiskDetector.analyze(records)
        sal_summary = res["salary_anomalies_summary"]

        # Phân biệt rành mạch giữa lỗi logic và giá trị cực đoan
        self.assertEqual(sal_summary["logic_errors_count"], 1)
        self.assertEqual(sal_summary["extreme_outliers_count"], 4)  # 2 bài cực đoan, mỗi bài có 2 mốc min & max

        logic_err = sal_summary["logic_errors"][0]
        self.assertEqual(logic_err["unified_id"], "sal_err_01")
        self.assertEqual(logic_err["anomaly_type"], "LOGIC_ERROR_MIN_GREATER_THAN_MAX")

    def test_crash_safety_and_json_serializability(self):
        records: list[Any] = [
            None,
            "invalid record",
            {"title": None, "company": None},
            {"salary": {"salary_min": "bad", "salary_max": float("nan")}},
        ]
        res = RiskDetector.analyze(records)  # type: ignore[arg-type]  # Co y truyen du lieu bat thuong (None, str) de kiem thu crash-safety
        self.assertEqual(res["total_analyzed"], 4)

        # Tuần tự hóa JSON thành công 100%
        json_output = json.dumps(res, ensure_ascii=False)
        self.assertIsInstance(json_output, str)


    def test_salary_anomalies_unknown_period_handling(self):
        """Regression test cho Finding 03 (P2): xu ly rieng canh bao luong khi period == UNKNOWN."""
        records = [
            # 1. Monthly bat thuong: van duoc phat hien trong extreme_outliers nhu truoc
            {
                "_meta": {"unified_id": "monthly_low", "source": "src1"},
                "salary": {"salary_min": 100000, "salary_currency": "VND", "salary_raw_text": "100k/tháng"},
            },
            # 2. Unknown period <= 0: ZERO_OR_NEGATIVE_SALARY
            {
                "_meta": {"unified_id": "unk_zero", "source": "src2"},
                "salary": {"salary_min": 0, "salary_currency": "VND", "salary_raw_text": "0 - 10 triệu / project"},
            },
            # 3. Unknown period VND cuc thap (< 20,000 VND): EXTREME_LOW_SALARY_UNKNOWN_PERIOD
            {
                "_meta": {"unified_id": "unk_vnd_low", "source": "src3"},
                "salary": {"salary_min": 1995, "salary_currency": "VND", "salary_raw_text": "Thương lượng"},
            },
            # 4. Unknown period USD cuc thap (< 5 USD): EXTREME_LOW_SALARY_UNKNOWN_PERIOD
            {
                "_meta": {"unified_id": "unk_usd_low", "source": "src4"},
                "salary": {"salary_min": 1.0, "salary_currency": "USD", "salary_raw_text": "1.000 - 1.300 USD"},
            },
            # 5. Unknown period gia tri binh thuong: KHONG bi gan nhan bat thuong tuy tien
            {
                "_meta": {"unified_id": "unk_normal", "source": "src5"},
                "salary": {"salary_min": 15000000, "salary_max": 25000000, "salary_currency": "VND", "salary_raw_text": "Thỏa thuận"},
            },
            # 6. Unknown period 50,000 USD (khong du can cu ket luan neu khong biet ky luong): KHONG gan nhan tuy tien
            {
                "_meta": {"unified_id": "unk_ambiguous", "source": "src6"},
                "salary": {"salary_min": 50000, "salary_max": 50000, "salary_currency": "USD", "salary_raw_text": "Thương lượng"},
            },
            # 7. Null/missing salary: an toan, khong crash
            {
                "_meta": {"unified_id": "null_sal", "source": "src7"},
                "salary": None,
            },
            {
                "_meta": {"unified_id": "missing_sal", "source": "src8"},
            },
        ]
        res = RiskDetector.analyze(records)
        sa = res["salary_anomalies_summary"]

        # 1. Monthly bat thuong duoc tinh vao extreme_outliers_count
        self.assertEqual(sa["extreme_outliers_count"], 1)
        self.assertEqual(sa["extreme_outliers_sample"][0]["unified_id"], "monthly_low")
        self.assertEqual(sa["extreme_outliers_sample"][0]["anomaly_type"], "EXTREME_LOW_SALARY")

        # 2. Unknown period bat thuong duoc tach rieng vao unknown_period_anomalies
        self.assertEqual(sa["unknown_period_anomalies_count"], 3)  # unk_zero, unk_vnd_low, unk_usd_low
        unk_types = {item["unified_id"]: item["anomaly_type"] for item in sa["unknown_period_anomalies_sample"]}
        self.assertEqual(unk_types["unk_zero"], "ZERO_OR_NEGATIVE_SALARY")
        self.assertEqual(unk_types["unk_vnd_low"], "EXTREME_LOW_SALARY_UNKNOWN_PERIOD")
        self.assertEqual(unk_types["unk_usd_low"], "EXTREME_LOW_SALARY_UNKNOWN_PERIOD")

        # 3. unk_normal va unk_ambiguous KHONG bi gan nhan bat thuong
        all_flagged_uids = (
            [x["unified_id"] for x in sa["logic_errors"]]
            + [x["unified_id"] for x in sa["extreme_outliers_sample"]]
            + [x["unified_id"] for x in sa["unknown_period_anomalies_sample"]]
        )
        self.assertNotIn("unk_normal", all_flagged_uids)
        self.assertNotIn("unk_ambiguous", all_flagged_uids)
        self.assertNotIn("null_sal", all_flagged_uids)
        self.assertNotIn("missing_sal", all_flagged_uids)

    def test_company_title_normalization_consistency(self):
        """Regression test cho Finding 04 (P3): dam bao RiskDetector normalize giong EDAProfiler."""
        from crawlers.preprocessing.eda.profiler import EDAProfiler

        # Chuan hoa chuoi co khoang trang kep
        self.assertEqual(RiskDetector.normalize_text("FPT   Software"), "fpt software")
        self.assertEqual(RiskDetector.normalize_text("FPT Software"), "fpt software")
        self.assertEqual(
            RiskDetector.normalize_text("FPT   Software"),
            EDAProfiler.normalize_text("FPT Software"),
        )

    def test_bug01_pay_period_detection_consistency(self):
        """Regression test cho BUG-01: Dong bo hoa logic nhan dien pay_period giua SalaryAnalyzer va RiskDetector."""
        from crawlers.preprocessing.eda.salary_analyzer import SalaryAnalyzer

        # 1. Ky luong tuong minh (explicit pay_period / period)
        sal_explicit_1 = {"pay_period": "monthly", "salary_raw_text": "Thoa thuan"}
        sal_explicit_2 = {"period": "yearly", "salary_raw_text": "Thuong luong"}
        self.assertEqual(SalaryAnalyzer.detect_pay_period(sal_explicit_1), "MONTHLY")
        self.assertEqual(RiskDetector.detect_pay_period(sal_explicit_1), "MONTHLY")
        self.assertEqual(SalaryAnalyzer.detect_pay_period(sal_explicit_2), "YEARLY")
        self.assertEqual(RiskDetector.detect_pay_period(sal_explicit_2), "YEARLY")

        # 2. Chuoi nhan dien duoc ky luong ro rang
        sal_valid_monthly_1 = {"salary_raw_text": "10 - 20 triệu/tháng"}
        sal_valid_monthly_2 = {"salary_raw_text": "1,000 - 2,000 USD / month"}
        sal_valid_hourly = {"salary_raw_text": "50,000 VND / giờ"}
        self.assertEqual(RiskDetector.detect_pay_period(sal_valid_monthly_1), "MONTHLY")
        self.assertEqual(SalaryAnalyzer.detect_pay_period(sal_valid_monthly_1), "MONTHLY")
        self.assertEqual(RiskDetector.detect_pay_period(sal_valid_monthly_2), "MONTHLY")
        self.assertEqual(SalaryAnalyzer.detect_pay_period(sal_valid_monthly_2), "MONTHLY")
        self.assertEqual(RiskDetector.detect_pay_period(sal_valid_hourly), "HOURLY")
        self.assertEqual(SalaryAnalyzer.detect_pay_period(sal_valid_hourly), "HOURLY")

        # 3. Chuoi co tu 'thang' / 'month' nhung KHONG noi ve ky luong -> UNKNOWN
        sal_probation = {"salary_raw_text": "Thương lượng (thử việc 2 tháng)"}
        sal_experience = {"salary_raw_text": "Yêu cầu kinh nghiệm trên 6 tháng"}
        sal_contract = {"salary_raw_text": "Hợp đồng 12 tháng"}
        self.assertEqual(RiskDetector.detect_pay_period(sal_probation), "UNKNOWN")
        self.assertEqual(SalaryAnalyzer.detect_pay_period(sal_probation), "UNKNOWN")
        self.assertEqual(RiskDetector.detect_pay_period(sal_experience), "UNKNOWN")
        self.assertEqual(SalaryAnalyzer.detect_pay_period(sal_experience), "UNKNOWN")
        self.assertEqual(RiskDetector.detect_pay_period(sal_contract), "UNKNOWN")
        self.assertEqual(SalaryAnalyzer.detect_pay_period(sal_contract), "UNKNOWN")

        # 4. Du lieu thieu, None, dict rong
        self.assertEqual(RiskDetector.detect_pay_period(None), "UNKNOWN")
        self.assertEqual(SalaryAnalyzer.detect_pay_period(None), "UNKNOWN")
        self.assertEqual(RiskDetector.detect_pay_period({}), "UNKNOWN")
        self.assertEqual(SalaryAnalyzer.detect_pay_period({}), "UNKNOWN")

        # 5. Kiem tra tac dong len analyze(): Ban ghi co 'thử việc 2 tháng' khong bi quy ket la MONTHLY
        records = [
            {
                "_meta": {"unified_id": "job_probation", "source": "topdev"},
                "salary": {
                    "salary_min": 100000,  # 100k VND
                    "salary_currency": "VND",
                    "salary_raw_text": "Thương lượng (thử việc 2 tháng)",
                },
            }
        ]
        res = RiskDetector.analyze(records)
        sa = res["salary_anomalies_summary"]
        # Khong bi coi la monthly outlier (< 500k monthly)
        self.assertEqual(sa["extreme_outliers_count"], 0)
        # Vi period la UNKNOWN va 100k > 20k -> khong phat sinh canh bao bat thuong tuy tien
        self.assertEqual(sa["unknown_period_anomalies_count"], 0)


if __name__ == "__main__":
    unittest.main()
