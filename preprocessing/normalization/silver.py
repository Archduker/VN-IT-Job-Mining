# -*- coding: utf-8 -*-
"""Bảng Silver (luật S1–S5, docs/spec/preprocessing/silver.md; hợp đồng 26 trường ở spec 05 mục 4.4).

Chọn cột của bảng 04 và đổi tên sang tiếng Anh, **không tính lại giá trị**. Trường `skills` lấy từ bước 08
(`data/processing/08_skills/job_skills.parquet`, từ điển skills_v2; người dùng chốt K8.9 ngày 18/11), nên Silver chạy
sau bước 08. Tin cách ly ở bước 04 (Q1) không có trong `all.parquet` nên cũng không có ở đây (S5).

    python -m preprocessing.normalization.silver [--dry-run]

Ghi `data/preprocessing/04_normalization/silver.parquet` và `reports/preprocessing/04_normalization/silver.json`
(độ phủ từng trường theo nguồn, kiểu, giá trị mẫu, đánh dấu) cho trang `silver_gap.html`.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from preprocessing.common import REPO_ROOT, SOURCES
from preprocessing.common import step_report

DATA_04 = REPO_ROOT / "data" / "preprocessing" / "04_normalization"
IN_FILE = DATA_04 / "all.parquet"
SKILLS_FILE = REPO_ROOT / "data" / "processing" / "08_skills" / "job_skills.parquet"
OUT_FILE = DATA_04 / "silver.parquet"

# (trường Silver, cột bảng 04), đúng thứ tự spec 05 mục 4.4 (S4). `skills` là trường tính từ bước 08.
SILVER_FIELDS = [
    ("job_id", "job_id_global"), ("source", "source_platform"), ("url", "source_url"),
    ("title", "job_title_clean"), ("title_canonical", "title_canonical"), ("job_family", "job_family"),
    ("seniority", "seniority"), ("seniority_inferred", "level_inferred"),
    ("exp_min_years", "exp_min_years"), ("exp_max_years", "exp_max_years"), ("exp_inferred", "exp_inferred"),
    ("salary_min", "salary_min_vnd_capped"), ("salary_max", "salary_max_vnd_capped"),
    ("salary_negotiable", "is_negotiable"), ("salary_outlier", "is_outlier_salary"),
    ("province", "tinh_chinh"), ("work_mode", "work_mode"), ("employment_type", "employment_type"),
    ("company", "company_norm"), ("company_id", "company_key"), ("skills", None),
    ("benefits", "benefits_std"), ("description", "description_clean"), ("requirements", "requirements_clean"),
    ("language", "language"), ("posted_month", "posted_month"),
]
BOOL_FIELDS = ("seniority_inferred", "exp_inferred", "salary_negotiable", "salary_outlier")
LIST_FIELDS = ("skills", "benefits")
FLOAT_FIELDS = ("exp_min_years", "exp_max_years", "salary_min", "salary_max")
LOW_COVERAGE_PCT = 50.0  # dưới mức này thì đánh dấu "phủ thấp" trên trang đối chiếu


class SilverContractError(ValueError):
    """Bảng 04 thiếu cột nguồn hoặc giá trị sai kiểu: dừng và báo, không tạo cột rỗng (silver.md mục 3)."""


def _is_null(v: Any) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def _as_list(v: Any) -> List[str]:
    if _is_null(v):
        return []
    return [str(x) for x in list(v)]


def skills_by_job(job_skills: pd.DataFrame) -> Dict[str, List[str]]:
    """Slug kỹ năng của mỗi tin (mọi `via`: văn bản gốc, bản dịch, thẻ của sàn), bỏ trùng, sắp xếp."""
    if job_skills.empty:
        return {}
    return {j: sorted(set(g)) for j, g in job_skills.groupby("job_id_global")["slug"]}


def build_silver(t04: pd.DataFrame, job_skills: pd.DataFrame) -> pd.DataFrame:
    missing = [src for _, src in SILVER_FIELDS if src and src not in t04.columns]
    if missing:
        raise SilverContractError(f"bảng 04 thiếu cột nguồn: {', '.join(missing)}")
    for f, src in SILVER_FIELDS:
        if f in BOOL_FIELDS and t04[src].isna().any():
            raise SilverContractError(f"{src} (→ {f}) có null; Silver yêu cầu bool không null")
    sk = skills_by_job(job_skills)
    out = pd.DataFrame(index=t04.index)
    for f, src in SILVER_FIELDS:
        if f == "skills":
            out[f] = [sk.get(j, []) for j in t04["job_id_global"]]
        elif f in BOOL_FIELDS:
            out[f] = t04[src].astype(bool)
        elif f in LIST_FIELDS:
            out[f] = [_as_list(v) for v in t04[src]]
        elif f in FLOAT_FIELDS:
            out[f] = pd.to_numeric(t04[src], errors="raise").astype(float)
        elif f == "work_mode":   # S2: thiếu thì unknown, không để null
            out[f] = [v if not _is_null(v) else "unknown" for v in t04[src]]
        else:
            out[f] = [None if _is_null(v) else str(v) for v in t04[src]]
    out = out.reset_index(drop=True)
    if not out["job_id"].is_unique:
        raise SilverContractError("job_id trùng trong bảng 04")
    return out


def check_silver(silver: pd.DataFrame, t04: pd.DataFrame) -> List[str]:
    """Nghiệm thu silver.md mục 6: số dòng, khóa duy nhất, 26 trường, giá trị trùng cột nguồn (trừ S2 và `skills`)."""
    errs: List[str] = []
    if len(silver) != len(t04):
        errs.append(f"số dòng {len(silver)} khác bảng 04 {len(t04)}")
    if list(silver.columns) != [f for f, _ in SILVER_FIELDS]:
        errs.append("cột không đúng 26 trường hoặc sai thứ tự")
    if not silver["job_id"].is_unique:
        errs.append("job_id trùng")
    t = t04.reset_index(drop=True)
    for f, src in SILVER_FIELDS:
        if src is None or f not in silver:
            continue
        a, b = silver[f], t[src]
        for i in range(len(t)):
            x, y = a.iloc[i], b.iloc[i]
            if f == "work_mode" and _is_null(y):
                ok = x == "unknown"
            elif f in LIST_FIELDS:
                ok = list(x) == _as_list(y)
            elif _is_null(y):
                ok = _is_null(x)
            elif f in FLOAT_FIELDS:
                ok = float(x) == float(y)
            elif f in BOOL_FIELDS:
                ok = bool(x) == bool(y)
            else:
                ok = str(x) == str(y)
            if not ok:
                errs.append(f"{f}: dòng {i} khác cột nguồn {src}")
                break
    return errs


def gap_report(silver: pd.DataFrame) -> Dict[str, Any]:
    """Độ phủ từng trường theo nguồn, kiểu, 3 giá trị mẫu và đánh dấu cho trang `silver_gap.html`."""
    def filled(v: Any) -> bool:
        if isinstance(v, (list, tuple)) or hasattr(v, "__len__") and not isinstance(v, str):
            return len(v) > 0
        return not _is_null(v) and v != "unknown"

    fields = []
    for f, src in SILVER_FIELDS:
        col = silver[f]
        by_src = {s: round(100.0 * sum(filled(v) for v in col[silver["source"] == s]) / max(1, (silver["source"] == s).sum()), 1)
                  for s in SOURCES if (silver["source"] == s).any()}
        pct = round(100.0 * sum(filled(v) for v in col) / max(1, len(col)), 1)
        samples = [str(list(v)[:5]) if f in LIST_FIELDS else str(v)[:80] for v in col[[filled(v) for v in col]].head(3)]
        status = "có" if f in BOOL_FIELDS or pct >= LOW_COVERAGE_PCT else "phủ thấp"
        fields.append({"field": f, "source_column": src or "08_skills/job_skills.parquet (slug)",
                       "dtype": str(col.dtype), "fill_pct": pct, "fill_pct_by_source": by_src,
                       "samples": samples, "status": status})
    return {"rows": len(silver), "n_fields": len(SILVER_FIELDS), "fields": fields,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def run(dry_run: bool = True, in_file: Path = IN_FILE, skills_file: Path = SKILLS_FILE,
        out_file: Path = OUT_FILE, report_root: Optional[Path] = None) -> Dict[str, Any]:
    if not skills_file.exists():
        raise FileNotFoundError(f"thiếu {skills_file}: Silver chạy sau bước 08")
    t04 = pd.read_parquet(in_file)
    silver = build_silver(t04, pd.read_parquet(skills_file))
    errs = check_silver(silver, t04)
    rep = {"step": "silver", "input": {"rows": len(t04)}, "output": {"rows": len(silver)},
           "checks": {"errors": errs, "passed": not errs}, **gap_report(silver), "dry_run": dry_run}
    if errs:
        raise SilverContractError("; ".join(errs))
    if not dry_run:
        out_file.parent.mkdir(parents=True, exist_ok=True)
        silver.to_parquet(out_file, engine="pyarrow", index=False)
        root = report_root or step_report.REPORTS_ROOT
        path = root / "04_normalization" / "silver.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    return rep


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="dựng và kiểm, không ghi file")
    a = ap.parse_args(argv)
    rep = run(dry_run=a.dry_run)
    low = [f["field"] for f in rep["fields"] if f["status"] != "có"]
    print(f"silver: {rep['input']['rows']} → {rep['output']['rows']} dòng, {rep['n_fields']} trường; "
          f"kiểm {'đạt' if rep['checks']['passed'] else 'LỖI'}; phủ thấp: {', '.join(low) or 'không'}"
          f"{' (dry-run, không ghi)' if a.dry_run else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
