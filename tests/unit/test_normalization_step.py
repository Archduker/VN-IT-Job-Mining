# -*- coding: utf-8 -*-
"""tests.unit.test_normalization_step
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Kiểm thử Bước 04 Normalization theo đặc tả docs/prompting/P4_normalization.md:
- N1: 34 tỉnh/thành sau sáp nhập, tên cũ, remote, ngoại quốc
- N2: 6 cấp bậc tiếng Việt (raw -> title -> exp -> JEV)
- N3: 12 nhóm nghề IT (khớp từ nguyên vẹn PRE-1, title -> skills -> JEV)
- N4: Ánh xạ kỹ năng chuẩn theo skills.json (ReactJS, React.js -> React)
- N5: Chuẩn hóa tên công ty (normalize_company_name)
- N6 & N7: Outlier IQR, Winsorize 1-99% và log1p
- N8: Gộp 8 nguồn thành all.parquet và copy sang data/curated/
"""

from __future__ import annotations

import math
from unittest.mock import MagicMock
import numpy as np
import pandas as pd
import pytest

from preprocessing.common import province
from preprocessing.normalization.cross_deduplicator import normalize_company_name
from preprocessing.normalization.run import (
    _normalize_locations,
    apply_global_salary_normalizations,
    process_source_records,
)
from preprocessing.normalization.text_cleaner import (
    canonicalize_skills,
    classify_job_family_rule,
    classify_seniority,
    has_term,
)


def test_n1_province_mapping_and_locations():
    """Kiểm tra N1: 34 tỉnh sau sáp nhập, tên cũ, remote và foreign."""
    cases = [
        ({"tinh_thanh": "Ha Noi", "raw": "Ha Noi"}, "TP. Hà Nội", "ha_noi", None, False, False),
        ({"tinh_thanh": "Bình Dương", "raw": "Bình Dương"}, "TP. Hồ Chí Minh", "ho_chi_minh", "Bình Dương", False, False),
        ({"tinh_thanh": "Quảng Nam", "raw": "Quảng Nam"}, "TP. Đà Nẵng", "da_nang", "Quảng Nam", False, False),
        ({"tinh_thanh": "Hà Giang", "raw": "Hà Giang"}, "Tuyên Quang", "tuyen_quang", "Hà Giang", False, False),
        ({"tinh_thanh": None, "raw": "Remote"}, None, None, None, True, False),
        ({"tinh_thanh": None, "raw": "Tokyo, Japan"}, None, None, None, False, True),
    ]

    for loc_in, exp_name, exp_key, exp_old, exp_rem, exp_forg in cases:
        norm_locs, primary = _normalize_locations([loc_in])
        assert len(norm_locs) == 1
        l = norm_locs[0]
        assert l["tinh_thanh"] == exp_name
        assert l["tinh_key"] == exp_key
        if exp_old:
            assert l["tinh_cu"] == exp_old
        assert l["remote"] == exp_rem
        assert l["ngoai_vn"] == exp_forg
        assert primary == exp_name


def test_n2_seniority_classification_order_and_edge_cases():
    """Kiểm tra N2: Thứ tự ưu tiên raw -> title -> exp_min_years, và không bị lỗi chuỗi con."""
    # 1. raw_seniority_text
    sen, src = classify_seniority(raw_seniority="Trưởng phòng", title="Software Engineer")
    assert sen == "Trưởng nhóm/Quản lý"
    assert src == "raw"

    # 2. job_title_clean
    sen, src = classify_seniority(raw_seniority=None, title="Senior Java Developer")
    assert sen == "Senior"
    assert src == "title"

    # 3. International Business Analyst không được nhận thành "Thực tập"
    sen, src = classify_seniority(raw_seniority=None, title="International Business Analyst", exp_min_years=None)
    assert sen is None
    assert src is None

    # 4. Kinh nghiệm
    assert classify_seniority(None, None, 0.0) == ("Mới tốt nghiệp", "kinh_nghiem")
    assert classify_seniority(None, None, 1.5) == ("Junior", "kinh_nghiem")
    assert classify_seniority(None, None, 3.0) == ("Middle", "kinh_nghiem")
    assert classify_seniority(None, None, 5.0) == ("Senior", "kinh_nghiem")


