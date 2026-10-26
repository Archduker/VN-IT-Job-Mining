# -*- coding: utf-8 -*-
"""tests.test_qa_pipeline
~~~~~~~~~~~~~~~~~~~~~~~~
Bộ kiểm thử tự động toàn diện cho đường ống kiểm định chất lượng QA (preprocessing/qa/run_qa_checks.py).

Kiểm định 5 trụ cột:
  1. Check 1 (Lineage & File Existence): Tính toàn vẹn dòng dõi 3 tệp (9,824 -> 9,824 -> ~8,474).
  2. Check 2 (100% PURE JSON & RFC 8259): Tuyệt đối không có Parquet/CSV, quét sâu đệ quy zero NaN.
  3. Check 3 (Golden Master Contract & Zero Raw): Zero raw_* ở root, chuẩn jd_clean_text, lọc sạch 'Phúc lợi'.
  4. Check 4 (Skills & Extract_from_JD Contract): Nhóm skills độc lập ở root, bóc tách extract_from_jd.
  5. Check 5 (Outlier & Quality Governance): quality_score trong [0, 1], is_outlier_capped boolean, tuân thủ QR1-QR5.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict

import pytest

from preprocessing.qa.run_qa_checks import (
    PROJECT_ROOT,
    QACheckSuite,
    detect_nan_recursive,
    generate_json_report,
    generate_markdown_report,
    scan_raw_json_tokens_for_nan,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_valid_golden_record() -> Dict[str, Any]:
    """Bản ghi Golden Master mẫu tuân thủ 100% hợp đồng dữ liệu."""
    return {
        "job_id_global": "topcv_test_001",
        "source_platform": "topcv",
        "source_job_id": "test_001",
        "source_url": "https://topcv.vn/job/test",
        "job_title": "Senior Python Backend Engineer",
        "company": {
            "company_name": "Tech Corp Vietnam",
            "company_name_normalized": "tech corp vietnam",
            "company_scale": "100-499 nhân viên",
            "category_text": ["CNTT - Phần mềm", "Fintech"],
        },
        "salary": {
            "salary_text": "30 - 50 triệu",
            "salary_min_vnd": 30000000.0,
            "salary_max_vnd": 50000000.0,
            "salary_currency": "VND",
            "is_negotiable": False,
        },
        "date": {
            "posted_date": "2026-10-01",
            "deadline_date": "2026-10-31",
            "crawled_at_iso": "2026-10-20T10:00:00Z",
        },
        "working_locations": ["Hà Nội"],
        "cities_list": ["Hà Nội"],
        "districts_list": ["Cầu Giấy"],
        "detailed_locations": [
            {"province": "Hà Nội", "district": "Cầu Giấy", "full_address": "Duy Tân, Cầu Giấy, Hà Nội"}
        ],
        "employment_type": "Full-time",
        "work_mode": "Hybrid",
        "min_experience_years": 3.0,
        "headcount": 2,
        "jd_clean_text": {
            "benefits_text": ["Chế độ bảo hiểm đầy đủ", "Lương tháng 13", "Thưởng hiệu quả"],
            "description_text": "Phát triển hệ thống microservices backend xử lý dữ liệu giao dịch lớn.",
            "requirements_text": "Tối thiểu 3 năm kinh nghiệm với Python, FastAPI, Docker, PostgreSQL.",
        },
        "skills": {
            "skills_list": ["Docker", "FastAPI", "PostgreSQL", "Python"],
            "skills_count": 4,
        },
        "extract_from_jd": {
            "standardized_education": "Đại học",
            "standardized_seniority": "Senior",
            "age_min": 24,
            "age_max": 35,
            "is_saturday_work": False,
            "word_count": 280,
            "char_count": 1650,
            "is_stub_jd": False,
            "primary_language": "vi",
            "company_size_min": 100,
            "company_size_max": 499,
            "company_scale_tier": "100-499 nhân viên",
            "skills_count": 4,
            "benefits_count": 3,
            "imputed_fields": None,
            "salary_max_winsorized": 50000000.0,
            "is_salary_winsorized": False,
            "is_outlier_capped": False,
            "log_salary_max": 17.7275,
            "quality_score": 1.0,
        },
        "primary_city": "Hà Nội",
        "standardized_districts": ["Cầu Giấy"],
        "is_saturday_work": False,
        "standardized_education": "Đại học",
        "age_min": 24,
        "age_max": 35,
        "standardized_seniority": "Senior",
        "log_salary_max": 17.7275,
        "is_outlier_capped": False,
        "quality_score": 1.0,
    }


# ---------------------------------------------------------------------------
# Check 1: Lineage & File Existence Unit & Integration Tests
# ---------------------------------------------------------------------------

class TestCheck1LineageAndExistence:
    """Kiểm tra Bộ Check 1: Hiện diện tệp, tính toàn vẹn cú pháp và tính kế thừa dòng dõi."""

    def test_unit_lineage_logic_success(self, tmp_path: Path):
        f1 = tmp_path / "raw_for_outlier.json"
        f2 = tmp_path / "raw_for_normalization.json"
        f3 = tmp_path / "golden_master.json"

        # Mock 9824 bản ghi cho f1 và f2
        dummy_recs = [{"job_id_global": f"id_{i}"} for i in range(9824)]
        with f1.open("w") as f:
            json.dump(dummy_recs, f)
        with f2.open("w") as f:
            json.dump(dummy_recs, f)

        # Mock 8475 bản ghi cho f3
        dummy_golden = dummy_recs[:8475]
        with f3.open("w") as f:
            json.dump(dummy_golden, f)

        suite = QACheckSuite(
            raw_outlier_path=f1,
            raw_norm_path=f2,
            golden_master_path=f3,
            staging_dir=tmp_path / "staging",
            curated_dir=tmp_path / "curated",
        )
        res = suite.check_1_lineage_and_file_existence()
        assert res["status"] == "PASSED"
        assert res["lineage"]["stage1_to_stage2"]["is_exact_match"] is True
        assert res["lineage"]["stage2_to_golden"]["golden_ids_in_stage2"] is True

    def test_unit_lineage_fails_on_id_leakage(self, tmp_path: Path):
        f1 = tmp_path / "raw_for_outlier.json"
        f2 = tmp_path / "raw_for_normalization.json"
        f3 = tmp_path / "golden_master.json"

        recs1 = [{"job_id_global": f"id_{i}"} for i in range(9824)]
        with f1.open("w") as f:
            json.dump(recs1, f)
        with f2.open("w") as f:
            json.dump(recs1, f)

        # Golden chứa ID lạ không bắt nguồn từ stage 2
        recs3 = [{"job_id_global": f"unknown_alien_{i}"} for i in range(8475)]
        with f3.open("w") as f:
            json.dump(recs3, f)

        suite = QACheckSuite(
            raw_outlier_path=f1,
            raw_norm_path=f2,
            golden_master_path=f3,
            staging_dir=tmp_path / "staging",
            curated_dir=tmp_path / "curated",
        )
        res = suite.check_1_lineage_and_file_existence()
        assert res["status"] == "FAILED"
        assert any("không bắt nguồn từ Stage 2" in err for err in res["errors"])

    @pytest.mark.integration
    def test_real_pipeline_files_exist_and_counts_match(self):
        """Integration test: Kiểm tra trực tiếp 3 file thực tế trong dự án."""
        p1 = PROJECT_ROOT / "data" / "transformation" / "raw_for_outlier.json"
        p2 = PROJECT_ROOT / "data" / "missing_outlier" / "raw_for_normalization.json"
        p3 = PROJECT_ROOT / "data" / "curated" / "golden_master.json"

        assert p1.is_file(), f"Không tìm thấy File 1: {p1}"
        assert p2.is_file(), f"Không tìm thấy File 2: {p2}"
        assert p3.is_file(), f"Không tìm thấy File 3: {p3}"

        suite = QACheckSuite(
            raw_outlier_path=p1,
            raw_norm_path=p2,
            golden_master_path=p3,
            staging_dir=PROJECT_ROOT / "data" / "staging",
            curated_dir=PROJECT_ROOT / "data" / "curated",
        )
        res = suite.check_1_lineage_and_file_existence()
        assert res["status"] == "PASSED"
        assert res["files"]["raw_for_outlier"]["records"] == 9824
        assert res["files"]["raw_for_normalization"]["records"] == 9824
        assert 8400 <= res["files"]["golden_master"]["records"] <= 8550
        assert res["lineage"]["stage1_to_stage2"]["is_exact_match"] is True
        assert res["lineage"]["stage2_to_golden"]["golden_ids_in_stage2"] is True


# ---------------------------------------------------------------------------
# Check 2: Pure JSON & Zero NaN Compliance Tests
# ---------------------------------------------------------------------------

class TestCheck2PureJsonAndRFC8259:
    """Kiểm tra Bộ Check 2: 100% Pure JSON, Zero Parquet/CSV, và Zero NaN."""

    def test_detect_nan_recursive_catches_all_levels(self):
        clean_obj = {
            "a": 1,
            "b": [1.5, 2.0, None, {"c": "hello", "d": None}],
            "e": {"f": [None, 3.14]},
        }
        assert len(detect_nan_recursive(clean_obj)) == 0

        dirty_obj = {
            "a": 1,
            "b": [1.5, float("nan"), {"c": "hello", "d": float("nan")}],
            "e": {"f": [float("nan"), 3.14]},
        }
        violations = detect_nan_recursive(dirty_obj)
        assert len(violations) == 3
        assert "b[1]" in violations
        assert "b[2].d" in violations
        assert "e.f[0]" in violations

    def test_scan_raw_json_tokens_detects_nan(self, tmp_path: Path):
        clean_json = tmp_path / "clean.json"
        clean_json.write_text('{"salary": null, "title": "NaN Engineer"}', encoding="utf-8")
        assert len(scan_raw_json_tokens_for_nan(clean_json)) == 0

        dirty_json = tmp_path / "dirty.json"
        dirty_json.write_text('{"salary": NaN, "count": 10}', encoding="utf-8")
        violations = scan_raw_json_tokens_for_nan(dirty_json)
        assert len(violations) > 0
        assert "NaN" in violations[0]

    def test_unit_forbidden_parquet_csv_detected(self, tmp_path: Path):
        staging = tmp_path / "staging"
        curated = tmp_path / "curated"
        staging.mkdir(parents=True)
        curated.mkdir(parents=True)

        # Tạo file cấm
        (staging / "forbidden.parquet").write_bytes(b"PAR1")
        (curated / "forbidden.csv").write_text("a,b,c\n1,2,3", encoding="utf-8")

        dummy_f = tmp_path / "dummy.json"
        dummy_f.write_text("[]", encoding="utf-8")

        suite = QACheckSuite(
            raw_outlier_path=dummy_f,
            raw_norm_path=dummy_f,
            golden_master_path=dummy_f,
            staging_dir=staging,
            curated_dir=curated,
        )
        res = suite.check_2_pure_json_and_rfc8259()
        assert res["status"] == "FAILED"
        assert len(res["forbidden_files_found"]) == 2

    @pytest.mark.integration
    def test_real_directories_zero_parquet_and_zero_csv(self):
        """Integration test: Kiểm tra tuyệt đối 0 tệp Parquet/CSV trong data/staging và data/curated."""
        staging_dir = PROJECT_ROOT / "data" / "staging"
        curated_dir = PROJECT_ROOT / "data" / "curated"

        parquet_files = list(staging_dir.rglob("*.parquet")) + list(curated_dir.rglob("*.parquet"))
        csv_files = list(staging_dir.rglob("*.csv")) + list(curated_dir.rglob("*.csv"))

        assert len(parquet_files) == 0, f"Vẫn còn tệp .parquet: {parquet_files}"
        assert len(csv_files) == 0, f"Vẫn còn tệp .csv: {csv_files}"


# ---------------------------------------------------------------------------
# Check 3: Golden Master Contract & Zero Raw Tests
# ---------------------------------------------------------------------------

class TestCheck3GoldenMasterContractZeroRaw:
    """Kiểm tra Bộ Check 3: Zero trường thô raw_* ở root, sạch benefits_text, chuẩn jd_clean_text."""

    def test_unit_golden_master_catches_root_raw(self, tmp_path: Path, sample_valid_golden_record: Dict[str, Any]):
        invalid_rec = sample_valid_golden_record.copy()
        invalid_rec["raw_working_time"] = "8h - 17h"
        invalid_rec["raw_salary_text"] = "Thỏa thuận"

        p = tmp_path / "golden.json"
        p.write_text(json.dumps([invalid_rec]), encoding="utf-8")

        suite = QACheckSuite(
            raw_outlier_path=p,
            raw_norm_path=p,
            golden_master_path=p,
            staging_dir=tmp_path,
            curated_dir=tmp_path,
        )
        suite.data_golden_master = [invalid_rec]
        res = suite.check_3_golden_master_contract_zero_raw()
        assert res["status"] == "FAILED"
        assert res["root_raw_violations_count"] == 1
        assert "raw_working_time" in res["offending_root_raw_keys"]
        assert "raw_salary_text" in res["offending_root_raw_keys"]

    def test_unit_golden_master_catches_benefits_prefix(self, tmp_path: Path, sample_valid_golden_record: Dict[str, Any]):
        invalid_rec = sample_valid_golden_record.copy()
        invalid_rec["jd_clean_text"] = {
            "benefits_text": ["Phúc lợi: Chế độ bảo hiểm", "Chế độ đãi ngộ: Thưởng Tết"],
            "description_text": "Mô tả...",
            "requirements_text": "Yêu cầu...",
        }

        p = tmp_path / "golden.json"
        suite = QACheckSuite(
            raw_outlier_path=p,
            raw_norm_path=p,
            golden_master_path=p,
            staging_dir=tmp_path,
            curated_dir=tmp_path,
        )
        suite.data_golden_master = [invalid_rec]
        res = suite.check_3_golden_master_contract_zero_raw()
        assert res["status"] == "FAILED"
        assert res["benefits_prefix_violations_count"] == 2

    @pytest.mark.integration
    def test_real_golden_master_zero_raw_and_clean_jd(self):
        """Integration test: Kiểm tra toàn bộ bản ghi golden_master.json thực tế."""
        p3 = PROJECT_ROOT / "data" / "curated" / "golden_master.json"
        with p3.open("r", encoding="utf-8") as f:
            records = json.load(f)

        suite = QACheckSuite(
            raw_outlier_path=p3,
            raw_norm_path=p3,
            golden_master_path=p3,
            staging_dir=PROJECT_ROOT / "data" / "staging",
            curated_dir=PROJECT_ROOT / "data" / "curated",
        )
        suite.data_golden_master = records
        res = suite.check_3_golden_master_contract_zero_raw()
        assert res["status"] == "PASSED"
        assert res["root_raw_violations_count"] == 0
        assert res["benefits_prefix_violations_count"] == 0
        assert res["jd_clean_text_metrics"]["missing_description_text"] == 0
        assert res["jd_clean_text_metrics"]["missing_requirements_text"] == 0
        assert res["jd_clean_text_metrics"]["unexpected_raw_prefixes"] == 0


# ---------------------------------------------------------------------------
# Check 4: Skills & Extract_from_JD Contract Tests
# ---------------------------------------------------------------------------

class TestCheck4SkillsAndExtractContract:
    """Kiểm tra Bộ Check 4: Khế ước nhóm skills và extract_from_jd."""

    def test_unit_skills_mismatch_fails(self, tmp_path: Path, sample_valid_golden_record: Dict[str, Any]):
        invalid_rec = sample_valid_golden_record.copy()
        invalid_rec["skills"] = {
            "skills_list": ["Python", "Docker"],
            "skills_count": 5,  # Không khớp với len(skills_list)
        }

        p = tmp_path / "golden.json"
        suite = QACheckSuite(
            raw_outlier_path=p,
            raw_norm_path=p,
            golden_master_path=p,
            staging_dir=tmp_path,
            curated_dir=tmp_path,
        )
        suite.data_golden_master = [invalid_rec]
        res = suite.check_4_skills_and_extract_contract()
        assert res["status"] == "FAILED"
        assert any("skills_count không khớp" in err for err in res["errors"])

    @pytest.mark.integration
    def test_real_golden_master_skills_and_extract_contract(self):
        """Integration test: Toàn bộ bản ghi golden_master.json phải có skills và extract_from_jd."""
        p3 = PROJECT_ROOT / "data" / "curated" / "golden_master.json"
        with p3.open("r", encoding="utf-8") as f:
            records = json.load(f)

        suite = QACheckSuite(
            raw_outlier_path=p3,
            raw_norm_path=p3,
            golden_master_path=p3,
            staging_dir=PROJECT_ROOT / "data" / "staging",
            curated_dir=PROJECT_ROOT / "data" / "curated",
        )
        suite.data_golden_master = records
        res = suite.check_4_skills_and_extract_contract()
        assert res["status"] == "PASSED"
        assert res["skills_group_metrics"]["records_with_skills_group"] == len(records)
        assert res["skills_group_metrics"]["records_valid_skills_count"] == len(records)
        assert res["extract_from_jd_metrics"]["records_with_extract_group"] == len(records)
        assert res["extract_from_jd_metrics"]["text_metrics_present_count"] == len(records)


# ---------------------------------------------------------------------------
# Check 5: Outlier & Quality Governance Tests
# ---------------------------------------------------------------------------

class TestCheck5OutlierAndQualityGovernance:
    """Kiểm tra Bộ Check 5: Quản trị chất lượng & Xử lý ngoại lai từ nhánh Tài."""

    def test_unit_quality_score_out_of_bounds_fails(self, tmp_path: Path, sample_valid_golden_record: Dict[str, Any]):
        invalid_rec = sample_valid_golden_record.copy()
        invalid_rec["quality_score"] = 1.25  # Ngoài dải [0, 1]

        p = tmp_path / "golden.json"
        suite = QACheckSuite(
            raw_outlier_path=p,
            raw_norm_path=p,
            golden_master_path=p,
            staging_dir=tmp_path,
            curated_dir=tmp_path,
        )
        suite.data_golden_master = [invalid_rec]
        res = suite.check_5_outlier_and_quality_governance()
        assert res["status"] == "FAILED"
        assert any("quality_score ngoài [0, 1]" in err for err in res["errors"])

    def test_unit_negative_salary_fails_qr4(self, tmp_path: Path, sample_valid_golden_record: Dict[str, Any]):
        invalid_rec = sample_valid_golden_record.copy()
        invalid_rec["salary"]["salary_min_vnd"] = -5000000.0

        p = tmp_path / "golden.json"
        suite = QACheckSuite(
            raw_outlier_path=p,
            raw_norm_path=p,
            golden_master_path=p,
            staging_dir=tmp_path,
            curated_dir=tmp_path,
        )
        suite.data_golden_master = [invalid_rec]
        res = suite.check_5_outlier_and_quality_governance()
        assert res["status"] == "FAILED"
        assert res["rules_audit"]["qr4_negative_salary_violations"] == 1

    @pytest.mark.integration
    def test_real_golden_master_quality_score_and_qr_compliance(self):
        """Integration test: Kiểm tra quality_score và QR1-QR5 trên golden_master.json thực tế."""
        p3 = PROJECT_ROOT / "data" / "curated" / "golden_master.json"
        with p3.open("r", encoding="utf-8") as f:
            records = json.load(f)

        suite = QACheckSuite(
            raw_outlier_path=p3,
            raw_norm_path=p3,
            golden_master_path=p3,
            staging_dir=PROJECT_ROOT / "data" / "staging",
            curated_dir=PROJECT_ROOT / "data" / "curated",
        )
        suite.data_golden_master = records
        res = suite.check_5_outlier_and_quality_governance()
        assert res["status"] == "PASSED"
        assert res["quality_score_metrics"]["valid_score_count"] == len(records)
        assert 0.0 <= res["quality_score_metrics"]["score_min"] <= 1.0
        assert 0.0 <= res["quality_score_metrics"]["score_max"] <= 1.0
        assert res["rules_audit"]["qr4_negative_salary_violations"] == 0
        assert res["rules_audit"]["qr2_experience_range_violations"] == 0
        assert res["outlier_capping_metrics"]["is_outlier_capped_count"] > 0


# ---------------------------------------------------------------------------
# Report Generation & End-to-End Suite Execution Tests
# ---------------------------------------------------------------------------

class TestReportGenerationAndSuiteExecution:
    """Kiểm tra xuất báo cáo Markdown, JSON và quy trình chạy trọn vẹn."""

    def test_report_generation(self, tmp_path: Path):
        dummy_result = {
            "timestamp": "2026-10-26T18:00:00Z",
            "overall_status": "PASSED",
            "duration_seconds": 1.234,
            "total_checks": 5,
            "passed_checks": 5,
            "failed_checks": 0,
            "checks": {
                "check_1_lineage_and_existence": {
                    "status": "PASSED",
                    "files": {
                        "raw_for_outlier": {"path": "f1.json", "records": 9824, "size_mb": 68.0, "json_valid": True},
                        "raw_for_normalization": {"path": "f2.json", "records": 9824, "size_mb": 72.0, "json_valid": True},
                        "golden_master": {"path": "f3.json", "records": 8475, "size_mb": 53.0, "json_valid": True},
                    },
                    "lineage": {
                        "stage1_to_stage2": {"id_preservation_rate_pct": 100.0, "is_exact_match": True},
                        "stage2_to_golden": {"records_reduced": 1349, "deduplication_reduction_pct": 13.73, "golden_ids_in_stage2": True},
                    },
                    "errors": [],
                },
                "check_2_pure_json_rfc8259": {
                    "status": "PASSED",
                    "forbidden_files_found": [],
                    "nan_scan_results": {},
                    "errors": [],
                },
                "check_3_golden_master_contract": {
                    "status": "PASSED",
                    "total_records_checked": 8475,
                    "root_raw_violations_count": 0,
                    "offending_root_raw_keys": [],
                    "jd_clean_text_metrics": {
                        "missing_jd_clean_text": 0,
                        "missing_description_text": 0,
                        "missing_requirements_text": 0,
                        "unexpected_raw_prefixes": 0,
                    },
                    "benefits_prefix_violations_count": 0,
                    "errors": [],
                },
                "check_4_skills_and_extract_contract": {
                    "status": "PASSED",
                    "total_records_checked": 8475,
                    "skills_group_metrics": {
                        "records_with_skills_group": 8475,
                        "records_valid_skills_count": 8475,
                        "average_skills_per_record": 2.8,
                    },
                    "extract_from_jd_metrics": {
                        "records_with_extract_group": 8475,
                        "education_coverage_count": 6800,
                        "seniority_coverage_count": 8475,
                        "saturday_specified_count": 3500,
                        "age_limits_extracted_count": 680,
                        "text_metrics_present_count": 8475,
                    },
                    "errors": [],
                },
                "check_5_outlier_quality_governance": {
                    "status": "PASSED",
                    "total_records_checked": 8475,
                    "quality_score_metrics": {
                        "valid_score_count": 8475,
                        "score_min": 0.45,
                        "score_max": 1.0,
                        "score_mean": 0.998,
                        "records_perfect_1_0": 8332,
                        "records_penalized": 143,
                    },
                    "outlier_capping_metrics": {
                        "is_outlier_capped_count": 115,
                        "is_outlier_capped_pct": 1.36,
                    },
                    "rules_audit": {
                        "qr1_salary_range_violations": 6,
                        "qr2_experience_range_violations": 0,
                        "qr3_date_order_violations": 6,
                        "qr4_negative_salary_violations": 0,
                        "qr5_multiple_fixes_tracked": 0,
                    },
                    "errors": [],
                },
            },
        }

        md_path = tmp_path / "report.md"
        json_path = tmp_path / "report.json"

        generate_markdown_report(dummy_result, md_path)
        generate_json_report(dummy_result, json_path)

        assert md_path.is_file()
        assert json_path.is_file()

        md_text = md_path.read_text(encoding="utf-8")
        assert "QA AUDIT PIPELINE REPORT" in md_text
        assert "PASSED" in md_text
        assert "8,475" in md_text
        assert "100% PURE JSON" in md_text

        with json_path.open("r", encoding="utf-8") as f:
            loaded_json = json.load(f)
        assert loaded_json["overall_status"] == "PASSED"
        assert loaded_json["total_checks"] == 5

    @pytest.mark.integration
    def test_full_pipeline_run_all_checks_passes(self):
        """End-to-End test: Chạy trọn vẹn run_all_checks() trên toàn bộ dataset dự án."""
        p1 = PROJECT_ROOT / "data" / "transformation" / "raw_for_outlier.json"
        p2 = PROJECT_ROOT / "data" / "missing_outlier" / "raw_for_normalization.json"
        p3 = PROJECT_ROOT / "data" / "curated" / "golden_master.json"

        suite = QACheckSuite(
            raw_outlier_path=p1,
            raw_norm_path=p2,
            golden_master_path=p3,
            staging_dir=PROJECT_ROOT / "data" / "staging",
            curated_dir=PROJECT_ROOT / "data" / "curated",
        )
        report = suite.run_all_checks()
        assert report["overall_status"] == "PASSED"
        assert report["passed_checks"] == 5
        assert report["failed_checks"] == 0
