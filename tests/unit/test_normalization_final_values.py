"""Bước 04, luật mới 2.2 (đặc tả 04_normalization.md, người dùng duyệt 19/11): N14 sửa, N19, N2 bổ sung, M4 sửa, Q1.

Giá trị cuối chọn từ các cột T9 của bước 03; bước 04 không trích lại JD.
"""
import pandas as pd
import pytest

from preprocessing.normalization import final_values as FV
from preprocessing.normalization import run as N


# ---------------------------------------------------------------- N14
@pytest.mark.parametrize("rec,old,expected", [
    ({"work_mode_raw": "hybrid", "work_mode_jd": None}, "onsite", ("hybrid", "raw")),
    ({"work_mode_raw": "onsite", "work_mode_jd": "remote", "work_mode_conflict": True, "work_mode_jd_strong": True},
     "onsite", ("remote", "jd_over_raw")),
    ({"work_mode_raw": "onsite", "work_mode_jd": "remote", "work_mode_conflict": True, "work_mode_jd_strong": False},
     "onsite", ("onsite", "raw")),                                   # JD yếu không thắng ô của sàn
    ({"work_mode_raw": None, "work_mode_jd": "hybrid"}, "onsite", ("hybrid", "jd")),
    ({"work_mode_raw": None, "work_mode_jd": None}, "onsite", ("onsite", "location")),
    ({"work_mode_raw": None, "work_mode_jd": None}, "unknown", ("unknown", "unknown")),
])
def test_n14_work_mode_order(rec, old, expected):
    assert FV.final_work_mode(rec, old) == expected


# ---------------------------------------------------------------- N19
@pytest.mark.parametrize("rec,expected", [
    ({"job_title_clean": "Thực Tập Sinh Java", "employment_type_raw": "full_time"}, ("internship", "title")),  # EI1 thắng raw
    ({"job_title_clean": "Backend Intern", "employment_type_raw": None}, ("internship", "title")),
    ({"job_title_clean": "Backend Developer", "employment_type_raw": "part_time", "employment_type_jd": "full_time"}, ("part_time", "raw")),
    ({"job_title_clean": "Backend Developer", "employment_type_raw": None, "employment_type_jd": "contract"}, ("contract", "jd")),
    ({"job_title_clean": "Backend Developer", "employment_type_raw": None, "employment_type_jd": None}, (None, "unknown")),
    ({"job_title_clean": "International Sales Engineer", "employment_type_raw": "full_time"}, ("full_time", "raw")),  # không khớp chuỗi con
])
def test_n19_employment_type(rec, expected):
    assert FV.final_employment_type(rec) == expected


# ---------------------------------------------------------------- M4
def test_m4_itviec_jd_first_then_jsonld():
    r = FV.select_experience("itviec", {"exp_min_years": 3.08, "exp_min_years_jd": 2.0, "exp_jd_kind": "jd"})
    assert (r["exp_min_years"], r["exp_source"], r["exp_conflict"], r["exp_min_years_parsed"]) == (2.0, "jd", True, 3.08)
    r = FV.select_experience("itviec", {"exp_min_years": 0.83, "exp_min_years_jd": None})
    assert (r["exp_min_years"], r["exp_source"]) == (0.83, "itviec_jsonld")


def test_m4_other_sources_raw_first_jd_fills():
    r = FV.select_experience("topcv", {"exp_min_years": 1.0, "exp_min_years_jd": 3.0, "exp_jd_kind": "jd"})
    assert (r["exp_min_years"], r["exp_source"], r["exp_conflict"]) == (1.0, "raw", True)
    r = FV.select_experience("topdev", {"exp_min_years": None, "exp_min_years_jd": 0.0, "exp_jd_kind": "jd_zero"})
    assert (r["exp_min_years"], r["exp_source"], r["exp_conflict"]) == (0.0, "jd_zero", False)
    r = FV.select_experience("topcv", {"exp_min_years": 2.0, "exp_min_years_jd": 2.5, "exp_jd_kind": "jd"})
    assert r["exp_conflict"] is False                                 # lệch dưới 1 năm
    r = FV.select_experience("glints", {"exp_min_years": None, "exp_min_years_jd": None})
    assert (r["exp_min_years"], r["exp_source"]) == (None, None)


# ---------------------------------------------------------------- Q1
def test_q1_quarantine_reason():
    assert FV.quarantine_reason({"translation_status": "failed"}) == "TRANSLATION_FAILED"
    for st in ("translated", "not_needed", None):
        assert FV.quarantine_reason({"translation_status": st}) is None