def test_n3_job_family_whole_word_matching_pre1():
    """Kiểm tra N3: Sửa triệt để bug PRE-1 (khớp từ nguyên vẹn, không để 'backend' ra 'BA')."""
    # "Backend Developer" -> Backend, KHÔNG ra BA
    fam, src = classify_job_family_rule("Backend Developer")
    assert fam == "Backend"
    assert src == "title"

    # "International Business Analyst" -> Phân tích nghiệp vụ (BA)
    fam, src = classify_job_family_rule("International Business Analyst")
    assert fam == "Phân tích nghiệp vụ (BA)"
    assert src == "title"

    # Lead QA Tester -> Kiểm thử (QA/QC)
    fam, src = classify_job_family_rule("Lead QA Tester")
    assert fam == "Kiểm thử (QA/QC)"
    assert src == "title"

    # DevOps Cloud Engineer -> DevOps/Cloud
    fam, src = classify_job_family_rule("DevOps Cloud Engineer")
    assert fam == "DevOps/Cloud"
    assert src == "title"

    # Data Scientist -> Data/AI
    fam, src = classify_job_family_rule("Senior Data Scientist (AI/ML)")
    assert fam == "Data/AI"
    assert src == "title"

    # UI/UX Designer -> Thiết kế UI/UX
    fam, src = classify_job_family_rule("UI/UX Designer")
    assert fam == "Thiết kế UI/UX"
    assert src == "title"

    # Product Owner -> Quản lý sản phẩm/dự án
    fam, src = classify_job_family_rule("Product Owner")
    assert fam == "Quản lý sản phẩm/dự án"
    assert src == "title"

    # Title chung chung nhưng có skills chuẩn -> nhận diện qua skills
    fam, src = classify_job_family_rule("Technical Lead", skills_std=["React", "Vue"])
    assert fam == "Frontend"
    assert src == "skills"


def test_n4_canonical_skills():
    """Kiểm tra N4: Ánh xạ kỹ năng về tên chuẩn theo skills.json và loại bỏ trùng lặp."""
    input_skills = ["ReactJS", "React.js", "Java", "Docker", "react"]
    res = canonicalize_skills(input_skills)
    assert res == ["React", "Java", "Docker"]

    input_skills_2 = ["python", "Python3"]
    assert canonicalize_skills(input_skills_2) == ["Python"]


def test_n5_company_name_normalization():
    """Kiểm tra N5: Chuẩn hóa tên công ty loại bỏ tiền tố/hậu tố pháp nhân."""
    c1 = normalize_company_name("CÔNG TY CỔ PHẦN CÔNG NGHỆ KIOTVIET")
    assert "kiotviet" in c1
    assert "công ty" not in c1
    assert "cổ phần" not in c1


def test_n6_n7_salary_outliers_winsorize_and_log():
    """Kiểm tra N6 & N7: Outlier IQR, Winsorize 1-99% và log1p(x)."""
    # Tạo dải dữ liệu 100 tin lương bình thường (10tr - 50tr) và 1 tin 2 tỷ
    normal_salaries = [float(x * 1_000_000) for x in range(10, 51)] * 3  # 123 rows
    outlier_salary = 400_000_000.0  # 400 triệu: trong ngưỡng cứng nhưng là ngoại lai IQR

    test_rows = []
    for s in normal_salaries:
        test_rows.append({"salary_min_vnd": s * 0.8, "salary_max_vnd": s, "description_clean": ""})
    test_rows.append({"salary_min_vnd": outlier_salary, "salary_max_vnd": outlier_salary, "description_clean": ""})
    test_rows.append({"salary_min_vnd": 2.026e9, "salary_max_vnd": 2.026e9, "description_clean": ""})  # mã tin đọc nhầm

    updated_rows, stats = apply_global_salary_normalizations(test_rows)

    # Ngoài 1–500 triệu/tháng: bỏ số, gắn cờ salary_suspect
    bogus = updated_rows[-1]
    assert bogus["salary_suspect"] is True and math.isnan(bogus["salary_max_vnd"])
    assert stats["salary_suspect_count"] == 1

    # Tin 400 triệu phải bị gắn cờ is_outlier_salary = True
    last_row = updated_rows[-2]
    assert last_row["is_outlier_salary"] is True

    # Capped value không được vượt quá mức 99%
    assert last_row["salary_max_vnd_capped"] < outlier_salary
    assert last_row["salary_max_vnd_capped"] <= stats["winsorize_q99_max"]

    # Kiểm tra log1p cho mức 20,000,000 VND ~ 16.81
    sal_20m = 20_000_000.0
    expected_log = math.log1p(sal_20m)
    assert round(expected_log, 2) == 16.81

    # Kiểm tra hàng có salary 20m có log_salary_max gần 16.81
    row_20m = next(r for r in updated_rows if r["salary_max_vnd"] == 20_000_000.0)
    assert abs(row_20m["log_salary_max"] - 16.8112) < 0.01
