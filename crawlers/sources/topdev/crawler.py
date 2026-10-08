# -*- coding: utf-8 -*-
"""Crawler nguồn TopDev (https://topdev.vn).

Owner: Sơn (refactored to single file BaseCrawler architecture).
API: https://api.topdev.vn/td/v2/jobs
Cung cấp đầy đủ thông tin chi tiết (mô tả, yêu cầu, phúc lợi, kỹ năng, địa điểm, mức lương).
"""

import argparse
import logging
import sys
import time
from typing import Any, Dict, Generator, List, Optional
from urllib.parse import urljoin

from crawlers.base.base_crawler import BaseCrawler
from crawlers.common.http_client import DelayConfig, HttpClient
from crawlers.common.schema import JobRecord
from crawlers.common.utils import strip_html_tags

log = logging.getLogger("topdev.crawler")

SOURCE = "topdev"
CRAWLER_VERSION = "0.2.0"
BASE_URL = "https://topdev.vn"
API_ENDPOINT = "https://api.topdev.vn/td/v2/jobs"
PAGE_SIZE = 15
DEFAULT_FIELDS = (
    "id,title,slug,company,salary,skills,addresses,job_types,levels,"
    "experiences,published_at,refreshed_at,content,requirements_arr,"
    "requirements_original,responsibilities,responsibilities_original,benefits_v2"
)


