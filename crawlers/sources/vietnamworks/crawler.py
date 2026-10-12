# -*- coding: utf-8 -*-
"""Crawler nguồn VietnamWorks (https://www.vietnamworks.com) — Phiên bản chuẩn Data Contract Schema v1.

Sử dụng Search API chính thức: https://ms.vietnamworks.com/job-search/v1.0/search
Hỗ trợ 2 chế độ:
1. Online: Gửi POST requests theo danh sách từ khóa IT, tự động retry, phân trang và lấy đầy đủ thông tin.
2. Offline (--local-json-file): Tải trực tiếp payload JSON đã lưu để test nhanh không phụ thuộc mạng.
"""

import argparse
import json
import logging
import os
from collections.abc import Generator
from typing import Any

from crawlers.base.base_crawler import BaseCrawler
from crawlers.common.http_client import DelayConfig, HttpClient
from crawlers.common.schema import JobRecord
from crawlers.common.utils import (
    clean_text,
    detect_language,
    parse_salary_detail,
    strip_html_tags,
    text_to_clean_lines,
    classify_job_tags,
)

log = logging.getLogger("vietnamworks.crawler")

SOURCE = "vietnamworks"
CRAWLER_VERSION = "0.5.0"
API_URL = "https://ms.vietnamworks.com/job-search/v1.0/search"
IT_QUERIES = [
    "software developer",
    "software engineer",
    "backend",
    "frontend",
    "fullstack",
    "data engineer",
    "devops",
    "tester",
    "qa qc",
    "lập trình viên",
    "cntt",
    "công nghệ thông tin",
    "system engineer",
    "solution architect",
    "business analyst",
    "mobile developer",
    "product owner",
    "data analyst",
    "ai engineer",
    "machine learning",
    "cyber security",
    "cloud engineer",
]
HITS_PER_PAGE = 50


