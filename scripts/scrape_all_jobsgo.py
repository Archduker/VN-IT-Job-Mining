#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kịch bản cào toàn bộ tin tuyển dụng CNTT JobsGO bằng nodriver & đồng bộ R2 Lakehouse.

Thực hiện:
1. Kéo Catalog Master mới nhất từ Cloudflare R2 Lakehouse.
2. Chạy cào chi tiết với nodriver (bypassing Cloudflare Turnstile).
3. Checkpoint Sync tự động mỗi 15 tin lên R2.
4. Tự động cào vét các tin trong Failed Queue (nếu có rớt mạng).
5. Đồng bộ toàn bộ dữ liệu lên Cloudflare R2.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from crawlers.sources.jobsgo.crawler import JobsGoCrawler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
log = logging.getLogger("scrape_all_jobsgo")


def main() -> int:
    log.info("=" * 70)
    log.info("   BẮT ĐẦU CÀO TOÀN BỘ VIỆC LÀM CNTT JOBSGO BẰNG NODRIVER & R2")
    log.info("=" * 70)

    t_start = time.time()
    crawler = JobsGoCrawler(
        engine="nodriver",
        sync_minio=True,
        min_delay=1.2,
        max_delay=2.5,
    )

    # Vòng 1: Cào toàn bộ tin PENDING
    log.info("[Vòng 1] Bắt đầu cào tất cả các bài đăng PENDING...")
    stats_round1 = crawler.crawl_details(online=True)
    log.info("[Vòng 1] Kết quả: %s", stats_round1)

    # Vòng 2: Cào vét các bài đăng trong Failed Queue (nếu có)
    ledger = crawler._get_ledger()
    failed_candidates = ledger.get_failed_records()
    if failed_candidates:
        log.info("[Vòng 2] Phát hiện %d bài đăng lỗi. Bắt đầu cào vét (retry_failed)...", len(failed_candidates))
        stats_round2 = crawler.crawl_details(online=True, retry_failed=True)
        log.info("[Vòng 2] Kết quả cào vét: %s", stats_round2)

    # Đồng bộ tổng kết cuối cùng lên Cloudflare R2
    log.info("Đang đồng bộ catalog và manifests cuối cùng lên R2 Lakehouse...")
    ledger.save_catalog()
    ledger.export_daily_manifest()
    ledger.sync_to_minio()

    duration_m = (time.time() - t_start) / 60.0
    total = len(ledger.records)
    done_count = len([r for r in ledger.records.values() if r.get("status") == "DONE"])
    failed_count = len([r for r in ledger.records.values() if r.get("status") == "FAILED"])
    pending_count = len([r for r in ledger.records.values() if r.get("status") == "PENDING"])

    log.info("=" * 70)
    log.info("   TỔNG KẾT TIẾN TRÌNH CÀO JOBSGO")
    log.info("   Thời gian chạy: %.2f phút", duration_m)
    log.info("   Tổng URL: %d | DONE: %d | FAILED: %d | PENDING: %d", total, done_count, failed_count, pending_count)
    log.info("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
