"""mining/data_io.py: chuẩn hóa schema cũ/mới của golden + features và kiểm tra hợp đồng."""

import numpy as np
import pandas as pd
import pytest

from mining.data_io import (
    MiningContractError,
    find_skill_columns,
    location_group,
    prepare_mining_data,
    seniority_to_ordinal,
    skills_from_lists,
    strip_skill_prefix,
)
from mining.synthetic import make_synthetic_jobs


def _old_schema_golden() -> pd.DataFrame:
    """Tên cột như output 04_normalization hiện tại: lương VNĐ, seniority, tinh_chinh, skills_std."""
    return pd.DataFrame({
        "job_id_global": ["a", "b", "c"],
        "job_title_clean": ["Java Dev", "React Dev", "Tester"],
        "company_name": ["X", "Y", "Z"],
        "job_family": ["Backend", "Frontend", None],
        "seniority": ["Junior", "Senior", None],
        "exp_min_years": [1.0, None, 3.0],
        "tinh_chinh": ["ha_noi", "ho_chi_minh", "da_nang"],
        "skills_std": [["Java", "SQL"], ["React", "JavaScript"], []],
        "salary_min_vnd_capped": [10_000_000, 30_000_000, None],
        "salary_max_vnd_capped": [20_000_000, 50_000_000, None],
        "is_negotiable": [False, False, True],
        "salary_suspect": [False, False, False],
        "description_clean": ["mô tả", None, ""],
        "requirements_clean": ["java sql", "react", None],
    })


def test_old_schema_salary_converted_to_million_and_skills_built_from_lists():
    data = prepare_mining_data(_old_schema_golden())
    m = data.meta
    assert m["salary_avg_mil"].tolist()[:2] == [15.0, 40.0]
    assert np.isnan(m["salary_avg_mil"].iloc[2])
    assert m["seniority_ord"].tolist() == [1, 3, -1]
    assert m["location_group"].tolist() == ["ha_noi", "ho_chi_minh", "khac"]
    assert m["job_family"].iloc[2] == "Other"
    assert set(data.skills.columns) == {"Java", "SQL", "React", "JavaScript"}
    assert m["n_skills"].tolist() == [2, 2, 0]
    assert any("vnd" in n for n in data.notes)


def test_new_schema_with_features_uses_skill_map_and_aligns_rows():
    b = make_synthetic_jobs(n_jobs=200, seed=1)
    feats = b.features.sample(frac=1.0, random_state=0)  # đảo thứ tự dòng
    data = prepare_mining_data(b.golden, feats, b.encoding_dict["skills"]["skills_map"])
    assert data.resolved_columns["salary_avg"] == "salary_avg"
    assert data.resolved_columns["seniority"] == "seniority"
    assert any("cột seniority (dạng label)" in n for n in data.notes)
    assert "Spring Boot" in data.skills.columns and "Node.js" in data.skills.columns
    # căn đúng theo job_id dù features bị đảo
    for i in (0, 57, 199):
        expected = set(b.golden["skills_extracted"].iloc[i])
        got = set(data.skills.columns[data.skills.iloc[i].to_numpy() == 1])
        assert got == expected


def test_skill_prefix_detection_handles_both_conventions():
    cols = ["job_id_global", "skill__python", "skill_java", "skills__other_count", "seniority_ord"]
    assert find_skill_columns(cols) == ["skill__python", "skill_java"]
    assert strip_skill_prefix("skill__python") == "python"
    assert strip_skill_prefix("skill_java") == "java"


def test_contract_errors_are_explicit():
    g = _old_schema_golden()
    with pytest.raises(MiningContractError, match="khóa"):
        prepare_mining_data(g.drop(columns=["job_id_global"]))
    with pytest.raises(MiningContractError, match="trùng"):
        prepare_mining_data(pd.concat([g, g.iloc[[0]]], ignore_index=True))

    feats = pd.DataFrame({"job_id_global": ["a", "b", "c"], "skill_java": [1, 2, 0]})
    with pytest.raises(MiningContractError, match="0/1"):
        prepare_mining_data(g, feats)
    feats_missing = pd.DataFrame({"job_id_global": ["a", "b"], "skill_java": [1, 0]})
    with pytest.raises(MiningContractError, match="không có dòng"):
        prepare_mining_data(g, feats_missing)


@pytest.mark.parametrize("label,expected", [
    ("Intern/Fresher", 0), ("Fresher", 0), ("junior", 1), ("Middle", 2),
    ("Senior", 3), ("Lead/Manager", 4), ("Chưa rõ", -1), (None, -1), (3, 3), (5, -1),
])
def test_seniority_to_ordinal(label, expected):
    assert seniority_to_ordinal(label) == expected


