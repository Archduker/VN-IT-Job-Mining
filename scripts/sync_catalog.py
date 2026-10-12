#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts.sync_catalog
~~~~~~~~~~~~~~~~~~~~~~
Đồng bộ hóa các file batch đã cào trên đĩa vào JobStateCatalog (SQLite).
Đánh dấu tất cả các job đã có thành trạng thái SUCCESS để Airflow không cào lại.

Sử dụng:
    python scripts/sync_catalog.py
    python scripts/sync_catalog.py --source topcv
    python scripts/sync_catalog.py --data-dir data
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crawlers.common.job_catalog import JobStateCatalog


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Đồng bộ hóa dữ liệu đã cào vào JobStateCatalog với trạng thái SUCCESS."
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
        help="Thư mục chứa dữ liệu cào (mặc định: 'data')",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Đường dẫn file database Catalog (mặc định: 'data/state/job_catalog.db')",
    )

    args = parser.parse_args()

    print(f"=== KHỞI ĐỘNG ĐỒNG BỘ STATE CATALOG (DATA -> SQLITE) ===")
    print(f"  Thư mục dữ liệu: {args.data_dir}")
    print(f"  Nguồn mục tiêu  : {args.source or 'TOÀN BỘ'}")

    catalog = JobStateCatalog(db_path=args.db_path)
    before_stats = catalog.get_catalog_stats(args.source)
    print(f"\n[TRƯỚC ĐỒNG BỘ] Total: {before_stats['total']}, Success: {before_stats['success']}, Failed Retry: {before_stats['failed_retry']}")

    result = catalog.sync_from_batches(data_dir=args.data_dir, source=args.source)

    print(f"\n[KẾT QUẢ ĐỒNG BỘ]")
    print(f"  Số files đã duyệt : {result['files_scanned']}")
    print(f"  Số jobs đã nạp    : {result['total_synced']}")
    for src, count in sorted(result["by_source"].items()):
        print(f"    - {src:15}: {count:5} jobs -> SUCCESS")

    after_stats = catalog.get_catalog_stats(args.source)
    print(f"\n[SAU ĐỒNG BỘ] Total: {after_stats['total']}, Success: {after_stats['success']}, Failed Retry: {after_stats['failed_retry']}")
    print("=== ĐỒNG BỘ HOÀN TẤT THÀNH CÔNG ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
