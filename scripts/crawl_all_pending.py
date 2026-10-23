#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bộ điều phối tự động thu thập toàn bộ URL còn lại (Smart Resilient Batch Crawler).

Tự động cào toàn bộ các URL đang ở trạng thái PENDING của TopCV & VietnamWorks,
tích hợp cơ chế Smart Lock Recovery:
- Tự động phát hiện Cloudflare WAF / HTTP 429 Rate Limiting.
- Bảo toàn URL ở trạng thái PENDING (Zero Failures do IP lock).
- Đóng sạch session trình duyệt và giải phóng tài nguyên.
- Lập tức cưỡng bức đồng bộ (Force Sync) lên Cloudflare R2 Lakehouse.
- Tự động nghỉ ngơi 15 phút (900 giây) với đồng hồ đếm ngược trực quan để hạ nhiệt IP.
- Sau 15 phút, tự động khởi tạo session mới sạch và tiếp tục cào các URL PENDING còn lại.

Sử dụng:
    .venv/bin/python scripts/crawl_all_pending.py --source all
    .venv/bin/python scripts/crawl_all_pending.py --source topcv --batch-size 20 --lock-cooldown 900
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Đảm bảo nhận thư mục gốc của dự án
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crawlers.sources.topcv.crawler import RateLimitLockError, TopCVCrawler
from crawlers.sources.vietnamworks.crawler import VietnamWorksCrawler
from crawlers.common.ip_rotator import ProxyPool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("orchestrator")

running = True


def handle_shutdown_signal(signum, frame):
    """Bắt tín hiệu ngắt (Ctrl+C hoặc SIGTERM) để dừng an toàn và đồng bộ dữ liệu."""
    global running
    log.warning(
        "\n[Shutdown] Nhận tín hiệu dừng (Signal %s). Đang chuẩn bị hoàn tất tác vụ hiện tại và đồng bộ an toàn...",
        signum,
    )
    running = False


signal.signal(signal.SIGINT, handle_shutdown_signal)
signal.signal(signal.SIGTERM, handle_shutdown_signal)


def reset_failed_records_to_pending(source: str) -> int:
    """Khôi phục các bản ghi FAILED trước đó quay trở lại PENDING để cào lại."""
    catalog_path = PROJECT_ROOT / f"data/{source}/url_ledger/catalog_master.json"
    if not catalog_path.exists():
        return 0

    try:
        data = json.loads(catalog_path.read_text(encoding="utf-8"))
        reset_count = 0
        for rec in data.values():
            if rec.get("status") == "FAILED":
                rec["status"] = "PENDING"
                rec["error_log"] = None
                reset_count += 1

        if reset_count > 0:
            catalog_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            log.info("[%s] Đã khôi phục %d bản ghi FAILED quay trở lại hàng đợi PENDING.", source.upper(), reset_count)
        return reset_count
    except Exception as exc:
        log.warning("[%s] Không thể khôi phục bản ghi FAILED: %s", source.upper(), exc)
        return 0


def get_pending_summary(source: str) -> Dict[str, int]:
    """Lấy thống kê số lượng URL theo trạng thái từ catalog_master.json."""
    catalog_path = PROJECT_ROOT / f"data/{source}/url_ledger/catalog_master.json"
    if not catalog_path.exists():
        return {"total": 0, "pending": 0, "done": 0, "failed": 0, "repost": 0}

    try:
        data = json.loads(catalog_path.read_text(encoding="utf-8"))
        counts = {"total": len(data), "pending": 0, "done": 0, "failed": 0, "repost": 0}
        for rec in data.values():
            st = rec.get("status", "UNKNOWN")
            if st == "PENDING":
                counts["pending"] += 1
            elif st == "DONE":
                if rec.get("repost_of_url_hash"):
                    counts["repost"] += 1
                counts["done"] += 1
            elif st == "FAILED":
                counts["failed"] += 1
        return counts
    except Exception:
        return {"total": 0, "pending": 0, "done": 0, "failed": 0, "repost": 0}


def crawl_vietnamworks_pending(sync_r2: bool = True) -> None:
    """Cào sạch các URL đang đợi của VietnamWorks qua API search nội bộ."""
    stats = get_pending_summary("vietnamworks")
    if stats["pending"] == 0:
        log.info("[VietnamWorks] Không còn URL nào ở trạng thái PENDING. Bỏ qua.")
        return

    log.info("=" * 70)
    log.info("▶ BẮT ĐẦU CÀO NGUỒN VIETNAMWORKS (Còn %d URL PENDING)...", stats["pending"])
    log.info("=" * 70)

    try:
        crawler = VietnamWorksCrawler(sync_minio=sync_r2)
        res = crawler.crawl_details(online=True, limit=None)
        log.info("✔ [VietnamWorks] Hoàn tất cào chi tiết: %s", res)
    except Exception as exc:
        log.error("❌ [VietnamWorks] Gặp lỗi khi cào chi tiết: %s", exc)


