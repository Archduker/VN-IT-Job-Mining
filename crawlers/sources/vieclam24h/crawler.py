# -*- coding: utf-8 -*-
"""Crawler nguồn Việc Làm 24h (https://vieclam24h.vn) — Nguồn 6 (thay thế LinkedIn).

Owner: Phúc / Hệ thống VN-IT-Job-Mining.
Kiến trúc: BaseCrawler, trích xuất dữ liệu qua SSR __NEXT_DATA__ và Schema.org JobPosting.
"""

import argparse
import json
import logging
import re
import sys
from typing import Any, Dict, Generator, List, Optional
from urllib.parse import quote_plus, urljoin

from crawlers.base.base_crawler import BaseCrawler
from crawlers.common.http_client import DelayConfig, HttpClient
from crawlers.common.schema import JobRecord
from crawlers.common.utils import clean_text, strip_html_tags

log = logging.getLogger("vieclam24h.crawler")

SOURCE = "vieclam24h"
CRAWLER_VERSION = "0.2.0"
BASE_URL = "https://vieclam24h.vn"
SEARCH_URL = "https://vieclam24h.vn/tim-kiem-viec-lam-nhanh"
IT_KEYWORDS = ["it", "developer", "backend", "frontend", "tester", "phan-mem"]
MAX_PAGES_PER_KEYWORD = 10


class ViecLam24hCrawler(BaseCrawler):
    """Crawler cho nguồn Việc Làm 24h."""

    source_name = SOURCE
    crawler_version = CRAWLER_VERSION

    def __init__(
        self,
        checkpoint_dir: Optional[str] = None,
        output_dir: Optional[str] = None,
        max_items: Optional[int] = 30,
        checkpoint_interval: int = 10,
        http_client: Optional[HttpClient] = None,
        keywords: Optional[List[str]] = None,
    ) -> None:
        super().__init__(
            checkpoint_dir=checkpoint_dir,
            output_dir=output_dir,
            max_items=max_items,
            checkpoint_interval=checkpoint_interval,
        )
        self.keywords = keywords or IT_KEYWORDS
        self.http_client = http_client or HttpClient(
            source=self.source_name,
            delay_config=DelayConfig(min_seconds=1.5, max_seconds=3.0),
            timeout=25,
        )

    def fetch_items(self) -> Generator[Dict[str, Any], None, None]:
        """Tìm kiếm theo keywords IT và yield raw job item từ __NEXT_DATA__."""
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": BASE_URL,
        }

        seen_ids_in_run = set()

        for kw in self.keywords:
            log.info("[ViecLam24h] Crawling keyword '%s'...", kw)
            for page in range(1, MAX_PAGES_PER_KEYWORD + 1):
                url = f"{SEARCH_URL}?key={quote_plus(kw)}"
                if page > 1:
                    url += f"&page={page}"

                try:
                    html = self.http_client.get_html(url, headers=headers)
                except Exception as exc:
                    log.error("[ViecLam24h] Failed to fetch page %d for kw '%s': %s", page, kw, exc)
                    break

                match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
                if not match:
                    log.warning("[ViecLam24h] No __NEXT_DATA__ found at %s", url)
                    break

                try:
                    payload = json.loads(match.group(1))
                    items = (
                        payload.get("props", {})
                        .get("initialState", {})
                        .get("api", {})
                        .get("getJobList", {})
                        .get("data", {})
                        .get("items", [])
                    )
                except Exception as exc:
                    log.error("[ViecLam24h] Error parsing __NEXT_DATA__: %s", exc)
                    break

                if not items:
                    log.info("[ViecLam24h] No jobs found at page %d for kw '%s'.", page, kw)
                    break

                for it in items:
                    jid = str(it.get("id"))
                    if jid and jid not in seen_ids_in_run:
                        seen_ids_in_run.add(jid)
                        yield it

    def parse_item(self, item: Dict[str, Any]) -> Optional[JobRecord]:
        """Parse raw job dictionary từ __NEXT_DATA__ thành JobRecord."""
        raw_id = item.get("id")
        if not raw_id:
            return None
        job_id = str(raw_id).strip()

        title = clean_text(item.get("title") or "")
        if not title:
            return None

        slug = item.get("title_slug") or "job"
        job_url = f"{BASE_URL}/{slug}-id{job_id}.html"

        employer_info = item.get("employer_info") or {}
        company = clean_text(
            employer_info.get("name")
            or item.get("employer_name")
            or "Doanh nghiệp ẩn danh"
        )

        # Requirements and Description
        desc_html = item.get("job_requirement_html") or item.get("job_requirement") or ""
        if not desc_html:
            desc_html = f"<p>Tuyển dụng {title} tại {company}</p>"
        desc_text = strip_html_tags(desc_html)

        req_html = item.get("other_requirement_html") or item.get("other_requirement") or ""
        req_text = strip_html_tags(req_html) if req_html else None

        # Salary
        sal_min = item.get("salary_min")
        sal_max = item.get("salary_max")
        if sal_min and sal_max:
            salary_raw = f"{sal_min} - {sal_max} VND"
        else:
            salary_raw = "Thương lượng"

        # Places / location
        places = item.get("places") or []
        loc_list = []
        if isinstance(places, list):
            for p in places:
                if isinstance(p, dict):
                    loc_list.append(str(p.get("city_name") or p.get("address") or ""))
                elif isinstance(p, str):
                    loc_list.append(p)
        location_text = ", ".join([l for l in loc_list if l]) or None

        raw_data = {
            "title": title,
            "company": company,
            "description_html": desc_html,
            "description_text": desc_text,
            "salary_text": salary_raw,
            "location_text": location_text,
            "skills_text": None,
            "experience_text": str(item.get("experience_range")) if item.get("experience_range") else None,
            "employment_type_text": str(item.get("working_method")) if item.get("working_method") else None,
            "seniority_text": str(item.get("level_requirement")) if item.get("level_requirement") else None,
            "requirements_text": req_text,
            "benefits_text": None,
            "posted_date_text": str(item.get("created_at") or ""),
        }

        return JobRecord.create(
            source=self.source_name,
            source_job_id=job_id,
            url=job_url,
            batch_id=self.batch_id,
            raw_data=raw_data,
            crawler_version=self.crawler_version,
        )


def main():
    parser = argparse.ArgumentParser(description="ViecLam24h IT Job Crawler")
    parser.add_argument("--max-items", type=int, default=30, help="Số tin tối đa cần cào")
    parser.add_argument("--output-dir", type=str, default="data", help="Thư mục xuất dữ liệu")
    parser.add_argument("--checkpoint-dir", type=str, default=None, help="Thư mục lưu checkpoint")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    crawler = ViecLam24hCrawler(
        checkpoint_dir=args.checkpoint_dir,
        output_dir=args.output_dir,
        max_items=args.max_items,
    )
    result = crawler.run()
    print("Crawl completed:", result)


if __name__ == "__main__":
    main()
