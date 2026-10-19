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
