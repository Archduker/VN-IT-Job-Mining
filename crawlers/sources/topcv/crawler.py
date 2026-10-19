"""Crawler nguồn TopCV (https://www.topcv.vn) — Phiên bản 2 giai đoạn (Listing -> Detail).

Cơ chế hoạt động:
1. Giai đoạn 1 (Listing): Sử dụng Google Chrome headless với persistent context để quét danh sách
   việc làm IT từ https://www.topcv.vn/viec-lam-it, lấy danh sách Job IDs & Job URLs.
2. Giai đoạn 2 (Detail): Truy cập từng trang chi tiết tin tuyển dụng, tải toàn bộ mã HTML,
   lưu file HTML ({job_id}.html) phục vụ phân tích / cache và trích xuất đầy đủ 100% dữ liệu
   (mô tả chi tiết, yêu cầu ứng viên, quyền lợi, hạn nộp hồ sơ, kỹ năng, địa điểm, lịch làm việc).
"""

import argparse
import glob
import logging
import os
import re
from collections.abc import Generator
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from crawlers.base.base_crawler import BaseCrawler
from crawlers.common.anti_blocking import (
    handle_cloudflare_backoff,
    human_like_interaction,
    is_cloudflare_challenge,
    polite_sleep,
)
from crawlers.common.schema import JobRecord, JobSalary, JobTags
from crawlers.common.url_ledger import (
    UrlLedger,
    calculate_container_html_hash,
    calculate_json_canonical_hash,
    calculate_json_field_hashes,
    diff_json_versions,
    clean_canonical_url,
)
from crawlers.common.utils import (
    clean_text,
    detect_language,
    parse_salary,
    parse_salary_detail,
    strip_html_tags,
    text_to_clean_lines,
    classify_job_tags,
)

log = logging.getLogger("topcv.crawler")

SOURCE = "topcv"
CRAWLER_VERSION = "2.0.0"
BASE_URL = "https://www.topcv.vn"
START_URL = "https://www.topcv.vn/tim-viec-lam-cong-nghe-thong-tin-cr257"
CONTAINER_SELECTOR = "div.job-detail"



