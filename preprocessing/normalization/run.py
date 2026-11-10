# -*- coding: utf-8 -*-
"""Bước 04 Normalization (docs/spec/preprocessing/spec/P4_normalization.md).

Chuẩn hóa 34 tỉnh/thành sau sáp nhập, 5 cấp bậc (Intern/Fresher..Lead/Manager), 12 nhóm nghề SPEC-01 + Other
(chức danh lõi -> chức danh chuẩn -> nhóm), ánh xạ kỹ năng chuẩn, company_key (rapidfuzz), PH7 thiếu/ngoại lai có cờ
(IQR theo cấp bậc, khoảng lương 2-100 triệu), Winsorize 1-99% cột riêng, log1p lương. Mọi cờ ngoại lai/suy luận
kèm job_id và nguồn trong anomalies.json. Nhãn mâu thuẫn được gắn cờ bằng luật if-else, không gọi model. Đọc và ghi một file all.parquet (đã gộp 8 nguồn từ bước Integration).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from preprocessing.common import REPO_ROOT, SOURCES
from preprocessing.common.province import fold, is_foreign, is_remote, key as prov_key, name as prov_name
from preprocessing.common.step_report import REPORTS_ROOT, StepReport, merge_reports
from preprocessing.missing_outlier.missing_rules import (
    infer_experience_from_level,
    infer_level_from_experience,
    range_flags,
    salary_status,
    tinh_status,
)
from preprocessing.missing_outlier.outlier_handler import (
    detect_iqr_outliers,
    iqr_flags_by_group,
    winsorize_series,
)
from preprocessing.normalization.company_key import compute_company_keys
from preprocessing.normalization.job_title import (
    canonical_title,
    core_title,
    family_from_title,
    fold as tfold,
    is_generic_title,
    load_title_dict,
)
from preprocessing.normalization.cross_deduplicator import normalize_company_name
from preprocessing.transformation.salary_parser import MONTHLY_MAX_VND, MONTHLY_MIN_VND
from preprocessing.normalization.text_cleaner import (
    canonicalize_skills,
    classify_seniority,
    has_term,
    seniority_level,
)

STEP = "04_normalization"
DATA_DIR = REPO_ROOT / "data"
IN_FILE = DATA_DIR / "preprocessing" / "03_transformation" / "all.parquet"
OUT_FILE = DATA_DIR / "preprocessing" / STEP / "all.parquet"

KEY_FIELDS = (
    "locations", "tinh_chinh", "seniority", "seniority_source",
    "job_family", "job_family_source", "skills_std", "company_norm",
    "salary_min_vnd_capped", "salary_max_vnd_capped",
    "log_salary_min", "log_salary_max", "is_outlier_salary",
    "job_title_core", "title_canonical", "company_key", "work_mode", "tinh_status",
    "salary_status", "level_inferred", "exp_min_years", "exp_source", "salary_out_of_range",
    "salary_iqr_outlier_by_level",
)


def _is_filled(val: Any) -> bool:
    if val is None:
        return False
    if isinstance(val, (float, int)) and pd.isna(val):
        return False
    if isinstance(val, str):
        return bool(val.strip())
    if isinstance(val, (list, tuple, dict, set)):
        return len(val) > 0
    if hasattr(val, "__len__"):
        return len(val) > 0
    return True


def _normalize_locations(locations_val: Any) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """N1: Chuẩn hóa địa điểm theo 34 tỉnh/thành sau sáp nhập."""
    if locations_val is None:
        return [], None

    if isinstance(locations_val, (list, tuple)):
        loc_list = list(locations_val)
    elif hasattr(locations_val, "tolist"):
        loc_list = locations_val.tolist()
    else:
        loc_list = []

    norm_locs: List[Dict[str, Any]] = []
    for item in loc_list:
        if isinstance(item, dict):
            loc = dict(item)
        else:
            loc = {"raw": str(item)}

        raw_text = loc.get("raw") or ""
        input_tinh = loc.get("tinh_thanh") or raw_text

        # Tra cứu tỉnh chuẩn
        pk = prov_key(input_tinh)
        pn = prov_name(pk)

        loc["tinh_key"] = pk
        loc["tinh_thanh"] = pn

        # Tên cũ nếu raw khác tên chuẩn
        if pn and input_tinh and fold(input_tinh) != fold(pn):
            loc["tinh_cu"] = str(input_tinh).strip()
        else:
            loc["tinh_cu"] = None

        loc["remote"] = is_remote(raw_text) or is_remote(input_tinh)
        loc["ngoai_vn"] = is_foreign(raw_text) or is_foreign(input_tinh)
        norm_locs.append(loc)

    primary_city = next((l["tinh_thanh"] for l in norm_locs if l.get("tinh_thanh")), None)
    return norm_locs, primary_city


SENIOR_LEVELS = {"Senior", "Lead/Manager"}
ENTRY_LEVELS = {"Intern/Fresher"}
ANOMALIES_FILE = REPORTS_ROOT / STEP / "anomalies.json"
_HYBRID_RE = re.compile(r"(?<!\w)hybrid(?!\w)", re.I)
_REMOTE_TITLE_RE = re.compile(r"(?<!\w)(remote|work from home|wfh|từ xa)(?!\w)", re.I)


def _num(v: Any) -> Optional[float]:
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else float(v)


def seniority_conflict(sen: Optional[str], exp_min: Any, exp_max: Any) -> bool:
    """N2b: cấp bậc mâu thuẫn số năm kinh nghiệm (Senior mà < 2 năm, Intern/Fresher mà ≥ 3 năm)."""
    lo, hi = _num(exp_min), _num(exp_max)
    if sen in SENIOR_LEVELS:
        return (hi if hi is not None else lo) is not None and (hi if hi is not None else lo) < 2
    if sen in ENTRY_LEVELS:
        return lo is not None and lo >= 3
    return False


def work_mode(locs: List[Dict[str, Any]], title: Any, raw_location: Any, tinh: Optional[str]) -> str:
    """N14 (K8): chỉ địa điểm và tiêu đề, không dùng JD. remote -> hybrid -> onsite (có tỉnh) -> unknown."""
    title, raw_location = str(title or ""), str(raw_location or "")
    if any(l.get("remote") for l in locs) or is_remote(raw_location) or _REMOTE_TITLE_RE.search(title):
        return "remote"
    if _HYBRID_RE.search(title) or _HYBRID_RE.search(raw_location):
        return "hybrid"
    return "onsite" if tinh else "unknown"


def _fallback_tinh(rec: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """N13: raw_location_text toàn chuỗi, rồi company_address. Quận/huyện đơn lẻ không suy ra tỉnh."""
    for field, tag in (("raw_location_text", "raw_location_full"), ("company_address", "company_address")):
        txt = rec.get(field)
        if isinstance(txt, str) and txt.strip():
            name = prov_name(prov_key(txt))
            if name:
                return name, tag
    return None, None


def process_source_records(
    source: str,
    input_records: List[Dict[str, Any]],
    dry_run: bool = True,
    title_dict: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], StepReport]:
    report = StepReport(STEP, source, dry_run)
    total_rows = len(input_records)
    report.set_io(IN_FILE, total_rows, OUT_FILE, total_rows)
    title_dict = title_dict if title_dict is not None else load_title_dict()

    rows: List[Dict[str, Any]] = []
    cnt = dict(n1=0, n2=0, n3=0, n4=0, n5=0, n13=0, n16=0, can_kiem=0, m3c=0, m4=0)
    ex: Dict[str, List[Dict[str, Any]]] = {k: [] for k in ("n1", "n2", "n3", "n13", "n16")}

    def _ex(key: str, rec: Dict[str, Any], field: str, before: Any, after: Any) -> None:
        if len(ex[key]) < 3:
            ex[key].append({"job_id": rec.get("source_job_id") or rec.get("job_id_global") or "", "field": field,
                            "before": str(before), "after": str(after), "url": rec.get("source_url") or ""})

    for row in input_records:
        rec = dict(row)

        # N1 + N13: địa điểm 34 tỉnh
        locs, primary_city = _normalize_locations(rec.get("locations"))
        rec["locations"] = locs
        rec["tinh_source"] = "locations" if primary_city else None
        if not primary_city:
            primary_city, tag = _fallback_tinh(rec)
            rec["tinh_source"] = tag
            if primary_city:
                cnt["n13"] += 1
                _ex("n13", rec, "tinh_chinh", rec.get("raw_location_text"), primary_city)
        rec["tinh_chinh"] = primary_city
        if primary_city or any(l.get("remote") or l.get("ngoai_vn") for l in locs):
            cnt["n1"] += 1
            if primary_city:
                _ex("n1", rec, "tinh_chinh", rec.get("raw_location_text"), primary_city)

        # N14 work_mode + M7 tinh_status
        rec["work_mode"] = work_mode(locs, rec.get("job_title_clean"), rec.get("raw_location_text"), primary_city)
        rec["tinh_status"] = tinh_status(primary_city, rec["work_mode"], any(l.get("ngoai_vn") for l in locs))

        # N4 kỹ năng chuẩn
        skills_std = canonicalize_skills(rec.get("skills_clean"))
        rec["skills_std"] = skills_std
        cnt["n4"] += bool(skills_std)

        # N15 chức danh lõi
        core, _title_level, tech_hint = core_title(rec.get("job_title_clean"))
        rec["job_title_core"], rec["title_tech_hint"] = core, tech_hint

        # N12 cấp bậc (raw, title) rồi PH7 M3c (số năm, có cờ)
        sen, sen_src = classify_seniority(rec.get("raw_seniority_text"), rec.get("job_title_clean"))
        inf = infer_level_from_experience(sen, rec.get("exp_min_years"))
        sen = inf["seniority"]
        rec["seniority"] = sen
        rec["level_inferred"] = inf["level_inferred"]
        rec["seniority_source"] = "kinh_nghiem" if inf["from_years"] else (sen_src or "none")
        rec["seniority_level"] = seniority_level(sen)
        rec["seniority_can_kiem"] = (not inf["from_years"]) and seniority_conflict(
            sen, rec.get("exp_min_years"), rec.get("exp_max_years"))
        cnt["n2"] += bool(sen)
        cnt["m3c"] += inf["from_years"]
        if sen:
            _ex("n2", rec, "seniority", rec.get("raw_seniority_text") or rec.get("job_title_clean"), f"{sen} ({rec['seniority_source']})")

        # PH7 M4 kinh nghiệm
        ei = infer_experience_from_level(rec.get("exp_min_years"), sen, rec["seniority_source"])
        rec["exp_min_years"], rec["exp_inferred"], rec["exp_source"] = ei["exp_min_years"], ei["exp_inferred"], ei["exp_source"]
        cnt["m4"] += ei["exp_inferred"]

        # N16-N17 chức danh chuẩn -> nhóm nghề
        core_fold = tfold(core)
        canon, csrc, score = canonical_title(core_fold, title_dict)
        fam, fsrc = family_from_title(core_fold, canon, skills_std, title_dict, tech_hint)
        rec["title_canonical"], rec["title_canonical_source"], rec["title_match_score"] = canon, csrc, score
        rec["job_family"], rec["job_family_source"] = fam, fsrc
        rec["job_family_generic_title"] = is_generic_title(core)
        rec["job_family_can_kiem"] = fam != "Other" and not skills_std
        cnt["n16"] += canon is not None
        if fam != "Other":
            cnt["n3"] += 1
            _ex("n3", rec, "job_family", rec.get("job_title_clean"), f"{fam} ({fsrc})")
        cnt["can_kiem"] += bool(rec["seniority_can_kiem"] or rec["job_family_can_kiem"])

        # N5 công ty
        c_norm = normalize_company_name(rec.get("company_name"))
        rec["company_norm"] = c_norm
        cnt["n5"] += bool(c_norm)

        # PH7 M1, M2, M5, M8 (cờ theo từng tin; IQR làm ở bảng gộp)
        rec.update(salary_status(rec.get("salary_min_vnd"), rec.get("salary_max_vnd"), bool(rec.get("is_negotiable"))))
        rec.update(range_flags(rec.get("salary_min_vnd"), rec.get("salary_max_vnd"), rec.get("exp_min_years"), rec.get("exp_max_years")))
        rows.append(rec)

    report.rule("N1", "Chuẩn hóa địa phương 34 tỉnh/thành sau sáp nhập", "modify", cnt["n1"], ex["n1"])
    report.rule("N13", "Tỉnh từ raw_location_text/company_address khi locations không ra tỉnh", "modify", cnt["n13"], ex["n13"])
    report.rule("N2", "Cấp bậc 5 cấp (raw -> tiêu đề; số năm chỉ ở M3c, có cờ level_inferred)", "modify", cnt["n2"], ex["n2"])
    report.rule("N3", "Nhóm nghề: 12 nhóm SPEC-01 + Other", "modify", cnt["n3"], ex["n3"])
    report.rule("N16", "Chức danh chuẩn từ từ điển đã duyệt (exact/alias/fuzzy)", "modify", cnt["n16"])
    report.rule("N4", "Ánh xạ kỹ năng chuẩn theo từ điển", "modify", cnt["n4"])
    report.rule("N5", "Chuẩn hóa tên công ty", "modify", cnt["n5"])
    report.rule("N2b", "Nhãn mâu thuẫn với kinh nghiệm/kỹ năng: gắn cờ cần kiểm", "flag", cnt["can_kiem"])
    report.rule("M3c", "Cấp bậc trống suy từ số năm (X6), level_inferred=True", "flag", cnt["m3c"])
    report.rule("M4", "Intern/Fresher thiếu kinh nghiệm điền 0, exp_inferred=True", "flag", cnt["m4"])
    report.check_conserved()
    return rows, report


def apply_global_salary_normalizations(
    all_rows: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """N6, N7 + PH7 M5/M6: không sửa số lương; NaN hóa ngoài 1-500 triệu (salary_suspect), cờ ngoài 2-100 triệu,
    cờ IQR gộp (cột cũ) và IQR theo cấp bậc, Winsorize 1-99% ra cột riêng, rồi log1p."""
    if not all_rows:
        return [], {}

    df = pd.DataFrame(all_rows)

    # N6a: ngoài 1–500 triệu là đọc sai, bỏ số trước khi tính IQR
    bad = pd.Series(False, index=df.index)
    for c in ("salary_min_vnd", "salary_max_vnd"):
        v = pd.to_numeric(df[c], errors="coerce")
        bad |= (v < MONTHLY_MIN_VND) | (v > MONTHLY_MAX_VND)
    prev = df["salary_suspect"].fillna(False).astype(bool) if "salary_suspect" in df else False
    df["salary_suspect"] = bad | prev
    df.loc[bad, ["salary_min_vnd", "salary_max_vnd"]] = np.nan

    sal_eval = df["salary_max_vnd"].combine_first(df["salary_min_vnd"])

    # IQR gộp (cột cũ, Monitoring dùng)
    iqr_res = detect_iqr_outliers(sal_eval)
    lower_b, upper_b = iqr_res.get("lower_bound"), iqr_res.get("upper_bound")
    if lower_b is not None and upper_b is not None:
        is_outlier = (sal_eval < lower_b) | (sal_eval > upper_b)
    else:
        is_outlier = pd.Series(False, index=df.index)
    df["is_outlier_salary"] = is_outlier.fillna(False)

    # M6: IQR theo cấp bậc (chỉ cờ)
    flags = iqr_flags_by_group(sal_eval, df["seniority"] if "seniority" in df else pd.Series(None, index=df.index, dtype=object))
    df["salary_iqr_outlier_by_level"] = flags["outlier"]
    df["salary_iqr_scope"] = flags["scope"]
    df["salary_iqr_lower"], df["salary_iqr_upper"] = flags["lower"], flags["upper"]

    # M5: cờ khoảng 2-100 triệu tính lại sau N6a (số đã NaN hóa không còn bị cờ), M8 min > max
    rf = [range_flags(a, b, c, d) for a, b, c, d in zip(
        df["salary_min_vnd"], df["salary_max_vnd"],
        df["exp_min_years"] if "exp_min_years" in df else [None] * len(df),
        df["exp_max_years"] if "exp_max_years" in df else [None] * len(df))]
    for k in ("salary_out_of_range", "salary_min_gt_max", "exp_out_of_range"):
        df[k] = [r[k] for r in rf]

    # X4: winsorize giữ làm cột riêng, không thay cột gốc
    df["salary_min_vnd_capped"] = winsorize_series(df["salary_min_vnd"], 0.01, 0.99)
    df["salary_max_vnd_capped"] = winsorize_series(df["salary_max_vnd"], 0.01, 0.99)

    # N7: log1p sau M5-M6
    df["log_salary_min"] = np.log1p(df["salary_min_vnd_capped"])
    df["log_salary_max"] = np.log1p(df["salary_max_vnd_capped"])

    updated_records = df.to_dict(orient="records")
    stats = {
        "outlier_count": int(df["is_outlier_salary"].sum()),
        "salary_suspect_count": int(bad.sum()),
        "iqr_bounds": {"lower": lower_b, "upper": upper_b},
        "winsorize_q01_min": float(df["salary_min_vnd"].quantile(0.01)) if df["salary_min_vnd"].notna().any() else None,
        "winsorize_q99_min": float(df["salary_min_vnd"].quantile(0.99)) if df["salary_min_vnd"].notna().any() else None,
        "winsorize_q01_max": float(df["salary_max_vnd"].quantile(0.01)) if df["salary_max_vnd"].notna().any() else None,
        "winsorize_q99_max": float(df["salary_max_vnd"].quantile(0.99)) if df["salary_max_vnd"].notna().any() else None,
    }
    return updated_records, stats


def _truthy(v: Any) -> bool:
    return bool(v) and not (isinstance(v, float) and np.isnan(v))


def build_anomalies(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Danh sách mọi cờ ngoại lai/suy luận, mỗi mục có job_id + source để Monitoring/slide mở đúng tin.
    Không chứa nội dung JD (chỉ giá trị trường ngắn)."""
    def item(r: Dict[str, Any], kind: str, field: str, value: Any, detail: str = "") -> Dict[str, Any]:
        if isinstance(value, float):
            value = None if np.isnan(value) else value
        return {"kind": kind, "source": r.get("source_platform"), "job_id": r.get("source_job_id"),
                "job_id_global": r.get("job_id_global"), "url": r.get("source_url"),
                "field": field, "value": value, "detail": detail}

    out: List[Dict[str, Any]] = []
    for r in rows:
        sal = f"{r.get('salary_min_vnd')} - {r.get('salary_max_vnd')} | {r.get('raw_salary_text')}"
        if _truthy(r.get("salary_suspect")):
            out.append(item(r, "salary_suspect", "raw_salary_text", r.get("raw_salary_text"), "ngoài 1-500 triệu, số bị bỏ (NaN)"))
        if _truthy(r.get("salary_out_of_range")):
            out.append(item(r, "salary_out_of_range", "salary_vnd", sal, "ngoài 2-100 triệu/tháng"))
        if _truthy(r.get("salary_iqr_outlier_by_level")):
            out.append(item(r, "salary_iqr_outlier_by_level", "salary_vnd", sal, f"scope={r.get('salary_iqr_scope')}, cấp={r.get('seniority')}"))
        elif _truthy(r.get("is_outlier_salary")):
            out.append(item(r, "salary_iqr_outlier_pooled", "salary_vnd", sal, "IQR gộp (cột is_outlier_salary)"))
        if _truthy(r.get("salary_min_gt_max")):
            out.append(item(r, "salary_min_gt_max", "salary_vnd", sal))
        if _truthy(r.get("salary_negotiable_with_value")):
            out.append(item(r, "salary_negotiable_with_value", "salary_vnd", sal, "vừa thỏa thuận vừa có số"))
        raw_txt = str(r.get("raw_salary_text") or "")
        if r.get("salary_currency_raw") == "VND" and re.search(r"usd|\$", raw_txt, re.I) and _truthy(r.get("salary_min_vnd") or r.get("salary_max_vnd")):
            out.append(item(r, "currency_reinterpreted", "raw_salary_text", raw_txt, "nhãn USD nhưng số quá lớn: đọc là VND"))
        if r.get("salary_period_raw") == "year":
            out.append(item(r, "salary_period_year", "raw_salary_text", raw_txt or None, "lương năm đã chia 12"))
        if _truthy(r.get("level_inferred")):
            out.append(item(r, "level_inferred", "seniority", r.get("seniority"), f"suy từ exp_min_years={r.get('exp_min_years')}"))
        if _truthy(r.get("exp_inferred")):
            out.append(item(r, "exp_inferred", "exp_min_years", r.get("exp_min_years"), r.get("exp_source")))
        if _truthy(r.get("exp_out_of_range")):
            out.append(item(r, "exp_out_of_range", "exp_min_years", r.get("exp_min_years")))
        if r.get("tinh_status") == "unknown":
            out.append(item(r, "tinh_unknown", "raw_location_text", r.get("raw_location_text")))
        if _truthy(r.get("seniority_can_kiem")):
            out.append(item(r, "seniority_can_kiem", "seniority", r.get("seniority")))
        if _truthy(r.get("job_family_can_kiem")):
            out.append(item(r, "job_family_can_kiem", "job_family", r.get("job_family")))
    return out


