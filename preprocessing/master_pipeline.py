# -*- coding: utf-8 -*-
"""preprocessing.master_pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Master Pipeline Orchestrator for VN-IT-Job-Mining Data Preprocessing.

Chạy tuần tự toàn bộ 4 giai đoạn Tiền xử lý + 1 giai đoạn QA kiểm định chất lượng:
  1. Integration:      Ép phẳng JSON 8 sàn -> integrated_flat_all_sources.json
  2. Transformation:   Chuẩn hóa ngày/lương/số/text -> raw_for_outlier.json
  3. Missing/Outlier:  Xử lý null trá hình + Winsorization + QR1-QR5 -> raw_for_normalization.json
  4. Normalization:    Chuẩn hóa 10 nhóm + khử trùng xuyên sàn -> golden_master.json
  5. QA Checks:        Kiểm định 5 trụ cột chất lượng (RFC 8259, Lineage, Zero Raw, Domain Groups, QR1-QR5)

Sử dụng:
  python -m preprocessing.master_pipeline --all
  python -m preprocessing.master_pipeline --step integration
  python -m preprocessing.master_pipeline --step qa
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("MasterPipeline")


def run_stage_integration() -> int:
    logger.info("=== GIAI ĐOẠN 1: INTEGRATION (Tích hợp & Khảo sát 8 sàn) ===")
    from preprocessing.integration.run_integration import run_all_integration
    run_all_integration()
    return 0


def run_stage_transformation() -> int:
    logger.info("=== GIAI ĐOẠN 2: TRANSFORMATION (Chuyển đổi kiểu & Trích xuất lương/ngày) ===")
    from preprocessing.transformation.run_transformation import SOURCES, run_transformation
    res = run_transformation(SOURCES)
    return 0 if res else 1


def run_stage_missing_outlier() -> int:
    logger.info("=== GIAI ĐOẠN 3: MISSING VALUES & OUTLIER HANDLING (Xử lý khuyết & Ngoại lai) ===")
    from preprocessing.missing_outlier.run_missing_outlier import run_missing_outlier_pipeline
    res = run_missing_outlier_pipeline()
    return 0 if res else 1


def run_stage_gemini_enrichment(
    mock_mode: bool = False,
    limit: Optional[int] = None,
    force: bool = False,
    force_ai: bool = False,
) -> int:
    logger.info("=== GIAI ĐOẠN 4.5: GEMINI ALL-IN-ONE AGENT ENRICHMENT & GROUND-TRUTH NORMALIZATION ===")
    from preprocessing.missing_outlier.run_gemini_enrichment import run_enrichment_pipeline
    input_candidate = Path("data/curated/golden_master.json")
    if not input_candidate.exists():
        input_candidate = Path("data/missing_outlier/raw_for_normalization.json")

    res = run_enrichment_pipeline(
        input_file=str(input_candidate),
        checkpoint_file="data/staging/gemini_checkpoint.jsonl",
        golden_output="data/curated/golden_master.json",
        flat_output="data/curated/curated_flat_golden_jobs.json",
        mock_mode=mock_mode,
        limit=limit,
        force=force,
        force_ai=force_ai,
    )

    # Đồng bộ sang phân tầng Silver Dataset chuẩn Medallion
    silver_dir = PROJECT_ROOT / "data" / "silver"
    silver_dir.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copy2("data/curated/golden_master.json", silver_dir / "silver_master_dataset.json")
    shutil.copy2("data/curated/curated_flat_golden_jobs.json", silver_dir / "silver_flat_jobs.json")
    logger.info("Đã đồng bộ Silver Dataset chuẩn tại: %s", silver_dir)

    return 0 if res["errors_count"] == 0 else 1


def run_stage_normalization() -> int:
    logger.info("=== GIAI ĐOẠN 4: DEEP NORMALIZATION & DEDUPLICATION (Chuẩn hóa sâu 10 nhóm / 11 khóa) ===")
    from preprocessing.normalization.run_deep_normalization import run_deep_normalization
    res = run_deep_normalization()
    return 0 if res else 1


def run_stage_qa() -> int:
    logger.info("=== GIAI ĐOẠN 5: QA QUALITY AUDIT (Kiểm định chất lượng 5 trụ cột) ===")
    from preprocessing.qa.run_qa_checks import main as qa_main
    return qa_main([])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Master Pipeline Orchestrator cho VN-IT-Job-Mining Preprocessing."
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Chạy toàn bộ các bước từ Integration đến QA Quality Audit.",
    )
    parser.add_argument(
        "--step",
        choices=["integration", "transformation", "missing_outlier", "gemini_enrichment", "normalization", "qa"],
        help="Chạy một bước cụ thể.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Chạy Gemini Agent ở chế độ mock offline không cần API key.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Giới hạn số bản ghi xử lý trong Gemini Agent.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Chạy lại toàn bộ không bỏ qua checkpoint.",
    )
    parser.add_argument(
        "--force-ai",
        action="store_true",
        help="Ép buộc gọi Gemini API cho tất cả bản ghi (bỏ qua 2-Tier filter).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    start_time = time.perf_counter()

    if not args.all and not args.step:
        logger.info("Không có cờ chỉ định. Chạy mặc định toàn bộ pipeline (--all)...")
        args.all = True

    steps_to_run = []
    if args.all:
        steps_to_run = [
            ("integration", run_stage_integration),
            ("transformation", run_stage_transformation),
            ("missing_outlier", run_stage_missing_outlier),
            ("normalization", run_stage_normalization),
            ("gemini_enrichment", lambda: run_stage_gemini_enrichment(mock_mode=args.mock, limit=args.limit, force=args.force, force_ai=args.force_ai)),
            ("qa", run_stage_qa),
        ]
    else:
        step_map = {
            "integration": ("integration", run_stage_integration),
            "transformation": ("transformation", run_stage_transformation),
            "missing_outlier": ("missing_outlier", run_stage_missing_outlier),
            "normalization": ("normalization", run_stage_normalization),
            "gemini_enrichment": ("gemini_enrichment", lambda: run_stage_gemini_enrichment(mock_mode=args.mock, limit=args.limit, force=args.force, force_ai=args.force_ai)),
            "qa": ("qa", run_stage_qa),
        }
        steps_to_run = [step_map[args.step]]

    for step_name, step_fn in steps_to_run:
        step_start = time.perf_counter()
        logger.info("Bắt đầu thực thi: %s", step_name.upper())
        exit_code = step_fn()
        elapsed = time.perf_counter() - step_start
        if exit_code != 0:
            logger.error("Bước %s thất bại với mã lỗi %d! Dừng pipeline.", step_name, exit_code)
            return exit_code
        logger.info("Hoàn tất %s trong %.2f giây.\n", step_name.upper(), elapsed)

    total_elapsed = time.perf_counter() - start_time
    logger.info("==================================================================")
    logger.info("TOÀN BỘ PIPELINE ĐÃ HOÀN TẤT THÀNH CÔNG TRONG %.2f GIÂY!", total_elapsed)
    logger.info("Dữ liệu Silver Dataset đạt chuẩn đã sẵn sàng tại:")
    logger.info("  - Nested Master: data/silver/silver_master_dataset.json")
    logger.info("  - Flat View:     data/silver/silver_flat_jobs.json")
    logger.info("  - Curated Alias: data/curated/golden_master.json")
    logger.info("==================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
