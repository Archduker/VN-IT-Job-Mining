# -*- coding: utf-8 -*-
"""Báo cáo tiến độ thu thập dữ liệu tự động từ các nguồn IT Job.

Quét toàn bộ partition trong thư mục `data/` và in ra bảng tổng kết:
- Tên nguồn (Source)
- Số ngày đã thu thập (Dates)
- Tổng số tin (Total Jobs)
- Số tin duy nhất trong Checkpoint (Seen IDs)
- Trạng thái kiểm tra chất lượng (Data Quality)
"""

from __future__ import annotations

import glob
import json
import logging
import os
import sys
from pathlib import Path

# Thêm project root vào sys.path để chạy trực tiếp từ bất kỳ thư mục nào
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crawlers.common.data_quality import DataQualityChecker

# Giảm mức log của data_quality khi in bảng để không bị vỡ layout
dq_logger = logging.getLogger("data_quality")
dq_logger.setLevel(logging.ERROR)
for h in dq_logger.handlers:
    h.setLevel(logging.ERROR)


def generate_report(data_dir: str = "data") -> None:
    base = Path(data_dir)
    if not base.is_absolute():
        base = PROJECT_ROOT / data_dir
    if not base.exists():
        print(f"Directory {data_dir} does not exist.")
        return

    print("=" * 80)
    print("           BÁO CÁO TIẾN ĐỘ THU THẬP DỮ LIỆU VN-IT-JOB-MINING")
    print("=" * 80)
    print(f"{'Source':<15} | {'Dates':<8} | {'Total Files':<12} | {'Total Jobs':<12} | {'Quality':<10}")
    print("-" * 80)

    grand_total_jobs = 0

    sources = [
        d for d in base.iterdir()
        if d.is_dir() and not d.name.startswith(".") and d.name not in ("checkpoints", "__pycache__")
    ]

    for src_dir in sorted(sources):
        src_name = src_dir.name
        json_files = sorted(list(src_dir.glob("dt=*/*.json")) + list(src_dir.glob("dt=*/*.jsonl")))
        date_dirs = list(src_dir.glob("dt=*"))

        total_jobs = 0
        quality_ok = True

        for jf in json_files:
            checker = DataQualityChecker(jf)
            res = checker.check()
            total_jobs += res["total_records"]
            if not res["passed"]:
                quality_ok = False

        grand_total_jobs += total_jobs
        status_str = "✅ PASS" if quality_ok and total_jobs > 0 else ("⚠️ NO DATA" if total_jobs == 0 else "❌ FAIL")

        print(
            f"{src_name:<15} | {len(date_dirs):<8} | {len(json_files):<12} | {total_jobs:<12} | {status_str:<10}"
        )

    print("-" * 80)
    print(f"TỔNG CỘNG TẤT CẢ NGUỒN: {grand_total_jobs} tin tuyển dụng.")
    print("=" * 80)


if __name__ == "__main__":
    generate_report()
