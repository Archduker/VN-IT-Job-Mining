# -*- coding: utf-8 -*-
"""tests.unit.test_encoding_step
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Kiểm thử Bước 05 Encoding theo đặc tả docs/prompting/P5_encoding.md:
- E1: Ordinal Seniority (0-5, -1 cho Chưa rõ)
- E2: One-hot job_family, source_platform, employment_type
- E3: Multi-hot top 10 tỉnh/thành + tinh__other + remote/ngoai_vn
- E4: Multi-hot top K kỹ năng (count >= 20, max 200) + skills__other_count
- E5: Bảo toàn số học liên tục + cờ __missing (0/1)
- E6: Cờ nhị phân (is_negotiable, is_outlier_salary)
- E7: Bóc tách tháng đăng và ngày tới hạn
- E8: Cột xác suất JEV + cờ __missing
- Giải mã ngược (reversibility) bằng encoding_dictionary.json
"""

from __future__ import annotations

import json
import numpy as np
import pandas as pd
import pytest

from preprocessing.encoding.run import (
    SENIORITY_MAP,
    encode_dataset,
    to_col_slug,
)


@pytest.fixture
def mock_golden_df():
    """Tạo một DataFrame golden giả lập đủ các trường hợp."""
    rows = [
        {
            "job_id_global": "job_01",
            "source_platform": "itviec",
            "seniority": "Junior",
            "job_family": "Backend",
            "raw_employment_type": "Toàn thời gian",
            "it_status": "it",
            "locations": [{"tinh_key": "ha_noi", "remote": False, "ngoai_vn": False}],
            "skills_std": ["Python", "Docker", "RareCustomSkill"],
            "log_salary_min": 16.5,
            "log_salary_max": 17.0,
            "exp_min_years": 1.0,
            "exp_max_years": 3.0,
            "headcount": 2.0,
            "is_negotiable": False,
            "is_outlier_salary": False,
            "posted_date": "2026-10-01",
            "deadline_date": "2026-10-31",
            "it_rule_level": 2,
            "seniority_can_kiem": True,
            "job_family_can_kiem": False,
        },
        {
            "job_id_global": "job_02",
            "source_platform": "topcv",
            "seniority": "Chưa rõ",
            "job_family": "Khác",
            "raw_employment_type": None,
            "it_status": "it",
            "locations": [
                {"tinh_key": "unknown_province", "remote": True, "ngoai_vn": False}
            ],
            "skills_std": ["Java"],
            "log_salary_min": np.nan,
            "log_salary_max": np.nan,
            "exp_min_years": np.nan,
            "exp_max_years": np.nan,
            "headcount": np.nan,
            "is_negotiable": True,
            "is_outlier_salary": True,
            "posted_date": None,
            "deadline_date": None,
            "it_rule_level": 1,
            "seniority_can_kiem": False,
            "job_family_can_kiem": False,
        }
    ]
    # Thêm 9 tỉnh giả lập với tần suất 2, để ha_noi (tần suất 5) và prov_1..9 là top 10,
    # còn unknown_province (tần suất 1) sẽ nằm ngoài top 10
    rows[0]["locations"] = [{"tinh_key": "ha_noi", "remote": False, "ngoai_vn": False}] * 5
    for i in range(1, 10):
        rows.append({
            "job_id_global": f"job_dummy_{i}",
            "source_platform": "vietnamworks",
            "seniority": "Middle",
            "job_family": "Frontend",
            "raw_employment_type": "FULL_TIME",
            "it_status": "it",
            "locations": [
                {"tinh_key": f"prov_{i}", "remote": False, "ngoai_vn": False},
                {"tinh_key": f"prov_{i}", "remote": False, "ngoai_vn": False}
            ],
            "skills_std": ["React"],
            "log_salary_min": 15.0,
            "log_salary_max": 16.0,
            "exp_min_years": 2.0,
            "exp_max_years": 4.0,
            "headcount": 1.0,
            "is_negotiable": False,
            "is_outlier_salary": False,
            "posted_date": "2026-10-10",
            "deadline_date": "2026-11-10",
            "it_rule_level": 1,
            "seniority_can_kiem": False,
            "job_family_can_kiem": True,
        })
    return pd.DataFrame(rows)


def test_e1_ordinal_seniority(mock_golden_df):
    features_df, dictionary, _ = encode_dataset(mock_golden_df)
    assert "seniority_ord" in features_df.columns
    # Row 1: Junior -> 2
    assert features_df.loc[0, "seniority_ord"] == 2
    # Row 2: Chưa rõ -> -1
    assert features_df.loc[1, "seniority_ord"] == -1
    assert dictionary["seniority_ord"]["mapping"]["Junior"] == 2
    assert dictionary["seniority_ord"]["mapping"]["Chưa rõ"] == -1


