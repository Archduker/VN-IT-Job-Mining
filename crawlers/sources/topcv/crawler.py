# -*- coding: utf-8 -*-
"""Crawler việc làm TopCV Việt Nam (https://www.topcv.vn).

Tuân thủ nghiêm ngặt chuẩn Modern Data Stack (docs/crawler_output_checklist.md &
docs/two_phase_minio_crawler_playbook.md):
1. Hai pha độc lập: Pha 1 discover_urls() & Pha 2 crawl_details().
2. Pha 1: URL ban đầu hoàn toàn chưa có hash (content_hash = None, status = "PENDING").
3. Pha 2: Kéo URL từ MinIO về máy trước khi lọc URL (ledger.pull_from_minio()).
4. Cơ chế Vượt Cloudflare Triệt Để:
   - Playwright Stealth Off-Screen (--window-position=-2400,-2400, Full GPU, No popup).
   - nodriver (CDP thuần qua WebSocket).
   - curl_cffi Chrome 124 TLS.
5. Cơ chế Hash: CHỈ LƯU DUY NHẤT 1 TRƯỜNG content_hash (băm canonical SHA-256 từ raw_payload).
6. Trường language: Nhận diện ngôn ngữ ("vi" / "en") bằng detect_language().
7. Bóc tách 100% trường dữ liệu theo necessary.md (Zero Information Loss).
8. Triệt tiêu mã 429: Adaptive Pacing (3.5s - 6.5s) + Power Nap mỗi 25 bài + Cooldown 45s-60s tự phục hồi.
9. Checkpoint Sync định kỳ: Cứ mỗi 15 tin tự động lưu & đồng bộ MinIO / Cloudflare R2 Lakehouse.
10. Đầy đủ các cờ CLI chuẩn: --phase, --engine, --online, --sync-minio, --retry-failed, --limit, --max-pages.
"""

from __future__ import annotations

import argparse
import asyncio
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
    handle_cloudflare_backoff,
    handle_rate_limit_cooldown,
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

log = logging.getLogger("topcv.crawler")

SOURCE = "topcv"
CRAWLER_VERSION = "2.1.0"
BASE_URL = "https://www.topcv.vn"
START_URL = "https://www.topcv.vn/tim-viec-lam-cong-nghe-thong-tin-cr257"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def extract_job_id(url: str) -> str:
    """Trích xuất mã ID bài tuyển dụng từ TopCV URL."""
    m = re.search(r"/([0-9]+)\.html", url)
    if m:
        return m.group(1)
    m = re.search(r"-([0-9]+)\.html", url)
    if m:
        return m.group(1)
    return hashlib.md5(url.encode()).hexdigest()[:12]


