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
    max_items: int = 30,
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

    if source == "topdev":
        from crawlers.sources.topdev.crawler import TopDevCrawler

        crawler = TopDevCrawler(
            checkpoint_dir=checkpoint_dir,
            output_dir=output_dir,
            max_items=max_items,
        )
        if batch_id:
            crawler.batch_id = batch_id
        return crawler.run()

    elif source == "vietnamworks":
        from crawlers.sources.vietnamworks.crawler import VietnamWorksCrawler

        crawler = VietnamWorksCrawler(
            checkpoint_dir=checkpoint_dir,
            output_dir=output_dir,
            max_items=max_items,
        )
        if batch_id:
            crawler.batch_id = batch_id
        return crawler.run()

    elif source == "careerviet":
        from crawlers.sources.careerviet.crawler import CareerVietCrawler

        crawler = CareerVietCrawler(
            checkpoint_dir=checkpoint_dir,
            output_dir=output_dir,
            max_items=max_items,
        )
        if batch_id:
            crawler.batch_id = batch_id
        return crawler.run()

    elif source == "vieclam24h":
        from crawlers.sources.vieclam24h.crawler import ViecLam24hCrawler

        crawler = ViecLam24hCrawler(
            checkpoint_dir=checkpoint_dir,
            output_dir=output_dir,
            max_items=max_items,
        )
        if batch_id:
            crawler.batch_id = batch_id
        return crawler.run()

    elif source == "topcv":
        from crawlers.sources.topcv.crawler import TopCVCrawler

        crawler = TopCVCrawler(
            checkpoint_dir=checkpoint_dir,
            output_dir=output_dir,
            max_items=max_items,
        )
        if batch_id:
            crawler.batch_id = batch_id
        return crawler.run()

    elif source == "itviec":
        import crawlers.sources.itviec.config as itviec_config
        import crawlers.sources.itviec.crawler as itviec_crawler

        # Đồng bộ cấu hình thư mục đầu ra
        itviec_data_dir = os.path.join(output_dir, "itviec")
        itviec_config.DATA_DIR = itviec_data_dir
        itviec_config.ERROR_DIR = os.path.join(itviec_data_dir, "errors")
        if checkpoint_dir:
            itviec_config.CHECKPOINT_FILE = os.path.join(checkpoint_dir, "checkpoint.json")
        else:
            itviec_config.CHECKPOINT_FILE = os.path.join(itviec_data_dir, "checkpoint.json")

        stats = itviec_crawler.crawl(max_items=max_items, batch_id=batch_id)

        # Tìm file output mới nhất của itviec (ưu tiên .json, fallback .jsonl)
        now = datetime.now(timezone(timedelta(hours=7)))
        date_str = now.strftime("%Y-%m-%d")
        dt_dir = os.path.join(itviec_data_dir, f"dt={date_str}")
        json_files = sorted(glob.glob(os.path.join(dt_dir, "batch_*.json")))
        if not json_files:
            json_files = sorted(glob.glob(os.path.join(dt_dir, "batch_*.jsonl")))
        output_file = stats.get("output_file") or (json_files[-1] if json_files else None)

        seen_total = 0
        if os.path.exists(itviec_config.CHECKPOINT_FILE):
            cp = itviec_crawler.load_checkpoint(itviec_config.CHECKPOINT_FILE)
            seen_total = len(cp.get("seen_ids", []))

        return {
            "source": "itviec",
            "crawled": stats.get("written", 0),
            "skipped": stats.get("skipped_seen_on_listing", 0),
            "errors": stats.get("failed", 0),
            "total_seen": seen_total,
            "output_file": output_file,
        }

    raise ValueError(f"Chưa cài đặt runner cho nguồn {source}")


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
        choices=SUPPORTED_SOURCES,
        help="Nguồn tuyển dụng cần cào",
    )
    parser.add_argument(
        "--max-items",
        "-m",
        type=int,
        default=30,
        help="Số lượng tin tối đa cần thu thập trong batch (mặc định: 30)",
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

    log.info("=" * 60)
    log.info("Bắt đầu chạy crawler nguồn: %s | max_items: %d", args.source, args.max_items)
    log.info("=" * 60)

    try:
        stats = run_crawler(
            source=args.source,
            max_items=args.max_items,
            output_dir=args.output_dir,
            checkpoint_dir=args.checkpoint_dir,
            batch_id=args.batch_id,
        )
    except Exception as exc:
        log.error("Lỗi trong quá trình chạy crawler nguồn %s: %s", args.source, exc, exc_info=True)
        return 1

    out_file = stats.get("output_file")
    log.info("-" * 60)
    log.info("KẾT QUẢ THU THẬP NGUỒN [%s]:", args.source.upper())
    log.info("  - Số tin thu thập mới (crawled) : %d", stats.get("crawled", 0))
    log.info("  - Số tin bỏ qua / trùng lặp    : %d", stats.get("skipped", 0))
    log.info("  - Số lỗi (errors)               : %d", stats.get("errors", 0))
    log.info("  - Tổng seen checkpoint          : %d", stats.get("total_seen", 0))
    log.info("  - File kết quả (.json)          : %s", out_file or "N/A")
    log.info("-" * 60)

    if out_file and os.path.exists(out_file) and os.path.getsize(out_file) > 0:
        print("\n" + "=" * 60)
        print("💡 CÂU LỆNH XEM NHANH 1 SAMPLE JSON ĐA DÒNG (PRETTY FORMAT):")
        if out_file.endswith(".jsonl"):
            print(f"python -c \"import json; print(json.dumps(json.loads(open('{out_file}').readline()), indent=2, ensure_ascii=False))\"")
            print("Hoặc dùng jq:")
            print(f"head -n 1 {out_file} | jq .")
        else:
            print(f"python -c \"import json; data = json.load(open('{out_file}')); print(json.dumps(data[0] if isinstance(data, list) and data else data, indent=2, ensure_ascii=False))\"")
            print("Hoặc dùng jq:")
            print(f"jq '.[0]' {out_file}")
        print("=" * 60 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
