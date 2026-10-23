# -*- coding: utf-8 -*-
"""Điều phối cào dữ liệu TopCV theo đợt an toàn (Rate-Safe Batch Scheduler).

Chiến lược điều phối:
- 10 tin mỗi tiếng (10 jobs / hour).
- Tối đa 240 tin mỗi ngày (24 giờ x 10 tin = 240 tin/ngày).
- Pacing giãn cách tự nhiên giữa mỗi tin: 8.0s - 15.0s.
- Tự động đồng bộ URL Ledger & Raw Snapshot lên Cloudflare R2 sau mỗi đợt.
- Nghỉ ngơi giải phóng toàn bộ tài nguyên trình duyệt sau mỗi đợt 10 tin để hạ nhiệt IP.
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Đảm bảo import được các module của dự án
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from crawlers.sources.topcv.crawler import TopCVCrawler

log = logging.getLogger("topcv.scheduler")
running = True


def handle_sigterm(signum, frame):
    global running
    log.info("[Scheduler] Nhận tín hiệu dừng (Signal %s). Đang chuẩn bị dừng an toàn...", signum)
    running = False


signal.signal(signal.SIGINT, handle_sigterm)
signal.signal(signal.SIGTERM, handle_sigterm)


def run_scheduler(
    jobs_per_hour: int = 10,
    max_daily: int = 240,
    interval_seconds: int = 3600,
    engine: str = "playwright",
    sync_minio: bool = True,
    run_once: bool = False,
) -> None:
    global running

    log.info("======================================================================")
    log.info(" KHỞI ĐỘNG TOPCV RATE-SAFE BATCH SCHEDULER")
    log.info(" • Hạn mức mỗi đợt   : %d tin / đợt", jobs_per_hour)
    log.info(" • Tần suất cào      : Mỗi %d giây (%.1f giờ)", interval_seconds, interval_seconds / 3600.0)
    log.info(" • Hạn mức mỗi ngày  : Tối đa %d tin / ngày", max_daily)
    log.info(" • Engine vượt WAF   : %s (Off-screen GPU)", engine)
    log.info(" • Đồng bộ R2 Lakehouse: %s", "BẬT" if sync_minio else "TẮT")
    log.info("======================================================================")

    current_day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    daily_crawled = 0
    batch_count = 0

    while running:
        today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today_utc != current_day:
            log.info("[Scheduler] Đổi ngày mới (%s -> %s). Đặt lại hạn mức ngày về 0.", current_day, today_utc)
            current_day = today_utc
            daily_crawled = 0

        if daily_crawled >= max_daily:
            log.warning(
                "[Scheduler] Đã đạt hạn mức ngày (%d/%d tin). Tạm dừng chờ sang ngày mới...",
                daily_crawled,
                max_daily,
            )
            # Ngủ 15 phút rồi kiểm tra lại ngày mới
            for _ in range(15):
                if not running:
                    break
                time.sleep(60)
            continue

        batch_count += 1
        log.info(
            "\n▶ [ĐỢT %d] Bắt đầu cào đợt mới lúc %s (Đã cào trong ngày: %d/%d tin)...",
            batch_count,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            daily_crawled,
            max_daily,
        )

        start_time = time.time()
        round_limit = min(jobs_per_hour, max_daily - daily_crawled)

        # Khởi tạo crawler mới độc lập cho đợt này để đóng sạch browser sau khi cào xong 10 tin
        crawler = TopCVCrawler(
            engine=engine,
            sync_minio=sync_minio,
            min_delay=8.0,
            max_delay=15.0,
        )

        try:
            stats = crawler.crawl_details(
                online=True,
                limit=round_limit,
                retry_failed=False,
            )
            success_in_batch = stats.get("success", 0)
            daily_crawled += success_in_batch

            ledger = crawler._get_ledger()
            total_records = len(ledger.records)
            done_count = sum(1 for r in ledger.records.values() if r.get("status") == "DONE")
            pending_count = sum(1 for r in ledger.records.values() if r.get("status") == "PENDING")

            log.info(
                "✔ [ĐỢT %d HOÀN TẤT] Thành công: %d tin, Lỗi: %d tin.",
                batch_count,
                success_in_batch,
                stats.get("failed", 0),
            )
            log.info(
                "📊 TIẾN ĐỘ TỔNG THỂ: %d/%d DONE (%.1f%%) | Còn lại: %d PENDING | Hôm nay: %d/%d",
                done_count,
                total_records,
                (done_count / total_records * 100) if total_records else 0,
                pending_count,
                daily_crawled,
                max_daily,
            )

            if pending_count == 0:
                log.info("🎉 TẤT CẢ CÁC BÀI ĐĂNG TUYỂN DỤNG ĐÃ ĐƯỢC CÀO XONG! Dừng Scheduler.")
                break

        except Exception as exc:
            log.error("[Scheduler] Lỗi trong đợt %d: %s", batch_count, exc)
        finally:
            # Đảm bảo đóng hoàn toàn browser để hạ nhiệt IP và giải phóng RAM
            crawler._close_playwright_session()

        if run_once:
            log.info("[Scheduler] Cờ --run-once được bật. Dừng sau 1 đợt.")
            break

        elapsed = time.time() - start_time
        sleep_needed = max(60, int(interval_seconds - elapsed))
        log.info(
            "⏳ Đợt %d kết thúc sau %.1fs. Trình duyệt đã đóng để hạ nhiệt IP. Ngủ %ds (%.1f phút) đến đợt tiếp theo...\n",
            batch_count,
            elapsed,
            sleep_needed,
            sleep_needed / 60.0,
        )

        # Ngủ từng khoảng nhỏ 5s để sẵn sàng nhận lệnh dừng SIGINT/SIGTERM
        slept = 0
        while running and slept < sleep_needed:
            time.sleep(min(5, sleep_needed - slept))
            slept += 5

    log.info("[Scheduler] Tiến trình điều phối cào TopCV đã kết thúc an toàn.")


def main() -> int:
    parser = argparse.ArgumentParser(description="TopCV Rate-Safe Batch Hourly Scheduler")
    parser.add_argument(
        "--jobs-per-hour",
        type=int,
        default=10,
        help="Số lượng tin tối đa cào trong 1 đợt mỗi tiếng (mặc định: 10)",
    )
    parser.add_argument(
        "--max-daily",
        type=int,
        default=240,
        help="Hạn mức tối đa mỗi ngày (mặc định: 240)",
    )
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=3600,
        help="Khoảng cách giữa các đợt (mặc định: 3600s = 1 giờ)",
    )
    parser.add_argument(
        "--engine",
        choices=["playwright", "nodriver", "curl_cffi"],
        default="playwright",
        help="Engine trình duyệt (mặc định: playwright)",
    )
    parser.add_argument(
        "--no-sync-minio",
        action="store_true",
        default=False,
        help="Tắt đồng bộ lên Cloudflare R2 / MinIO",
    )
    parser.add_argument(
        "--run-once",
        action="store_true",
        default=False,
        help="Chạy duy nhất 1 đợt rồi dừng ngay (dùng để kiểm thử)",
    )

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    run_scheduler(
        jobs_per_hour=args.jobs_per_hour,
        max_daily=args.max_daily,
        interval_seconds=args.interval_seconds,
        engine=args.engine,
        sync_minio=not args.no_sync_minio,
        run_once=args.run_once,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
