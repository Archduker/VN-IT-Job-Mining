# -*- coding: utf-8 -*-
"""Unit tests for TargetSchemaFormatter (Bước 4)."""

import pytest
from preprocessing.normalization.target_schema_formatter import (
    CANONICAL_ROOT_KEYS,
    TargetSchemaFormatter,
)


def test_exact_11_root_keys():
    """Kiểm tra bản ghi đầu ra có CHÍNH XÁC 11 khóa ở Root."""
    raw_rec = {
        "job_id_global": "topcv_test_001",
        "source_platform": "topcv",
        "source_url": "https://topcv.vn/job/123",
        "job_title": "Java Spring Boot Developer",
        "company_name": "Công ty Công nghệ ABC",
        "raw_location_text": "Hà Nội",
        "salary_min": 20000000.0,
        "salary_max": 35000000.0,
        "raw_description_text": "Phát triển hệ thống ngân hàng",
        "raw_requirements_text": "2 năm kinh nghiệm Java",
        "skills_list": ["Java", "Spring Boot"],
        # Các cờ kỹ thuật trung gian cần loại bỏ:
        "is_stub_jd": False,
        "is_content_image": False,
        "is_salary_winsorized": True,
        "is_outlier_capped": False,
        "quality_score": 0.95,
        "governance": {"clean": True},
        "nlp_metadata": {"char_count": 500},
    }

    res = TargetSchemaFormatter.format_record(raw_rec)

    assert len(res.keys()) == 11
    assert set(res.keys()) == set(CANONICAL_ROOT_KEYS)

    # Đảm bảo các cờ trung gian đã bị loại bỏ hoàn toàn
    for forbidden_key in [
        "is_stub_jd",
        "is_content_image",
        "is_salary_winsorized",
        "is_outlier_capped",
        "quality_score",
        "governance",
        "nlp_metadata",
    ]:
        assert forbidden_key not in res


def test_locations_hierarchy_structure():
    """Kiểm tra trường locations đúng cấu trúc mảng {province, district, Details_address}."""
    raw_rec = {
        "job_id_global": "itviec_002",
        "source_platform": "itviec",
        "working_locations": [
            {"name": "Hồ Chí Minh", "district": "Quận 1"},
            {"name": "Đà Nẵng", "district": "Hải Châu"},
        ],
        "raw_location_text": "Tòa nhà Bitexco, Q1, HCM",
    }

    res = TargetSchemaFormatter.format_record(raw_rec)
    locs = res["locations"]
    assert isinstance(locs, list)
    assert len(locs) == 2
    assert locs[0]["province"] == "Hồ Chí Minh"
    assert locs[0]["district"] == "Quận 1"
    assert locs[1]["province"] == "Đà Nẵng"
    assert locs[1]["district"] == "Hải Châu"


def test_flat_target_record_conversion():
    """Kiểm tra hàm to_flat_target_record xuất đúng dict phẳng 1 tầng."""
    hierarchical_rec = {
        "job_id_global": "vietnamworks_999",
        "source_platform": "vietnamworks",
        "source_url": "https://vietnamworks.com/job/999",
        "job_info": {
            "title": "Senior AI Engineer",
            "job_family": "JF07_DATA_AI",
            "work_type": "fulltime",
            "is_remote": True,
        },
        "company": {
            "name": "AI Corp",
            "industry": "IT - Phần mềm",
            "size": "500-1000",
        },
        "locations": [
            {
                "province": "Hà Nội",
                "district": "Cầu Giấy",
                "Details_address": "Duy Tân, Cầu Giấy",
            }
        ],
        "salary": {
            "salary_min": 40000000.0,
            "salary_max": 70000000.0,
            "salary_currency": "VND",
            "salary_source": "predicted",
        },
        "skills": {
            "hard_skills": ["Python", "PyTorch", "Transformers"],
            "soft_skills": ["Tư duy logic"],
            "domain_skills": ["Trí tuệ nhân tạo"],
        },
        "requirements": {
            "experience_years": 4.0,
            "standardized_seniority": "senior",
            "standardized_education": "bachelor",
            "is_saturday_work": False,
        },
        "jd_text": {
            "language": "vi",
            "description": "Nghiên cứu mô hình LLM",
            "requirements": "Kinh nghiệm 4 năm PyTorch",
            "benefits": ["Thưởng cổ phiếu", "Lương tháng 13"],
        },
        "date": {
            "posted_date": "2024-10-01",
            "expired_date": "2024-11-01",
        },
    }

    flat = TargetSchemaFormatter.to_flat_target_record(hierarchical_rec)

    assert flat["job_id_global"] == "vietnamworks_999"
    assert flat["job_title"] == "Senior AI Engineer"
    assert flat["job_family"] == "JF07_DATA_AI"
    assert flat["is_remote"] is True
    assert flat["company_name"] == "AI Corp"
    assert flat["primary_city"] == "Hà Nội"
    assert flat["salary_min"] == 40000000.0
    assert flat["salary_source"] == "predicted"
    assert flat["hard_skills"] == ["Python", "PyTorch", "Transformers"]
    assert flat["experience_years"] == 4.0
    assert flat["is_saturday_work"] is False
    assert flat["language"] == "vi"
