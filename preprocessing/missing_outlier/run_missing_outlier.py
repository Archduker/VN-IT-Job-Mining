# -*- coding: utf-8 -*-
"""preprocessing.missing_outlier.run_missing_outlier
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Runner điều phối toàn diện Bước 3 (Missing Values & Outliers Handling).

Quy trình chuẩn mực (100% PURE JSON):
  1. Nạp 9,824 bản ghi từ: `data/transformation/raw_for_outlier.json`.
  2. Bóc trần các Null Markers trá hình qua `sneaky_null_detector.py`.
  3. Khử bẫy lương ảo (SĐT, masked salary, dot glitch) qua `outlier_handler.py`.
  4. Bù khuyết Tầng 1 (Heuristic Extractor) cho số năm kinh nghiệm, cấp bậc, kỹ năng.
  5. Sửa lỗi số học R1-R3 và Winsorization P1-P99 theo từng sàn qua `outlier_handler.apply_outlier_pipeline()`.
  6. Kiểm định 5 luật chất lượng QR1-QR5 & tính `quality_score` qua `quality_rules.compute_quality_score()`.
  7. Xuất bản tệp dữ liệu chuẩn: `data/missing_outlier/raw_for_normalization.json` (100% PURE JSON).
  8. Bảo toàn 100% số lượng 9,824 bản ghi (Zero Record Loss Policy).
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from preprocessing.missing_outlier.genai_text_imputer import GenAITextImputer  # noqa: E402
from preprocessing.missing_outlier.outlier_handler import (  # noqa: E402
    apply_outlier_pipeline,
    clean_and_repair_salary_record,
    detect_iqr_outliers,
)
from preprocessing.missing_outlier.quality_rules import (  # noqa: E402
    compute_quality_score,
    summarize_quality,
)
from preprocessing.missing_outlier.sneaky_null_detector import is_val_null  # noqa: E402

logger = logging.getLogger("missing_outlier_runner")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

SOURCES = (
    "careerviet",
    "glints",
    "itviec",
    "jobsgo",
    "topcv",
    "topdev",
    "vieclam24h",
    "vietnamworks",
)


def clean_nans_to_none(obj: Any) -> Any:
    """Đệ quy chuyển đổi float('nan') thành None để serialize thành null chuẩn RFC 8259."""
    if isinstance(obj, float):
        return None if math.isnan(obj) else obj
    if isinstance(obj, dict):
        return {k: clean_nans_to_none(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean_nans_to_none(x) for x in obj]
    return obj


def _write_pure_json(path: Path, data: Any) -> None:
    """Lưu trữ tệp 100% PURE JSON chuẩn RFC 8259, không bao giờ tạo parquet/csv."""
    path.parent.mkdir(parents=True, exist_ok=True)
    cleaned = clean_nans_to_none(data)
    with path.open("w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2, allow_nan=False)


def run_missing_outlier_pipeline(
    input_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    reports_dir: Optional[Path] = None,
    team_approved: bool = False,
) -> Dict[str, Any]:
    start_time = time.perf_counter()

    # Nhận diện đường dẫn đầu vào (ưu tiên raw_for_outlier.json)
    if input_path:
        input_file = input_path
    else:
        candidate_primary = PROJECT_ROOT / "data" / "transformation" / "raw_for_outlier.json"
        candidate_legacy = PROJECT_ROOT / "data" / "transformation" / "transformed_flat_all_sources.json"
        input_file = candidate_primary if candidate_primary.is_file() else candidate_legacy

    missing_outlier_dir = PROJECT_ROOT / "data" / "missing_outlier"
    staging_dir = PROJECT_ROOT / "data" / "staging"
    rep_dir = reports_dir or PROJECT_ROOT / "reports" / "missing_outlier"
    gov_dir = PROJECT_ROOT / "reports" / "ai_governance"
    quality_rep_dir = PROJECT_ROOT / "reports" / "quality"

    missing_outlier_dir.mkdir(parents=True, exist_ok=True)
    staging_dir.mkdir(parents=True, exist_ok=True)
    rep_dir.mkdir(parents=True, exist_ok=True)
    gov_dir.mkdir(parents=True, exist_ok=True)
    quality_rep_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Bắt đầu thực thi Bước 3: Missing & Outlier Pipeline (100%% PURE JSON)...")
    logger.info("Đọc dữ liệu chuyển hóa từ: %s", input_file)

    if not input_file.is_file():
        raise FileNotFoundError(f"Không tìm thấy file đầu vào: {input_file}")

    with input_file.open("r", encoding="utf-8") as f:
        records = json.load(f)

    total_records = len(records)
    logger.info("Tổng số bản ghi nạp vào: %d", total_records)

    imputer = GenAITextImputer(team_approved=team_approved)

    cleaned_records: List[Dict[str, Any]] = []
    stats = {
        "sneaky_nulls_unmasked": 0,
        "masked_salaries_scrubbed": 0,
        "phone_salaries_scrubbed": 0,
        "dot_glitches_repaired": 0,
        "experience_imputed_heuristic": 0,
        "seniority_imputed_heuristic": 0,
        "skills_imputed_heuristic": 0,
    }

    # Xuất báo cáo Pilot Benchmark cho Quản trị AI
    imputer.generate_pilot_benchmark(
        records,
        sample_size=20,
        output_path=gov_dir / "pilot_gemini_imputation_benchmark.md",
    )

    for r in records:
        rec = dict(r)

        # 1. Bóc trần sneaky nulls ở các trường chuỗi
        for field in ("primary_city", "standardized_seniority", "company_scale_tier", "employment_type"):
            val = rec.get(field)
            if is_val_null(val):
                rec[field] = None
                stats["sneaky_nulls_unmasked"] += 1

        # 2. Khử bẫy lương ảo & sửa lỗi dấu chấm phần nghìn
        old_max = rec.get("salary_max_vnd")
        rec = clean_and_repair_salary_record(rec)

        if rec.get("salary_source") == "masked_negotiable":
            stats["masked_salaries_scrubbed"] += 1
        elif str(rec.get("salary_source", "")).startswith("scrubbed_false_positive"):
            stats["phone_salaries_scrubbed"] += 1
        elif old_max and rec.get("salary_max_vnd") and rec["salary_max_vnd"] == old_max * 1000:
            stats["dot_glitches_repaired"] += 1

        # 3. Bù khuyết Tầng 1 (Heuristic)
        had_exp = rec.get("min_experience_years") is not None
        had_sen = bool(rec.get("standardized_seniority"))
        had_skills = bool(rec.get("skills_list"))

        rec = imputer.impute_job_record(rec)

        if not had_exp and rec.get("min_experience_years") is not None:
            stats["experience_imputed_heuristic"] += 1
        if not had_sen and rec.get("standardized_seniority"):
            stats["seniority_imputed_heuristic"] += 1
        if not had_skills and rec.get("skills_list"):
            stats["skills_imputed_heuristic"] += 1

        cleaned_records.append(rec)

    # 4. Áp dụng toàn trình Outlier Pipeline của Tài (R1-R3, IQR, Winsorize P1-P99 per-source)
    df = pd.DataFrame(cleaned_records)
    df_outlier, outlier_stats = apply_outlier_pipeline(
        df,
        salary_cols=("salary_min_vnd", "salary_max_vnd"),
        experience_col="min_experience_years",
        source_col="source_platform",
        lower_pct=0.01,
        upper_pct=0.99,
    )

    # 5. Áp dụng 5 Luật Chất Lượng QR1-QR5 & Tính quality_score của Tài
    df_scored = compute_quality_score(df_outlier)
    quality_summary = summarize_quality(df_scored)

    # Thống kê lương max winsorized phục vụ tương thích
    df_scored["salary_max_winsorized"] = df_scored["salary_max_vnd"]
    df_scored["is_salary_winsorized"] = df_scored["is_outlier_capped"]

    stats["salary_records_winsorized"] = int(df_scored["is_outlier_capped"].sum())
    stats["salary_fixes"] = outlier_stats.get("salary_fix_counts", {})
    stats["quality_summary"] = quality_summary

    final_records = df_scored.to_dict(orient="records")
    assert len(final_records) == total_records, "Vi phạm Zero Record Loss Policy!"

    # 6. Xuất bản 100% PURE JSON
    # File 2 chính thức theo đúng khế ước: raw_for_normalization.json
    raw_for_norm_path = missing_outlier_dir / "raw_for_normalization.json"
    legacy_staging_path = staging_dir / "staging_flat_all_sources.json"

    logger.info("Lưu trữ tệp chuẩn: %s", raw_for_norm_path)
    _write_pure_json(raw_for_norm_path, final_records)
    _write_pure_json(legacy_staging_path, final_records)

    # 7. Lưu trữ theo từng sàn (Per-source pure JSON)
    by_source = defaultdict(list)
    for r in final_records:
        by_source[r.get("source_platform", "unknown")].append(r)

    source_metrics = {}
    for s, recs in by_source.items():
        s_dir = missing_outlier_dir / s
        s_dir.mkdir(parents=True, exist_ok=True)
        s_file = s_dir / f"{s}_missing_outlier.json"
        _write_pure_json(s_file, recs)
        source_metrics[s] = {
            "total_records": len(recs),
            "output_file": str(s_file),
            "with_numeric_salary": sum(1 for x in recs if x.get("salary_max_vnd") is not None),
            "with_experience": sum(1 for x in recs if x.get("min_experience_years") is not None),
            "with_skills": sum(1 for x in recs if len(x.get("skills_list") or []) > 0),
            "outlier_capped_count": sum(1 for x in recs if x.get("is_outlier_capped")),
        }

    # 8. Xuất Bệnh Án Chất Lượng Dữ Liệu (Quality Health Card)
    duration = round(time.perf_counter() - start_time, 3)
    health_card = {
        "step": "step_3_missing_and_outlier",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_records_in": total_records,
        "total_records_out": len(final_records),
        "zero_record_loss_verified": True,
        "pure_json_only": True,
        "duration_seconds": duration,
        "ai_governance": {
            "team_approved": team_approved,
            "pilot_benchmark_path": str(gov_dir / "pilot_gemini_imputation_benchmark.md"),
            "heuristic_imputer_active": True,
            "genai_batch_called": False if not team_approved else True,
        },
        "scrubbing_and_cleaning_metrics": stats,
        "iqr_diagnostics": outlier_stats.get("iqr_diagnostics", {}),
        "quality_rules_summary": quality_summary,
        "sources": source_metrics,
        "master_output_files": {
            "raw_for_normalization": str(raw_for_norm_path),
            "legacy_staging_flat": str(legacy_staging_path),
        },
    }

    health_card_path = rep_dir / "master_missing_outlier_health_card.json"
    _write_pure_json(health_card_path, health_card)

    logger.info("=== HOÀN TẤT BƯỚC 3: MISSING & OUTLIER PIPELINE ===")
    logger.info("Output chính thức (File 2): %s", raw_for_norm_path)
    logger.info("Bệnh án chất lượng: %s", health_card_path)
    logger.info("Kinh nghiệm bù khuyết: %d bản ghi", stats["experience_imputed_heuristic"])
    logger.info("Lương được Winsorized P1-P99 per-source: %d bản ghi", stats["salary_records_winsorized"])
    logger.info("Điểm chất lượng trung bình (quality_score): %.3f", quality_summary.get("quality_score_mean", 0.0))

    return health_card


def main() -> None:
    parser = argparse.ArgumentParser(description="Chạy Step 3: Missing & Outlier Engine.")
    parser.add_argument(
        "--team-approved",
        action="store_true",
        default=False,
        help="Cờ phê duyệt từ User & Team để kích hoạt mô hình GenAI nếu cần.",
    )
    args = parser.parse_args()
    run_missing_outlier_pipeline(team_approved=args.team_approved)


if __name__ == "__main__":
    main()
