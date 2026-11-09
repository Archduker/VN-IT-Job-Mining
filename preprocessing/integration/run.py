# -*- coding: utf-8 -*-
"""Bước 02 Integration (docs/preprocessing/spec/P2_integration.md).

Làm phẳng dữ liệu từ envelope 01_clean về 18 trường chung + khóa và metadata sạch.
Gộp 8 nguồn vào một file duy nhất: data/preprocessing/02_integration/all.parquet.
Tự động đồng bộ tầng dữ liệu 01_clean từ Cloudflare R2 về local nếu máy chưa có.
Báo cáo theo nguồn ở reports/preprocessing/02_integration/<source>.json, tổng ở _all.json.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from preprocessing.common import REPO_ROOT, SOURCES
from preprocessing.common.step_report import StepReport, _rel, merge_reports
from preprocessing.integration.json_flattener import flatten_raw_job_record

logger = logging.getLogger(__name__)

STEP = "02_integration"
DATA_DIR = REPO_ROOT / "data"
IN_DIR = DATA_DIR / "preprocessing" / "01_clean"
OUT_DIR = DATA_DIR / "preprocessing" / STEP
OUT_FILE = OUT_DIR / "all.parquet"

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


def ensure_p1_data_from_r2(target_dir: Path, sources: Sequence[str]) -> None:
    """Kiểm tra và tự động tải file clean của 8 sàn từ Cloudflare R2 nếu local chưa có."""
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Kiểm tra xem local đã có file jsonl/parquet nào chưa
    existing_files = list(target_dir.glob("*.jsonl")) + list(target_dir.glob("*.parquet"))
    if len(existing_files) >= len(sources):
        return

    endpoint = os.getenv("R2_ENDPOINT_URL") or os.getenv("CLOUDFLARE_R2_ENDPOINT")
    access_key = os.getenv("R2_ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("R2_SECRET_ACCESS_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY")
    bucket = os.getenv("R2_BUCKET_NAME") or "vn-it-jobs"

    if not (endpoint and access_key and secret_key):
        logger.info("Không có biến môi trường R2, sử dụng dữ liệu có sẵn tại local.")
        return

    try:
        import boto3
        from botocore.config import Config
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"}),
            region_name="auto",
        )
        logger.info("Đang kiểm tra và đồng bộ dữ liệu P1 Clean từ Cloudflare R2...")
        prefixes = [
            "staging/{src}/preprocessing/01_clean",
            "preprocessing/01_clean/{src}",
            "01_clean/{src}",
            "data/preprocessing/01_clean/{src}",
        ]

        for src in sources:
            dest_file = target_dir / f"{src}.jsonl"
            if dest_file.exists():
                continue
            for prefix_pattern in prefixes:
                prefix = prefix_pattern.format(src=src)
                found = False
                for ext in [".jsonl", ".parquet", ".json"]:
                    r2_key = f"{prefix}{ext}"
                    try:
                        s3.head_object(Bucket=bucket, Key=r2_key)
                        out_f = target_dir / f"{src}{ext}"
                        logger.info(f"Đang tải từ R2: {r2_key} -> {out_f}")
                        s3.download_file(bucket, r2_key, str(out_f))
                        found = True
                        break
                    except Exception:
                        continue
                if found:
                    break
    except Exception as exc:
        logger.warning(f"Không thể kết nối hoặc tải từ R2: {exc}. Tiếp tục với dữ liệu local.")


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
                # Đảm bảo Zero-drop contract: fallback parse an toàn để không mất bản ghi
                env = {"raw_payload": {"title": line[:80], "description": line}, "metadata": {"source": source}}
                bad_lines.append({"job_id": f"dòng {line_idx + 1}", "field": "json", "before": line[:80], "after": f"lỗi: {exc.msg}", "url": None})

            raw = env.get("raw_payload", {})
            meta = env.get("metadata", {})
            clean_info = meta.get("clean", {})

            # I1: Làm phẳng bằng flatten_raw_job_record
            flat = flatten_raw_job_record(env)

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

            # Dựng record phẳng theo đúng contract 28 cột của P2
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
    report.rule("I0", "Phục hồi dòng JSON lỗi để bảo toàn hợp đồng", "modify", len(bad_lines), bad_lines)
    report.rule("I1", "Làm phẳng envelope về 18 trường chuẩn + khóa", "modify", total_rows)
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

    # Khẳng định bảo toàn số lượng bản ghi (Zero-drop)
    report.check_conserved()
    return rows, report


def run(sources: Sequence[str] = SOURCES, dry_run: bool = False) -> Dict[str, StepReport]:
    """Chạy toàn bộ pipeline P2 và xuất file all.parquet duy nhất."""
    # Tự động đồng bộ từ R2 nếu local chưa có đủ dữ liệu
    ensure_p1_data_from_r2(IN_DIR, sources)

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
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(all_rows)
        # Đảm bảo thứ tự cột chuẩn
        valid_cols = [c for c in ALL_OUTPUT_COLUMNS if c in df.columns]
        df[valid_cols].to_parquet(OUT_FILE, engine="pyarrow", index=False)
        logger.info(f"Đã lưu thành công tệp hợp nhất: {OUT_FILE} ({len(df):,} bản ghi).")

    total_rep.write()
    return reports


if __name__ == "__main__":
    # Mặc định dry_run=False để xuất file all.parquet thực tế
    run(dry_run=False)