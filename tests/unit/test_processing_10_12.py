# -*- coding: utf-8 -*-
"""Processing bước 10 (rời rạc hóa), 10b (chọn), 10c (xây), 10d (mã hóa), 12 (TF-IDF). Dữ liệu tổng hợp nhỏ, chạy offline."""

import numpy as np
import pandas as pd
import pytest

from processing.construction.features import construct
from processing.encoding.features import build_features
from processing.extraction.vectorize import vectorize
from processing.transformation.discretize import SALARY_EDGES_M, discretize, exp_bin


def _loc(*keys, remote=False, ngoai_vn=False):
    return [{"tinh_key": k, "remote": remote, "ngoai_vn": ngoai_vn} for k in keys] or [
        {"tinh_key": None, "remote": remote, "ngoai_vn": ngoai_vn}]


def _df():
    return pd.DataFrame({
        "job_id_global": ["a_1", "a_2", "b_1", "b_2", "b_3", "b_4"],
        "source_platform": ["a", "a", "b", "b", "b", "b"],
        "salary_min_vnd": [10e6, np.nan, 30e6, 20e6, np.nan, np.nan],
        "salary_max_vnd": [20e6, 50e6, 30e6, np.nan, np.nan, np.nan],
        "salary_status": ["value", "value", "value", "value", "negotiable", "not_stated"],
        "is_negotiable": [False, False, False, False, True, False],
        "is_outlier_salary": [False, False, False, False, False, False],
        "seniority_can_kiem": [False, False, False, False, False, True],
        "exp_min_years": [0.0, 1.0, 3.0, 6.0, np.nan, 2.5],
        "seniority": ["Intern/Fresher", "Junior", "Senior", "Lead/Manager", None, "Middle"],
        "job_family": ["Web", "Web", "Design", "Other", "Web", "Mobile"],
        "work_mode": ["onsite", "remote", "onsite", "hybrid", None, "onsite"],
        "tinh_chinh": ["Hà Nội", "TP. Hồ Chí Minh", "Hà Nội", None, "Đà Nẵng", "Hà Nội"],
        "benefits_std": [["Bảo hiểm", "Thưởng"], [], ["Bảo hiểm"], None, [], ["Thưởng", "Du lịch", "Đào tạo"]],
        "locations": [_loc("ha_noi"), _loc("ho_chi_minh"), _loc("ha_noi", "da_nang"), _loc(), _loc("da_nang", remote=True),
                      _loc("ha_noi", ngoai_vn=True)],
        "raw_employment_type": ["Toàn thời gian", "FULL_TIME", "Thực tập", "Bán thời gian", None, "6"],
        "log_salary_min": [16.1, np.nan, 17.2, np.nan, np.nan, np.nan],
        "log_salary_max": [16.8, 17.7, 17.2, np.nan, np.nan, np.nan],
        "exp_max_years": [1.0, np.nan, 5.0, np.nan, np.nan, 3.0],
        "headcount": [1.0, np.nan, 3.0, np.nan, np.nan, 2.0],
        "crawled_at": ["2026-11-01"] * 6,
        "posted_date": ["2026-10-20", None, "2026-10-31", None, None, "2026-11-01"],
        "deadline_date": ["2026-11-11", "2026-11-01", None, None, "2026-10-30", "2026-12-01"],
    })


def _skills():
    rows = []
    for j, slugs in {"a_1": ["python", "sql"], "a_2": ["python"], "b_1": ["python", "rare_x"], "b_2": ["rare_y"]}.items():
        for k, s in enumerate(slugs):
            rows.append({"job_id_global": j, "slug": s, "level": "required" if k == 0 else "preferred",
                         "weight": 1.0, "n_mentions": 1})
    return pd.DataFrame(rows)


def test_exp_bin_edges():
    assert [exp_bin(x) for x in (0, 0.9, 1, 2.9, 3, 5, 5.1, np.nan)] == [0, 0, 1, 1, 2, 2, 3, -1]


def test_salary_bins_use_reference_and_unknown_is_minus_one():
    d = _df()
    ref = pd.concat([d["salary_min_vnd"], d["salary_max_vnd"]], axis=1).mean(axis=1) / 1e6
    out = discretize(d, ref)
    assert list(out["salary_bin_range"]) == [1, 3, 2, 2, -1, -1]  # 15, 50, 30, 20 triệu (biên dưới thuộc khoảng sau); hai tin không có lương
    assert SALARY_EDGES_M == (10, 20, 35, 60)
    assert (out["salary_bin_eqfreq5"][ref.isna()] == -1).all()
    # đủ >= 5 tin có lương thì chia 5 phần bằng tần suất
    big = pd.DataFrame({"exp_min_years": [1.0] * 10})
    eq = discretize(big, pd.Series([float(i) for i in range(10)]))["salary_bin_eqfreq5"]
    assert sorted(eq.unique()) == [0, 1, 2, 3, 4] and eq.value_counts().nunique() == 1


def test_construct_nan_when_salary_missing_and_counts():
    d = _df()
    tok = pd.DataFrame({"job_id_global": d["job_id_global"], "n_tokens": [10, 20, 30, 40, 50, 60]})
    c = construct(d, _skills(), tok)
    assert list(c["n_skills"]) == [2, 1, 2, 1, 0, 0]
    assert list(c["n_required"]) == [1, 1, 1, 1, 0, 0]
    assert c["required_ratio"].iloc[0] == 0.5 and np.isnan(c["required_ratio"].iloc[4])
    assert list(c["n_benefits"]) == [2, 0, 1, 0, 0, 3]  # None -> 0
    assert c["salary_mid"].iloc[0] == 15.0 and c["salary_range_ratio"].iloc[0] == pytest.approx(10 / 15)
    # thiếu min hoặc max thì NaN, không điền
    assert c["salary_mid"].iloc[[1, 3, 4, 5]].isna().all()
    assert list(c["n_tokens"]) == [10, 20, 30, 40, 50, 60]