def sleep_with_countdown(seconds: int, reason: str = "") -> bool:
    """Ngủ có đếm ngược từng 30s-60s và hỗ trợ ngắt an toàn qua SIGINT/SIGTERM."""
    global running
    start_time = time.time()
    remaining = seconds

    log.info("=" * 70)
    log.info("🛌 BẮT ĐẦU NGHỈ %d GIÂY (%.1f PHÚT) ĐỂ HẠ NHIỆT IP...", seconds, seconds / 60.0)
    if reason:
        log.info("   Lý do: %s", reason)
    log.info("   Thời gian hiện tại : %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    wake_time = datetime.fromtimestamp(start_time + seconds).strftime("%Y-%m-%d %H:%M:%S")
    log.info("   Dự kiến thức dậy lúc: %s", wake_time)
    log.info("=" * 70)

    while running and remaining > 0:
        mins = remaining // 60
        secs = remaining % 60
        if remaining % 60 == 0 or remaining == seconds or remaining <= 10:
            log.info("⏳ [COOLDOWN] Đang nghỉ... Còn lại %02d:%02d đến khi tiếp tục cào.", mins, secs)

        step = min(5, remaining)
        time.sleep(step)
        remaining = max(0, int(seconds - (time.time() - start_time)))

    if not running:
        log.info("[COOLDOWN] Đã nhận tín hiệu dừng trong lúc đang nghỉ.")
        return False

    log.info("🔔 [COOLDOWN HOÀN TẤT] Hết %d giây nghỉ. IP đã hạ nhiệt! Tiếp tục cào bài đăng...", seconds)
    return True


def run_topcv_resilient_loop(
    batch_size: int = 20,
    lock_cooldown_sec: int = 900,
    min_delay: float = 3.5,
    max_delay: float = 7.0,
    engine: str = "cloakbrowser",
    sync_r2: bool = True,
    proxy_url: Optional[str] = None,
    proxy_file: Optional[str] = None,
    rotate_interval: int = 0,
) -> None:
    """Vòng lặp cào TopCV theo batch với bẫy khóa IP tự động nghỉ 15 phút hoặc xoay Proxy."""
    global running

    reset_failed_records_to_pending("topcv")
    st_init = get_pending_summary("topcv")
    total_to_crawl = st_init["pending"]

    proxy_pool = ProxyPool(proxy_url=proxy_url, proxy_file=proxy_file)
    active_proxy = proxy_pool.get_current() if proxy_pool.has_proxies() else None

    log.info("=" * 70)
    log.info("🚀 KHỞI ĐỘNG TOPCV RESILIENT BATCH CRAWLER")
    log.info(" • Tổng URL cần cào   : %d tin PENDING", total_to_crawl)
    log.info(" • Kích thước đợt cào : %d tin / sub-batch", batch_size)
    log.info(" • Pacing an toàn     : %.1fs - %.1fs / tin", min_delay, max_delay)
    log.info(" • Engine vượt WAF    : %s (Off-screen Stealth)", engine)
    log.info(" • Đồng bộ R2         : %s", "BẬT" if sync_r2 else "TẮT")
    if proxy_pool.has_proxies():
        masked = active_proxy.split("@")[-1] if active_proxy and "@" in active_proxy else active_proxy
        log.info(" • Proxy Pool         : BẬT (%d proxies | Đang dùng: %s)", len(proxy_pool.proxies), masked)
        log.info(" • Chế độ xoay IP     : Tự động đổi IP ngay khi gặp 429 (Triệt tiêu 15p chờ!)")
    else:
        log.info(" • Proxy Pool         : TẮT (Chạy IP trực tiếp)")
        log.info(" • Thời gian chờ Lock : %d giây (%.1f phút)", lock_cooldown_sec, lock_cooldown_sec / 60.0)
    log.info("=" * 70)

    batch_idx = 0
    total_crawled_in_session = 0
    start_session_time = time.time()

    while running:
        summary = get_pending_summary("topcv")
        pending_remaining = summary["pending"]

        if pending_remaining == 0:
            log.info("\n🎉🎉🎉 CHÚC MỪNG: TOÀN BỘ URL TOPCV ĐÃ ĐƯỢC CÀO XONG 100%! 🎉🎉🎉")
            break

        # Chủ động đổi proxy định kỳ nếu được cấu hình
        if rotate_interval > 0 and total_crawled_in_session > 0 and total_crawled_in_session % rotate_interval == 0:
            if proxy_pool.has_proxies():
                active_proxy = proxy_pool.rotate()

        batch_idx += 1
        current_limit = min(batch_size, pending_remaining)
        done_cnt = summary["done"]
        total_cnt = summary["total"]
        pct = (done_cnt / total_cnt * 100.0) if total_cnt > 0 else 0.0

        log.info(
            "\n▶ [SUB-BATCH %d] Bắt đầu cào %d tin | Tiến độ: %d/%d (%.1f%%) | Còn lại: %d PENDING...",
            batch_idx,
            current_limit,
            done_cnt,
            total_cnt,
            pct,
            pending_remaining,
        )

        crawler = TopCVCrawler(
            engine=engine,
            sync_minio=sync_r2,
            min_delay=min_delay,
            max_delay=max_delay,
            raise_on_lock=True,
            proxy=active_proxy,
        )

        try:
            batch_stats = crawler.crawl_details(
                online=True,
                limit=current_limit,
                retry_failed=False,
                raise_on_lock=True,
            )

            success_cnt = batch_stats.get("success", 0)
            total_crawled_in_session += success_cnt
            elapsed = time.time() - start_session_time
            speed = (total_crawled_in_session / (elapsed / 3600.0)) if elapsed > 0 else 0.0

            log.info(
                "✔ [SUB-BATCH %d XONG] Thành công: %d, Lỗi: %d | Tốc độ phiên: %.1f tin/giờ",
                batch_idx,
                success_cnt,
                batch_stats.get("failed", 0),
                speed,
            )

            # Đảm bảo đóng phiên Trình duyệt sau mỗi batch để giải phóng RAM
            crawler._close_playwright_session()
            crawler._close_cloakbrowser_session()

            # Nghỉ ngắn giữa các batch (10s - 15s) để giữ IP sạch
            if running and pending_remaining - success_cnt > 0:
                short_pause = 10.0
                log.info("⏸️ Nghỉ ngắn %.1fs giữa các batch để xả bộ nhớ trình duyệt...", short_pause)
                time.sleep(short_pause)

        except RateLimitLockError as lock_err:
            log.warning(
                "\n⚠️ [LOCK PHÁT HIỆN] Cloudflare WAF / HTTP 429 kích hoạt tại URL: %s!",
                lock_err.url or "(đang tải)",
            )
            # 1. Đóng trình duyệt
            crawler._close_playwright_session()
            crawler._close_cloakbrowser_session()

            # 2. Cưỡng bức đồng bộ URL Ledger & Raw lên Cloudflare R2
            if sync_r2:
                log.info("☁️ Đang đồng bộ khẩn cấp dữ liệu hiện có lên Cloudflare R2 Lakehouse...")
                try:
                    ledger = crawler._get_ledger()
                    ledger.save_catalog()
                    ledger.sync_to_minio()
                    log.info("✔ Đồng bộ R2 khẩn cấp thành công!")
                except Exception as sync_exc:
                    log.warning("Lỗi đồng bộ khẩn cấp lên R2: %s", sync_exc)

            # 3. Nếu có ProxyPool, xoay sang IP Proxy mới ngay lập tức
            if proxy_pool.has_proxies():
                active_proxy = proxy_pool.rotate()
                masked = active_proxy.split("@")[-1] if active_proxy and "@" in active_proxy else active_proxy
                log.info("🔄 [PROXY ROTATE] Bị khóa IP cũ! Đã xoay sang Proxy mới: %s. Tiếp tục cào ngay sau 3s!", masked)
                time.sleep(3.0)
                continue

            # 4. Nếu không có proxy, nghỉ ngơi 15 phút (900s) như bình thường
            if not sleep_with_countdown(lock_cooldown_sec, reason=f"Cloudflare Rate Limit Lock tại {lock_err.url}"):
                break

        except Exception as generic_err:
            log.error("[SUB-BATCH %d] Lỗi ngoại lệ không lường trước: %s", batch_idx, generic_err)
            crawler._close_playwright_session()
            crawler._close_cloakbrowser_session()
            time.sleep(10.0)

    # Đồng bộ chốt sổ sau khi kết thúc vòng lặp
    if sync_r2:
        log.info("\n☁️ Đang đồng bộ chốt sổ toàn bộ URL Ledger lên Cloudflare R2...")
        try:
            final_crawler = TopCVCrawler(sync_minio=True)
            final_ledger = final_crawler._get_ledger()
            final_ledger.save_catalog()
            final_ledger.sync_to_minio()
            log.info("✔ Đồng bộ chốt sổ Cloudflare R2 hoàn tất!")
        except Exception as e:
            log.warning("Lỗi đồng bộ chốt sổ: %s", e)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Smart Resilient Batch Crawler — Cào sạch URL còn lại với cơ chế Cooldown 15p chống khoá IP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--source",
        choices=["all", "topcv", "vietnamworks"],
        default="all",
        help="Nguồn cần cào: 'all' (VietnamWorks trước, TopCV sau), hoặc từng nguồn riêng biệt (mặc định: all)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=20,
        help="Số lượng tin tối đa trong mỗi sub-batch trước khi xả bộ nhớ trình duyệt (mặc định: 20)",
    )
    parser.add_argument(
        "--lock-cooldown",
        type=int,
        default=900,
        help="Thời gian nghỉ (giây) khi bị Cloudflare / WAF khoá IP (mặc định: 900s = 15 phút)",
    )
    parser.add_argument(
        "--min-delay",
        type=float,
        default=3.5,
        help="Thời gian chờ tối thiểu (giây) giữa 2 tin (mặc định: 3.5)",
    )
    parser.add_argument(
        "--max-delay",
        type=float,
        default=7.0,
        help="Thời gian chờ tối đa (giây) giữa 2 tin (mặc định: 7.0)",
    )
    parser.add_argument(
        "--engine",
        choices=["cloakbrowser", "playwright", "nodriver", "curl_cffi"],
        default="cloakbrowser",
        help="Engine vượt WAF (mặc định: cloakbrowser C++ Stealth)",
    )
    parser.add_argument(
        "--proxy",
        type=str,
        default=None,
        help="Proxy đơn lẻ (VD: http://user:pass@host:port hoặc ip:port)",
    )
    parser.add_argument(
        "--proxy-file",
        type=str,
        default=None,
        help="Đường dẫn file danh sách proxy (mặc định kiểm tra data/proxies.txt)",
    )
    parser.add_argument(
        "--rotate-interval",
        type=int,
        default=0,
        help="Số tin thành công thì chủ động xoay sang proxy tiếp theo (0 = chỉ xoay khi bị WAF lock)",
    )
    parser.add_argument(
        "--no-sync-r2",
        action="store_true",
        default=False,
        help="Tắt tự động đồng bộ lên Cloudflare R2 Lakehouse",
    )

    args = parser.parse_args()
    sync_r2 = not args.no_sync_r2

    print("=" * 80)
    print("   VN-IT-JOB-MINING — BỘ ĐIỀU PHỐI CÀO URL THÔNG MINH CHỐNG KHOÁ IP")
    print(f"   Mục tiêu: {args.source.upper()} | Cooldown khi bị khoá: {args.lock_cooldown}s (15 phút)")
    print(f"   Đồng bộ Cloudflare R2: {'BẬT' if sync_r2 else 'TẮT'}")
    print("=" * 80)

    # Pha 1: VietnamWorks (nếu chọn 'all' hoặc 'vietnamworks')
    if args.source in ["all", "vietnamworks"] and running:
        crawl_vietnamworks_pending(sync_r2=sync_r2)

    # Pha 2: TopCV (nếu chọn 'all' hoặc 'topcv')
    if args.source in ["all", "topcv"] and running:
        run_topcv_resilient_loop(
            batch_size=args.batch_size,
            lock_cooldown_sec=args.lock_cooldown,
            min_delay=args.min_delay,
            max_delay=args.max_delay,
            engine=args.engine,
            sync_r2=sync_r2,
            proxy_url=args.proxy,
            proxy_file=args.proxy_file,
            rotate_interval=args.rotate_interval,
        )

    # Báo cáo tổng kết cuối cùng
    print("\n" + "=" * 80)
    print("📊 BÁO CÁO TỔNG KẾT TRẠNG THÁI CUỐI CÙNG")
    print("=" * 80)
    for src in ["vietnamworks", "topcv"]:
        st = get_pending_summary(src)
        print(f"• {src.upper():<15}: {st['done']}/{st['total']} DONE | Còn lại: {st['pending']} PENDING | Lỗi: {st['failed']}")
    print("=" * 80 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