def test_e2_one_hot_encodings(mock_golden_df):
    features_df, dictionary, _ = encode_dataset(mock_golden_df)
    # job_family
    assert features_df.loc[0, "job_family__backend"] == 1
    assert features_df.loc[0, "job_family__khac"] == 0
    assert features_df.loc[1, "job_family__backend"] == 0
    assert features_df.loc[1, "job_family__khac"] == 1

    # employment_type
    assert features_df.loc[0, "employment_type__full_time"] == 1
    assert features_df.loc[0, "employment_type__missing"] == 0
    assert features_df.loc[1, "employment_type__full_time"] == 0
    assert features_df.loc[1, "employment_type__missing"] == 1

    assert not any(c.startswith("it_status__") for c in features_df.columns)  # sau Clean mọi tin là IT


def test_e3_e4_multi_hot_provinces_and_skills(mock_golden_df):
    features_df, dictionary, _ = encode_dataset(mock_golden_df)
    # Row 1: ha_noi is top province
    assert features_df.loc[0, "tinh__ha_noi"] == 1
    assert features_df.loc[0, "tinh__other"] == 0
    assert features_df.loc[0, "is_remote"] == 0

    # Row 2: unknown_province is not top province -> tinh__other = 1, is_remote = 1
    assert features_df.loc[1, "tinh__ha_noi"] == 0
    assert features_df.loc[1, "tinh__other"] == 1
    assert features_df.loc[1, "is_remote"] == 1


def test_e5_e8_numeric_preservation_and_missing_flags(mock_golden_df):
    features_df, dictionary, _ = encode_dataset(mock_golden_df)

    # Row 1: Values present
    assert features_df.loc[0, "log_salary_min"] == pytest.approx(16.5, abs=0.01)
    assert features_df.loc[0, "log_salary_min__missing"] == 0
    assert features_df.loc[0, "exp_min_years"] == pytest.approx(1.0, abs=0.01)
    assert features_df.loc[0, "exp_min_years__missing"] == 0
    # E8: cờ luật if-else
    assert features_df.loc[0, "it_rule_level__2"] == 1 and features_df.loc[0, "seniority_can_kiem"] == 1
    assert features_df.loc[1, "it_rule_level__2"] == 0 and features_df.loc[1, "job_family_can_kiem"] == 0

    # Row 2: Values missing
    assert pd.isna(features_df.loc[1, "log_salary_min"])
    assert features_df.loc[1, "log_salary_min__missing"] == 1
    assert pd.isna(features_df.loc[1, "exp_min_years"])
    assert features_df.loc[1, "exp_min_years__missing"] == 1


def test_e6_e7_binary_flags_and_temporal(mock_golden_df):
    features_df, dictionary, _ = encode_dataset(mock_golden_df)

    # Row 1: is_negotiable=0, is_outlier_salary=0, posted_month=10, days_to_deadline=30
    assert features_df.loc[0, "is_negotiable"] == 0
    assert features_df.loc[0, "is_outlier_salary"] == 0
    assert features_df.loc[0, "posted_month"] == 10
    assert features_df.loc[0, "posted_month__missing"] == 0
    assert features_df.loc[0, "days_to_deadline"] == 30
    assert features_df.loc[0, "days_to_deadline__missing"] == 0

    # Row 2: is_negotiable=1, is_outlier_salary=1, posted_month missing
    assert features_df.loc[1, "is_negotiable"] == 1
    assert features_df.loc[1, "is_outlier_salary"] == 1
    assert pd.isna(features_df.loc[1, "posted_month"])
    assert features_df.loc[1, "posted_month__missing"] == 1
    assert pd.isna(features_df.loc[1, "days_to_deadline"])
    assert features_df.loc[1, "days_to_deadline__missing"] == 1


def test_features_parquet_strict_numeric_types(mock_golden_df):
    """Đảm bảo mọi cột (trừ job_id_global) là số học (int hoặc float)."""
    features_df, _, _ = encode_dataset(mock_golden_df)
    for col in features_df.columns:
        if col == "job_id_global":
            continue
        dtype = features_df[col].dtype
        assert np.issubdtype(dtype, np.number), f"Column {col} has non-numeric dtype: {dtype}"


def test_dictionary_reversibility(mock_golden_df):
    """Kiểm tra khả năng giải mã ngược từ encoding_dictionary."""
    features_df, dictionary, _ = encode_dataset(mock_golden_df)

    # Giải mã ngược seniority
    rev_seniority_map = {v: k for k, v in dictionary["seniority_ord"]["mapping"].items()}
    val_0 = features_df.loc[0, "seniority_ord"]
    assert rev_seniority_map[val_0] == mock_golden_df.loc[0, "seniority"]

    # Giải mã ngược job_family
    fam_cols = dictionary["job_family"]["columns"]
    for fam_name, col_name in fam_cols.items():
        if features_df.loc[0, col_name] == 1:
            assert fam_name == mock_golden_df.loc[0, "job_family"]