def write_anomalies(anoms: List[Dict[str, Any]], path: Path = ANOMALIES_FILE) -> Path:
    by_kind: Dict[str, int] = {}
    for a in anoms:
        by_kind[a["kind"]] = by_kind.get(a["kind"], 0) + 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"step": STEP, "total": len(anoms), "by_kind": by_kind, "anomalies": anoms},
                               ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return path


def run(
    sources: Sequence[str] = SOURCES,
    dry_run: bool = True,
) -> Dict[str, StepReport]:
    df_in = pd.read_parquet(IN_FILE) if IN_FILE.exists() else pd.DataFrame(columns=["source_platform"])
    groups = {src: g.to_dict(orient="records") for src, g in df_in.groupby("source_platform")}

    reports: Dict[str, StepReport] = {}
    all_rows: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {}
    title_dict = load_title_dict()
    for src in sources:
        rows, rep = process_source_records(src, groups.get(src, []), dry_run=dry_run, title_dict=title_dict)
        reports[src] = rep
        counts[src] = len(rows)
        all_rows.extend(rows)

    # N18: company_key trên cả bảng gộp
    key_map, pending = compute_company_keys([r.get("company_norm") for r in all_rows])
    for r in all_rows:
        r["company_key"] = key_map.get(r.get("company_norm")) if r.get("company_norm") else None

    # N6, N7, M5, M6 tính trên cả bảng gộp
    all_normalized, salary_stats = apply_global_salary_normalizations(all_rows)
    anomalies = build_anomalies(all_normalized)
    by_kind: Dict[str, int] = {}
    for a in anomalies:
        by_kind[a["kind"]] = by_kind.get(a["kind"], 0) + 1

    idx = 0
    for src in sources:
        src_normalized = all_normalized[idx: idx + counts[src]]
        idx += counts[src]
        rep = reports[src]
        n6_outliers = sum(1 for r in src_normalized if r.get("is_outlier_salary"))
        n6_suspect = sum(1 for r in src_normalized if r.get("salary_suspect"))
        n7_log_count = sum(1 for r in src_normalized if _is_filled(r.get("log_salary_max")) and not pd.isna(r.get("log_salary_max")))
        rep.rule("N6a", "Lương tháng ngoài 1–500 triệu: bỏ số, gắn cờ salary_suspect", "flag", n6_suspect)
        rep.rule("N6", "Gắn cờ ngoại lai lương IQR gộp và Winsorize 1-99% (cột *_capped)", "modify", n6_outliers)
        rep.rule("M5", "Lương ngoài 2-100 triệu/tháng: chỉ cờ salary_out_of_range", "flag", sum(1 for r in src_normalized if r.get("salary_out_of_range")))
        rep.rule("M6", "IQR theo cấp bậc: chỉ cờ salary_iqr_outlier_by_level", "flag", sum(1 for r in src_normalized if r.get("salary_iqr_outlier_by_level")))
        rep.rule("M8", "min > max, kinh nghiệm ngoài khoảng: chỉ cờ", "flag", sum(1 for r in src_normalized if r.get("salary_min_gt_max") or r.get("exp_out_of_range")))
        rep.rule("N7", "Biến đổi log1p cho mức lương", "modify", n7_log_count)
        rep.rule("N18", "company_key (rapidfuzz token_sort >= 90 và tập con)", "modify", sum(1 for r in src_normalized if r.get("company_key")))

        total_rows = len(src_normalized)
        rep.data["fields"] = [
            {"field": f, "fill_pct_in": pct, "fill_pct_out": pct}
            for f in KEY_FIELDS
            for pct in [round(sum(1 for r in src_normalized if _is_filled(r.get(f))) * 100.0 / total_rows, 1) if total_rows else 0.0]
        ]
        vc = lambda col: pd.Series([r.get(col) or "(trống)" for r in src_normalized]).value_counts().to_dict()  # noqa: E731
        rep.data["extra"] = {
            "seniority_distribution": vc("seniority"),
            "job_family_distribution": vc("job_family"),
            "job_family_source_distribution": vc("job_family_source"),
            "work_mode_distribution": vc("work_mode"),
            "salary_status_distribution": vc("salary_status"),
            "salary_outliers": n6_outliers,
            "inference": {"level_inferred": sum(1 for r in src_normalized if r.get("level_inferred")),
                          "exp_inferred": sum(1 for r in src_normalized if r.get("exp_inferred"))},
            "title_taxonomy": {
                "job_title_clean_distinct": len({r.get("job_title_clean") for r in src_normalized}),
                "job_title_core_distinct": len({tfold(r.get("job_title_core")) for r in src_normalized}),
                "title_canonical_source": vc("title_canonical_source"),
            },
            "anomalies_file": ANOMALIES_FILE.relative_to(REPO_ROOT).as_posix(),
            "anomalies_by_kind": {k: sum(1 for a in anomalies if a["kind"] == k and a["source"] == src) for k in by_kind},
        }
        rep.check_conserved()
        rep.write()

    total_rep = merge_reports(STEP, list(reports.values()), dry_run)
    total_rep.set_io(IN_FILE, len(df_in), OUT_FILE, len(all_normalized))
    total_rep.data["extra"].update({"global_salary_stats": salary_stats, "total_jobs": len(all_normalized),
                                    "anomalies_total": len(anomalies), "anomalies_by_kind": by_kind,
                                    "anomalies_file": ANOMALIES_FILE.relative_to(REPO_ROOT).as_posix(),
                                    "company_pairs_pending": len(pending)})
    total_rep.check_conserved()
    if not dry_run and all_normalized:
        OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(all_normalized).to_parquet(OUT_FILE, engine="pyarrow", index=False)
        _write_company_pairs(pending)
    write_anomalies(anomalies)
    total_rep.write()
    return reports


def _write_company_pairs(pending: List[Tuple[str, str, float]]) -> None:
    """N18c: data/preprocessing/review/company_pairs.csv; nhãn decision đã điền tay không bao giờ bị ghi đè."""
    path = DATA_DIR / "preprocessing" / "review" / "company_pairs.csv"
    old: Dict[Tuple[str, str], str] = {}
    if path.exists():
        for line in pd.read_csv(path).fillna("").to_dict("records"):
            old[(line["a"], line["b"])] = line["decision"]
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"a": a, "b": b, "score": sc, "decision": old.get((a, b), "")} for a, b, sc in pending]).to_csv(path, index=False)
