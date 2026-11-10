from __future__ import annotations

import pandas as pd
import pytest

from preprocessing.normalization.location_normalizer import (
    get_province_count,
    normalize_location,
    normalize_location_from_fields,
)
from preprocessing.normalization.skill_normalizer import (
    extract_skills,
    get_taxonomy_skill_count,
    taxonomy_lookup,
)
from preprocessing.transformation.experience_parser import (
    UNKNOWN_SENIORITY,
    normalize_seniority,
    parse_experience_range,
)
from preprocessing.transformation.job_family_classifier import (
    JOB_FAMILIES,
    classify_job_family,
)
from preprocessing.transformation.pipeline import partition_salary_subsets, transform_dataframe
from preprocessing.transformation.salary_parser import parse_salary


# Salary parser: ranges, open bounds, locale separators, currency and periods.
@pytest.mark.parametrize(
    ("raw", "expected_min", "expected_max", "expected_avg", "status"),
    [
        ("15 - 25 triệu", 15.0, 25.0, 20.0, "range"),
        ("$1,500 - $3,000", 38.1, 76.2, 57.15, "range"),
        ("Lên đến 40 triệu", None, 40.0, 40.0, "upper_bound"),
        ("Từ 20tr", 20.0, None, 20.0, "lower_bound"),
        ("9e+06 - 2e+07 VND / month", 9.0, 20.0, 14.5, "range"),
        ("60,000 USD/year", 127.0, 127.0, 127.0, "single_value"),
        ("15 - 25 triệu/tháng", 15.0, 25.0, 20.0, "range"),
        ("100,000 VND/day", 2.2, 2.2, 2.2, "single_value"),
        ("100,000 VND/hour", 16.0, 16.0, 16.0, "single_value"),
        ("8,5 triệu", 8.5, 8.5, 8.5, "single_value"),
        ("1.000 - 2.500 USD", 25.4, 63.5, 44.45, "range"),
    ],
)
def test_salary_numeric_cases(raw, expected_min, expected_max, expected_avg, status):
    result = parse_salary(raw)
    assert result.salary_min == pytest.approx(expected_min) if expected_min is not None else result.salary_min is None
    assert result.salary_max == pytest.approx(expected_max) if expected_max is not None else result.salary_max is None
    assert result.salary_avg == pytest.approx(expected_avg) if expected_avg is not None else result.salary_avg is None
    assert result.parse_status == status


def test_salary_dictionary_string_and_scientific_notation():
    raw = (
        "{'salary_text': '9e+06 - 2e+07 VND / month', "
        "'salary_min': 9000000.0, 'salary_max': 20000000.0, "
        "'salary_currency': 'VND', 'pay_period': 'MONTH', 'is_negotiable': False}"
    )
    result = parse_salary(raw)
    assert (result.salary_min, result.salary_max, result.salary_avg) == (9.0, 20.0, 14.5)
    assert result.is_negotiable is False


def test_negotiable_text_overrides_false_crawler_flag():
    raw = "{'salary_text': 'Thương lượng', 'salary_min': None, 'salary_max': None, 'is_negotiable': False}"
    result = parse_salary(raw)
    assert result.is_negotiable is True
    assert result.salary_min is result.salary_max is result.salary_avg is None
    assert result.parse_status == "negotiable"


def test_negotiable_english_and_vietnamese():
    for value in ("Thỏa thuận", "Thương lượng", "Negotiable", "Competitive salary", "Cạnh tranh"):
        result = parse_salary(value)
        assert result.is_negotiable
        assert result.salary_avg is None


def test_project_period_is_not_converted_to_monthly_salary():
    result = parse_salary("{'salary_text': '1e+06 - 2e+06 VND / project', 'salary_currency': 'VND', 'pay_period': 'PROJECT'}")
    assert result.parse_status == "unsupported_period"
    assert result.salary_min is result.salary_max is result.salary_avg is None


def test_structured_numeric_fallback_when_salary_text_missing():
    result = parse_salary({"salary_min": 9_000_000, "salary_max": 20_000_000, "salary_currency": "VND", "pay_period": "MONTH"})
    assert result.salary_min == 9
    assert result.salary_max == 20


# Experience bounds and no-invention rules.
@pytest.mark.parametrize(
    ("raw", "minimum", "maximum", "status"),
    [
        ("1-3 năm", 1.0, 3.0, "range"),
        ("2 - 5 years", 2.0, 5.0, "range"),
        ("Tối thiểu 3 năm", 3.0, None, "lower_bound"),
        ("5+ years", 5.0, None, "lower_bound"),
        ("Up to 3 years", 0.0, 3.0, "upper_bound"),
        ("Không yêu cầu kinh nghiệm", 0.0, None, "explicit_zero"),
        ("10 năm", 10.0, None, "single_value"),
        ("2D Rigger", None, None, "unparsed"),
        (None, None, None, "missing"),
    ],
)
def test_experience_cases(raw, minimum, maximum, status):
    result = parse_experience_range(raw)
    assert result[0] == minimum
    assert result[1] == maximum
    assert result[2] == status


