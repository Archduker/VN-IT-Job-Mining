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
    max_items: int = 30,
    output_dir: str = "data",
    checkpoint_dir: Optional[str] = None,
    batch_id: Optional[str] = None,
    phase: str = "all",
    max_pages: Optional[int] = None,
    engine: Optional[str] = None,
    online: bool = True,
) -> Dict[str, Any]:
    """Khởi tạo và thực thi crawler theo source và phase."""
    source = source.lower()
    if source not in SUPPORTED_SOURCES:
        raise ValueError(
            f"Nguồn '{source}' không được hỗ trợ. Chọn một trong: {', '.join(SUPPORTED_SOURCES)}"
        )

    crawler_map = {}

    if source == "topcv":
        from collection.sources.topcv.crawler import TopCVCrawler
        kwargs = {
            "checkpoint_dir": checkpoint_dir,
            "output_dir": output_dir,
            "max_items": max_items,
        }
        if engine:
            kwargs["engine"] = engine
        crawler = TopCVCrawler(**kwargs)
    elif source == "topdev":
        from collection.sources.topdev.crawler import TopDevCrawler
        crawler = TopDevCrawler(
            checkpoint_dir=checkpoint_dir,
            output_dir=output_dir,
            max_items=max_items,
        )
    elif source == "vietnamworks":
        from collection.sources.vietnamworks.crawler import VietnamWorksCrawler
        crawler = VietnamWorksCrawler(
            checkpoint_dir=checkpoint_dir,
            output_dir=output_dir,
            max_items=max_items,
        )
    elif source == "careerviet":
        from collection.sources.careerviet.crawler import CareerVietCrawler
        crawler = CareerVietCrawler(
            checkpoint_dir=checkpoint_dir,
            output_dir=output_dir,
            max_items=max_items,
            ledger_dir=os.path.join(output_dir, source, "url_ledger") if output_dir else None,
            raw_dir=os.path.join(output_dir, source, "raw") if output_dir else None,
        )
    elif source == "vieclam24h":
        from collection.sources.vieclam24h.crawler import ViecLam24hCrawler
        crawler = ViecLam24hCrawler(
            checkpoint_dir=checkpoint_dir,
            output_dir=output_dir,
            max_items=max_items,
        )
    elif source == "itviec":
        from collection.sources.itviec.crawler import ItviecCrawler
        crawler = ItviecCrawler(
            checkpoint_dir=checkpoint_dir,
            output_dir=output_dir,
            max_items=max_items,
        )
    elif source == "glints":
        from collection.sources.glints.raw_pipeline import GlintsRawPipeline
        crawler = GlintsRawPipeline(
            max_items=max_items,
            storage_dir=os.path.join(output_dir, source, "url_ledger") if output_dir else None,
        )
    elif source == "jobsgo":
        from collection.sources.jobsgo.crawler import JobsGORawCrawler
        crawler = JobsGORawCrawler(
            max_items=max_items,
            storage_dir=os.path.join(output_dir, source, "url_ledger") if output_dir else None,
        )
    else:
        raise ValueError(f"Chưa cài đặt runner cho nguồn {source}")

    if batch_id:
        crawler.batch_id = batch_id

    # ── Điều phối theo Phase ───────────────────────────────────
    if phase == "discover":
        if hasattr(crawler, "discover_urls"):
            kw = {"max_pages": max_pages}
            if "online" in crawler.discover_urls.__code__.co_varnames:
                kw["online"] = online
            discovered = crawler.discover_urls(**kw)
            return {"source": source, "phase": "discover", "discovered_urls": discovered}
        else:
            raise NotImplementedError(f"Crawler nguồn '{source}' chưa cài đặt hàm discover_urls()")

    elif phase == "detail":
        if hasattr(crawler, "crawl_details"):
            kw = {"limit": max_items}
            if "online" in crawler.crawl_details.__code__.co_varnames:
                kw["online"] = online
            stats = crawler.crawl_details(**kw)
            return {"source": source, "phase": "detail", **stats}
        else:
            raise NotImplementedError(f"Crawler nguồn '{source}' chưa cài đặt hàm crawl_details()")

    else:  # phase == "all"
        if hasattr(crawler, "discover_urls") and hasattr(crawler, "crawl_details"):
            kw_disc = {"max_pages": max_pages}
            if "online" in crawler.discover_urls.__code__.co_varnames:
                kw_disc["online"] = online
            discovered = crawler.discover_urls(**kw_disc)

            kw_det = {"limit": max_items}
            if "online" in crawler.crawl_details.__code__.co_varnames:
                kw_det["online"] = online
            stats = crawler.crawl_details(**kw_det)
            return {"source": source, "phase": "all", "discovered_urls": discovered, **stats}
        return crawler.run()



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
  .venv/bin/python run.py --source jobsgo --phase all --max-items 5
        """,
    )
    parser.add_argument(
        "--source",
        "-s",
        type=str,
        required=True,
        choices=SUPPORTED_SOURCES + ["all"],
        help="Nguồn tuyển dụng cần cào (hoặc 'all' để chạy toàn bộ 8 nguồn)",
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
        "--phase",
        "-p",
        type=str,
        default="all",
        choices=["discover", "detail", "all"],
        help="Giai đoạn thực thi: 'discover' (Pha 1: quét link), 'detail' (Pha 2: cào chi tiết), 'all' (cả hai)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Số trang danh mục tối đa cần quét ở Phase 1 (mặc định: không giới hạn)",
    )
    parser.add_argument(
        "--engine",
        type=str,
        default="cloakbrowser",
        choices=["cloakbrowser", "curl_cffi", "playwright", "nodriver"],
        help="Engine vượt Cloudflare cho các nguồn hỗ trợ (mặc định: cloakbrowser)",
    )
    parser.add_argument(
        "--online",
        action="store_true",
        default=True,
        help="Bật chế độ cào trực tuyến (mặc định: True)",
    )
    parser.add_argument(
        "--offline",
        dest="online",
        action="store_false",
        help="Chạy chế độ offline từ cache HTML",
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

    all_results = []
    overall_exit_code = 0

    log.info("=" * 70)
    log.info("BẮT ĐẦU CHẠY CRAWLER (Tổng %d nguồn) | Phase: %s | max_items: %d", len(target_sources), args.phase.upper(), args.max_items)
    log.info("=" * 70)

    for src in target_sources:
        log.info("\n>>> ĐANG CHẠY NGUỒN: %s (Phase: %s) ...", src.upper(), args.phase.upper())
        try:
            stats = run_crawler(
                source=src,
                max_items=args.max_items,
                output_dir=args.output_dir,
                checkpoint_dir=args.checkpoint_dir,
                batch_id=args.batch_id,
                phase=args.phase,
                max_pages=args.max_pages,
                engine=args.engine,
                online=args.online,
            )
            all_results.append((src, True, stats))
            log.info(
                "[%s] Hoàn tất: %s",
                src.upper(),
                stats,
            )
        except Exception as exc:
            log.error("Lỗi khi chạy crawler nguồn %s: %s", src, exc, exc_info=args.verbose)
            all_results.append((src, False, {"error": str(exc)}))
            overall_exit_code = 1

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