# ---------------------------------------------------------------- tích hợp trong process_source_records
def _row(**kw):
    base = {"job_id_global": "topcv_1", "source_platform": "topcv", "source_job_id": "1", "source_url": "u",
            "job_title_clean": "Backend Developer", "raw_seniority_text": None, "locations": [],
            "raw_location_text": "Hà Nội", "company_name": "Công ty A", "skills_clean": [],
            "salary_min_vnd": float("nan"), "salary_max_vnd": float("nan"), "is_negotiable": True,  # như bảng 03 thật
            "exp_min_years": None, "exp_max_years": None, "exp_min_years_jd": None, "exp_jd_kind": None,
            "work_mode_raw": None, "work_mode_jd": None, "work_mode_conflict": False, "work_mode_jd_strong": False,
            "employment_type_raw": "full_time", "employment_type_jd": None, "translation_status": "not_needed"}
    return {**base, **kw}


def test_n2_internship_gives_intern_level_and_seniority_inferred_meaning():
    rows, _ = N.process_source_records("topcv", [_row(job_title_clean="Backend Developer",
                                                      employment_type_raw="internship")], dry_run=True)
    r = rows[0]
    assert (r["employment_type"], r["seniority"], r["seniority_source"]) == ("internship", "Intern/Fresher", "employment_type")
    assert r["level_inferred"] is True                                  # Silver: suy ra ở bước 04, không phải ô của sàn
    rows, _ = N.process_source_records("topcv", [_row(raw_seniority_text="Trưởng nhóm")], dry_run=True)
    assert (rows[0]["seniority"], rows[0]["level_inferred"]) == ("Lead/Manager", False)   # từ ô của sàn
    rows, _ = N.process_source_records("topcv", [_row(job_title_clean="Senior Backend Developer")], dry_run=True)
    assert (rows[0]["seniority"], rows[0]["level_inferred"]) == ("Senior", True)          # từ tiêu đề


def test_m4_level_fill_after_selection_and_source_names():
    rows, _ = N.process_source_records("topcv", [_row(job_title_clean="Senior Backend Developer")], dry_run=True)
    r = rows[0]
    assert (r["exp_min_years"], r["exp_source"], r["exp_inferred"]) == (4.0, "level_senior", True)
    rows, _ = N.process_source_records("topcv", [_row(exp_min_years=None, exp_min_years_jd=3.0, exp_jd_kind="jd")],
                                       dry_run=True)
    r = rows[0]
    assert (r["exp_min_years"], r["exp_source"], r["exp_inferred"], r["seniority"]) == (3.0, "jd", False, "Middle")


def test_q1_run_splits_quarantine_and_conserves(tmp_path, monkeypatch):
    rows = [_row(job_id_global=f"topcv_{i}", source_job_id=str(i), company_name=f"Công ty {i}") for i in range(4)]
    rows[1]["translation_status"] = "failed"
    inp = tmp_path / "in.parquet"
    pd.DataFrame(rows).to_parquet(inp, index=False)
    out = tmp_path / "04" / "all.parquet"
    monkeypatch.setattr(N, "IN_FILE", inp)
    monkeypatch.setattr(N, "OUT_FILE", out)
    monkeypatch.setattr(N, "QUARANTINE_FILE", out.parent / "quarantine.parquet")
    monkeypatch.setattr(N, "ANOMALIES_FILE", tmp_path / "anomalies.json")
    monkeypatch.setattr(N.step_report, "REPORTS_ROOT", tmp_path / "reports")
    monkeypatch.setattr(N, "_write_company_pairs", lambda pending: None)
    reps = N.run(["topcv"], dry_run=False)
    kept = pd.read_parquet(out)
    q = pd.read_parquet(out.parent / "quarantine.parquet")
    assert sorted(kept.job_id_global) == ["topcv_0", "topcv_2", "topcv_3"]
    assert list(q.job_id_global) == ["topcv_1"] and list(q.quarantine_reason) == ["TRANSLATION_FAILED"]
    assert set(kept.columns) <= set(q.columns)                          # cùng cột, thêm quarantine_reason
    d = reps["topcv"].data
    assert d["input"]["rows"] == 4 and d["output"]["rows"] == 3 and d["checks"]["rows_conserved"]
    assert any(x["rule"] == "Q1" and x["rows"] == 1 for x in d["dropped"])