class TopCVCrawler(BaseCrawler):
    """Crawler cho nguồn TopCV sử dụng Playwright / Chrome browser theo mô hình 2 giai đoạn."""

    source_name = SOURCE
    crawler_version = CRAWLER_VERSION

    def __init__(
        self,
        checkpoint_dir: str | None = None,
        output_dir: str | None = None,
        max_items: int | None = 5,
        checkpoint_interval: int = 10,
        chrome_path: str = "/usr/bin/google-chrome",
        headless: bool = True,
        save_html: bool = False,
        html_storage_dir: str | None = None,
        local_html_dir: str | None = None,
        min_delay: float = 3.0,
        max_delay: float = 5.5,
    ) -> None:
        target_output_dir = output_dir or "data/topcv"
        super().__init__(
            checkpoint_dir=checkpoint_dir,
            output_dir=target_output_dir,
            max_items=max_items,
            checkpoint_interval=checkpoint_interval,
        )
        self.chrome_path = chrome_path
        self.headless = headless
        self.save_html = save_html
        self.html_storage_dir = html_storage_dir or os.path.join(self.output_dir, "raw")
        self.local_html_dir = local_html_dir
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.ledger = UrlLedger(
            source=self.source_name,
            storage_dir=os.path.join(self.output_dir, "url_ledger"),
        )

    # ── PHA 1: URL DISCOVERY ──────────────────────────────────
    def discover_urls(self, max_pages: int | None = None) -> int:
        """Quét sạch toàn bộ link bài đăng từ trang danh mục TopCV và lưu vào UrlLedger & MinIO."""
        log.info("[TopCV] === Bắt đầu Pha 1: URL Discovery ===")
        from playwright.sync_api import sync_playwright

        total_discovered = 0
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=self.headless,
                    executable_path=self.chrome_path if os.path.exists(self.chrome_path) else None,
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
                )
                curr_page = 1
                consecutive_empty = 0
                while True:
                    if max_pages and curr_page > max_pages:
                        break

                    target_url = (
                        f"{START_URL}?type_keyword=1&disable_auto_detect_type_keyword=1&category_family=r257&saturday_status=0&page={curr_page}"
                    )
                    log.info("[TopCV] Đang quét danh mục trang %d: %s", curr_page, target_url)

                    cards = []
                    page_soup = None
                    try:
                        for attempt in range(1, 4):
                            context = browser.new_context(
                                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                                locale="vi-VN",
                                viewport={"width": 1280, "height": 800},
                            )
                            context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                            page = context.new_page()

                            try:
                                try:
                                    page.goto(target_url, wait_until="networkidle", timeout=30000)
                                except Exception:
                                    page.goto(target_url, wait_until="domcontentloaded", timeout=30000)

                                human_like_interaction(page, scroll_times=1)
                                content = page.content()

                                if is_cloudflare_challenge(content):
                                    log.warning("[TopCV] Trang %d gặp Cloudflare challenge (lần thử %d/3).", curr_page, attempt)
                                    context.close()
                                    polite_sleep(8.0 * attempt, 12.0 * attempt, reason=f"Chờ giải phóng challenge trang {curr_page}")
                                    continue

                                soup = BeautifulSoup(content, "html.parser")
                                cards = soup.select(".job-item-search-result, .job-item, div[data-job-id]")
                                page_soup = soup
                                context.close()
                                if cards:
                                    break
                            except Exception as exc:
                                log.warning("[TopCV] Lỗi khi tải trang %d (lần %d/3): %s", curr_page, attempt, exc)
                                try:
                                    context.close()
                                except Exception:
                                    pass
                                polite_sleep(5.0 * attempt, 8.0 * attempt, reason="Lỗi tải trang")

                        if not cards or page_soup is None:
                            consecutive_empty += 1
                            if consecutive_empty >= 2:
                                log.info("[TopCV] Không còn bài đăng nào tại trang %d sau nhiều lần thử. Dừng quét danh mục.", curr_page)
                                break
                            else:
                                log.warning("[TopCV] Bỏ qua trang %d do không đọc được thẻ, chuyển trang kế tiếp.", curr_page)
                                curr_page += 1
                                continue
                        else:
                            consecutive_empty = 0

                        page_new = 0
                        page_seen = 0
                        for card in cards:
                            # Tìm thẻ tiêu đề chính xác (ưu tiên h3, tránh thẻ avatar rỗng text)
                            title_el = card.select_one("h3.title a, h3 a, .title a, a.title-link, a[data-toggle='tooltip']")
                            a_tag = None
                            if title_el:
                                a_tag = title_el
                            else:
                                for a in card.select("a[href*='/viec-lam/']"):
                                    if clean_text(a.text) and not any(k in a.get("href", "") for k in ["viec-lam-it", "cr257", "tag"]):
                                        a_tag = a
                                        break
                                if not a_tag:
                                    a_tag = card.select_one("a[href*='/viec-lam/']")

                            if not a_tag:
                                continue

                            raw_href = a_tag.get("href", "")
                            if any(k in raw_href for k in ["viec-lam-it", "cr257", "tag"]):
                                continue

                            job_id = card.get("data-job-id")
                            if not job_id:
                                m = re.search(r"[-_/](\d+)\.html", raw_href)
                                job_id = m.group(1) if m else None

                            if not job_id:
                                continue

                            clean_url = clean_canonical_url(urljoin(BASE_URL, raw_href))
                            title = clean_text(a_tag.text)
                            if not title:
                                fallback_h = card.select_one("h3, .title, strong")
                                title = clean_text(fallback_h.text) if fallback_h else ""

                            comp_el = card.select_one(".company, .company-name, a.company, a[href*='/cong-ty/']")
                            comp = clean_text(comp_el.text) if comp_el else "Unknown"

                            # Ghi nhận vào Ledger và kiểm tra URL mới
                            before_count = len(self.ledger.records)
                            self.ledger.register_url(
                                raw_url=clean_url,
                                job_id=str(job_id),
                                preliminary_title=title,
                                preliminary_company=comp,
                            )
                            if len(self.ledger.records) > before_count:
                                page_new += 1
                            else:
                                page_seen += 1
                            total_discovered += 1

                        # Kiểm tra xem có phải trang cuối cùng không
                        next_el = page_soup.select_one("a[rel='next']")
                        paginate_text = page_soup.select_one("#job-listing-paginate-text")
                        is_last_page = not next_el and paginate_text is not None

                        # Lưu catalog ngay sau mỗi trang để tránh mất mát dữ liệu
                        self.ledger.save_catalog()
                        log.info(
                            "[TopCV] Trang %d: +%d link mới, %d link trùng. Tích lũy sổ cái: %d bài đăng",
                            curr_page,
                            page_new,
                            page_seen,
                            len(self.ledger.records),
                        )

                        # Đồng bộ định kỳ lên MinIO mỗi 5 trang
                        if curr_page % 5 == 0:
                            self.ledger.export_daily_manifest()
                            self.ledger.sync_to_minio()

                        if is_last_page:
                            log.info("[TopCV] Đã chạm trang cuối cùng (%s). Hoàn tất quét toàn bộ danh mục.", paginate_text.text.strip())
                            break

                        curr_page += 1
                        polite_sleep(self.min_delay, self.max_delay, reason=f"Chuyển tiếp trang danh mục {curr_page}")

                    except Exception as exc:
                        log.error("[TopCV] Lỗi khi quét danh mục trang %d: %s", curr_page, exc)
                        break

                browser.close()
        except Exception as exc:
            log.error("[TopCV] Không thể khởi chạy Playwright cho Discovery: %s", exc)

        self.ledger.save_catalog()
        manifest_file = self.ledger.export_daily_manifest()
        # Đồng bộ tự động lên MinIO
        self.ledger.sync_to_minio()
        log.info("[TopCV] Hoàn thành Pha 1. Tổng cộng %d URL đã được ghi nhận vào %s", total_discovered, manifest_file)
        return total_discovered

    # ── PHA 2: DETAIL EXTRACTION ──────────────────────────────
    def crawl_details(self, limit: int | None = None) -> dict[str, int]:
        """Đọc URL Ledger, lọc các link PENDING hoặc (DONE và >= 21 ngày), tải HTML, băm Clean Hash và lưu raw."""
        log.info("[TopCV] === Bắt đầu Pha 2: Detail Extraction (Chu kỳ Re-crawl 21 ngày) ===")
        pending_records = self.ledger.get_pending_or_due_records(recheck_days=21)
        log.info("[TopCV] Tìm thấy %d link cần xử lý trong Ledger.", len(pending_records))

        stats = {"success": 0, "failed": 0, "skipped": 0, "repost": 0}
        raw_storage_dir = os.path.join(self.output_dir, "raw")
        os.makedirs(raw_storage_dir, exist_ok=True)

        from playwright.sync_api import sync_playwright

        count = 0
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=self.headless,
                    executable_path=self.chrome_path if os.path.exists(self.chrome_path) else None,
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
                )
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    locale="vi-VN",
                    viewport={"width": 1280, "height": 800},
                )
                context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

                page = context.new_page()

                for item in pending_records:
                    if limit and count >= limit:
                        break

                    url = item["canonical_url"]
                    url_hash = item["url_hash"]
                    job_id = item["job_id"]

                    try:
                        log.info("[TopCV] [%d/%d] Đang tải chi tiết: %s", count + 1, len(pending_records), url)
                        page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        human_like_interaction(page, scroll_times=1)
                        content = page.content()

                        soup = BeautifulSoup(content, "html.parser")

                        # Kiểm tra Cloudflare WAF / Turnstile
                        if is_cloudflare_challenge(content):
                            log.warning("[TopCV] Phát hiện Cloudflare challenge tại: %s. Chờ backoff...", url)
                            if handle_cloudflare_backoff(page, retry_attempt=1):
                                content = page.content()
                                soup = BeautifulSoup(content, "html.parser")
                            else:
                                raise RuntimeError(f"Cloudflare Turnstile/WAF challenge blocked: {url}")

                        # Kiểm tra bài đăng hết hạn hoặc xóa
                        if "404 - Không tìm thấy" in content or "Tin tuyển dụng này đã hết hạn" in content:
                            log.warning("[TopCV] Bài đăng đã hết hạn hoặc bị xóa: %s", url)
                            self.ledger.mark_closed(url_hash)
                        # Bóc tách cấu trúc dữ liệu thô (Raw Structured Payload)
                        h1_el = soup.select_one("h1")
                        title_text = h1_el.get_text(strip=True) if h1_el else "Unknown"
                        
                        comp_el = soup.select_one(".company-name, .company, a[href*='/cong-ty/']")
                        company_text = comp_el.get_text(strip=True) if comp_el else "Unknown"

                        salary_el = soup.select_one(".salary, .job-detail__info--salary, .box-header-job__salary--title")
                        salary_text = salary_el.get_text(strip=True) if salary_el else "Thương lượng"

                        deadline_el = soup.select_one(".deadline, .job-detail__info--deadline, .job-deadline")
                        deadline_text = deadline_el.get_text(strip=True) if deadline_el else ""

                        container_el = soup.select_one(CONTAINER_SELECTOR) or soup.body or soup
                        desc_text = container_el.get_text(separator=" ", strip=True) if container_el else ""

                        raw_payload = {
                            "title": title_text,
                            "company": company_text,
                            "salary": salary_text,
                            "deadline": deadline_text,
                            "content_text": desc_text,
                            "raw_html": content,
                        }

                        # BƯỚC BĂM JSON SAU KHI CÀO (Post-Crawl Canonical JSON Hashing)
                        new_hash = calculate_json_canonical_hash(raw_payload, exclude_keys=["raw_html"])
                        field_hashes = calculate_json_field_hashes({k: v for k, v in raw_payload.items() if k != "raw_html"})

                        # Kiểm tra kịch bản Repost (URL mới nhưng content JSON trùng tin cũ)
                        existing = self.ledger.find_by_content_hash(new_hash)
                        if existing and existing["url_hash"] != url_hash:
                            log.info("[TopCV] Phát hiện Repost: %s trùng nội dung JSON với %s", url, existing["canonical_url"])
                            self.ledger.mark_done(url_hash, content_hash=new_hash, repost_of_url_hash=existing["url_hash"])
                            stats["repost"] += 1
                            count += 1
                            continue

                        # Xác định version snapshot
                        curr_ver = item.get("latest_version") or 0
                        new_ver = curr_ver if (item.get("content_hash") == new_hash and curr_ver > 0) else curr_ver + 1

                        # Lưu file snapshot thô nguyên bản
                        import json
                        from datetime import datetime, timezone
                        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                        dest_dir = os.path.join(raw_storage_dir, today_str)
                        os.makedirs(dest_dir, exist_ok=True)
                        dest_file = os.path.join(dest_dir, f"{job_id}_v{new_ver}.json")

                        envelope = {
                            "metadata": {
                                "job_id": job_id,
                                "source": self.source_name,
                                "source_url": url,
                                "scraped_at": datetime.now(timezone.utc).isoformat(),
                                "version": new_ver,
                                "content_hash": new_hash,
                                "field_hashes": field_hashes,
                            },
                            "raw_payload": raw_payload,
                        }
                        with open(dest_file, "w", encoding="utf-8") as f:
                            json.dump(envelope, f, ensure_ascii=False, indent=2)

                        # Đánh dấu DONE trong Ledger
                        self.ledger.mark_done(url_hash, content_hash=new_hash, new_version=new_ver)
                        stats["success"] += 1
                        count += 1

                        # Polite sleep giữa 2 bài đăng
                        polite_sleep(self.min_delay, self.max_delay, reason=f"Nghỉ giữa bài đăng {count}")

                    except Exception as exc:
                        # Safe Skip: Ghi nhận lỗi và chuyển tiếp link sau
                        log.error("[TopCV] Lỗi cào %s: %s. Safe Skip qua link tiếp theo.", url, exc)
                        self.ledger.mark_failed(url_hash, error_message=str(exc))
                        stats["failed"] += 1

                page.close()
                browser.close()
        except Exception as exc:
            log.error("[TopCV] Lỗi trong quá trình chạy Detail Extraction: %s", exc)

        self.ledger.save_catalog()
        # Đồng bộ kết quả lên MinIO
        self.ledger.sync_to_minio()
        log.info("[TopCV] Hoàn thành Pha 2. Thống kê: %s", stats)
        return stats

    def _fetch_listing_urls(self, page) -> list[dict[str, Any]]:
        """Quét trang danh sách tìm kiếm và thu thập danh sách {job_id, url}."""
        log.info("[TopCV] Navigating to listing: %s", START_URL)
        page.goto(START_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(4000)

        content = page.content()
        if "Attention Required! | Cloudflare" in content:
            log.warning("[TopCV] Cloudflare challenge detected! Waiting extra time...")
            page.wait_for_timeout(6000)
            content = page.content()

        soup = BeautifulSoup(content, "html.parser")
        cards = soup.select(".job-item-search-result, .job-item, div[data-job-id]")
        log.info("[TopCV] Found %d job cards on listing page.", len(cards))

        job_targets = []
        seen_ids = set()

        for card in cards:
            job_id = card.get("data-job-id")
            a_tag = None
            for a in card.select("a[href*='/viec-lam/']"):
                href = a.get("href", "")
                if clean_text(a.text) and not any(k in href for k in ["viec-lam-it", "tag"]):
                    a_tag = a
                    break

            if not a_tag:
                continue

            raw_url = a_tag.get("href", "")
            if not job_id and raw_url:
                m = re.search(r"[-_/](\d+)\.html", raw_url)
                job_id = m.group(1) if m else None

            if not job_id or str(job_id) in seen_ids:
                continue

            # Bỏ qua nếu đã từng crawl trong checkpoint
            if str(job_id) in self.checkpoint.seen_ids:
                continue

            comp_tag = card.select_one(".company, .company-name, a.company, a[href*='/cong-ty/']")
            comp = clean_text(comp_tag.text) if comp_tag else "Unknown"
            sal_tag = card.select_one(".salary, .title-salary, span.salary")
            sal = clean_text(sal_tag.text) if sal_tag else "Thương lượng"

            seen_ids.add(str(job_id))
            full_url = urljoin(BASE_URL, raw_url)
            job_targets.append({
                "job_id": str(job_id),
                "url": full_url,
                "title": clean_text(a_tag.text),
                "company": comp,
                "salary": sal,
                "html_snippet": str(card),
            })

            if self.max_items and len(job_targets) >= self.max_items:
                break

        return job_targets

    def _sync_fetch_with_playwright(self) -> list[dict[str, Any]]:
        """Thu thập danh sách và tải toàn bộ HTML chi tiết từng trang."""
        from playwright.sync_api import sync_playwright

        items: list[dict[str, Any]] = []

        # Chế độ đọc file HTML cục bộ (Offline testing / fast validation)
        if self.local_html_dir and os.path.exists(self.local_html_dir):
            log.info("[TopCV] Loading local HTML files from %s", self.local_html_dir)
            pattern = os.path.join(self.local_html_dir, "*.html")
            for fpath in sorted(glob.glob(pattern)):
                fname = os.path.basename(fpath)
                m = re.match(r"(\d+)\.html", fname)
                if not m:
                    continue
                job_id = m.group(1)
                with open(fpath, encoding="utf-8") as f:
                    html_content = f.read()
                items.append({
                    "job_id": job_id,
                    "url": f"https://www.topcv.vn/viec-lam/{job_id}.html",
                    "html_content": html_content,
                })
                if self.max_items and len(items) >= self.max_items:
                    break
            return items

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    executable_path=self.chrome_path,
                    headless=self.headless,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                    ],
                )
                listing_context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1920, "height": 1080},
                )
                listing_page = listing_context.new_page()
                targets = self._fetch_listing_urls(listing_page)
                listing_page.close()
                listing_context.close()

                log.info("[TopCV] Fetched %d candidate job URLs. Fetching details...", len(targets))

                for target in targets:
                    job_id = target["job_id"]
                    raw_job_url = target["url"]
                    # Làm sạch URL bỏ tracking token (u_sr_id, ta_source) để tránh Cloudflare challenge
                    clean_job_url = raw_job_url.split("?")[0]

                    # Kiểm tra file HTML đã lưu trước đó nếu có
                    dest_file = os.path.join(self.html_storage_dir, f"{job_id}.html")
                    content = ""
                    if os.path.exists(dest_file):
                        log.info("[TopCV] Reusing cached HTML: %s", dest_file)
                        with open(dest_file, encoding="utf-8") as f:
                            content = f.read()
                    else:
                        log.info("[TopCV] Navigating to detail: %s (Job ID: %s)", clean_job_url, job_id)
                        # Dùng context sạch riêng biệt cho mỗi trang chi tiết để vượt Cloudflare triệt để
                        detail_context = browser.new_context(
                            user_agent=(
                                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                            ),
                            viewport={"width": 1920, "height": 1080},
                        )
                        detail_page = detail_context.new_page()
                        try:
                            detail_page.goto(clean_job_url, wait_until="domcontentloaded", timeout=30000)
                            detail_page.wait_for_timeout(3500)
                            content = detail_page.content()
                            if "Attention Required! | Cloudflare" in content:
                                detail_page.wait_for_timeout(5000)
                                content = detail_page.content()

                            if self.save_html and "Attention Required" not in content and len(content) > 10000:
                                with open(dest_file, "w", encoding="utf-8") as f:
                                    f.write(content)
                                log.info("[TopCV] Saved detail HTML to %s (%d bytes)", dest_file, len(content))
                        finally:
                            detail_page.close()
                            detail_context.close()

                    if content and "Attention Required" not in content and len(content) > 10000:
                        items.append({
                            "job_id": job_id,
                            "url": clean_job_url,
                            "html_content": content,
                        })
                    else:
                        log.warning("[TopCV] Detail page %s was blocked or incomplete. Using listing card fallback.", job_id)
                        items.append({
                            "job_id": job_id,
                            "url": clean_job_url,
                            "title": target.get("title"),
                            "company": target.get("company"),
                            "salary": target.get("salary"),
                            "html_snippet": target.get("html_snippet"),
                        })

                browser.close()
        except Exception as exc:
            log.error("[TopCV] Error in Playwright crawling: %s", exc, exc_info=True)

        return items

    def fetch_items(self) -> Generator[dict[str, Any], None, None]:
        """Fetch items từ Playwright và yield từng item."""
        yield from self._sync_fetch_with_playwright()

    def parse_item(self, item: dict[str, Any]) -> JobRecord | None:
        """Bóc tách toàn diện dữ liệu từ HTML chi tiết sang JobRecord chuẩn."""
        job_id = item.get("job_id")
        job_url = item.get("url")
        html_content = item.get("html_content") or item.get("html_snippet")

        if not job_id or not job_url:
            return None

        soup = BeautifulSoup(html_content, "html.parser") if html_content else None

        # 1. Tiêu đề công việc
        title = None
        if soup:
            t_el = soup.select_one(".box-header-job__title, h1.box-header-job__title, h1")
            if t_el:
                title = clean_text(t_el.get_text(separator=" ", strip=True))
                title = re.sub(r"Nhà tuyển dụng\s+đã được xác thực:.*", "", title, flags=re.DOTALL).strip()
        if not title:
            title = clean_text(item.get("title", ""))

        if not title:
            return None

        # 2. Tên công ty (Xử lý bỏ qua thẻ logo rỗng)
        company = None
        if soup:
            c_el = soup.select_one(".company-name-label a, .company-name-label")
            if not c_el:
                for a in soup.select(".box-company-info a[href*='/cong-ty/']"):
                    txt = clean_text(a.get_text(strip=True))
                    if txt and not any(ign in txt.lower() for ign in ["xem trang", "tuyển dụng"]):
                        c_el = a
                        break
            if c_el:
                company = clean_text(c_el.get_text(strip=True))
        if not company:
            company = clean_text(item.get("company", "")) or "Unknown"

        # 3. Mức lương
        salary_text = None
        if soup:
            s_el = soup.select_one(".box-header-job__salary--title, .box-header-job__salary")
            if s_el:
                salary_text = clean_text(s_el.get_text(strip=True))
        if not salary_text:
            salary_text = clean_text(item.get("salary", "")) or "Thoả thuận"

        # Phân tích mức lương chi tiết (chu kỳ trả lương, hoa hồng, thỏa thuận)
        salary_detail = parse_salary_detail(salary_text, title=title)
        sal_min = salary_detail["salary_min"]
        sal_max = salary_detail["salary_max"]
        sal_currency = salary_detail["salary_currency"]

        # 4. Hạn nộp hồ sơ (Deadline)
        d_el = soup.select_one(".box-applied-cv .date, .date")
        deadline_text = clean_text(d_el.get_text(strip=True)) if d_el else None

        # 5. Các khối chi tiết (Hỗ trợ song ngữ Tiếng Việt & Tiếng Anh)
        sections: dict[str, dict[str, str]] = {}
        for sec in soup.select(".box-job-information-detail-item"):
            h2 = sec.select_one(".box-job-information-detail-item__title--title, h2")
            if not h2:
                continue
            h2_title = h2.get_text(strip=True).lower()
            content_box = (
                sec.select_one(
                    ".box-job-information-detail-item__content, .job-description__item--content, .box-job-information-detail-item__text"
                )
                or sec
            )
            raw_html = str(content_box)
            clean_desc = content_box.get_text(separator="\n", strip=True)
            lines = [line.strip() for line in clean_desc.split("\n") if line.strip()]
            if lines and lines[0].lower() == h2_title:
                lines = lines[1:]
            clean_desc = "\n".join(lines)
            sections[h2_title] = {"html": raw_html, "text": clean_desc}

        def get_sec(keywords: list[str], return_html: bool = False) -> str | None:
            for k, v in sections.items():
                if any(kw in k for kw in keywords):
                    return v["html"] if return_html else v["text"]
            return None

        desc_html = get_sec(["job description", "mô tả công việc"], return_html=True) or item.get("html_snippet") or f"<p>{title}</p>"
        desc_text = get_sec(["job description", "mô tả công việc"]) or (strip_html_tags(desc_html) if desc_html else title)
        req_html = get_sec(["candidate requirements", "yêu cầu ứng viên", "yêu cầu"], return_html=True)
        req_text = get_sec(["candidate requirements", "yêu cầu ứng viên", "yêu cầu"])
        ben_html = get_sec(["benefits", "quyền lợi ứng viên", "quyền lợi"], return_html=True)
        ben_text = get_sec(["benefits", "quyền lợi ứng viên", "quyền lợi"])

        # Chuẩn hóa văn bản thành mảng dòng sạch (list[str])
        desc_list = text_to_clean_lines(desc_html or desc_text)
        req_list = text_to_clean_lines(req_html or req_text)
        ben_list = text_to_clean_lines(ben_html or ben_text)

        # 6. Thông tin chung (Key-Value)
        general_info: dict[str, str] = {}
        if soup:
            for item_node in soup.select(".box-job-information-general-info-list__item"):
                parts = [p.strip() for p in item_node.get_text(separator="\n", strip=True).split("\n") if p.strip()]
                if len(parts) >= 2:
                    general_info[parts[0]] = parts[1]

        seniority = general_info.get("Cấp bậc")
        emp_type = general_info.get("Loại hình làm việc") or general_info.get("Hình thức làm việc")

        # 7. Thẻ tags theo 3 nhóm cốt lõi: Yêu cầu, Quyền lợi, Chuyên môn
        tag_requirements: list[str] = []
        tag_benefits: list[str] = []
        tag_skills: list[str] = []
        found_benefits_group = False

        if soup:
            for group in soup.select(".job-tags .job-tags__group"):
                g_name_el = group.select_one(".job-tags__group-name")
                g_name = g_name_el.get_text(strip=True).lower() if g_name_el else ""
                group_items = []
                for a in group.select(".item"):
                    txt = clean_text(a.get_text(strip=True))
                    if txt and not txt.startswith("+") and txt not in group_items:
                        group_items.append(txt)

                if any(kw in g_name for kw in ["yêu cầu", "requirement"]):
                    tag_requirements.extend(group_items)
                elif any(kw in g_name for kw in ["quyền lợi", "benefit", "phúc lợi"]):
                    found_benefits_group = True
                    tag_benefits.extend(group_items)
                elif any(kw in g_name for kw in ["chuyên môn", "specialization", "skill"]):
                    tag_skills.extend(group_items)
                else:
                    tag_skills.extend(group_items)

            # Fallback cho layout không dùng .job-tags__group (như thẻ flat tag cũ)
            if not tag_requirements and not tag_skills and not found_benefits_group:
                flat_tags = []
                for tag_node in soup.select(".job-tags .item, .tag .item-tag, .tag-quickview .item-tag"):
                    txt = clean_text(tag_node.get_text(strip=True))
                    if txt and not txt.startswith("+") and txt not in flat_tags:
                        flat_tags.append(txt)
                if flat_tags:
                    classified_fallback = classify_job_tags(flat_tags)
                    tag_requirements = classified_fallback.get("requirements") or []
                    tag_benefits = classified_fallback.get("benefits") or []
                    found_benefits_group = bool(tag_benefits)
                    tag_skills = classified_fallback.get("skills") or []

        tags_data = {
            "requirements": tag_requirements if tag_requirements else None,
            "benefits": tag_benefits if (found_benefits_group and tag_benefits) else None,
            "skills": tag_skills if tag_skills else None,
        }

        # 8. Địa điểm làm việc & Lịch làm việc
        loc_item = (
            soup.select_one(
                ".box-job-information-address-and-time-list__item:-soup-contains('Location'), "
                ".box-job-information-address-and-time-list__item:-soup-contains('Địa điểm')"
            )
            if soup
            else None
        )
        if loc_item:
            loc_content = loc_item.select_one(".box-job-information-address-and-time-list__item--content")
            loc_text = clean_text(loc_content.get_text(separator=" ", strip=True)) if loc_content else None
        else:
            loc_header = soup.select_one(".box-header-job a[href*='/tim-viec-lam-moi-nhat-tai-']")
            loc_text = clean_text(loc_header.get_text(strip=True)) if loc_header else None

        sched_item = soup.select_one(
            ".box-job-information-address-and-time-list__item:-soup-contains('Work Schedule'), "
            ".box-job-information-address-and-time-list__item:-soup-contains('Thời gian')"
        )
        sched_text = (
            clean_text(sched_item.select_one(".box-job-information-address-and-time-list__item--content").get_text(separator=" ", strip=True))
            if sched_item
            else None
        )

        # 9. Kinh nghiệm & Học vấn
        exp_text = general_info.get("Kinh nghiệm")
        if not exp_text and tag_requirements:
            for t in tag_requirements:
                if any(w in t.lower() for w in ["kinh nghiệm", "experience", "năm"]):
                    exp_text = t
                    break
        edu_text = general_info.get("Học vấn")
        if not edu_text and tag_requirements:
            for t in tag_requirements:
                if any(w in t.lower() for w in ["đại học", "cao đẳng", "thạc sĩ"]):
                    edu_text = t
                    break

        raw_data = {
            "title": title,
            "company": company,
            "salary": salary_detail,
            "tags": tags_data,
            "description_list": desc_list,
            "requirements_list": req_list,
            "benefits_list": ben_list,
            "location_text": loc_text,
            "deadline_text": deadline_text,
            "posted_date_text": "",
            "employment_type_text": emp_type,
            "seniority_text": seniority,
            "extra": {
                "work_schedule": sched_text,
                "education": edu_text,
                "hiring_quantity": general_info.get("Số lượng tuyển"),
                "workplace_type": general_info.get("Hình thức làm việc"),
                "experience": exp_text,
            },
        }

        # Ưu tiên nhận diện ngôn ngữ trên phần nội dung mô tả công việc
        lang = detect_language(desc_text) if desc_text else detect_language(f"{title} {company}")

        return JobRecord.create(
            source=self.source_name,
            source_job_id=job_id,
            url=job_url,
            batch_id=self.batch_id,
            raw_data=raw_data,
            crawler_version=self.crawler_version,
            language=lang,
        )


