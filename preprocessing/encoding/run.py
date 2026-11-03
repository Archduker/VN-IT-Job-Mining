# -*- coding: utf-8 -*-
"""Bước 05 Encoding (docs/preprocessing/spec/P5_encoding.md).

Mã hóa bộ golden đã chuẩn hóa (04_normalization/all.parquet) thành bảng số học
cho các mô hình Machine Learning:
- E1: Ordinal Seniority (0-5, -1 cho Chưa rõ).
- E2: One-hot job_family, source_platform, employment_type, it_status.
- E3: Multi-hot top 10 tỉnh/thành + tinh__other + is_remote + is_foreign.
- E4: Multi-hot top K kỹ năng (count >= 20, tối đa 200) + skills__other_count.
- E5: Giữ cột số liên tục + thêm cột __missing (0/1).
- E6: Binary flags (is_negotiable, is_outlier_salary).
- E7: Đặc trưng thời gian (posted_month, days_to_deadline).
- E8: Probability scores (it_prob, seniority_prob, job_family_prob) + __missing.
Xuất features.parquet và encoding_dictionary.json.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import numpy as np
import pandas as pd

from preprocessing.common import REPO_ROOT, SOURCES
from preprocessing.common.province import fold
from preprocessing.common.step_report import StepReport, merge_reports
from preprocessing.normalization.text_cleaner import JOB_FAMILIES, SENIORITY_LABELS

STEP = "05_encoding"
DATA_DIR = REPO_ROOT / "data"
IN_FILE = DATA_DIR / "preprocessing" / "04_normalization" / "all.parquet"
OUT_DIR = DATA_DIR / "preprocessing" / STEP
OUT_FEATURES_FILE = OUT_DIR / "features.parquet"
OUT_DICT_FILE = OUT_DIR / "encoding_dictionary.json"

SENIORITY_ORDER = [
    "Thực tập",
    "Mới tốt nghiệp",
    "Junior",
    "Middle",
    "Senior",
    "Trưởng nhóm/Quản lý",
]
SENIORITY_MAP = {lab: idx for idx, lab in enumerate(SENIORITY_ORDER)}
SENIORITY_MAP["Chưa rõ"] = -1

TOP_PROVINCES_K = 10
SKILL_MIN_COUNT = 20
SKILL_MAX_K = 200


def to_col_slug(text: str) -> str:
    """Tạo slug chuẩn cho tên cột (chữ thường, ascii, gạch dưới)."""
    s = str(text or "").lower()
    s = s.replace("c#", "csharp").replace(".net", "dotnet").replace("c++", "cpp")
    s = fold(s)
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "unknown"


def _normalize_employment_type(raw_val: Any) -> str:
    if raw_val is None or (isinstance(raw_val, float) and pd.isna(raw_val)):
        return "missing"
    s = str(raw_val).lower().strip()
    if any(k in s for k in ["toàn thời gian", "full_time", "full time", "nhân viên chính thức"]):
        return "full_time"
    if any(k in s for k in ["bán thời gian", "part_time", "part time"]):
        return "part_time"
    if any(k in s for k in ["thực tập", "intern", "internship"]):
        return "intern"
    return "other"


def encode_dataset(
    df: pd.DataFrame
) -> Tuple[pd.DataFrame, Dict[str, Any], Dict[str, int]]:
    """Thực hiện mã hóa toàn bộ tập dữ liệu thành ma trận số học."""
    total_rows = len(df)
    rules_counts: Dict[str, int] = {}
    dictionary: Dict[str, Any] = {}
    cols: Dict[str, Any] = {}

    cols["job_id_global"] = df["job_id_global"].astype(str).values

    # -------------------------------------------------------------
    # E1: Ordinal Seniority
    # -------------------------------------------------------------
    sen_ord = df["seniority"].map(lambda x: SENIORITY_MAP.get(str(x), -1)).astype(np.int8)
    cols["seniority_ord"] = sen_ord.values
    rules_counts["E1"] = int((sen_ord != -1).sum())
    dictionary["seniority_ord"] = {
        "source_column": "seniority",
        "method": "ordinal",
        "mapping": SENIORITY_MAP,
    }

    # -------------------------------------------------------------
    # E2: One-hot job_family, source_platform, employment_type, it_status
    # -------------------------------------------------------------
    # job_family
    all_fams = JOB_FAMILIES + ["Khác"]
    fam_slug_map = {f: f"job_family__{to_col_slug(f)}" for f in all_fams}
    for fam, col_name in fam_slug_map.items():
        cols[col_name] = (df["job_family"] == fam).astype(np.uint8).values
    dictionary["job_family"] = {
        "source_column": "job_family",
        "method": "one-hot",
        "columns": fam_slug_map,
    }

    # source_platform
    sources_slug_map = {src: f"source_platform__{src}" for src in SOURCES}
    for src, col_name in sources_slug_map.items():
        cols[col_name] = (df["source_platform"] == src).astype(np.uint8).values
    dictionary["source_platform"] = {
        "source_column": "source_platform",
        "method": "one-hot",
        "columns": sources_slug_map,
    }

    # employment_type
    emp_norm_series = df["raw_employment_type"].apply(_normalize_employment_type)
    for emp_cat in ["full_time", "part_time", "intern", "other"]:
        cols[f"employment_type__{emp_cat}"] = (emp_norm_series == emp_cat).astype(np.uint8).values
    cols["employment_type__missing"] = (emp_norm_series == "missing").astype(np.uint8).values
    dictionary["employment_type"] = {
        "source_column": "raw_employment_type",
        "method": "one-hot",
        "categories": ["full_time", "part_time", "intern", "other"],
        "missing_indicator": "employment_type__missing",
    }

    # it_status
    for st in ["it", "non_it", "can_kiem"]:
        cols[f"it_status__{st}"] = (df["it_status"] == st).astype(np.uint8).values
    dictionary["it_status"] = {
        "source_column": "it_status",
        "method": "one-hot",
        "categories": ["it", "non_it", "can_kiem"],
    }

    rules_counts["E2"] = total_rows

    # -------------------------------------------------------------
    # E3: Top 10 tỉnh/thành + tinh__other + is_remote + is_foreign
    # -------------------------------------------------------------
    prov_counter = Counter()
    for locs in df["locations"]:
        if hasattr(locs, "__iter__"):
            for l in locs:
                if isinstance(l, dict) and l.get("tinh_key"):
                    prov_counter[l["tinh_key"]] += 1

    top_provinces = [k for k, _ in prov_counter.most_common(TOP_PROVINCES_K)]
    top_prov_set = set(top_provinces)

    e3_affected = 0
    tinh_cols_data = {pk: np.zeros(total_rows, dtype=np.uint8) for pk in top_provinces}
    tinh_other_data = np.zeros(total_rows, dtype=np.uint8)
    remote_data = np.zeros(total_rows, dtype=np.uint8)
    foreign_data = np.zeros(total_rows, dtype=np.uint8)

    for i, locs in enumerate(df["locations"]):
        row_has_loc = False
        if hasattr(locs, "__iter__"):
            for l in locs:
                if not isinstance(l, dict):
                    continue
                row_has_loc = True
                pk = l.get("tinh_key")
                if pk in top_prov_set:
                    tinh_cols_data[pk][i] = 1
                elif pk is not None:
                    tinh_other_data[i] = 1

                if l.get("remote"):
                    remote_data[i] = 1
                if l.get("ngoai_vn"):
                    foreign_data[i] = 1
        if row_has_loc:
            e3_affected += 1

    for pk in top_provinces:
        cols[f"tinh__{pk}"] = tinh_cols_data[pk]
    cols["tinh__other"] = tinh_other_data
    cols["is_remote"] = remote_data
    cols["is_foreign"] = foreign_data

    rules_counts["E3"] = e3_affected
    dictionary["provinces"] = {
        "source_column": "locations[].tinh_key",
        "method": "multi-hot",
        "top_k": TOP_PROVINCES_K,
        "top_provinces": top_provinces,
        "other_column": "tinh__other",
        "flags": ["is_remote", "is_foreign"],
    }

    # -------------------------------------------------------------
    # E4: Top K kỹ năng (count >= 20, max 200) + skills__other_count
    # -------------------------------------------------------------
    slug_counter = Counter()
    slug_to_canonical: Dict[str, str] = {}

    for sl in df["skills_std"]:
        if hasattr(sl, "__iter__"):
            seen_row_slugs = set()
            for s in sl:
                if not s:
                    continue
                slug = to_col_slug(s)
                if not slug or slug in seen_row_slugs:
                    continue
                seen_row_slugs.add(slug)
                slug_counter[slug] += 1
                if slug not in slug_to_canonical or len(str(s)) > len(slug_to_canonical[slug]):
                    slug_to_canonical[slug] = str(s).strip()

    top_skill_slugs = [slug for slug, count in slug_counter.most_common(SKILL_MAX_K) if count >= SKILL_MIN_COUNT]
    top_skill_set = set(top_skill_slugs)

    skill_matrix = {slug: np.zeros(total_rows, dtype=np.uint8) for slug in top_skill_slugs}
    other_skill_counts = np.zeros(total_rows, dtype=np.int32)
    e4_affected = 0

    for i, sl in enumerate(df["skills_std"]):
        if hasattr(sl, "__iter__"):
            seen_in_row = set()
            row_hits = 0
            for s in sl:
                if not s:
                    continue
                slug = to_col_slug(s)
                if not slug or slug in seen_in_row:
                    continue
                seen_in_row.add(slug)
                if slug in top_skill_set:
                    skill_matrix[slug][i] = 1
                    row_hits += 1
                else:
                    other_skill_counts[i] += 1
            if row_hits > 0 or other_skill_counts[i] > 0:
                e4_affected += 1

    for slug in top_skill_slugs:
        cols[f"skill__{slug}"] = skill_matrix[slug]
    cols["skills__other_count"] = other_skill_counts

    rules_counts["E4"] = e4_affected
    dictionary["skills"] = {
        "source_column": "skills_std",
        "method": "multi-hot",
        "threshold_min_count": SKILL_MIN_COUNT,
        "max_k": SKILL_MAX_K,
        "total_encoded": len(top_skill_slugs),
        "skills_map": {slug: slug_to_canonical[slug] for slug in top_skill_slugs},
        "other_count_column": "skills__other_count",
    }

    # -------------------------------------------------------------
    # E5: Cột số liên tục + missing indicators
    # -------------------------------------------------------------
    numeric_cols = [
        "log_salary_min", "log_salary_max",
        "exp_min_years", "exp_max_years",
        "headcount"
    ]
    e5_affected = 0
    for col in numeric_cols:
        s_vals = pd.to_numeric(df[col], errors="coerce")
        cols[col] = s_vals.astype(np.float32).values
        cols[f"{col}__missing"] = s_vals.isna().astype(np.uint8).values
        e5_affected += int(s_vals.notna().sum())

    rules_counts["E5"] = e5_affected
    dictionary["continuous_features"] = {
        "columns": numeric_cols,
        "missing_suffix": "__missing",
    }

    # -------------------------------------------------------------
    # E6: Binary flags (is_negotiable, is_outlier_salary)
    # -------------------------------------------------------------
    cols["is_negotiable"] = df["is_negotiable"].fillna(False).astype(bool).astype(np.uint8).values
    cols["is_outlier_salary"] = df["is_outlier_salary"].fillna(False).astype(bool).astype(np.uint8).values
    rules_counts["E6"] = int((cols["is_negotiable"] == 1).sum() + (cols["is_outlier_salary"] == 1).sum())
    dictionary["binary_flags"] = ["is_negotiable", "is_outlier_salary"]

    # -------------------------------------------------------------
    # E7: Đặc trưng thời gian (posted_month, days_to_deadline)
    # -------------------------------------------------------------
    posted_dt = pd.to_datetime(df["posted_date"], errors="coerce")
    deadline_dt = pd.to_datetime(df["deadline_date"], errors="coerce")

    posted_month = posted_dt.dt.month
    cols["posted_month"] = posted_month.astype(np.float32).values
    cols["posted_month__missing"] = posted_month.isna().astype(np.uint8).values

    diff_days = (deadline_dt - posted_dt).dt.days
    diff_days_valid = diff_days.where(diff_days >= 0, np.nan)
    cols["days_to_deadline"] = diff_days_valid.astype(np.float32).values
    cols["days_to_deadline__missing"] = diff_days_valid.isna().astype(np.uint8).values

    rules_counts["E7"] = int(posted_month.notna().sum() + diff_days_valid.notna().sum())
    dictionary["temporal_features"] = {
        "columns": ["posted_month", "days_to_deadline"],
        "missing_suffix": "__missing",
    }

    # -------------------------------------------------------------
    # E8: Probability scores (it_prob, seniority_prob, job_family_prob)
    # -------------------------------------------------------------
    prob_cols = ["it_prob", "seniority_prob", "job_family_prob"]
    e8_affected = 0
    for pcol in prob_cols:
        val_series = pd.to_numeric(df[pcol], errors="coerce") if pcol in df.columns else pd.Series(np.nan, index=df.index)
        cols[pcol] = val_series.astype(np.float32).values
        cols[f"{pcol}__missing"] = val_series.isna().astype(np.uint8).values
        e8_affected += int(val_series.notna().sum())

    rules_counts["E8"] = e8_affected
    dictionary["probability_features"] = {
        "columns": prob_cols,
        "missing_suffix": "__missing",
    }

    res_df = pd.DataFrame(cols)
    return res_df, dictionary, rules_counts


def run(
    sources: Sequence[str] = SOURCES,
    dry_run: bool = True,
    use_api: bool = False
) -> Dict[str, StepReport]:
    report = StepReport(STEP, "_all", dry_run)

    if not IN_FILE.exists():
        report.set_io(IN_FILE, 0, OUT_FEATURES_FILE, 0)
        report.note(f"Không tìm thấy file đầu vào {IN_FILE}")
        report.check_conserved()
        report.write()
        return {"_all": report}

    df_in = pd.read_parquet(IN_FILE)
    total_rows = len(df_in)
    report.set_io(IN_FILE, total_rows, OUT_FEATURES_FILE, total_rows)

    # Lọc nguồn nếu người dùng chỉ định một phần
    selected_sources = set(sources)
    if selected_sources != set(SOURCES) and len(selected_sources) < len(SOURCES):
        df_target = df_in[df_in["source_platform"].isin(selected_sources)].copy()
    else:
        df_target = df_in

    # Tiến hành mã hóa
    features_df, dictionary, rules_counts = encode_dataset(df_target)

    # Đăng ký rules vào báo cáo
    report.rule("E1", "Mã hóa Ordinal cho Seniority (0-5, -1 cho Chưa rõ)", "modify", rules_counts.get("E1", 0))
    report.rule("E2", "Mã hóa One-hot cho Job Family, Nền tảng, Hình thức, IT status", "modify", rules_counts.get("E2", 0))
    report.rule("E3", "Mã hóa Multi-hot cho Top 10 tỉnh/thành, Remote, Ngoại quốc", "modify", rules_counts.get("E3", 0))
    report.rule("E4", "Mã hóa Multi-hot cho Top K kỹ năng phổ biến", "modify", rules_counts.get("E4", 0))
    report.rule("E5", "Bảo toàn số học và gắn cờ khuyết thiếu missing", "modify", rules_counts.get("E5", 0))
    report.rule("E6", "Mã hóa nhị phân cờ lương và IT status", "modify", rules_counts.get("E6", 0))
    report.rule("E7", "Bóc tách đặc trưng thời gian (tháng đăng, ngày tới hạn)", "modify", rules_counts.get("E7", 0))
    report.rule("E8", "Bảo toàn điểm xác suất JEV và gắn cờ khuyết thiếu", "modify", rules_counts.get("E8", 0))

    # Đo độ thưa của kỹ năng
    skill_cols = [c for c in features_df.columns if c.startswith("skill__")]
    if skill_cols:
        skill_vals = features_df[skill_cols].to_numpy()
        sparsity = float((skill_vals == 0).sum() / skill_vals.size)
    else:
        sparsity = 1.0

    report.data["extra"] = {
        "total_columns": features_df.shape[1],
        "feature_types": {
            "id_columns": ["job_id_global"],
            "ordinal_columns": ["seniority_ord"],
            "one_hot_columns": [c for c in features_df.columns if "__" in c and any(c.startswith(p) for p in ["job_family__", "source_platform__", "employment_type__", "it_status__"]) and not c.endswith("__missing")],
            "multi_hot_columns": [c for c in features_df.columns if c.startswith("tinh__") or c.startswith("skill__") or c in ["is_remote", "is_foreign"]],
            "continuous_numeric_columns": [c for c in features_df.columns if not c.endswith("__missing") and c in ["log_salary_min", "log_salary_max", "exp_min_years", "exp_max_years", "headcount", "posted_month", "days_to_deadline", "it_prob", "seniority_prob", "job_family_prob"]],
            "missing_indicator_columns": [c for c in features_df.columns if c.endswith("__missing")],
        },
        "skills_sparsity": round(sparsity * 100, 2),
        "encoded_skills_count": len(skill_cols),
    }

    report.check_conserved()

    if not dry_run:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        features_df.to_parquet(OUT_FEATURES_FILE, engine="pyarrow", index=False)
        OUT_DICT_FILE.write_text(json.dumps(dictionary, ensure_ascii=False, indent=2), encoding="utf-8")

    report.write()
    return {"_all": report}
