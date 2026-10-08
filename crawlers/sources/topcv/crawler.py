# -*- coding: utf-8 -*-
"""Crawler nguồn TopCV (https://www.topcv.vn) — Nguồn được bảo vệ bởi Cloudflare.

Owner: Thuận (refactored to single file BaseCrawler architecture).
Cơ chế: Sử dụng Google Chrome headless với persistent context để vượt qua Cloudflare Challenge.
Nếu chạy trong môi trường headless bị chặn, crawler sẽ chuyển sang chế độ fallback hoặc ghi nhận lỗi theo quy chuẩn.
"""

import argparse
import asyncio
import logging
import re
import sys
from typing import Any, Dict, Generator, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from crawlers.base.base_crawler import BaseCrawler
from crawlers.common.schema import JobRecord
from crawlers.common.utils import clean_text, strip_html_tags

log = logging.getLogger("topcv.crawler")

SOURCE = "topcv"
CRAWLER_VERSION = "0.2.0"
BASE_URL = "https://www.topcv.vn"
START_URL = "https://www.topcv.vn/viec-lam-it"


class TopCVCrawler(BaseCrawler):
    """Crawler cho nguồn TopCV sử dụng Playwright / Chrome browser."""

    source_name = SOURCE
    crawler_version = CRAWLER_VERSION

    def __init__(
        self,
        checkpoint_dir: Optional[str] = None,
        output_dir: Optional[str] = None,
        max_items: Optional[int] = 30,
        checkpoint_interval: int = 10,
        chrome_path: str = "/usr/bin/google-chrome",
        headless: bool = True,
    ) -> None:
        super().__init__(
            checkpoint_dir=checkpoint_dir,
            output_dir=output_dir,
            max_items=max_items,
            checkpoint_interval=checkpoint_interval,
        )
        self.chrome_path = chrome_path
        self.headless = headless

    def _sync_fetch_with_playwright(self) -> List[Dict[str, Any]]:
        """Hàm đồng bộ bọc async Playwright để crawl listing cards."""
        from playwright.sync_api import sync_playwright

        items: List[Dict[str, Any]] = []

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
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1920, "height": 1080},
                )
                page = context.new_page()

                log.info("[TopCV] Navigating to %s...", START_URL)
                page.goto(START_URL, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(4000)

                content = page.content()
                if "Attention Required! | Cloudflare" in content:
                    log.warning("[TopCV] Cloudflare challenge detected! Retrying with extra wait...")
                    page.wait_for_timeout(6000)
                    content = page.content()

                soup = BeautifulSoup(content, "html.parser")
                cards = soup.select(".job-item-search-result, .job-item, div[data-job-id]")
                log.info("[TopCV] Found %d job cards on page.", len(cards))

                for card in cards:
                    # Lấy link chi tiết chứa tiêu đề (bỏ qua thẻ avatar rỗng)
                    a_tag = None
                    for a in card.select("a[href*='/viec-lam/']"):
                        if clean_text(a.text):
                            a_tag = a
                            break
                    if not a_tag:
                        continue
                    url = a_tag.get("href")
                    title = clean_text(a_tag.text)
                    comp_tag = card.select_one(".company, .company-name, a.company, a[href*='/cong-ty/']")
                    comp = clean_text(comp_tag.text) if comp_tag else "Unknown"
                    sal_tag = card.select_one(".salary, .title-salary, span.salary")
                    sal = clean_text(sal_tag.text) if sal_tag else "Thương lượng"

                    # Lấy thông tin phụ
                    city_tag = card.select_one(".city-text, .address, span.address")
                    city = clean_text(city_tag.text) if city_tag else None

                    exp_tag = card.select_one(".exp, span.exp")
                    exp = clean_text(exp_tag.text) if exp_tag else None

                    job_id = card.get("data-job-id")
                    if not job_id and url:
                        m = re.search(r"[-_/](\d+)\.html", url)
                        job_id = m.group(1) if m else None

                    if title and url and job_id:
                        items.append({
                            "job_id": str(job_id),
                            "url": urljoin(BASE_URL, url),
                            "title": title,
                            "company": comp,
                            "salary": sal,
                            "location": city,
                            "experience": exp,
                            "html_snippet": str(card),
                        })

                browser.close()
        except Exception as exc:
            log.error("[TopCV] Error running Playwright: %s", exc)

        return items

    def fetch_items(self) -> Generator[Dict[str, Any], None, None]:
        """Fetch job cards."""
        items = self._sync_fetch_with_playwright()
        for item in items:
            yield item

    def parse_item(self, item: Dict[str, Any]) -> Optional[JobRecord]:
        """Parse raw job card thành JobRecord."""
        job_id = item.get("job_id")
        job_url = item.get("url")
        title = item.get("title")
        company = item.get("company")

        if not job_id or not job_url or not title:
            return None

        desc_html = item.get("html_snippet") or f"<p>{title} at {company}</p>"
        desc_text = strip_html_tags(desc_html)

        raw_data = {
            "title": title,
            "company": company,
            "description_html": desc_html,
            "description_text": desc_text,
            "salary_text": item.get("salary") or "Thương lượng",
            "location_text": item.get("location"),
            "skills_text": None,
            "experience_text": item.get("experience"),
            "employment_type_text": None,
            "seniority_text": None,
            "requirements_text": None,
            "benefits_text": None,
            "posted_date_text": "",
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
    parser = argparse.ArgumentParser(description="TopCV IT Job Crawler")
    parser.add_argument("--max-items", type=int, default=30, help="Số tin tối đa cần cào")
    parser.add_argument("--output-dir", type=str, default="data", help="Thư mục xuất dữ liệu")
    parser.add_argument("--checkpoint-dir", type=str, default=None, help="Thư mục lưu checkpoint")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    crawler = TopCVCrawler(
        checkpoint_dir=args.checkpoint_dir,
        output_dir=args.output_dir,
        max_items=args.max_items,
    )
    result = crawler.run()
    print("Crawl completed:", result)


if __name__ == "__main__":
    main()
