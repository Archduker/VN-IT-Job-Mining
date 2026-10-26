#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Autonomous temporary background runner: Drains TopCV pending queue (20-min cycle).

Self-terminating & Auto-revoking:
1. Runs every 20 minutes with a hard quota of 30 items per batch.
2. Syncs output raw JSON envelopes and UrlLedger to Cloudflare R2 after each batch.
3. Automatically self-deletes when pending queue reaches 0.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from collection.common.url_ledger import UrlLedger
from run import run_crawler

SOURCE = "topcv"
BATCH_SIZE = 30
COOLDOWN_SECONDS = 20 * 60  # 20 minutes
VN_TZ = timezone(timedelta(hours=7))

DATA_DIR = PROJECT_ROOT / "data" / SOURCE
DATA_DIR.mkdir(parents=True, exist_ok=True)
PID_FILE = DATA_DIR / "drain.pid"
LOG_FILE = DATA_DIR / "drain_progress.log"
SUMMARY_FILE = DATA_DIR / "drain_completed_summary.json"

# Configure logging to both file and stdout
logger = logging.getLogger("topcv_drain")
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(str(LOG_FILE), encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s"))
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s"))
logger.addHandler(file_handler)
logger.addHandler(stream_handler)


def cleanup_pid():
    if PID_FILE.exists():
        try:
            PID_FILE.unlink()
        except Exception:
            pass


def handle_shutdown(signum, frame):
    logger.info("[Drain TopCV] Nhận tín hiệu dừng (Signal %s). Dọn dẹp và kết thúc tiến trình...", signum)
    cleanup_pid()
    sys.exit(0)


signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)


def self_revoke():
    """Tự thu hồi/xóa sạch file script khi hoàn tất 100% nhiệm vụ."""
    cleanup_pid()
    script_path = Path(__file__).resolve()
    logger.info("[Drain TopCV] Bắt đầu tự thu hồi script: %s", script_path)
    try:
        if script_path.exists():
            script_path.unlink()
            logger.info("[Drain TopCV] ĐÃ TỰ XÓA FILE THÀNH CÔNG! Kho mã nguồn hoàn toàn sạch sẽ.")
    except Exception as e:
        logger.warning("[Drain TopCV] Không thể tự xóa file: %s", e)


