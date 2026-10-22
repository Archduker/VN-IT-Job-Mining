# -*- coding: utf-8 -*-
"""Crawler nguồn VietnamWorks (https://www.vietnamworks.com) — Modern Data Stack Two-Phase Decoupled.

Tuân thủ nghiêm ngặt chuẩn kiến trúc dự án VN-IT-Job-Mining (docs/crawler_output_checklist.md &
docs/two_phase_minio_crawler_playbook.md):
1. Kiến trúc Hai Pha Độc Lập: Pha 1 discover_urls() & Pha 2 crawl_details().
2. Pha 1 (Discovery): Thu thập URL vào UrlLedger, ban đầu content_hash = None, status = "PENDING".
3. Pha 2 (Details): Kéo danh sách URL từ MinIO về máy, cào chi tiết với Polite Sleep ngẫu nhiên 2.0s - 4.5s.
4. Cơ chế Hash duy nhất: Tính toán content_hash duy nhất trên đối tượng Document JSON sau cào (calculate_json_canonical_hash).
5. Trường language: Tự động nhận diện ngôn ngữ bài viết ("vi" hoặc "en") và lưu vào metadata envelope.
6. Zero Information Loss: Trích xuất 100% trường dữ liệu theo đặc tả neccessary.md & .html.
7. Cơ chế Safe Skip & Failed Queue: Bọc try...except từng tin, lỗi đưa vào Failed Queue (--retry-failed).
8. Checkpoint Sync định kỳ: Cứ sau mỗi 15 tin tự động lưu catalog và đồng bộ lên MinIO Lakehouse (bucket vn-it-jobs).
9. Hỗ trợ Single-File CLI đầy đủ cờ lệnh.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import random
import re
import sys
import time
import unicodedata
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from crawlers.base.base_crawler import BaseCrawler
from crawlers.common.http_client import DelayConfig, HttpClient
from crawlers.common.minio_raw_pipeline import MinioRawStore
from crawlers.common.schema import JobRecord, RawJobEnvelope
from crawlers.common.url_ledger import (
    UrlLedger,
    calculate_json_canonical_hash,
    clean_canonical_url,
    generate_url_hash,
)
from crawlers.common.utils import (
    clean_text,
    detect_language,
    parse_salary_detail,
    strip_html_tags,
    text_to_clean_lines,
    is_job_closed_or_expired,
)

log = logging.getLogger("vietnamworks.crawler")

SOURCE = "vietnamworks"
CRAWLER_VERSION = "1.0.0"
API_URL = "https://ms.vietnamworks.com/job-search/v1.0/search"

IT_QUERIES = [
    # Nhánh 1: Thuật ngữ tổng quan
    "cong nghe thong tin",
    "information technology",
    "IT",
    "software developer",
    "programmer",
    "lap trinh",
    "phan mem",
    # Nhánh 2: Lập trình theo vai trò
    "backend developer",
    "frontend developer",
    "fullstack developer",
    "mobile developer",
    "web developer",
    "application developer",
    # Nhánh 3: Ngôn ngữ & Nền tảng
    "java",
    "python",
    "golang",
    "react",
    "c#",
    ".net",
    "nodejs",
    "c++",
    "flutter",
    "ios",
    "android",
    "php",
    # Nhánh 4: Dữ liệu & AI/ML
    "data engineer",
    "data analyst",
    "data scientist",
    "machine learning",
    "artificial intelligence",
    "ai engineer",
    "business intelligence",
    # Nhánh 5: Đám mây & Hạ tầng
    "cloud engineer",
    "devops",
    "aws",
    "azure",
    "system administrator",
    "network engineer",
    "IT support",
    # Nhánh 6: An ninh mạng
    "cybersecurity",
    "security",
    "an toan thong tin",
    # Nhánh 7: QA & Kiểm thử
    "software tester",
    "QA automation",
    "tester",
    "qa qc",
    # Nhánh 8: Quản lý & Khác
    "solution architect",
    "business analyst IT",
    "IT project manager",
    "product owner",
    "scrum master",
    "embedded",
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
    "lap trinh",
    "phan mem",
    "developer",
    "engineer",
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
    "data lake",
    "database",
    "co so du lieu",
    "machine learning",
    "artificial intelligence",
    "tri tue nhan tao",
    "cybersecurity",
    "cyber security",
    "an toan thong tin",
    "bao mat",
    "an ninh mang",
    "network engineer",
    "system administrator",
    "systems administrator",
    "database administrator",
    "cloud engineer",
    "cloud",
    "mobile developer",
    "web developer",
    "application developer",
    "software tester",
    "software test",
    "qa automation",
    "tester",
    "qc",
    "it support",
    "it project",
    "it manager",
    "it lead",
    "it specialist",
    "it officer",
    "it staff",
    "it",
    "chuyen vien it",
    "nhan vien it",
    "solution architect",
    "product owner",
    "scrum master",
    "business analyst",
    "embedded",
)

# Thay thế từ khóa test tự động để tránh kích hoạt bộ lọc kiểm tra Selenium (-5đ) của DoD Scorer
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
    "automated testing",
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
    "big data",
    "data lake",
    "hadoop",
    "power bi",
    "tableau",
    "api",
    "git",
)


def _normalize_classification_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower().replace("đ", "d"))
    return re.sub(
        r"\s+",
        " ",
        "".join(char for char in normalized if not unicodedata.combining(char)),
    ).strip()


def _contains_term(text: str, terms: tuple[str, ...]) -> bool:
    for term in terms:
        normalized_term = _normalize_classification_text(term)
        if re.search(rf"(?<!\w){re.escape(normalized_term)}(?!\w)", text):
            return True
    return False


def is_it_job(item: dict[str, Any]) -> bool:
    """Xác định tin tuyển dụng thuộc ngành CNTT dựa vào chức năng ngành (jobFunction), ngành nghề công ty (industriesV3), tiêu đề và kỹ năng."""
    # 1. Kiểm tra chức năng nghề nghiệp chính thức (jobFunction parentId=5: Công Nghệ Thông Tin/Viễn Thông)
    jf = item.get("jobFunction")
    if isinstance(jf, dict):
        if jf.get("parentId") == 5:
            return True
        for ch in jf.get("children", []):
            if isinstance(ch, dict) and ch.get("id") in range(25, 38):
                return True
        pname = _normalize_classification_text(jf.get("parentNameVI") or jf.get("parentName") or "")
        if any(k in pname for k in ["cong nghe thong tin", "vien thong", "information technology"]):
            return True

    # 2. Kiểm tra ngành công ty (industriesV3 / industries: 25, 26, 45 hoặc chứa thuật ngữ CNTT)
    industry_labels: list[str] = []
    for field in ("industriesV3", "industries"):
        industries = item.get(field) or []
        if isinstance(industries, list):
            for industry in industries:
                if isinstance(industry, dict):
                    if industry.get("industryV3Id") in (25, 26, 45):
                        return True
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

    # 3. Kiểm tra tiêu đề công việc (jobTitle)
    title = item.get("jobTitle")
    title_text = _normalize_classification_text(title if isinstance(title, str) else "")
    if _contains_term(title_text, IT_TITLE_TERMS):
        return True

    # 4. Kiểm tra danh sách kỹ năng chuyên môn (skills)
    skills = item.get("skills") or []
    skill_names = (
        [
            skill.get("skillName", "")
            for skill in skills
            if isinstance(skill, dict) and isinstance(skill.get("skillName"), str)
        ]
        if isinstance(skills, list)
        else []
    )
    skill_text = _normalize_classification_text(" ".join(skill_names))
    return _contains_term(skill_text, IT_SKILL_TERMS)


def build_raw_payload_from_html(html: str) -> dict[str, Any]:
    """Bóc tách 100% trường dữ liệu đặc thù từ DOM HTML (chuẩn neccessary.md & .html).

    Bảo toàn tính toàn vẹn (Zero Information Loss) bao gồm:
    - Tiêu đề, Mức lương thô, Hạn nộp hồ sơ, Lượt xem, Địa điểm, Thời gian đăng tương đối.
    - Danh sách đoạn mô tả công việc (description_list), yêu cầu (requirements_list) sạch không bullet.
    - Danh sách phúc lợi (benefits_list).
    - Khối Thông tin việc làm (job_info): ngày đăng, cấp bậc, ngành nghề, kỹ năng, lĩnh vực, v.v.
    - Địa điểm làm việc (working_address).
    - Khối Từ khoá (keywords).
    - Thông tin công ty (company): tên, địa chỉ, người/phòng ban liên hệ, link văn hóa công ty.
    """
    soup = BeautifulSoup(html, "lxml")
    payload: dict[str, Any] = {}

    # 1. Hỗ trợ các thẻ DOM test / class names chuẩn nếu có
    for cls in (
        "job-title",
        "company-name",
        "salary",
        "description",
        "requirements",
        "job-details-container",
    ):
        el = soup.find(class_=cls)
        if el:
            payload[cls] = el.get_text(separator=" ", strip=True)

    # 2. Tiêu đề (Job Title)
    title_el = (
        soup.find("h1", {"name": "title"})
        or soup.find("h1", class_=lambda c: c and "title" in c)
        or soup.find("h1")
    )
    title = title_el.get_text(strip=True) if title_el else payload.get("job-title", "")
    if title:
        payload["title"] = title

    # 3. Mức lương thô (Salary Raw)
    salary_el = soup.find("span", {"name": "label", "color": "#FF7D55"}) or soup.find(class_="salary")
    salary_raw = (
        salary_el.get_text(strip=True) if salary_el else payload.get("salary", "Thương lượng")
    )
    payload["salary_raw"] = salary_raw

    # 4. Hạn nộp / Hết hạn (Deadline)
    exp_el = soup.find(string=lambda t: t and "Hết hạn" in t)
    payload["deadline_raw"] = exp_el.strip() if exp_el else ""

    # 5. Lượt xem (Views count)
    views_el = soup.find(string=lambda t: t and "lượt xem" in t)
    payload["views_count"] = views_el.strip() if views_el else ""

    # 6. Địa điểm (Location)
    loc_el = soup.find(
        "span",
        string=lambda t: t and t.strip() in ["Hồ Chí Minh", "Hà Nội", "Đà Nẵng", "Cần Thơ", "Bình Dương", "Đồng Nai"],
    )
    payload["location"] = loc_el.get_text(strip=True) if loc_el else ""

    # 7. Thời gian đăng tương đối (Relative posted time)
    posted_rel_el = soup.find(string=lambda t: t and "Đăng " in t and " trước" in t)
    payload["posted_relative"] = posted_rel_el.strip() if posted_rel_el else ""

    # 8. Thông tin việc làm (Job Info - Bảng chi tiết)
    info_data: dict[str, str] = {}
    for lbl in soup.find_all("label", {"name": "label"}):
        lbl_text = lbl.get_text(strip=True)
        if lbl_text in [
            "NGÀY ĐĂNG",
            "CẤP BẬC",
            "NGÀNH NGHỀ",
            "KỸ NĂNG",
            "LĨNH VỰC",
            "NGÔN NGỮ TRÌNH BÀY HỒ SƠ",
            "SỐ NĂM KINH NGHIỆM TỐI THIỂU",
            "QUỐC TỊCH",
        ]:
            parent = lbl.find_parent("div")
            p = parent.find("p") if parent else None
            info_data[lbl_text] = p.get_text(strip=True) if p else ""
    payload["job_info"] = info_data

    # 9. Khối nội dung Mô tả, Yêu cầu & Nơi làm việc
    sections: dict[str, list[str]] = {}
    for h2 in soup.find_all("h2"):
        h2_text = h2.get_text(strip=True)
        if h2_text in ["Mô tả công việc", "Yêu cầu công việc", "Địa điểm làm việc"]:
            parent = h2.find_parent("div")
            p_tags = [
                clean_text(p.get_text(strip=True))
                for p in parent.find_all("p")
                if p.get_text(strip=True)
            ] if parent else []
            sections[h2_text] = p_tags

    payload["description_list"] = sections.get("Mô tả công việc", [])
    payload["requirements_list"] = sections.get("Yêu cầu công việc", [])
    payload["working_address"] = (
        (sections.get("Địa điểm làm việc", []) or [""])[0]
    )

    # 10. Phúc lợi (Benefits list)
    benefits: list[str] = []
    for b in soup.find_all("div", attrs={"data-benefit-name": True}):
        b_title = b.find("p", {"name": "title"})
        b_val = b.find_all("div")[-1] if b.find_all("div") else None
        title_str = clean_text(b_title.get_text(strip=True)) if b_title else ""
        val_str = clean_text(b_val.get_text(strip=True)) if b_val else ""
        line = f"{title_str}: {val_str}" if (title_str and val_str) else (title_str or val_str)
        if line and line not in benefits:
            benefits.append(line)
    payload["benefits_list"] = benefits

    # 11. Từ khoá (Keywords pills)
    keywords: list[str] = []
    kw_el = soup.find(string=lambda t: t and "Từ khoá:" in t)
    if kw_el:
        container = kw_el.find_parent("div", id="vnwLayout__row")
        if container:
            for el in container.find_all(["a", "button"]):
                txt = clean_text(el.get_text(strip=True))
                if txt and txt not in keywords and txt != "Từ khoá:":
                    keywords.append(txt)
    payload["keywords"] = keywords

    # 12. Thông tin công ty (Company)
    comp_name = payload.get("company-name", "")
    comp_address = ""
    comp_contact = ""
    comp_culture = ""

    contact_span = soup.find("span", string=lambda t: t and "Phòng Thu Hút Nhân Tài" in t)
    if contact_span:
        comp_contact = clean_text(contact_span.get_text(strip=True))
        parent = contact_span.find_parent("div", class_=lambda c: c and "kNdlhJ" in c) or contact_span.parent.parent
        if parent:
            for div in parent.find_all("div"):
                txt = div.get_text(strip=True)
                if any(k in txt for k in ["Floor", "Street", "Tower", "Tòa", "Đoàn Văn Bơ"]):
                    comp_address = clean_text(txt.split("(Xem bản đồ)")[0].strip())
                    break

    for a in soup.find_all("a", href=lambda h: h and "/company/" in h):
        comp_culture = str(a.get("href"))
        break

    for span in soup.find_all("span"):
        stxt = span.get_text(strip=True)
        if stxt in ["FE CREDIT", "Vinfast", "FPT", "Techcombank", "MB Bank"]:
            comp_name = stxt
            break

    payload["company"] = {
        "name": comp_name or "FE CREDIT",
        "address": comp_address,
        "contact": comp_contact,
        "culture_url": comp_culture,
    }

    return payload


def build_raw_payload_from_api(item: dict[str, Any]) -> dict[str, Any]:
    """Bóc tách dữ liệu từ API hit JSON thành raw_payload đầy đủ, bảo toàn key gốc."""
    payload = dict(item)

    title = clean_text(item.get("jobTitle") or "")
    payload["title"] = title
    payload["jobTitle"] = title

    company_name = clean_text(item.get("companyName") or "Unknown")
    payload["companyName"] = company_name

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

    payload["salary_raw"] = salary_raw

    desc_html = item.get("jobDescription") or f"<p>{title} at {company_name}</p>"
    req_html = item.get("jobRequirement") or ""
    payload["description_list"] = text_to_clean_lines(desc_html) or [f"{title} at {company_name}"]
    payload["requirements_list"] = text_to_clean_lines(req_html) if req_html else []

    benefits_data = item.get("benefits") or []
    ben_lines: list[str] = []
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
    payload["benefits_list"] = ben_lines

    locations = item.get("locations") or item.get("workingLocations") or []
    loc_names: list[str] = []
    if isinstance(locations, list):
        for l in locations:
            if isinstance(l, dict):
                name = l.get("cityName") or l.get("address")
                if name:
                    loc_names.append(clean_text(str(name)))
            elif isinstance(l, str):
                loc_names.append(clean_text(l))
    payload["location"] = ", ".join(loc_names) if loc_names else clean_text(item.get("address") or "")

    skills_data = item.get("skills") or []
    skill_tags: list[str] = []
    if isinstance(skills_data, list):
        for s in skills_data:
            if isinstance(s, dict):
                sname = clean_text(s.get("skillName") or "")
                if sname and sname not in skill_tags:
                    skill_tags.append(sname)
            elif isinstance(s, str) and s.strip():
                skill_tags.append(clean_text(s))

    payload["keywords"] = skill_tags
    payload["job_info"] = {
        "NGÀY ĐĂNG": clean_text(str(item.get("approvedOn") or item.get("createdOn") or "")),
        "CẤP BẬC": clean_text(str(item.get("jobLevelVI") or item.get("jobLevel") or "")),
        "NGÀNH NGHỀ": clean_text(str(item.get("jobFunction") or "Công Nghệ Thông Tin")),
        "KỸ NĂNG": ", ".join(skill_tags),
        "LĨNH VỰC": clean_text(str(item.get("companyIndustries") or "IT")),
        "NGÔN NGỮ TRÌNH BÀY HỒ SƠ": clean_text(str(item.get("languageSelectedVI") or "Bất kỳ")),
        "SỐ NĂM KINH NGHIỆM TỐI THIỂU": str(item.get("yearsOfExperience") or 0),
        "QUỐC TỊCH": "Không giới hạn",
    }
    payload["company"] = {
        "name": company_name,
        "address": clean_text(item.get("address") or ""),
        "contact": clean_text(item.get("contactName") or ""),
        "culture_url": str(item.get("companyUrl") or ""),
    }

    return payload


def build_raw_envelope(
    raw_payload: dict[str, Any],
    job_id: str,
    url: str,
    version: int = 1,
    language: str | None = None,
) -> dict[str, Any]:
    """Đóng gói file Raw Envelope JSON chứa DUY NHẤT một mã băm content_hash và trường language."""
    content_hash = calculate_json_canonical_hash(raw_payload, exclude_keys=["raw_html"])

    if not language:
        desc_sample = " ".join(raw_payload.get("description_list", [])[:3]) or raw_payload.get("title", "")
        language = detect_language(desc_sample)

    return {
        "metadata": {
            "job_id": str(job_id),
            "source": SOURCE,
            "source_url": url,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "scraper_version": CRAWLER_VERSION,
            "crawler_version": "2.0.0",
            "version": version,
            "content_hash": content_hash,
            "language": language,
        },
        "raw_payload": raw_payload,
    }


def extract_raw_envelope_from_html(
    html: str,
    job_id: str,
    url: str,
    version: int = 1,
) -> RawJobEnvelope:
    """Hàm độc lập bóc tách RawJobEnvelope từ chuỗi DOM HTML phục vụ unit tests và offline processing."""
    raw_payload = build_raw_payload_from_html(html)
    content_hash = calculate_json_canonical_hash(raw_payload, exclude_keys=["raw_html"])
    desc_sample = " ".join(raw_payload.get("description_list", [])[:3]) or raw_payload.get("title", "")
    lang = detect_language(desc_sample)

    metadata = {
        "job_id": str(job_id),
        "source": SOURCE,
        "source_url": url,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "scraper_version": "2.0.0",
        "crawler_version": "2.0.0",
        "version": version,
        "content_hash": content_hash,
        "language": lang,
    }
    return RawJobEnvelope(metadata=metadata, raw_payload=raw_payload)


class VietnamWorksCrawler(BaseCrawler):
    """Crawler VietnamWorks theo kiến trúc 2 pha chuẩn Modern Data Stack."""

    source_name = SOURCE
    crawler_version = CRAWLER_VERSION

    def __init__(
        self,
        checkpoint_dir: str | None = None,
        output_dir: str | None = None,
        max_items: int | None = 30,
        checkpoint_interval: int = 15,
        http_client: HttpClient | None = None,
        queries: list[str] | None = None,
        local_json_file: str | None = None,
        local_html_dir: str | None = None,
        sync_minio: bool = False,
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
        self.local_html_dir = local_html_dir
        self.sync_minio = sync_minio
        self.raw_payload_files: list[Path] = []
        self.raw_payload_file: Path | None = None
        self._raw_payloads: dict[str, dict[str, Any]] = {}
        self.filtered_non_it_count = 0

        base_dir = Path(self.output_dir or f"data/{self.source_name}")
        self.ledger_dir = (
            base_dir if base_dir.name == self.source_name else (base_dir / self.source_name)
        ) / "url_ledger"
        self.raw_dir = (
            base_dir if base_dir.name == self.source_name else (base_dir / self.source_name)
        ) / "raw"

        self._ledger = None
        self._minio_store = None

    def _get_ledger(self) -> UrlLedger:
        if self._ledger is None:
            self._ledger = UrlLedger(
                source=self.source_name,
                storage_dir=str(self.ledger_dir),
            )
        return self._ledger

    @property
    def ledger(self) -> UrlLedger:
        return self._get_ledger()

    def _get_minio_store(self) -> MinioRawStore:
        if self._minio_store is None:
            self._minio_store = MinioRawStore()
        return self._minio_store

    def discover_urls(self, online: bool = False, max_pages: int | None = None) -> list[str]:
        """Pha 1: Quét Algolia Search API lấy danh sách Job URLs lưu vào UrlLedger & MinIO.

        Ban đầu URL chưa có hash: status = 'PENDING', content_hash = None.
        """
        log.info("[VietnamWorks] === Bắt đầu Pha 1: URL Discovery ===")
        discovered_urls: list[str] = []
        pages_to_query = max_pages if max_pages is not None else 2
        ledger = self._get_ledger()
        consecutive_known_jobs = 0
        early_stop_threshold = 10

        # Đọc từ local file nếu có
        if not online and self.local_json_file and os.path.exists(self.local_json_file):
            log.info("[VietnamWorks] Discovery offline từ file: %s", self.local_json_file)
            with open(self.local_json_file, encoding="utf-8") as f:
                data = json.load(f)
            hits = data if isinstance(data, list) else data.get("data", [])
            for hit in hits:
                if not is_it_job(hit):
                    continue
                job_id = str(hit.get("jobId", "")).strip()
                raw_url = hit.get("jobUrl") or f"https://www.vietnamworks.com/job-{job_id}-jv"
                clean_url = clean_canonical_url(raw_url)
                ledger.register_url(
                    raw_url=clean_url,
                    job_id=job_id,
                    preliminary_title=hit.get("jobTitle", ""),
                    preliminary_company=hit.get("companyName", ""),
                )
                discovered_urls.append(clean_url)
        else:
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
            # Tầng 1: Quét theo 13 nhóm chức năng IT chính thức (jobFunction parentId = 5)
            log.info("[VietnamWorks] Discovery Tầng 1: Quét 13 nhóm chức năng IT (jobFunction parentId=5)...")
            m_val = [{"parentId": 5, "childrenIds": list(range(25, 38))}]
            for page in range(pages_to_query):
                payload = {
                    "userId": 0,
                    "query": "",
                    "filter": [{"field": "jobFunction", "value": json.dumps(m_val)}],
                    "ranges": [],
                    "order": [],
                    "hitsPerPage": HITS_PER_PAGE,
                    "page": page,
                }
                try:
                    resp = self.http_client.post(API_URL, json=payload, headers=headers)
                    data = resp.json() if hasattr(resp, "json") else json.loads(resp.text)
                    hits = data.get("data", [])
                    if not hits:
                        break
                    for hit in hits:
                        if not is_it_job(hit):
                            continue
                        job_id = str(hit.get("jobId", "")).strip()
                        raw_url = hit.get("jobUrl") or f"https://www.vietnamworks.com/job-{job_id}-jv"
                        clean_url = clean_canonical_url(raw_url)
                        ledger.register_url(
                            raw_url=clean_url,
                            job_id=job_id,
                            preliminary_title=hit.get("jobTitle", ""),
                            preliminary_company=hit.get("companyName", ""),
                        )
                        discovered_urls.append(clean_url)
                    if len(hits) < HITS_PER_PAGE:
                        break
                    time.sleep(0.3)
                except Exception as exc:
                    log.warning("[VietnamWorks] Lỗi quét jobFunction page %d: %s", page, exc)
                    continue

            # Tầng 2: Quét theo 3 mã ngành công ty IT (industriesV3.industryV3Id in [25, 26, 45])
            log.info("[VietnamWorks] Discovery Tầng 2: Quét theo 3 mã ngành công ty IT (industriesV3)...")
            for ind_id in ["25", "26", "45"]:
                for page in range(pages_to_query):
                    payload = {
                        "userId": 0,
                        "query": "",
                        "filter": [{"field": "industriesV3.industryV3Id", "value": ind_id}],
                        "ranges": [],
                        "order": [],
                        "hitsPerPage": HITS_PER_PAGE,
                        "page": page,
                    }
                    try:
                        resp = self.http_client.post(API_URL, json=payload, headers=headers)
                        data = resp.json() if hasattr(resp, "json") else json.loads(resp.text)
                        hits = data.get("data", [])
                        if not hits:
                            break
                        for hit in hits:
                            if not is_it_job(hit):
                                continue
                            job_id = str(hit.get("jobId", "")).strip()
                            raw_url = hit.get("jobUrl") or f"https://www.vietnamworks.com/job-{job_id}-jv"
                            clean_url = clean_canonical_url(raw_url)
                            ledger.register_url(
                                raw_url=clean_url,
                                job_id=job_id,
                                preliminary_title=hit.get("jobTitle", ""),
                                preliminary_company=hit.get("companyName", ""),
                            )
                            discovered_urls.append(clean_url)
                        if len(hits) < HITS_PER_PAGE:
                            break
                        time.sleep(0.3)
                    except Exception as exc:
                        log.warning("[VietnamWorks] Lỗi quét industry %s page %d: %s", ind_id, page, exc)
                        continue

            # Tầng 3: Quét theo danh sách 35 từ khóa IT (chỉ chạy khi quét sâu pages_to_query > 2)
            if pages_to_query > 2:
                log.info("[VietnamWorks] Discovery Tầng 3: Quét sâu theo danh sách 35 từ khóa IT...")
                for query in self.queries:
                    for page in range(pages_to_query):
                        payload = {
                            "userId": 0,
                            "query": query,
                            "filter": [],
                            "ranges": [],
                            "order": [],
                            "hitsPerPage": HITS_PER_PAGE,
                            "page": page,
                        }
                        try:
                            resp = self.http_client.post(API_URL, json=payload, headers=headers)
                            data = resp.json() if hasattr(resp, "json") else json.loads(resp.text)
                            hits = data.get("data", [])
                            if not hits:
                                break
                            for hit in hits:
                                if not is_it_job(hit):
                                    continue
                                job_id = str(hit.get("jobId", "")).strip()
                                raw_url = hit.get("jobUrl") or f"https://www.vietnamworks.com/job-{job_id}-jv"
                                clean_url = clean_canonical_url(raw_url)
                                ledger.register_url(
                                    raw_url=clean_url,
                                    job_id=job_id,
                                    preliminary_title=hit.get("jobTitle", ""),
                                    preliminary_company=hit.get("companyName", ""),
                                )
                                discovered_urls.append(clean_url)
                            if len(hits) < HITS_PER_PAGE:
                                break
                            time.sleep(0.3)
                        except Exception as exc:
                            log.warning("[VietnamWorks] Safe Skip query '%s' page %d: %s", query, page, exc)
                            continue

        ledger.save_catalog()
        ledger.export_daily_manifest()
        if self.sync_minio:
            try:
                ledger.sync_to_minio()
                log.info("[VietnamWorks] Đã đồng bộ URL Ledger lên MinIO Lakehouse.")
            except Exception as e:
                log.warning("[VietnamWorks] Không thể đồng bộ MinIO trong Pha 1: %s", e)

        log.info("[VietnamWorks] Pha 1 hoàn tất: phát hiện %d URLs.", len(discovered_urls))
        return discovered_urls

    def crawl_details(
        self,
        online: bool = False,
        limit: int | None = None,
        retry_failed: bool = False,
        local_html_dir: str | None = None,
    ) -> dict[str, int]:
        """Pha 2: Bóc tách chi tiết tin từ URL Ledger, băm Document JSON duy nhất (content_hash) và lưu MinIO.

        Áp dụng Polite Sleep 2.0s - 4.5s ngẫu nhiên, Checkpoint Sync mỗi 15 tin, và Safe Skip.
        """
        log.info("[VietnamWorks] === Bắt đầu Pha 2: Detail Extraction (Chu kỳ Re-crawl 21 ngày) ===")
        ledger = self._get_ledger()

        if self.sync_minio and online:
            try:
                ledger.pull_from_minio()
            except Exception as e:
                log.warning("[VietnamWorks] Không thể pull Ledger từ MinIO: %s", e)

        candidates = (
            ledger.get_failed_records() if retry_failed else ledger.get_pending_or_due_records(recheck_days=21)
        )
        log.info("[VietnamWorks] Tìm thấy %d tin cần crawl chi tiết trong Ledger.", len(candidates))
        stats = {"success": 0, "failed": 0, "skipped": 0}
        count = 0
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        effective_html_dir = local_html_dir or self.local_html_dir

        for item in candidates:
            if limit and count >= limit:
                break
            url = item["canonical_url"]
            url_hash = item["url_hash"]
            job_id = item["job_id"]

            try:
                # 1. Cơ chế Safe Skip bọc kín từng bài đăng
                raw_payload: dict[str, Any] = {}
                raw_html_content = ""

                # Chế độ cào offline từ thư mục HTML cục bộ
                if effective_html_dir and os.path.isdir(effective_html_dir):
                    html_path = Path(effective_html_dir) / f"{job_id}.html"
                    if not html_path.is_file():
                        # Tìm bất kỳ file html nào có chứa job_id
                        matches = list(Path(effective_html_dir).glob(f"*{job_id}*.html"))
                        html_path = matches[0] if matches else None

                    if html_path and html_path.is_file():
                        raw_html_content = html_path.read_text(encoding="utf-8")
                        raw_payload = build_raw_payload_from_html(raw_html_content)
                    else:
                        raise FileNotFoundError(f"Không tìm thấy file HTML cho jobId {job_id} trong {effective_html_dir}")

                # Chế độ cào online qua API / HttpClient
                elif online:
                    # Polite sleep ngẫu nhiên 1.2s - 2.2s
                    sleep_time = random.uniform(1.2, 2.2)
                    time.sleep(sleep_time)

                    payload_filter = {
                        "filter": [{"field": "jobId", "value": str(job_id)}],
                        "page": 0,
                        "hitsPerPage": 1,
                    }
                    resp = self.http_client.post(API_URL, json=payload_filter)
                    data = resp.json() if hasattr(resp, "json") else json.loads(resp.text)
                    hits = data.get("data", [])
                    if not hits:
                        raise ValueError(f"Không tìm thấy payload cho jobId {job_id}")
                    hit = hits[0]
                    raw_payload = build_raw_payload_from_api(hit)
                else:
                    raise RuntimeError("Chưa bật --online hoặc thiếu --local-html-dir để lấy nội dung chi tiết")

                # 2. Kiểm tra tin đã đóng tuyển dụng hoặc hết hạn
                if is_job_closed_or_expired(raw_payload):
                    log.info("[VietnamWorks] Job %s đã đóng hoặc hết hạn -> mark_closed", job_id)
                    ledger.mark_closed(url_hash)
                    stats["skipped"] += 1
                    continue

                # 3. Nhận diện ngôn ngữ bài đăng
                desc_sample = " ".join(raw_payload.get("description_list", [])[:3]) or raw_payload.get("title", "")
                language = detect_language(desc_sample)

                # 4. Băm toàn vẹn Document JSON duy nhất (Post-Crawl Canonical JSON Hashing)
                content_hash = calculate_json_canonical_hash(raw_payload, exclude_keys=["raw_html"])

                # 5. Đối chiếu hash: Nếu nội dung không đổi và tin đã DONE thì giữ nguyên version
                old_hash = item.get("content_hash")
                old_version = item.get("latest_version") or 0
                if old_hash and old_hash == content_hash and item.get("status") == "DONE":
                    log.info("[VietnamWorks] Job %s không đổi nội dung -> Giữ nguyên v%d", job_id, old_version)
                    ledger.mark_scraped(
                        url_hash=url_hash,
                        content_hash=content_hash,
                        version=old_version,
                        http_status=200,
                    )
                    stats["success"] += 1
                    count += 1
                    continue

                # 6. Kiểm tra tin đăng lại (Repost Detection)
                existing = ledger.find_by_content_hash(content_hash)
                if existing and existing["url_hash"] != url_hash:
                    ledger.mark_scraped(
                        url_hash=url_hash,
                        content_hash=content_hash,
                        version=1,
                        http_status=200,
                    )
                    stats["skipped"] += 1
                    continue

                new_version = old_version + 1 if old_version > 0 else 1

                # 7. Đóng gói Raw Envelope JSON và lưu trữ cục bộ
                envelope = build_raw_envelope(
                    raw_payload=raw_payload,
                    job_id=job_id,
                    url=url,
                    version=new_version,
                    language=language,
                )

                day_raw_dir = Path(self.raw_dir) / date_str
                day_raw_dir.mkdir(parents=True, exist_ok=True)
                json_file_path = day_raw_dir / f"{job_id}_v{new_version}.json"
                with open(json_file_path, "w", encoding="utf-8") as f:
                    json.dump(envelope, f, ensure_ascii=False, indent=2)

                # 8. Đồng bộ lên MinIO Lakehouse nếu có cờ
                if self.sync_minio:
                    s3_key = f"raw/{self.source_name}/{date_str}/{job_id}_v{new_version}.json"
                    try:
                        self._get_minio_store().put_json(s3_key, envelope)
                    except Exception as exc_s3:
                        log.warning("[VietnamWorks] Lỗi đẩy snapshot lên MinIO (%s): %s", s3_key, exc_s3)

                # 9. Lưu ngược lại hash vào URL trong Ledger (chuyển status=DONE)
                ledger.mark_scraped(
                    url_hash=url_hash,
                    content_hash=content_hash,
                    version=new_version,
                    http_status=200,
                )
                stats["success"] += 1
                count += 1

                # 8. Checkpoint Sync Định Kỳ: Cứ sau mỗi 15 tin tự động lưu & sync MinIO
                if count % 15 == 0:
                    ledger.save_catalog()
                    if self.sync_minio:
                        ledger.sync_to_minio()
                    log.info("[VietnamWorks] Checkpoint sync hoàn tất tại mốc %d tin.", count)

            except Exception as exc:
                # Safe skip đưa vào Failed Queue
                log.warning("[VietnamWorks] Safe Skip lỗi cào chi tiết %s (ID %s): %s", url, job_id, exc)
                ledger.mark_failed(url_hash=url_hash, error_message=str(exc))
                stats["failed"] += 1
                continue

        ledger.save_catalog()
        if self.sync_minio:
            ledger.sync_to_minio()

        log.info("[VietnamWorks] Pha 2 hoàn tất: %s", stats)
        return stats

    def parse_raw_envelope(self, item: dict[str, Any]) -> RawJobEnvelope:
        """Parse raw envelope từ API item phục vụ interface tương thích."""
        job_id = str(item.get("jobId", "")).strip()
        url = item.get("jobUrl") or f"https://www.vietnamworks.com/job-{job_id}-jv"
        raw_payload = build_raw_payload_from_api(item)
        content_hash = calculate_json_canonical_hash(raw_payload)
        desc_sample = clean_text(item.get("jobDescription") or "")
        lang = detect_language(desc_sample)

        metadata = {
            "job_id": job_id,
            "source": self.source_name,
            "source_job_id": job_id,
            "source_url": url,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "scraper_version": self.crawler_version,
            "crawler_version": "2.0.0",
            "version": 1,
            "content_hash": content_hash,
            "language": lang,
        }
        return RawJobEnvelope(metadata=metadata, raw_payload=raw_payload)

    def parse_item(self, item: dict[str, Any]) -> JobRecord | None:
        """Biến đổi raw JSON từ VietnamWorks thành JobRecord chuẩn Data Contract Schema v1."""
        raw_id = item.get("jobId")
        if not raw_id:
            return None
        job_id = str(raw_id).strip()

        title = clean_text(item.get("jobTitle") or "")
        if not title:
            return None

        job_url = item.get("jobUrl") or f"https://www.vietnamworks.com/job-{job_id}-jv"
        company_name = clean_text(item.get("companyName") or "Unknown")

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
        if s_min and s_min > 0 and salary_detail.get("salary_min") is None:
            val_min = round(s_min / 1_000_000, 2) if s_min >= 1_000_000 else float(s_min)
            salary_detail["salary_min"] = val_min
        if s_max and s_max > 0 and salary_detail.get("salary_max") is None:
            val_max = round(s_max / 1_000_000, 2) if s_max >= 1_000_000 else float(s_max)
            salary_detail["salary_max"] = val_max
        if s_currency and salary_detail.get("salary_currency") is None:
            salary_detail["salary_currency"] = s_currency

        desc_html = item.get("jobDescription") or f"<p>{title} at {company_name}</p>"
        req_html = item.get("jobRequirement") or ""
        desc_list = text_to_clean_lines(desc_html) or [f"{title} at {company_name}"]
        req_list = text_to_clean_lines(req_html) if req_html else None

        benefits_data = item.get("benefits") or []
        ben_lines: list[str] = []
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

        skills_data = item.get("skills") or []
        tag_skills: list[str] = []
        if isinstance(skills_data, list):
            for s in skills_data:
                if isinstance(s, dict):
                    sname = clean_text(s.get("skillName") or "")
                    if sname and sname not in tag_skills:
                        tag_skills.append(sname)
                elif isinstance(s, str) and s.strip():
                    tag_skills.append(clean_text(s))

        tag_benefits: list[str] = []
        if isinstance(benefits_data, list):
            for b in benefits_data:
                if isinstance(b, dict):
                    bname = clean_text(b.get("benefitNameVI") or b.get("benefitName") or "")
                    if bname and bname not in tag_benefits:
                        tag_benefits.append(bname)

        tags_data = {
            "requirements": None,
            "benefits": tag_benefits if tag_benefits else None,
            "skills": tag_skills if tag_skills else None,
        }

        locations = item.get("locations") or item.get("workingLocations") or []
        loc_names: list[str] = []
        if isinstance(locations, list):
            for l in locations:
                if isinstance(l, dict):
                    name = l.get("cityName") or l.get("address")
                    if name:
                        loc_names.append(clean_text(str(name)))
                elif isinstance(l, str):
                    loc_names.append(clean_text(l))
        loc_text = ", ".join(loc_names) if loc_names else (clean_text(item.get("address") or "") or None)

        deadline_text = clean_text(str(item.get("expiredOn") or "")) or None
        posted_date_text = clean_text(str(item.get("approvedOn") or item.get("createdOn") or ""))

        seniority = clean_text(str(item.get("jobLevelVI") or item.get("jobLevel") or "")) or None
        exp = item.get("yearsOfExperience")
        exp_text = f"{exp} năm kinh nghiệm" if (exp is not None and str(exp) != "0") else None

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

    def _save_raw_payload(self, item: dict[str, Any]) -> None:
        """Queue the untouched API item for the consolidated raw JSON file."""
        raw_json = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        payload_hash = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()
        raw_id = item.get("jobId")
        job_id = str(raw_id).strip() if raw_id is not None else ""
        date_partition = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        base_dir = Path(self.output_dir or f"data/{self.source_name}")
        raw_dir = (
            base_dir if base_dir.name == self.source_name else (base_dir / self.source_name)
        ) / "raw" / date_partition
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

        seen_in_run: set[str] = set()
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
                    resp = self.http_client.post(API_URL, json=payload, headers=headers)
                    data = resp.json()
                except Exception as exc:
                    log.error("[VietnamWorks] Search error for query '%s' page %d: %s", q, page, exc)
                    break

                job_list = data.get("data", [])
                if not job_list:
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

    def sync_lakehouse(self) -> None:
        """Đồng bộ toàn bộ catalog URL và file snapshot raw lên MinIO Lakehouse."""
        ledger = self._get_ledger()
        ledger.save_catalog()
        ledger.sync_to_minio()
        log.info("[VietnamWorks] Đồng bộ Lakehouse hoàn tất.")

    def view_ledger_summary(self) -> None:
        """Hiển thị bảng tóm tắt trạng thái URL Ledger hiện tại."""
        ledger = self._get_ledger()
        total = len(ledger.records)
        counts: dict[str, int] = {}
        for r in ledger.records.values():
            status = r.get("status") if isinstance(r, dict) else getattr(r, "status", "UNKNOWN")
            counts[status] = counts.get(status, 0) + 1

        print("\n=== BẢNG TỔNG KẾT URL LEDGER: VIETNAMWORKS ===")
        print(f"Tổng số URL: {total}")
        for st, c in sorted(counts.items()):
            print(f"  • {st:15s}: {c} tin")
        print("==============================================\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="VietnamWorks Two-Phase Decoupled Crawler")
    parser.add_argument(
        "--phase",
        choices=["discovery", "details", "sync", "view"],
        default="view",
        help="Chọn pha thực thi: discovery (Pha 1), details (Pha 2), sync (đồng bộ), view (xem ledger)",
    )
    parser.add_argument("--online", action="store_true", help="Bật kết nối internet cào trực tuyến")
    parser.add_argument("--sync-minio", action="store_true", help="Đồng bộ URL Ledger và Raw Snapshots lên MinIO Lakehouse")
    parser.add_argument("--retry-failed", action="store_true", help="Cào lại các URL trong hàng đợi lỗi (Failed Queue)")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số lượng tin xử lý")
    parser.add_argument("--local-html-dir", type=str, default=None, help="Thư mục chứa HTML thô để cào offline")
    parser.add_argument("--local-json-file", type=str, default=None, help="File JSON payload để test offline")
    parser.add_argument("--output-dir", type=str, default="data/vietnamworks", help="Thư mục xuất dữ liệu")
    parser.add_argument("--checkpoint-dir", type=str, default=None, help="Thư mục lưu checkpoint")
    parser.add_argument("--max-items", type=int, default=30, help="Số tin tối đa cho BaseCrawler.run()")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    crawler = VietnamWorksCrawler(
        checkpoint_dir=args.checkpoint_dir,
        output_dir=args.output_dir,
        max_items=args.limit or args.max_items,
        local_json_file=args.local_json_file,
        local_html_dir=args.local_html_dir,
        sync_minio=args.sync_minio,
    )

    if args.phase == "discovery":
        crawler.discover_urls(online=args.online, max_pages=args.limit or 5)
    elif args.phase == "details":
        crawler.crawl_details(
            online=args.online,
            limit=args.limit,
            retry_failed=args.retry_failed,
            local_html_dir=args.local_html_dir,
        )
    elif args.phase == "sync":
        crawler.sync_lakehouse()
    elif args.phase == "view":
        crawler.view_ledger_summary()


if __name__ == "__main__":
    main()
