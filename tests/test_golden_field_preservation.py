# -*- coding: utf-8 -*-
"""Regression tests: bảo toàn dữ liệu khi đóng gói Golden Master (Nhiệm vụ A).

Bối cảnh lỗi (đã tái hiện trên 931 bản ghi thô thật của VietnamWorks, run
RUN_20261027T172150Z_deff14c_vwonly):

    deep_normalize_record() sinh bản ghi NESTED (job_info.job_title,
    company.company_name, skills.skills_list, location.primary_city),
    nhưng TargetSchemaFormatter.format_record() lại đi tìm các tên khác
    (job_info.title, company.name, skills.hard_skills, primary_city ở root).

    Kết quả trước khi sửa: title/company/province/hard_skills/job_family
    đều về 0/899 trên Golden Master, trong khi staging có 931/931.

Các test dưới đây cố ý dùng ĐÚNG hình thái nested mà pipeline thật đẩy vào
formatter (test cũ chỉ dùng shape phẳng nên không bao giờ bắt được lỗi).
"""

from __future__ import annotations

import copy

import pytest

from preprocessing.normalization.target_schema_formatter import (
    CANONICAL_ROOT_KEYS,
    TargetSchemaFormatter,
    is_unknown,
)


def make_deep_normalized_record() -> dict:
    """Shape THẬT do deep_normalize_record(keep_raw=False) trả về.

    Lấy từ bản ghi thật vietnamworks_2111943 (data/transformation/raw_for_outlier.json).
    """
    return {
        "job_id_global": "vietnamworks_2111943",
        "source_platform": "vietnamworks",
        "source_job_id": "2111943",
        "source_url": "https://www.vietnamworks.com/marketing-manager-2111943",
        "crawled_at_iso": "2026-10-16",
        "job_info": {
            "job_title": "Marketing Manager (IT Domain required)",
            "standardized_job_family": "JF10_PROD_BA",
            "standardized_seniority": "Lead/Manager",
            "employment_type": "Full-time",
            "work_mode": "Onsite",
            "min_experience_years": 10.0,
            "headcount": 1,
        },
        "company": {
            "company_name": "Nakivo",
            "company_name_normalized": "nakivo",
            "company_scale": "100-499",
            "company_scale_tier": "Medium",
            "company_address": "TGIS Building, 208 Nguyen Trai, Quan 1",
            "company_industry": "Phần Mềm CNTT/Dịch Vụ Phần Mềm",
        },
        "location": {
            "primary_city": "Hồ Chí Minh",
            "cities_list": ["Hồ Chí Minh", "Hà Nội"],
            "districts_list": ["Quận 1"],
            "detailed_locations": [
                {"province": "Hồ Chí Minh", "district": "Quận 1", "full_address": "208 Nguyễn Trãi, Quận 1"},
                {"province": "Hà Nội", "district": None, "full_address": "Hà Nội"},
            ],
            "geo_coordinates": {"lat": 10.76, "lon": 106.66},
        },
        "salary": {
            "salary_text": "30 - 45 triệu",
            "salary_min_vnd": 30000000.0,
            "salary_max_vnd": 45000000.0,
            "salary_currency_original": "VND",
            "pay_period": "month",
            "is_negotiable": False,
            "salary_source": "explicit_range",
            "is_outlier_capped": False,
            "is_salary_winsorized": False,
            "log_salary_max": 17.6,
        },
        "skills": {
            "skills_list": ["B2B Marketing", "Digital Marketing", "PR Content", "ROI Analysis"],
            "skills_count": 4,
            "soft_skills": ["Giao tiếp"],
            "domain_skills": ["SaaS"],
        },
        "requirements": {
            "standardized_education": "Đại học",
            "age_min": None,
            "age_max": None,
            "is_saturday_work": False,
        },
        "jd_text": {
            "description_text": "Xây dựng chiến lược marketing cho sản phẩm SaaS B2B.",
            "requirements_text": "Tối thiểu 10 năm kinh nghiệm marketing.",
            "benefits_text": ["Bảo hiểm đầy đủ", "Lương tháng 13"],
        },
        "date": {
            "posted_date": "2026-10-16",
            "updated_date": "2026-10-16",
            "deadline_date": "2026-11-30",
        },
        "nlp_metadata": {"word_count": 120, "char_count": 800, "primary_language": "vi",
                         "is_stub_jd": False, "is_content_image": False},
        "governance": {
            "quality_score": 0.93,
            "imputed_fields": [],
            "is_golden_merged": True,
            "duplicate_count": 3,
            "duplicate_platforms": ["vietnamworks", "topcv"],
            "duplicate_job_ids": ["vietnamworks_2111943", "topcv_1", "topcv_2"],
        },
    }


