"""mining/data_io.py: nạp Silver + features (ba khối kỹ năng) + e5 khóa job, kiểm hợp đồng (M0)."""

import numpy as np
import pandas as pd
import pytest

from mining.data_io import (
    MiningContractError,
    find_skill_columns,
    load_e5,
    load_mining_data,
    location_group,
    prepare_mining_data,
    seniority_to_ordinal,
    skills_from_lists,
    strip_skill_prefix,
)
from mining.synthetic import make_synthetic_jobs


def _silver() -> pd.DataFrame:
    """Tên cột như data/preprocessing/04_normalization/silver.parquet (26 trường; ở đây lấy phần Mining dùng)."""
    return pd.DataFrame({
        "job_id": ["a", "b", "c"],
        "source": ["topcv", "itviec", "jobsgo"],
        "title": ["Java Dev", "React Dev", "Tester"],
        "company": ["X", "Y", "Z"],
        "company_id": ["x", "y", None],
        "job_family": ["Web", "Web", None],
        "seniority": ["Junior", "Senior", None],
        "seniority_inferred": [False, True, False],
        "exp_min_years": [1.0, None, 3.0],
        "exp_inferred": [False, False, True],
        "province": ["TP. Hà Nội", "TP. Hồ Chí Minh", "TP. Đà Nẵng"],
        "work_mode": ["onsite", "hybrid", None],
        "employment_type": ["full_time", None, "internship"],
        "salary_min": [10_000_000.0, 30_000_000.0, None],
        "salary_max": [20_000_000.0, 50_000_000.0, None],
        "salary_negotiable": [False, False, True],
        "salary_outlier": [False, True, False],
        "benefits": [["bao_hiem"], [], None],
        "language": ["vi", "en", "vi"],
        "posted_month": ["2026-10", "2026-09", None],
    })


def _features(order=("a", "b", "c")) -> pd.DataFrame:
    rows = {
        "a": dict(skill__java=1, skill__python=0, skill__other_skill=1, concept__oop=1, concept__other_skill=0,
                  soft__english=0, soft__other_skill=0, n_tools=2, n_concepts=1, n_soft=0, salary_target_m=15.0),
        "b": dict(skill__java=0, skill__python=1, skill__other_skill=0, concept__oop=0, concept__other_skill=1,
                  soft__english=1, soft__other_skill=0, n_tools=1, n_concepts=1, n_soft=1, salary_target_m=40.0),
        "c": dict(skill__java=0, skill__python=0, skill__other_skill=0, concept__oop=0, concept__other_skill=0,
                  soft__english=0, soft__other_skill=0, n_tools=0, n_concepts=0, n_soft=0, salary_target_m=np.nan),
    }
    df = pd.DataFrame([{"job_id_global": k, **rows[k]} for k in order])
    for c in df.columns:
        if c.startswith(("skill__", "concept__", "soft__")):
            df[c] = df[c].astype(np.uint8)
    return df


def test_silver_meta_resolves_new_names():
    data = prepare_mining_data(_silver(), _features())
    m = data.meta
    assert data.resolved_columns["job_title"] == "title"
    assert data.resolved_columns["source_platform"] == "source"
    assert data.resolved_columns["is_negotiable"] == "salary_negotiable"
    assert data.resolved_columns["salary_outlier"] == "salary_outlier"
    assert m["job_title"].tolist() == ["Java Dev", "React Dev", "Tester"]
    assert m["seniority_ord"].tolist() == [1, 3, -1]
    assert m["location_group"].tolist() == ["ha_noi", "ho_chi_minh", "khac"]
    assert m["job_family"].iloc[2] == "Other"
    assert m["is_negotiable"].tolist() == [False, False, True]
    assert m["salary_outlier"].tolist() == [False, True, False]
    for c in ("company_id", "seniority_inferred", "posted_month", "work_mode", "employment_type",
              "language", "benefits", "exp_inferred"):
        assert c in m.columns, c
    assert m["company_id"].iloc[0] == "x" and pd.isna(m["company_id"].iloc[2])


def test_three_blocks_without_other_skill_and_counts_from_features():
    data = prepare_mining_data(_silver(), _features())
    assert list(data.skills.columns) == ["java", "python"]
    assert list(data.concepts.columns) == ["oop"]
    assert list(data.soft.columns) == ["english"]
    m = data.meta
    # lấy thẳng từ bước 10, không đếm lại (tin a có công cụ hiếm đã gom nên n_tools = 2 > 1 cột)
    assert m["n_tools"].tolist() == [2, 1, 0]
    assert m["n_concepts"].tolist() == [1, 1, 0]
    assert m["n_soft"].tolist() == [0, 1, 0]
    assert m["salary_target_m"].tolist()[:2] == [15.0, 40.0] and np.isnan(m["salary_target_m"].iloc[2])
    # một định nghĩa lương: salary_avg_mil = salary_target_m (M0.9)
    assert m["salary_avg_mil"].tolist()[:2] == [15.0, 40.0]


