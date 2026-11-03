# -*- coding: utf-8 -*-
"""Bước 04 Normalization (docs/preprocessing/spec/P4_normalization.md).

Chuẩn hóa 34 tỉnh/thành sau sáp nhập, 6 cấp bậc tiếng Việt, 12 nhóm nghề IT (khớp từ nguyên vẹn + JEV),
ánh xạ kỹ năng chuẩn, chuẩn hóa tên công ty, xử lý ngoại lai lương (IQR + Winsorize 1-99%),
log1p lương. Đọc và ghi một file all.parquet (đã gộp 8 nguồn từ bước Integration).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from preprocessing.common import REPO_ROOT, SOURCES
from preprocessing.common.jev_client import JevClient
from preprocessing.common.province import fold, is_foreign, is_remote, key as prov_key, name as prov_name
from preprocessing.common.step_report import StepReport, merge_reports
from preprocessing.missing_outlier.outlier_handler import (
    detect_iqr_outliers,
    fix_common_salary_input_errors,
    winsorize_series,
)
from preprocessing.normalization.cross_deduplicator import normalize_company_name
from preprocessing.transformation.salary_parser import MONTHLY_MAX_VND, MONTHLY_MIN_VND
from preprocessing.normalization.text_cleaner import (
    canonicalize_skills,
    classify_job_family_rule,
    classify_seniority,
)

STEP = "04_normalization"
DATA_DIR = REPO_ROOT / "data"
IN_FILE = DATA_DIR / "preprocessing" / "03_transformation" / "all.parquet"
OUT_FILE = DATA_DIR / "preprocessing" / STEP / "all.parquet"

KEY_FIELDS = (
    "locations", "tinh_chinh", "seniority", "seniority_source",
    "job_family", "job_family_source", "skills_std", "company_norm",
    "salary_min_vnd_capped", "salary_max_vnd_capped",
    "log_salary_min", "log_salary_max", "is_outlier_salary"
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


def _jev_question(name: str, what: str, label: str) -> Tuple[str, str, str, str]:
    return (f"{name}_dung", f"Tin tuyển dụng này có {what} là '{label}' không?",
            f"{what} của tin đúng là '{label}'", f"{what} của tin không phải '{label}'")


def _jev_state(rec: Dict[str, Any]) -> Dict[str, Any]:
    jd = rec.get("description_clean")
    return {"title": rec.get("job_title_clean"), "jd": jd[:500] if isinstance(jd, str) else ""}


def _jev_verify(jev: JevClient, name: str, what: str, label: str, rec: Dict[str, Any]) -> Optional[float]:
    """Hỏi JEV có/không: nhãn luật đưa ra có đúng không. Không gọi được thì None."""
    return jev.noul(*_jev_question(name, what, label), _jev_state(rec))


def _prefetch_labels(jev: JevClient, records: List[Dict[str, Any]]) -> None:
    """Chạy luật trước để biết nhãn, rồi gọi JEV song song theo từng nhãn (vòng chính lấy kết quả đã nhớ)."""
    groups: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
    for rec in records:
        sen, _ = classify_seniority(rec.get("raw_seniority_text"), rec.get("job_title_clean"), rec.get("exp_min_years"))
        fam, _ = classify_job_family_rule(rec.get("job_title_clean"), canonicalize_skills(rec.get("skills_clean")))
        if sen:
            groups.setdefault(("seniority", "cấp bậc", sen), []).append(_jev_state(rec))
        if fam:
            groups.setdefault(("job_family", "nhóm nghề", fam), []).append(_jev_state(rec))
    for (name, what, label), states in groups.items():
        jev.prefetch(*_jev_question(name, what, label), states)


def _low(prob: Optional[float]) -> bool:
    return prob is not None and prob < 0.5


def process_source_records(
    source: str,
    input_records: List[Dict[str, Any]],
    jev: JevClient,
    dry_run: bool = True
) -> Tuple[List[Dict[str, Any]], StepReport]:
    report = StepReport(STEP, source, dry_run)
    total_rows = len(input_records)
    report.set_io(IN_FILE, total_rows, OUT_FILE, total_rows)

    rows: List[Dict[str, Any]] = []
    _prefetch_labels(jev, input_records)

    n1_count, n2_count, n3_count, n4_count, n5_count, n_can_kiem = 0, 0, 0, 0, 0, 0
    n1_examples, n2_examples, n3_examples = [], [], []

    for row in input_records:
        rec = dict(row)
        job_id = rec.get("source_job_id") or rec.get("job_id_global") or ""
        url = rec.get("source_url") or ""

        # N1: Địa điểm 34 tỉnh/thành
        locs, primary_city = _normalize_locations(rec.get("locations"))
        rec["locations"] = locs
        rec["tinh_chinh"] = primary_city
        if primary_city or any(l.get("remote") or l.get("ngoai_vn") for l in locs):
            n1_count += 1
            if len(n1_examples) < 3 and primary_city:
                n1_examples.append({
                    "job_id": job_id,
                    "field": "tinh_chinh",
                    "before": str(rec.get("raw_location_text")),
                    "after": primary_city,
                    "url": url,
                })

        # N4: Ánh xạ kỹ năng chuẩn theo skills.json
        skills_std = canonicalize_skills(rec.get("skills_clean"))
        rec["skills_std"] = skills_std
        if skills_std:
            n4_count += 1

        # N2: Cấp bậc: raw -> tiêu đề -> kinh nghiệm; không có thì để trống
        sen, sen_src = classify_seniority(
            rec.get("raw_seniority_text"),
            rec.get("job_title_clean"),
            rec.get("exp_min_years")
        )
        rec["seniority"] = sen
        rec["seniority_source"] = sen_src
        rec["seniority_prob"] = _jev_verify(jev, "seniority", "cấp bậc", sen, rec) if sen else None
        rec["seniority_can_kiem"] = _low(rec["seniority_prob"])
        if sen:
            n2_count += 1
            if len(n2_examples) < 3:
                n2_examples.append({
                    "job_id": job_id,
                    "field": "seniority",
                    "before": str(rec.get("raw_seniority_text") or rec.get("job_title_clean")),
                    "after": f"{sen} ({sen_src})",
                    "url": url,
                })

        # N3: Nhóm nghề theo tiêu đề -> skills_std; không có thì "Khác"
        fam, fam_src = classify_job_family_rule(rec.get("job_title_clean"), skills_std)
        fam = fam or "Khác"
        rec["job_family"] = fam
        rec["job_family_source"] = fam_src or "none"
        rec["job_family_prob"] = _jev_verify(jev, "job_family", "nhóm nghề", fam, rec) if fam != "Khác" else None
        rec["job_family_can_kiem"] = _low(rec["job_family_prob"])
        if fam != "Khác":
            n3_count += 1
            if len(n3_examples) < 3:
                n3_examples.append({
                    "job_id": job_id,
                    "field": "job_family",
                    "before": str(rec.get("job_title_clean")),
                    "after": f"{fam} ({fam_src})",
                    "url": url,
                })
        n_can_kiem += bool(rec["seniority_can_kiem"] or rec["job_family_can_kiem"])

        # N5: Chuẩn hóa tên công ty
        c_norm = normalize_company_name(rec.get("company_name"))
        rec["company_norm"] = c_norm
        if c_norm:
            n5_count += 1

        rows.append(rec)

    # Đăng ký rules cơ bản
    report.rule("N1", "Chuẩn hóa địa phương 34 tỉnh/thành sau sáp nhập", "modify", n1_count, n1_examples)
    report.rule("N2", "Chuẩn hóa cấp bậc nghề nghiệp 6 bậc", "modify", n2_count, n2_examples)
    report.rule("N3", "Phân loại 12 nhóm nghề IT", "modify", n3_count, n3_examples)
    report.rule("N4", "Ánh xạ kỹ năng chuẩn theo từ điển", "modify", n4_count)
    report.rule("N5", "Chuẩn hóa tên công ty", "modify", n5_count)
    report.rule("N2b", "JEV không đồng ý nhãn cấp bậc/nhóm nghề: gắn cờ cần kiểm", "flag", n_can_kiem)

    report.check_conserved()
    return rows, report


def apply_global_salary_normalizations(
    all_rows: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """N6 & N7: Sửa lỗi nhập liệu, gắn cờ ngoại lai IQR, Winsorize 1-99% và tính log1p."""
    if not all_rows:
        return [], {}

    df = pd.DataFrame(all_rows)

    # 1. Sửa lỗi nhập liệu số phổ biến
    def _fix_sal(val: Any, jd: str) -> Optional[float]:
        if val is None or pd.isna(val):
            return None
        return fix_common_salary_input_errors(float(val), jd)

    jd_col = df["description_clean"].fillna("").astype(str)
    df["salary_min_vnd"] = [_fix_sal(v, jd) for v, jd in zip(df["salary_min_vnd"], jd_col)]
    df["salary_max_vnd"] = [_fix_sal(v, jd) for v, jd in zip(df["salary_max_vnd"], jd_col)]

    # Ngưỡng cứng lương tháng: ngoài 1–500 triệu là đọc sai, bỏ số trước khi tính IQR
    bad = pd.Series(False, index=df.index)
    for c in ("salary_min_vnd", "salary_max_vnd"):
        v = pd.to_numeric(df[c], errors="coerce")
        bad |= (v < MONTHLY_MIN_VND) | (v > MONTHLY_MAX_VND)
    prev = df["salary_suspect"].fillna(False).astype(bool) if "salary_suspect" in df else False
    df["salary_suspect"] = bad | prev
    df.loc[bad, ["salary_min_vnd", "salary_max_vnd"]] = np.nan

    # 2. Gắn cờ ngoại lai bằng IQR trên mức lương tối đa (hoặc tối thiểu nếu chỉ có min)
    sal_eval = df["salary_max_vnd"].combine_first(df["salary_min_vnd"])
    iqr_res = detect_iqr_outliers(sal_eval)
    lower_b = iqr_res.get("lower_bound")
    upper_b = iqr_res.get("upper_bound")

    if lower_b is not None and upper_b is not None:
        is_outlier = (sal_eval < lower_b) | (sal_eval > upper_b)
    else:
        is_outlier = pd.Series(False, index=df.index)

    df["is_outlier_salary"] = is_outlier.fillna(False)

    # 3. Winsorize 1% - 99% cho salary_min và salary_max
    df["salary_min_vnd_capped"] = winsorize_series(df["salary_min_vnd"], 0.01, 0.99)
    df["salary_max_vnd_capped"] = winsorize_series(df["salary_max_vnd"], 0.01, 0.99)

    # 4. N7: log1p mức lương sau khi capped
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


def run(
    sources: Sequence[str] = SOURCES,
    dry_run: bool = True,
    use_api: bool = False,
) -> Dict[str, StepReport]:
    jev = JevClient(use_api=use_api, dry_run=dry_run)
    df_in = pd.read_parquet(IN_FILE) if IN_FILE.exists() else pd.DataFrame(columns=["source_platform"])
    groups = {src: g.to_dict(orient="records") for src, g in df_in.groupby("source_platform")}

    reports: Dict[str, StepReport] = {}
    all_rows: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {}
    for src in sources:
        rows, rep = process_source_records(src, groups.get(src, []), jev, dry_run=dry_run)
        reports[src] = rep
        counts[src] = len(rows)
        all_rows.extend(rows)

    # N6, N7 tính trên cả bảng gộp
    all_normalized, salary_stats = apply_global_salary_normalizations(all_rows)

    idx = 0
    for src in sources:
        src_normalized = all_normalized[idx: idx + counts[src]]
        idx += counts[src]
        rep = reports[src]
        n6_outliers = sum(1 for r in src_normalized if r.get("is_outlier_salary"))
        n6_suspect = sum(1 for r in src_normalized if r.get("salary_suspect"))
        n7_log_count = sum(1 for r in src_normalized if _is_filled(r.get("log_salary_max")) and not pd.isna(r.get("log_salary_max")))
        rep.rule("N6a", "Lương tháng ngoài 1–500 triệu: bỏ số, gắn cờ salary_suspect", "flag", n6_suspect)
        rep.rule("N6", "Gắn cờ ngoại lai lương IQR và Winsorize 1-99%", "modify", n6_outliers)
        rep.rule("N7", "Biến đổi log1p cho mức lương", "modify", n7_log_count)

        total_rows = len(src_normalized)
        rep.data["fields"] = [
            {"field": f, "fill_pct_in": pct, "fill_pct_out": pct}
            for f in KEY_FIELDS
            for pct in [round(sum(1 for r in src_normalized if _is_filled(r.get(f))) * 100.0 / total_rows, 1) if total_rows else 0.0]
        ]
        rep.data["api"] = jev.report()
        rep.data["extra"] = {
            "seniority_distribution": pd.Series([r.get("seniority") or "(trống)" for r in src_normalized]).value_counts().to_dict(),
            "job_family_distribution": pd.Series([r.get("job_family") for r in src_normalized]).value_counts().to_dict(),
            "salary_outliers": n6_outliers,
        }
        rep.check_conserved()
        rep.write()

    total_rep = merge_reports(STEP, list(reports.values()), dry_run)
    total_rep.set_io(IN_FILE, len(df_in), OUT_FILE, len(all_normalized))
    total_rep.data["api"] = jev.report()
    total_rep.data["extra"].update({"global_salary_stats": salary_stats, "total_jobs": len(all_normalized)})
    total_rep.check_conserved()
    if not dry_run and all_normalized:
        OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(all_normalized).to_parquet(OUT_FILE, engine="pyarrow", index=False)
    total_rep.write()
    return reports
