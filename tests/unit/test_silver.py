"""Bảng Silver (docs/spec/preprocessing/silver.md S1–S5, spec 05 mục 4.4): chọn cột, đổi tên, không tính lại."""
import pandas as pd
import pytest

from preprocessing.normalization import silver as SV


def _t04(n=2):
    rows = []
    for i in range(n):
        rows.append({
            "job_id_global": f"topcv_{i}", "source_platform": "topcv", "source_url": f"u{i}",
            "job_title_clean": "Backend Developer", "title_canonical": None, "job_family": "Web",
            "seniority": "Junior", "level_inferred": True, "exp_min_years": 1.0, "exp_max_years": float("nan"),
            "exp_inferred": False, "salary_min_vnd_capped": 10e6, "salary_max_vnd_capped": 20e6,
            "is_negotiable": False, "is_outlier_salary": False, "tinh_chinh": "TP. Hà Nội",
            "work_mode": None if i == 1 else "onsite", "employment_type": None, "company_norm": "a",
            "company_key": "a", "benefits_std": ["bảo hiểm"], "description_clean": "d", "requirements_clean": "r",
            "language": "vi", "posted_month": "2026-10", "cot_thua": 1})
    return pd.DataFrame(rows)


def _skills():
    return pd.DataFrame([
        {"job_id_global": "topcv_0", "slug": "python", "via": "text"},
        {"job_id_global": "topcv_0", "slug": "docker", "via": "meta"},
        {"job_id_global": "topcv_0", "slug": "python", "via": "text_vi"},
    ])


def test_s1_s4_columns_order_types_and_values():
    s = SV.build_silver(_t04(), _skills())
    assert list(s.columns) == [f for f, _ in SV.SILVER_FIELDS] and len(s.columns) == 26
    assert len(s) == 2 and s["job_id"].is_unique
    r0 = s.iloc[0]
    assert r0["job_id"] == "topcv_0" and r0["source"] == "topcv" and r0["province"] == "TP. Hà Nội"
    assert list(r0["skills"]) == ["docker", "python"]            # slug, bỏ trùng, sắp xếp; mọi `via`
    assert list(s.iloc[1]["skills"]) == []                         # tin không có kỹ năng: list rỗng
    assert s["seniority_inferred"].dtype == bool and s["salary_outlier"].dtype == bool
    assert s["posted_month"].iloc[0] == "2026-10"


def test_s2_work_mode_unknown_and_s3_employment_type_null():
    s = SV.build_silver(_t04(), _skills())
    assert s.iloc[1]["work_mode"] == "unknown"
    assert s["employment_type"].isna().all()


def test_missing_source_column_stops():
    with pytest.raises(SV.SilverContractError, match="tinh_chinh"):
        SV.build_silver(_t04().drop(columns=["tinh_chinh"]), _skills())


def test_bool_column_with_null_stops():
    t = _t04()
    t["is_negotiable"] = t["is_negotiable"].astype(object)
    t.loc[0, "is_negotiable"] = None
    with pytest.raises(SV.SilverContractError, match="is_negotiable"):
        SV.build_silver(t, _skills())


def test_check_values_match_source():
    t = _t04()
    s = SV.build_silver(t, _skills())
    assert SV.check_silver(s, t) == []
    s.loc[0, "title"] = "khác"
    assert any("title" in e for e in SV.check_silver(s, t))
