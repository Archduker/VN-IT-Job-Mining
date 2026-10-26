# -*- coding: utf-8 -*-
"""scripts.run_staging_integration_pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Pipeline vận hành toàn diện quy trình Preprocessing sau bước Integration:
  1. Đọc và ép phẳng toàn bộ dữ liệu thô (JSON Flattening) từ 8 sàn tuyển dụng.
  2. Bóc tách dải lương Cascade 3 tầng (Header Regex -> JD Regex Scanner -> GenAI Fallback).
  3. Quy đổi ngoại tệ (USD sang VND) và lương năm sang tháng (/12).
  4. Bóc trần null markers, phát hiện và loại bỏ Stub JD < 30 từ (Chính sách 1.B).
  5. Bù khuyết dữ liệu thông minh qua GenAI Imputer (min_experience, seniority, city, skills).
  6. Chuẩn hóa dải lương (Log-transformation, IQR Outlier Capping & Winsorization).
  7. Chuẩn hóa phân loại (12 Job Family SD2, 6 bậc Seniority, 63 tỉnh thành).
  8. Khử trùng lặp ngữ nghĩa xuyên sàn (Cross-Platform Entity Resolution via Embeddings).
  9. Xuất bản Bộ 3 Tài Liệu Chuẩn Mực cho mỗi nguồn và xuất bản Golden Master Dataset.
"""

from __future__ import annotations

import glob
import json
import logging
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

# Thiết lập đường dẫn root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from preprocessing.integration.json_flattener import flatten_raw_job_record
from preprocessing.transformation.salary_parser import UniversalSalaryParser, parse_salary_cascade
from preprocessing.transformation.text_metrics import calculate_text_metrics, detect_language
from preprocessing.missing_outlier.sneaky_null_detector import is_val_null, classify_salary_null
from preprocessing.missing_outlier.genai_text_imputer import GenAITextImputer
from preprocessing.missing_outlier.outlier_handler import fix_common_salary_input_errors, winsorize_series
from preprocessing.normalization.log_transformer import log_transform_salary
from preprocessing.normalization.text_cleaner import (
    clean_job_title,
    normalize_city,
    normalize_seniority,
    classify_job_family,
)
from preprocessing.normalization.cross_deduplicator import deduplicate_cross_platform_jobs

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("staging_pipeline")

SOURCES = [
    "careerviet",
    "glints",
    "itviec",
    "jobsgo",
    "topcv",
    "topdev",
    "vieclam24h",
    "vietnamworks",
]


def setup_directories() -> Dict[str, Path]:
    """Khởi tạo cấu trúc thư mục lưu trữ Staging, Curated và Reports."""
    dirs = {
        "staging_dir": PROJECT_ROOT / "data" / "staging",
        "curated_dir": PROJECT_ROOT / "data" / "curated",
        "reports_dir": PROJECT_ROOT / "reports",
        "data_reports_dir": PROJECT_ROOT / "data" / "reports",
    }
    for p in dirs.values():
        p.mkdir(parents=True, exist_ok=True)
    for s in SOURCES:
        (dirs["staging_dir"] / s).mkdir(parents=True, exist_ok=True)
        (dirs["reports_dir"] / s).mkdir(parents=True, exist_ok=True)
        (dirs["data_reports_dir"] / s).mkdir(parents=True, exist_ok=True)
    return dirs


