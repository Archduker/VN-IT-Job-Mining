# -*- coding: utf-8 -*-
"""Các lỗi tìm thấy khi review P2–P5 ngày 03/11/2026, mỗi test dùng đúng ví dụ sai trên dữ liệu thật."""

from __future__ import annotations

import json

import pytest

from preprocessing.normalization.text_cleaner import classify_seniority
from preprocessing.transformation.salary_parser import parse_salary_cascade
from preprocessing.transformation.skill_extractor import extract_skills_from_text
from preprocessing.transformation.text_metrics import detect_jd_language


@pytest.mark.parametrize("title", [
    "Chuyên viên Quản lý chất lượng dữ liệu (2026TD450981)",
    "Chuyên Viên Ứng Dụng Microsoft 365 & AI",
    "2 AI Engineer",
    "CVCC Bán Sản Phẩm Cho Vay - Bình Dương - TA186",
    "Chuyên viên cao cấp Quan hệ khách hàng Doanh nghiệp - Bậc 1 (RM)",
])
def test_title_numbers_without_money_unit_are_not_salary(title):
    r = parse_salary_cascade("Thỏa thuận", title=title, jd_text="")
    assert r["salary_source"] == "none" and r["salary_max_vnd"] is None


def test_title_salary_ignores_years_of_experience():
    r = parse_salary_cascade(None, title="Business Analyst (2+ Năm Kinh Nghiệm) - Upto 35 Triệu", jd_text="")
    assert (r["salary_source"], r["salary_min_vnd"], r["salary_max_vnd"]) == ("title", None, 35_000_000.0)


def test_salary_outside_monthly_bounds_is_suspect():
    r = parse_salary_cascade("300 - 900 triệu")
    assert r["salary_suspect"] is True and r["salary_min_vnd"] is None and r["salary_max_vnd"] is None


def test_single_letter_skill_needs_context():
    assert extract_skills_from_text("Nhân viên kinh doanh, làm việc tại tòa nhà C") == []
    assert "C" in extract_skills_from_text("Thành thạo C/C++ cho hệ nhúng")
    assert "Golang" not in extract_skills_from_text("Ready to go the extra mile")


def test_nhan_vien_is_not_a_level():
    assert classify_seniority("Nhân viên", "Kế toán tổng hợp", None) == (None, None)
    assert classify_seniority("Nhân Viên/Chuyên Viên", "Backend Developer", 3.0) == ("Middle", "kinh_nghiem")


def test_language_is_decided_on_jd_only():
    en = ("Responsibilities: design REST APIs with Python and maintain CI/CD pipelines for our platform. " * 8
          + "\nBằng cấp / Education: Bachelor degree in Computer Science.")
    topcv_header = "Chi tiết công việc Backend Developer tại Công ty Cổ phần ABC " + en
    assert detect_jd_language(en) == "en"
    assert detect_jd_language(topcv_header, "Backend Developer", "Công ty Cổ phần ABC") == "en"
    assert detect_jd_language("Tham gia phát triển hệ thống phần mềm quản lý cho khu du lịch.") == "vi"


def test_header_with_thousand_separators():
    r = parse_salary_cascade("Up to 40.000.000 VND")
    assert (r["salary_max_vnd"], r["salary_suspect"]) == (40_000_000.0, False)


@pytest.mark.parametrize("text,lo,hi", [
    ("From 9.000.000 VND", 9_000_000.0, None),
    ("0 - 30000000 VND", None, 30_000_000.0),
    ("Trưởng nhóm 20 - 30", 20_000_000.0, 30_000_000.0),
])
def test_header_unit_and_zero_bounds(text, lo, hi):
    r = parse_salary_cascade(text)
    assert (r["salary_min_vnd"], r["salary_max_vnd"], r["salary_suspect"]) == (lo, hi, False)


def test_quan_ly_in_title_is_a_job_not_a_level():
    assert classify_seniority(None, "Kỹ Sư Quản Lý Dự Án - PC Junior", None) == ("Junior", "title")


def test_vietnamese_word_ai_is_not_machine_learning():
    from preprocessing.transformation.skill_extractor import extract_skills_from_text
    assert "Machine Learning" not in extract_skills_from_text("Ứng viên là ai cũng được, bất kỳ ai yêu thích lập trình")
    assert "Machine Learning" in extract_skills_from_text("Kinh nghiệm xây dựng mô hình trí tuệ nhân tạo")


@pytest.mark.parametrize("sen,lo,hi,expected", [
    ("Senior", 0.0, 1.0, True), ("Senior", 5.0, None, False), ("Thực tập", 3.0, 5.0, True),
    ("Junior", 0.0, 1.0, False), ("Senior", None, None, False),
])
def test_seniority_conflict_with_experience(sen, lo, hi, expected):
    from preprocessing.normalization.run import seniority_conflict
    assert seniority_conflict(sen, lo, hi) is expected
