# -*- coding: utf-8 -*-
"""Bước 10d (PH8): ma trận đặc trưng số cho Mining. Gộp 10 (rời rạc hóa), 10b (chọn kỹ năng), 10c (xây), 10d (mã hóa).

Giữ đúng số dòng của bảng 04. Cờ `seniority_can_kiem` được giữ thành cột (không bỏ dòng) để Mining tự lọc.
Lương thỏa thuận và không ghi gộp thành `salary_status__unknown`; số lương không điền.
"""

from __future__ import annotations

import json
from typing import Dict, Tuple

import numpy as np
import pandas as pd

from preprocessing.common import REPO_ROOT
from preprocessing.common.step_report import StepReport, merge_reports
from preprocessing.encoding.run import SENIORITY_MAP, TOP_PROVINCES_K, to_col_slug
from preprocessing.normalization.job_title import fold
from preprocessing.normalization.job_title import JOB_FAMILIES, OTHER
from processing.construction.features import construct, salary_ref_m
from processing.selection.sparsity import OTHER as OTHER_SKILL
from processing.selection.sparsity import reduce_sparsity
from processing.transformation.discretize import discretize

STEP = "10_features"
MIN_DF = 15  # người dùng đề xuất 10-20; mặc định 15


def _onehot(values: pd.Series, cats, prefix: str, dic: dict, extra_unknown: bool = False) -> pd.DataFrame:
    cols = {}
    slugs = {c: f"{prefix}__{to_col_slug(c)}" for c in cats}
    for c, name in slugs.items():
        cols[name] = (values == c).astype(np.uint8)
    if extra_unknown:
        cols[f"{prefix}__unknown"] = (~values.isin(list(cats))).astype(np.uint8)
    for name in cols:
        dic[name] = {"method": "one_hot", "source_column": prefix}
    return pd.DataFrame(cols, index=values.index)


def employment_class(text) -> str:
    """Luật từ khóa trên chuỗi gốc [ĐỀ XUẤT]; null hoặc không nhận ra (ví dụ "6") -> unknown, không đoán."""
    t = fold(text)
    for cls, keys in (("intern", ("thuc tap", "intern")), ("part_time", ("ban thoi gian", "part time", "part_time", "parttime")),
                      ("contract", ("hop dong", "contract", "freelance", "thoi vu", "temporary")),
                      ("full_time", ("toan thoi gian", "full time", "full_time", "fulltime", "chinh thuc"))):
        if any(k in t for k in keys):
            return cls
    return "unknown"


def _provinces(locations) -> list:
    return sorted({loc.get("tinh_key") for loc in (locations if locations is not None else []) if loc.get("tinh_key")})


def _numeric(out: dict, names, df, dic) -> None:
    for c in names:
        out[c] = df[c].astype(float).values
        out[f"{c}__missing"] = df[c].isna().astype(np.uint8).values
        dic[c] = {"method": "numeric", "source_column": c}
        dic[f"{c}__missing"] = {"method": "flag", "source_column": c}