def build_raw_payload(html_content: str) -> dict[str, Any]:
    """Bóc tách 100% trường dữ liệu đặc thù của TopCV theo necessary.md (Zero Info Loss)."""
    soup = BeautifulSoup(html_content, "html.parser")

    # 1. Tiêu đề
    title_el = soup.select_one("h1.box-header-job__title, h1.title, h1")
    title = clean_text(title_el.text) if title_el else ""

    # 2. Lương
    sal_el = soup.select_one(".box-header-job__salary--title, .box-header-job__salary, .salary, .job-detail__info--salary")
    salary_raw = clean_text(sal_el.text) if sal_el else ""

    # 3. Thông tin thanh header: Địa điểm, Kinh nghiệm, Hạn ứng tuyển
    location = ""
    experience = ""
    deadline_raw = ""
    for it in soup.select(".box-header-job-list-info__item"):
        t_el = it.select_one(".list-info__content__title, .item__title")
        d_el = it.select_one(".list-info__content__desc, .item__desc")
        if t_el and d_el:
            t_txt = clean_text(t_el.text)
            d_txt = clean_text(d_el.text)
            if "Địa điểm" in t_txt:
                location = d_txt
            elif "Kinh nghiệm" in t_txt:
                experience = d_txt
            elif "Hạn ứng tuyển" in t_txt:
                deadline_raw = d_txt

    if not deadline_raw:
        dead_el = soup.select_one(".deadline, .job-deadline, .box-job-information-detail-item__deadline")
        if dead_el:
            deadline_raw = clean_text(dead_el.text).replace("Hạn ứng tuyển:", "").strip()

    # 4. Thẻ Overview Tags (Yêu cầu, Quyền lợi, Chuyên môn)
    overview_tags: dict[str, list[str]] = {}
    for g in soup.select(".job-tags__group"):
        gn_el = g.select_one(".job-tags__group-name")
        if gn_el:
            gn = clean_text(gn_el.text).rstrip(":")
            tags = [clean_text(a.text) for a in g.select(".search-from-tag, a, span") if clean_text(a.text) and a != gn_el]
            seen: set[str] = set()
            overview_tags[gn] = [x for x in tags if not (x in seen or seen.add(x))]

    # 5. Mô tả công việc (Job Description Bullets)
    desc_bullets: list[str] = []
    desc_sec = soup.find(
        lambda el: el.name == "div"
        and el.select_one(".box-job-information-detail-item__title")
        and "Mô tả công việc" in el.select_one(".box-job-information-detail-item__title").text
    )
    if desc_sec:
        txt_el = desc_sec.select_one(".box-job-information-detail-item__text")
        if txt_el:
            desc_bullets = [clean_text(li.text) for li in txt_el.select("li")] or [
                clean_text(line) for line in txt_el.get_text("\n").splitlines() if clean_text(line)
            ]
    if not desc_bullets:
        for legacy in soup.select(".job-description, #job-description, .job-detail__description"):
            desc_bullets = [clean_text(li.text) for li in legacy.select("li")] or [
                clean_text(line) for line in legacy.get_text("\n").splitlines() if clean_text(line)
            ]
            if desc_bullets:
                break

    # 6. Yêu cầu ứng viên (Candidate Requirements Bullets)
    req_bullets: list[str] = []
    req_sec = soup.find(
        lambda el: el.name == "div"
        and el.select_one(".box-job-information-detail-item__title")
        and "Yêu cầu ứng viên" in el.select_one(".box-job-information-detail-item__title").text
    )
    if req_sec:
        txt_el = req_sec.select_one(".box-job-information-detail-item__text")
        if txt_el:
            req_bullets = [clean_text(li.text) for li in txt_el.select("li")] or [
                clean_text(line) for line in txt_el.get_text("\n").splitlines() if clean_text(line)
            ]
    if not req_bullets:
        for legacy in soup.select(".job-requirement, #job-requirement, .job-detail__requirement"):
            req_bullets = [clean_text(li.text) for li in legacy.select("li")] or [
                clean_text(line) for line in legacy.get_text("\n").splitlines() if clean_text(line)
            ]
            if req_bullets:
                break

    # 7. Thẻ yêu cầu: Kiến thức ngành & Kỹ năng cần có
    industry_knowledge: list[str] = []
    required_skills: list[str] = []
    for r_tag in soup.select(".box-job-information-required-candidate .required-tag"):
        t_el = r_tag.select_one(".required-tag__content--title")
        d_el = r_tag.select_one(".required-tag__content--desc")
        if t_el and d_el:
            t_txt = clean_text(t_el.text)
            vals = [clean_text(v) for v in d_el.text.split(",") if clean_text(v)]
            if "Kiến thức ngành" in t_txt:
                industry_knowledge = vals
            elif "Kỹ năng cần có" in t_txt:
                required_skills = vals

    # 8. Quyền lợi ứng viên (Benefits Bullets)
    ben_bullets: list[str] = []
    ben_sec = soup.find(
        lambda el: el.name == "div"
        and el.select_one(".box-job-information-detail-item__title")
        and "Quyền lợi ứng viên" in el.select_one(".box-job-information-detail-item__title").text
    )
    if ben_sec:
        txt_el = ben_sec.select_one(".box-job-information-detail-item__text")
        if txt_el:
            ben_bullets = [clean_text(li.text) for li in txt_el.select("li")] or [
                clean_text(line) for line in txt_el.get_text("\n").splitlines() if clean_text(line)
            ]
    if not ben_bullets:
        for legacy in soup.select(".job-benefit, #job-benefit, .job-detail__benefit"):
            ben_bullets = [clean_text(li.text) for li in legacy.select("li")] or [
                clean_text(line) for line in legacy.get_text("\n").splitlines() if clean_text(line)
            ]
            if ben_bullets:
                break

    # 9. Thẻ quyền lợi bổ sung: Phúc lợi & Phụ cấp
    welfare_tags: list[str] = []
    allowance_tags: list[str] = []
    for b_tag in soup.select(".box-job-information-benefit .required-tag"):
        t_el = b_tag.select_one(".required-tag__content--title")
        d_el = b_tag.select_one(".required-tag__content--desc")
        if t_el and d_el:
            t_txt = clean_text(t_el.text)
            vals = [clean_text(v) for v in d_el.text.split(",") if clean_text(v)]
            if "Phúc lợi" in t_txt:
                welfare_tags = vals
            elif "Phụ cấp" in t_txt:
                allowance_tags = vals

    # 10. Địa điểm & Thời gian làm việc, Cách thức ứng tuyển
    working_places: list[str] = []
    working_time = ""
    apply_method = ""
    for it in soup.select(".box-job-information-address-and-time-list__item"):
        t_el = it.select_one(".box-job-information-address-and-time-list__item--title")
        c_el = it.select_one(".box-job-information-address-and-time-list__item--content")
        if t_el and c_el:
            t_txt = clean_text(t_el.text)
            c_txt = clean_text(c_el.text)
            if "Địa điểm làm việc" in t_txt:
                working_places = [clean_text(li.text) for li in c_el.select("li")] or [c_txt]
            elif "Thời gian làm việc" in t_txt:
                working_time = c_txt
            elif "Cách thức ứng tuyển" in t_txt:
                apply_method = c_txt

    # 11. Thông tin chung (Body right)
    general_info: dict[str, str] = {}
    for it in soup.select(".box-job-information-general-info-list__item"):
        t = it.select_one(".box-job-information-general-info-list__item--content-title")
        d = it.select_one(".box-job-information-general-info-list__item--content-desc")
        if t and d:
            general_info[clean_text(t.text)] = clean_text(d.text)
    if not general_info:
        for row in soup.select(".box-general-group-info"):
            t_el = row.select_one(".box-general-group-info__title")
            v_el = row.select_one(".box-general-group-info__value")
            if t_el and v_el:
                general_info[clean_text(t_el.text)] = clean_text(v_el.text)

    # 12. Thông tin công ty
    company_name = ""
    company_scale = ""
    company_address = ""
    company_industry = ""

    comp_box = soup.select_one(".box-company-info-detail")
    if comp_box:
        c_name_el = comp_box.select_one(".company-name, .box-company-info__detail .name, .name")
        if c_name_el:
            company_name = clean_text(c_name_el.text)
        for it in comp_box.select(".box-company-info-detail__list--item"):
            txt = it.get_text(" ", strip=True)
            val_el = it.select_one(".box-company-info-detail__list--item-value")
            val = clean_text(val_el.text) if val_el else clean_text(txt.split(":", 1)[-1])
            if "Quy mô" in txt:
                company_scale = val
            elif "Địa điểm" in txt:
                company_address = val
            elif "Ngành nghề" in txt:
                company_industry = val

    if not company_name:
        for selector in [".box-company-info__detail .name", ".company-name-label", ".company-name", ".company", "a[href*='/cong-ty/']"]:
            c_header = soup.select_one(selector)
            if c_header and clean_text(c_header.text):
                company_name = clean_text(c_header.text)
                break

    return {
        "title": title,
        "company": company_name,
        "salary_raw": salary_raw,
        "location": location,
        "experience": experience,
        "deadline_raw": deadline_raw,
        "overview_tags": overview_tags,
        "description_bullets": desc_bullets,
        "requirements_bullets": req_bullets,
        "industry_knowledge": industry_knowledge,
        "required_skills": required_skills,
        "benefits_bullets": ben_bullets,
        "welfare_tags": welfare_tags,
        "allowance_tags": allowance_tags,
        "working_places": working_places,
        "working_time": working_time,
        "apply_method": apply_method,
        "general_info": general_info,
        "company_scale": company_scale,
        "company_address": company_address,
        "company_industry": company_industry,
    }


