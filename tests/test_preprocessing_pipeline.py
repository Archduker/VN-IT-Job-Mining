# -*- coding: utf-8 -*-
"""tests/test_preprocessing_pipeline.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Bộ kiểm thử toàn diện cho hệ thống Tiền xử lý dữ liệu (VN-IT-Job-Mining).

Kiểm thử:
  - Ép phẳng JSON đa nguồn (json_flattener) với skills_list dạng list[str].
  - Bóc tách dải lương & cascade lương ẩn trong JD (salary_parser).
  - Bóc trần null markers trá hình (sneaky_null_detector).
  - Kiểm tra và sửa lỗi nhập liệu số, Winsorization (outlier_handler).
  - Chuẩn hóa văn bản, địa danh, cấp bậc (text_cleaner).
"""

import json
import os
import pytest
import pandas as pd

from preprocessing.integration.json_flattener import flatten_raw_job_record
from preprocessing.transformation.salary_parser import UniversalSalaryParser, parse_salary_cascade
from preprocessing.missing_outlier.sneaky_null_detector import is_val_null, detect_null_type
from preprocessing.missing_outlier.outlier_handler import detect_iqr_outliers, fix_common_salary_input_errors, winsorize_series
from preprocessing.normalization.text_cleaner import clean_job_title, normalize_city, normalize_seniority


def test_flatten_sources_samples():
    """Kiểm tra ép phẳng JSON trên mẫu thực tế của 8 sàn."""
    sample_files = {
        "careerviet": "data/careerviet/raw/2026-10-20/35C8AEA1_v1.json",
        "glints": "data/glints/raw/2026-10-20/f28b7d28-bc1d-41bb-9e15-2d80bd4ca47c_v1.json",
        "itviec": "data/itviec/raw/2026-10-19/ho-chi-minh-full-stack-developer-reactjs-nodejs-one-tech-stop-vietnam-company-ltd-2723_v1.json",
        "jobsgo": "data/jobsgo/raw/2026-10-20/29104590387_v1.json",
        "topcv": "data/topcv/raw/2026-10-20/2324170_v1.json",
        "topdev": "data/topdev/raw/2026-10-20/2139491_v1.json",
        "vieclam24h": "data/vieclam24h/raw/2026-10-20/200969132_v1.json",
        "vietnamworks": "data/vietnamworks/raw/2026-10-20/2114692_v1.json",
    }

    for source, path in sample_files.items():
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            flat = flatten_raw_job_record(raw_data)

            # Kiểm tra định danh toàn cục
            assert flat["job_id_global"].startswith(source)
            assert flat["source_platform"] == source
            assert flat["job_title"] is not None

            # Kiểm tra định dạng mảng của skills_list
            assert isinstance(flat["skills_list"], list)
            assert isinstance(flat["benefits_list"], list)


def test_salary_parser_vnd_and_usd():
    """Kiểm tra bóc tách mức lương VNĐ và ngoại tệ USD."""
    # Test VNĐ triệu
    res1 = UniversalSalaryParser.parse_text("15 - 25 triệu")
    assert res1["salary_min_vnd"] == 15_000_000.0
    assert res1["salary_max_vnd"] == 25_000_000.0
    assert res1["is_negotiable"] is False

    # Test USD
    res2 = UniversalSalaryParser.parse_text("1,000 - 2,000 USD")
    assert res2["salary_min_vnd"] == 1_000 * 25_400.0
    assert res2["salary_max_vnd"] == 2_000 * 25_400.0
    assert res2["salary_currency_original"] == "USD"

    # Test lương năm
    res3 = UniversalSalaryParser.parse_text("360 triệu / năm")
    assert res3["salary_max_vnd"] == 30_000_000.0
    assert res3["pay_period"] == "year"

    # Test thỏa thuận
    res4 = UniversalSalaryParser.parse_text("Thỏa thuận")
    assert res4["is_negotiable"] is True
    assert res4["salary_min_vnd"] is None


def test_cascade_salary_extractor():
    """Kiểm tra cơ chế quét lương ẩn trong thân bài JD khi header là thỏa thuận."""
    header = "Thỏa thuận"
    jd = "Chúng tôi tìm kiếm Kỹ sư AI. Mức thu nhập upto 20-25 triệu/tháng kèm theo thưởng dự án."

    res = parse_salary_cascade(header, jd)
    assert res["salary_min_vnd"] == 20_000_000.0
    assert res["salary_max_vnd"] == 25_000_000.0
    assert res["salary_source"] == "jd_regex"
    assert res.get("is_salary_negotiable_declared") is True


def test_sneaky_null_detector():
    """Kiểm tra bóc trần các null marker ngụy trang."""
    assert is_val_null("") is True
    assert is_val_null("   ") is True
    assert is_val_null("nan") is True
    assert is_val_null("null") is True
    assert is_val_null("thỏa thuận") is True
    assert is_val_null("cạnh tranh") is True
    assert is_val_null(0) is True
    assert is_val_null("0") is True
    assert is_val_null([]) is True
    assert is_val_null({}) is True
    assert is_val_null("Python Developer") is False
    assert is_val_null(25000000) is False


def test_outlier_handling_and_winsorization():
    """Kiểm tra sửa lỗi nhập liệu số và kỹ thuật Winsorization."""
    # Sửa lỗi nhầm USD vào ô VNĐ
    fixed_usd = fix_common_salary_input_errors(2000.0)
    assert fixed_usd == 2000.0 * 25_400.0

    # Sửa lỗi lương năm vào ô lương tháng
    fixed_annual = fix_common_salary_input_errors(360_000_000.0, "Thu nhập năm cho vị trí Senior")
    assert fixed_annual == 30_000_000.0

    # Winsorization
    s = pd.Series([10_000_000, 15_000_000, 20_000_000, 25_000_000, 500_000_000])
    w = winsorize_series(s, lower_pct=0.05, upper_pct=0.95)
    assert w.max() < 500_000_000
    assert len(w) == len(s)  # Không drop bản ghi nào


def test_text_normalization():
    """Kiểm tra chuẩn hóa tiêu đề, địa danh và cấp bậc."""
    # Clean job title
    assert clean_job_title("[HN/HCM] Senior Java Developer") == "Senior Java Developer"
    assert clean_job_title("Python Developer - Lương 20-25M") == "Python Developer"

    # Normalize city
    assert normalize_city("Quận 1, TP.HCM") == "Hồ Chí Minh"
    assert normalize_city("Cầu Giấy, Hà Nội") == "Hà Nội"
    assert normalize_city("Làm việc từ xa (Remote)") == "Remote"

    # Normalize seniority
    assert normalize_seniority("Thực tập sinh", "Intern Python") == "Intern"
    assert normalize_seniority("Senior", "Senior Data Engineer") == "Senior"
    assert normalize_seniority("Trưởng nhóm", "Team Lead") == "Lead/Manager"
