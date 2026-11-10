# -*- coding: utf-8 -*-
"""PH6 (chuẩn hóa trường, gom chức danh) và PH7 (thiếu/ngoại lai có cờ). Chuỗi thật lấy từ data/preprocessing/01_clean,
ghi job_id nguồn trong chú thích. Không ghi file dữ liệu; file anomalies ghi vào tmp_path."""
from __future__ import annotations

import json
import math

import pandas as pd
import pytest

from preprocessing.common.constants import USD_VND
from preprocessing.missing_outlier.missing_rules import (
    infer_experience_from_level, infer_level_from_experience, range_flags, salary_status, tinh_status)
from preprocessing.missing_outlier.outlier_handler import fix_common_salary_input_errors, iqr_flags_by_group
from preprocessing.normalization.company_key import compute_company_keys, fix_tone
from preprocessing.normalization.job_title import build_title_dict, canonical_title, core_title, family_from_title, fold
from preprocessing.normalization.run import (
    _fallback_tinh, apply_global_salary_normalizations, build_anomalies, work_mode, write_anomalies)
from preprocessing.transformation.experience_parser import parse_experience, parse_experience_range
from preprocessing.transformation.salary_parser_legacy import detect_other_currency, parse_salary_cascade

# ------------------------------------------------------------------ lương / tiền tệ
def test_usd_rate_constant_is_single_source():
    assert USD_VND == 25_400.0


def test_usd_range_not_divided_by_12():
    # vietnamworks 2117441, 2117446 (raw "8000 - 9000 USD"); JD có "năm" không được làm chia 12
    r = parse_salary_cascade("8000 - 9000 USD", jd_text="Yêu cầu 2 năm kinh nghiệm")
    assert (r["salary_min_vnd"], r["salary_max_vnd"]) == (203_200_000.0, 228_600_000.0)
    assert fix_common_salary_input_errors(r["salary_max_vnd"], "2 năm kinh nghiệm") == 228_600_000.0
    assert fix_common_salary_input_errors(2000.0) == 2000.0  # không coi số nhỏ là USD


@pytest.mark.parametrize("text,lo,hi", [
    ("1,000 - 2,000 USD", 25_400_000.0, 50_800_000.0),   # topcv
    ("Tới 1,500 USD", None, 38_100_000.0),               # topcv
    ("1.000 USD to 2.500 USD", 25_400_000.0, 63_500_000.0),  # topdev
    ("6,000 - 9,000 USD", 152_400_000.0, 228_600_000.0),  # itviec vinsoc
])
def test_usd_conversion_real_strings(text, lo, hi):
    r = parse_salary_cascade(text)
    assert r["salary_currency_original"] == "USD"
    assert (r["salary_min_vnd"], r["salary_max_vnd"]) == (lo, hi)


@pytest.mark.parametrize("text,lo,hi", [
    ("7000000 - 10000000 USD", 7_000_000.0, 10_000_000.0),   # vietnamworks 2103985: số VND bị gắn nhãn USD
    ("30000000 - 50000000 USD", 30_000_000.0, 50_000_000.0),  # vietnamworks 2104725
])
def test_usd_label_with_vnd_sized_numbers_is_reinterpreted(text, lo, hi):
    r = parse_salary_cascade(text)
    assert r["salary_currency_original"] == "VND" and r["currency_reinterpreted"] == "USD->VND"
    assert (r["salary_min_vnd"], r["salary_max_vnd"]) == (lo, hi)


def test_usd_annual_only_with_evidence_in_jd():
    # vietnamworks 2119566: header "22000 - 36000 USD", JD ghi "Annual Salary: 22,000~36,000 USD"
    jd = "HCMC Vietnam Annual Salary: 22,000~36,000 USD The term of contract: 12 months"
    r = parse_salary_cascade("22000 - 36000 USD", jd_text=jd)
    assert r["pay_period"] == "year"
    assert r["salary_min_vnd"] == pytest.approx(22000 * USD_VND / 12)
    # cùng header nhưng JD không nói lương năm: giữ nguyên, bị coi là đọc sai (salary_suspect)
    assert parse_salary_cascade("22000 - 36000 USD", jd_text="2 năm kinh nghiệm")["salary_suspect"] is True


def test_other_currency_is_detected_not_guessed():
    # dẫn xuất từ chuỗi thật "400 - 900 USD" (topcv) bằng cách đổi mã tiền: dữ liệu hiện chưa có tiền tệ khác
    assert detect_other_currency("400 - 900 SGD") == "SGD" and detect_other_currency("400 - 900 USD") is None
    r = parse_salary_cascade("400 - 900 SGD")
    assert r["salary_currency_original"] == "SGD" and r["salary_min_vnd"] is None and r["salary_max_vnd"] is None


