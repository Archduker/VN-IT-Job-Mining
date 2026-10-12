#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts.run_preclean
~~~~~~~~~~~~~~~~~~~~~~~
Script chạy Pipeline Sơ chế (PreClean), Lọc Mẫu Dị Biệt và Hợp Nhất Đa Nguồn.

Sử dụng:
    python scripts/run_preclean.py
    python scripts/run_preclean.py --source topcv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crawlers.preprocessing.preClean.pipeline import PreCleanPipeline


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Chạy Pipeline Sơ chế (preClean) và Hợp nhất dữ liệu tuyển dụng phục vụ EDA."
    )
    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="Chỉ định nguồn cụ thể (mặc định: tất cả nguồn)",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data",
        help="Thư mục chứa dữ liệu thô (mặc định: 'data')",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/processed/preClean",
        help="Thư mục lưu dataset sạch (mặc định: 'data/processed/preClean')",
    )
    parser.add_argument(
        "--queue-dir",
        type=str,
        default="data/queue",
        help="Thư mục lưu hàng đợi cào lại (mặc định: 'data/queue')",
    )

    args = parser.parse_args()

    print("=== KHỞI ĐỘNG PIPELINE SƠ CHẾ & HỢP NHẤT DỮ LIỆU (PRECLEAN) ===")
    pipeline = PreCleanPipeline(
        data_dir=args.data_dir,
        output_clean_dir=args.output_dir,
        queue_dir=args.queue_dir,
    )

    result = pipeline.run(source=args.source)

    print("\n=== KẾT QUẢ SƠ CHẾ & HỢP NHẤT ===")
    print(f"  Tổng số bản ghi xử lý  : {result['total_processed']:,}")
    print(f"  Số bản ghi SẠCH (EDA)   : {result['cleaned_count']:,} -> {result['clean_file']}")
    print(f"  Số bản ghi DỊ BIỆT/LỖI  : {result['corrupted_count']:,} -> {result['corrupted_queue_file']}")

    print("\n  Chi tiết theo từng nguồn:")
    for src, st in sorted(result["stats_by_source"].items()):
        print(f"    - {src:15}: Tổng {st['total']:5} | Sạch {st['cleaned']:5} | Dị biệt {st['corrupted']:4}")

    print("\n=== PIPELINE HOÀN TẤT THÀNH CÔNG ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