# --------------------------------------------------------------------- 11 keys
def test_nested_input_still_yields_exactly_11_root_keys():
    out = TargetSchemaFormatter.format_record(make_deep_normalized_record())
    assert set(out.keys()) == set(CANONICAL_ROOT_KEYS)
    assert len(out) == 11


# ------------------------------------------------- regression: field survival
@pytest.mark.parametrize(
    "path,expected",
    [
        (("job_info", "title"), "Marketing Manager (IT Domain required)"),
        (("job_info", "job_family"), "JF10_PROD_BA"),
        (("job_info", "work_type"), "Full-time"),
        (("job_info", "working_model"), "Onsite"),
        (("company", "name"), "Nakivo"),
        (("company", "industry"), "Phần Mềm CNTT/Dịch Vụ Phần Mềm"),
        (("company", "size"), "100-499"),
        (("requirements", "standardized_seniority"), "lead/manager"),
        (("requirements", "standardized_education"), "đại học"),
    ],
)
def test_deep_normalized_fields_survive_packaging(path, expected):
    """Mọi giá trị thật từ Deep Normalizer phải còn nguyên trong Golden."""
    out = TargetSchemaFormatter.format_record(make_deep_normalized_record())
    node = out
    for key in path:
        node = node[key]
    if isinstance(expected, str):
        assert node is not None, f"{path} bị mất (None) — đúng lỗi dữ liệu đã audit"
        assert str(node).strip().lower() == expected.lower()
    else:
        assert node == expected


def test_hard_skills_are_not_silently_dropped():
    out = TargetSchemaFormatter.format_record(make_deep_normalized_record())
    assert out["skills"]["hard_skills"] == ["B2B Marketing", "Digital Marketing", "PR Content", "ROI Analysis"]
    assert out["skills"]["domain_skills"] == ["SaaS"]


def test_salary_numbers_survive():
    out = TargetSchemaFormatter.format_record(make_deep_normalized_record())
    assert out["salary"]["salary_min"] == 30000000.0
    assert out["salary"]["salary_max"] == 45000000.0
    assert out["salary"]["is_salary_negotiable"] is False


def test_experience_survives_from_nested_job_info():
    out = TargetSchemaFormatter.format_record(make_deep_normalized_record())
    assert out["requirements"]["experience_years"] == 10.0


# ------------------------------------------------------ multi-value locations
def test_multi_location_record_keeps_all_provinces():
    """Một tin có nhiều địa điểm phải giữ ĐỦ, không cắt lấy phần tử đầu."""
    out = TargetSchemaFormatter.format_record(make_deep_normalized_record())
    provinces = {loc["province"] for loc in out["locations"]}
    assert len(out["locations"]) == 2
    assert "Hồ Chí Minh" in provinces
    assert "Hà Nội" in provinces, "Địa điểm thứ hai bị mất khi đóng gói"


def test_flat_record_still_supported_for_backward_compatibility():
    """Shape phẳng của staging cũ phải còn hoạt động (không hồi quy tương thích)."""
    flat = {
        "job_id_global": "topcv_flat_1",
        "source_platform": "topcv",
        "job_title": "Java Developer",
        "company_name": "ABC Corp",
        "primary_city": "Hà Nội",
        "skills_list": ["Java"],
        "salary_min_vnd": 20000000.0,
        "salary_max_vnd": 35000000.0,
        "raw_description_text": "Mô tả công việc cũ",
    }
    out = TargetSchemaFormatter.format_record(flat)
    assert out["job_info"]["title"] == "Java Developer"
    assert out["company"]["name"] == "ABC Corp"
    assert out["skills"]["hard_skills"] == ["Java"]
    assert out["locations"][0]["province"] == "Hà Nội"