def build_raw_envelope(html: str, job_id: str, url: str, version: int = 1) -> RawJobEnvelope:
    """Đóng gói Raw Envelope: duy nhất 1 trường content_hash và có language."""
    raw_payload = build_raw_payload(html)

    # 1. Băm canonical SHA-256 trên toàn bộ JSON raw_payload (duy nhất 1 mã băm)
    content_hash = calculate_json_canonical_hash(raw_payload, exclude_keys=["raw_html"])

    # 2. Nhận diện ngôn ngữ
    title = raw_payload.get("title", "")
    desc = " ".join(raw_payload.get("description_bullets", []))
    req = " ".join(raw_payload.get("requirements_bullets", []))
    lang = detect_language(f"{title} {desc} {req}")

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


class TopCVCrawler(BaseCrawler):
    """Crawler nguồn TopCV theo kiến trúc 2 pha chuẩn Modern Data Stack & Vượt Cloudflare Triệt Để."""

    source_name = SOURCE
    crawler_version = CRAWLER_VERSION

    def __init__(
        self,
        ledger_dir: str = "data/topcv/url_ledger",
        raw_root: str = "data/topcv/raw",
        engine: str = "playwright",
        browser_path: Optional[str] = "/usr/bin/google-chrome",
        sync_minio: bool = False,
        min_delay: float = 5.0,
        max_delay: float = 8.5,
        local_html_dir: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            checkpoint_dir=kwargs.get("checkpoint_dir", "data/topcv/checkpoints"),
            output_dir=kwargs.get("output_dir", "data/topcv"),
            max_items=kwargs.get("max_items", None),
            checkpoint_interval=kwargs.get("checkpoint_interval", 15),
        )
        self.ledger_dir = ledger_dir
        self.raw_root = raw_root
        self.engine = engine.lower()
        self.browser_path = browser_path
        self.sync_minio = sync_minio
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.local_html_dir = local_html_dir

        self._ledger: Optional[UrlLedger] = None
        self._minio_store: Optional[MinioRawStore] = None
        self._http_client: Optional[HttpClient] = None

        # Persistent session objects for reuse across the batch
        self._playwright_instance: Any = None
        self._playwright_context: Any = None
        self._playwright_page: Any = None
        self._nodriver_browser: Any = None

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
                retry_config=RetryConfig(max_retries=2, backoff_factor=1.5),
            )
        return self._http_client

    def _ensure_playwright_page(self) -> Any:
        """Khởi tạo một persistent browser context duy nhất (Off-Screen Headful) để cào bền bỉ."""
        if self._playwright_page is not None:
            try:
                if not self._playwright_page.is_closed():
                    return self._playwright_page
            except Exception:
                pass

        # Dọn dẹp sạch sẽ session cũ nếu bị đóng/hỏng để tránh xung đột event loop
        self._close_playwright_session()

        from playwright.sync_api import sync_playwright

        user_data_dir = os.path.join(self.output_dir, ".browser_profile")
        os.makedirs(user_data_dir, exist_ok=True)

        log.info("[TopCV] Khởi tạo Playwright Off-Screen Persistent Session (Profile: %s)...", user_data_dir)
        self._playwright_instance = sync_playwright().start()
        self._playwright_context = self._playwright_instance.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            executable_path=self.browser_path if (self.browser_path and os.path.exists(self.browser_path)) else None,
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--window-position=-2400,-2400",
                "--window-size=1920,1080",
            ],
            user_agent=DEFAULT_USER_AGENT,
            viewport={"width": 1920, "height": 1080},
            locale="vi-VN",
            timezone_id="Asia/Ho_Chi_Minh",
        )

        self._playwright_page = self._playwright_context.new_page()
        # Áp dụng script stealth che giấu môi trường tự động
        self._playwright_page.add_init_script(
            """
            Object.defineProperty(navigator, 'languages', {get: () => ['vi-VN', 'vi', 'en-US', 'en']});
            Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
            if (!window.chrome) {
                window.chrome = { runtime: {} };
            }
            """
        )
        return self._playwright_page

    def _close_playwright_session(self) -> None:
        """Đóng an toàn phiên Playwright."""
        try:
            if self._playwright_page and not self._playwright_page.is_closed():
                self._playwright_page.close()
        except Exception:
            pass
        try:
            if self._playwright_context:
                self._playwright_context.close()
        except Exception:
            pass
        try:
            if self._playwright_instance:
                self._playwright_instance.stop()
        except Exception:
            pass
        self._playwright_page = None
        self._playwright_context = None
        self._playwright_instance = None

    def _fetch_playwright(self, url: str) -> str:
        """Tải nội dung trang qua Playwright Persistent Off-Screen Context với tự động Cooldown khi gặp 429."""
        try:
            page = self._ensure_playwright_page()
            resp = page.goto(url, timeout=35000, wait_until="domcontentloaded")
            human_like_interaction(page, scroll_times=1)
            content = page.content()

            # Kiểm tra nếu bị Cloudflare Rate Limit (429) hoặc Turnstile Challenge
            status_code = resp.status if resp else 200
            if status_code == 429 or is_cloudflare_challenge(content):
                log.warning("[TopCV] Gặp mã 429 hoặc Cloudflare Challenge tại %s. Kích hoạt Cooldown Mode...", url)
                if handle_rate_limit_cooldown(page, cooldown_sec=45.0):
                    content = page.content()
                elif handle_cloudflare_backoff(page, retry_attempt=1):
                    content = page.content()
                else:
                    raise RuntimeError(f"Cloudflare rate limit / challenge blocked after cooldown: {url}")

            return content
        except Exception as e:
            if "closed" in str(e).lower() or "target" in str(e).lower():
                log.warning("[TopCV] Trình duyệt hoặc tab bị đóng bất ngờ (%s). Đang đặt lại phiên...", e)
                self._close_playwright_session()
            raise

    def _fetch_nodriver(self, url: str) -> str:
        """Tải nội dung trang qua nodriver (CDP thuần không WebDriver) với cửa sổ Off-Screen."""
        import nodriver as uc

        async def _async_get():
            nonlocal self
            if self._nodriver_browser is None:
                log.info("[TopCV] Khởi tạo nodriver Off-Screen Browser...")
                self._nodriver_browser = await uc.start(
                    headless=False,
                    browser_executable_path=self.browser_path if (self.browser_path and os.path.exists(self.browser_path)) else None,
                    browser_args=["--no-sandbox", "--disable-dev-shm-usage", "--window-position=-2400,-2400", "--window-size=1920,1080"],
                )

            tab = await self._nodriver_browser.get(url)
            await tab.sleep(random.uniform(2.5, 4.0))
            content = await tab.get_content()

            if is_cloudflare_challenge(content):
                log.warning("[TopCV] [nodriver] Phát hiện Cloudflare challenge tại %s. Tạm dừng 45s...", url)
                await tab.sleep(45.0)
                await tab.reload()
                await tab.sleep(3.0)
                content = await tab.get_content()

            return content

        loop = uc.loop()
        return loop.run_until_complete(_async_get())

    def _get_page_content(self, url: str) -> str:
        """Điều phối tải nội dung trang web theo Engine được cấu hình."""
        if self.engine == "nodriver":
            return self._fetch_nodriver(url)
        elif self.engine == "playwright":
            return self._fetch_playwright(url)

        # Mặc định curl_cffi nếu chỉ định cụ thể
        try:
            client = self._get_http_client()
            resp = client.get(url)
            html = resp.text
            if is_cloudflare_challenge(html) or resp.status_code in [403, 429]:
                log.warning("[TopCV] curl_cffi nhận status %s / Cloudflare challenge, tự động chuyển sang Playwright Stealth...", resp.status_code)
                return self._fetch_playwright(url)
            return html
        except Exception as exc:
            log.warning("[TopCV] curl_cffi thất bại (%s), chuyển sang Playwright Stealth...", exc)
            return self._fetch_playwright(url)

    # ── PHA 1: URL DISCOVERY ──────────────────────────────────────────
    def discover_urls(self, online: bool = False, max_pages: Optional[int] = None) -> List[str]:
        """Pha 1: Quét danh mục việc làm CNTT TopCV, ban đầu chưa có hash, đẩy lên MinIO."""
        log.info("[TopCV] === Bắt đầu Pha 1: URL Discovery (Engine: %s) ===", self.engine)
        ledger = self._get_ledger()
        discovered_urls: List[str] = []

        if not online:
            log.warning("[TopCV] Pha 1 đang chạy ở chế độ offline. Dùng --online để cào trực tuyến.")
            return [rec["canonical_url"] for rec in ledger.records.values()]

        page = 1
        max_p = max_pages or 100

        try:
            while page <= max_p:
                page_url = (
                    f"{START_URL}?type_keyword=1&disable_auto_detect_type_keyword=1&category_family=r257&saturday_status=0&page={page}"
                )
                log.info("[TopCV] [Pha 1] Đang quét trang %d: %s", page, page_url)
                try:
                    html = self._get_page_content(page_url)
                    if not html or len(html) < 2000:
                        log.warning("[TopCV] Nội dung trang %d rỗng hoặc quá ngắn, dừng quét.", page)
                        break

                    soup = BeautifulSoup(html, "html.parser")
                    job_links = soup.select("a[href*='/viec-lam/']")
                    new_on_page = 0

                    for a in job_links:
                        href = a.get("href", "")
                        if not re.search(r"/([0-9]+)\.html", href) and not re.search(r"-([0-9]+)\.html", href):
                            continue
                        clean_url = clean_canonical_url(urljoin(BASE_URL, href))
                        job_id = extract_job_id(clean_url)
                        title = clean_text(a.text)

                        if len(title) < 5 or any(k in href for k in ["viec-lam-it", "cr257", "tag"]):
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

                    log.info("[TopCV] Trang %d: phát hiện %d URL mới.", page, new_on_page)

                    # Kiểm tra trang tiếp theo
                    next_page_str = f"page={page + 1}"
                    if next_page_str not in html and page > 1 and new_on_page == 0:
                        log.info("[TopCV] Đã đến trang cuối cùng của danh mục việc làm IT.")
                        break

                    page += 1
                    polite_sleep(self.min_delay, self.max_delay, reason=f"Nghỉ giữa các trang listing {page}")

                except Exception as exc:
                    log.warning("[TopCV] Lỗi khi quét danh mục trang %d: %s", page, exc)
                    break
        finally:
            self._close_playwright_session()

        ledger.save_catalog()
        ledger.export_daily_manifest()
        if self.sync_minio:
            ledger.sync_to_minio()

        log.info("[TopCV] Hoàn thành Pha 1. Tổng URL ghi nhận: %d.", len(ledger.records))
        return discovered_urls

    # ── PHA 2: DETAIL EXTRACTION ──────────────────────────────────────
    def crawl_details(
        self,
        online: bool = False,
        limit: Optional[int] = None,
        retry_failed: bool = False,
    ) -> Dict[str, int]:
        """Pha 2: Kéo URL từ MinIO, cào chi tiết với Pacing an toàn + Power Nap + Checkpoint sync lên MinIO."""
        log.info("[TopCV] === Bắt đầu Pha 2: Detail Extraction (Engine: %s, Chu kỳ Re-crawl 21 ngày) ===", self.engine)
        ledger = self._get_ledger()

        # Kéo catalog mới nhất từ MinIO Lakehouse
        if self.sync_minio and online:
            log.info("[TopCV] Đang kéo catalog mới nhất từ MinIO / Cloudflare R2 Lakehouse...")
            ledger.pull_from_minio()

        # Lọc danh sách cần cào
        candidates = ledger.get_failed_records() if retry_failed else ledger.get_pending_or_due_records(recheck_days=21)
        total_candidates = len(candidates)
        log.info("[TopCV] Tìm thấy %d bài đăng cần cào chi tiết (retry_failed=%s).", total_candidates, retry_failed)

        if limit and limit > 0:
            candidates = candidates[:limit]
            log.info("[TopCV] Áp dụng giới hạn --limit: xử lý %d bài đăng.", len(candidates))

        stats = {"success": 0, "failed": 0, "repost": 0}
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        daily_raw_dir = os.path.join(self.raw_root, today_str)
        os.makedirs(daily_raw_dir, exist_ok=True)

        try:
            for idx, rec in enumerate(candidates, 1):
                url = rec["canonical_url"]
                url_hash = rec["url_hash"]
                job_id = rec.get("job_id") or extract_job_id(url)
                log.info("[TopCV] [%d/%d] Đang xử lý: %s (ID: %s)", idx, len(candidates), url, job_id)

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
                        log.info("[TopCV] Phát hiện tin Repost của URL hash %s. Ghi nhận không sinh snapshot mới.", existing["url_hash"])
                        ledger.mark_done(url_hash, content_hash=content_hash, repost_of_url_hash=existing["url_hash"])
                        stats["repost"] += 1
                        continue

                    # 4. Lưu snapshot cục bộ
                    snapshot_file = os.path.join(daily_raw_dir, f"{job_id}_v1.json")
                    with open(snapshot_file, "w", encoding="utf-8") as f:
                        json.dump(envelope.model_dump(), f, ensure_ascii=False, indent=2)

                    # 5. Đẩy snapshot lên MinIO / R2 Lakehouse
                    if self.sync_minio:
                        s3_key = f"raw/{self.source_name}/{today_str}/{job_id}_v1.json"
                        self._get_minio_store().put_json(s3_key, envelope.model_dump())

                    # 6. Lưu ngược lại hash vào URL trong Ledger (status = DONE)
                    ledger.mark_done(url_hash, content_hash=content_hash)
                    stats["success"] += 1

                    # 7. Checkpoint Sync định kỳ mỗi 15 tin
                    if self.sync_minio and stats["success"] % 15 == 0:
                        log.info("[TopCV] Checkpoint sync: Tự động đồng bộ tiến độ (%d tin DONE) lên Cloudflare R2...", stats["success"])
                        ledger.save_catalog()
                        ledger.sync_to_minio()

                    # 8. Power Nap sau mỗi 25 bài đăng thành công để reset rate limit pool
                    if stats["success"] > 0 and stats["success"] % 25 == 0:
                        nap_sec = polite_sleep(15.0, 20.0, reason=f"Power Nap giải phóng Cloudflare Rate Limit sau {stats['success']} tin")

                    # Polite Sleep ngẫu nhiên giữa 2 bài đăng (3.5s - 6.5s)
                    polite_sleep(self.min_delay, self.max_delay, reason=f"Nghỉ giữa bài đăng {idx}")

                except Exception as exc:
                    # Safe Skip & đưa vào Failed Queue
                    log.warning("[TopCV] Safe Skip lỗi cào chi tiết %s: %s", url, exc)
                    ledger.mark_failed(url_hash, error_message=str(exc))
                    stats["failed"] += 1
                    continue
        finally:
            self._close_playwright_session()
            if self._nodriver_browser:
                try:
                    self._nodriver_browser.stop()
                except Exception:
                    pass
                self._nodriver_browser = None

        ledger.save_catalog()
        if self.sync_minio:
            ledger.sync_to_minio()

        log.info(
            "[TopCV] Hoàn thành Pha 2. Thành công: %d, Lỗi: %d, Repost: %d.",
            stats["success"],
            stats["failed"],
            stats["repost"],
        )
        return stats

    def fetch_items(self) -> Generator[dict[str, Any], None, None]:
        """Phương thức tương thích chuẩn BaseCrawler."""
        ledger = self._get_ledger()
        for rec in ledger.records.values():
            if rec.get("status") == "DONE":
                yield rec

    def parse_item(self, item: dict[str, Any]) -> RawJobEnvelope:
        """Phương thức tương thích chuẩn BaseCrawler."""
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        job_id = item.get("job_id", "")
        snapshot_file = Path(self.raw_root) / today_str / f"{job_id}_v1.json"
        if snapshot_file.is_file():
            data = json.loads(snapshot_file.read_text(encoding="utf-8"))
            return RawJobEnvelope(**data)
        return RawJobEnvelope(
            metadata={
                "job_id": job_id,
                "source": SOURCE,
                "source_url": item.get("canonical_url", ""),
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "scraper_version": CRAWLER_VERSION,
                "version": 1,
                "language": "vi",
                "content_hash": item.get("content_hash", ""),
            },
            raw_payload={"title": item.get("preliminary_title", "")},
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="TopCV Two-Phase Modern Decoupled Crawler")
    parser.add_argument(
        "--phase",
        choices=["discovery", "details", "sync", "view"],
        default="view",
        help="Lựa chọn pha thực thi",
    )
    parser.add_argument(
        "--engine",
        choices=["playwright", "nodriver", "curl_cffi"],
        default="playwright",
        help="Engine vượt Cloudflare (mặc định: playwright Off-Screen Stealth)",
    )
    parser.add_argument("--online", action="store_true", default=False, help="Bật kết nối mạng ngoài")
    parser.add_argument("--sync-minio", action="store_true", default=False, help="Đồng bộ URL Ledger và raw lên MinIO/R2")
    parser.add_argument("--retry-failed", action="store_true", default=False, help="Cào lại các URL trong Failed Queue")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số bài đăng chi tiết")
    parser.add_argument("--max-pages", type=int, default=None, help="Giới hạn số trang quét Pha 1")
    parser.add_argument("--local-html-dir", type=str, default=None, help="Thư mục chứa HTML tải trước")
    parser.add_argument("--minio", action="store_true", default=False, help="Đọc dữ liệu URL Ledger từ MinIO khi xem")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    crawler = TopCVCrawler(
        engine=args.engine,
        sync_minio=args.sync_minio,
        local_html_dir=args.local_html_dir,
    )

    if args.phase == "discovery":
        crawler.discover_urls(online=args.online, max_pages=args.max_pages)
    elif args.phase == "details":
        crawler.crawl_details(online=args.online, limit=args.limit, retry_failed=args.retry_failed)
    elif args.phase == "sync":
        ledger = crawler._get_ledger()
        ledger.save_catalog()
        ledger.sync_to_minio()
        log.info("[TopCV] Đã đồng bộ Ledger lên MinIO / Cloudflare R2 Lakehouse.")
    elif args.phase == "view":
        ledger = crawler._get_ledger()
        records = ledger.records
        st = {}
        for r in records.values():
            s = r.get("status", "UNKNOWN")
            st[s] = st.get(s, 0) + 1
        print(f"\n📊 THỐNG KÊ URL LEDGER TOPCV:\n  • Tổng URL: {len(records)}")
        for k, v in st.items():
            print(f"  • {k:<8}: {v}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