def main():
    parser = argparse.ArgumentParser(description="TopCV IT Job Two-Phase Crawler (URL Discovery & Detail Extraction)")
    parser.add_argument("--phase", type=str, choices=["all", "discovery", "details", "view"], default="all", help="Pha cần chạy: discovery (Pha 1), details (Pha 2), all (cả hai), view (xem link đã lưu)")
    parser.add_argument("--max-pages", type=int, default=None, help="Số trang danh mục tối đa cần quét ở Pha 1 (mặc định: quét hết)")
    parser.add_argument("--max-items", type=int, default=5, help="Số tin tối đa cần cào ở Pha 2 / legacy")
    parser.add_argument("--min-delay", type=float, default=3.0, help="Thời gian nghỉ tối thiểu giữa các request (giây)")
    parser.add_argument("--max-delay", type=float, default=5.5, help="Thời gian nghỉ tối đa giữa các request (giây)")
    parser.add_argument("--output-dir", type=str, default="data/topcv", help="Thư mục gốc lưu trữ dữ liệu (mặc định: data/topcv)")
    parser.add_argument("--checkpoint-dir", type=str, default=None, help="Thư mục lưu checkpoint")
    parser.add_argument("--save-html", action="store_true", default=False, help="Lưu file HTML chi tiết (mặc định tắt)")
    parser.add_argument("--local-html-dir", type=str, default=None, help="Thư mục chứa HTML cục bộ để parse nhanh offline")
    parser.add_argument("--view-ledger", action="store_true", default=False, help="Xem bảng kiểm kê URL Ledger đã lưu")
    parser.add_argument("--minio", action="store_true", default=False, help="Đọc dữ liệu URL Ledger từ MinIO khi xem")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.view_ledger or args.phase == "view":
        from scripts.view_urls import load_local_ledger, load_minio_ledger, render_dashboard
        if args.minio:
            res = load_minio_ledger(source="topcv")
        else:
            res = load_local_ledger(source="topcv")
        if res["exists"] and res["records"]:
            render_dashboard(res["records"], source="topcv", source_path=res["source_path"], is_minio=args.minio)
        else:
            print(f"⚠️ Chưa có dữ liệu URL Ledger tại: {res['source_path']}")
        return

    crawler = TopCVCrawler(
        checkpoint_dir=args.checkpoint_dir,
        output_dir=args.output_dir,
        max_items=args.max_items,
        save_html=args.save_html,
        local_html_dir=args.local_html_dir,
        min_delay=args.min_delay,
        max_delay=args.max_delay,
    )

    if args.phase == "discovery":
        total = crawler.discover_urls(max_pages=args.max_pages)
        print(f"Pha 1 Discovery hoàn thành. Tổng số URL ghi nhận: {total}")
    elif args.phase == "details":
        stats = crawler.crawl_details(limit=args.max_items)
        print("Pha 2 Detail Extraction hoàn thành:", stats)
    else:
        # Mặc định: Chạy cả 2 pha hoặc run legacy
        crawler.discover_urls(max_pages=args.max_pages or 1)
        stats = crawler.crawl_details(limit=args.max_items)
        print("Crawl hoàn tất:", stats)


if __name__ == "__main__":
    main()
