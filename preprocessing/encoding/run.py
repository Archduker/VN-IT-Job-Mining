"""Bước 05 Encoding (docs/preprocessing/spec/P5_encoding.md, SPEC-06, SPEC-07).

Nhiệm vụ của Phát: Mã hóa bộ dữ liệu đã chuẩn hóa thành bảng số học cho Machine Learning:
- E1: Ordinal Seniority (0-5, -1 cho Chưa rõ).
- E2: One-hot job_family, source_platform, employment_type.
- E3: Multi-hot top 10 tỉnh/thành + tinh__other + is_remote + is_foreign.
- E4: Multi-hot đúng 230 cột kỹ năng chuẩn (tiền tố skill_<slug>, uint8) + other_skills_count.
- E5: Giữ cột số liên tục + thêm cột __missing (0/1).
- E6: Binary flags (is_negotiable, is_outlier_salary).
- E7: Đặc trưng thời gian (posted_month, days_to_deadline).
- E8: Cờ của luật if-else (it_rule_level__2, seniority_can_kiem, job_family_can_kiem), 0/1.

Đồng thời tính toán ma trận đồng xuất hiện kỹ năng (Skill Co-occurrence Matrix) C = X^T @ X (230x230).
Các output của runner hiện tại:
- features.parquet (bảng đặc trưng số học)
- skill_cooccurrence.parquet (ma trận vuông 230x230)
- encoding_dictionary.json (từ điển tra cứu ánh xạ)
Các pure helpers giữ API prototype cho callers/tests cũ. Hàm run chỉ delegate
về execute.py khi đủ explicit config; execute.py xuất full bundle theo frozen
assets, gồm TF-IDF qua execution_tfidf.py. Prototype không phải publish path.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd

from preprocessing.common import REPO_ROOT, SOURCES
from preprocessing.common.province import fold
from preprocessing.encoding.skills_taxonomy_230 import (
    EXACT_SKILL_COUNT,
    ORDERED_SKILL_COLUMNS,
    SKILL_LOOKUP_MAP,
    TAXONOMY_230,
)
from preprocessing.normalization.text_cleaner import JOB_FAMILIES

STEP = "05_encoding"
DATA_DIR = REPO_ROOT / "data"
IN_FILE = DATA_DIR / "preprocessing" / "04_normalization" / "all.parquet"
OUT_DIR = DATA_DIR / "preprocessing" / STEP
OUT_FEATURES_FILE = OUT_DIR / "features.parquet"
OUT_COOCCURRENCE_FILE = OUT_DIR / "skill_cooccurrence.parquet"
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


def compute_skill_cooccurrence(skill_matrix_df: pd.DataFrame) -> pd.DataFrame:
    """Tính toán ma trận vuông đồng xuất hiện kỹ năng: C = X^T @ X.

    Kích thước: đúng 230 x 230.
    Tính chất:
    - Đối xứng: C = C^T
    - Đường chéo C[i, i] == sum(X[:, i])
    - Tên cột và tên hàng khớp chính xác danh mục 230 kỹ năng chuẩn.
    """
    col_names = list(skill_matrix_df.columns)
    if col_names != ORDERED_SKILL_COLUMNS or len(set(col_names)) != EXACT_SKILL_COUNT:
        raise ValueError(
            f"Skill matrix must have exactly {EXACT_SKILL_COUNT} columns, got {len(col_names)}"
        )

    if not skill_matrix_df.isin([0, 1]).all().all():
        raise ValueError("Skill matrix must contain only binary values")
    X = skill_matrix_df.to_numpy(dtype=np.int64)
    C_mat = X.T @ X

    # Kiểm tra tính chất toán học
    if not np.array_equal(C_mat, C_mat.T):
        raise ValueError("Co-occurrence matrix must be symmetric C == C^T")
    if not np.array_equal(np.diag(C_mat), X.sum(axis=0)):
        raise ValueError("Co-occurrence diagonal must equal individual skill frequencies")

    return pd.DataFrame(C_mat, index=col_names, columns=col_names)


def encode_dataset(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any], dict[str, int]]:
    """Thực hiện mã hóa toàn bộ tập dữ liệu thành ma trận số học."""
    total_rows = len(df)
    rules_counts: dict[str, int] = {}
    for field, element_type in [("skills_std", str), ("locations", dict)]:
        for value in df[field]:
            if value is None or (isinstance(value, float) and np.isnan(value)):
                continue
            if not isinstance(value, (list, tuple, np.ndarray)) or any(
                not isinstance(v, element_type) for v in value
            ):
                raise ValueError(f"Malformed array in {field}")
    if len(ORDERED_SKILL_COLUMNS) != 230 or len(set(ORDERED_SKILL_COLUMNS)) != 230:
        raise ValueError("Vocabulary column collision or incorrect width")
    dictionary: dict[str, Any] = {}
    cols: dict[str, Any] = {}

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
    # E2: One-hot job_family, source_platform, employment_type
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

    rules_counts["E2"] = total_rows

    # -------------------------------------------------------------
    # E3: Top 10 tỉnh/thành + tinh__other + is_remote + is_foreign
    # -------------------------------------------------------------
    prov_counter = Counter()
    for locs in df["locations"]:
        if hasattr(locs, "__iter__"):
            for location in locs:
                if isinstance(location, dict) and location.get("tinh_key"):
                    prov_counter[location["tinh_key"]] += 1

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
            for location in locs:
                if not isinstance(location, dict):
                    continue
                row_has_loc = True
                pk = location.get("tinh_key")
                if pk in top_prov_set:
                    tinh_cols_data[pk][i] = 1
                elif pk is not None:
                    tinh_other_data[i] = 1

                if location.get("remote"):
                    remote_data[i] = 1
                if location.get("ngoai_vn"):
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
    # E4: Multi-hot ĐÚNG 230 CỘT KỸ NĂNG CHUẨN (skill_<slug>) + other_skills_count
    # -------------------------------------------------------------
    # Khởi tạo ma trận nhị phân 230 cột kỹ năng với kiểu np.uint8
    skill_cols_data = {
        col_name: np.zeros(total_rows, dtype=np.uint8) for col_name in ORDERED_SKILL_COLUMNS
    }
    other_skills_count = np.zeros(total_rows, dtype=np.int32)
    e4_affected = 0

    for i, sl in enumerate(df["skills_std"]):
        row_matched_skills = 0
        if hasattr(sl, "__iter__"):
            seen_in_row: set[str] = set()
            for s in sl:
                if not s:
                    continue
                s_str = str(s).strip()
                s_lower = s_str.lower()
                s_slug = to_col_slug(s_str)

                # Tìm kiếm trong lookup map 230 kỹ năng
                matched_slug = (
                    SKILL_LOOKUP_MAP.get(s_lower)
                    or SKILL_LOOKUP_MAP.get(s_slug)
                    or SKILL_LOOKUP_MAP.get(s_str)
                )

                if matched_slug:
                    target_col = f"skill_{matched_slug}"
                    if target_col in skill_cols_data and target_col not in seen_in_row:
                        seen_in_row.add(target_col)
                        skill_cols_data[target_col][i] = 1
                        row_matched_skills += 1
                else:
                    if s_slug not in seen_in_row:
                        seen_in_row.add(s_slug)
                        other_skills_count[i] += 1

        if row_matched_skills > 0 or other_skills_count[i] > 0:
            e4_affected += 1

    # Nạp 230 cột kỹ năng theo đúng thứ tự cố định vào cols
    for col_name in ORDERED_SKILL_COLUMNS:
        cols[col_name] = skill_cols_data[col_name]

    # Cột đếm kỹ năng ngoài top đặt tên là other_skills_count (không bắt đầu bằng skill_ để tránh FP-Growth dính nhầm)
    cols["other_skills_count"] = other_skills_count

    rules_counts["E4"] = e4_affected
    dictionary["skills"] = {
        "source_column": "skills_std",
        "method": "multi-hot",
        "total_encoded": EXACT_SKILL_COUNT,
        "column_prefix": "skill_",
        "ordered_columns": ORDERED_SKILL_COLUMNS,
        "taxonomy": [
            {
                "index": entry.index,
                "canonical": entry.canonical,
                "slug": entry.slug,
                "column_name": entry.column_name,
                "group": entry.group,
            }
            for entry in TAXONOMY_230
        ],
        "other_count_column": "other_skills_count",
    }

    # -------------------------------------------------------------
    # E5: Cột số liên tục + missing indicators
    # -------------------------------------------------------------
    numeric_cols = [
        "log_salary_min",
        "log_salary_max",
        "exp_min_years",
        "exp_max_years",
        "headcount",
    ]
    e5_affected = 0
    for col in numeric_cols:
        s_vals = (
            pd.to_numeric(df[col], errors="coerce")
            if col in df.columns
            else pd.Series(np.nan, index=df.index)
        )
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
    is_neg = (
        df["is_negotiable"].fillna(False).astype(bool).astype(np.uint8).values
        if "is_negotiable" in df.columns
        else np.zeros(total_rows, dtype=np.uint8)
    )
    is_out = (
        df["is_outlier_salary"].fillna(False).astype(bool).astype(np.uint8).values
        if "is_outlier_salary" in df.columns
        else np.zeros(total_rows, dtype=np.uint8)
    )
    cols["is_negotiable"] = is_neg
    cols["is_outlier_salary"] = is_out
    rules_counts["E6"] = int(
        (cols["is_negotiable"] == 1).sum() + (cols["is_outlier_salary"] == 1).sum()
    )
    dictionary["binary_flags"] = ["is_negotiable", "is_outlier_salary"]

    # -------------------------------------------------------------
    # E7: Đặc trưng thời gian (posted_month, days_to_deadline)
    # -------------------------------------------------------------
    posted_dt = (
        pd.to_datetime(df["posted_date"], errors="coerce")
        if "posted_date" in df.columns
        else pd.Series(pd.NaT, index=df.index)
    )
    deadline_dt = (
        pd.to_datetime(df["deadline_date"], errors="coerce")
        if "deadline_date" in df.columns
        else pd.Series(pd.NaT, index=df.index)
    )

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
    # E8: Cờ của luật if-else
    # -------------------------------------------------------------
    flag_src = {
        "it_rule_level__2": (pd.to_numeric(df["it_rule_level"], errors="coerce") == 2)
        if "it_rule_level" in df.columns
        else pd.Series(False, index=df.index),
        "seniority_can_kiem": df["seniority_can_kiem"]
        if "seniority_can_kiem" in df.columns
        else pd.Series(False, index=df.index),
        "job_family_can_kiem": df["job_family_can_kiem"]
        if "job_family_can_kiem" in df.columns
        else pd.Series(False, index=df.index),
    }
    for col, ser in flag_src.items():
        cols[col] = ser.fillna(False).astype(bool).astype(np.uint8).values
    rules_counts["E8"] = int(sum(cols[c].sum() for c in flag_src))
    dictionary["rule_flags"] = list(flag_src)

    res_df = pd.DataFrame(cols)
    return res_df, dictionary, rules_counts


def run(
    sources: Sequence[str] = SOURCES,
    dry_run: bool = True,
    *,
    input_manifest=None,
    vocabulary=None,
    stopwords=None,
    cohort_ledger=None,
    decision_record=None,
    output_root=None,
    evidence_root=None,
    history_root=None,
) -> dict[str, Any]:
    """Delegate explicit configurations; legacy driver calls fail before any IO."""
    if set(sources) != set(SOURCES):
        raise ValueError("P5 subset output contract is undefined; use all sources")
    required = [input_manifest, vocabulary, stopwords, cohort_ledger, decision_record,
                output_root, evidence_root, history_root]
    if any(value is None for value in required):
        raise ValueError(
            "Legacy P5 writer is disabled: use python -m preprocessing.encoding.execute "
            "with explicit --input-manifest --vocabulary --stopwords --cohort-ledger "
            "--decision-record --output-root --evidence-root --history-root; "
            "prototype output must not overwrite the canonical cohort bundle."
        )
    from preprocessing.encoding.execute import run_execution

    return run_execution(input_manifest, vocabulary, stopwords, output_root, evidence_root,
                         dry_run=dry_run, publish=not dry_run, cohort_ledger=cohort_ledger,
                         decision_record=decision_record, history_root=history_root)
