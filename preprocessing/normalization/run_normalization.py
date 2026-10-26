# -*- coding: utf-8 -*-
"""preprocessing.normalization.run_normalization
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Runner điều phối toàn diện Bước 4 (Normalization, Scaling & Cross-Platform Deduplication).

Quy trình chuẩn mực:
  1. Nạp dữ liệu Master Staging từ Bước 3: `data/staging/staging_flat_all_sources.json`.
  2. Chuẩn hóa thuộc tính danh mục (Categorical Standardization):
     - 63 Tỉnh/Thành phố Việt Nam (`primary_city`).
     - 6 Cấp bậc nghề nghiệp chuẩn (`standardized_seniority`).
     - 12 Job Family IT chuẩn (SD2) (`standardized_job_family`).
     - Làm sạch tiêu đề công việc (`cleaned_job_title`).
  3. Biến đổi phân phối số học Log-Transformation:
     - `log_salary_max = log(1 + salary_max_winsorized)` nén phân phối lệch phải.
     - Robust Scaling cho lương và số năm kinh nghiệm.
  4. Khử trùng lặp thực thể ngữ nghĩa xuyên sàn (Cross-Platform Entity Resolution):
     - Blocking (company + city) -> Jaccard Title & TF-IDF Cosine Similarity >= 0.82.
     - Hợp nhất hồ sơ Vàng (Golden Record Fusion) và bảo toàn vết truy xuất nguồn gốc.
  5. Xuất bản BỘ DỮ LIỆU VÀNG (GOLDEN MASTER DATASET):
     - `data/curated/curated_flat_golden_jobs.parquet` & `.csv`.
     - Xuất Bệnh án tổng thể tại `reports/curated_golden_dataset_health_card.json`.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from preprocessing.normalization.cross_deduplicator import deduplicate_cross_platform_jobs  # noqa: E402
from preprocessing.normalization.log_transformer import (  # noqa: E402
    log_transform_salary,
    robust_scale_series,
)
from preprocessing.normalization.text_cleaner import (  # noqa: E402
    classify_job_family,
    clean_job_title,
    normalize_city,
    normalize_seniority,
)

logger = logging.getLogger("normalization_runner")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


def run_normalization_pipeline(
    input_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    reports_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    start_time = time.perf_counter()
    input_file = input_path or PROJECT_ROOT / "data" / "staging" / "staging_flat_all_sources.json"
    out_dir = output_dir or PROJECT_ROOT / "data" / "curated"
    rep_dir = reports_dir or PROJECT_ROOT / "reports"

    out_dir.mkdir(parents=True, exist_ok=True)
    rep_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Bắt đầu thực thi Bước 4: Normalization & Deduplication Pipeline...")
    logger.info("Đọc dữ liệu Staging từ: %s", input_file)

    if not input_file.is_file():
        raise FileNotFoundError(f"Không tìm thấy dữ liệu Staging: {input_file}")

    with input_file.open("r", encoding="utf-8") as f:
        records = json.load(f)

    df = pd.DataFrame(records)
    total_staging_records = len(df)
    logger.info("Tổng số bản ghi Staging: %d", total_staging_records)

    # 1. Chuẩn hóa Categorical Fields
    logger.info("Chuẩn hóa các trường danh mục (City, Seniority, Job Title, 12 Job Families)...")
    df["cleaned_job_title"] = df["job_title"].apply(clean_job_title)
    df["primary_city"] = df["primary_city"].apply(normalize_city)
    df["standardized_seniority"] = df.apply(
        lambda r: normalize_seniority(r.get("standardized_seniority") or r.get("raw_seniority_text"), r.get("job_title")),
        axis=1,
    )
    df["standardized_job_family"] = df.apply(
        lambda r: classify_job_family(r.get("job_title"), r.get("skills_list")),
        axis=1,
    )

    # 2. Biến đổi phân phối số học Log-Transformation
    logger.info("Áp dụng Log-transformation y = log(1 + x) cho mức lương...")
    # Ưu tiên lấy salary_max_winsorized nếu có, fallback về salary_max_vnd
    base_salary = df["salary_max_winsorized"] if "salary_max_winsorized" in df.columns else df["salary_max_vnd"]
    df["log_salary_max"] = log_transform_salary(base_salary)
    df["salary_scaled_robust"] = robust_scale_series(base_salary)

    if "min_experience_years" in df.columns:
        df["experience_scaled_robust"] = robust_scale_series(df["min_experience_years"])

    # 3. Khử trùng lặp ngữ nghĩa xuyên sàn (Entity Resolution)
    logger.info("Thực hiện khử trùng lặp thực thể xuyên sàn (Blocking + Jaccard Title & TF-IDF JD Cosine)...")
    curated_df, dedup_metrics = deduplicate_cross_platform_jobs(
        df,
        title_sim_threshold=0.65,
        jd_sim_threshold=0.82,
    )

    logger.info("Khử trùng lặp thành công: %d bản ghi gốc -> %d bản ghi Vàng (Tỷ lệ trùng: %.2f%%)",
                dedup_metrics["total_input_records"],
                dedup_metrics["total_golden_records"],
                dedup_metrics["deduplication_rate_pct"])

    # 4. Lọc bỏ bài đăng rác siêu ngắn (Stub JD < 30 từ) theo Chính sách 1.B khi xuất bản bảng Vàng
    if "is_stub_jd" in curated_df.columns:
        valid_golden_df = curated_df[curated_df["is_stub_jd"] != True].copy()
        stub_removed = len(curated_df) - len(valid_golden_df)
        logger.info("Loại bỏ %d bài đăng rác siêu ngắn (Stub JD < 30 từ) khỏi bảng Vàng", stub_removed)
    else:
        valid_golden_df = curated_df.copy()
        stub_removed = 0

    # 5. Lưu trữ Bộ Dữ Liệu Vàng (Curated Golden Master)
    golden_parquet_out = out_dir / "curated_flat_golden_jobs.parquet"
    golden_csv_out = out_dir / "curated_flat_golden_jobs.csv"
    golden_json_out = out_dir / "curated_flat_golden_jobs.json"

    logger.info("Xuất bản Bộ Dữ Liệu Vàng tại: %s", out_dir)
    export_df = valid_golden_df.copy()

    # Chuẩn hóa kiểu dữ liệu cho Parquet/CSV
    for bool_col in ("is_negotiable", "is_salary_negotiable_declared", "is_stub_jd", "has_commission", "is_saturday_work", "is_golden_merged"):
        if bool_col in export_df.columns:
            export_df[bool_col] = export_df[bool_col].apply(lambda x: bool(x) if pd.notnull(x) else False).astype(bool)

    for col in export_df.columns:
        if export_df[col].apply(lambda x: isinstance(x, (list, dict))).any():
            export_df[col] = export_df[col].apply(lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, (list, dict)) else x)

    export_df.to_parquet(golden_parquet_out, index=False)
    export_df.to_csv(golden_csv_out, index=False, encoding="utf-8")

    # Lưu thêm JSON master cho hệ thống
    golden_records = valid_golden_df.to_dict(orient="records")
    with golden_json_out.open("w", encoding="utf-8") as f:
        json.dump(golden_records, f, ensure_ascii=False, indent=2)

    # 6. Đo lường phân bổ và Bệnh án Bộ Dữ Liệu Vàng
    duration = round(time.perf_counter() - start_time, 3)
    job_family_dist = dict(Counter(valid_golden_df["standardized_job_family"]).most_common())
    seniority_dist = dict(Counter(valid_golden_df["standardized_seniority"]).most_common())
    city_dist = dict(Counter(valid_golden_df["primary_city"]).most_common(10))

    health_card = {
        "dataset_name": "VN-IT-Job-Mining Curated Golden Master Dataset",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_staging_records_in": total_staging_records,
        "total_golden_records_out": len(valid_golden_df),
        "stub_jds_excluded_from_curated": stub_removed,
        "duration_seconds": duration,
        "cross_platform_deduplication": dedup_metrics,
        "distribution_metrics": {
            "skewness_raw_salary": round(float(df["salary_max_vnd"].dropna().skew()), 2) if len(df["salary_max_vnd"].dropna()) > 2 else 0.0,
            "skewness_log_salary": round(float(valid_golden_df["log_salary_max"].dropna().skew()), 2) if len(valid_golden_df["log_salary_max"].dropna()) > 2 else 0.0,
            "salary_coverage_pct": round(float(valid_golden_df["salary_max_vnd"].notnull().mean() * 100), 2),
            "experience_coverage_pct": round(float(valid_golden_df["min_experience_years"].notnull().mean() * 100), 2),
            "skills_coverage_pct": round(float(valid_golden_df["skills_list"].apply(lambda x: len(x) if isinstance(x, list) else 0).gt(0).mean() * 100), 2),
        },
        "taxonomies": {
            "top_job_families": job_family_dist,
            "seniority_distribution": seniority_dist,
            "top_10_cities": city_dist,
        },
        "output_files": {
            "parquet": str(golden_parquet_out),
            "csv": str(golden_csv_out),
            "json": str(golden_json_out),
        },
    }

    health_card_path = rep_dir / "curated_golden_dataset_health_card.json"
    with health_card_path.open("w", encoding="utf-8") as f:
        json.dump(health_card, f, ensure_ascii=False, indent=2)

    logger.info("=== HOÀN TẤT BƯỚC 4: NORMALIZATION & DEDUPLICATION PIPELINE ===")
    logger.info("Bệnh án Bộ Dữ Liệu Vàng: %s", health_card_path)
    logger.info("Số lượng bài đăng Vàng cuối cùng: %d", len(valid_golden_df))
    logger.info("Độ lệch Skewness mức lương: từ %.2f giảm xuống %.2f (Dạng chuẩn Bell-shaped)",
                health_card["distribution_metrics"]["skewness_raw_salary"],
                health_card["distribution_metrics"]["skewness_log_salary"])

    return health_card


def main() -> None:
    parser = argparse.ArgumentParser(description="Chạy Step 4: Normalization & Deduplication Engine.")
    args = parser.parse_args()
    run_normalization_pipeline()


if __name__ == "__main__":
    main()
