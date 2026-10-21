# -*- coding: utf-8 -*-
"""Crawler ITViec — Two-Phase Decoupled (URL Discovery -> Detail Extraction), RAW-FIRST.

Tuân thủ nghiêm ngặt chuẩn Modern Data Stack (docs/crawler_output_checklist.md &
docs/two_phase_minio_crawler_playbook.md):
1. Hai pha độc lập: Pha 1 discover_urls() & Pha 2 crawl_details().
2. Pha 1: URL ban đầu hoàn toàn chưa có hash (content_hash = None, status = "PENDING").
3. Pha 2: Kéo URL từ MinIO về máy trước khi lọc URL (ledger.pull_from_minio()).
4. Băm toàn vẹn Document JSON sau cào (calculate_json_canonical_hash & calculate_json_field_hashes).
5. Lưu ngược lại hash vào cả URL trong Ledger lẫn file Raw Snapshot (metadata.content_hash, canonical_hash, field_hashes).
6. Cơ chế Safe Skip & Failed Queue (ledger.mark_failed, cờ CLI --retry-failed).
7. Checkpoint Sync định kỳ (mỗi 15 tin tự động lưu & sync MinIO Lakehouse).
8. Chống chặn bot: Polite sleep ngẫu nhiên 2.0s - 4.5s.
9. Đầy đủ các cờ CLI chuẩn: --phase {discovery, details, sync, view}, --online, --sync-minio, --retry-failed, --limit, --local-html-dir.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
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
from crawlers.common.http_client import DelayConfig, HttpClient, RetryConfig
from crawlers.common.minio_raw_pipeline import MinioRawStore
from crawlers.common.url_ledger import (
    UrlLedger,
    calculate_json_canonical_hash,
    calculate_json_field_hashes,
    clean_canonical_url,
)
from crawlers.sources.itviec import config as C
from crawlers.sources.itviec import parser

log = logging.getLogger("itviec.crawler")

CLOSED_MARKERS = ("Không tìm thấy", "không tồn tại", "đã hết hạn", "không còn")


class ItviecCrawler(BaseCrawler):
    """Crawler ITViec theo kiến trúc 2 pha chuẩn Modern Data Stack."""

    source_name = C.SOURCE
    crawler_version = C.CRAWLER_VERSION

    def __init__(
        self,
        checkpoint_dir: Optional[str] = None,
        output_dir: Optional[str] = None,
        max_items: Optional[int] = None,
        limit: Optional[int] = None,
        checkpoint_interval: int = 15,
        headless: bool = True,
        save_html: bool = False,
        min_delay: float = C.MIN_DELAY,
        max_delay: float = C.MAX_DELAY,
        browser_path: Optional[str] = C.BROWSER_PATH,
        ledger_dir: Optional[str] = None,
        raw_dir: Optional[str] = None,
        sync_minio: bool = False,
        local_html_dir: Optional[str] = None,
        auth_file: Optional[str] = None,
        use_playwright: bool = False,
    ) -> None:
        root = (output_dir or "data/itviec").rstrip(os.sep)
        if os.path.basename(root) != C.SOURCE:
            root = os.path.join(root, C.SOURCE)

        effective_limit = limit if limit is not None else max_items
        super().__init__(
            checkpoint_dir=checkpoint_dir,
            output_dir=root,
            max_items=effective_limit,
            checkpoint_interval=checkpoint_interval,
        )
        self.headless = headless
        self.save_html = save_html
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.browser_path = browser_path
        self.local_html_dir = local_html_dir
        self.sync_minio = sync_minio
        self.use_playwright = use_playwright

        self.ledger_dir = ledger_dir or os.path.join(self.output_dir, "url_ledger")
        self.raw_root = raw_dir or os.path.join(self.output_dir, "raw")
        self.auth_file = auth_file or os.path.join(self.output_dir, "auth", "session.json")
        os.makedirs(self.ledger_dir, exist_ok=True)
        os.makedirs(self.raw_root, exist_ok=True)
        os.makedirs(os.path.dirname(self.auth_file), exist_ok=True)

        self._ledger = None
        self._minio_store = None

    def _load_session_cookies(self) -> list[dict[str, Any]]:
        """Nạp danh sách cookie phiên từ auth_file (định dạng Playwright storage_state)."""
        if os.path.isfile(self.auth_file):
            try:
                with open(self.auth_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                cookies = data.get("cookies", [])
                log.info("[ITViec] Đã nạp %d cookies phiên làm việc từ: %s", len(cookies), self.auth_file)
                return cookies
            except Exception as exc:
                log.warning("[ITViec] Không thể đọc auth session %s: %s", self.auth_file, exc)
        return []

    def login_interactive(self, timeout_seconds: int = 120) -> bool:
        """Mở trình duyệt Playwright có giao diện để người dùng đăng nhập tài khoản ITViec (Google/Email).
        Tự động phát hiện phiên đăng nhập thành công và lưu cookies vào auth_file.
        """
        import time
        from playwright.sync_api import sync_playwright

        os.makedirs(os.path.dirname(self.auth_file), exist_ok=True)
        print("\n" + "=" * 65)
        print(" 🔑 TRÌNH ĐĂNG NHẬP ITVIEC (INTERACTIVE AUTHENTICATION)")
        print(" Đang mở trình duyệt Chromium có giao diện...")
        print(" Vui lòng thao tác đăng nhập tài khoản ITViec (bằng Google hoặc Email/Mật khẩu)")
        print(f" Phiên làm việc sẽ được lưu tự động vào: {self.auth_file}")
        print(f" Thời gian chờ tối đa: {timeout_seconds} giây")
        print("=" * 65 + "\n")

        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=False,
                    executable_path=self.browser_path if (self.browser_path and os.path.exists(self.browser_path)) else None,
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
                )
                ctx = browser.new_context(
                    user_agent=C.USER_AGENT,
                    locale="vi-VN",
                    viewport={"width": 1280, "height": 900},
                )
                ctx.add_init_script("Object.defineProperty(navigator, ['web', 'driver'].join(''), {get: () => undefined})")
                page = ctx.new_page()
                page.goto("https://itviec.com/sign_in", wait_until="domcontentloaded")

                start = time.time()
                logged_in = False
                while time.time() - start < timeout_seconds:
                    cookies = ctx.cookies()
                    has_session = any(c.get("name") in ("_itviec_session", "remember_user_token") for c in cookies)
                    cur_url = page.url
                    if has_session and "sign_in" not in cur_url:
                        logged_in = True
                        break
                    time.sleep(1.5)

                if logged_in or any(c.get("name") in ("_itviec_session", "remember_user_token") for c in ctx.cookies()):
                    ctx.storage_state(path=self.auth_file)
                    print(f"\n✅ ĐĂNG NHẬP THÀNH CÔNG! Đã lưu phiên làm việc vào: {self.auth_file}")
                    browser.close()
                    return True
                else:
                    print(f"\n⚠️ Hết {timeout_seconds}s hoặc chưa phát hiện đăng nhập thành công.")
                    browser.close()
                    return False
        except Exception as exc:
            print(f"\n❌ Lỗi khi mở trình duyệt đăng nhập: {exc}")
            return False

    def _get_ledger(self) -> UrlLedger:
        if self._ledger is None:
            self._ledger = UrlLedger(source=C.SOURCE, storage_dir=self.ledger_dir)
        return self._ledger

    @property
    def ledger(self) -> UrlLedger:
        return self._get_ledger()

    def _get_minio_store(self) -> MinioRawStore:
        if self._minio_store is None:
            self._minio_store = MinioRawStore()
        return self._minio_store

    def sync_ledger_to_minio(self) -> bool:
        """Đồng bộ catalog_master và manifests lên MinIO Lakehouse."""
        return self.ledger.sync_to_minio()

    def view_ledger(self) -> dict[str, int]:
        """Tóm tắt trạng thái URL Ledger hiện tại."""
        counts: dict[str, int] = {}
        for rec in self.ledger.records.values():
            st = rec.get("status", "?")
            counts[st] = counts.get(st, 0) + 1
        print(f"\n========================================================")
        print(f" URL LEDGER SUMMARY — NGUỒN: {self.source_name.upper()}")
        print(f" Tổng số URL trong ledger: {len(self.ledger.records)}")
        for st, c in sorted(counts.items()):
            print(f"   • Trạng thái {st:<12}: {c} tin")
        print(f"========================================================\n")
        return counts

    # ── BaseCrawler interface (giữ tính tương thích kế thừa) ──────
    def fetch_items(self):  # pragma: no cover
        return iter(())

    def parse_item(self, item):  # pragma: no cover
        return None

    # ── Engine: HttpClient (nhanh, chuẩn SSR) -> fallback Playwright ──
    @contextlib.contextmanager
    def _fetcher(self, use_playwright: bool = False):
        """Yield fetch(url) -> (html, status_code)."""
        cookies = self._load_session_cookies()
        effective_pw = use_playwright or self.use_playwright

        if not effective_pw:
            client = HttpClient(
                source=C.SOURCE,
                retry_config=RetryConfig(raise_on_status=False),
                delay_config=DelayConfig(min_seconds=self.min_delay, max_seconds=self.max_delay),
                extra_headers={"Accept-Encoding": "gzip, deflate"},
            )
            if cookies:
                for c in cookies:
                    client._session.cookies.set(
                        c["name"],
                        c["value"],
                        domain=c.get("domain", ".itviec.com"),
                        path=c.get("path", "/"),
                    )
                log.info("[ITViec] Đã nạp %d cookies đăng nhập vào HttpClient.", len(cookies))
            try:
                def fetch_http(url: str):
                    resp = client.get(url)
                    resp.encoding = resp.apparent_encoding or "utf-8"
                    content = resp.text
                    if is_cloudflare_challenge(content):
                        log.warning("[ITViec] Phát hiện Cloudflare challenge khi gọi HTTP: %s", url)
                    return content, resp.status_code

                yield fetch_http
            finally:
                client.close()
            return

        # Playwright fallback khi cần mô phỏng trình duyệt có JS
        pw = browser = ctx = page = None
        try:
            from playwright.sync_api import sync_playwright

            pw = sync_playwright().start()
            browser = pw.chromium.launch(
                headless=self.headless,
                executable_path=self.browser_path if (self.browser_path and os.path.exists(self.browser_path)) else None,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            storage = self.auth_file if (self.auth_file and os.path.isfile(self.auth_file)) else None
            ctx = browser.new_context(
                storage_state=storage,
                user_agent=C.USER_AGENT,
                locale="vi-VN",
                viewport={"width": 1280, "height": 900},
            )
            if storage:
                log.info("[ITViec] Đã nạp storage_state vào Playwright: %s", storage)
            ctx.add_init_script("Object.defineProperty(navigator, ['web', 'driver'].join(''), {get: () => undefined})")
            page = ctx.new_page()

            def fetch_pw(url: str):
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                human_like_interaction(page, scroll_times=1)
                content = page.content()
                if is_cloudflare_challenge(content):
                    if handle_cloudflare_backoff(page, retry_attempt=1):
                        content = page.content()
                return content, 200

            yield fetch_pw
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

    def _discover_from_sitemaps(self, client: Optional[HttpClient] = None) -> int:
        """Quét bổ sung URL việc làm từ sitemap VN (twinnings_jobs_*_vn.xml).

        Sitemap là XML tĩnh nên HttpClient đọc cực nhanh. Trả về số URL MỚI ghi nhận.
        """
        import requests
        headers = {"User-Agent": C.USER_AGENT}
        try:
            r = requests.get(C.SITEMAP_URL, headers=headers, timeout=30)
            children = parser.parse_sitemap(r.text)
        except Exception as exc:
            log.error("[ITViec] Không đọc được sitemap index (%s): %s", C.SITEMAP_URL, exc)
            return 0

        job_maps = [u for u in children if "job" in u.lower() and "_vn" in u.lower()]
        log.info("[ITViec] Sitemap index: %d file con, phát hiện %d job-sitemap VN", len(children), len(job_maps))

        new_count = 0
        for sm in job_maps:
            try:
                polite_sleep(self.min_delay, self.max_delay, reason=f"Đọc job-sitemap {sm}")
                resp = requests.get(sm, headers=headers, timeout=45)
                locs = [l for l in parser.parse_sitemap(resp.text) if C.DETAIL_PATH_PREFIX in l]
            except Exception as exc:
                log.warning("[ITViec] Lỗi đọc job-sitemap %s: %s", sm, exc)
                continue

            jobs, non_jobs = parser.filter_job_urls(locs)
            page_new = 0
            for loc in jobs:
                canonical = clean_canonical_url(loc)
                before = len(self.ledger.records)
                # Pha 1: Ban đầu hoàn toàn CHƯA CÓ HASH (content_hash=None, status="PENDING")
                self.ledger.register_url(
                    raw_url=canonical,
                    job_id=parser.extract_job_id(canonical),
                    preliminary_title=None,
                    preliminary_company=None,
                )
                if len(self.ledger.records) > before:
                    page_new += 1
            new_count += page_new
            self.ledger.save_catalog()
            log.info("[ITViec]   Sitemap %s: %d link (%d tin hợp lệ, +%d mới). Ledger: %d",
                     sm, len(locs), len(jobs), page_new, len(self.ledger.records))
        return new_count

    # ── PHA 1: URL DISCOVERY ─────────────────────────────────────
    def discover_urls(
        self,
        online: bool = False,
        max_pages: Optional[int] = None,
        sync_minio: bool = False,
    ) -> int:
        """Pha 1: Quét danh mục và sitemap, URL ban đầu chưa có hash, đồng bộ MinIO."""
        log.info("[ITViec] === PHA 1: URL DISCOVERY (Online=%s, MaxPages=%s) ===", online, max_pages)
        if not online:
            log.info("[ITViec] Discovery OFFLINE: Không gọi mạng. Số URL hiện có trong Ledger: %d", len(self.ledger.records))
            return len(self.ledger.records)

        total_new = 0
        curr = 1
        consecutive_empty = 0
        with self._fetcher(use_playwright=False) as fetch:
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
                        log.info("[ITViec] Kết thúc phân trang danh mục (trang %d trống liên tiếp).", curr)
                        break
                    curr += 1
                    continue
                consecutive_empty = 0

                page_new = 0
                for j in jobs:
                    canonical = clean_canonical_url(j["url"])
                    if not parser.is_job_url(canonical):
                        continue
                    before = len(self.ledger.records)
                    # Ban đầu chưa có hash, status = PENDING
                    self.ledger.register_url(
                        raw_url=canonical,
                        job_id=j["job_id"],
                        preliminary_title=j.get("title"),
                        preliminary_company=j.get("company"),
                    )
                    if len(self.ledger.records) > before:
                        page_new += 1
                        total_new += 1

                self.ledger.save_catalog()
                log.info("[ITViec] Trang %d: %d tin (+%d mới). Ledger hiện tại: %d",
                         curr, len(jobs), page_new, len(self.ledger.records))

                if curr % 5 == 0:
                    self.ledger.export_daily_manifest()
                    if self.sync_minio or sync_minio:
                        self.ledger.sync_to_minio()

                curr += 1
                polite_sleep(self.min_delay, self.max_delay, reason=f"Chuyển trang danh mục {curr}")

        # Quét bổ sung từ sitemaps để vét sạch toàn bộ việc làm
        s_new = self._discover_from_sitemaps()
        total_new += s_new

        self.ledger.save_catalog()
        manifest = self.ledger.export_daily_manifest()
        if self.sync_minio or sync_minio:
            self.ledger.sync_to_minio()

        log.info("[ITViec] Pha 1 hoàn thành. Tổng cộng %d URL trong Ledger (+%d mới). Manifest: %s",
                 len(self.ledger.records), total_new, manifest)
        return len(self.ledger.records)

    # ── PHA 2: DETAIL EXTRACTION & POST-CRAWL HASHING ────────────
    def crawl_details(
        self,
        limit: Optional[int] = None,
        local_html_dir: Optional[str] = None,
        online: bool = False,
        sync_minio: bool = False,
        retry_failed: bool = False,
        force: bool = False,
        only_job_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Pha 2: Kéo URL từ MinIO về máy, cào chi tiết, băm Document JSON, lưu ngược hash."""
        do_sync = self.sync_minio or sync_minio
        log.info("[ITViec] === PHA 2: DETAIL EXTRACTION (Online=%s, SyncMinIO=%s, RetryFailed=%s, Limit=%s) ===",
                 online, do_sync, retry_failed, limit)

        # 1. Kéo Catalog mới nhất từ MinIO Lakehouse về máy
        if do_sync and online:
            log.info("[ITViec] Đang kéo catalog mới nhất từ MinIO Lakehouse (pull_from_minio)...")
            try:
                self.ledger.pull_from_minio()
            except Exception as exc:
                log.warning("[ITViec] Không thể kéo ledger từ MinIO (%s), dùng ledger local hiện tại.", exc)

        # 2. Lọc danh sách cần cào
        if only_job_ids:
            wanted = set(only_job_ids)
            candidates = [r for r in self.ledger.records.values() if r.get("job_id") in wanted]
        elif retry_failed:
            candidates = self.ledger.get_failed_records()
            log.info("[ITViec] Chế độ RETRY FAILED: %d tin trong hàng đợi lỗi.", len(candidates))
        elif force:
            candidates = list(self.ledger.records.values())
            log.info("[ITViec] Chế độ FORCE: cào lại toàn bộ %d tin.", len(candidates))
        else:
            candidates = self.ledger.get_pending_or_due_records(recheck_days=C.RECHECK_DAYS)
            log.info("[ITViec] Chế độ TIÊU CHUẨN: %d tin cần xử lý (PENDING hoặc quá 21 ngày).", len(candidates))

        if not online and not local_html_dir:
            print(f"[details] PREVIEW MODE (chưa bật --online / chưa có --local-html-dir):")
            print(f"  • Số tin ứng viên sẵn sàng cào: {len(candidates)}")
            print(f"  • Chạy với cờ --online để bắt đầu cào thực tế.")
            return {"candidate_count": len(candidates), "mode": "preview"}

        effective_limit = limit if limit is not None else self.max_items
        if effective_limit:
            candidates = candidates[:effective_limit]
            log.info("[ITViec] Áp dụng giới hạn limit = %d tin.", effective_limit)

        stats = {
            "processed_urls": 0,
            "crawled_new": 0,
            "repost": 0,
            "unchanged": 0,
            "closed": 0,
            "errors": 0,
        }
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        dest_dir = os.path.join(self.raw_root, today)
        os.makedirs(dest_dir, exist_ok=True)

        with self._fetcher(use_playwright=False) as fetch:
            for idx, rec in enumerate(candidates, 1):
                url = rec["canonical_url"]
                url_hash = rec["url_hash"]
                job_id = rec["job_id"]
                stats["processed_urls"] += 1

                try:
                    log.info("[ITViec] [%d/%d] Đang xử lý job_id=%s url=%s", idx, len(candidates), job_id, url)
                    html = ""
                    status_code = 200

                    # Tải nội dung HTML: offline từ local dir HOẶC online qua HttpClient
                    if local_html_dir:
                        local_path = Path(local_html_dir) / f"{job_id}.html"
                        if not local_path.is_file():
                            # Thử tìm file có đuôi _v*.html hoặc file đầu tiên khớp job_id
                            matches = list(Path(local_html_dir).glob(f"{job_id}*.html"))
                            if matches:
                                local_path = matches[0]
                            else:
                                raise FileNotFoundError(f"Không tìm thấy file HTML cục bộ cho job_id {job_id} trong {local_html_dir}")
                        html = local_path.read_text(encoding="utf-8")
                    else:
                        html, status_code = fetch(url)

                    # Kiểm tra trang bị đóng hoặc 404
                    if status_code == 404 or any(m in html for m in CLOSED_MARKERS):
                        self.ledger.mark_closed(url_hash)
                        stats["closed"] += 1
                        log.warning("[ITViec] CLOSED job_id=%s (HTTP %s hoặc chứa thông báo hết hạn).", job_id, status_code)
                        continue

                    # Bóc tách Document JSON (Zero Information Loss)
                    raw_payload = parser.parse_detail(html, job_id)

                    sal_txt = str(raw_payload.get("salary_display_text") or "").lower()
                    if "đăng nhập để" in sal_txt or "sign in to view" in sal_txt:
                        log.warning("[ITViec] ⚠️ CẢNH BÁO PHIÊN ĐĂNG NHẬP: job_id=%s yêu cầu '%s'. Session cookie có thể đã hết hạn!",
                                    job_id, raw_payload.get("salary_display_text"))

                    # Băm toàn vẹn Document JSON sau cào (Post-Crawl Canonical JSON Hashing & CDC)
                    canonical_hash = calculate_json_canonical_hash(raw_payload, exclude_keys=["raw_html"])
                    field_hashes = calculate_json_field_hashes(raw_payload)

                    # Kiểm tra bài đăng lặp (Repost Detection)
                    existing = self.ledger.find_by_content_hash(canonical_hash)
                    if existing and existing["url_hash"] != url_hash:
                        self.ledger.mark_done(url_hash, content_hash=canonical_hash, repost_of_url_hash=existing["url_hash"])
                        stats["repost"] += 1
                        log.info("[ITViec] REPOST phát hiện: job_id=%s trùng nội dung với url_hash=%s",
                                 job_id, existing["url_hash"][:8])
                        polite_sleep(self.min_delay, self.max_delay, reason="Repost skip delay")
                        continue

                    # Kiểm tra nội dung không đổi
                    curr_ver = rec.get("latest_version") or 0
                    prev_hash = rec.get("content_hash")
                    if (not force) and curr_ver > 0 and prev_hash == canonical_hash:
                        self.ledger.mark_done(url_hash, content_hash=canonical_hash)
                        stats["unchanged"] += 1
                        log.info("[ITViec] UNCHANGED job_id=%s (nội dung không đổi so với v%d).", job_id, curr_ver)
                        polite_sleep(self.min_delay, self.max_delay, reason="Unchanged delay")
                        continue

                    # Đóng gói Envelope chuẩn theo Data Contract
                    new_ver = curr_ver + 1
                    envelope = {
                        "metadata": {
                            "job_id": job_id,
                            "source": C.SOURCE,
                            "source_url": url,
                            "scraped_at": datetime.now(timezone.utc).isoformat(),
                            "scraper_version": C.CRAWLER_VERSION,
                            "version": new_ver,
                            "content_hash": canonical_hash,
                            "canonical_hash": canonical_hash,
                            "field_hashes": field_hashes,
                            "http_status": status_code,
                        },
                        "raw_payload": raw_payload,
                    }

                    # Lưu file cục bộ: data/itviec/raw/<YYYY-MM-DD>/{job_id}_v{version}.json
                    dest_file = os.path.join(dest_dir, f"{job_id}_v{new_ver}.json")
                    with open(dest_file, "w", encoding="utf-8") as f:
                        json.dump(envelope, f, ensure_ascii=False, indent=2)

                    # Lưu file HTML thô nếu bật cờ save_html
                    if self.save_html:
                        html_file = os.path.join(dest_dir, f"{job_id}_v{new_ver}.html")
                        with open(html_file, "w", encoding="utf-8") as f:
                            f.write(html)

                    # Đẩy snapshot lên MinIO Lakehouse
                    if do_sync:
                        s3_key = f"raw/{C.SOURCE}/{today}/{job_id}_v{new_ver}.json"
                        try:
                            self._get_minio_store().put_json(s3_key, envelope)
                            if self.save_html:
                                self._get_minio_store().put_bytes(
                                    f"raw_html/{C.SOURCE}/{today}/{job_id}_v{new_ver}.html",
                                    html.encode("utf-8"),
                                    content_type="text/html; charset=utf-8",
                                )
                        except Exception as sync_exc:
                            log.warning("[ITViec] Bỏ qua sync MinIO file %s: %s (local file an toàn)", s3_key, sync_exc)

                    # Lưu ngược lại mã hash vào URL trong Ledger
                    self.ledger.mark_done(url_hash, content_hash=canonical_hash, new_version=new_ver)
                    stats["crawled_new"] += 1
                    log.info("[ITViec] ĐÃ CÀO THÀNH CÔNG: job_id=%s -> %s (v%d)", job_id, os.path.basename(dest_file), new_ver)

                    # Checkpoint Sync định kỳ: mỗi 15 tin tự động lưu & sync MinIO
                    if stats["crawled_new"] % 15 == 0:
                        self.ledger.save_catalog()
                        if do_sync:
                            self.ledger.sync_to_minio()
                            log.info("[ITViec] Checkpoint sync định kỳ: đã đồng bộ %d tin lên MinIO Lakehouse.", stats["crawled_new"])

                    polite_sleep(self.min_delay, self.max_delay, reason=f"Nghỉ giữa 2 bài đăng ({idx})")

                except Exception as exc:
                    # Safe Skip & Failed Queue: Bắt lỗi, ghi log cảnh báo và tiếp tục tin sau
                    log.warning("[ITViec] LỖI Safe Skip URL job_id=%s url=%s: %s -> Đưa vào Failed Queue", job_id, url, exc)
                    self.ledger.mark_failed(url_hash, str(exc))
                    stats["errors"] += 1

        # Lưu catalog và đồng bộ lần cuối
        self.ledger.save_catalog()
        if do_sync:
            self.ledger.sync_to_minio()

        log.info("[ITViec] === Tổng kết Pha 2: %s ===", stats)
        return stats


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="ITViec Two-Phase Decoupled Crawler (Modern Data Stack)")
    ap.add_argument(
        "--phase",
        choices=["discovery", "details", "all", "sync", "view"],
        default="details",
        help="Pha 1 (discovery) / Pha 2 (details) / đồng bộ MinIO (sync) / xem ledger (view) / toàn bộ (all)",
    )
    ap.add_argument("--login", action="store_true", default=False, help="Mở trình duyệt đăng nhập tương tác (Google/Email) và lưu session cookies")
    ap.add_argument("--auth-file", type=str, default=None, help="Đường dẫn file lưu session đăng nhập (mặc định data/itviec/auth/session.json)")
    ap.add_argument("--use-playwright", action="store_true", default=False, help="Sử dụng Playwright thay cho HttpClient khi cào chi tiết")
    ap.add_argument("--limit", type=int, default=None, help="Số tin chi tiết tối đa cần xử lý ở Pha 2")
    ap.add_argument("--max-items", type=int, default=None, help="Alias của --limit (tương thích ngược)")
    ap.add_argument("--max-pages", type=int, default=None, help="Số trang danh mục tối đa ở Pha 1 (mặc định: hết)")
    ap.add_argument("--online", action="store_true", default=False, help="Cho phép kết nối mạng bên ngoài")
    ap.add_argument("--sync-minio", action="store_true", default=False, help="Đồng bộ URL Ledger và Raw Snapshots lên MinIO Lakehouse")
    ap.add_argument("--retry-failed", action="store_true", default=False, help="Cào lại các URL trong hàng đợi lỗi (Failed Queue)")
    ap.add_argument("--local-html-dir", type=str, default=None, help="Thư mục chứa HTML cục bộ -> cào offline không cần mạng")
    ap.add_argument("--save-html", action="store_true", default=False, help="Lưu file HTML thô mỗi bài đăng (mặc định TẮT)")
    ap.add_argument("--force", action="store_true", default=False, help="Cào lại các bài đã DONE -> tạo version mới")
    ap.add_argument("--only-job-ids", type=str, default=None, help="Chỉ cào các job_id cụ thể (phân tách bởi dấu phẩy)")
    ap.add_argument("--min-delay", type=float, default=C.MIN_DELAY)
    ap.add_argument("--max-delay", type=float, default=C.MAX_DELAY)
    ap.add_argument("--output-dir", type=str, default="data/itviec")
    ap.add_argument("--ledger-dir", type=str, default=None)
    ap.add_argument("--raw-dir", type=str, default=None)
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    limit_val = args.limit if args.limit is not None else args.max_items

    crawler = ItviecCrawler(
        output_dir=args.output_dir,
        ledger_dir=args.ledger_dir,
        raw_dir=args.raw_dir,
        limit=limit_val,
        save_html=args.save_html,
        min_delay=args.min_delay,
        max_delay=args.max_delay,
        sync_minio=args.sync_minio,
        local_html_dir=args.local_html_dir,
        auth_file=args.auth_file,
        use_playwright=args.use_playwright,
    )

    if args.login:
        crawler.login_interactive()
        return

    if args.phase == "discovery":
        total = crawler.discover_urls(
            online=args.online,
            max_pages=args.max_pages,
            sync_minio=args.sync_minio,
        )
        print(f"[discovery] Tổng số record trong Ledger: {total} (online={args.online})")
    elif args.phase == "details":
        only_ids = [x.strip() for x in args.only_job_ids.split(",")] if args.only_job_ids else None
        stats = crawler.crawl_details(
            limit=limit_val,
            local_html_dir=args.local_html_dir,
            online=args.online,
            sync_minio=args.sync_minio,
            retry_failed=args.retry_failed,
            force=args.force,
            only_job_ids=only_ids,
        )
        print(f"[details] Kết quả hoàn thành: {json.dumps(stats, ensure_ascii=False)}")
    elif args.phase == "sync":
        ok = crawler.sync_ledger_to_minio()
        print(f"[sync] Đồng bộ URL Ledger lên MinIO: {'THÀNH CÔNG' if ok else 'THẤT BẠI'}")
    elif args.phase == "view":
        crawler.view_ledger()
    elif args.phase == "all":
        crawler.discover_urls(online=args.online, max_pages=args.max_pages or 1, sync_minio=args.sync_minio)
        stats = crawler.crawl_details(limit=limit_val, online=args.online, sync_minio=args.sync_minio, force=args.force)
        print(f"[all] Kết quả hoàn thành: {json.dumps(stats, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
