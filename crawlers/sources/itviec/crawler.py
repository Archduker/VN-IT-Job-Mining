# -*- coding: utf-8 -*-
"""Crawler ITViec — Two-Phase Decoupled (URL Discovery -> Detail Extraction), RAW-FIRST.

Tuân thủ chuẩn repo (docs/02 + skill crawling-architect) và yêu cầu TASKS.md (219d):
- Pha 1 discover_urls(): vét sạch link từ trang danh mục (không giới hạn thời gian),
  lưu vào UrlLedger + sync MinIO.
- Pha 2 crawl_details(): đọc ledger, lọc PENDING / (DONE >= 21 ngày), tải chi tiết,
  bảo toàn RAW (JSON-LD verbatim + sections text + file HTML), tính Clean Container
  SHA-256, phát hiện Repost, tăng version chỉ khi nội dung đổi, Safe Skip từng URL.
- Engine: Playwright headless (system chromium) là chính, TỰ FALLBACK sang requests
  (ITViec là SSR nên requests vẫn lấy đủ dữ liệu).
- Lưu trữ: local `data/itviec/{url_ledger,raw}/` theo layout MinIO, + sync MinIO non-fatal.

Chạy:
  python run.py --source itviec --phase detail --max-items 2
  python crawlers/sources/itviec/crawler.py --phase all --max-pages 1 --max-items 2
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Đảm bảo import được gói `crawlers.*` khi chạy trực tiếp file này.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from bs4 import BeautifulSoup

from crawlers.base.base_crawler import BaseCrawler
from crawlers.common.anti_blocking import (
    handle_cloudflare_backoff,
    human_like_interaction,
    is_cloudflare_challenge,
    polite_sleep,
)
from crawlers.common.url_ledger import (
    UrlLedger,
    calculate_container_html_hash,
    clean_canonical_url,
)
from crawlers.sources.itviec import config as C
from crawlers.sources.itviec import parser

log = logging.getLogger("itviec.crawler")

CLOSED_MARKERS = ("Không tìm thấy", "không tồn tại", "đã hết hạn", "không còn")


class ItviecCrawler(BaseCrawler):
    """Crawler ITViec theo mô hình 2 pha, raw-first, chống chặn bot lịch sự."""

    source_name = C.SOURCE
    crawler_version = C.CRAWLER_VERSION

    def __init__(
        self,
        checkpoint_dir: Optional[str] = None,
        output_dir: Optional[str] = None,
        max_items: Optional[int] = 5,
        checkpoint_interval: int = 10,
        headless: bool = True,
        save_html: bool = False,          # Mặc định KHÔNG lưu .html mỗi job (job-crawler-analyzer B5). Bật --save-html khi cần.
        min_delay: float = C.MIN_DELAY,
        max_delay: float = C.MAX_DELAY,
        browser_path: Optional[str] = C.BROWSER_PATH,
    ) -> None:
        # Chuẩn hóa gốc dữ liệu về data/itviec/ (dù run.py có truyền "data")
        root = (output_dir or "data").rstrip(os.sep)
        if os.path.basename(root) != C.SOURCE:
            root = os.path.join(root, C.SOURCE)
        super().__init__(
            checkpoint_dir=checkpoint_dir,
            output_dir=root,
            max_items=max_items,
            checkpoint_interval=checkpoint_interval,
        )
        self.headless = headless
        self.save_html = save_html
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.browser_path = browser_path
        self.raw_root = os.path.join(self.output_dir, "raw")
        self.ledger = UrlLedger(
            source=C.SOURCE,
            storage_dir=os.path.join(self.output_dir, "url_ledger"),
        )
        self.sync_mode = parser.sync_mode()
        if not self.sync_mode:
            log.info("[ITViec] ITVIEC_SYNC=0 -> CHẾ ĐỘ SIMULATION, sẽ KHÔNG sync MinIO.")

    # ── BaseCrawler interface (không dùng ở mô hình 2 pha; giữ để kế thừa hợp lệ) ──
    def fetch_items(self):  # pragma: no cover - unused in two-phase mode
        return iter(())

    def parse_item(self, item):  # pragma: no cover - unused in two-phase mode
        return None

    # ── Engine: Playwright (chính) -> requests (fallback) ─────────
    @contextlib.contextmanager
    def _fetcher(self):
        """Yield fetch(url)->(html, http_status). Playwright là chính, fallback requests.

        LUÔN teardown Playwright (pw.stop) trong finally để không rò asyncio loop
        giữa hai pha (tránh lỗi 'Sync API inside the asyncio loop').
        """
        from crawlers.common.http_client import DelayConfig, HttpClient, RetryConfig

        pw = browser = ctx = page = client = None
        use_playwright = True
        try:
            try:
                from playwright.sync_api import sync_playwright

                pw = sync_playwright().start()
                browser = pw.chromium.launch(
                    headless=self.headless,
                    executable_path=self.browser_path if (self.browser_path and os.path.exists(self.browser_path)) else None,
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
                )
                ctx = browser.new_context(
                    user_agent=C.USER_AGENT, locale="vi-VN", viewport={"width": 1280, "height": 900},
                )
                ctx.add_init_script("Object.defineProperty(navigator, ['web', 'driver'].join(''), {get: () => undefined})")
                page = ctx.new_page()
            except Exception as exc:
                log.warning("[ITViec] Playwright không khả dụng (%s) -> fallback requests.", exc)
                use_playwright = False
                client = HttpClient(
                    source=C.SOURCE,
                    retry_config=RetryConfig(raise_on_status=False),
                    delay_config=DelayConfig(min_seconds=self.min_delay, max_seconds=self.max_delay),
                )

            if use_playwright:
                def fetch(url: str):
                    page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    human_like_interaction(page, scroll_times=1)
                    content = page.content()
                    if is_cloudflare_challenge(content):
                        if handle_cloudflare_backoff(page, retry_attempt=1):
                            content = page.content()
                    return content, 200
            else:
                def fetch(url: str):
                    resp = client.get(url)  # HttpClient tự quản lý timeout
                    resp.encoding = resp.apparent_encoding or "utf-8"
                    return resp.text, resp.status_code

            yield fetch
        finally:
            for obj in (page, ctx, browser):
                try:
                    if obj is not None:
                        obj.close()
                except Exception:
                    pass
            try:
                if pw is not None:
                    pw.stop()
            except Exception:
                pass
            try:
                if client is not None:
                    client.close()
            except Exception:
                pass

    @staticmethod
    def _detect_hash_container(soup: BeautifulSoup) -> Optional[str]:
        for sel in C.DETAIL_HASH_CONTAINERS:
            if soup.select_one(sel):
                return sel
        return None

    @staticmethod
    def _sync_file_to_minio(local_path: str, object_key: str) -> Optional[str]:
        try:
            from crawlers.common.minio_storage import upload_file_to_minio

            return upload_file_to_minio(local_path, object_key)
        except Exception as exc:  # non-fatal
            log.warning("[ITViec] Bỏ qua sync MinIO %s: %s (dữ liệu local vẫn an toàn)", object_key, exc)
            return None

    def _guard_sync_minio(self) -> bool:
        """Sync catalog ITViec lên MinIO CÓ GUARD.

        Bỏ sync khi: (1) chế độ simulation (self.sync_mode False / env ITVIEC_SYNC=0);
        (2) catalog local rỗng; (3) local < remote (ledger tạm/ít -> không ghi đè ledger lớn hơn).
        Trả về True nếu đã gọi sync.
        """
        if not self.sync_mode or not parser.sync_mode():
            log.info("[ITViec] Bỏ ledger.sync_to_minio (simulation / ITVIEC_SYNC=0).")
            return False
        lc = parser.local_catalog_count(self.ledger)
        if lc <= 0:
            log.info("[ITViec] Bỏ ledger.sync_to_minio: catalog local rỗng.")
            return False
        rc = parser.remote_catalog_count(self.ledger)
        if not parser.can_upload_catalog(lc, rc):
            log.warning("[ITViec] Bỏ ledger.sync_to_minio: local=%d < remote=%s (không ghi đè).", lc, rc)
            return False
        self.ledger.sync_to_minio()
        return True

    def _discover_from_sitemaps(self) -> int:
        """Bổ sung URL việc làm từ sitemap VN (twinnings_jobs_*_vn.xml).

        Vượt trần ~660 của listing phân trang; sitemap expose ~1.5k job URL.
        Sitemap là XML tĩnh nên dùng requests (khỏi Playwright). Trả về số URL MỚI ghi nhận.
        """
        import requests
        headers = {"User-Agent": C.USER_AGENT}
        try:
            idx = requests.get(C.SITEMAP_URL, headers=headers, timeout=30)
            children = parser.parse_sitemap(idx.text)
        except Exception as exc:
            log.error("[ITViec] Không đọc được sitemap index (%s): %s", C.SITEMAP_URL, exc)
            return 0
        job_maps = [u for u in children if "job" in u.lower() and "_vn" in u.lower()]
        log.info("[ITViec] Sitemap: %d child, %d job-sitemap VN", len(children), len(job_maps))

        new = 0
        for sm in job_maps:
            try:
                polite_sleep(self.min_delay, self.max_delay, reason=f"job-sitemap {sm}")
                r = requests.get(sm, headers=headers, timeout=45)
                locs = [l for l in parser.parse_sitemap(r.text) if C.DETAIL_PATH_PREFIX in l]
            except Exception as exc:
                log.warning("[ITViec] Lỗi đọc job-sitemap %s: %s", sm, exc)
                continue
            jobs, non_jobs = parser.filter_job_urls(locs)
            page_new = 0
            for loc in jobs:
                canonical = clean_canonical_url(loc)
                before = len(self.ledger.records)
                self.ledger.register_url(
                    raw_url=canonical,
                    job_id=parser.extract_job_id(canonical),
                    preliminary_title=None,
                    preliminary_company=None,
                )
                if len(self.ledger.records) > before:
                    page_new += 1
            new += page_new
            self.ledger.save_catalog()
            log.info("[ITViec]   %s: %d URL (%d tin hợp lệ + %d trang chuyên mục bị lọc), +%d mới", sm, len(locs), len(jobs), len(non_jobs), page_new)
        return new

    # ── PHA 1: URL DISCOVERY ─────────────────────────────────────
    def discover_urls(self, max_pages: Optional[int] = None) -> int:
        log.info("[ITViec] === Pha 1: URL Discovery ===")
        total = 0
        curr = 1
        consecutive_empty = 0
        with self._fetcher() as fetch:
            while True:
                if max_pages and curr > max_pages:
                    break
                target = C.LISTING_PAGE_TEMPLATE.format(page=curr)
                log.info("[ITViec] Quét danh mục trang %d: %s", curr, target)
                try:
                    html, _ = fetch(target)
                    jobs = parser.parse_listing(html)
                except Exception as exc:
                    log.error("[ITViec] Lỗi đọc trang danh mục %d: %s", curr, exc)
                    jobs = []

                if not jobs:
                    consecutive_empty += 1
                    if consecutive_empty >= 2:
                        log.info("[ITViec] Hết danh mục (trang %d trống). Dừng.", curr)
                        break
                    curr += 1
                    continue
                consecutive_empty = 0

                new = 0
                skipped_nonjob = 0
                for j in jobs:
                    canonical = clean_canonical_url(j["url"])
                    if not parser.is_job_url(canonical):     # C: chỉ ghi URL là tin thật
                        skipped_nonjob += 1
                        continue
                    before = len(self.ledger.records)
                    self.ledger.register_url(
                        raw_url=canonical,
                        job_id=j["job_id"],
                        preliminary_title=j.get("title"),
                        preliminary_company=j.get("company"),
                    )
                    if len(self.ledger.records) > before:
                        new += 1
                        total += 1

                self.ledger.save_catalog()
                log.info("[ITViec] Trang %d: %d card (%d link mới, %d không phải tin). Ledger: %d", curr, len(jobs), new, skipped_nonjob, len(self.ledger.records))

                if curr % 5 == 0:
                    self.ledger.export_daily_manifest()
                    self._guard_sync_minio()

                curr += 1
                polite_sleep(self.min_delay, self.max_delay, reason=f"Chuyển trang danh mục {curr}")

        s_new = self._discover_from_sitemaps()
        total += s_new
        self.ledger.save_catalog()
        manifest = self.ledger.export_daily_manifest()
        self._guard_sync_minio()
        log.info("[ITViec] Pha 1 xong. Tổng %d URL ghi nhận (gồm %d từ sitemap) -> %s", total, s_new, manifest)
        return total

    # ── PHA 2: DETAIL EXTRACTION ─────────────────────────────────
    def crawl_details(self, limit: Optional[int] = None, force: bool = False,
                      only_job_ids: Optional[List[str]] = None) -> Dict[str, int]:
        log.info("[ITViec] === Pha 2: Detail Extraction (Re-crawl %d ngày%s) ===",
                 C.RECHECK_DAYS, " [FORCE]" if force else "")
        if only_job_ids:
            wanted = set(only_job_ids)
            pending = [r for r in self.ledger.records.values() if r.get("job_id") in wanted]
        elif force:
            pending = list(self.ledger.records.values())
        else:
            pending = self.ledger.get_pending_or_due_records(recheck_days=C.RECHECK_DAYS)
        log.info("[ITViec] %d link cần xử lý trong Ledger.", len(pending))

        stats = {"processed_urls": 0, "scanned": 0, "crawled_new": 0, "new_job_ids": 0,
                 "closed": 0, "repost": 0, "unchanged": 0, "dup_job_id": 0, "non_job_url": 0, "errors": 0}
        new_jobids: set = set()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        dest_dir = os.path.join(self.raw_root, today)
        os.makedirs(dest_dir, exist_ok=True)

        count = 0        # số URL tin HỢP LỆ đã xử lý -> mới tính vào --max-items
        scanned = 0      # số mục đã duyệt (kể cả rác) -> KHÔNG đốt ngân sách limit
        with self._fetcher() as fetch:
            for item in pending:
                if limit and count >= limit:
                    break
                scanned += 1
                url = item["canonical_url"]
                url_hash = item["url_hash"]
                job_id = item["job_id"]
                try:
                    stats["processed_urls"] += 1
                    if not parser.is_job_url(url):            # C: không cào trang chuyên mục
                        stats["non_job_url"] += 1
                        log.warning("[ITViec] Bỏ KHÔNG phải tin tuyển dụng job_id=%s url=%s", job_id, url)
                        continue
                    # C: URL trùng job_id đã cào thành công -> bỏ, giữ ledger PENDING (chưa đổi trạng thái)
                    if (not force) and job_id in new_jobids:
                        stats["dup_job_id"] += 1
                        log.info("[ITViec] Bỏ URL trùng job_id=%s (đã cào) url=%s", job_id, url)
                        count += 1
                        polite_sleep(self.min_delay, self.max_delay, reason="Trùng job_id")
                        continue
                    log.info("[ITViec] [%d] Chi tiết job_id=%s url=%s", count + 1, job_id, url)
                    html, status = fetch(url)
                    soup = BeautifulSoup(html, "html.parser")

                    if status == 404 or any(m in html for m in CLOSED_MARKERS):
                        self.ledger.mark_closed(url_hash)
                        stats["closed"] += 1
                        log.warning("[ITViec] CLOSED (hết hạn/không tồn tại) job_id=%s url=%s http=%s", job_id, url, status)
                        count += 1
                        continue

                    raw_payload = parser.parse_detail(html, job_id)
                    if soup.select_one(C.JD_HASH_CONTAINER):
                        container = C.JD_HASH_CONTAINER
                    else:
                        container = self._detect_hash_container(soup) or "body"
                    new_hash = parser.compute_content_hash(
                        html, raw_payload.get("job_posting_jsonld"),
                        container_selector=container,
                    )
                    log.info("[ITViec] Hash algo=%s container=%s len=%d",
                             C.CONTENT_HASH_ALGO, container, len(new_hash))

                    existing = self.ledger.find_by_content_hash(new_hash)
                    if existing and existing["url_hash"] != url_hash:
                        self.ledger.mark_done(url_hash, content_hash=new_hash, repost_of_url_hash=existing["url_hash"])
                        stats["repost"] += 1
                        count += 1
                        log.info("[ITViec] REPOST job_id=%s url=%s repost_of=%s", job_id, url, existing["url_hash"][:8])
                        polite_sleep(self.min_delay, self.max_delay, reason="Repost skip")
                        continue

                    curr_ver = item.get("latest_version") or 0
                    prev_hash = item.get("content_hash")
                    # Nội dung không đổi (đã có version và hash trùng) -> KHÔNG tạo snapshot mới
                    # (ngoại lệ: --force để vá bản đã cào, vẫn ghi version MỚI, không ghi đè).
                    if (not force) and curr_ver > 0 and prev_hash == new_hash:
                        self.ledger.mark_done(url_hash, content_hash=new_hash)
                        stats["unchanged"] += 1
                        count += 1
                        log.info("[ITViec] UNCHANGED job_id=%s url=%s", job_id, url)
                        polite_sleep(self.min_delay, self.max_delay, reason="Nội dung không đổi")
                        continue

                    new_ver = curr_ver + 1
                    tracked = sorted(k for k in C.HASH_JSONLD_FIELDS if k in (raw_payload.get("job_posting_jsonld") or {}))
                    envelope = {
                        "metadata": {
                            "job_id": job_id,
                            "source": C.SOURCE,
                            "source_url": url,
                            "scraped_at": datetime.now(timezone.utc).isoformat(),
                            "scraper_version": C.CRAWLER_VERSION,
                            "version": new_ver,
                            "content_hash": new_hash,
                            "content_hash_algo": C.CONTENT_HASH_ALGO,
                            "hash_container": container or "body",
                            "hash_jsonld_fields": tracked,
                            "http_status": status,
                        },
                        "raw_payload": raw_payload,
                    }
                    dest_file = os.path.join(dest_dir, f"{job_id}_v{new_ver}.json")
                    with open(dest_file, "w", encoding="utf-8") as f:
                        json.dump(envelope, f, ensure_ascii=False, indent=2)

                    html_file = None
                    if self.save_html:
                        html_file = os.path.join(dest_dir, f"{job_id}_v{new_ver}.html")
                        with open(html_file, "w", encoding="utf-8") as f:
                            f.write(html)

                    self.ledger.mark_done(url_hash, content_hash=new_hash, new_version=new_ver)
                    stats["crawled_new"] += 1
                    if job_id not in new_jobids:
                        new_jobids.add(job_id); stats["new_job_ids"] += 1
                    count += 1
                    log.info("[ITViec] OK job_id=%s -> %s v%d url=%s", job_id, os.path.basename(dest_file), new_ver, url)

                    # D4: chỉ đồng bộ snapshot + HTML lên MinIO khi có VERSION mới
                    self._sync_file_to_minio(dest_file, f"{C.MINIO_RAW_PREFIX}{today}/{job_id}_v{new_ver}.json")
                    if C.SYNC_HTML and html_file:
                        self._sync_file_to_minio(html_file, f"{C.MINIO_HTML_PREFIX}{today}/{job_id}_v{new_ver}.html")

                    # D5: flush ledger định kỳ để an toàn khi gián đoạn (tránh cào lại)
                    if count % C.LEDGER_FLUSH_EVERY == 0:
                        self.ledger.save_catalog()
                    if count % C.LEDGER_MINIO_SYNC_EVERY == 0:
                        self._guard_sync_minio()

                    polite_sleep(self.min_delay, self.max_delay, reason=f"Nghỉ giữa tin {count}")
                except Exception as exc:
                    log.error("[ITViec] LỖI job_id=%s url=%s: %s -> Safe Skip.", job_id, url, exc)
                    self.ledger.mark_failed(url_hash, str(exc))
                    stats["errors"] += 1

        self.ledger.save_catalog()
        self._guard_sync_minio()
        stats["output_dir"] = dest_dir
        stats["scanned"] = scanned
        log.info("[ITViec] === Tổng kết Pha 2: %s ===", stats)
        return stats


def main() -> None:
    ap = argparse.ArgumentParser(description="ITViec Two-Phase Crawler (Discovery & Detail), Raw-First")
    ap.add_argument("--phase", choices=["all", "discovery", "details"], default="all")
    ap.add_argument("--max-pages", type=int, default=None, help="Số trang danh mục ở Pha 1 (mặc định: hết)")
    ap.add_argument("--max-items", type=int, default=5, help="Số tin chi tiết ở Pha 2")
    ap.add_argument("--min-delay", type=float, default=C.MIN_DELAY)
    ap.add_argument("--max-delay", type=float, default=C.MAX_DELAY)
    ap.add_argument("--output-dir", type=str, default="data/itviec")
    ap.add_argument("--save-html", action="store_true", help="Lưu file HTML thô mỗi job (mặc định TẮT)")
    ap.add_argument("--force", action="store_true", help="Cào lại cả bản đã DONE -> tạo VERSION mới (append, không ghi đè)")
    ap.add_argument("--only-job-ids", type=str, default=None, help="Chỉ cào các job_id (phân tách dấu phẩy) — dùng cho bản vá/targeted")
    ap.add_argument("--log-file", type=str, default=None, help="Đường dẫn log file (mặc định logs/itviec_<run_id>.log)")
    args = ap.parse_args()

    # B: log RIÊNG từng lần chạy -> logs/itviec_<timestamp>.log (+ run_id), không ghi đè
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_dir = os.path.join(REPO_ROOT, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = args.log_file or os.path.join(log_dir, f"itviec_{run_id}.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler()],
    )
    log.info("[ITViec] run_id=%s phase=%s -> log=%s", run_id, args.phase, log_file)
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(REPO_ROOT, ".env"))
    except Exception:
        pass

    crawler = ItviecCrawler(
        output_dir=args.output_dir,
        max_items=args.max_items,
        save_html=args.save_html,
        min_delay=args.min_delay,
        max_delay=args.max_delay,
    )
    if args.phase == "discovery":
        print("Pha 1:", crawler.discover_urls(max_pages=args.max_pages), "URL")
    elif args.phase == "details":
        only = [x.strip() for x in args.only_job_ids.split(",")] if args.only_job_ids else None
        print("Pha 2:", crawler.crawl_details(limit=args.max_items, force=args.force, only_job_ids=only))
    else:
        crawler.discover_urls(max_pages=args.max_pages or 1)
        print("All:", crawler.crawl_details(limit=args.max_items))


if __name__ == "__main__":
    main()