def test_features_joined_by_id_not_row_order():
    data = prepare_mining_data(_silver(), _features(order=("c", "a", "b")))
    assert data.skills["java"].tolist() == [1, 0, 0]
    assert data.meta["n_tools"].tolist() == [2, 1, 0]
    assert data.soft["english"].tolist() == [0, 1, 0]


def test_contract_errors_are_explicit():
    g = _silver()
    with pytest.raises(MiningContractError, match="khóa"):
        prepare_mining_data(g.drop(columns=["job_id"]), _features())
    with pytest.raises(MiningContractError, match="trùng"):
        prepare_mining_data(pd.concat([g, g.iloc[[0]]], ignore_index=True), _features())
    bad = _features()
    bad["skill__java"] = [1, 2, 0]
    with pytest.raises(MiningContractError, match="0/1"):
        prepare_mining_data(g, bad)
    with pytest.raises(MiningContractError, match="không có dòng"):
        prepare_mining_data(g, _features(order=("a", "b")))


def test_skill_prefix_only_double_underscore():
    cols = ["job_id_global", "skill__python", "skill_java", "skill__other_skill", "concept__oop", "n_skills"]
    assert find_skill_columns(cols) == ["skill__python"]
    assert find_skill_columns(cols, "concept__") == ["concept__oop"]
    assert strip_skill_prefix("skill__python") == "python"
    assert strip_skill_prefix("concept__oop") == "oop"


def test_load_e5_reads_job_key_and_aligns(tmp_path):
    p = tmp_path / "job_emb.npz"
    np.savez(p, ids=np.array(["b", "a", "c"]), all=np.zeros((3, 2), dtype=np.float16),
             job=np.array([[0, 1], [1, 0], [1, 1]], dtype=np.float16))
    assert load_e5(p, pd.Series(["a", "b"])).tolist() == [[1, 0], [0, 1]]
    with pytest.raises(MiningContractError):
        load_e5(p, pd.Series(["a", "zzz"]))  # thiếu tin thì báo lỗi, không bịa vector


def test_load_e5_without_job_key_is_an_error(tmp_path):
    p = tmp_path / "old.npz"
    np.savez(p, ids=np.array(["a"]), all=np.ones((1, 2)))
    with pytest.raises(MiningContractError, match="job"):
        load_e5(p, pd.Series(["a"]))


def test_load_mining_data_from_files_records_sha(tmp_path):
    sp, fp, ep = tmp_path / "silver.parquet", tmp_path / "features.parquet", tmp_path / "job_emb.npz"
    _silver().to_parquet(sp, index=False)
    _features(order=("b", "c", "a")).to_parquet(fp, index=False)
    np.savez(ep, ids=np.array(["a", "b", "c"]), job=np.eye(3, dtype=np.float16))
    data = load_mining_data(sp, fp, None, ep)
    assert data.e5.shape == (3, 3) and data.e5[1].tolist() == [0, 1, 0]
    assert data.table_path == sp
    assert set(data.input_sha256) == {"table", "features", "encoding_dict", "e5"}
    assert data.input_sha256["table"] and data.input_sha256["encoding_dict"] is None


def test_missing_table_is_not_replaced_by_another_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_mining_data(tmp_path / "silver.parquet", None, None, None)


@pytest.mark.parametrize("label,expected", [
    ("Intern/Fresher", 0), ("Fresher", 0), ("junior", 1), ("Middle", 2),
    ("Senior", 3), ("Lead/Manager", 4), ("Chưa rõ", -1), (None, -1), (3, 3), (5, -1),
])
def test_seniority_to_ordinal(label, expected):
    assert seniority_to_ordinal(label) == expected


@pytest.mark.parametrize("prov,expected", [
    ("Hà Nội", "ha_noi"), ("TP. Hà Nội", "ha_noi"), ("TP. Hồ Chí Minh", "ho_chi_minh"), ("HCM", "ho_chi_minh"),
    ("Đà Nẵng", "khac"), ("Remote", "remote"), (None, "khong_ro"), ("", "khong_ro"),
    ("Nhiều địa điểm", "nhieu_dia_diem"), ("Toàn quốc", "toan_quoc"),
])
def test_location_group(prov, expected):
    assert location_group(prov) == expected


def test_skills_from_lists_dedups_within_row():
    m = skills_from_lists([["A", "A", "B"], "B, C", None])
    assert m.loc[0, "A"] == 1 and m.sum().to_dict() == {"B": 2, "A": 1, "C": 1}


def test_synthetic_bundle_has_silver_schema_and_three_blocks():
    b = make_synthetic_jobs(n_jobs=300, seed=1)
    for c in ("job_id", "title", "source", "company_id", "salary_negotiable", "salary_outlier", "posted_month"):
        assert c in b.golden.columns, c
    d = prepare_mining_data(b.golden, b.features.sample(frac=1.0, random_state=0),
                            b.encoding_dict["skills"]["skills_map"])
    assert "Spring Boot" in d.skills.columns and "Machine Learning" in d.concepts.columns
    assert "English" in d.soft.columns and "English" not in d.skills.columns
    assert (d.meta["n_tools"].to_numpy() == d.skills.sum(axis=1).to_numpy()).all()