# ------------------------------------------------------------------ kinh nghiệm
@pytest.mark.parametrize("text,expected", [
    ("Không yêu cầu", (0.0, None, "explicit_zero")),                 # jobsgo, topcv
    ("Dưới một năm kinh nghiệm", (0.0, 1.0, "upper_bound")),         # glints
    ("Lên đến 2 Năm", (0.0, 2.0, "upper_bound")),                    # careerviet
    ("Hơn 5 năm", (5.0, None, "lower_bound")),                       # careerviet
    ("3.1 năm (37 tháng)", (3.0, None, "compound_years_months")),   # itviec, K4: phần nguyên
    ("0.8 năm (10 tháng)", (0.0, None, "compound_years_months")),
    ("5.1 năm (61 tháng)", (5.0, None, "compound_years_months")),
])
def test_experience_real_strings(text, expected):
    assert parse_experience_range(text) == expected


def test_experience_wrapper_keeps_zero_zero():
    assert parse_experience("Không yêu cầu") == (0.0, 0.0)


# ------------------------------------------------------------------ chức danh
def test_core_title_real_titles():
    core, lvl, hint = core_title("[All level] BackEnd Engineer (Java, Spring Boot) - Khối Công nghệ thông tin (2025TD1785)")
    assert (core, hint) == ("BackEnd Engineer", ["Java", "Spring Boot"])
    assert core_title("Nhân Viên IT- Thu Nhập 15-35 Triệu- Tại Hải Phòng")[0] == "IT"
    core, lvl, _ = core_title("Tuyển Gấp- Junior QA Automation Engineer (M/f/d)")
    assert (core, lvl) == ("QA Automation Engineer", "Junior")
    core, lvl, _ = core_title("Senior DevOps Engineer")
    assert (core, lvl) == ("DevOps Engineer", "Senior")
    assert core_title("Embedded Engineer (C/C++, Firmware, Git, RTOS)")[0] == "Embedded Engineer"


def test_title_dictionary_exact_alias_fuzzy_and_short_guard():
    d = build_title_dict([{"canonical": "Business Analyst", "family": "Product/Project",
                           "aliases": ["business analyst", "ba", "phân tích nghiệp vụ"], "approved": True}])
    assert canonical_title(fold("Business Analyst"), d)[:2] == ("Business Analyst", "exact")
    assert canonical_title(fold("Chuyên viên phân tích nghiệp vụ"), d)[:2] == ("Business Analyst", "alias")
    canon, src, score = canonical_title(fold("Busines Analyst"), d)  # lỗi gõ dựng từ "Business Analyst"
    assert (canon, src) == ("Business Analyst", "fuzzy") and score >= 90
    assert canonical_title("ba", d)[:2] == ("Business Analyst", "exact")   # chỉ exact, độ dài 2 không đi fuzzy
    assert canonical_title("bb", d)[0] is None
    assert family_from_title(fold("x"), "Business Analyst", [], d) == ("Product/Project", "canonical")


def test_unapproved_dictionary_entries_are_not_loaded(tmp_path):
    from preprocessing.normalization.job_title import load_title_dict
    f = tmp_path / "t.json"
    f.write_text(json.dumps({"entries": [{"canonical": "A B", "aliases": ["a b"], "approved": False},
                                          {"canonical": "C D", "aliases": ["c d"], "approved": True}]}), encoding="utf-8")
    assert list(load_title_dict(f)["exact"]) == ["c d"]


def test_job_titles_json_candidates_all_unapproved():
    from preprocessing.common import REPO_ROOT
    data = json.loads((REPO_ROOT / "preprocessing/dictionaries/job_titles.json").read_text(encoding="utf-8"))
    assert data["entries"] and all(e["approved"] is False for e in data["entries"])


# ------------------------------------------------------------------ địa điểm, công ty
def test_tinh_fallback_and_work_mode():
    # topcv/itviec: locations không ra tỉnh nhưng raw_location_text có
    rec = {"raw_location_text": "Tòa nhà MB, số 18 Lê Văn Lương, Phường Yên Hòa, Hà Nội"}
    assert _fallback_tinh(rec) == ("TP. Hà Nội", "raw_location_full")
    assert _fallback_tinh({"raw_location_text": "Quận Cầu Giấy"}) == (None, None)  # quận đơn lẻ: không đoán
    assert work_mode([], "x", "Remote", None) == "remote"
    assert work_mode([], "Hybrid Backend", "Hà Nội", "TP. Hà Nội") == "hybrid"
    assert work_mode([], "Backend", "Hà Nội", "TP. Hà Nội") == "onsite" and work_mode([], "Backend", "", None) == "unknown"


