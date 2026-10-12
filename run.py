#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Điều phối và chạy độc lập các Crawler cho VN-IT-Job-Mining.

Sử dụng:
    python run.py --source topdev --max-items 1
    python run.py --source vietnamworks --max-items 5
    python run.py --source itviec --max-items 1
    python run.py --source careerviet --max-items 1
    python run.py --source vieclam24h --max-items 1
    python run.py --source topcv --max-items 1
"""

import argparse
import glob
from datetime import datetime, timezone, timedelta
import logging
import os
import sys
from typing import Any, Dict, Optional

# Đảm bảo PYTHONPATH nhận thư mục gốc dự án
CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

SUPPORTED_SOURCES = [
    "topdev",
    "vietnamworks",
    "itviec",
    "careerviet",
    "vieclam24h",
    "topcv",
    "glints",
    "jobsgo",
]


def setup_logger(verbose: bool = False) -> logging.Logger:
    """Cấu hình logger chuẩn cho CLI."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger("runner")


def run_crawler(
    source: str,
    max_items: Optional[int] = 30,
    output_dir: str = "data",
    checkpoint_dir: Optional[str] = None,
    batch_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Khởi tạo và thực thi crawler theo source."""
    source = source.lower()
    if source not in SUPPORTED_SOURCES:
        raise ValueError(
            f"Nguồn '{source}' không được hỗ trợ. Chọn một trong: {', '.join(SUPPORTED_SOURCES)}"
        )

    crawler_obj = None
    if source == "topdev":
        from crawlers.sources.topdev.crawler import TopDevCrawler
        crawler_obj = TopDevCrawler(
            checkpoint_dir=checkpoint_dir,
            output_dir=output_dir,
            max_items=max_items,
        )
    elif source == "vietnamworks":
        from crawlers.sources.vietnamworks.crawler import VietnamWorksCrawler
        crawler_obj = VietnamWorksCrawler(
            checkpoint_dir=checkpoint_dir,
            output_dir=output_dir,
            max_items=max_items,
        )
    elif source == "careerviet":
        from crawlers.sources.careerviet.crawler import CareerVietCrawler
        crawler_obj = CareerVietCrawler(
            checkpoint_dir=checkpoint_dir,
            output_dir=output_dir,
            max_items=max_items,
        )
    elif source == "vieclam24h":
        from crawlers.sources.vieclam24h.crawler import ViecLam24hCrawler
        crawler_obj = ViecLam24hCrawler(
            checkpoint_dir=checkpoint_dir,
            output_dir=output_dir,
            max_items=max_items,
        )
    elif source == "topcv":
        from crawlers.sources.topcv.crawler import TopCVCrawler
        crawler_obj = TopCVCrawler(
            checkpoint_dir=checkpoint_dir,
            output_dir=output_dir,
            max_items=max_items,
        )
    elif source == "itviec":
        from crawlers.sources.itviec.crawler import ItviecCrawler
        crawler_obj = ItviecCrawler(
            checkpoint_dir=checkpoint_dir,
            output_dir=output_dir,
            max_items=max_items,
        )
    elif source == "glints":
        try:
            from crawlers.sources.glints.crawler import GlintsCrawler
            crawler_obj = GlintsCrawler(
                checkpoint_dir=checkpoint_dir,
                output_dir=output_dir,
                max_items=max_items,
            )
        except ImportError:
            raise NotImplementedError("Crawler nguồn 'glints' đang được phát triển hoặc chưa có file crawler.py.")
    elif source == "jobsgo":
        from crawlers.sources.jobsgo.crawler import JobsGOCrawler
        crawler_obj = JobsGOCrawler(
            checkpoint_dir=checkpoint_dir,
            output_dir=output_dir,
            max_items=max_items,
        )
    else:
        raise ValueError(f"Chưa cài đặt runner cho nguồn {source}")

    if batch_id:
        crawler_obj.batch_id = batch_id
    stats = crawler_obj.run()

    # Tự động đồng bộ các jobs vừa cào vào State Catalog (SUCCESS)
    try:
        from crawlers.common.job_catalog import JobStateCatalog
        JobStateCatalog().sync_from_batches(data_dir=output_dir, source=source)
    except Exception as exc:
        logging.getLogger("runner").warning("Không thể tự động đồng bộ catalog: %s", exc)

    return stats



def main() -> int:
    parser = argparse.ArgumentParser(
        description="VN IT Job Mining — Bộ điều phối chạy crawler độc lập",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ sử dụng:
  .venv/bin/python run.py --source topdev --max-items 1
  .venv/bin/python run.py --source vietnamworks --max-items 5
  .venv/bin/python run.py --source itviec --max-items 1
  .venv/bin/python run.py --source careerviet --max-items 1
  .venv/bin/python run.py --source vieclam24h --max-items 1
  .venv/bin/python run.py --source topcv --max-items 1
        """,
    )
    parser.add_argument(
        "--source",
        "-s",
        type=str,
        required=True,
        choices=SUPPORTED_SOURCES + ["all"],
        help="Nguồn tuyển dụng cần cào (hoặc 'all' để chạy toàn bộ 7 nguồn)",
    )
    parser.add_argument(
        "--max-items",
        "-m",
        type=int,
        default=30,
        help="Số lượng tin tối đa cần thu thập trong batch (mặc định: 30, đặt 0 hoặc dùng --all-items để cào hết)",
    )
    parser.add_argument(
        "--all-items",
        action="store_true",
        help="Cào toàn bộ items / toàn bộ trang không giới hạn (tương đương max_items=None)",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default="data",
        help="Thư mục gốc lưu trữ dữ liệu (mặc định: data)",
    )
    parser.add_argument(
        "--checkpoint-dir",
        type=str,
        default=None,
        help="Thư mục lưu trữ checkpoint (mặc định: data/<source>)",
    )
    parser.add_argument(
        "--batch-id",
        type=str,
        default=None,
        help="Mã định danh batch (mặc định: tự sinh dạng YYYY-MM-DD_<source>_<seq>)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Bật log chi tiết DEBUG",
    )

    args = parser.parse_args()
    log = setup_logger(verbose=args.verbose)

    target_sources = SUPPORTED_SOURCES if args.source == "all" else [args.source]

    # Xác định giới hạn items (None = cào toàn bộ tất cả các trang)
    effective_max_items: Optional[int] = None if (args.all_items or args.max_items <= 0) else args.max_items

    all_results = []
    overall_exit_code = 0

    log.info("=" * 70)
    items_desc = "TOÀN BỘ (All Items / All Pages)" if effective_max_items is None else f"{effective_max_items} items/nguồn"
    log.info("BẮT ĐẦU CHẠY CRAWLER (Tổng %d nguồn) | Mục tiêu: %s", len(target_sources), items_desc)
    log.info("=" * 70)

    for src in target_sources:
        log.info("\n>>> ĐANG CHẠY NGUỒN: %s ...", src.upper())
        try:
            stats = run_crawler(
                source=src,
                max_items=effective_max_items,
                output_dir=args.output_dir,
                checkpoint_dir=args.checkpoint_dir,
                batch_id=args.batch_id,
            )
            all_results.append((src, True, stats))
            log.info(
                "[%s] Hoàn tất: crawled=%d, skipped=%d, errors=%d, file=%s",
                src.upper(),
                stats.get("crawled", 0),
                stats.get("skipped", 0),
                stats.get("errors", 0),
                stats.get("output_file", "N/A"),
            )
        except Exception as exc:
            log.error("Lỗi khi chạy crawler nguồn %s: %s", src, exc, exc_info=args.verbose)
            all_results.append((src, False, {"error": str(exc)}))
            overall_exit_code = 1

    # Sắp xếp kết quả theo tên nguồn để hiển thị bảng rõ ràng
    all_results.sort(key=lambda x: x[0])

    print("\n" + "=" * 80)
    print("📊 BẢNG TỔNG KẾT KẾT QUẢ THU THẬP CẢ 7 NGUỒN TUYỂN DỤNG")
    print("=" * 80)
    print(f"{'NGUỒN':<15} | {'TRẠNG THÁI':<10} | {'MỚI (CRAWLED)':<13} | {'BỎ QUA':<8} | {'LỖI':<6} | {'FILE ĐẦU RA'}")
    print("-" * 80)

    for src, success, st in all_results:
        status_str = "✅ SUCCESS" if success else "❌ FAILED"
        crawled_val = str(st.get("crawled", 0)) if success else "0"
        skipped_val = str(st.get("skipped", 0)) if success else "0"
        errors_val = str(st.get("errors", 0)) if success else "1"
        out_f = str(st.get("output_file") or "N/A") if success else f"Err: {st.get('error', '')[:25]}"
        print(f"{src:<15} | {status_str:<10} | {crawled_val:<13} | {skipped_val:<8} | {errors_val:<6} | {out_f}")

    print("=" * 80 + "\n")
    return overall_exit_code


if __name__ == "__main__":
    sys.exit(main())