class VietnamWorksCrawler(BaseCrawler):
    """Crawler cho nguồn VietnamWorks kế thừa BaseCrawler chuẩn hóa Data Contract v1."""

    source_name = SOURCE
    crawler_version = CRAWLER_VERSION

    def __init__(
        self,
        checkpoint_dir: str | None = None,
        output_dir: str | None = None,
        max_items: int | None = 30,
        checkpoint_interval: int = 10,
        http_client: HttpClient | None = None,
        queries: list[str] | None = None,
        local_json_file: str | None = None,
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
            delay_config=DelayConfig(min_seconds=1.0, max_seconds=2.0),
            timeout=25,
        )
        self.local_json_file = local_json_file

    def fetch_items(self) -> Generator[dict[str, Any], None, None]:
        """Lấy danh sách job items từ file offline hoặc từ Search API trực tuyến."""
        # 1. Chế độ đọc file JSON offline
        if self.local_json_file and os.path.exists(self.local_json_file):
            log.info("[VietnamWorks] Loading local JSON file: %s", self.local_json_file)
            with open(self.local_json_file, encoding="utf-8") as f:
                data = json.load(f)
            job_list = data if isinstance(data, list) else data.get("data", [])
            yielded = 0
            for job in job_list:
                yield job
                yielded += 1
                if self.max_items and yielded >= self.max_items:
                    break
            return

        # 2. Chế độ cào Search API trực tuyến
        headers = {
            "Content-Type": "application/json",
            "X-Source": "Page-Container",
            "Origin": "https://www.vietnamworks.com",
            "Referer": "https://www.vietnamworks.com/viec-lam?q=it",
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        }

        seen_in_run = set()
        total_yielded = 0

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
                    if not jid:
                        continue
                    str_jid = str(jid).strip()
                    if str_jid in seen_in_run:
                        continue
                    if self.checkpoint.is_seen(str_jid):
                        self.skipped_count += 1
                        continue

                    seen_in_run.add(str_jid)
                    yield job
                    total_yielded += 1

                    if self.max_items and total_yielded >= self.max_items:
                        return

                if len(job_list) < HITS_PER_PAGE:
                    break

                page += 1

    def parse_item(self, item: dict[str, Any]) -> JobRecord | None:
        """Biến đổi raw JSON từ VietnamWorks Search API thành JobRecord chuẩn Data Contract Schema v1."""
        raw_id = item.get("jobId")
        if not raw_id:
            return None
        job_id = str(raw_id).strip()

        title = clean_text(item.get("jobTitle") or "")
        if not title:
            return None

        job_url = item.get("jobUrl") or f"https://www.vietnamworks.com/job-{job_id}-jv"
        company_name = clean_text(item.get("companyName") or "Unknown")

        # 1. Mức lương (prettySalary + salaryMin + salaryMax + salaryCurrency)
        pretty_salary = clean_text(item.get("prettySalary") or "")
        s_min = item.get("salaryMin")
        s_max = item.get("salaryMax")
        s_currency = item.get("salaryCurrency", "USD")

        if pretty_salary and not any(pretty_salary.startswith(p) for p in ["0", "Thương lượng", "Thoả thuận"]):
            salary_raw = pretty_salary
        elif s_min and s_max and (s_min > 0 or s_max > 0):
            salary_raw = f"{s_min} - {s_max} {s_currency}"
        elif pretty_salary:
            salary_raw = pretty_salary
        else:
            salary_raw = "Thương lượng"

        salary_detail = parse_salary_detail(salary_raw, title=title)
        # Nếu API có min/max rõ ràng mà regex chưa bắt được
        if s_min and s_min > 0 and salary_detail.get("salary_min") is None:
            # Quy đổi nếu VND > 1 triệu
            val_min = round(s_min / 1_000_000, 2) if s_min >= 1_000_000 else float(s_min)
            salary_detail["salary_min"] = val_min
        if s_max and s_max > 0 and salary_detail.get("salary_max") is None:
            val_max = round(s_max / 1_000_000, 2) if s_max >= 1_000_000 else float(s_max)
            salary_detail["salary_max"] = val_max
        if s_currency and salary_detail.get("salary_currency") is None:
            salary_detail["salary_currency"] = s_currency

        # 2. Bóc tách mô tả, yêu cầu, quyền lợi thành list[str] sạch không bullet
        desc_html = item.get("jobDescription") or f"<p>{title} at {company_name}</p>"
        req_html = item.get("jobRequirement") or ""
        desc_list = text_to_clean_lines(desc_html)
        if not desc_list:
            desc_list = [f"{title} at {company_name}"]
        req_list = text_to_clean_lines(req_html) if req_html else None

        # Phúc lợi dạng danh sách (Benefits List)
        benefits_data = item.get("benefits") or []
        ben_lines = []
        if isinstance(benefits_data, list):
            for b in benefits_data:
                if isinstance(b, dict):
                    bname = b.get("benefitNameVI") or b.get("benefitName")
                    bval = b.get("benefitValue")
                    line = f"{bname}: {bval}" if (bname and bval) else (bname or bval)
                    if line:
                        ben_lines.append(clean_text(str(line)))
                elif isinstance(b, str) and b.strip():
                    ben_lines.append(clean_text(b))
        ben_list = ben_lines if ben_lines else None

        # 3. Phân nhóm thẻ Tags (JobTags: requirements, benefits, skills)
        skills_data = item.get("skills") or []
        tag_skills = []
        if isinstance(skills_data, list):
            for s in skills_data:
                if isinstance(s, dict):
                    sname = clean_text(s.get("skillName") or "")
                    if sname and sname not in tag_skills:
                        tag_skills.append(sname)
                elif isinstance(s, str) and s.strip():
                    tag_skills.append(clean_text(s))

        tag_benefits = []
        if isinstance(benefits_data, list):
            for b in benefits_data:
                if isinstance(b, dict):
                    bname = clean_text(b.get("benefitNameVI") or b.get("benefitName") or "")
                    if bname and bname not in tag_benefits:
                        tag_benefits.append(bname)

        tags_data = {
            "requirements": None,  # VietnamWorks không có riêng pill tags cho requirements
            "benefits": tag_benefits if tag_benefits else None,
            "skills": tag_skills if tag_skills else None,
        }

        # 4. Địa điểm làm việc
        locations = item.get("locations") or item.get("workingLocations") or []
        loc_names = []
        if isinstance(locations, list):
            for l in locations:
                if isinstance(l, dict):
                    name = l.get("cityName") or l.get("address")
                    if name:
                        loc_names.append(clean_text(str(name)))
                elif isinstance(l, str):
                    loc_names.append(clean_text(l))
        loc_text = ", ".join(loc_names) if loc_names else (clean_text(item.get("address") or "") or None)

        # 5. Hạn nộp hồ sơ & Ngày đăng
        deadline_text = clean_text(str(item.get("expiredOn") or "")) or None
        posted_date_text = clean_text(str(item.get("approvedOn") or item.get("createdOn") or ""))

        # 6. Cấp bậc & Kinh nghiệm
        seniority = clean_text(str(item.get("jobLevelVI") or item.get("jobLevel") or "")) or None
        exp = item.get("yearsOfExperience")
        exp_text = f"{exp} năm kinh nghiệm" if (exp is not None and str(exp) != "0") else None

        # 7. Nhận diện ngôn ngữ
        desc_sample = " ".join(desc_list[:3]) if desc_list else f"{title} {company_name}"
        lang = detect_language(desc_sample)

        raw_data = {
            "title": title,
            "company": company_name,
            "salary": salary_detail,
            "tags": tags_data,
            "description_list": desc_list,
            "requirements_list": req_list or [],
            "benefits_list": ben_list or [],
            "location_text": loc_text,
            "deadline_text": deadline_text,
            "posted_date_text": posted_date_text,
            "employment_type_text": str(item.get("typeWorkingId")) if item.get("typeWorkingId") else None,
            "seniority_text": seniority,
            "extra": {
                "experience": exp_text,
                "job_level": seniority,
                "company_size": clean_text(str(item.get("companySizeVI") or item.get("companySize") or "")),
                "number_of_recruits": item.get("numberOfRecruits"),
                "alias": item.get("alias"),
            },
        }

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
    parser = argparse.ArgumentParser(description="VietnamWorks IT Job Crawler")
    parser.add_argument("--max-items", type=int, default=30, help="Số tin tối đa cần cào")
    parser.add_argument("--output-dir", type=str, default="data", help="Thư mục xuất dữ liệu")
    parser.add_argument("--checkpoint-dir", type=str, default=None, help="Thư mục lưu checkpoint")
    parser.add_argument("--local-json-file", type=str, default=None, help="File JSON payload để chạy offline")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    crawler = VietnamWorksCrawler(
        checkpoint_dir=args.checkpoint_dir,
        output_dir=args.output_dir,
        max_items=args.max_items,
        local_json_file=args.local_json_file,
    )
    result = crawler.run()
    print("Crawl completed:", result)


if __name__ == "__main__":
    main()
