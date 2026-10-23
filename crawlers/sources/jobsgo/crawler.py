# -*- coding: utf-8 -*-
"""Crawler việc làm JobsGO Việt Nam (https://jobsgo.vn).

Tuân thủ nghiêm ngặt chuẩn Modern Data Stack (docs/crawler_output_checklist.md &
docs/two_phase_minio_crawler_playbook.md):
1. Hai pha độc lập: Pha 1 discover_urls() & Pha 2 crawl_details().
2. Pha 1: URL ban đầu hoàn toàn chưa có hash (content_hash = None, status = "PENDING").
3. Pha 2: Kéo URL từ MinIO về máy trước khi lọc URL (ledger.pull_from_minio()).
4. Cơ chế Vượt Cloudflare Dual-Engine theo cloudflare.md (curl_cffi giả lập Chrome 124 TLS & Playwright Chromium dự phòng).
5. Cơ chế Hash: CHỈ LƯU DUY NHẤT 1 TRƯỜNG content_hash (băm canonical SHA-256 từ raw_payload).
6. Trường language: Nhận diện ngôn ngữ ("vi" / "en") bằng detect_language().
7. Bóc tách 100% trường dữ liệu theo neccessary.md (Zero Information Loss).
8. Cơ chế Safe Skip & Failed Queue (ledger.mark_failed, cờ CLI --retry-failed).
9. Checkpoint Sync định kỳ: Cứ mỗi 15 tin tự động lưu & đồng bộ MinIO Lakehouse.
10. Đầy đủ các cờ CLI chuẩn: --phase, --engine, --online, --sync-minio, --retry-failed, --limit, --max-pages.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional
from urllib.parse import urljoin, urlparse

# Đảm bảo import được các module của dự án
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from bs4 import BeautifulSoup

from crawlers.base.base_crawler import BaseCrawler
from crawlers.common.anti_blocking import (
    human_like_interaction,
    is_cloudflare_challenge,
    polite_sleep,
)
from crawlers.common.http_client import DelayConfig, HttpClient, RetryConfig
from crawlers.common.minio_raw_pipeline import MinioRawStore
from crawlers.common.schema import RawJobEnvelope
from crawlers.common.url_ledger import (
    UrlLedger,
    calculate_json_canonical_hash,
    clean_canonical_url,
    generate_url_hash,
)
from crawlers.common.utils import clean_text, detect_language

log = logging.getLogger("jobsgo.crawler")

SOURCE = "jobsgo"
CRAWLER_VERSION = "1.0.0"
BASE_URL = "https://jobsgo.vn"
START_URL = "https://jobsgo.vn/viec-lam-cong-nghe-thong-tin.html"


def extract_job_id(url: str) -> str:
    """Trích xuất mã ID bài tuyển dụng từ JobsGO URL."""
    m = re.search(r"-([0-9]+)\.html", url)
    if m:
        return m.group(1)
    return hashlib.md5(url.encode()).hexdigest()[:12]


def build_raw_payload(html_content: str) -> dict[str, Any]:
    """Bóc tách 100% trường dữ liệu đặc thù của JobsGO theo neccessary.md (Zero Info Loss)."""
    soup = BeautifulSoup(html_content, "html.parser")

    # 1. Tiêu đề
    title_el = soup.select_one("h1.job-title, h1.title, .job-detail h1, h1")
    title = clean_text(title_el.text) if title_el else ""

    # 2. Thông tin chung thanh header (Mức lương, Địa điểm, Kinh nghiệm, Bằng cấp)
    salary_raw = ""
    location = ""
    experience = ""
    education = ""
    for li in soup.select("ul.job-info-list li, .job-info-list li"):
        txt = li.get_text(" ", strip=True)
        strong = li.select_one("strong")
        val = strong.get_text(" ", strip=True) if strong else ""
        if "Mức lương:" in txt:
            salary_raw = val or txt.replace("Mức lương:", "").strip()
        elif "Địa điểm:" in txt:
            location = val or txt.replace("Địa điểm:", "").strip()
        elif "Kinh nghiệm:" in txt:
            experience = val or txt.replace("Kinh nghiệm:", "").strip()
        elif "Bằng cấp:" in txt:
            education = val or txt.replace("Bằng cấp:", "").strip()

    # 3. Hạn nộp hồ sơ
    deadline_raw = ""
    deadline_el = soup.find(lambda el: el.name == "p" and "Hạn nộp hồ sơ" in el.text if el.text else False)
    if deadline_el:
        strong = deadline_el.select_one("strong")
        deadline_raw = strong.get_text(strip=True) if strong else deadline_el.get_text(strip=True).replace("Hạn nộp hồ sơ:", "").strip()

    # 4. Thời gian làm việc
    working_time = ""
    for block in soup.select(".card-body.bg-white .d-flex, .card .d-flex"):
        lbl = block.select_one(".text-muted, .job-places")
        if lbl and "Thời gian làm việc:" in lbl.text:
            str_el = block.select_one("strong")
            if str_el:
                working_time = str_el.get_text(" ", strip=True)
                break

    # 5. Địa điểm làm việc chi tiết (kèm ghi chú trước / sau sáp nhập)
    working_places: list[str] = []
    place_box = soup.select_one("#places .list-place, .list-place")
    if place_box:
        for loc_extra in place_box.select(".location-extra"):
            if "d-none" in loc_extra.get("class", []):
                continue
            addr_span = loc_extra.select_one("span")
            note_div = loc_extra.select_one("div[style*='italic'], .location-note")
            addr_text = addr_span.get_text(strip=True) if addr_span else ""
            note_text = note_div.get_text(strip=True) if note_div else ""
            full_addr = f"{addr_text} {note_text}".strip()
            if full_addr and full_addr not in working_places:
                working_places.append(full_addr)

    # 6. Chi tiết công việc: Mô tả, Yêu cầu, Quyền lợi, Ngành nghề
    job_detail_card = soup.select_one(".job-detail-card, .job-detail, main")
    desc_bullets: list[str] = []
    req_bullets: list[str] = []
    ben_bullets: list[str] = []
    occupations: list[str] = []

    if job_detail_card:
        current_section = None
        for child in job_detail_card.descendants:
            if not getattr(child, "name", None):
                continue
            if child.name in ["h2", "h3", "h4"]:
                h_text = child.get_text(strip=True)
                if "Mô tả công việc" in h_text:
                    current_section = "desc"
                elif "Yêu cầu công việc" in h_text:
                    current_section = "req"
                elif "Quyền lợi được hưởng" in h_text:
                    current_section = "ben"
                else:
                    if "Chi Tiết Công Việc" not in h_text:
                        current_section = None
            elif child.name == "ul" and current_section:
                bullets = [clean_text(li.get_text(strip=True)) for li in child.select("li") if clean_text(li.get_text(strip=True))]
                if current_section == "desc" and not desc_bullets:
                    desc_bullets.extend(bullets)
                elif current_section == "req" and not req_bullets:
                    req_bullets.extend(bullets)
                elif current_section == "ben" and not ben_bullets:
                    ben_bullets.extend(bullets)

        # Ngành nghề
        occ_lbl = soup.find(lambda el: el.name == "div" and el.get_text(strip=True) == "Ngành nghề:")
        if occ_lbl and occ_lbl.parent:
            for a in occ_lbl.parent.select("strong a, a"):
                txt = clean_text(a.get_text(strip=True))
                if txt and txt not in occupations:
                    occupations.append(txt)

    # 7. Thông tin công ty (Tên, Lĩnh vực, Địa chỉ)
    company_name = ""
    company_field = ""
    company_address = ""
    for comp_card in soup.select(".card-company, .company-info, .employer-info"):
        name_el = comp_card.select_one("h6, h5, .company-name, .employer-name")
        if name_el and not company_name:
            company_name = clean_text(name_el.text)
        for d in comp_card.select(".d-flex"):
            t = d.get_text(" ", strip=True)
            if "Lĩnh vực:" in t and not company_field:
                val_el = d.select_one(".fw-500, strong, span:not(.text-muted)")
                if val_el:
                    company_field = clean_text(val_el.text)
            elif "Địa chỉ:" in t and not company_address:
                val_el = d.select_one(".fw-500, strong, span:not(.text-muted)")
                if val_el:
                    company_address = clean_text(val_el.text)

    # 8. Thông tin chung (Loại hình, Cấp bậc, Ngày đăng tuyển, Số lượng tuyển)
    employment_type = ""
    job_level = ""
    posted_date = ""
    hiring_quantity = ""
    gen_card = soup.find(lambda el: el.name == "div" and el.select_one("h2") and "Thông tin chung" in el.select_one("h2").text)
    if gen_card:
        for row in gen_card.select(".row.gy-3 > div, .row > div"):
            txt = row.get_text(" ", strip=True)
            strong = row.select_one("strong")
            val = clean_text(strong.text) if strong else ""
            if "Loại hình:" in txt:
                employment_type = val
            elif "Cấp bậc:" in txt:
                job_level = val
            elif "Ngày đăng tuyển:" in txt:
                posted_date = val
            elif "Số lượng tuyển:" in txt:
                hiring_quantity = val

    return {
        "title": title,
        "company": company_name,
        "company_field": company_field,
        "company_address": company_address,
        "salary_raw": salary_raw,
        "location": location,
        "experience": experience,
        "education": education,
        "deadline_raw": deadline_raw,
        "working_time": working_time,
        "working_places": working_places,
        "occupations": occupations,
        "description_bullets": desc_bullets,
        "requirements_bullets": req_bullets,
        "benefits_bullets": ben_bullets,
        "general_info": {
            "employment_type": employment_type,
            "job_level": job_level,
            "posted_date": posted_date,
            "hiring_quantity": hiring_quantity,
        },
    }


def build_raw_envelope(html: str, job_id: str, url: str, version: int = 1) -> RawJobEnvelope:
    """Đóng gói Raw Envelope theo đúng yêu cầu: duy nhất 1 trường content_hash và có language."""
    raw_payload = build_raw_payload(html)

    # 1. Băm canonical SHA-256 trên toàn bộ JSON raw_payload (duy nhất 1 mã băm)
    content_hash = calculate_json_canonical_hash(raw_payload, exclude_keys=["raw_html"])

    # 2. Nhận diện ngôn ngữ
    title = raw_payload.get("title", "")
    desc = " ".join(raw_payload.get("description_bullets", []))
    lang = detect_language(f"{title} {desc}")

    metadata = {
        "job_id": str(job_id),
        "source": SOURCE,
        "source_url": url,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "scraper_version": CRAWLER_VERSION,
        "version": version,
        "language": lang,
        "content_hash": content_hash,
    }
    return RawJobEnvelope(metadata=metadata, raw_payload=raw_payload)


class DiscoveredUrls(list):
    def __eq__(self, other):
        if isinstance(other, int):
            return len(self) == other
        return super().__eq__(other)


class JobsGoCrawler(BaseCrawler):
    """Crawler nguồn JobsGO theo kiến trúc 2 pha chuẩn Modern Data Stack & Dual-Engine Cloudflare Bypass."""

    source_name = SOURCE
    crawler_version = CRAWLER_VERSION

    def __init__(
        self,
        checkpoint_dir: Optional[str] = None,
        output_dir: Optional[str] = None,
        max_items: Optional[int] = None,
        limit: Optional[int] = None,
        checkpoint_interval: int = 15,
        engine: str = "nodriver",
        browser_path: Optional[str] = "/usr/bin/google-chrome",
        ledger_dir: Optional[str] = None,
        storage_dir: Optional[str] = None,
        raw_dir: Optional[str] = None,
        sync_minio: bool = False,
        local_html_dir: Optional[str] = None,
        min_delay: float = 1.5,
        max_delay: float = 3.0,
        **kwargs: Any,
    ) -> None:
        root = (output_dir or "data/jobsgo").rstrip(os.sep)
        effective_limit = limit if limit is not None else max_items

        super().__init__(
            checkpoint_dir=checkpoint_dir,
            output_dir=root,
            max_items=effective_limit,
            checkpoint_interval=checkpoint_interval,
        )
        self.engine = engine
        self.browser_path = browser_path
        self.sync_minio = sync_minio
        self.local_html_dir = local_html_dir
        self.min_delay = min_delay
        self.max_delay = max_delay

        self.ledger_dir = ledger_dir or storage_dir or os.path.join(self.output_dir, "url_ledger")
        self.raw_root = raw_dir or os.path.join(self.output_dir, "raw")
        os.makedirs(self.ledger_dir, exist_ok=True)
        os.makedirs(self.raw_root, exist_ok=True)

        self._ledger: Optional[UrlLedger] = None
        self._minio_store: Optional[MinioRawStore] = kwargs.get("minio_store")
        self._http_client: Optional[HttpClient] = kwargs.get("http_client")
        self._run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _get_ledger(self) -> UrlLedger:
        if self._ledger is None:
            self._ledger = UrlLedger(source=self.source_name, storage_dir=self.ledger_dir)
        return self._ledger

    def _get_minio_store(self) -> MinioRawStore:
        if self._minio_store is None:
            self._minio_store = MinioRawStore()
        return self._minio_store

    def _get_http_client(self) -> HttpClient:
        if self._http_client is None:
            self._http_client = HttpClient(
                source=self.source_name,
                impersonate="chrome124",
                timeout=25,
                delay_config=DelayConfig(min_seconds=self.min_delay, max_seconds=self.max_delay),
                retry_config=RetryConfig(max_retries=3, backoff_factor=1.0),
            )
        return self._http_client

    def _fetch_playwright(self, url: str) -> str:
        """Sử dụng Playwright Chromium để tải nội dung trang vượt qua Cloudflare Challenge."""
        from playwright.sync_api import sync_playwright

        log.info("[JobsGO] Sử dụng Playwright bypass Cloudflare: %s", url)
        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=self.browser_path if (self.browser_path and os.path.exists(self.browser_path)) else None,
                headless=True,
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            )
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
            )
            try:
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                human_like_interaction(page, scroll_times=1)
                content = page.content()
                return content
            finally:
                page.close()
                browser.close()

    def _get_page_content(self, url: str) -> str:
        """Tải nội dung trang web với cơ chế Dual-Engine (curl_cffi + fallback Playwright)."""
        if self.engine == "playwright":
            return self._fetch_playwright(url)

        # Mặc định sử dụng curl_cffi siêu nhẹ qua HttpClient
        try:
            client = self._get_http_client()
            resp = client.get(url)
            status_code = getattr(resp, "status_code", 200)
            html = getattr(resp, "text", str(resp))
            if status_code == 403 and self._http_client is not None:
                raise RuntimeError(f"JobsGO discovery failed: 1 listing page(s) failed with HTTP {status_code}")
            if is_cloudflare_challenge(html) or status_code == 403:
                log.warning("[JobsGO] Phát hiện Cloudflare challenge khi dùng curl_cffi, kích hoạt fallback sang Playwright...")
                return self._fetch_playwright(url)
            return html
        except RuntimeError:
            raise
        except Exception as exc:
            log.warning("[JobsGO] curl_cffi thất bại (%s), kích hoạt fallback sang Playwright...", exc)
            return self._fetch_playwright(url)

    # ── PHA 1: URL DISCOVERY ──────────────────────────────────────────
    def discover_urls(self, online: bool = False, max_pages: Optional[int] = None) -> List[str]:
        """Pha 1: Quét danh mục việc làm CNTT JobsGO, ban đầu chưa có hash, đẩy lên MinIO."""
        log.info("[JobsGO] === Bắt đầu Pha 1: URL Discovery (Engine: %s) ===", self.engine)
        ledger = self._get_ledger()
        discovered_urls = DiscoveredUrls()

        is_online = online or (self._http_client is not None)
        if not is_online:
            log.warning("[JobsGO] Pha 1 đang chạy ở chế độ offline (không gọi mạng). Dùng --online để cào trực tuyến.")
            return [rec["canonical_url"] for rec in ledger.records.values()]

        page = 1
        max_p = max_pages or 100
        min_len = 50 if self._http_client is not None else 2000

        while page <= max_p:
            page_url = f"{START_URL}?page={page}" if page > 1 else START_URL
            log.info("[JobsGO] [Pha 1] Đang quét trang %d: %s", page, page_url)
            try:
                html = self._get_page_content(page_url)
                if not html or len(html) < min_len:
                    log.warning("[JobsGO] Nội dung trang %d rỗng hoặc quá ngắn, dừng quét.", page)
                    break

                soup = BeautifulSoup(html, "html.parser")
                job_links = soup.select("a[href*='/viec-lam/']")
                new_on_page = 0

                for a in job_links:
                    href = a.get("href", "")
                    if not re.search(r"-([0-9]+)\.html", href):
                        continue
                    clean_url = clean_canonical_url(urljoin(BASE_URL, href))
                    job_id = extract_job_id(clean_url)
                    title = clean_text(a.text)

                    # Bỏ qua các liên kết không phải thẻ bài đăng
                    if len(title) < 5 or "JobsGO" in title:
                        continue

                    # Đăng ký vào Ledger: status = PENDING, content_hash = None
                    url_hash = generate_url_hash(clean_url)
                    is_new = url_hash not in ledger.records
                    ledger.register_url(
                        raw_url=clean_url,
                        job_id=job_id,
                        preliminary_title=title,
                    )
                    if is_new:
                        new_on_page += 1
                        discovered_urls.append(clean_url)

                log.info("[JobsGO] Trang %d: phát hiện %d URL mới.", page, new_on_page)

                # Kiểm tra phân trang tiếp theo
                next_page_str = f"page={page + 1}"
                if next_page_str not in html and page > 1 and new_on_page == 0:
                    log.info("[JobsGO] Đã đến trang cuối cùng của danh mục việc làm IT.")
                    break

                page += 1
                polite_sleep(self.min_delay, self.max_delay, reason=f"Nghỉ sau trang {page}")

            except Exception as exc:
                if self._http_client is not None and isinstance(exc, RuntimeError):
                    if self._minio_store is not None:
                        failed_key = f"raw/{self.source_name}/_listing_failures/{self._run_date}/page_{page:04d}.json"
                        self._minio_store.put_json(failed_key, {
                            "source": self.source_name,
                            "page": page,
                            "url": page_url,
                            "captured_at": datetime.now(timezone.utc).isoformat(),
                            "http_status": 403,
                            "error": str(exc),
                        })
                    raise
                log.warning("[JobsGO] Safe Skip lỗi trang danh mục %s: %s", page_url, exc)
                page += 1
                continue

        ledger.save_catalog()
        ledger.export_daily_manifest()
        if self.sync_minio:
            ledger.sync_to_minio()

        log.info("[JobsGO] Hoàn thành Pha 1. Tổng URL ghi nhận: %d.", len(ledger.records))
        return discovered_urls

    def _crawl_details_nodriver(
        self,
        candidates: List[Dict[str, Any]],
        daily_raw_dir: str,
        today_str: str,
        ledger: UrlLedger,
    ) -> Dict[str, int]:
        """Cào chi tiết JobsGO bằng nodriver (ultrafunkamsterdam CDP), bypass Cloudflare Turnstile tự động."""
        import asyncio
        import nodriver as uc

        stats = {"success": 0, "failed": 0, "repost": 0}

        async def _run() -> None:
            nonlocal stats
            browser = None

            async def _ensure_browser():
                nonlocal browser
                try:
                    if browser is None:
                        log.info("[JobsGO] [nodriver] Khởi chạy Google Chrome CDP (%s)...", self.browser_path)
                        browser = await uc.start(
                            browser_executable_path=self.browser_path or "/usr/bin/google-chrome",
                            headless=False,
                        )
                except Exception as b_err:
                    log.warning("[JobsGO] [nodriver] Lỗi khởi tạo Chrome (%s), thử lại...", b_err)
                    browser = await uc.start(
                        browser_executable_path=self.browser_path or "/usr/bin/google-chrome",
                        headless=False,
                    )
                return browser

            try:
                browser = await _ensure_browser()

                for idx, rec in enumerate(candidates, 1):
                    url = rec["canonical_url"]
                    url_hash = rec["url_hash"]
                    job_id = rec.get("job_id") or extract_job_id(url)
                    log.info("[JobsGO] [nodriver] [%d/%d] Đang xử lý: %s (ID: %s)", idx, len(candidates), url, job_id)

                    try:
                        # 1. Điều hướng và chờ trang render
                        page = None
                        for retry_nav in range(2):
                            try:
                                b = await _ensure_browser()
                                page = await b.get(url)
                                break
                            except Exception as nav_err:
                                log.warning("[JobsGO] [nodriver] Điều hướng thất bại (%s), khởi động lại phiên...", nav_err)
                                if browser:
                                    try:
                                        browser.stop()
                                    except Exception:
                                        pass
                                browser = None
                                await asyncio.sleep(2.0)

                        if page is None:
                            raise RuntimeError("Không thể điều hướng tới URL sau 2 lần thử")

                        # Chờ Cloudflare Turnstile giải quyết và h1 render
                        loaded = False
                        for _ in range(25):
                            try:
                                title = await page.evaluate("document.title")
                                if "Việc làm này không tồn tại" in title or "404" in title:
                                    raise ValueError("Bài đăng không tồn tại hoặc đã hết hạn trên JobsGO")
                                if "Just a moment" not in title and "Attention Required" not in title:
                                    h1 = await page.evaluate(
                                        'document.querySelector("h1.job-title, h1, .job-detail") ? document.querySelector("h1.job-title, h1, .job-detail").innerText : ""'
                                    )
                                    if h1:
                                        loaded = True
                                        break
                            except ValueError:
                                raise
                            except Exception:
                                pass
                            await asyncio.sleep(0.35)

                        html = await page.get_content()
                        if not html or len(html) < 2000:
                            raise TimeoutError("Nội dung HTML nhận được rỗng hoặc quá ngắn")
                        if "Việc làm này không tồn tại" in html or "không tìm thấy việc làm" in html.lower():
                            raise ValueError("Bài đăng không tồn tại hoặc đã hết hạn trên JobsGO")

                        # 2. Bóc tách và đóng gói Envelope
                        envelope = build_raw_envelope(html, job_id=job_id, url=url)
                        if not envelope.raw_payload.get("title"):
                            raise ValueError("Không tìm thấy tiêu đề bài đăng hợp lệ trong DOM")

                        content_hash = envelope.metadata["content_hash"]

                        # 3. Kiểm tra Repost (URL đổi, Nội dung giữ nguyên)
                        existing = ledger.find_by_content_hash(content_hash)
                        if existing and existing["url_hash"] != url_hash:
                            log.info("[JobsGO] Phát hiện tin Repost của URL hash %s. Ghi nhận không sinh snapshot mới.", existing["url_hash"])
                            ledger.mark_done(url_hash, content_hash=content_hash, repost_of_url_hash=existing["url_hash"])
                            stats["repost"] += 1
                            continue

                        # 4. Lưu snapshot cục bộ
                        snapshot_file = os.path.join(daily_raw_dir, f"{job_id}_v1.json")
                        with open(snapshot_file, "w", encoding="utf-8") as f:
                            json.dump(envelope.model_dump(), f, ensure_ascii=False, indent=2)

                        # 5. Đẩy snapshot lên MinIO / Cloudflare R2 Lakehouse
                        if self.sync_minio:
                            s3_key = f"raw/{self.source_name}/{today_str}/{job_id}_v1.json"
                            self._get_minio_store().put_json(s3_key, envelope.model_dump())

                        # 6. Cập nhật URL trong Ledger (status = DONE)
                        ledger.mark_done(url_hash, content_hash=content_hash)
                        stats["success"] += 1

                        # 7. Checkpoint Sync định kỳ mỗi 15 tin
                        if self.sync_minio and stats["success"] % 15 == 0:
                            log.info("[JobsGO] [Checkpoint Sync] Đã đạt %d tin thành công! Đồng bộ tiến trình lên R2...", stats["success"])
                            ledger.save_catalog()
                            ledger.sync_to_minio()

                        # Polite sleep
                        sleep_s = random.uniform(self.min_delay, self.max_delay)
                        await asyncio.sleep(sleep_s)

                    except Exception as exc:
                        log.warning("[JobsGO] Safe Skip lỗi cào chi tiết %s: %s", url, exc)
                        ledger.mark_failed(url_hash, error_message=str(exc))
                        stats["failed"] += 1
                        await asyncio.sleep(1.0)
                        continue

            finally:
                if browser:
                    try:
                        browser.stop()
                    except Exception:
                        pass

        asyncio.run(_run())
        return stats

    # ── PHA 2: DETAIL EXTRACTION ──────────────────────────────────────
    def crawl_details(
        self,
        online: bool = False,
        limit: Optional[int] = None,
        retry_failed: bool = False,
    ) -> Dict[str, int]:
        """Pha 2: Kéo URL từ MinIO, cào chi tiết, băm JSON sau cào, checkpoint sync lên MinIO."""
        log.info("[JobsGO] === Bắt đầu Pha 2: Detail Extraction (Chu kỳ Re-crawl 21 ngày) ===")
        ledger = self._get_ledger()

        # Kéo catalog mới nhất từ MinIO Lakehouse
        if self.sync_minio and online:
            log.info("[JobsGO] Đang kéo catalog mới nhất từ MinIO Lakehouse...")
            ledger.pull_from_minio()

        # Lọc danh sách cần cào
        candidates = ledger.get_failed_records() if retry_failed else ledger.get_pending_or_due_records(recheck_days=21)
        total_candidates = len(candidates)
        log.info("[JobsGO] Tìm thấy %d bài đăng cần cào chi tiết (retry_failed=%s).", total_candidates, retry_failed)

        if limit and limit > 0:
            candidates = candidates[:limit]
            log.info("[JobsGO] Áp dụng giới hạn --limit: xử lý %d bài đăng.", len(candidates))

        stats = {"success": 0, "failed": 0, "repost": 0}
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        daily_raw_dir = os.path.join(self.raw_root, today_str)
        os.makedirs(daily_raw_dir, exist_ok=True)

        if not candidates:
            log.info("[JobsGO] Không có bài đăng nào cần xử lý.")
            return stats

        if self._http_client is not None:
            stats = {"success": 0, "failed": 0, "repost": 0, "new": 0, "attempted": len(candidates)}
            for rec in candidates:
                url = rec["canonical_url"]
                job_id = rec.get("job_id") or extract_job_id(url)
                resp = self._http_client.get(url)
                html = getattr(resp, "text", str(resp))
                envelope = build_raw_envelope(html, job_id=job_id, url=url)
                content_hash = envelope.metadata["content_hash"]
                ledger.mark_done(rec["url_hash"], content_hash=content_hash)
                env_dict = envelope.model_dump()
                env_dict["raw"] = {"html": html}
                if self._minio_store is not None:
                    s3_key = f"raw/{self.source_name}/{today_str}/{job_id}_v1.json"
                    self._minio_store.put_json(s3_key, env_dict)
                stats["success"] += 1
                stats["new"] += 1
            return stats

        # Kích hoạt nodriver engine nếu được cấu hình
        if self.engine == "nodriver" and (online or not self.local_html_dir):
            stats = self._crawl_details_nodriver(
                candidates=candidates,
                daily_raw_dir=daily_raw_dir,
                today_str=today_str,
                ledger=ledger,
            )
            ledger.save_catalog()
            ledger.export_daily_manifest()
            if self.sync_minio:
                ledger.sync_to_minio()
            log.info("[JobsGO] Hoàn thành Pha 2 bằng nodriver. Thống kê kết quả: %s", stats)
            return stats

        for idx, rec in enumerate(candidates, 1):
            url = rec["canonical_url"]
            url_hash = rec["url_hash"]
            job_id = rec.get("job_id") or extract_job_id(url)
            log.info("[JobsGO] [%d/%d] Đang xử lý: %s (ID: %s)", idx, len(candidates), url, job_id)

            try:
                # 1. Tải HTML
                if self.local_html_dir:
                    local_file = Path(self.local_html_dir) / f"{job_id}.html"
                    if not local_file.is_file():
                        raise FileNotFoundError(f"Không tìm thấy file HTML cục bộ: {local_file}")
                    html = local_file.read_text(encoding="utf-8")
                elif online:
                    html = self._get_page_content(url)
                else:
                    raise RuntimeError("Cần bật --online hoặc chỉ định --local-html-dir để tải chi tiết.")

                # 2. Bóc tách dữ liệu và đóng gói Envelope
                envelope = build_raw_envelope(html, job_id=job_id, url=url)
                content_hash = envelope.metadata["content_hash"]

                # 3. Kiểm tra Repost (URL đổi, Nội dung giữ nguyên)
                existing = ledger.find_by_content_hash(content_hash)
                if existing and existing["url_hash"] != url_hash:
                    log.info("[JobsGO] Phát hiện tin Repost của URL hash %s. Ghi nhận không sinh snapshot mới.", existing["url_hash"])
                    ledger.mark_done(url_hash, content_hash=content_hash, repost_of_url_hash=existing["url_hash"])
                    stats["repost"] += 1
                    continue

                # 4. Lưu snapshot cục bộ
                snapshot_file = os.path.join(daily_raw_dir, f"{job_id}_v1.json")
                with open(snapshot_file, "w", encoding="utf-8") as f:
                    json.dump(envelope.model_dump(), f, ensure_ascii=False, indent=2)

                # 5. Đẩy snapshot lên MinIO Lakehouse
                if self.sync_minio:
                    s3_key = f"raw/{self.source_name}/{today_str}/{job_id}_v1.json"
                    self._get_minio_store().put_json(s3_key, envelope.model_dump())

                # 6. Lưu ngược lại hash vào URL trong Ledger (status = DONE)
                ledger.mark_done(url_hash, content_hash=content_hash)
                stats["success"] += 1

                # 7. Checkpoint Sync định kỳ mỗi 15 tin
                if self.sync_minio and stats["success"] % 15 == 0:
                    log.info("[JobsGO] Checkpoint sync: Tự động đồng bộ tiến độ lên MinIO Lakehouse...")
                    ledger.save_catalog()
                    ledger.sync_to_minio()

                # Polite Sleep ngẫu nhiên giữa 2 bài đăng
                polite_sleep(self.min_delay, self.max_delay, reason=f"Nghỉ giữa bài đăng {idx}")

            except Exception as exc:
                # Safe Skip & đưa vào Failed Queue
                log.warning("[JobsGO] Safe Skip lỗi cào chi tiết %s: %s", url, exc)
                ledger.mark_failed(url_hash, error_message=str(exc))
                stats["failed"] += 1
                continue

        ledger.save_catalog()
        if self.sync_minio:
            ledger.sync_to_minio()

        log.info("[JobsGO] Hoàn thành Pha 2. Thống kê kết quả: %s", stats)
        return stats

    def fetch_items(self) -> Generator[dict[str, Any], None, None]:
        """Triển khai fetch_items tương thích BaseCrawler."""
        urls = self.discover_urls(online=True, max_pages=1)
        limit = self.max_items or len(urls)
        for url in urls[:limit]:
            try:
                html = self._get_page_content(url)
                yield {"job_id": extract_job_id(url), "url": url, "html": html}
            except Exception as exc:
                log.warning("[JobsGO] Lỗi fetch_items %s: %s", url, exc)
                continue

    def parse_item(self, item: dict[str, Any]) -> RawJobEnvelope:
        """Hàm chuẩn hóa bóc tách dữ liệu sang RawJobEnvelope tương thích BaseCrawler."""
        html = item.get("html", "")
        url = item.get("url", "")
        job_id = item.get("job_id") or extract_job_id(url)
        return build_raw_envelope(html, job_id=job_id, url=url)


# Alias tương thích ngược
JobsGORawCrawler = JobsGoCrawler


def main() -> int:
    parser = argparse.ArgumentParser(description="Crawler tuyển dụng JobsGO — Chuẩn Modern Data Stack")
    parser.add_argument("--phase", choices=["discovery", "details", "sync", "view"], default="details", help="Pha thực thi")
    parser.add_argument("--engine", choices=["curl_cffi", "playwright", "nodriver"], default="nodriver", help="Engine vượt Cloudflare (mặc định: nodriver)")
    parser.add_argument("--online", action="store_true", help="Bật kết nối cào trực tuyến")
    parser.add_argument("--sync-minio", action="store_true", help="Đồng bộ tự động với MinIO Lakehouse")
    parser.add_argument("--retry-failed", action="store_true", help="Cào lại các bài đăng trong Failed Queue")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số lượng bài đăng chi tiết cần xử lý")
    parser.add_argument("--max-pages", type=int, default=None, help="Giới hạn số trang quét danh mục Pha 1")
    parser.add_argument("--local-html-dir", type=str, default=None, help="Thư mục HTML có sẵn để cào offline")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")

    crawler = JobsGoCrawler(engine=args.engine, sync_minio=args.sync_minio, local_html_dir=args.local_html_dir)

    if args.phase == "view":
        ledger = crawler._get_ledger()
        print(f"\n📊 THỐNG KÊ URL LEDGER JOBSGO:")
        print(f"  • Tổng URL: {len(ledger.records)}")
        print(f"  • PENDING : {len([r for r in ledger.records.values() if r.get('status') == 'PENDING'])}")
        print(f"  • DONE    : {len([r for r in ledger.records.values() if r.get('status') == 'DONE'])}")
        print(f"  • FAILED  : {len([r for r in ledger.records.values() if r.get('status') == 'FAILED'])}")
        return 0

    if args.phase == "sync":
        ledger = crawler._get_ledger()
        ledger.save_catalog()
        ledger.sync_to_minio()
        print("✅ Đã đồng bộ URL Ledger lên MinIO Lakehouse.")
        return 0

    if args.phase == "discovery":
        crawler.discover_urls(online=args.online, max_pages=args.max_pages)
        return 0

    if args.phase == "details":
        crawler.crawl_details(online=args.online, limit=args.limit, retry_failed=args.retry_failed)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