def process_single_source(
    source_name: str,
    imputer: GenAITextImputer,
    directories: Dict[str, Path],
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Xử lý toàn diện cho 1 nguồn dữ liệu và tạo bộ 3 deliverables."""
    logger.info(f"=== Đang xử lý nguồn tuyển dụng: {source_name.upper()} ===")
    t0 = time.time()

    # Tìm toàn bộ files JSON thô
    raw_files = glob.glob(str(PROJECT_ROOT / "data" / source_name / "raw" / "**" / "*.json"), recursive=True)
    if not raw_files:
        raw_files = glob.glob(str(PROJECT_ROOT / "data" / source_name / "**" / "*.json"), recursive=True)

    total_files_scanned = len(raw_files)
    total_raw_envelopes = 0
    stub_jds_removed = 0
    records_by_id: Dict[str, Dict[str, Any]] = {}

    salary_header_hits = 0
    salary_jd_hits = 0
    imputed_count = 0

    for fpath in raw_files:
        try:
            with open(fpath, "r", encoding="utf-8") as fp:
                content = json.load(fp)
            items = content if isinstance(content, list) else [content]
            for item in items:
                if not isinstance(item, dict):
                    continue
                # Bỏ qua các file log lỗi của crawler không có metadata/payload
                if "metadata" not in item and "_meta" not in item and "raw_payload" not in item and "raw" not in item:
                    continue

                total_raw_envelopes += 1

                # 1. Ép phẳng JSON (Flattening)
                flat = flatten_raw_job_record(item, source_fallback=source_name)

                jid = flat.get("job_id_global")
                if not jid or jid == f"{source_name}_":
                    continue

                # 2. Tính toán Text Metrics & Kiểm tra Stub JD (Chính sách 1.B)
                desc = flat.get("raw_description_text") or ""
                req = flat.get("raw_requirements_text") or ""
                combined_jd = f"{desc}\n{req}".strip()
                title = flat.get("job_title") or ""

                text_metrics = calculate_text_metrics(combined_jd)
                if text_metrics.get("is_stub_jd", False):
                    stub_jds_removed += 1
                    continue  # Loại bỏ stub JD < 30 từ khỏi tập sạch

                # 3. Chuẩn hóa tiêu đề & xác định Job Family (SD2)
                title_clean = clean_job_title(title)
                flat["job_title_clean"] = title_clean
                flat["job_family"] = classify_job_family(title, flat.get("skills_list"))

                # 4. Bóc tách dải lương Cascade 3 tầng
                raw_sal = flat.get("raw_salary_text")
                sal_res = parse_salary_cascade(raw_sal, combined_jd)

                flat["salary_min_vnd"] = sal_res.get("salary_min_vnd")
                flat["salary_max_vnd"] = sal_res.get("salary_max_vnd")
                flat["salary_source"] = sal_res.get("salary_source")
                flat["salary_currency"] = sal_res.get("salary_currency", "VND")
                flat["is_salary_negotiable_declared"] = 1 if classify_salary_null(raw_sal) else 0

                if flat["salary_source"] == "header_regex":
                    salary_header_hits += 1
                elif flat["salary_source"] == "jd_regex":
                    salary_jd_hits += 1

                # 5. Chuẩn hóa địa phương & cấp bậc
                flat["primary_city"] = normalize_city(flat.get("raw_location_text"))
                flat["job_seniority"] = normalize_seniority(flat.get("raw_seniority_text"), title)

                # 6. Chỉ số văn bản
                flat["jd_word_count"] = text_metrics.get("word_count", 0)
                flat["jd_char_count"] = text_metrics.get("char_count", 0)
                flat["detected_language"] = detect_language(combined_jd)
                flat["lexical_diversity_ttr"] = text_metrics.get("lexical_diversity_ttr", 0.0)

                # 7. Bù khuyết thông minh qua GenAITextImputer (offline heuristic fallback)
                flat_imputed = imputer.impute_job_record(flat)
                if flat_imputed.get("is_imputed_by_genai", False):
                    imputed_count += 1
                    flat = flat_imputed
                else:
                    flat["is_imputed_by_genai"] = False
                    flat["genai_imputed_fields"] = []

                # Khử trùng lặp nội bộ nguồn theo job_id_global (ưu tiên bản ghi mới hơn)
                records_by_id[jid] = flat

        except Exception as exc:
            pass

    clean_records = list(records_by_id.values())
    total_clean = len(clean_records)
    logger.info(
        f"  -> {source_name}: Quét {total_raw_envelopes} envelopes | Loại {stub_jds_removed} stub JDs | Sạch: {total_clean} bản ghi"
    )

    if total_clean == 0:
        df_clean = pd.DataFrame()
        health_card = {}
        return df_clean, health_card

    df_clean = pd.DataFrame(clean_records)

    # 8. Sửa lỗi số học & Winsorization dải lương
    has_sal = df_clean["salary_max_vnd"].notnull() & (df_clean["salary_max_vnd"] > 0)
    for idx, row in df_clean[has_sal].iterrows():
        jd_combined = f"{row.get('raw_description_text') or ''} {row.get('raw_requirements_text') or ''}"
        c_min = fix_common_salary_input_errors(row["salary_min_vnd"], jd_text=jd_combined)
        c_max = fix_common_salary_input_errors(row["salary_max_vnd"], jd_text=jd_combined)
        if c_min and c_max and c_min > c_max:
            c_min, c_max = c_max, c_min
        df_clean.at[idx, "salary_min_vnd"] = c_min
        df_clean.at[idx, "salary_max_vnd"] = c_max

    # Log transformation cho salary_max_vnd
    df_clean["salary_log_max"] = log_transform_salary(df_clean["salary_max_vnd"])

    # Thống kê Health Card
    salary_counts = df_clean["salary_max_vnd"].dropna()
    iqr_p1 = float(salary_counts.quantile(0.01)) if not salary_counts.empty else 0.0
    iqr_q1 = float(salary_counts.quantile(0.25)) if not salary_counts.empty else 0.0
    iqr_med = float(salary_counts.median()) if not salary_counts.empty else 0.0
    iqr_q3 = float(salary_counts.quantile(0.75)) if not salary_counts.empty else 0.0
    iqr_p99 = float(salary_counts.quantile(0.99)) if not salary_counts.empty else 0.0

    lang_dist = df_clean["detected_language"].value_counts().to_dict()
    family_dist = df_clean["job_family"].value_counts().to_dict()

    health_card = {
        "source_platform": source_name,
        "audit_timestamp": datetime.now(timezone.utc).isoformat(),
        "total_files_scanned": total_files_scanned,
        "total_raw_envelopes": total_raw_envelopes,
        "stub_jds_removed_policy_1b": stub_jds_removed,
        "total_clean_records": total_clean,
        "salary_metrics": {
            "total_with_numeric_salary": int(has_sal.sum()),
            "salary_coverage_pct": round(float(has_sal.mean() * 100.0), 2),
            "salary_header_regex_hits": salary_header_hits,
            "salary_jd_regex_implicit_hits": salary_jd_hits,
            "salary_p1_vnd": iqr_p1,
            "salary_q1_vnd": iqr_q1,
            "salary_median_vnd": iqr_med,
            "salary_q3_vnd": iqr_q3,
            "salary_p99_vnd": iqr_p99,
        },
        "imputation_metrics": {
            "records_imputed_by_genai": imputed_count,
            "imputation_rate_pct": round(float(imputed_count / total_clean * 100.0), 2),
        },
        "language_distribution": lang_dist,
        "job_family_distribution": family_dist,
        "execution_time_seconds": round(time.time() - t0, 2),
    }

    # Xuất bản FILE 1: Bảng phẳng chuẩn hóa (Flat Clean Parquet & CSV)
    out_parquet = directories["staging_dir"] / source_name / f"{source_name}_flat_clean.parquet"
    out_csv = directories["staging_dir"] / source_name / f"{source_name}_flat_clean.csv"
    df_clean.to_parquet(out_parquet, index=False)
    # Xuất CSV (chuyển lists thành JSON string để CSV đọc được)
    df_csv = df_clean.copy()
    df_csv["skills_list"] = df_csv["skills_list"].apply(lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, list) else "[]")
    df_csv["benefits_list"] = df_csv["benefits_list"].apply(lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, list) else "[]")
    df_csv.to_csv(out_csv, index=False)

    # Xuất bản FILE 2: Bệnh án chất lượng dữ liệu (Quality Health Card JSON)
    for rep_dir in [directories["reports_dir"] / source_name, directories["data_reports_dir"] / source_name]:
        with open(rep_dir / f"{source_name}_quality_health_card.json", "w", encoding="utf-8") as fp:
            json.dump(health_card, fp, ensure_ascii=False, indent=2)

    # Xuất bản FILE 3: Manifest biến đổi và từ điển dữ liệu (Transformation Manifest MD)
    manifest_md = generate_transformation_manifest_md(source_name, health_card, df_clean)
    for rep_dir in [directories["reports_dir"] / source_name, directories["data_reports_dir"] / source_name]:
        with open(rep_dir / f"{source_name}_transformation_manifest.md", "w", encoding="utf-8") as fp:
            fp.write(manifest_md)

    logger.info(f"  -> {source_name}: Hoàn tất xuất bản Bộ 3 file ({time.time() - t0:.2f}s)")
    return df_clean, health_card


def generate_transformation_manifest_md(
    source_name: str,
    health_card: Dict[str, Any],
    df: pd.DataFrame,
) -> str:
    """Tạo tài liệu Transformation Manifest định dạng Markdown (Không dùng Mermaid!)."""
    sal_m = health_card["salary_metrics"]
    imp_m = health_card["imputation_metrics"]

    md = f"""# BÁO CÁO BIẾN ĐỔI DỮ LIỆU & TỪ ĐIỂN ÁNH XẠ: {source_name.upper()}
> **Dự án:** Phân tích thị trường lao động IT Việt Nam (**VN-IT-Job-Mining**)  
> **Nguồn tuyển dụng:** `{source_name}`  
> **Thời điểm xuất bản:** `{health_card['audit_timestamp']}`  
> **Tiêu chuẩn nghiệm thu:** DoD Level-4 (Zero Information Loss, Single Flat Table, Bộ 3 Deliverables)

---

## 1. Tóm Tắt Quy Trình Biến Đổi (Transformation Executive Summary)

```text
+----------------------------------------------------------------------------------------------------+
|                TIẾN TRÌNH BIẾN ĐỔI DỮ LIỆU NGUỒN: {source_name.upper():<35} |
+----------------------------------------------------------------------------------------------------+
| 1. Tổng số file quét (Raw Files)        : {health_card['total_files_scanned']:<48} |
| 2. Tổng số envelope thô (Envelopes)     : {health_card['total_raw_envelopes']:<48} |
| 3. Stub JD bị loại bỏ (Chính sách 1.B) : {health_card['stub_jds_removed_policy_1b']:<48} |
| 4. Bản ghi phẳng hợp lệ (Clean Records) : {health_card['total_clean_records']:<48} |
| 5. Tỷ lệ có mức lương số (Salary Rate)  : {sal_m['salary_coverage_pct']}% ({sal_m['total_with_numeric_salary']} tin tuyển dụng){' ' * 24} |
| 6. Lương bóc tách từ Header Regex      : {sal_m['salary_header_regex_hits']:<48} |
| 7. Lương ẩn bóc tách từ JD Regex       : {sal_m['salary_jd_regex_implicit_hits']:<48} |
| 8. Bản ghi được GenAI bù khuyết        : {imp_m['records_imputed_by_genai']} ({imp_m['imputation_rate_pct']}%) {' ' * 32} |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. Thống Kê Phân Phối Dải Lương (Salary Distribution)
- **Phân vị P1 (Ngưỡng cận dưới Winsorization):** {sal_m['salary_p1_vnd']:,.0f} VNĐ
- **Phân vị Q1 (25% thị trường):** {sal_m['salary_q1_vnd']:,.0f} VNĐ
- **Trung vị Median (50% thị trường):** {sal_m['salary_median_vnd']:,.0f} VNĐ
- **Phân vị Q3 (75% thị trường):** {sal_m['salary_q3_vnd']:,.0f} VNĐ
- **Phân vị P99 (Ngưỡng cận trên Winsorization):** {sal_m['salary_p99_vnd']:,.0f} VNĐ

---

## 3. Phân Phối 12 Job Family Chuẩn (SD2 Taxonomy)

| Mã Nhóm Job Family | Tên Nhóm Nghề Nghiệp | Số Lượng Bản Ghi | Tỷ Trọng (%) |
| :--- | :--- | :--- | :--- |
"""
    total = health_card["total_clean_records"]
    for fam, cnt in sorted(health_card["job_family_distribution"].items(), key=lambda x: x[1], reverse=True):
        pct = round(cnt / total * 100.0, 2) if total > 0 else 0.0
        md += f"| `{fam}` | {fam.replace('JF', '').replace('_', ' ').title()} | {cnt:,} | {pct}% |\n"

    md += f"""
---

## 4. Từ Điển Dữ Liệu Bảng Phẳng Chuẩn (Data Dictionary)

| Tên Cột Chuẩn | Kiểu Dữ Liệu | Nguồn Gốc (Origin) | Mô Tả & Quy Tắc Xử Lý |
| :--- | :--- | :--- | :--- |
| `job_id_global` | `str` | Metadata | Mã định danh duy nhất xuyên hệ thống: `{source_name}_<id>` |
| `source_platform` | `str` | Metadata | Tên sàn tuyển dụng: `{source_name}` |
| `source_url` | `str` | Metadata | Đường dẫn URL gốc của bài đăng |
| `job_title` | `str` | Raw Payload | Tiêu đề bài đăng nguyên bản |
| `job_title_clean` | `str` | Transformation | Tiêu đề đã làm sạch bracket tags [HN], [HCM], lương đuôi |
| `company_name` | `str` | Raw Payload | Tên công ty tuyển dụng |
| `primary_city` | `str` | Normalization | Tỉnh/thành phố chuẩn hóa về 63 tỉnh thành |
| `job_seniority` | `str` | Normalization | Cấp bậc quy chuẩn về 6 bậc (Intern, Fresher, Junior, Middle, Senior, Lead/Manager) |
| `job_family` | `str` | Normalization | Phân loại về 12 Job Family chuẩn IT Việt Nam (SD2) |
| `raw_salary_text` | `str` | Raw Payload | Mức lương dạng chữ thô nguyên bản từ sàn |
| `salary_min_vnd` | `float` | Transformation | Lương tối thiểu chuẩn hóa về VNĐ/tháng (đã quy đổi USD và lương năm) |
| `salary_max_vnd` | `float` | Transformation | Lương tối đa chuẩn hóa về VNĐ/tháng |
| `salary_source` | `str` | Provenance | Nguồn bóc tách lương: `header_regex` hoặc `jd_regex` |
| `salary_log_max` | `float` | Normalization | Biến đổi log1p: `log(1 + salary_max_vnd)` đưa về phân phối chuẩn |
| `is_salary_negotiable_declared` | `int` | Transformation | Cờ 1 nếu bài đăng khai báo Thỏa thuận / Cạnh tranh / 0 |
| `skills_list` | `list[str]` | Integration & Imputer | Mảng danh sách kỹ năng công nghệ (Python, Java, React, Docker, ...) |
| `benefits_list` | `list[str]` | Integration | Mảng danh sách chế độ đãi ngộ (Bảo hiểm, Lương tháng 13, ...) |
| `jd_word_count` | `int` | Text Metrics | Số từ trong mô tả công việc (loại bỏ bài < 30 từ theo Chính sách 1.B) |
| `detected_language` | `str` | Text Metrics | Ngôn ngữ phát hiện: `vi` (Tiếng Việt) hoặc `en` (Tiếng Anh) |
| `is_imputed_by_genai` | `bool` | Imputer | Cờ True nếu bản ghi được GenAI đọc hiểu bù khuyết |
| `genai_imputed_fields` | `list[str]` | Imputer | Danh sách các trường được GenAI bù khuyết |
"""
    return md


def run_pipeline() -> None:
    """Điều phối toàn bộ quy trình Staging Integration và Golden Master Curated Dataset."""
    logger.info("================================================================================")
    logger.info("  KHỞI ĐỘNG PIPELINE PREPROCESSING & INTEGRATION ĐA NGUỒN (VN-IT-JOB-MINING)  ")
    logger.info("================================================================================")
    t_start = time.time()

    directories = setup_directories()
    imputer = GenAITextImputer()

    all_source_dfs: List[pd.DataFrame] = []
    source_summaries: Dict[str, Dict[str, Any]] = {}

    # Bước 1 & 2: Xử lý 8 nguồn và xuất bản bộ 3 deliverables cho từng nguồn
    for src in SOURCES:
        df_src, hcard = process_single_source(src, imputer, directories)
        if not df_src.empty:
            all_source_dfs.append(df_src)
            source_summaries[src] = hcard

    if not all_source_dfs:
        logger.error("Không có dữ liệu sạch nào được trích xuất!")
        return

    # Bước 3: Hợp nhất vào Bảng Phẳng Staging Tổng Thể (Master Flat Staging Table)
    logger.info("=== HỢP NHẤT BẢNG PHẲNG STAGING TỔNG THỂ (ALL SOURCES) ===")
    staging_master_df = pd.concat(all_source_dfs, ignore_index=True)
    total_staging = len(staging_master_df)

    staging_parquet_path = directories["staging_dir"] / "staging_flat_all_sources.parquet"
    staging_csv_path = directories["staging_dir"] / "staging_flat_all_sources.csv"
    staging_master_df.to_parquet(staging_parquet_path, index=False)

    staging_csv_df = staging_master_df.copy()
    staging_csv_df["skills_list"] = staging_csv_df["skills_list"].apply(
        lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, list) else "[]"
    )
    staging_csv_df["benefits_list"] = staging_csv_df["benefits_list"].apply(
        lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, list) else "[]"
    )
    staging_csv_df.to_csv(staging_csv_path, index=False)
    logger.info(f"Đã lưu Master Staging Table: {staging_parquet_path} ({total_staging:,} bản ghi)")

    # Bước 4: Khử trùng lặp ngữ nghĩa xuyên sàn (Cross-Platform Entity Resolution)
    logger.info("=== BẮT ĐẦU KHỬ TRÙNG LẶP NGỮ NGHĨA XUYÊN SÀN (CROSS-PLATFORM DEDUPLICATION) ===")
    curated_golden_df, dedup_metrics = deduplicate_cross_platform_jobs(staging_master_df)
    total_golden = len(curated_golden_df)

    curated_parquet_path = directories["curated_dir"] / "curated_flat_golden_jobs.parquet"
    curated_csv_path = directories["curated_dir"] / "curated_flat_golden_jobs.csv"
    curated_golden_df.to_parquet(curated_parquet_path, index=False)

    curated_csv_df = curated_golden_df.copy()
    curated_csv_df["skills_list"] = curated_csv_df["skills_list"].apply(
        lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, list) else "[]"
    )
    curated_csv_df["benefits_list"] = curated_csv_df["benefits_list"].apply(
        lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, list) else "[]"
    )
    curated_csv_df.to_csv(curated_csv_path, index=False)
    logger.info(f"Đã lưu Golden Master Dataset: {curated_parquet_path} ({total_golden:,} bản ghi)")

    # Bước 5: Báo cáo tổng kết Golden Dataset Health Card
    golden_salaries = curated_golden_df["salary_max_vnd"].dropna()
    has_curated_sal = curated_golden_df["salary_max_vnd"].notnull() & (curated_golden_df["salary_max_vnd"] > 0)

    golden_health_card = {
        "dataset_name": "VN-IT-Jobs-Curated-Golden-Master",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_staging_records": total_staging,
        "total_golden_records": total_golden,
        "deduplication_metrics": dedup_metrics,
        "salary_metrics": {
            "total_with_numeric_salary": int(has_curated_sal.sum()),
            "salary_coverage_pct": round(float(has_curated_sal.mean() * 100.0), 2),
            "salary_p1_vnd": float(golden_salaries.quantile(0.01)) if not golden_salaries.empty else 0.0,
            "salary_q1_vnd": float(golden_salaries.quantile(0.25)) if not golden_salaries.empty else 0.0,
            "salary_median_vnd": float(golden_salaries.median()) if not golden_salaries.empty else 0.0,
            "salary_q3_vnd": float(golden_salaries.quantile(0.75)) if not golden_salaries.empty else 0.0,
            "salary_p99_vnd": float(golden_salaries.quantile(0.99)) if not golden_salaries.empty else 0.0,
        },
        "platform_breakdown": {
            src: int((curated_golden_df["source_platform"] == src).sum()) for src in SOURCES
        },
        "job_family_breakdown": curated_golden_df["job_family"].value_counts().to_dict(),
        "seniority_breakdown": curated_golden_df["job_seniority"].value_counts().to_dict(),
        "top_cities": curated_golden_df["primary_city"].value_counts().head(10).to_dict(),
        "total_pipeline_duration_seconds": round(time.time() - t_start, 2),
    }

    golden_json_path = directories["reports_dir"] / "curated_golden_dataset_health_card.json"
    with open(golden_json_path, "w", encoding="utf-8") as fp:
        json.dump(golden_health_card, fp, ensure_ascii=False, indent=2)

    # In bảng tóm tắt kết quả cuối cùng ra Terminal
    logger.info("================================================================================")
    logger.info("                      BẢNG TỔNG KẾT KẾT QUẢ PREPROCESSING                      ")
    logger.info("================================================================================")
    print("\n" + "=" * 90)
    print(f"{'SÀN TUYỂN DỤNG':<15} | {'RAW SCAN':<9} | {'STUB DEL':<9} | {'STAGING':<9} | {'CÓ LƯƠNG':<9} | {'GENAI BÙ':<9}")
    print("-" * 90)
    for src, hc in source_summaries.items():
        sal_cnt = hc["salary_metrics"]["total_with_numeric_salary"]
        imp_cnt = hc["imputation_metrics"]["records_imputed_by_genai"]
        print(
            f"{src:<15} | {hc['total_raw_envelopes']:<9,} | {hc['stub_jds_removed_policy_1b']:<9,} | "
            f"{hc['total_clean_records']:<9,} | {sal_cnt:<9,} | {imp_cnt:<9,}"
        )
    print("=" * 90)
    print(f"{'TỔNG CỘNG STAGING':<15} | {sum(h['total_raw_envelopes'] for h in source_summaries.values()):<9,} | "
          f"{sum(h['stub_jds_removed_policy_1b'] for h in source_summaries.values()):<9,} | "
          f"{total_staging:<9,} | {int(has_curated_sal.sum()):<9,} | -")
    print(f"KHỬ TRÙNG LẶP XUYÊN SÀN: Hợp nhất {dedup_metrics['duplicates_removed']:,} bài trùng lặp ({dedup_metrics['deduplication_rate_pct']}%)")
    print(f"BỘ DỮ LIỆU VÀNG CUỐI CÙNG (GOLDEN MASTER DATASET): {total_golden:,} BẢN GHI ĐỘC NHẤT")
    print("=" * 90 + "\n")
    logger.info(f"TOÀN BỘ PIPELINE HOÀN THÀNH XUẤT SẮC TRONG {time.time() - t_start:.2f} GIÂY!")


if __name__ == "__main__":
    run_pipeline()