def test_experience_can_be_found_in_requirements_text():
    result = parse_experience_range(None, "Minimum 3 years of experience with Python")
    assert result[:2] == (3.0, None)


def test_seniority_ordinal_mapping_and_ambiguous_staff_label():
    assert normalize_seniority("Intern Developer", "Nhân viên", None) == 0
    assert normalize_seniority("Marketing Manager", "Trưởng phòng", 10) == 4
    assert normalize_seniority("Senior Backend Developer", "Nhân viên", 1) == 3
    assert normalize_seniority("Backend Developer", "Nhân viên", 1) == 1
    assert normalize_seniority("Backend Developer", "Nhân viên", None) == UNKNOWN_SENIORITY


# Location normalization.
def test_province_dictionary_has_34_units():
    assert get_province_count() == 34


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("TP HCM", "Hồ Chí Minh"),
        ("TP. Hồ Chí Minh", "Hồ Chí Minh"),
        ("Sài Gòn", "Hồ Chí Minh"),
        ("HN", "Hà Nội"),
        ("Hanoi", "Hà Nội"),
        ("Hòa Lạc", "Hà Nội"),
        ("Khu công nghệ cao Hòa Lạc", "Hà Nội"),
        ("Hà Giang", "Tuyên Quang"),
        ("Quảng Nam", "Đà Nẵng"),
        ("Bình Dương", "Hồ Chí Minh"),
        ("Remote work", "Remote"),
        ("Toàn quốc", "Toàn quốc"),
    ],
)
def test_location_aliases(raw, expected):
    assert normalize_location(raw) == expected


def test_location_multiple_addresses_same_province():
    raw = ["208 Nguyen Trai, Ho Chi Minh City", "District 1, Thành phố Hồ Chí Minh"]
    assert normalize_location(raw) == "Hồ Chí Minh"


def test_location_multiple_provinces_is_not_arbitrarily_selected():
    assert normalize_location(["Hà Nội", "TP HCM"]) == "Nhiều địa điểm"


def test_location_fallback_prefers_working_locations_then_company_address():
    assert normalize_location_from_fields([], None, "Company address, Hanoi") == "Hà Nội"
    assert normalize_location_from_fields(["Hòa Lạc, Hà Nội"], "TP HCM", None) == "Hà Nội"


# Skill taxonomy and false-positive protection.
def test_taxonomy_six_categories_and_baseline_count():
    assert get_taxonomy_skill_count() == 92


def test_skill_alias_lookup():
    assert taxonomy_lookup("golang")["canonical"] == "Go"
    assert taxonomy_lookup("k8s")["canonical"] == "Kubernetes"
    assert taxonomy_lookup("reactjs")["canonical"] == "React"


def test_short_skills_do_not_match_ordinary_english():
    skills = extract_skills("Good communication is required. We need to go further next week.")
    assert "Go" not in skills
    assert "Artificial Intelligence" not in skills
    assert "Next.js" not in skills


def test_short_skills_match_technical_context():
    assert "Go" in extract_skills("Backend developer: build microservices with Go")
    assert "C" in extract_skills("Embedded C programming for firmware")
    assert "R" in extract_skills("Data analysis with RStudio and tidyverse")
    assert "Artificial Intelligence" in extract_skills("AI Engineer working with PyTorch")


def test_ambiguous_common_aliases_need_context():
    assert "REST API" not in extract_skills("Please take a rest after work")
    assert "Spring Boot" not in extract_skills("Spring is a nice season")
    assert "Node.js" not in extract_skills("A node in a tree")
    assert "Spark" not in extract_skills("A spark of creativity")
    assert "Next.js" not in extract_skills("We will meet next week")


def test_contextual_aliases_match_technical_phrases():
    assert "REST API" in extract_skills("Design REST API endpoints")
    assert "Spring Boot" in extract_skills("Java Spring Boot microservices")
    assert "Node.js" in extract_skills("Node.js backend runtime")
    assert "Spark" in extract_skills("Apache Spark data processing")
    assert "Next.js" in extract_skills("Next.js App Router")


