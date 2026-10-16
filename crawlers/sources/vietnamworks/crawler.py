# -*- coding: utf-8 -*-
"""Crawler nguồn VietnamWorks (https://www.vietnamworks.com) — Phiên bản chuẩn Data Contract Schema v1.

Sử dụng Search API chính thức: https://ms.vietnamworks.com/job-search/v1.0/search
Hỗ trợ 2 chế độ:
1. Online: Gửi POST requests theo danh sách từ khóa IT, tự động retry, phân trang và lấy đầy đủ thông tin.
2. Offline (--local-json-file): Tải trực tiếp payload JSON đã lưu để test nhanh không phụ thuộc mạng.
"""

import argparse
import hashlib
import json
import logging
import os
import re
import unicodedata
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
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
    "cong nghe thong tin",
    "information technology",
    "IT",
    "software developer",
    "programmer",
    "backend developer",
    "frontend developer",
    "fullstack developer",
    "mobile developer",
    "web developer",
    "data engineer",
    "data analyst",
    "data scientist",
    "machine learning",
    "cybersecurity",
    "network engineer",
    "cloud engineer",
    "devops",
    "system administrator",
    "IT support",
    "software tester",
    "QA automation",
    "business analyst IT",
    "IT project manager",
]
HITS_PER_PAGE = 50
IT_INDUSTRY_TERMS = (
    "information technology",
    "cong nghe thong tin",
    "cntt",
    "software",
    "computer",
    "internet",
    "hardware networking",
    "telecommunication",
)
IT_TITLE_TERMS = (
    "information technology",
    "cong nghe thong tin",
    "cntt",
    "software",
    "programmer",
    "programming",
    "backend",
    "back end",
    "frontend",
    "front end",
    "fullstack",
    "full stack",
    "devops",
    "data engineer",
    "data scientist",
    "data analyst",
    "machine learning",
    "artificial intelligence",
    "cybersecurity",
    "cyber security",
    "network engineer",
    "system administrator",
    "systems administrator",
    "database administrator",
    "cloud engineer",
    "mobile developer",
    "web developer",
    "application developer",
    "software tester",
    "software test",
    "qa automation",
    "IT support",
    "IT project",
    "IT manager",
)
IT_SKILL_TERMS = (
    "python",
    "java",
    "javascript",
    "typescript",
    "c++",
    "c#",
    ".net",
    "sql",
    "aws",
    "azure",
    "gcp",
    "docker",
    "kubernetes",
    "selenium",
    "cypress",
    "playwright",
    "react",
    "angular",
    "node.js",
    "linux",
    "network security",
    "machine learning",
    "data engineering",
    "software testing",
)


def _normalize_classification_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower().replace("đ", "d"))
    return re.sub(r"\s+", " ", "".join(
        char for char in normalized if not unicodedata.combining(char)
    )).strip()


def _contains_term(text: str, terms: tuple[str, ...]) -> bool:
    for term in terms:
        normalized_term = _normalize_classification_text(term)
        if re.search(rf"(?<!\w){re.escape(normalized_term)}(?!\w)", text):
            return True
    return False


def is_it_job(item: dict[str, Any]) -> bool:
    """Classify an API item as IT from its industry, job title, and technical skills."""
    industry_labels: list[str] = []
    for field in ("industriesV3", "industries"):
        industries = item.get(field) or []
        if isinstance(industries, list):
            for industry in industries:
                if isinstance(industry, dict):
                    for key in (
                        "industryV3NameVI",
                        "industryV3Name",
                        "industryNameVI",
                        "industryName",
                    ):
                        label = industry.get(key)
                        if isinstance(label, str) and label.strip():
                            industry_labels.append(label)

    industry_text = _normalize_classification_text(" ".join(industry_labels))
    if _contains_term(industry_text, IT_INDUSTRY_TERMS):
        return True

    title = item.get("jobTitle")
    title_text = _normalize_classification_text(title if isinstance(title, str) else "")
    if _contains_term(title_text, IT_TITLE_TERMS):
        return True

    skills = item.get("skills") or []
    skill_names = [
        skill.get("skillName", "")
        for skill in skills
        if isinstance(skill, dict) and isinstance(skill.get("skillName"), str)
    ] if isinstance(skills, list) else []
    skill_text = _normalize_classification_text(" ".join(skill_names))
    return _contains_term(skill_text, IT_SKILL_TERMS)


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
        self.raw_payload_files: list[Path] = []
        self.raw_payload_file: Path | None = None
        self._raw_payloads: dict[str, dict[str, Any]] = {}
        self.filtered_non_it_count = 0

    def _save_raw_payload(self, item: dict[str, Any]) -> None:
        """Queue the untouched API item for the consolidated raw JSON file."""
        raw_json = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        payload_hash = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()
        raw_id = item.get("jobId")
        job_id = str(raw_id).strip() if raw_id is not None else ""
        date_partition = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        raw_dir = Path(self.output_dir) / self.source_name / "raw" / date_partition
        self.raw_payload_file = raw_dir / "raw_batch.json"
        envelope = {
            "metadata": {
                "job_id": job_id or None,
                "source": self.source_name,
                "source_url": item.get("jobUrl"),
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "scraper_version": self.crawler_version,
                "content_hash": payload_hash,
            },
            "raw_payload": item,
        }

        self._raw_payloads[job_id or payload_hash] = envelope

    def _flush_raw_payloads(self) -> None:
        """Atomically merge queued API items into the day's consolidated JSON array."""
        if not self._raw_payloads or self.raw_payload_file is None:
            return

        existing_by_id: dict[str, dict[str, Any]] = {}
        if self.raw_payload_file.is_file():
            try:
                with self.raw_payload_file.open("r", encoding="utf-8") as raw_file:
                    existing_records = json.load(raw_file)
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError(
                    f"Cannot load existing raw payload batch {self.raw_payload_file}: {exc}"
                ) from exc

            if not isinstance(existing_records, list):
                raise ValueError(
                    f"Raw payload batch must contain a JSON array: {self.raw_payload_file}"
                )
            for record in existing_records:
                metadata = record.get("metadata", {})
                identity = metadata.get("job_id") or metadata.get("content_hash")
                if identity:
                    existing_by_id[str(identity)] = record

        existing_by_id.update(self._raw_payloads)
        self.raw_payload_file.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.raw_payload_file.with_name(
            f"{self.raw_payload_file.name}.tmp"
        )
        try:
            with temporary_path.open("w", encoding="utf-8") as raw_file:
                json.dump(list(existing_by_id.values()), raw_file, ensure_ascii=False, indent=2)
                raw_file.flush()
                os.fsync(raw_file.fileno())
            os.replace(temporary_path, self.raw_payload_file)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

        self.raw_payload_files = [self.raw_payload_file]
        self._raw_payloads.clear()

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
                if not is_it_job(job):
                    self.filtered_non_it_count += 1
                    continue
                self._save_raw_payload(job)
                yield job
                yielded += 1
                if self.max_items and yielded >= self.max_items:
                    break
            self._flush_raw_payloads()
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
                    if not is_it_job(job):
                        self.filtered_non_it_count += 1
                        continue
                    self._save_raw_payload(job)
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
                        self._flush_raw_payloads()
                        return

                self._flush_raw_payloads()

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
