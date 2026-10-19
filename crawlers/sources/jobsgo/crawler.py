# -*- coding: utf-8 -*-
"""Crawler việc làm JobsGO Việt Nam (https://jobsgo.vn).

Thu thập thông tin việc làm CNTT qua SSR HTML (listing và trang chi tiết).
Tuân thủ chuẩn BaseCrawler, 2-Phase URL Ledger, Safe Skip và chu kỳ Re-crawl 21 ngày.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from crawlers.base.base_crawler import BaseCrawler
from crawlers.common.http_client import DelayConfig, HttpClient, RetryConfig
from crawlers.common.schema import JobMetadata, JobRaw, JobRecord, JobSalary, JobTags
from crawlers.common.url_ledger import UrlLedger, clean_canonical_url
from crawlers.common.utils import (
    clean_text,
    detect_language,
    parse_salary_detail,
    strip_html_tags,
    text_to_clean_lines,
)

log = logging.getLogger("jobsgo.crawler")

SOURCE = "jobsgo"
CRAWLER_VERSION = "1.0.0"
BASE_URL = "https://jobsgo.vn"
START_URL = "https://jobsgo.vn/viec-lam-cong-nghe-thong-tin.html"
LOCAL_TIMEZONE = timezone(timedelta(hours=7))


class JobsGoCrawler(BaseCrawler):
    """Crawler nguồn JobsGO kế thừa BaseCrawler chuẩn hóa Data Contract Schema v1."""

    source_name = SOURCE
    crawler_version = CRAWLER_VERSION

    def __init__(
        self,
        checkpoint_dir: str | None = None,
        output_dir: str | None = None,
        max_items: int | None = 30,
        checkpoint_interval: int = 10,
        http_client: HttpClient | None = None,
        max_pages: int | None = 5,
    ) -> None:
        super().__init__(
            checkpoint_dir=checkpoint_dir,
            output_dir=output_dir,
            max_items=max_items,
            checkpoint_interval=checkpoint_interval,
        )
        self.max_pages = max_pages or 5
        self.http_client = http_client or HttpClient(
            source=self.source_name,
            delay_config=DelayConfig(min_seconds=1.5, max_seconds=3.0),
            retry_config=RetryConfig(max_retries=3, backoff_factor=1.0),
            timeout=25,
            extra_headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Referer": BASE_URL,
            },
        )
        self.ledger = UrlLedger(
            source=self.source_name,
            storage_dir=os.path.join(self.output_dir or "data/jobsgo", "url_ledger"),
        )

    def _extract_job_id(self, url: str) -> str:
        m = re.search(r"-([0-9]+)\.html", url)
        if m:
            return m.group(1)
        return hashlib.md5(url.encode()).hexdigest()[:10]

    # ── PHA 1: URL DISCOVERY ──────────────────────────────────────────
    def discover_urls(self, max_pages: int | None = None) -> list[str]:
        """Pha 1: Quét danh mục việc làm CNTT JobsGO, lưu vào UrlLedger & MinIO."""
        log.info("[JobsGO] === Bắt đầu Pha 1: URL Discovery ===")
        discovered_urls: list[str] = []
        pages_to_crawl = max_pages or self.max_pages

        for page in range(1, pages_to_crawl + 1):
            page_url = f"{START_URL}?page={page}" if page > 1 else START_URL
            try:
                resp = self.http_client.get(page_url)
                if not resp or resp.status_code != 200:
                    break
                soup = BeautifulSoup(resp.text, "html.parser")
                job_cards = soup.select("div.h-job-item, div.job-item, div.item")
                if not job_cards:
                    break
                for card in job_cards:
                    a_tag = card.select_one("h3 a, a.job-link, a[href*='/viec-lam/']")
                    if not a_tag or not a_tag.get("href"):
                        continue
                    raw_href = a_tag["href"]
                    clean_url = clean_canonical_url(urljoin(BASE_URL, raw_href))
                    job_id = self._extract_job_id(clean_url)
                    title = clean_text(a_tag.text)
                    comp_tag = card.select_one("div.company-name, a.company, .employer")
                    company = clean_text(comp_tag.text) if comp_tag else ""
                    self.ledger.register_url(
                        raw_url=clean_url,
                        job_id=job_id,
                        preliminary_title=title,
                        preliminary_company=company,
                    )
                    discovered_urls.append(clean_url)
            except Exception as exc:
                log.warning("[JobsGO] Safe Skip trang listing %d: %s", page, exc)
                continue

        self.ledger.save_catalog()
        self.ledger.export_daily_manifest()
        log.info("[JobsGO] Pha 1 hoàn thành: phát hiện %d URLs.", len(discovered_urls))
        return discovered_urls

    # ── PHA 2: DETAIL EXTRACTION ──────────────────────────────────────
    def crawl_details(self, limit: int | None = None) -> dict[str, int]:
        """Pha 2: Bóc tách SSR HTML chi tiết với Safe Skip và chu kỳ Re-crawl 21 ngày."""
        log.info("[JobsGO] === Bắt đầu Pha 2: Detail Extraction (Chu kỳ Re-crawl 21 ngày) ===")
        pending = self.ledger.get_pending_or_due_records(recheck_days=21)
        log.info("[JobsGO] Tìm thấy %d tin cần crawl chi tiết trong Ledger.", len(pending))
        stats = {"success": 0, "failed": 0, "skipped": 0}
        count = 0

        for item in pending:
            if limit and count >= limit:
                break
            url = item["canonical_url"]
            url_hash = item["url_hash"]
            job_id = item["job_id"]
            try:
                # Safe Skip block
                resp = self.http_client.get(url)
                if not resp or resp.status_code != 200:
                    raise RuntimeError(f"HTTP Error {resp.status_code if resp else 'No response'} for {url}")
                record = self.parse_item({
                    "job_id": job_id,
                    "url": url,
                    "html": resp.text,
                    "preliminary_title": item.get("preliminary_title"),
                    "preliminary_company": item.get("preliminary_company"),
                })
                if not record:
                    raise ValueError(f"Không thể parse JobRecord cho {url}")

                raw_out_dir = Path(self.output_dir or "data/jobsgo") / "raw"
                raw_out_dir.mkdir(parents=True, exist_ok=True)
                snapshot_file = raw_out_dir / f"{job_id}_v1.json"
                with open(snapshot_file, "w", encoding="utf-8") as f:
                    json.dump(record.model_dump(), f, ensure_ascii=False, indent=2)

                content_hash = hashlib.md5(json.dumps(record.raw.model_dump(), sort_keys=True).encode()).hexdigest()
                self.ledger.mark_scraped(url_hash=url_hash, content_hash=content_hash, version=1, http_status=200)
                stats["success"] += 1
                count += 1
            except Exception as exc:
                log.warning("[JobsGO] Safe Skip lỗi cào chi tiết %s (ID %s): %s", url, job_id, exc)
                self.ledger.mark_failed(url_hash=url_hash, error_message=str(exc))
                stats["failed"] += 1
                continue

        self.ledger.save_catalog()
        log.info("[JobsGO] Pha 2 hoàn tất: %s", stats)
        return stats

    def fetch_items(self) -> Generator[dict[str, Any], None, None]:
        """Triển khai fetch_items tương thích BaseCrawler."""
        urls = self.discover_urls(max_pages=2)
        for url in urls:
            job_id = self._extract_job_id(url)
            try:
                resp = self.http_client.get(url)
                if resp and resp.status_code == 200:
                    yield {"job_id": job_id, "url": url, "html": resp.text}
            except Exception as exc:
                log.warning("[JobsGO] Lỗi tải %s: %s", url, exc)
                continue

    def parse_item(self, item: dict[str, Any]) -> JobRecord | None:
        """Chuẩn hóa dữ liệu JobsGO sang Data Contract Schema v1."""
        html = item.get("html", "")
        url = item.get("url", "")
        job_id = item.get("job_id", self._extract_job_id(url))
        soup = BeautifulSoup(html, "html.parser")

        title_el = soup.select_one("h1.job-title, h1.title, .job-detail h1")
        title = clean_text(title_el.text) if title_el else item.get("preliminary_title", "")
        if not title:
            return None

        comp_el = soup.select_one(".company-name, .employer-name, .company a")
        company = clean_text(comp_el.text) if comp_el else item.get("preliminary_company", "Công ty JobsGO")

        # Lương
        salary_el = soup.select_one(".salary, .job-salary, .badge-salary")
        salary_text = clean_text(salary_el.text) if salary_el else "Thương lượng"
        parsed_sal = parse_salary_detail(salary_text)
        job_salary = JobSalary(
            salary_text=salary_text,
            salary_min=parsed_sal["salary_min"],
            salary_max=parsed_sal["salary_max"],
            salary_currency=parsed_sal["salary_currency"],
            pay_period=parsed_sal["pay_period"] or "month",
            is_negotiable=parsed_sal["is_negotiable"] or ("thỏa thuận" in salary_text.lower() or "thương lượng" in salary_text.lower()),
            has_commission=parsed_sal["has_commission"],
        )

        # Mô tả và yêu cầu
        desc_list: list[str] = []
        req_list: list[str] = []
        benefit_list: list[str] = []

        desc_block = soup.select_one(".job-description, #job-description, .description")
        if desc_block:
            desc_list = text_to_clean_lines(desc_block.get_text("\n"))

        req_block = soup.select_one(".job-requirements, #job-requirements, .requirement")
        if req_block:
            req_list = text_to_clean_lines(req_block.get_text("\n"))

        benefit_block = soup.select_one(".job-benefits, #job-benefits, .benefit")
        if benefit_block:
            benefit_list = text_to_clean_lines(benefit_block.get_text("\n"))

        tags_skills = [clean_text(s.text) for s in soup.select(".skill-tag, .tag, .badge-skill") if clean_text(s.text)]

        metadata = JobMetadata(
            source=self.source_name,
            source_job_id=str(job_id),
            url=url,
            dedup_key=f"{self.source_name}:{job_id}",
            crawled_at=datetime.now(LOCAL_TIMEZONE),
            batch_id=self.batch_id,
            crawler_version=self.crawler_version,
            language=detect_language(f"{title} {' '.join(desc_list)}"),
        )

        raw = JobRaw(
            title=title,
            company=company,
            description_list=desc_list or [title],
            salary=job_salary,
            tags=JobTags(requirements=None, benefits=None, skills=tags_skills or ["IT"]),
            requirements_list=req_list,
            benefits_list=benefit_list,
            location_text="Hồ Chí Minh",
            deadline_text=None,
            posted_date_text=None,
            employment_type_text="Toàn thời gian",
            seniority_text=None,
            extra={},
        )

        return JobRecord(_meta=metadata, raw=raw)


"""JobsGO Vietnam raw-first crawler (SSR HTML listing/detail pages)."""

import base64
import logging
import re
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from crawlers.common.minio_raw_pipeline import TwoPhaseRawCrawler, safe_object_part
from crawlers.common.url_ledger import clean_canonical_url

logger = logging.getLogger(__name__)

SOURCE = "jobsgo"
LISTING_URL = "https://jobsgo.vn/viec-lam-cong-nghe-thong-tin.html"
JOB_PATH_RE = re.compile(r"^/viec-lam/[^/]+-([0-9]+)\.html$", re.IGNORECASE)


class JobsGORawCrawler(TwoPhaseRawCrawler):
    """Two-phase JobsGO crawler preserving SSR HTML without early normalization."""

    source = SOURCE
    default_listing_url = LISTING_URL
    detail_selectors = (
        ".job-detail",
        "#job-detail",
        "main",
        "body",
    )

    def __init__(self, max_items: Optional[int] = 30, http_client: Any = None, listing_url: str = LISTING_URL, **kwargs: Any) -> None:
        super().__init__(max_items=max_items, http_client=http_client or requests.Session(), **kwargs)
        self.listing_url = listing_url
        self.http_client.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "identity",
            "Referer": "https://jobsgo.vn/",
        })

    @staticmethod
    def _job_id(url: str) -> str:
        match = JOB_PATH_RE.match(urlparse(url).path)
        return match.group(1) if match else __import__("hashlib").md5(url.encode("utf-8")).hexdigest()[:12]

    @staticmethod
    def _is_job_url(href: str) -> bool:
        parsed = urlparse(href)
        return parsed.netloc.lower() in {"jobsgo.vn", "www.jobsgo.vn"} and bool(JOB_PATH_RE.match(parsed.path))

    @staticmethod
    def _listing_page_links(html: str, base_url: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        base_path = urlparse(base_url).path
        links: list[str] = []
        for anchor in soup.select("a[href]"):
            text = anchor.get_text(" ", strip=True)
            href = urljoin(base_url, anchor.get("href", ""))
            parsed = urlparse(href)
            if parsed.netloc.lower() not in {"jobsgo.vn", "www.jobsgo.vn"}:
                continue
            # JobsGO's pagination uses links on the same category route, with a
            # page parameter or a pagination container. Do not follow all SEO links.
            inside_pagination = bool(anchor.find_parent(class_=re.compile("pagination|paging|page-list", re.I)))
            same_route = parsed.path == base_path
            has_page_param = any(k.lower() in {"page", "p", "trang"} for k in parse_qs(parsed.query))
            is_number = text.isdigit() or text in {"«", "»", "‹", "›", "Previous", "Next", "Trước", "Sau"}
            if same_route and (inside_pagination or has_page_param or (is_number and parsed.query)):
                clean = clean_canonical_url(href)
                if clean != clean_canonical_url(base_url) and clean not in links:
                    links.append(clean)
        return links

    @staticmethod
    def _card_for_anchor(anchor) -> Any:
        node = anchor
        for _ in range(6):
            node = getattr(node, "parent", None)
            if node is None:
                break
            classes = " ".join(node.get("class", [])) if getattr(node, "get", None) else ""
            text = node.get_text(" ", strip=True) if getattr(node, "get_text", None) else ""
            if len(text) > 25 and (re.search(r"job|viec|item|card|result", classes, re.I) or re.search(r"triệu|thỏa thuận|thoả thuận|full.time|kinh nghiệm", text, re.I)):
                return node
        return anchor.parent or anchor

    @staticmethod
    def _extract_card_payload(anchor, canonical_url: str) -> Tuple[str, str, Dict[str, Any]]:
        title = anchor.get_text(" ", strip=True)
        card = JobsGORawCrawler._card_for_anchor(anchor)
        card_text = card.get_text("\n", strip=True) if getattr(card, "get_text", None) else title
        company = ""
        for candidate in card.select("a[href]") if getattr(card, "select", None) else []:
            candidate_text = candidate.get_text(" ", strip=True)
            candidate_url = candidate.get("href", "")
            if candidate is not anchor and candidate_text and (
                "cong-ty" in candidate_url.lower() or "company" in candidate_url.lower()
                or candidate_text.lower().startswith(("công ty", "cty", "company"))
            ):
                company = candidate_text
                break
        if not company:
            lines = [x.strip() for x in card_text.splitlines() if x.strip()]
            company = next((x for x in lines if x.lower().startswith(("công ty", "cty", "company"))), "")
        payload = {
            "title": title,
            "company": company,
            "card_text": card_text,
            "raw_anchor_html": str(anchor),
            "raw_card_html": str(card),
            "canonical_url": canonical_url,
        }
        return title, company, payload

    def discover_urls(self, max_pages: Optional[int] = None) -> int:
        queue = [clean_canonical_url(self.listing_url)]
        visited_pages: set[str] = set()
        seen_jobs: set[str] = set()
        self._discovered_hashes.clear()
        self._manifest_entries.clear()
        full_scan = True
        page_count = 0
        reported_total = None
        last_range_end = None
        failed_pages: list[tuple[str, str]] = []

        while queue and (max_pages is None or page_count < max_pages):
            page_url = queue.pop(0)
            if page_url in visited_pages:
                continue
            visited_pages.add(page_url)
            page_count += 1
            response = None
            try:
                self._sleep()
                response = self.http_client.get(page_url, timeout=25, headers={"Accept-Encoding": "identity"})
                status = int(getattr(response, "status_code", 0))
                if status != 200:
                    raise RuntimeError(f"HTTP {status}")
                html = response.text
                if isinstance(html, bytes):
                    html = html.decode("utf-8", errors="replace")
                if not isinstance(html, str) or not html:
                    raise RuntimeError("Empty listing HTML")
            except Exception as exc:
                failed_pages.append((page_url, str(exc)))
                logger.exception("JobsGO listing page failed: %s", page_url)
                full_scan = False
                # Preserve the HTTP error page for diagnosis when the request returned a response.
                try:
                    failed_response = response
                    if failed_response is not None:
                        error_status = int(getattr(failed_response, "status_code", 0) or 0)
                        error_html = getattr(failed_response, "text", "")
                        error_key = f"raw/jobsgo/_listing_failures/{self._run_date}/page_{page_count:04d}.html"
                        if isinstance(error_html, bytes):
                            error_html = error_html.decode("utf-8", errors="replace")
                        if isinstance(error_html, str) and error_html:
                            self.store.put_text(error_key, error_html, "text/html; charset=utf-8")
                        self.store.put_json(error_key + ".json", {
                            "source": self.source, "url": page_url, "page": page_count,
                            "http_status": error_status, "error": str(exc),
                            "captured_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                        })
                except Exception:
                    logger.debug("Could not archive failed JobsGO listing response", exc_info=True)
                continue

            page_key = f"raw/jobsgo/_listing/{self._run_date}/page_{page_count:04d}.html"
            self.store.put_text(page_key, html, "text/html; charset=utf-8")
            raw_body = getattr(response, "content", None)
            if isinstance(raw_body, (bytes, bytearray)):
                # Save the exact response body bytes alongside decoded HTML.
                self.store.put_text(
                    page_key + ".body_base64.txt",
                    base64.b64encode(raw_body).decode("ascii"),
                    "text/plain; charset=us-ascii",
                )
            soup = BeautifulSoup(html, "html.parser")
            visible_listing_text = soup.get_text(" ", strip=True)
            count_match = re.search(r"Việc\s+(\d+)\s*[-–]\s*(\d+)\s*/\s*([\d.,]+)", visible_listing_text, re.IGNORECASE)
            if count_match:
                last_range_end = int(count_match.group(2))
                try:
                    reported_total = int(count_match.group(3).replace(".", "").replace(",", ""))
                except ValueError:
                    pass
            page_jobs = 0
            for anchor in soup.select("a[href]"):
                absolute = clean_canonical_url(urljoin(page_url, anchor.get("href", "")))
                if not self._is_job_url(absolute):
                    continue
                job_id = self._job_id(absolute)
                if job_id in seen_jobs:
                    continue
                title, company, payload = self._extract_card_payload(anchor, absolute)
                if not title:
                    continue
                seen_jobs.add(job_id)
                self.register_discovered(absolute, job_id, title, company, payload, page_key=page_key)
                page_jobs += 1
            for next_url in self._listing_page_links(html, page_url):
                if next_url not in visited_pages and next_url not in queue:
                    queue.append(next_url)

        # JobsGO pagination does not expose a structured hasMore flag. Any run
        # with an explicit page limit is treated as partial to avoid false CLOSED.
        if max_pages is not None and page_count >= max_pages:
            full_scan = False
        # If page metadata says more results exist but pagination links were not
        # discovered, do not call this a complete scan or increment absence counts.
        if reported_total is not None and last_range_end is not None and last_range_end < reported_total and not queue and max_pages is None:
            full_scan = False
            logger.warning("JobsGO listing reports %s results but pagination ended at %s; no CLOSED decisions this run.", reported_total, last_range_end)
        self._finish_discovery(full_scan=full_scan)
        logger.info("JobsGO discovery: %d unique job URLs; pages=%d; full_scan=%s; failed_pages=%d",
                    len(self._discovered_hashes), page_count, full_scan, len(failed_pages))
        if failed_pages:
            first_url, first_reason = failed_pages[0]
            raise RuntimeError(
                f"JobsGO discovery failed: {len(failed_pages)} listing page(s) failed, "
                f"{len(self._discovered_hashes)} job URLs discovered. "
                f"First URL: {first_url}, reason: {first_reason}"
            )
        return len(self._discovered_hashes)

    def fetch_detail(self, url: str) -> Dict[str, Any]:
        self._sleep()
        response = self.http_client.get(url, timeout=25, headers={"Accept-Encoding": "identity"})
        body = response.text
        if isinstance(body, bytes):
            body = body.decode("utf-8", errors="replace")
        return {
            "status_code": int(getattr(response, "status_code", 0)),
            "html": body,
            "final_url": getattr(response, "url", url),
            "content_type": getattr(response, "headers", {}).get("Content-Type"),
            "response_encoding": getattr(response, "encoding", None),
            "body_bytes_base64": (
                base64.b64encode(response.content).decode("ascii")
                if isinstance(getattr(response, "content", None), (bytes, bytearray))
                else None
            ),
        }