def main():
    # Ghi PID file
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    start_time = datetime.now(VN_TZ)

    logger.info("=" * 70)
    logger.info("   BẮT ĐẦU CHU TRÌNH CÀO TỰ ĐỘNG XẢ HÀNG ĐỢI TOPCV (20 PHÚT / CA)")
    logger.info("   PID: %d | Thư mục dữ liệu: %s", os.getpid(), DATA_DIR)
    logger.info("=" * 70)

    ledger = UrlLedger(SOURCE)
    initial_summary = ledger.get_queue_summary()
    initial_pending = initial_summary.get("pending", 0)
    logger.info("Khởi động: Tổng số tin ban đầu cần xả: %d tin (Đã xong: %d tin)", initial_pending, initial_summary.get("done", 0))

    if initial_pending == 0:
        logger.info("[Drain TopCV] Hàng đợi đã rỗng sẵn (pending=0). Kết thúc ngay lập tức.")
        self_revoke()
        return

    batch_idx = 1
    if LOG_FILE.exists():
        try:
            import re
            content = LOG_FILE.read_text(encoding="utf-8")
            matches = re.findall(r"\[Ca (\d+) Hoàn Tất\]", content)
            if matches:
                batch_idx = max(int(m) for m in matches) + 1
                logger.info("Tiếp tục tiến trình từ Ca %d dựa trên lịch sử log.", batch_idx)
        except Exception:
            pass
    total_crawled_session = 0

    while True:
        ledger.reload()
        summary = ledger.get_queue_summary()
        pending = summary.get("pending", 0)
        done = summary.get("done", 0)

        # 1. Kiểm tra điều kiện hoàn tất 100%
        if pending == 0:
            end_time = datetime.now(VN_TZ)
            duration = end_time - start_time
            logger.info("=" * 70)
            logger.info("🎉 HOÀN TẤT 100% HÀNG ĐỢI TOPCV! PENDING = 0!")
            logger.info("   Tổng số ca đã chạy: %d ca", batch_idx - 1)
            logger.info("   Tổng số tin cào thành công phiên này: %d tin", total_crawled_session)
            logger.info("   Tổng thời gian thực thi: %s", duration)
            logger.info("=" * 70)

            # Đồng bộ lần cuối lên Cloudflare R2
            try:
                ledger.sync_to_minio()
                logger.info("[Drain TopCV] Đã đồng bộ UrlLedger lần cuối lên Cloudflare R2.")
            except Exception as se:
                logger.warning("[Drain TopCV] Lỗi đồng bộ R2 lần cuối: %s", se)

            try:
                from scripts.push_raw_to_r2 import push_source_data
                logger.info("[Drain TopCV] Bắt đầu đồng bộ toàn bộ file raw lên Cloudflare R2...")
                push_source_data(source=SOURCE)
                logger.info("[Drain TopCV] Đã đồng bộ toàn bộ file raw lên Cloudflare R2 thành công.")
            except Exception as re:
                logger.warning("[Drain TopCV] Lỗi đồng bộ raw lên R2: %s", re)

            # Xuất báo cáo tổng kết
            summary_data = {
                "source": SOURCE,
                "status": "COMPLETED",
                "completed_at": end_time.isoformat(),
                "duration_seconds": duration.total_seconds(),
                "batches_run": batch_idx - 1,
                "items_crawled_session": total_crawled_session,
                "final_queue_summary": summary,
            }
            try:
                SUMMARY_FILE.write_text(json.dumps(summary_data, ensure_ascii=False, indent=2), encoding="utf-8")
                logger.info("[Drain TopCV] Đã xuất báo cáo tổng kết tại %s", SUMMARY_FILE)
            except Exception as we:
                logger.warning("[Drain TopCV] Lỗi ghi summary: %s", we)

            # Tự thu hồi script và thoát
            self_revoke()
            break

        # 2. Thực thi ca cào hiện tại
        items_this_batch = min(pending, BATCH_SIZE)
        batch_start = datetime.now(VN_TZ)
        logger.info(
            "--- [Ca %d] Bắt đầu cào %d tin (Còn tồn đọng: %d tin) lúc %s ---",
            batch_idx,
            items_this_batch,
            pending,
            batch_start.strftime("%H:%M:%S"),
        )

        try:
            stats = run_crawler(
                source=SOURCE,
                phase="detail",
                max_items=items_this_batch,
                online=True,
            )
            crawled = stats.get("success", 0) or stats.get("items_crawled", 0) or 0
            total_crawled_session += crawled
            logger.info(
                "[Ca %d Hoàn Tất] Đã cào thành công: %d tin | Lỗi: %d tin",
                batch_idx,
                crawled,
                stats.get("failed", 0),
            )

            # Đồng bộ UrlLedger lên R2
            try:
                ledger.sync_to_minio()
            except Exception:
                pass

        except Exception as exc:
            logger.error("[Ca %d Lỗi] Ngoại lệ khi cào: %s", batch_idx, exc)

        # 3. Tính toán trạng thái mới sau ca
        ledger.reload()
        new_summary = ledger.get_queue_summary()
        new_pending = new_summary.get("pending", 0)
        logger.info(
            "[Tiến Độ] Đã xong: %d tin | Còn lại: %d tin PENDING",
            new_summary.get("done", 0),
            new_pending,
        )

        if new_pending == 0:
            continue  # Vòng lặp sẽ tự bắt ở đầu và trigger self_revoke()

        # 4. Nghỉ Cooldown 20 phút
        next_run_time = datetime.now(VN_TZ) + timedelta(seconds=COOLDOWN_SECONDS)
        logger.info(
            "[Nghỉ Cooldown] Đang nghỉ 20 phút để bảo vệ IP và Cloudflare WAF. Ca kế tiếp sẽ chạy lúc %s...",
            next_run_time.strftime("%H:%M:%S"),
        )
        batch_idx += 1
        time.sleep(COOLDOWN_SECONDS)


if __name__ == "__main__":
    main()
