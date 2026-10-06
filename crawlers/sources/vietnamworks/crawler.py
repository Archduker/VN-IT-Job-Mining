# -*- coding: utf-8 -*-
"""Crawler nguồn VietnamWorks (https://www.vietnamworks.com).

Owner: Khoa (refactored to single file BaseCrawler architecture).
API: https://ms.vietnamworks.com/job-search/v1.0/search
Hỗ trợ tìm kiếm theo nhiều query IT, lấy trực tiếp thông tin việc làm và chi tiết HTML.
"""

import argparse
import logging
import sys
from typing import Any, Dict, Generator, List, Optional

from crawlers.base.base_crawler import BaseCrawler
from crawlers.common.http_client import DelayConfig, HttpClient
from crawlers.common.schema import JobRecord
from crawlers.common.utils import clean_text, strip_html_tags

log = logging.getLogger("vietnamworks.crawler")

SOURCE = "vietnamworks"
CRAWLER_VERSION = "0.2.0"
API_URL = "https://ms.vietnamworks.com/job-search/v1.0/search"
IT_QUERIES = [
    "software developer",
    "developer",
    "backend",
    "frontend",
    "fullstack",
    "data engineer",
    "devops",
    "tester",
    "qa qc",
    "cntt",
]
HITS_PER_PAGE = 50


class VietnamWorksCrawler(BaseCrawler):
    """Crawler cho nguồn VietnamWorks sử dụng Search API chính thức."""

    source_name = SOURCE
    crawler_version = CRAWLER_VERSION

    def __init__(
        self,
        checkpoint_dir: Optional[str] = None,
        output_dir: Optional[str] = None,
        max_items: Optional[int] = 30,
        checkpoint_interval: int = 10,
        http_client: Optional[HttpClient] = None,
        queries: Optional[List[str]] = None,
    ) -> None:
        super().__init__(
            checkpoint_dir=checkpoint_dir,
            output_dir=output_dir,
            max_items=max_items,
            checkpoint_interval=checkpoint_interval,
        )
        self.queries = queries or IT_QUERIES
        self.http_client = http_client or HttpClient(
            source=self.source_name,
            delay_config=DelayConfig(min_seconds=1.0, max_seconds=2.5),
            timeout=25,
        )

    def fetch_items(self) -> Generator[Dict[str, Any], None, None]:
        """Lần lượt gửi POST request đến search API theo từng query IT."""
        headers = {
            "Content-Type": "application/json",
            "X-Source": "Page-Container",
            "Origin": "https://www.vietnamworks.com",
            "Referer": "https://www.vietnamworks.com/viec-lam?q=it",
        }

        seen_in_run = set()

        for q in self.queries:
            page = 0
            log.info("[VietnamWorks] Searching query: '%s'...", q)

            while True:
                payload = {
                    "userId": 0,
                    "query": q,
                    "filter": [],
                    "ranges": [],
                    "order": [],
                    "hitsPerPage": HITS_PER_PAGE,
                    "page": page,
                }

                try:
                    resp = self.http_client.post(
                        API_URL,
                        json=payload,
                        headers=headers,
                    )
                    data = resp.json()
                except Exception as exc:
                    log.error("[VietnamWorks] Search error for query '%s' page %d: %s", q, page, exc)
                    break

                job_list = data.get("data", [])
                if not job_list:
                    log.info("[VietnamWorks] Query '%s' finished at page %d (no more results)", q, page)
                    break

                for job in job_list:
                    jid = job.get("jobId")
                    if jid and jid not in seen_in_run:
                        seen_in_run.add(jid)
                        yield job

                # Nếu số item trả về ít hơn HITS_PER_PAGE => đã là trang cuối
                if len(job_list) < HITS_PER_PAGE:
                    break

                page += 1

    def parse_item(self, item: Dict[str, Any]) -> Optional[JobRecord]:
        """Biến đổi raw JSON từ VietnamWorks thành JobRecord."""
        raw_id = item.get("jobId")
        if not raw_id:
            return None
        job_id = str(raw_id).strip()

        title = (item.get("jobTitle") or "").strip()
        if not title:
            return None

        job_url = item.get("jobUrl") or f"https://www.vietnamworks.com/job-{job_id}-jv"
        company_name = (item.get("companyName") or "Unknown").strip()

        # Description HTML
        desc_html = item.get("jobDescription") or f"<p>{title} at {company_name}</p>"
        desc_text = strip_html_tags(desc_html)

        # Requirements
        req_html = item.get("jobRequirement") or ""
        req_text = strip_html_tags(req_html) if req_html else None

        # Salary
        pretty_salary = (item.get("prettySalary") or "").strip()
        s_min = item.get("salaryMin")
        s_max = item.get("salaryMax")
        if pretty_salary:
            salary_raw = pretty_salary
        elif s_min and s_max:
            salary_raw = f"{s_min} - {s_max} {item.get('salaryCurrency', 'USD')}"
        else:
            salary_raw = "Thương lượng"

        # Location
        locations = item.get("locations") or item.get("workingLocations") or []
        loc_names = []
        if isinstance(locations, list):
            for l in locations:
                if isinstance(l, dict):
                    name = l.get("cityName") or l.get("address")
                    if name:
                        loc_names.append(str(name).strip())
                elif isinstance(l, str):
                    loc_names.append(l.strip())
        location_text = ", ".join(loc_names) if loc_names else (item.get("address") or None)

        # Skills
        skills = item.get("skills") or []
        skill_names = []
        if isinstance(skills, list):
            for s in skills:
                if isinstance(s, dict):
                    sname = s.get("skillName")
                    if sname:
                        skill_names.append(str(sname).strip())
                elif isinstance(s, str):
                    skill_names.append(s.strip())
        skills_text = ", ".join(skill_names) if skill_names else None

        # Benefits
        benefits = item.get("benefits") or []
        ben_names = []
        if isinstance(benefits, list):
            for b in benefits:
                if isinstance(b, dict):
                    bname = b.get("benefitName")
                    if bname:
                        ben_names.append(str(bname).strip())
                elif isinstance(b, str):
                    ben_names.append(b.strip())
        benefits_text = ", ".join(ben_names) if ben_names else None

        # Seniority / Experience
        seniority = item.get("jobLevelVI") or item.get("jobLevel")
        exp = item.get("yearsOfExperience")
        exp_text = f"{exp} năm kinh nghiệm" if exp is not None else None

        raw_data = {
            "title": title,
            "company": company_name,
            "description_html": desc_html,
            "description_text": desc_text,
            "salary_text": salary_raw,
            "location_text": location_text,
            "skills_text": skills_text,
            "experience_text": exp_text,
            "employment_type_text": str(item.get("typeWorkingId")) if item.get("typeWorkingId") else None,
            "seniority_text": str(seniority) if seniority else None,
            "requirements_text": req_text,
            "benefits_text": benefits_text,
            "posted_date_text": str(item.get("approvedOn") or item.get("createdOn") or ""),
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
    parser = argparse.ArgumentParser(description="VietnamWorks IT Job Crawler")
    parser.add_argument("--max-items", type=int, default=30, help="Số tin tối đa cần cào")
    parser.add_argument("--output-dir", type=str, default="data", help="Thư mục xuất dữ liệu")
    parser.add_argument("--checkpoint-dir", type=str, default=None, help="Thư mục lưu checkpoint")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    crawler = VietnamWorksCrawler(
        checkpoint_dir=args.checkpoint_dir,
        output_dir=args.output_dir,
        max_items=args.max_items,
    )
    result = crawler.run()
    print("Crawl completed:", result)


if __name__ == "__main__":
    main()
