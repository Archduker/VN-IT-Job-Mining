# -*- coding: utf-8 -*-
"""Bước 02 Integration (docs/spec/preprocessing/spec/P2_integration.md).

Làm phẳng dữ liệu từ envelope 01_clean về 18 trường chung + khóa và metadata sạch.
Gộp 8 nguồn vào một file data/preprocessing/02_integration/all.parquet (cột source_platform giữ nguồn).
Báo cáo theo nguồn ở reports/preprocessing/02_integration/<source>.json, tổng ở _all.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from preprocessing.common import REPO_ROOT, SOURCES
from preprocessing.common.step_report import StepReport, _rel, merge_reports
from preprocessing.integration.json_flattener import flatten_raw_job_record

STEP = "02_integration"
DATA_DIR = REPO_ROOT / "data"
IN_DIR = DATA_DIR / "preprocessing" / "01_clean"
OUT_FILE = DATA_DIR / "preprocessing" / STEP / "all.parquet"

KEYS = ("job_id_global", "source_platform", "source_job_id", "source_url", "crawled_at")
CLEAN_META = ("it_rule", "it_rule_level", "it_status", "dedup_key", "also_on")
KEEP_18 = (
    "job_title",
    "company_name",
    "company_address",
    "raw_category_text",
    "raw_location_text",
    "working_locations",
    "raw_posted_date",
    "raw_deadline",
    "raw_salary_text",
    "raw_employment_type",
    "raw_experience_text",
    "raw_seniority_text",
    "raw_education_text",
    "raw_headcount",
    "skills_list",
    "benefits_list",
    "raw_description_text",
    "raw_requirements_text",
)

ALL_OUTPUT_COLUMNS = KEYS + CLEAN_META + KEEP_18


def _is_empty(val: Any) -> bool:
    """I5: Chuỗi rỗng, khoảng trắng, container rỗng -> True."""
    if val is None:
        return True
    if isinstance(val, str):
        return not val.strip()
    if isinstance(val, (list, dict, set, tuple)):
        return len(val) == 0
    return False


def _clean_empty(val: Any) -> Any:
    """I5: Giá trị rỗng chuyển thành None."""
    return None if _is_empty(val) else val


def _calc_fill_pct(rows: List[Dict[str, Any]], field: str) -> float:
    if not rows:
        return 0.0
    filled = sum(1 for r in rows if not _is_empty(r.get(field)))
    return round((filled / len(rows)) * 100.0, 1)


def process_source(source: str, dry_run: bool = True) -> tuple[List[Dict[str, Any]], StepReport]:
    in_file = IN_DIR / f"{source}.jsonl"
    out_file = OUT_FILE
    report = StepReport(STEP, source, dry_run)

    if not in_file.exists():
        report.set_io(in_file, 0, out_file, 0)
        report.note(f"Không tìm thấy file đầu vào {in_file}")
        report.check_conserved()
        return [], report

    rows: List[Dict[str, Any]] = []
    i2_count = 0
    i3_date_count = 0
    i3_exp_count = 0
    i4_count = 0
    i5_count = 0

    i2_examples = []
    i3_examples = []
    i4_examples = []
    i5_examples = []
    bad_lines: List[Dict[str, Any]] = []
    n_in = 0

    with in_file.open("r", encoding="utf-8") as f:
        for line_idx, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            n_in += 1
            try:
                env = json.loads(line)
            except json.JSONDecodeError as exc:
                bad_lines.append({"job_id": f"dòng {line_idx + 1}", "field": "json", "before": line[:80], "after": f"lỗi: {exc.msg}", "url": None})
                continue

            raw = env.get("raw_payload", {})
            meta = env.get("metadata", {})
            clean_info = meta.get("clean", {})

            # I1: Làm phẳng bằng flatten_raw_job_record
            flat = flatten_raw_job_record(env)

            # Kiểm đếm các luật cụ thể
            job_id = meta.get("job_id") or flat.get("job_id_global") or str(line_idx)
            url = meta.get("source_url") or flat.get("source_url")

            # I2: ITviec datePosted JSON-LD
            if source == "itviec":
                jsonld = raw.get("job_posting_jsonld")
                if isinstance(jsonld, dict) and jsonld.get("datePosted"):
                    i2_count += 1
                    if len(i2_examples) < 3:
                        i2_examples.append({
                            "job_id": job_id,
                            "field": "raw_posted_date",
                            "before": raw.get("posted_at_raw"),
                            "after": flat.get("raw_posted_date"),
                            "url": url,
                        })

            # I3: TopDev published / jsonld
            if source == "topdev":
                jsonld = raw.get("job_posting_jsonld")
                jsonld_d = jsonld if isinstance(jsonld, dict) else {}
                if raw.get("published") or raw.get("date_posted") or jsonld_d.get("datePosted"):
                    i3_date_count += 1
                    if len(i3_examples) < 3:
                        i3_examples.append({
                            "job_id": job_id,
                            "field": "raw_posted_date",
                            "before": raw.get("recalled_at"),
                            "after": flat.get("raw_posted_date"),
                            "url": url,
                        })
                if jsonld_d.get("experienceRequirements"):
                    i3_exp_count += 1

            # I4: CareerViet / JobsGO SEO tags or occupations ignored
            if source == "careerviet" and raw.get("job-tags"):
                i4_count += 1
                if len(i4_examples) < 3:
                    i4_examples.append({
                        "job_id": job_id,
                        "field": "skills_list",
                        "before": str(raw.get("job-tags")[:3]),
                        "after": str(flat.get("skills_list")),
                        "url": url,
                    })
            elif source == "jobsgo" and raw.get("occupations"):
                i4_count += 1
                if len(i4_examples) < 3:
                    i4_examples.append({
                        "job_id": job_id,
                        "field": "skills_list",
                        "before": str(raw.get("occupations")[:3]),
                        "after": str(flat.get("skills_list")),
                        "url": url,
                    })

            # Dựng record phẳng theo đúng contract 28 cột
            record: Dict[str, Any] = {}
            had_i5_clean = False

            # 1. Keys
            record["job_id_global"] = flat.get("job_id_global")
            record["source_platform"] = flat.get("source_platform") or source
            record["source_job_id"] = flat.get("source_job_id") or meta.get("job_id")
            record["source_url"] = flat.get("source_url") or meta.get("source_url")
            record["crawled_at"] = flat.get("crawled_at") or meta.get("scraped_at")

            # 2. Metadata clean từ P1
            record["it_rule"] = clean_info.get("it_rule")
            record["it_rule_level"] = clean_info.get("it_rule_level")
            record["it_status"] = clean_info.get("it_status")
            record["dedup_key"] = clean_info.get("dedup_key")
            record["also_on"] = clean_info.get("also_on") or []

            # 3. 18 trường giữ
            for col in KEEP_18:
                orig_val = flat.get(col)
                cleaned_val = _clean_empty(orig_val)
                if orig_val is not None and cleaned_val is None:
                    had_i5_clean = True
                record[col] = cleaned_val

            if had_i5_clean:
                i5_count += 1
                if len(i5_examples) < 3:
                    i5_examples.append({
                        "job_id": job_id,
                        "field": "empty_value",
                        "before": "'' or []",
                        "after": None,
                        "url": url,
                    })

            rows.append(record)

    total_rows = len(rows)
    report.set_io(in_file, n_in, out_file, total_rows)

    # Đăng ký các luật đã thực thi
    report.rule("I0", "Bỏ dòng JSON hỏng trong file Clean", "drop", len(bad_lines), bad_lines,
                "dòng không đọc được JSON, cần xem lại file 01_clean")
    report.rule("I1", "Làm phẳng envelope về 18 trường chuẩn + khóa", "modify", total_rows)
    # Luôn ghi đủ I0–I5 (kể cả 0 dòng) để báo cáo gộp giữ đúng thứ tự chạy
    report.rule("I2", "ITviec lấy ngày đăng từ JSON-LD datePosted", "modify", i2_count, i2_examples)
    report.rule("I3", "TopDev lấy ngày đăng và kinh nghiệm từ published/JSON-LD", "modify",
                max(i3_date_count, i3_exp_count), i3_examples)
    report.rule("I4", "Bỏ tag SEO và ngành nghề khỏi skills_list", "modify", i4_count, i4_examples)
    report.rule("I5", "Chuyển chuỗi rỗng và container rỗng về null", "modify", i5_count, i5_examples)

    # Thống kê độ phủ 18 trường
    fields_stats = []
    for f in KEEP_18:
        pct = _calc_fill_pct(rows, f)
        fields_stats.append({"field": f, "fill_pct_in": pct, "fill_pct_out": pct})
    report.data["fields"] = fields_stats

    report.check_conserved()
    return rows, report


def run(sources: Sequence[str] = SOURCES, dry_run: bool = True) -> Dict[str, StepReport]:
    reports: Dict[str, StepReport] = {}
    all_rows: List[Dict[str, Any]] = []
    for src in sources:
        rows, rep = process_source(src, dry_run=dry_run)
        reports[src] = rep
        all_rows.extend(rows)

    total_rep = merge_reports(STEP, list(reports.values()), dry_run)
    total_rep.data["input"]["path"] = "data/preprocessing/01_clean/<nguồn>.jsonl"
    total_rep.data["output"]["path"] = _rel(OUT_FILE)
    total_rep.check_conserved()
    for rep in reports.values():
        rep.write()
    if not dry_run and all_rows:
        OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(all_rows)
        df[[c for c in ALL_OUTPUT_COLUMNS if c in df.columns]].to_parquet(OUT_FILE, engine="pyarrow", index=False)
    total_rep.write()
    return reports