def build_features(df: pd.DataFrame, skills: pd.DataFrame, tokens: pd.DataFrame, min_df: int = MIN_DF
                   ) -> Tuple[pd.DataFrame, Dict, dict]:
    df = df.reset_index(drop=True)
    dic: Dict[str, dict] = {}
    ref = salary_ref_m(df)
    parts = [pd.DataFrame({"job_id_global": df["job_id_global"]}),
             construct(df, skills, tokens).drop(columns="job_id_global"),
             discretize(df, ref)]
    dic.update({c: {"method": "construction", "source_column": "04/08/09"} for c in parts[1].columns})
    dic.update({c: {"method": "discretize", "source_column": "salary/exp_min_years"} for c in parts[2].columns})

    # 10b: gom kỹ năng hiếm (df < min_df) thành other_skill; số JD không đổi
    rows = skills.to_dict("records")
    kept, rep = reduce_sparsity(rows, len(df), {}, min_df=min_df, mode="other")
    sk = pd.DataFrame(kept)
    mat = pd.crosstab(sk["job_id_global"], sk["slug"]).clip(upper=1).astype(np.uint8)
    mat = mat.reindex(df["job_id_global"]).fillna(0).astype(np.uint8)
    mat.columns = [f"skill__{c}" for c in mat.columns]
    mat.index = df.index
    for c in mat.columns:
        dic[c] = {"method": "multi_hot", "source_column": "08_skills"}
    parts.append(mat)

    # 10d
    parts.append(pd.DataFrame({"seniority_ord": df["seniority"].map(lambda x: SENIORITY_MAP.get(str(x), -1)).astype(np.int8)}))
    dic["seniority_ord"] = {"method": "ordinal", "source_column": "seniority", "mapping": SENIORITY_MAP, "unknown": -1}
    parts.append(_onehot(df["job_family"], [*JOB_FAMILIES, OTHER], "fam", dic))
    parts.append(_onehot(df["source_platform"], sorted(df["source_platform"].dropna().unique()), "src", dic))
    parts.append(_onehot(df["work_mode"], ["onsite", "remote", "hybrid"], "wm", dic, extra_unknown=True))
    # E2 loại hình làm việc
    emp = df["raw_employment_type"].map(employment_class)
    parts.append(_onehot(emp, ["full_time", "part_time", "intern", "contract", "unknown"], "emp", dic))
    # E3 tỉnh: multi-hot top K theo mọi địa điểm của tin; còn lại other; không có tỉnh = unknown; remote, ngoài VN là cờ
    name2key = {p["name"]: p["key"] for p in json.loads((REPO_ROOT / "preprocessing" / "dictionaries" / "provinces_34.json")
                                                        .read_text(encoding="utf-8"))["provinces"]}
    provs = pd.Series([ks or ([name2key[t]] if t in name2key else []) for ks, t in zip(df["locations"].map(_provinces), df["tinh_chinh"])],
                      index=df.index)  # locations không ra tỉnh thì dùng tinh_chinh (đã suy từ địa chỉ ở bước 04)
    cnt = pd.Series([k for ks in provs for k in ks]).value_counts()
    top = list(cnt.head(TOP_PROVINCES_K).index)
    tcols = {f"tinh__{to_col_slug(k)}": provs.map(lambda ks, k=k: int(k in ks)) for k in top}
    tcols["tinh__other"] = provs.map(lambda ks: int(any(k not in top for k in ks)))
    tcols["tinh__unknown"] = provs.map(lambda ks: int(not ks))
    tcols["loc_remote"] = df["locations"].map(lambda L: int(any(x.get("remote") for x in (L if L is not None else []))))
    tcols["loc_ngoai_vn"] = df["locations"].map(lambda L: int(any(x.get("ngoai_vn") for x in (L if L is not None else []))))
    parts.append(pd.DataFrame({k: v.astype(np.uint8) for k, v in tcols.items()}))
    dic.update({c: {"method": "multi_hot" if c.startswith("tinh__") else "flag", "source_column": "locations"} for c in tcols})
    # E5 số giữ nguyên, thiếu giữ NaN kèm cột __missing
    num: dict = {}
    _numeric(num, ["log_salary_min", "log_salary_max", "exp_min_years", "exp_max_years", "headcount"], df, dic)
    # E7 ngày: tháng đăng và số ngày còn lại tới hạn nộp tính từ ngày cào
    crawled = pd.to_datetime(df["crawled_at"], errors="coerce", utc=True).dt.tz_localize(None).dt.normalize()
    posted = pd.to_datetime(df["posted_date"], errors="coerce")
    deadline = pd.to_datetime(df["deadline_date"], errors="coerce")
    num["posted_month"] = posted.dt.month.astype(float).values
    num["days_to_deadline"] = (deadline - crawled).dt.days.astype(float).values
    num["days_to_deadline__missing"] = pd.isna(num["days_to_deadline"]).astype(np.uint8)
    dic.update({"posted_month": {"method": "date", "source_column": "posted_date"},
                "days_to_deadline": {"method": "date", "source_column": "deadline_date - crawled_at"},
                "days_to_deadline__missing": {"method": "flag", "source_column": "deadline_date"}})
    parts.append(pd.DataFrame(num, index=df.index))
    st = df["salary_status"]
    flags = pd.DataFrame({
        "salary_status__value": (st == "value").astype(np.uint8),
        "salary_status__unknown": (st != "value").astype(np.uint8),  # thỏa thuận và không ghi
        "is_negotiable": df["is_negotiable"].astype(np.uint8),
        "is_outlier_salary": df["is_outlier_salary"].fillna(False).astype(np.uint8),
        "seniority_can_kiem": df["seniority_can_kiem"].fillna(False).astype(np.uint8),
    })
    dic.update({c: {"method": "flag", "source_column": c.split("__")[0]} for c in flags.columns})
    parts.append(flags)
    feats = pd.concat([p.reset_index(drop=True) for p in parts], axis=1)
    return feats, dic, {"min_df": min_df, "n_skill_cols": int(mat.shape[1]), "folded": rep["folded_into"]}


def run(sources, dry_run: bool = True, df=None, input_path=None, out_root=None, report_root=None, min_df: int = MIN_DF):
    from processing.extraction.run import DEFAULT_INPUT, OUT_ROOT, REPORT_ROOT
    input_path, out_root, report_root = input_path or DEFAULT_INPUT, out_root or OUT_ROOT, report_root or REPORT_ROOT
    df = pd.read_parquet(input_path) if df is None else df
    df = df[df["source_platform"].isin(list(sources))].sort_values("job_id_global", kind="mergesort")
    skills = pd.read_parquet(out_root / "08_skills" / "job_skills.parquet")
    tokens = pd.read_parquet(out_root / "09_tokens" / "all.parquet")[["job_id_global", "n_tokens"]]
    feats, dic, rep = build_features(df, skills, tokens, min_df)
    reports = {}
    for src in sources:
        n = int((df["source_platform"] == src).sum())
        r = StepReport(STEP, src, dry_run)
        r.set_io(None, n, out_root / STEP / "features.parquet", n)
        r.data["extra"] = {"n_cols": feats.shape[1] - 1, "min_df": min_df, "model": "không dùng model"}
        reports[src] = r
    total = merge_reports(STEP, list(reports.values()), dry_run)
    total.data["extra"].update(n_cols=feats.shape[1] - 1, min_df=min_df, n_skill_cols=rep["n_skill_cols"],
                               n_skills_folded=sum(len(v) for v in rep["folded"].values()))
    reports["_all"] = total
    for r in reports.values():
        r.check_conserved()
    if not dry_run:
        for r in reports.values():
            r.write(report_root)
        (out_root / STEP).mkdir(parents=True, exist_ok=True)
        feats.to_parquet(out_root / STEP / "features.parquet", index=False)
        (out_root / STEP / "encoding_dictionary.json").write_text(json.dumps(dic, ensure_ascii=False, indent=1), encoding="utf-8")
    return reports
