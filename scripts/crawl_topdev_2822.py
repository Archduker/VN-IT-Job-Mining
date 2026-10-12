#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts.crawl_topdev_2822
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Kịch bản cào toàn bộ 2.822 tin tuyển dụng TopDev theo đúng bộ lọc danh mục của người dùng.

Quy trình 3 pha:
  Pha 1: Harvesting danh sách 2.822 URL bài đăng từ trang 1 đến trang 189.
  Pha 2: Lọc trùng qua Catalog & Cào chi tiết, xuất batch JSON chuẩn Schema v1.
  Pha 3: Đồng bộ SQLite Catalog & Hợp nhất dữ liệu (PreClean Pipeline).
"""

from __future__ import annotations

import argparse
import glob
import json
import logging
import os
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bs4 import BeautifulSoup
from crawlers.common.checkpoint import CheckpointManager
from crawlers.common.job_catalog import JobStateCatalog
from crawlers.common.json_writer import JsonWriter
from crawlers.common.schema import JobRecord
from crawlers.common.utils import make_batch_id
from crawlers.preprocessing.preClean.pipeline import PreCleanPipeline
from crawlers.sources.topdev.crawler import _make_record

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("topdev_2822")

LOCAL_TIMEZONE = timezone(timedelta(hours=7))

SEARCH_CATS = (
    "2%2C3%2C4%2C5%2C6%2C7%2C8%2C9%2C10%2C11%2C12%2C13%2C67%2C"
    "15%2C16%2C17%2C18%2C19%2C20%2C21%2C22%2C23%2C24%2C25%2C26%2C"
    "28%2C29%2C30%2C31%2C32%2C34%2C35%2C36%2C37%2C38%2C39%2C40%2C"
    "41%2C42%2C43%2C44%2C45%2C46%2C47%2C48%2C49%2C51%2C52%2C53%2C"
    "54%2C55%2C56%2C57%2C58%2C59%2C60%2C62%2C63%2C64%2C65%2C66"
)
BASE_LISTING_URL = f"https://topdev.vn/viec-lam/tim-kiem?job_categories_ids={SEARCH_CATS}"
TOTAL_PAGES = 189
QUEUE_FILE = PROJECT_ROOT / "data" / "queue" / "topdev_urls_2822.json"

DETAIL_FIELDS = (
    "id,slug,title,salary,company,skills_str,skills_arr,job_types_str,"
    "job_levels_str,job_levels_arr,experiences_str,contract_types_str,"
    "addresses,detail_url,published,is_salary_visible,content,requirements_arr,"
    "requirements_original,benefits_v2,benefits_original,"
    "recruitment_process_original,valid_through"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
}


def harvest_listing_urls(
    start_page: int = 1,
    max_pages: int | None = None,
    delay: float = 0.8,
) -> list[dict[str, str]]:
    """Pha 1: Duyệt phân trang listing SSR của TopDev và bóc tách toàn bộ URLs."""
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    ssl_ctx = ssl.create_default_context()

    collected_targets: dict[str, dict[str, str]] = {}
    if QUEUE_FILE.exists():
        try:
            with open(QUEUE_FILE, encoding="utf-8") as f:
                existing_list = json.load(f)
                for item in existing_list:
                    collected_targets[item["job_id"]] = item
            log.info("Đã tải %d URLs có sẵn từ file hàng đợi.", len(collected_targets))
        except Exception as exc:
            log.warning("Không đọc được file hàng đợi cũ: %s", exc)

    end_page = TOTAL_PAGES
    if max_pages is not None:
        end_page = min(TOTAL_PAGES, start_page + max_pages - 1)

    log.info("=== BẮT ĐẦU PHA 1: THU HOẠCH URL (Trang %d -> %d) ===", start_page, end_page)

    for page in range(start_page, end_page + 1):
        url = f"{BASE_LISTING_URL}&page={page}"
        req = urllib.request.Request(url, headers=HEADERS)
        attempt = 0
        success = False

        while attempt < 3 and not success:
            attempt += 1
            try:
                with urllib.request.urlopen(req, context=ssl_ctx, timeout=15) as resp:
                    html = resp.read().decode("utf-8")
                soup = BeautifulSoup(html, "html.parser")

                page_new = 0
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if "/viec-lam/" in href and not any(
                        k in href for k in ["tim-kiem", "tao-thong-bao", "blog"]
                    ):
                        clean_href = href.split("?")[0].rstrip("/")
                        match = re.search(r"-(\d+)$", clean_href)
                        if match:
                            job_id = match.group(1)
                            full_url = f"https://topdev.vn{clean_href}"
                            if job_id not in collected_targets:
                                collected_targets[job_id] = {
                                    "job_id": job_id,
                                    "url": full_url,
                                    "page": str(page),
                                }
                                page_new += 1

                log.info(
                    "[Pha 1] Trang %3d/%d: Thêm +%d tin mới (Tổng cộng: %d)",
                    page,
                    TOTAL_PAGES,
                    page_new,
                    len(collected_targets),
                )
                success = True
            except Exception as exc:
                log.warning("[Pha 1] Trang %d lỗi ở lượt %d/3: %s", page, attempt, exc)
                time.sleep(1.5 * attempt)

        # Lưu checkpoint sau mỗi 5 trang
        if page % 5 == 0 or page == end_page:
            with open(QUEUE_FILE, "w", encoding="utf-8") as f:
                json.dump(list(collected_targets.values()), f, ensure_ascii=False, indent=2)

        time.sleep(delay)

    final_list = list(collected_targets.values())
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(final_list, f, ensure_ascii=False, indent=2)

    log.info("=== HOÀN TẤT PHA 1: Thu được %d URL trong hàng đợi ===", len(final_list))
    return final_list


def _get_next_batch_seq(source: str = "topdev", run_date: date | None = None) -> int:
    d = run_date or date.today()
    pattern = f"data/{source}/dt={d.isoformat()}/batch_*.json"
    files = glob.glob(pattern)
    if not files:
        return 1
    max_seq = 0
    for f in files:
        m = re.search(r"batch_(\d+)\.json", f)
        if m:
            max_seq = max(max_seq, int(m.group(1)))
    return max_seq + 1


def scrape_details(
    max_items: int | None = None,
    delay: float = 1.2,
    batch_size: int = 250,
) -> int:
    """Pha 2: Lọc trùng qua Catalog & Cào chi tiết các tin mới."""
    if not QUEUE_FILE.exists():
        log.error("Chưa có file hàng đợi %s. Hãy chạy Pha 1 trước!", QUEUE_FILE)
        return 0

    with open(QUEUE_FILE, encoding="utf-8") as f:
        job_targets = json.load(f)

    log.info("=== BẮT ĐẦU PHA 2: CÀO CHI TIẾT (Tổng hàng đợi: %d tin) ===", len(job_targets))

    # Khởi tạo Checkpoint và State Catalog
    checkpoint = CheckpointManager(source="topdev", checkpoint_dir="data/topdev")
    catalog = JobStateCatalog()

    # Xác định batch sequence tiếp theo để không ghi đè
    current_run_date = date.today()
    current_seq = _get_next_batch_seq("topdev", current_run_date)
    writer = JsonWriter(
        source="topdev",
        output_dir="data",
        run_date=current_run_date,
        batch_seq=current_seq,
    )
    current_batch_id = make_batch_id("topdev", seq=current_seq, run_date=current_run_date)

    ssl_ctx = ssl.create_default_context()
    api_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Origin": "https://topdev.vn",
        "Referer": "https://topdev.vn/jobs/search",
    }

    # Đọc seen_ids từ checkpoint và SQLite catalog
    already_seen_ids = set(checkpoint.seen_ids)
    try:
        with catalog._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT job_id FROM job_state_catalog WHERE source = 'topdev'")
            for row in cursor.fetchall():
                already_seen_ids.add(str(row[0]))
    except Exception as exc:
        log.warning("Lỗi tra cứu SQLite catalog: %s", exc)

    log.info("Catalog & Checkpoint hiện có %d job_ids đã cào trước đó.", len(already_seen_ids))

    crawled_count = 0
    skipped_count = 0
    error_count = 0
    records_in_current_batch = 0

    for idx, target in enumerate(job_targets, 1):
        if max_items is not None and crawled_count >= max_items:
            log.info("Đã đạt giới hạn max_items = %d. Dừng Pha 2.", max_items)
            break

        job_id = target["job_id"]
        job_url = target["url"]

        if job_id in already_seen_ids:
            skipped_count += 1
            continue

        # Chuyển batch nếu vượt quá batch_size
        if records_in_current_batch >= batch_size:
            writer.close()
            current_seq += 1
            writer = JsonWriter(
                source="topdev",
                output_dir="data",
                run_date=current_run_date,
                batch_seq=current_seq,
            )
            current_batch_id = make_batch_id("topdev", seq=current_seq, run_date=current_run_date)
            records_in_current_batch = 0
            log.info("Mở batch mới: %s", current_batch_id)

        # Gọi API Chi tiết
        params = urllib.parse.urlencode({
            "locale": "vi_VN",
            "fields[job]": DETAIL_FIELDS,
            "fields[company]": "display_name",
        })
        api_url = f"https://api.topdev.vn/td/v2/jobs/{job_id}?{params}"
        req = urllib.request.Request(api_url, headers=api_headers)

        attempt = 0
        success = False
        raw_payload = None

        while attempt < 3 and not success:
            attempt += 1
            try:
                with urllib.request.urlopen(req, context=ssl_ctx, timeout=12) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    raw_payload = resp_data.get("data")
                    if isinstance(raw_payload, dict):
                        success = True
            except Exception as exc:
                if attempt == 3:
                    log.warning("[Job %s] Thất bại sau 3 lần gọi API: %s", job_id, exc)
                    error_count += 1
                    catalog.mark_job_failed_for_next_run("topdev", job_id, str(exc))
                time.sleep(1.5 * attempt)

        if not success or not raw_payload:
            continue

        try:
            # Tạo record theo Data Contract Schema v1
            rec_dict = _make_record(
                raw_payload,
                raw_payload,
                batch_id=current_batch_id,
                crawled_at=datetime.now(LOCAL_TIMEZONE),
            )
            if job_url:
                rec_dict["_meta"]["url"] = job_url

            record = JobRecord.model_validate(rec_dict)
            writer.write(record)
            checkpoint.mark_seen(job_id)
            catalog.mark_job_success("topdev", job_id, str(writer.file_path))
            already_seen_ids.add(job_id)
            crawled_count += 1
            records_in_current_batch += 1

            if crawled_count % 25 == 0:
                log.info(
                    "[Pha 2] [%d/%d] Đã cào thành công +%d tin (Trùng: %d, Lỗi: %d)",
                    idx,
                    len(job_targets),
                    crawled_count,
                    skipped_count,
                    error_count,
                )
                checkpoint.save()
        except Exception as exc:
            log.warning("[Job %s] Parse/Validate thất bại: %s", job_id, exc)
            error_count += 1

        time.sleep(delay)

    writer.close()
    checkpoint.save()
    log.info(
        "=== HOÀN TẤT PHA 2: Cào mới: %d, Bỏ qua trùng: %d, Lỗi: %d ===",
        crawled_count,
        skipped_count,
        error_count,
    )
    return crawled_count


def sync_and_merge() -> None:
    """Pha 3: Đồng bộ Catalog và Chạy PreClean Pipeline."""
    log.info("=== BẮT ĐẦU PHA 3: ĐỒNG BỘ CATALOG & HỢP NHẤT DATASET ===")

    # 1. Đồng bộ Catalog
    try:
        catalog = JobStateCatalog()
        updated = catalog.sync_from_batches(data_dir=str(PROJECT_ROOT / "data"), source="topdev")
        log.info("Đã đồng bộ %d records từ TopDev vào SQLite State Catalog.", updated)
    except Exception as exc:
        log.error("Lỗi khi đồng bộ catalog: %s", exc)

    # 2. Chạy PreClean Pipeline
    try:
        pipeline = PreCleanPipeline(
            data_dir=str(PROJECT_ROOT / "data"),
            output_clean_dir=str(PROJECT_ROOT / "data" / "processed" / "preClean"),
            queue_dir=str(PROJECT_ROOT / "data" / "queue"),
        )
        report = pipeline.run()
        log.info(
            "PreClean hoàn tất: Đọc %d records thô, Hợp nhất & Lọc sạch thành công: %d records!",
            report.get("total_processed", 0),
            report.get("cleaned_count", 0),
        )
        out_file = PROJECT_ROOT / "data" / "processed" / "preClean" / "merged_jobs_clean.json"
        log.info("File kết quả hợp nhất: %s", out_file)
    except Exception as exc:
        log.error("Lỗi khi chạy PreClean Pipeline: %s", exc)


def main() -> int:
    parser = argparse.ArgumentParser(description="Thu thập toàn bộ 2.822 tin tuyển dụng TopDev")
    parser.add_argument("--phase", type=int, choices=[1, 2, 3], help="Chạy riêng lẻ Pha 1, 2 hoặc 3")
    parser.add_argument("--start-page", type=int, default=1, help="Trang bắt đầu Pha 1")
    parser.add_argument("--max-pages", type=int, default=None, help="Số trang tối đa Pha 1")
    parser.add_argument("--max-items", type=int, default=None, help="Số tin tối đa Pha 2")
    parser.add_argument("--delay", type=float, default=1.0, help="Độ trễ giữa các request (giây)")
    parser.add_argument("--run-all", action="store_true", help="Chạy liền mạch cả 3 Pha")

    args = parser.parse_args()

    if args.run_all or args.phase == 1:
        harvest_listing_urls(start_page=args.start_page, max_pages=args.max_pages, delay=args.delay)

    if args.run_all or args.phase == 2:
        scrape_details(max_items=args.max_items, delay=args.delay)

    if args.run_all or args.phase == 3:
        sync_and_merge()

    return 0


if __name__ == "__main__":
    sys.exit(main())