def test_company_key_merges_subsets_not_lookalikes():
    names = ["công nghệ quảng ích", "công nghệ quảng ích qig", "sotatek", "statek", "công nghệ dtg", "công nghệ itg",
             "truyền thông văn hoá việt", "truyền thông văn hóa việt", None, ""]
    m, pending = compute_company_keys(names)
    assert m["công nghệ quảng ích"] == m["công nghệ quảng ích qig"]
    assert m["truyền thông văn hoá việt"] == m["truyền thông văn hóa việt"]
    assert m["sotatek"] != m["statek"] and m["công nghệ dtg"] != m["công nghệ itg"]
    assert ("công nghệ dtg", "công nghệ itg") in [(a, b) for a, b, _ in pending]
    assert fix_tone("hoá") == "hóa"


# ------------------------------------------------------------------ PH7
def test_salary_status_rules():
    assert salary_status(None, None, True)["salary_status"] == "negotiable"
    assert salary_status(None, None, False)["salary_status"] == "not_stated"
    r = salary_status(None, 50e6, True)
    assert r["salary_status"] == "value" and r["salary_negotiable_with_value"] is True


def test_level_and_experience_inference_with_flags():
    assert infer_level_from_experience(None, 1) == {"seniority": "Junior", "level_inferred": True, "from_years": True}
    assert infer_level_from_experience(None, 0)["seniority"] == "Intern/Fresher"
    assert infer_level_from_experience(None, 3)["seniority"] == "Middle"
    assert infer_level_from_experience(None, 5)["seniority"] == "Senior"
    assert infer_level_from_experience("Senior", 1) == {"seniority": "Senior", "level_inferred": False, "from_years": False}
    assert infer_level_from_experience(None, None)["seniority"] is None
    assert infer_experience_from_level(None, "Intern/Fresher", "raw")["exp_min_years"] == 0.0
    assert infer_experience_from_level(None, "Senior", "title")["exp_source"] == "unknown"
    # chống vòng: cấp suy từ số năm không dùng để suy ngược kinh nghiệm
    assert infer_experience_from_level(None, "Intern/Fresher", "kinh_nghiem")["exp_min_years"] is None


def test_range_flags_and_tinh_status():
    f = range_flags(203_200_000.0, 228_600_000.0, None, None)  # vietnamworks 8000 - 9000 USD
    assert f["salary_out_of_range"] and not f["salary_min_gt_max"]
    assert range_flags(1_500_000.0, None, None, None)["salary_out_of_range"]       # < 2 triệu
    assert range_flags(20e6, 10e6, 20, None) == {"salary_out_of_range": False, "salary_min_gt_max": True, "exp_out_of_range": True}
    assert tinh_status(None, "onsite", False) == "unknown" and tinh_status(None, "remote", False) == "remote"
    assert tinh_status(None, "unknown", True) == "foreign"


def test_iqr_by_group_scope():
    s = pd.Series([float(x) for x in range(10, 50)] + [400.0] + [10.0] * 12)
    g = pd.Series(["Junior"] * 41 + ["Senior"] * 12)
    out = iqr_flags_by_group(s, g, min_n=30)
    assert out.loc[40, "outlier"] and out.loc[40, "scope"] == "level"
    assert set(out.loc[41:, "scope"]) == {"not_enough_data"} and not out.loc[41:, "outlier"].any()
    assert iqr_flags_by_group(s, pd.Series([None] * len(s)), min_n=30)["scope"].eq("pooled").all()


def test_anomalies_carry_job_id_and_source(tmp_path):
    base = {"source_platform": "vietnamworks", "source_job_id": "2117441", "job_id_global": "g1", "source_url": "u",
            "raw_salary_text": "8000 - 9000 USD", "description_clean": "", "seniority": "Junior"}
    rows = [{**base, "salary_min_vnd": 203_200_000.0, "salary_max_vnd": 228_600_000.0, "exp_min_years": 1.0, "exp_max_years": None,
             "level_inferred": True, "salary_period_raw": "month", "salary_currency_raw": "USD"}]
    out, _ = apply_global_salary_normalizations(rows)
    an = build_anomalies(out)
    kinds = {a["kind"] for a in an}
    assert {"salary_out_of_range", "level_inferred"} <= kinds
    assert all(a["job_id"] == "2117441" and a["source"] == "vietnamworks" for a in an)
    p = write_anomalies(an, tmp_path / "anomalies.json")
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["total"] == len(an) and data["by_kind"]["level_inferred"] == 1
    assert not math.isnan(out[0]["salary_max_vnd"])  # số không bị sửa hay xóa