@pytest.mark.parametrize("prov,expected", [
    ("Hà Nội", "ha_noi"), ("ha_noi", "ha_noi"), ("TP. Hồ Chí Minh", "ho_chi_minh"), ("HCM", "ho_chi_minh"),
    ("Đà Nẵng", "khac"), ("Remote", "remote"), (None, "khong_ro"), ("", "khong_ro"),
    ("Nhiều địa điểm", "nhieu_dia_diem"), ("Toàn quốc", "toan_quoc"),
])
def test_location_group(prov, expected):
    assert location_group(prov) == expected


def test_location_group_falls_back_to_locations_list():
    assert location_group(None, [{"tinh_key": "ho_chi_minh"}]) == "ho_chi_minh"
    assert location_group(None, [{"remote": True}]) == "remote"


def _duy_schema_golden(with_label: bool) -> pd.DataFrame:
    """Output 04_normalization của Duy (nhánh feature/p3-p4-transform-normalize, 9b33a05):
    seniority_level 0-4 (null = chưa rõ), city_normalized có "Nhiều địa điểm"/"Toàn quốc",
    salary_avg đã ở triệu VNĐ/tháng."""
    g = pd.DataFrame({
        "job_id_global": ["a", "b", "c", "d", "e", "f"],
        "job_title": ["Intern", "Junior Dev", "Mid Dev", "Senior Dev", "Tech Lead", "Dev"],
        "job_family": ["Backend"] * 6,
        "seniority_level": pd.Series([0, 1, 2, 3, 4, None], dtype="float64"),
        "exp_min_years": [0.0, 1.0, 2.0, 4.0, 6.0, None],
        "city_normalized": ["Hà Nội", "Hồ Chí Minh", "Nhiều địa điểm", "Toàn quốc", "Remote", "Đà Nẵng"],
        "skills_extracted": [["Java"], ["Java", "SQL"], ["SQL"], ["Java"], ["Java", "SQL"], []],
        "salary_avg": [5.0, 15.0, 25.0, 40.0, 55.0, None],
        "is_negotiable": [False] * 5 + [True],
    })
    if with_label:
        g["seniority"] = ["Intern/Fresher", "Junior", "Middle", "Senior", "Lead/Manager", None]
    return g


def test_duy_schema_int_seniority_level_maps_0_4_to_ordinal_scale():
    data = prepare_mining_data(_duy_schema_golden(with_label=False))
    m = data.meta
    # thang 0-4 dùng nguyên, null -> -1
    assert m["seniority_ord"].tolist() == [0, 1, 2, 3, 4, -1]
    assert m["seniority"].tolist() == ["Intern/Fresher", "Junior", "Middle", "Senior", "Lead/Manager", "Chưa rõ"]
    assert any("seniority_level (dạng level_0_4)" in n for n in data.notes)
    assert m["location_group"].tolist() == ["ha_noi", "ho_chi_minh", "nhieu_dia_diem", "toan_quoc", "remote", "khac"]
    assert m["salary_avg_mil"].tolist()[:5] == [5.0, 15.0, 25.0, 40.0, 55.0]


def test_duy_schema_prefers_text_label_over_int_level():
    """Có cả nhãn chữ thì dùng nhãn; kết quả trùng thang 0-4."""
    m = prepare_mining_data(_duy_schema_golden(with_label=True)).meta
    assert m["seniority_ord"].tolist() == [0, 1, 2, 3, 4, -1]


def test_seniority_ord_from_encoding_takes_priority():
    g = _duy_schema_golden(with_label=True)
    g["seniority_ord"] = [0, 1, 2, 3, 4, -1]  # E1 của bước Encoding, thang 0-4
    m = prepare_mining_data(g).meta
    assert m["seniority_ord"].tolist() == [0, 1, 2, 3, 4, -1]


def test_salary_features_have_new_location_groups():
    from mining.salary_model import build_salary_features

    data = prepare_mining_data(_duy_schema_golden(with_label=False))
    X = build_salary_features(data.meta, data.skills)
    assert X["loc::nhieu_dia_diem"].tolist() == [0, 0, 1, 0, 0, 0]
    assert X["loc::toan_quoc"].tolist() == [0, 0, 0, 1, 0, 0]
    assert X["loc::khac"].tolist() == [0, 0, 0, 0, 0, 1]


def test_skills_from_lists_dedups_within_row():
    m = skills_from_lists([["A", "A", "B"], "B, C", None])
    assert m.loc[0, "A"] == 1 and m.sum().to_dict() == {"B": 2, "A": 1, "C": 1}