class TopDevCrawler(BaseCrawler):
    """Crawler cho nguồn TopDev qua REST API chính thức."""

    source_name = SOURCE
    crawler_version = CRAWLER_VERSION

    def __init__(
        self,
        checkpoint_dir: Optional[str] = None,
        output_dir: Optional[str] = None,
        max_items: Optional[int] = 30,
        checkpoint_interval: int = 10,
        http_client: Optional[HttpClient] = None,
    ) -> None:
        super().__init__(
            checkpoint_dir=checkpoint_dir,
            output_dir=output_dir,
            max_items=max_items,
            checkpoint_interval=checkpoint_interval,
        )
        self.http_client = http_client or HttpClient(
            source=self.source_name,
            delay_config=DelayConfig(min_seconds=1.5, max_seconds=3.0),
            timeout=20,
        )

    def fetch_items(self) -> Generator[Dict[str, Any], None, None]:
        """Duyệt phân trang từ API TopDev và yield từng job dictionary."""
        page = 1
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://topdev.vn/viec-lam/tim-kiem",
        }

        while True:
            params = {
                "page": page,
                "page_size": PAGE_SIZE,
                "fields[job]": DEFAULT_FIELDS,
            }
            log.info("[TopDev] Fetching page %d...", page)

            try:
                resp = self.http_client.get(API_ENDPOINT, params=params, headers=headers)
                data = resp.json()
            except Exception as exc:
                log.error("[TopDev] Failed to fetch page %d: %s", page, exc)
                break

            job_list = data.get("data", [])
            if not job_list:
                log.info("[TopDev] No more jobs found at page %d.", page)
                break

            for job in job_list:
                yield job

            meta = data.get("meta", {})
            last_page = meta.get("last_page", page)
            if page >= last_page:
                log.info("[TopDev] Reached last page (%d).", last_page)
                break

            page += 1

    def parse_item(self, item: Dict[str, Any]) -> Optional[JobRecord]:
        """Biến đổi raw JSON từ TopDev thành đối tượng JobRecord."""
        raw_id = item.get("id")
        if not raw_id:
            return None
        job_id = str(raw_id).strip()

        # Build clean URL
        slug = item.get("slug")
        if slug:
            job_url = f"https://topdev.vn/detail-jobs/{slug}-{job_id}"
        else:
            job_url = item.get("detail_url") or f"https://topdev.vn/detail-jobs/{job_id}"

        title = (item.get("title") or "").strip()
        if not title:
            return None

        # Company info
        company_data = item.get("company") or {}
        company_name = (
            company_data.get("display_name")
            or company_data.get("name")
            or "Unknown"
        ).strip()

        # Location
        addresses_obj = item.get("addresses") or {}
        location = (
            addresses_obj.get("address_region_list")
            or addresses_obj.get("sort_addresses")
            or ""
        ).strip()

        # Salary
        salary_obj = item.get("salary") or {}
        if salary_obj.get("is_negotiable") == "1" and not salary_obj.get("value"):
            salary_raw = "Thương lượng"
        else:
            s_min = salary_obj.get("min")
            s_max = salary_obj.get("max")
            curr = salary_obj.get("currency", "VND")
            if s_min and s_max and s_min != "*" and s_max != "*":
                salary_raw = f"{s_min} - {s_max} {curr}"
            elif salary_obj.get("value"):
                salary_raw = f"{salary_obj.get('value')} {curr}"
            else:
                salary_raw = "Thương lượng"

        # Skills
        skill_items = item.get("skills") or []
        skills_list = []
        for s in skill_items:
            name = s.get("name_vi") or s.get("name_en")
            if name:
                skills_list.append(name.strip())
        skills_text = ", ".join(skills_list) if skills_list else None

        # Content HTML
        description_html = (
            item.get("content")
            or item.get("responsibilities_original")
            or item.get("responsibilities")
            or f"<p>{title} at {company_name}</p>"
        )

        requirements = (
            item.get("requirements_original")
            or item.get("requirements_arr")
        )
        if isinstance(requirements, list):
            req_cleaned = [strip_html_tags(str(r)) for r in requirements if r]
            requirements_text = "\n".join(r for r in req_cleaned if r) or None
        else:
            requirements_text = strip_html_tags(str(requirements)) if requirements else None

        benefits = item.get("benefits_v2")
        benefits_list = []
        if isinstance(benefits, list):
            for b in benefits:
                if isinstance(b, dict):
                    b_name = (b.get("name") or "").strip()
                    b_desc_raw = b.get("description") or ""
                    b_desc = strip_html_tags(b_desc_raw) if b_desc_raw else ""
                    if b_name and b_desc:
                        benefits_list.append(f"{b_name}: {b_desc}")
                    elif b_name:
                        benefits_list.append(b_name)
                    elif b_desc:
                        benefits_list.append(b_desc)
                elif isinstance(b, str):
                    cleaned = strip_html_tags(b)
                    if cleaned:
                        benefits_list.append(cleaned)
        elif isinstance(benefits, str):
            cleaned = strip_html_tags(benefits)
            if cleaned:
                benefits_list.append(cleaned)
        benefits_text = "\n".join(benefits_list) if benefits_list else None

        # Job type / Seniority
        job_types = item.get("job_types")
        job_type_str = str(job_types) if job_types else None
        levels = item.get("levels")
        seniority_str = str(levels) if levels else None

        raw_data = {
            "title": title,
            "company": company_name,
            "description_html": description_html,
            "description_text": strip_html_tags(description_html),
            "salary_text": salary_raw,
            "location_text": location or None,
            "skills_text": skills_text,
            "experience_text": str(item.get("experiences")) if item.get("experiences") else None,
            "employment_type_text": job_type_str,
            "seniority_text": seniority_str,
            "requirements_text": requirements_text,
            "benefits_text": benefits_text,
            "posted_date_text": str(item.get("published_at") or item.get("refreshed_at") or ""),
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
    parser = argparse.ArgumentParser(description="TopDev IT Job Crawler")
    parser.add_argument("--max-items", type=int, default=30, help="Số tin tối đa cần cào")
    parser.add_argument("--output-dir", type=str, default="data", help="Thư mục xuất dữ liệu")
    parser.add_argument("--checkpoint-dir", type=str, default=None, help="Thư mục lưu checkpoint")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    crawler = TopDevCrawler(
        checkpoint_dir=args.checkpoint_dir,
        output_dir=args.output_dir,
        max_items=args.max_items,
    )
    result = crawler.run()
    print("Crawl completed:", result)


if __name__ == "__main__":
    main()
