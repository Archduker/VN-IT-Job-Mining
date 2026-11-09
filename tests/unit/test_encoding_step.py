"""tests.unit.test_encoding_step
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Kiểm thử Bước 05 Encoding theo đặc tả SPEC-06, SPEC-07 và Task 05 của Phát:
- E1: Ordinal Seniority (0-5, -1 cho Chưa rõ)
- E2: One-hot job_family, source_platform, employment_type
- E3: Multi-hot top 10 tỉnh/thành + tinh__other + remote/ngoai_vn
- E4: Multi-hot ĐÚNG 230 cột kỹ năng chuẩn (skill_<slug>, uint8) + other_skills_count
- Co-occurrence: Ma trận vuông 230x230, C = X^T @ X đối xứng, đường chéo khớp tần suất
- TF-IDF: Trích xuất không gian đặc trưng n-gram văn bản JD
- E5: Bảo toàn số học liên tục + cờ __missing (0/1)
- E6: Cờ nhị phân (is_negotiable, is_outlier_salary)
- E7: Bóc tách tháng đăng và ngày tới hạn
- E8: Cờ của luật if-else
- Giải mã ngược (reversibility) bằng encoding_dictionary.json
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from preprocessing.encoding.run import (
    EXACT_SKILL_COUNT,
    ORDERED_SKILL_COLUMNS,
    compute_skill_cooccurrence,
    encode_dataset,
)
from preprocessing.encoding.tfidf_extractor import extract_tfidf_space


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
            "description_clean": "Tuyển dụng lập trình viên Python và Docker tại Hà Nội, phát triển hệ thống backend microservices.",
            "requirements_clean": "Yêu cầu nắm vững Python, kinh nghiệm làm việc với Docker và cơ sở dữ liệu PostgreSQL.",
        },
        {
            "job_id_global": "job_02",
            "source_platform": "topcv",
            "seniority": "Chưa rõ",
            "job_family": "Khác",
            "raw_employment_type": None,
            "it_status": "it",
            "locations": [{"tinh_key": "unknown_province", "remote": True, "ngoai_vn": False}],
            "skills_std": ["Java", "Docker"],
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
            "description_clean": "Cần tuyển kỹ sư Java Spring Boot làm việc remote.",
            "requirements_clean": "Thành thạo Java, Docker và microservices architecture.",
        },
    ]
    # Thêm 9 tỉnh giả lập với tần suất 2, để ha_noi (tần suất 5) và prov_1..9 là top 10,
    # còn unknown_province (tần suất 1) sẽ nằm ngoài top 10
    rows[0]["locations"] = [{"tinh_key": "ha_noi", "remote": False, "ngoai_vn": False}] * 5
    for i in range(1, 10):
        rows.append(
            {
                "job_id_global": f"job_dummy_{i}",
                "source_platform": "vietnamworks",
                "seniority": "Middle",
                "job_family": "Frontend",
                "raw_employment_type": "FULL_TIME",
                "it_status": "it",
                "locations": [
                    {"tinh_key": f"prov_{i}", "remote": False, "ngoai_vn": False},
                    {"tinh_key": f"prov_{i}", "remote": False, "ngoai_vn": False},
                ],
                "skills_std": ["React", "TypeScript"],
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
                "description_clean": f"Tuyển dụng Frontend React Developer tại prov_{i}.",
                "requirements_clean": "Thành thạo React, TypeScript và HTML/CSS.",
            }
        )
    return pd.DataFrame(rows)


@pytest.mark.parametrize(
    "field,value", [("skills_std", "Python"), ("skills_std", [123]), ("locations", [None])]
)
def test_malformed_arrays_rejected(mock_golden_df, field, value):
    mock_golden_df.at[0, field] = value
    with pytest.raises(ValueError, match="Malformed"):
        encode_dataset(mock_golden_df)


def test_legacy_full_run_is_blocked_before_any_write(mock_golden_df, tmp_path, monkeypatch):
    import importlib

    module = importlib.import_module("preprocessing.encoding.run")
    source = tmp_path / "input.parquet"
    mock_golden_df.to_parquet(source, index=False)
    monkeypatch.setattr(module, "IN_FILE", source)
    out = tmp_path / "out"
    out.mkdir()
    sentinel = out / "features.parquet"
    sentinel.write_bytes(b"validated-current-cohort")
    for dry_run in [True, False]:
        with pytest.raises(ValueError, match="Legacy P5 writer is disabled"):
            module.run(dry_run=dry_run)
    assert sentinel.read_bytes() == b"validated-current-cohort"
    assert not (out / "artifact_manifest.json").exists()


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

    assert not any(
        c.startswith("it_status__") for c in features_df.columns
    )  # sau Clean mọi tin là IT


def test_e3_multi_hot_provinces(mock_golden_df):
    features_df, dictionary, _ = encode_dataset(mock_golden_df)
    # Row 1: ha_noi is top province
    assert features_df.loc[0, "tinh__ha_noi"] == 1
    assert features_df.loc[0, "tinh__other"] == 0
    assert features_df.loc[0, "is_remote"] == 0

    # Row 2: unknown_province is not top province -> tinh__other = 1, is_remote = 1
    assert features_df.loc[1, "tinh__ha_noi"] == 0
    assert features_df.loc[1, "tinh__other"] == 1
    assert features_df.loc[1, "is_remote"] == 1


def test_e4_exact_230_skills_matrix(mock_golden_df):
    """Kiểm tra ma trận kỹ năng có ĐÚNG 230 cột nhị phân chuẩn (tiền tố skill_)."""
    features_df, dictionary, _ = encode_dataset(mock_golden_df)

    skill_cols = [c for c in features_df.columns if c.startswith("skill_")]
    assert len(skill_cols) == EXACT_SKILL_COUNT == 230
    assert skill_cols == ORDERED_SKILL_COLUMNS

    # Kiểm tra kiểu dữ liệu và tập giá trị {0, 1}
    for col in skill_cols:
        assert features_df[col].dtype == np.uint8
        assert set(features_df[col].unique()).issubset({0, 1})

    # Row 0: có Python, Docker -> skill_python=1, skill_docker=1, skill_java=0
    assert features_df.loc[0, "skill_python"] == 1
    assert features_df.loc[0, "skill_docker"] == 1
    assert features_df.loc[0, "skill_java"] == 0

    # Row 1: có Java, Docker -> skill_java=1, skill_docker=1, skill_python=0
    assert features_df.loc[1, "skill_java"] == 1
    assert features_df.loc[1, "skill_docker"] == 1
    assert features_df.loc[1, "skill_python"] == 0

    # RareCustomSkill không thuộc 230 kỹ năng chuẩn -> đếm vào other_skills_count
    assert "other_skills_count" in features_df.columns
    assert features_df.loc[0, "other_skills_count"] == 1
    # other_skills_count không được bắt đầu bằng skill_ để không dính filter của FP-Growth
    assert not "other_skills_count".startswith("skill_")


def test_skill_cooccurrence_matrix(mock_golden_df):
    """Kiểm tra tính chất toán học của Ma trận Đồng xuất hiện C = X^T @ X."""
    features_df, _, _ = encode_dataset(mock_golden_df)
    skill_matrix = features_df[ORDERED_SKILL_COLUMNS]

    C_df = compute_skill_cooccurrence(skill_matrix)

    # Kích thước vuông 230 x 230
    assert C_df.shape == (230, 230)
    assert list(C_df.columns) == ORDERED_SKILL_COLUMNS
    assert list(C_df.index) == ORDERED_SKILL_COLUMNS

    C_arr = C_df.to_numpy()

    # 1. Tính đối xứng C == C^T
    assert np.array_equal(C_arr, C_arr.T)

    # 2. Đường chéo chính bằng tổng tần suất đơn lẻ của từng kỹ năng
    diag_vals = np.diag(C_arr)
    col_sums = skill_matrix.to_numpy().sum(axis=0)
    assert np.array_equal(diag_vals, col_sums)

    # 3. Đồng xuất hiện giữa Docker và Python: Row 0 có cả hai -> C >= 1
    docker_idx = ORDERED_SKILL_COLUMNS.index("skill_docker")
    python_idx = ORDERED_SKILL_COLUMNS.index("skill_python")
    assert C_arr[docker_idx, python_idx] >= 1
    assert C_arr[python_idx, docker_idx] == C_arr[docker_idx, python_idx]


def test_tfidf_extraction(mock_golden_df):
    """Kiểm tra trích xuất không gian đặc trưng TF-IDF văn bản JD."""
    tfidf_df, metadata = extract_tfidf_space(mock_golden_df, max_features=100)

    assert tfidf_df is not None
    assert metadata["status"] == "SUCCESS"
    assert "job_id_global" in tfidf_df.columns
    assert len(tfidf_df) == len(mock_golden_df)

    # Các cột đặc trưng tfidf_xxxx đều là số thực float32
    feature_cols = [c for c in tfidf_df.columns if c.startswith("tfidf_")]
    assert len(feature_cols) > 0
    for col in feature_cols:
        assert tfidf_df[col].dtype == pd.SparseDtype(np.float32, 0)


def test_e5_e8_numeric_preservation_and_missing_flags(mock_golden_df):
    features_df, dictionary, _ = encode_dataset(mock_golden_df)

    # Row 1: Values present
    assert features_df.loc[0, "log_salary_min"] == pytest.approx(16.5, abs=0.01)
    assert features_df.loc[0, "log_salary_min__missing"] == 0
    assert features_df.loc[0, "exp_min_years"] == pytest.approx(1.0, abs=0.01)
    assert features_df.loc[0, "exp_min_years__missing"] == 0
    # E8: cờ luật if-else
    assert (
        features_df.loc[0, "it_rule_level__2"] == 1
        and features_df.loc[0, "seniority_can_kiem"] == 1
    )
    assert (
        features_df.loc[1, "it_rule_level__2"] == 0
        and features_df.loc[1, "job_family_can_kiem"] == 0
    )

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