def test_build_features_numeric_conserved_and_decodable():
    d = _df()
    tok = pd.DataFrame({"job_id_global": d["job_id_global"], "n_tokens": range(6)})
    feats, dic, rep = build_features(d, _skills(), tok, min_df=2)
    assert len(feats) == len(d) and list(feats["job_id_global"]) == list(d["job_id_global"])
    assert all(pd.api.types.is_numeric_dtype(feats[c]) for c in feats.columns if c != "job_id_global")
    # chọn đặc trưng: sql, rare_x, rare_y (df=1 < 2) gom thành other_skill; python (df=3) giữ; số JD không đổi
    assert "skill__python" in feats and "skill__rare_x" not in feats and "skill__sql" not in feats
    assert list(feats["skill__other_skill"]) == [1, 0, 1, 1, 0, 0]
    assert rep["min_df"] == 2 and set(sum(rep["folded"].values(), [])) == {"sql", "rare_x", "rare_y"}
    # cấp bậc thứ tự, chưa rõ = -1
    assert list(feats["seniority_ord"]) == [0, 1, 3, 4, -1, 2]
    # lương thỏa thuận và không ghi gộp thành unknown, không điền số
    assert list(feats["salary_status__unknown"]) == [0, 0, 0, 0, 1, 1]
    assert list(feats["salary_status__value"]) == [1, 1, 1, 1, 0, 0]
    # one-hot nhóm nghề: nhóm mới (Design) có cột
    assert feats["fam__design"].tolist() == [0, 0, 1, 0, 0, 0]
    # giải mã ngược 5 dòng: nhóm nghề từ one-hot trùng cột gốc
    fam_cols = [c for c in feats if c.startswith("fam__")]
    back = feats[fam_cols].idxmax(axis=1).str.replace("fam__", "")
    assert list(back) == ["web", "web", "design", "other", "web", "mobile"]
    assert dic["seniority_ord"]["method"] == "ordinal" and "skill__python" in dic


def test_tfidf_rows_l2_normalized_and_reproducible():
    toks = pd.DataFrame({"job_id_global": ["a", "b", "c", "d", "e", "f"],
                         "tokens_nostop": [["python", "sql", "dữ liệu"], ["python", "java"], ["python", "sql"],
                                           ["java", "sql", "dữ liệu"], ["python", "java", "sql"], ["sql", "dữ liệu"]]})
    m1, v1 = vectorize(toks, min_df=2, max_features=100)
    m2, v2 = vectorize(toks, min_df=2, max_features=100)
    assert m1.shape[0] == 6 and v1 == v2 and (m1 != m2).nnz == 0
    norms = np.sqrt(np.asarray(m1.multiply(m1).sum(axis=1)).ravel())
    assert np.allclose(norms, 1.0)
    assert "python" in v1 and "python|sql" in v1  # có bigram


def test_encoding_covers_p5_remaining_items():
    d = _df()
    tok = pd.DataFrame({"job_id_global": d["job_id_global"], "n_tokens": range(6)})
    feats, dic, _ = build_features(d, _skills(), tok, min_df=2)
    # E2: loại hình làm việc (luật từ khóa trên chuỗi gốc); null và giá trị lạ ("6") -> unknown/other, không bịa
    assert feats["emp__full_time"].tolist() == [1, 1, 0, 0, 0, 0]
    assert feats["emp__intern"].tolist() == [0, 0, 1, 0, 0, 0] and feats["emp__part_time"].tolist() == [0, 0, 0, 1, 0, 0]
    assert feats["emp__unknown"].tolist() == [0, 0, 0, 0, 1, 1]
    # E3: multi-hot tỉnh theo mọi địa điểm của tin; remote và ngoai_vn là cờ riêng
    assert feats["tinh__ha_noi"].tolist() == [1, 0, 1, 0, 0, 1] and feats["tinh__da_nang"].tolist() == [0, 0, 1, 0, 1, 0]
    assert feats["tinh__unknown"].tolist() == [0, 0, 0, 1, 0, 0]
    assert feats["loc_remote"].tolist() == [0, 0, 0, 0, 1, 0] and feats["loc_ngoai_vn"].tolist() == [0, 0, 0, 0, 0, 1]
    # E5: số giữ nguyên, thiếu giữ NaN và có cột __missing
    assert feats["log_salary_min"].iloc[0] == 16.1 and np.isnan(feats["log_salary_min"].iloc[1])
    assert feats["log_salary_min__missing"].tolist() == [0, 1, 0, 1, 1, 1]
    assert feats["headcount__missing"].tolist() == [0, 1, 0, 1, 1, 0] and feats["exp_max_years__missing"].iloc[1] == 1
    # E7: tháng đăng và số ngày còn lại tới hạn nộp, tính từ ngày cào (không có ngày thì NaN + __missing)
    assert feats["posted_month"].iloc[[0, 2, 5]].tolist() == [10, 10, 11] and np.isnan(feats["posted_month"].iloc[1])
    assert feats["days_to_deadline"].iloc[[0, 1, 4, 5]].tolist() == [10, 0, -2, 30] and np.isnan(feats["days_to_deadline"].iloc[2])
    assert feats["days_to_deadline__missing"].tolist() == [0, 0, 1, 1, 0, 0]
    assert all(pd.api.types.is_numeric_dtype(feats[c]) for c in feats.columns if c != "job_id_global")