# Job family classification per the Duy task handbook.
@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Java Backend Developer", "Backend"),
        ("React Frontend Developer", "Frontend"),
        ("Android Developer", "Mobile"),
        ("DevOps Engineer", "DevOps/Cloud"),
        ("Data Scientist", "Data/AI"),
        ("QA Engineer", "QA/QC"),
        ("Cybersecurity Specialist", "Security"),
        ("Business Analyst", "BA"),
        ("Product Manager", "Product"),
        ("System Administrator", "System"),
        ("Embedded System Test Engineer", "Embedded"),
    ],
)
def test_job_family_title_rules(title, expected):
    assert classify_job_family(title) == expected


def test_fullstack_requires_backend_and_frontend_skills():
    assert classify_job_family("Fullstack Developer", ["Java", "React"]) == "Fullstack"
    assert classify_job_family("Fullstack Developer", ["Java", "Spring Boot"]) == "Backend"
    assert classify_job_family("Fullstack Developer", ["React", "TypeScript"]) == "Frontend"
    assert classify_job_family("Fullstack Developer", []) is None


def test_generic_title_requires_it_category_and_two_skills():
    assert classify_job_family("Specialist", ["Python", "TensorFlow"], category="Information Technology") == "Data/AI"
    assert classify_job_family("Specialist", ["Python", "TensorFlow"], category="Human Resources") is None


def test_handbook_has_exactly_twelve_families():
    assert len(JOB_FAMILIES) == 12
    assert "Embedded" in JOB_FAMILIES
    assert "System" in JOB_FAMILIES


# DataFrame integration against the user's real column names.
def test_transform_dataframe_uses_integrated_silver_schema_and_preserves_rows():
    glints_payload = (
        "{'salary_text': '9e+06 - 2e+07 VND / month', 'salary_min': 9000000.0, "
        "'salary_max': 20000000.0, 'salary_currency': 'VND', 'pay_period': 'MONTH', 'is_negotiable': False}"
    )
    frame = pd.DataFrame([
        {
            "job_id_global": "g1", "source_platform": "glints",
            "job_title": "Fullstack Developer", "raw_salary_text": glints_payload,
            "raw_experience_text": "1-3 năm", "raw_seniority_text": "Nhân viên",
            "working_locations": ["208 Nguyen Trai, Ho Chi Minh City"],
            "company_address": None, "raw_category_text": "Information Technology",
            "skills_list": ["Java", "React"],
            "raw_description_text": "Build backend APIs and React interfaces",
            "raw_requirements_text": "Experience 1-3 years",
        },
        {
            "job_id_global": "v1", "source_platform": "vietnamworks",
            "job_title": "Embedded System Test Engineer", "raw_salary_text": "Thương lượng",
            "raw_experience_text": "10 năm", "raw_seniority_text": "Giám đốc và Cấp Cao Hơn",
            "working_locations": [], "raw_location_text": None,
            "company_address": "Khu công nghệ cao Hòa Lạc, Hà Nội",
            "raw_category_text": "Information Technology", "skills_list": ["C", "RTOS"],
            "raw_description_text": "Embedded firmware testing with C programming",
            "raw_requirements_text": "10 years of experience",
        },
    ])
    output = transform_dataframe(frame)
    assert len(output) == len(frame)
    assert output.loc[0, "salary_min"] == 9.0
    assert output.loc[0, "salary_max"] == 20.0
    assert output.loc[1, "is_negotiable"]
    assert pd.isna(output.loc[1, "salary_avg"])
    assert output.loc[0, "exp_min_years"] == 1.0
    assert output.loc[0, "exp_max_years"] == 3.0
    assert output.loc[0, "seniority_level"] == 1
    assert output.loc[1, "seniority_level"] == 4
    assert output.loc[0, "city_normalized"] == "Hồ Chí Minh"
    assert output.loc[1, "city_normalized"] == "Hà Nội"
    assert output.loc[0, "job_family"] == "Fullstack"
    assert output.loc[1, "job_family"] == "Embedded"
    assert set(output["skills_extracted"].iloc[0]) >= {"Java", "React"}


def test_salary_partition_keeps_all_records_in_subset_b_and_never_imputes():
    frame = pd.DataFrame({
        "salary_min": [15.0, None, None],
        "salary_max": [25.0, None, None],
        "is_negotiable": [False, True, False],
    })
    subset_a, subset_b = partition_salary_subsets(frame)
    assert len(subset_a) == 1
    assert len(subset_b) == 3
    assert subset_b.loc[1, "salary_min"] is None or pd.isna(subset_b.loc[1, "salary_min"])



def test_salary_unsupported_weekly_period_is_not_assumed_monthly():
    result = parse_salary("500 USD/week")
    assert result.parse_status == "unsupported_period"
    assert result.salary_avg is None


def test_salary_unsupported_currency_is_not_mislabeled_vnd():
    result = parse_salary("2,000 EUR/month")
    assert result.parse_status == "unsupported_currency"
    assert result.salary_avg is None
