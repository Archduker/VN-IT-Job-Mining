# -*- coding: utf-8 -*-
"""Crawler nguồn Vieclam24h (https://vieclam24h.vn) — Phiên bản 2 giai đoạn 
(Listing -> Detail) sử dụng UrlLedger và xuất dữ liệu chuẩn ra file JSON.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator
from urllib.parse import urljoin

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from bs4 import BeautifulSoup

from collection.base.base_crawler import BaseCrawler
from collection.common.anti_blocking import polite_sleep
from collection.common.http_client import DelayConfig, HttpClient, RetryConfig
from collection.common.minio_raw_pipeline import MinioRawStore
from collection.common.schema import JobMetadata, JobRaw, JobRecord, JobSalary, JobTags
from collection.common.url_ledger import (
    UrlLedger,
    calculate_container_html_hash,
    calculate_json_canonical_hash,
    calculate_json_field_hashes,
    clean_canonical_url,
)
from collection.common.utils import (
    clean_text,
    detect_language,
    parse_salary_detail,
    strip_html_tags,
    text_to_clean_lines,
)

log = logging.getLogger("vieclam24h.crawler")

SOURCE = "vieclam24h"
CRAWLER_VERSION = "2.0.0"
BASE_URL = "https://vieclam24h.vn"

# Các danh mục IT mục tiêu trên Vieclam24h
TARGET_CATEGORIES = [
    {"name": "IT Phần mềm", "path": "/viec-lam-it-phan-mem-o8.html"},
    {"name": "IT Phần cứng - Mạng", "path": "/viec-lam-it-phan-cung-mang-o7.html"},
    {"name": "Bưu chính viễn thông", "path": "/viec-lam-buu-chinh-vien-thong-o38.html"},
]

CONTAINER_SELECTOR = "main"


class ViecLam24hAPIError(RuntimeError):
    """Lỗi xử lý dữ liệu hoặc DOM tại Vieclam24h."""


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def _format_timestamp(ts: Any) -> str:
    if not ts:
        return ""
    try:
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        elif isinstance(ts, str) and ts.isdigit():
            return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")
        return str(ts)
    except Exception:
        return ""


def build_raw_payload(
    html: str = "",
    next_data: dict[str, Any] | None = None,
    job_detail: dict[str, Any] | None = None,
    employer_detail: dict[str, Any] | None = None,
    job_posting: dict[str, Any] | None = None,
    tags: Any = None,
) -> dict[str, Any]:
    """Bóc tách toàn bộ trường dữ liệu đặc thù của Vieclam24h vào đối tượng JSON (Zero Information Loss SD1).
    
    Tuân thủ đúng đặc tả tại neccessary.md:
    - Lưu chuỗi lương nguyên bản hiển thị (ví dụ '10 - 25 triệu'), KHÔNG tự ý tách salary_min/salary_max.
    - Bóc tách đầy đủ các khối: title, salary, deadline, location_summary, experience_summary,
      description, requirements, benefits, working_time, working_address, general_info, keywords, company.
    """
    soup = BeautifulSoup(html, "html.parser") if html else None

    # Nếu chưa có next_data nhưng có html, tìm thẻ script __NEXT_DATA__
    if soup and not next_data:
        script = soup.find("script", id="__NEXT_DATA__")
        if script and script.string:
            try:
                next_data = json.loads(script.string)
            except Exception:
                pass

    api = next_data.get("props", {}).get("initialState", {}).get("api", {}) if isinstance(next_data, dict) else {}
    jd = job_detail or api.get("jobDetailHiddenContact", {}).get("data", {}) or {}
    emp = employer_detail or api.get("employerDetailHiddenContact", {}).get("data", {}) or jd.get("employer_info", {}) or {}
    jp = job_posting or api.get("jobPosting", {}).get("data", {}) or {}
    tags_data = tags or api.get("getTags", {}).get("data", {}) or jd.get("skills_new") or jd.get("skills") or jd.get("tag") or []

    # 1. Header & Badges
    title = ""
    if soup:
        h1 = soup.find("h1")
        if h1:
            title = clean_text(h1.get_text(strip=True))
    if not title:
        title = clean_text(jd.get("title") or (jp.get("title") if isinstance(jp, dict) else "") or "")

    salary_text = ""
    if soup:
        salary_el = soup.find("h2", class_=lambda c: c and "text-24" in c)
        if salary_el and salary_el.get_text(strip=True):
            salary_text = clean_text(salary_el.get_text(strip=True))
        if not salary_text:
            sal_label = soup.find(lambda t: t.name in ["div", "span", "p"] and t.get_text(strip=True) == "Mức lương")
            if sal_label:
                parent = sal_label.find_parent("div")
                if parent:
                    val = parent.get_text(separator=" ", strip=True).replace("Mức lương", "").strip()
                    if val:
                        salary_text = clean_text(val)
    if not salary_text and next_data:
        key_replaces = next_data.get("props", {}).get("pageProps", {}).get("metaSeo", {}).get("keyReplace", [])
        for item in key_replaces:
            if item.get("key") == "{MUC_LUONG}" and item.get("value"):
                salary_text = clean_text(str(item["value"]))
                break
    if not salary_text:
        raw_sal = (
            jd.get("salary_range_text")
            or jd.get("salary_text")
            or (jp.get("baseSalary", {}).get("value", {}).get("value") if isinstance(jp.get("baseSalary"), dict) else "")
            or "Thoả thuận"
        )
        salary_text = clean_text(str(raw_sal))

    deadline = ""
    loc_summary = ""
    exp_summary = ""
    if soup:
        for div in soup.find_all("div", class_=lambda c: c and "flex items-center" in c and "gap" in c):
            text = div.get_text(separator=" ", strip=True)
            if "Hạn nộp hồ sơ" in text:
                m = re.search(r"(\d{2}/\d{2}/\d{4})", text)
                if m:
                    deadline = m.group(1)
            elif "Khu vực tuyển" in text:
                loc_summary = clean_text(text.replace("Khu vực tuyển", "").strip())
            elif "Kinh nghiệm" in text and not exp_summary:
                exp_summary = clean_text(text.replace("Kinh nghiệm", "").strip())

    if not deadline and jd.get("resume_apply_expired"):
        deadline = _format_timestamp(jd.get("resume_apply_expired"))
    if not loc_summary and jd.get("address"):
        loc_summary = clean_text(str(jd.get("address")))
    if not exp_summary and jd.get("experience_range"):
        exp_summary = f"{jd.get('experience_range')} năm"

    # 2. Content sections (Mô tả, Yêu cầu, Quyền lợi, Thời gian, Địa điểm)
    def _extract_section_lines(h2_title: str) -> list[str]:
        if not soup:
            return []
        h2 = soup.find(lambda t: t.name == "h2" and h2_title in t.get_text())
        if not h2:
            return []
        parent = h2.find_parent("div")
        if not parent:
            return []
        full_text = parent.get_text(separator="\n", strip=True)
        lines = [clean_text(l) for l in full_text.split("\n") if clean_text(l)]
        return lines[1:] if lines and h2_title in lines[0] else lines

    desc_lines = _extract_section_lines("Mô tả công việc")
    req_lines = _extract_section_lines("Yêu cầu công việc")
    benefit_raw_lines = _extract_section_lines("Quyền lợi")

    # Fallback to API text lines if DOM did not provide lines
    if not desc_lines and (jd.get("description") or jd.get("description_html")):
        desc_lines = text_to_clean_lines(jd.get("description_html") or jd.get("description"))
    if not req_lines and (jd.get("other_requirement") or jd.get("other_requirement_html") or jd.get("requirement")):
        req_lines = text_to_clean_lines(jd.get("other_requirement_html") or jd.get("other_requirement") or jd.get("requirement"))
    if not benefit_raw_lines and (jd.get("benefit") or jd.get("benefit_html")):
        benefit_raw_lines = text_to_clean_lines(jd.get("benefit_html") or jd.get("benefit"))

    # Tách Thời gian làm việc và Địa điểm làm việc từ khối quyền lợi
    benefit_lines = []
    working_time = []
    working_address = []
    curr_target = benefit_lines
    for line in benefit_raw_lines:
        if "Thời gian làm việc:" in line:
            curr_target = working_time
            continue
        elif "Địa điểm làm việc:" in line:
            curr_target = working_address
            continue
        curr_target.append(line)

    # 3. Thông tin chung (General info)
    general_info = {}
    if soup:
        gen_section = soup.find(lambda tag: tag.name == "h2" and "Thông tin chung" in tag.get_text())
        if gen_section:
            gen_parent = gen_section.find_parent("div")
            items = gen_parent.find_all("div", class_=lambda c: c and "text-12" in c and "text-grey-11" in c)
            for it in items:
                k = clean_text(it.get_text(strip=True))
                val_el = it.find_next_sibling("div") or it.find_parent("div").find_next_sibling("div")
                val = clean_text(val_el.get_text(separator=" ", strip=True)) if val_el else ""
                if k and val:
                    general_info[k] = val

    # Workplaces
    workplaces = []
    if soup:
        dd_el = soup.find(lambda t: t.name == "h2" and "Địa điểm làm việc" in t.get_text())
        if dd_el:
            p = dd_el.find_parent("div")
            container = p.find("div", class_=lambda c: c and "flex-col" in c)
            if container:
                for row in container.find_all("div", recursive=False):
                    text = clean_text(row.get_text(separator=" ", strip=True))
                    if text and text not in workplaces:
                        workplaces.append(text)
            else:
                for row in p.find_all("div", class_=lambda c: c and "flex" in c and "gap" in c):
                    if "flex-col" not in (row.get("class") or []):
                        text = clean_text(row.get_text(separator=" ", strip=True))
                        if text and text not in workplaces:
                            workplaces.append(text)

    # Fallbacks for general info from jd
    posted_date = general_info.get("Ngày đăng") or _format_timestamp(jd.get("created_at"))
    job_level = general_info.get("Cấp bậc") or clean_text(jd.get("level_requirement") or jd.get("position_text") or "")
    hiring_qty = general_info.get("Số lượng tuyển") or clean_text(str(jd.get("vacancy_quantity") or ""))
    working_type = general_info.get("Hình thức làm việc") or clean_text(jd.get("working_method") or jd.get("type_working_text") or "")
    exp_req = general_info.get("Yêu cầu kinh nghiệm") or exp_summary or clean_text(str(jd.get("experience_range") or ""))
    industries = general_info.get("Ngành nghề") or clean_text(str(jp.get("industry") or ""))

    # 4. Từ khoá (Keywords)
    keywords = []
    if soup:
        kw_el = soup.find(string=lambda t: t and "Từ khoá" in t)
        if kw_el:
            kw_parent = kw_el.find_parent("div").find_parent("div")
            for a in kw_parent.find_all("a"):
                t = clean_text(a.get_text(strip=True))
                if t and t not in keywords:
                    keywords.append(t)
    if not keywords and tags_data:
        if isinstance(tags_data, list):
            for t_item in tags_data:
                if isinstance(t_item, dict) and t_item.get("name"):
                    keywords.append(clean_text(t_item["name"]))
                elif isinstance(t_item, str) and t_item.strip():
                    keywords.append(clean_text(t_item))

    # 5. Thông tin công ty (Company)
    comp_name = ""
    comp_addr = ""
    comp_size = ""
    if soup:
        for el in soup.find_all(string=lambda t: t and "Quy mô" in t):
            p = el.find_parent("div")
            if p:
                comp_size = clean_text(p.get_text(separator=" ", strip=True).replace("Quy mô :", "").replace("Quy mô:", "").strip())
            box = el.find_parent("div", class_=lambda c: c and ("bg-white" in c or "rounded" in c))
            if box:
                c_title = box.find("div", class_=lambda c: c and "text-18" in c)
                if c_title:
                    comp_name = clean_text(c_title.get_text(strip=True))
                for a_el in box.find_all(string=lambda t: t and "Địa chỉ" in t):
                    a_p = a_el.find_parent("div")
                    if a_p:
                        comp_addr = clean_text(a_p.get_text(separator=" ", strip=True).replace("Địa chỉ :", "").replace("Địa chỉ:", "").strip())
    if not comp_name:
        comp_name = clean_text(
            (emp.get("name") if isinstance(emp, dict) else "")
            or jd.get("company_name")
            or jd.get("user_display_name")
            or (jp.get("hiringOrganization", {}).get("name") if isinstance(jp, dict) else "")
            or ""
        )
    if not comp_addr and emp.get("address"):
        comp_addr = clean_text(str(emp.get("address")))
    if not comp_size and emp.get("company_size"):
        comp_size = clean_text(str(emp.get("company_size")))

    return {
        "title": title,
        "salary": salary_text,  # Chuỗi nguyên bản, KHÔNG tách salary_min/salary_max
        "deadline": deadline,
        "location_summary": loc_summary,
        "experience_summary": exp_summary,
        "description": desc_lines,
        "requirements": req_lines,
        "benefits": benefit_lines,
        "working_time": "\n".join(working_time),
        "working_address": "\n".join(working_address) if working_address else comp_addr,
        "general_info": {
            "posted_date": posted_date,
            "level": job_level,
            "hiring_quantity": hiring_qty,
            "working_type": working_type,
            "experience": exp_req,
            "industries": industries,
            "workplaces": workplaces,
        },
        "keywords": keywords,
        "company": {
            "name": comp_name,
            "address": comp_addr,
            "size": comp_size,
        },
    }


def build_raw_envelope(
    raw_payload: dict[str, Any],
    job_id: str,
    url: str,
    version: int = 1,
) -> dict[str, Any]:
    """Đóng gói Raw Envelope JSON kèm Post-Crawl Canonical JSON Hashing."""
    canonical_hash = calculate_json_canonical_hash(raw_payload, exclude_keys=["raw_html"])
    field_hashes = calculate_json_field_hashes(raw_payload)
    return {
        "metadata": {
            "job_id": job_id,
            "source": SOURCE,
            "source_url": url,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "scraper_version": CRAWLER_VERSION,
            "version": version,
            "content_hash": canonical_hash,
            "canonical_hash": canonical_hash,
            "field_hashes": field_hashes,
        },
        "raw_payload": raw_payload,
    }


def _make_record(
    job_detail: dict[str, Any],
    fallback_url: str,
    *,
    batch_id: str = "batch_001",
    crawled_at: datetime | None = None,
) -> JobRecord:
    job_id = str(job_detail.get("id") or job_detail.get("job_id") or "")
    if not job_id and fallback_url:
        m_id = re.search(r"id(\d+)", fallback_url)
        if m_id:
            job_id = m_id.group(1)

    title = _clean_text(job_detail.get("title"))

    comp_obj = job_detail.get("company")
    if isinstance(comp_obj, dict):
        company = _clean_text(comp_obj.get("name"))
    elif isinstance(comp_obj, str):
        company = _clean_text(comp_obj)
    else:
        employer = job_detail.get("employer_info", {})
        company = _clean_text(employer.get("name") if isinstance(employer, dict) else (job_detail.get("company_name") or job_detail.get("user_display_name")))

    if not title or not company:
        raise ViecLam24hAPIError("Bản ghi thiếu tiêu đề hoặc tên công ty.")

    title_slug = job_detail.get("title_slug", "")
    job_url = fallback_url or f"{BASE_URL}/{title_slug}-id{job_id}.html"

    # Xử lý địa chỉ
    street_address, address_locality, address_region, address_country = None, None, None, None
    places = job_detail.get("places", [])
    if isinstance(places, str):
        try:
            places = json.loads(places)
        except Exception:
            places = []
    if places and isinstance(places, list) and isinstance(places[0], dict):
        p_info = places[0]
        street_address = _clean_text(p_info.get("address"))
        address_locality = _clean_text(p_info.get("city_name") or p_info.get("province_name"))

    if not street_address:
        street_address = _clean_text(job_detail.get("working_address") or (comp_obj.get("address") if isinstance(comp_obj, dict) else None))
    if not address_locality:
        address_locality = _clean_text(job_detail.get("location_summary"))

    location_parts = [p for p in [street_address, address_locality, address_region, address_country] if p]
    location_text = ", ".join(location_parts) if location_parts else None

    # Xử lý lương
    s_min = job_detail.get("salary_min")
    s_max = job_detail.get("salary_max")
    s_min_val, s_max_val = None, None
    if s_min is not None:
        try:
            s_min_num = float(s_min)
            if s_min_num > 0:
                s_min_val = s_min_num / 1_000_000 if s_min_num >= 1000 else s_min_num
        except (ValueError, TypeError):
            pass
    if s_max is not None:
        try:
            s_max_num = float(s_max)
            if s_max_num > 0:
                s_max_val = s_max_num / 1_000_000 if s_max_num >= 1000 else s_max_num
        except (ValueError, TypeError):
            pass

    raw_salary_text = job_detail.get("salary") or job_detail.get("salary_range_text") or job_detail.get("salary_text")
    if s_min_val is None and s_max_val is None and raw_salary_text:
        m_range = re.search(r"(\d+(?:[.,]\d+)?)\s*-\s*(\d+(?:[.,]\d+)?)\s*triệu", str(raw_salary_text), re.I)
        if m_range:
            s_min_val = float(m_range.group(1).replace(",", "."))
            s_max_val = float(m_range.group(2).replace(",", "."))
        else:
            m_single = re.search(r"(?:từ|trên)\s*(\d+(?:[.,]\d+)?)\s*triệu", str(raw_salary_text), re.I)
            if m_single:
                s_min_val = float(m_single.group(1).replace(",", "."))
            else:
                m_max_s = re.search(r"(?:tới|đến|dưới)\s*(\d+(?:[.,]\d+)?)\s*triệu", str(raw_salary_text), re.I)
                if m_max_s:
                    s_max_val = float(m_max_s.group(1).replace(",", "."))

    if not raw_salary_text:
        if s_min_val is not None and s_max_val is not None:
            salary_text = f"{int(s_min_val)} - {int(s_max_val)} triệu"
            is_neg = False
        elif s_min_val is not None:
            salary_text = f"Từ {int(s_min_val)} triệu"
            is_neg = False
        elif s_max_val is not None:
            salary_text = f"Tới {int(s_max_val)} triệu"
            is_neg = False
        else:
            salary_text = "Thoả thuận"
            is_neg = True
    else:
        salary_text = str(raw_salary_text)
        is_neg = (s_min_val is None and s_max_val is None)

    salary = JobSalary(
        salary_text=salary_text,
        salary_min=s_min_val,
        salary_max=s_max_val,
        salary_currency="VND" if (s_min_val is not None or s_max_val is not None) else None,
        pay_period="month" if (s_min_val is not None or s_max_val is not None) else None,
        is_negotiable=is_neg,
        has_commission=False,
    )

    desc_raw = (
        job_detail.get("description")
        or job_detail.get("description_html")
        or job_detail.get("job_description_html")
    )
    req_raw = (
        job_detail.get("requirements")
        or job_detail.get("other_requirement_html")
        or job_detail.get("other_requirement")
        or job_detail.get("job_requirement_html")
    )
    benefit_raw = (
        job_detail.get("benefits")
        or job_detail.get("benefit_html")
        or job_detail.get("benefit")
        or job_detail.get("job_benefit_html")
    )

    if isinstance(desc_raw, list):
        description_list = [_clean_text(str(x)) for x in desc_raw if _clean_text(str(x))]
    elif desc_raw:
        description_list = text_to_clean_lines(str(desc_raw))
    else:
        description_list = []

    if isinstance(req_raw, list):
        requirements_list = [_clean_text(str(x)) for x in req_raw if _clean_text(str(x))]
    elif req_raw:
        requirements_list = text_to_clean_lines(str(req_raw))
    else:
        requirements_list = []

    if isinstance(benefit_raw, list):
        benefits_list = [_clean_text(str(x)) for x in benefit_raw if _clean_text(str(x))]
    elif benefit_raw:
        benefits_list = text_to_clean_lines(str(benefit_raw))
    else:
        benefits_list = []

    if not description_list:
        description_list = requirements_list if requirements_list else [title]

    experience_val = (
        job_detail.get("experience_range")
        or job_detail.get("experience_text")
        or job_detail.get("experience_summary")
        or (job_detail.get("general_info", {}).get("experience") if isinstance(job_detail.get("general_info"), dict) else None)
    )
    experience_text = (
        f"{experience_val} năm kinh nghiệm chuyên môn"
        if (experience_val and str(experience_val).isdigit())
        else (str(experience_val) if experience_val else "Không yêu cầu kinh nghiệm")
    )

    # Thẻ kỹ năng / tags nếu có từ API
    skills_raw = job_detail.get("smart_tags") or job_detail.get("skills") or job_detail.get("tags") or []
    skill_names: list[str] = []
    if isinstance(skills_raw, list):
        for s in skills_raw:
            if isinstance(s, dict) and s.get("name"):
                skill_names.append(str(s["name"]).strip())
            elif isinstance(s, str) and s.strip():
                skill_names.append(s.strip())

    tags = JobTags(
        requirements=None,
        benefits=None,
        skills=skill_names or None,
    )

    raw_text = " ".join(value for value in (title, company, *description_list) if value)
    language = detect_language(raw_text)

    extra: dict[str, Any] = {
        "experience": experience_text,
        "address_components": {
            "streetAddress": street_address,
            "addressLocality": address_locality,
            "addressRegion": address_region,
            "addressCountry": address_country,
        },
    }
    if job_detail.get("vacancy_quantity"):
        extra["hiring_quantity"] = f"{job_detail['vacancy_quantity']} người"
    if job_detail.get("degree_requirement"):
        extra["education"] = str(job_detail["degree_requirement"])
    elif job_detail.get("education"):
        extra["education"] = str(job_detail["education"])
    if job_detail.get("working_method"):
        extra["work_schedule"] = str(job_detail["working_method"])
    elif job_detail.get("work_schedule"):
        extra["work_schedule"] = str(job_detail["work_schedule"])
    if job_detail.get("workplace_type"):
        extra["workplace_type"] = str(job_detail["workplace_type"])

    employment_type_text = (
        _clean_text(job_detail.get("type_working_text"))
        or _clean_text(job_detail.get("working_method"))
        or _clean_text(job_detail.get("employment_type"))
        or _clean_text(job_detail.get("work_type"))
        or None
    )
    seniority_text = (
        _clean_text(job_detail.get("position_text"))
        or _clean_text(job_detail.get("level"))
        or _clean_text(job_detail.get("level_requirement"))
        or _clean_text(job_detail.get("job_level"))
        or None
    )

    raw_values = dict(
        title=title,
        company=company,
        description_list=description_list,
        salary=salary,
        tags=tags,
        requirements_list=requirements_list,
        benefits_list=benefits_list,
        location_text=location_text,
        deadline_text=_format_timestamp(job_detail.get("resume_apply_expired")),
        posted_date_text=_format_timestamp(job_detail.get("created_at")),
        employment_type_text=employment_type_text,
        seniority_text=seniority_text,
        extra=extra,
    )
    meta = JobMetadata(
        source="vieclam24h",
        source_job_id=job_id,
        url=job_url,
        dedup_key=f"vieclam24h:{job_id}" if job_id else f"vieclam24h:{job_url}",
        crawled_at=crawled_at or datetime.now(timezone.utc),
        batch_id=batch_id,
        crawler_version=CRAWLER_VERSION,
        language=language,
    )
    return JobRecord(_meta=meta, raw=JobRaw(**raw_values))


class ViecLam24hCrawler(BaseCrawler):
    """Crawler cho nguồn Vieclam24h theo mô hình 2 giai đoạn (UrlLedger & MinIO Lakehouse Raw Envelope)."""

    source_name = SOURCE
    crawler_version = CRAWLER_VERSION

    def __init__(
        self,
        checkpoint_dir: str | None = None,
        output_dir: str | None = None,
        max_items: int | None = None,
        checkpoint_interval: int = 10,
        min_delay: float = 2.0,
        max_delay: float = 4.0,
        local_json_file: Path | str | None = None,
        sync_minio: bool = False,
        online: bool = False,
    ) -> None:
        base_dir = Path(output_dir or "data/vieclam24h")
        target_output_dir = str(base_dir if base_dir.name == "vieclam24h" else (base_dir / "vieclam24h"))
        super().__init__(
            checkpoint_dir=checkpoint_dir,
            output_dir=target_output_dir,
            checkpoint_interval=checkpoint_interval,
        )
        self.ledger = UrlLedger(
            source=self.source_name,
            storage_dir=str(Path(self.output_dir) / "url_ledger"),
        )
        self.sync_minio = sync_minio
        self.online = online
        self._minio_store = None
        self.client = HttpClient(
            source=self.source_name,
            delay_config=DelayConfig(min_seconds=min_delay, max_seconds=max_delay),
            retry_config=RetryConfig(max_retries=3, backoff_factor=1.0),
        )
        self.local_json_file = Path(local_json_file) if local_json_file else None
        browser_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.9",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://vieclam24h.vn/",
        }
        if hasattr(self.client, "session") and hasattr(self.client.session, "headers"):
            self.client.session.headers.update(browser_headers)

    def _get_minio_store(self) -> MinioRawStore:
        if self._minio_store is None:
            self._minio_store = MinioRawStore()
        return self._minio_store

    def _extract_next_data(self, html: str) -> dict[str, Any] | None:
        """Trích xuất state JSON từ thẻ script __NEXT_DATA__."""
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")
        script = soup.find("script", id="__NEXT_DATA__")
        if script and script.string:
            try:
                return json.loads(script.string)
            except Exception:
                pass
        return None

    def _get_target_records(self, recheck_days: int = 21) -> list[dict[str, Any]]:
        """Lấy danh sách các bản ghi cần xử lý."""
        records = []
        ledger_dict = (
            getattr(self.ledger, "records", None)
            or getattr(self.ledger, "catalog", None)
            or getattr(self.ledger, "urls", None)
        )
        
        if isinstance(ledger_dict, dict):
            for r in ledger_dict.values():
                if not r.get("content_hash") or not r.get("last_scraped_at"):
                    records.append(r)
                    continue
                
                last_str = r.get("last_scraped_at")
                if last_str and recheck_days > 0:
                    try:
                        last_dt = datetime.fromisoformat(last_str.replace("Z", "+00:00"))
                        age_days = (datetime.now(timezone.utc) - last_dt).days
                        if age_days >= recheck_days:
                            records.append(r)
                    except Exception:
                        pass
        else:
            records = self.ledger.get_pending_or_due_records(recheck_days=recheck_days)
            
        return records

    # ── PHA 1: URL DISCOVERY ──────────────────────────────────
    def discover_urls(self, online: bool = False, max_pages: int | None = None) -> int:
        """Quét toàn bộ danh mục IT Vieclam24h, ghi nhận vào UrlLedger (content_hash=None) và đẩy lên MinIO."""
        log.info("[Vieclam24h] === Bắt đầu Pha 1: URL Discovery ===")
        total_discovered = 0
        is_online = online or self.online

        for category in TARGET_CATEGORIES:
            cat_name = category["name"]
            cat_path = category["path"]
            log.info("[Vieclam24h] Quét danh mục: %s (%s)", cat_name, cat_path)

            page_idx = 1
            while True:
                if max_pages is not None and page_idx > max_pages:
                    break

                page_url = f"{BASE_URL}{cat_path}?page={page_idx}" if page_idx > 1 else f"{BASE_URL}{cat_path}"
                try:
                    if is_online and page_idx > 1:
                        polite_sleep(1.0, 2.0, reason=f"Nghỉ giữa các trang danh mục {cat_name}")
                    resp = self.client.get(page_url)
                    if resp.status_code >= 400:
                        log.warning("[Vieclam24h] HTTP Error %d tại trang %d danh mục %s", resp.status_code, page_idx, cat_name)
                        break

                    html = resp.text
                    soup = BeautifulSoup(html, "html.parser")
                    
                    detail_links_map: dict[str, dict[str, str]] = {}
                    for a in soup.find_all("a"):
                        href = a.get("href", "")
                        clean_href = href.split("?")[0].strip()
                        if ("-c" in clean_href or "id" in clean_href) and clean_href.endswith(".html"):
                            m = re.search(r"id(\d+)\.html", clean_href)
                            if m:
                                jid = m.group(1)
                                full_url = clean_canonical_url(urljoin(BASE_URL, clean_href))
                                title_text = clean_text(a.get_text())
                                detail_links_map[jid] = {"url": full_url, "title": title_text}

                    script = soup.find("script", id="__NEXT_DATA__")
                    if not script or not script.string:
                        log.warning("[Vieclam24h] Không tìm thấy __NEXT_DATA__ tại trang %d", page_idx)
                        break

                    next_data = json.loads(script.string)
                    api_state = next_data.get("props", {}).get("initialState", {}).get("api", {})
                    listing_items = api_state.get("getJobList", {}).get("data", {}).get("items", [])

                    if not listing_items:
                        log.info("[Vieclam24h] Hết tin tại trang %d ngành %s", page_idx, cat_name)
                        break

                    for item in listing_items:
                        jid = str(item.get("id", ""))
                        title_slug = item.get("title_slug", "")
                        title = clean_text(item.get("title", ""))
                        
                        comp_raw = (
                            item.get("company_name")
                            or item.get("user_display_name")
                            or item.get("company")
                        )
                        if isinstance(comp_raw, dict):
                            comp = clean_text(comp_raw.get("name") or comp_raw.get("display_name") or "") or "Unknown"
                        else:
                            comp = clean_text(str(comp_raw)) if comp_raw else "Unknown"

                        detail_info = detail_links_map.get(jid)
                        detail_url = detail_info["url"] if detail_info else None
                        if not detail_url and title_slug:
                            detail_url = clean_canonical_url(f"{BASE_URL}/{title_slug}-id{jid}.html")

                        if not detail_url or not jid:
                            continue

                        # Đăng ký URL vào ledger: ban đầu PENDING và content_hash=None
                        self.ledger.register_url(
                            raw_url=detail_url,
                            job_id=jid,
                            preliminary_title=title or (detail_info["title"] if detail_info else "Unknown"),
                            preliminary_company=comp,
                        )
                        total_discovered += 1

                    page_idx += 1
                except Exception as exc:
                    log.error("[Vieclam24h] Lỗi quét danh mục trang %d ngành %s: %s", page_idx, cat_name, exc)
                    break

        self.ledger.save_catalog()
        manifest_file = self.ledger.export_daily_manifest()
        if self.sync_minio:
            self.ledger.sync_to_minio()
        log.info("[Vieclam24h] Hoàn thành Pha 1. Tổng cộng %d URL trong Ledger (%s)", len(self.ledger.records), manifest_file)
        return len(self.ledger.records)

    # ── PHA 2: DETAIL EXTRACTION ──────────────────────────────
    def crawl_details(
        self,
        online: bool = False,
        limit: int | None = None,
        retry_failed: bool = False,
    ) -> dict[str, int]:
        """Pha 2: Kéo URL từ MinIO, cào chi tiết HTML, bóc tách JSON, băm Document JSON và đẩy Raw Envelope lên MinIO."""
        log.info("[Vieclam24h] === Bắt đầu Pha 2: Detail Extraction (MinIO Raw Envelope & Post-Crawl Hashing) ===")
        is_online = online or self.online

        if self.sync_minio and is_online:
            log.info("[Vieclam24h] Đang kéo URL Ledger mới nhất từ MinIO về máy...")
            self.ledger.pull_from_minio()

        if retry_failed:
            raw_candidates = self.ledger.get_failed_records()
            log.info("[Vieclam24h] Chế độ retry-failed: tìm thấy %d link trong Failed Queue.", len(raw_candidates))
        else:
            raw_candidates = self._get_target_records(recheck_days=21)
            log.info("[Vieclam24h] Tìm thấy %d link cần xử lý (PENDING hoặc đến hạn 21 ngày).", len(raw_candidates))

        # Chỉ xử lý các bài thuộc miền vieclam24h.vn để bảo đảm cách ly nguồn
        candidates = [r for r in raw_candidates if "vieclam24h.vn" in r.get("canonical_url", "")]

        if limit is not None:
            candidates = candidates[:limit]

        stats = {"success": 0, "failed": 0, "skipped": 0, "repost": 0}
        extracted_jobs: list[dict[str, Any]] = []
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        for idx, item in enumerate(candidates, 1):
            url = item["canonical_url"]
            url_hash = item["url_hash"]
            job_id = item["job_id"]

            try:
                log.info("[Vieclam24h] [%d/%d] Đang tải chi tiết: %s", idx, len(candidates), url)
                if is_online:
                    polite_sleep(2.0, 4.0, reason="Nghỉ giữa 2 bài đăng Vieclam24h")

                resp = self.client.get(url)
                if resp.status_code >= 400:
                    log.warning("[Vieclam24h] HTTP Error %d tại URL: %s", resp.status_code, url)
                    self.ledger.mark_failed(url_hash, error_message=f"HTTP {resp.status_code}")
                    stats["failed"] += 1
                    continue

                html = resp.text
                if resp.status_code == 404 or "Tin tuyển dụng này không tồn tại" in html or "<title>404" in html:
                    self.ledger.mark_closed(url_hash)
                    stats["skipped"] += 1
                    continue

                # Trích xuất dữ liệu từ Next.js SSR state
                next_data = self._extract_next_data(html)
                api = next_data.get("props", {}).get("initialState", {}).get("api", {}) if next_data else {}
                job_detail = api.get("jobDetailHiddenContact", {}).get("data", {})
                employer_detail = api.get("employerDetailHiddenContact", {}).get("data", {})
                job_posting = api.get("jobPosting", {}).get("data", {})
                tags = api.get("getTags", {}).get("data", {})

                if not job_detail:
                    soup = BeautifulSoup(html, "html.parser")
                    h1_el = soup.select_one("h1")
                    if not h1_el:
                        log.warning("[Vieclam24h] Không tìm thấy nội dung bài đăng tại URL: %s", url)
                        self.ledger.mark_closed(url_hash)
                        stats["skipped"] += 1
                        continue
                    job_detail = {
                        "id": job_id,
                        "title": clean_text(h1_el.get_text(strip=True)),
                        "description": str(soup.select_one(".job-description") or ""),
                    }

                # 1. Bóc tách 100% trường dữ liệu đặc thù vào raw_payload (Zero Information Loss)
                raw_payload = build_raw_payload(
                    html=html,
                    next_data=next_data,
                    job_detail=job_detail,
                    employer_detail=employer_detail,
                    job_posting=job_posting,
                    tags=tags,
                )

                # 2. Băm toàn vẹn Document JSON sau cào (Post-Crawl Canonical JSON Hashing)
                canonical_hash = calculate_json_canonical_hash(raw_payload, exclude_keys=["raw_html"])
                field_hashes = calculate_json_field_hashes(raw_payload)

                # 3. Kiểm tra Repost
                existing = self.ledger.find_by_content_hash(canonical_hash)
                if existing and existing["url_hash"] != url_hash:
                    log.info("[Vieclam24h] Phát hiện Repost: %s trùng nội dung với %s", url, existing["canonical_url"])
                    self.ledger.mark_done(url_hash, content_hash=canonical_hash, repost_of_url_hash=existing["url_hash"])
                    stats["repost"] += 1
                    continue

                # 4. Xác định version (CDC)
                curr_ver = item.get("latest_version") or 0
                new_ver = curr_ver if (item.get("content_hash") == canonical_hash and curr_ver > 0) else curr_ver + 1

                # 5. Đóng gói Raw Envelope
                envelope = build_raw_envelope(raw_payload, job_id=job_id, url=url, version=new_ver)

                # 6. Lưu file Raw Snapshot cục bộ
                raw_dir = Path(self.output_dir) / "raw" / today_str
                raw_dir.mkdir(parents=True, exist_ok=True)
                snapshot_file = raw_dir / f"{job_id}_v{new_ver}.json"
                with open(snapshot_file, "w", encoding="utf-8") as f:
                    json.dump(envelope, f, ensure_ascii=False, indent=2)

                # 7. Đẩy snapshot lên MinIO Lakehouse
                if self.sync_minio:
                    s3_key = f"raw/{self.source_name}/{today_str}/{job_id}_v{new_ver}.json"
                    self._get_minio_store().put_json(s3_key, envelope)

                # 8. Lưu ngược lại mã hash vào URL trong Ledger
                self.ledger.mark_done(url_hash, content_hash=canonical_hash, new_version=new_ver)
                extracted_jobs.append(envelope)
                stats["success"] += 1

                # 9. Checkpoint sync định kỳ mỗi 15 tin
                if (stats["success"] + stats["repost"]) % 15 == 0:
                    log.info("[Vieclam24h] Checkpoint sync: đồng bộ Ledger lên MinIO Lakehouse...")
                    self.ledger.save_catalog()
                    if self.sync_minio:
                        self.ledger.sync_to_minio()

            except Exception as exc:
                log.warning("[Vieclam24h] Lỗi cào %s: %s -> Safe Skip đưa vào Failed Queue", url, exc)
                self.ledger.mark_failed(url_hash, error_message=str(exc))
                stats["failed"] += 1

        # Lưu batch tổng hợp cục bộ
        if extracted_jobs:
            out_path = Path(self.output_dir)
            out_path.mkdir(parents=True, exist_ok=True)
            output_file = out_path / "batch_001.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(extracted_jobs, f, ensure_ascii=False, indent=2)

        self.ledger.save_catalog()
        if self.sync_minio:
            self.ledger.sync_to_minio()
        log.info("[Vieclam24h] Hoàn thành Pha 2. Thống kê: %s", stats)
        return stats

    def fetch_items(self) -> Generator[dict[str, Any], None, None]:
        """Tương thích BaseCrawler: Duyệt qua các bản ghi pending/due từ ledger hoặc file offline."""
        if self.local_json_file and self.local_json_file.exists():
            log.info("Đang đọc dữ liệu offline từ: %s", self.local_json_file)
            content = self.local_json_file.read_text(encoding="utf-8")
            data = json.loads(content)
            items = data if isinstance(data, list) else [data]
            for it in items:
                if isinstance(it, dict):
                    if "job_detail" in it:
                        yield it
                    else:
                        yield {"job_detail": it, "url": it.get("url", "")}
            return

        pending_records = self._get_target_records(recheck_days=21)
        for item in pending_records:
            url = item["canonical_url"]
            job_id = item["job_id"]
            try:
                resp = self.client.get(url)
                if resp.status_code >= 400:
                    continue
                html = resp.text
                next_data = self._extract_next_data(html)
                d_api = next_data.get("props", {}).get("initialState", {}).get("api", {}) if next_data else {}
                job_detail = d_api.get("jobDetailHiddenContact", {}).get("data", {})
                if not job_detail:
                    continue
                yield {
                    "job_id": job_id,
                    "url": url,
                    "html_content": html,
                    "job_detail": job_detail,
                }
            except Exception as exc:
                log.warning("[Vieclam24h] Lỗi fetch item %s: %s", url, exc)

    def parse_item(self, item: dict[str, Any]) -> JobRecord | None:
        """Chuẩn hóa dữ liệu thô sang JobRecord chuẩn xác."""
        job_detail = item.get("job_detail") or item
        fallback_url = item.get("url") or ""
        try:
            return _make_record(
                job_detail,
                fallback_url,
                batch_id=self.batch_id,
                crawled_at=datetime.now(timezone.utc),
            )
        except Exception as exc:
            log.warning("Bỏ qua bản ghi không hợp lệ: %s", exc)
            return None


def main():
    parser = argparse.ArgumentParser(description="Vieclam24h Two-Phase MinIO Job Crawler")
    parser.add_argument("--phase", type=str, choices=["all", "discovery", "details", "sync", "view"], default="all", help="Pha cần chạy: discovery, details, sync, view, all")
    parser.add_argument("--online", action="store_true", help="Cho phép gọi mạng cào trực tuyến")
    parser.add_argument("--sync-minio", action="store_true", help="Tự động đồng bộ Ledger và Raw Snapshots lên MinIO")
    parser.add_argument("--retry-failed", action="store_true", help="Cào lại các URL trong Failed Queue")
    parser.add_argument("--limit", type=int, default=None, help="Số tin tối đa cần cào ở Pha 2")
    parser.add_argument("--max-pages", type=int, default=None, help="Số trang danh mục tối đa cần quét ở Pha 1")
    parser.add_argument("--output-dir", type=str, default="data/vieclam24h", help="Thư mục gốc lưu trữ dữ liệu")
    parser.add_argument("--checkpoint-dir", type=str, default=None, help="Thư mục lưu checkpoint")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    crawler = ViecLam24hCrawler(
        checkpoint_dir=args.checkpoint_dir,
        output_dir=args.output_dir,
        sync_minio=args.sync_minio,
        online=args.online,
    )

    if args.phase == "discovery":
        total = crawler.discover_urls(online=args.online, max_pages=args.max_pages)
        print(f"Pha 1 Discovery hoàn thành. Tổng số URL ghi nhận: {total}")
    elif args.phase == "details":
        stats = crawler.crawl_details(online=args.online, limit=args.limit, retry_failed=args.retry_failed)
        print("Pha 2 Detail Extraction hoàn thành:", stats)
    elif args.phase == "sync":
        crawler.ledger.save_catalog()
        crawler.ledger.sync_to_minio()
        print("Đã đồng bộ URL Ledger lên MinIO Lakehouse thành công.")
    elif args.phase == "view":
        stats = crawler.ledger.get_stats()
        print("Trạng thái URL Ledger hiện tại:", stats)
    else:
        crawler.discover_urls(online=args.online, max_pages=args.max_pages)
        stats = crawler.crawl_details(online=args.online, limit=args.limit, retry_failed=args.retry_failed)
        print("Crawl hoàn tất:", stats)


if __name__ == "__main__":
    main()