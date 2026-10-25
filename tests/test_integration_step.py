# -*- coding: utf-8 -*-
"""Unit tests cho riêng giai đoạn Preprocessing: Step 1 - Integration."""

import json
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_INT_DIR = PROJECT_ROOT / "data" / "integration"
REPORTS_INT_DIR = PROJECT_ROOT / "reports" / "integration"


def test_integration_files_exist_and_are_valid_json():
    """Kiểm tra các tệp đầu ra của giai đoạn Integration đều tồn tại và chuẩn JSON."""
    sources = [
        "careerviet",
        "glints",
        "itviec",
        "jobsgo",
        "topcv",
        "topdev",
        "vieclam24h",
        "vietnamworks",
    ]

    for s in sources:
        src_json = DATA_INT_DIR / s / f"{s}_integrated_flat.json"
        rep_json = REPORTS_INT_DIR / f"{s}_integration_report.json"

        assert src_json.exists(), f"Thiếu file JSON tích hợp của sàn {s}"
        assert rep_json.exists(), f"Thiếu file báo cáo JSON tích hợp của sàn {s}"

        with open(src_json, "r", encoding="utf-8") as f:
            records = json.load(f)
            assert isinstance(records, list), f"Dữ liệu tích hợp {s} phải là một JSON array"
            assert len(records) > 0, f"Sàn {s} không có bản ghi tích hợp nào"

        with open(rep_json, "r", encoding="utf-8") as f:
            rep = json.load(f)
            assert rep["step"] == "integration"
            assert rep["output_format"] == "json"


def test_integration_master_flat_json():
    """Kiểm tra file Master Integrated JSON tổng hợp toàn bộ 8 nguồn."""
    master_path = DATA_INT_DIR / "integrated_flat_all_sources.json"
    rep_path = REPORTS_INT_DIR / "master_integration_report.json"

    assert master_path.exists(), "Thiếu file integrated_flat_all_sources.json"
    assert rep_path.exists(), "Thiếu file master_integration_report.json"

    with open(master_path, "r", encoding="utf-8") as f:
        master_records = json.load(f)

    assert len(master_records) == 9824, f"Tổng số bản ghi tích hợp là {len(master_records)}, mong đợi 9824"

    # Kiểm tra cấu trúc bản ghi phẳng chuẩn (Canonical Flat Record - 29 trường toàn diện)
    sample = master_records[0]
    expected_fields = [
        "job_id_global",
        "source_platform",
        "source_job_id",
        "source_url",
        "crawled_at",
        "job_title",
        "company_name",
        "company_address",
        "company_scale",
        "raw_category_text",
        "raw_location_text",
        "working_locations",
        "raw_posted_date",
        "raw_updated_at",
        "raw_deadline",
        "raw_working_time",
        "raw_salary_text",
        "raw_employment_type",
        "raw_work_mode",
        "raw_experience_text",
        "raw_seniority_text",
        "raw_education_text",
        "raw_headcount",
        "raw_age_text",
        "raw_gender_text",
        "skills_list",
        "benefits_list",
        "raw_description_text",
        "raw_requirements_text",
    ]

    for field in expected_fields:
        assert field in sample, f"Thiếu trường {field} trong bản ghi tích hợp"

    # TUYỆT ĐỐI KHÔNG LẤN SÂN: Không được có các trường của Transformer/Missing/Normalization
    forbidden_fields = [
        "salary_min_vnd",
        "salary_max_vnd",
        "salary_source",
        "salary_log_max",
        "job_family",
        "is_imputed_by_genai",
        "is_golden_merged",
    ]
    for forbidden in forbidden_fields:
        assert forbidden not in sample, (
            f"Vi phạm ranh giới: Trường '{forbidden}' thuộc giai đoạn sau, "
            f"không được xuất hiện ở bước Integration!"
        )


def test_null_diagnosis_in_all_source_reports():
    """Kiểm tra mọi trường bị missing đều có lời giải trình null_diagnosis kỹ thuật."""
    sources = [
        "careerviet",
        "glints",
        "itviec",
        "jobsgo",
        "topcv",
        "topdev",
        "vieclam24h",
        "vietnamworks",
    ]
    for s in sources:
        rep_json = REPORTS_INT_DIR / f"{s}_integration_report.json"
        assert rep_json.exists()
        with open(rep_json, "r", encoding="utf-8") as f:
            rep = json.load(f)
        audit = rep.get("field_completeness_audit", {})
        for field_name, stats in audit.items():
            if stats.get("missing_count", 0) > 0:
                assert "null_diagnosis" in stats, (
                    f"Trường {field_name} bị thiếu trong {s} nhưng không có null_diagnosis!"
                )
                assert len(stats["null_diagnosis"]) > 5, (
                    f"Lời giải thích null_diagnosis cho {field_name} trong {s} quá sơ sài!"
                )