# ------------------------------------------------ no fabricated placeholders
def test_no_invented_placeholder_when_values_are_genuinely_unknown():
    """Không được bịa 'Chưa xác định'/'fulltime'/'middle' khi dữ liệu thật sự thiếu."""
    rec = make_deep_normalized_record()
    rec["job_info"]["job_title"] = None
    rec["company"]["company_name"] = None
    rec["location"] = {}
    rec["job_info"]["employment_type"] = None
    rec["job_info"]["work_mode"] = None
    rec["requirements"]["standardized_education"] = None
    rec["jd_text"] = {"description_text": None, "requirements_text": None, "benefits_text": []}

    out = TargetSchemaFormatter.format_record(rec)
    assert out["job_info"]["title"] is None
    assert out["company"]["name"] is None
    assert out["job_info"]["work_type"] is None, "work_type bị mặc định 'fulltime'"
    assert out["requirements"]["standardized_seniority"] is None, "seniority bị mặc định 'middle'"
    assert out["locations"] == [], "Sinh ra dòng địa điểm giả khi không có bằng chứng"
    assert out["jd_text"]["description"] is None, "JD bị bịa text 'Tuyển dụng ...'"


def test_sentinel_from_upstream_is_normalized_to_null():
    """Sentinel 'Chưa xác định' do tầng trước ghi ra không được thành dữ liệu hợp lệ."""
    rec = make_deep_normalized_record()
    rec["location"]["detailed_locations"] = [
        {"province": "Hà Nội", "district": "Chưa xác định", "full_address": "Hà Nội"}
    ]
    out = TargetSchemaFormatter.format_record(rec)
    assert out["locations"][0]["district"] is None
    assert out["locations"][0]["province"] == "Hà Nội"


def test_zero_experience_is_not_confused_with_unknown():
    """first_known() phải phân biệt 0.0 với None (khác `or`)."""
    rec = make_deep_normalized_record()
    rec["job_info"]["min_experience_years"] = 0.0
    rec["requirements"] = {"standardized_education": None}
    out = TargetSchemaFormatter.format_record(rec)
    assert out["requirements"]["experience_years"] == 0.0


# ------------------------------------------------------- provenance sidecar
def test_extract_provenance_preserves_dedup_metadata():
    """Formatter cắt về 11 khóa, nên provenance phải được trích trước đó."""
    rec = make_deep_normalized_record()
    prov = TargetSchemaFormatter.extract_provenance(rec)
    assert prov["job_id_global"] == "vietnamworks_2111943"
    assert prov["quality_score"] == 0.93
    assert prov["is_golden_merged"] is True
    assert prov["duplicate_count"] == 3
    assert prov["duplicate_platforms"] == ["vietnamworks", "topcv"]
    assert len(prov["duplicate_job_ids"]) == 3


def test_format_record_does_not_leak_governance_into_golden():
    out = TargetSchemaFormatter.format_record(make_deep_normalized_record())
    for forbidden in ("governance", "nlp_metadata", "quality_score", "duplicate_job_ids", "is_outlier_capped"):
        assert forbidden not in out


def test_provenance_survives_deep_copy_of_record():
    """extract_provenance không được biến đổi bản ghi gốc (pure function)."""
    rec = make_deep_normalized_record()
    snapshot = copy.deepcopy(rec)
    TargetSchemaFormatter.extract_provenance(rec)
    assert rec == snapshot


# -------------------------------------------------------------------- helpers
def test_is_unknown_covers_sentinels_and_nan():
    for val in [None, "", "  ", "Chưa xác định", "N/A", "null", float("nan"), [], {}, set()]:
        assert is_unknown(val) is True, val
    assert is_unknown("Hà Nội") is False
    assert is_unknown(0) is False
    assert is_unknown(0.0) is False
    assert is_unknown(False) is False


def test_to_flat_target_record_exposes_all_provinces():
    out = TargetSchemaFormatter.format_record(make_deep_normalized_record())
    flat = TargetSchemaFormatter.to_flat_target_record(out)
    assert flat["primary_city"] == "Hồ Chí Minh"
    assert set(flat["all_provinces"]) == {"Hồ Chí Minh", "Hà Nội"}
    assert flat["location_count"] == 2
    assert flat["skills_count"] == 4
    assert flat["working_model"] == "Onsite"
