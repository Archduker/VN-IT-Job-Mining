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

from crawlers.base.base_crawler import BaseCrawler
from crawlers.common.http_client import DelayConfig, HttpClient, RetryConfig
from crawlers.common.schema import JobMetadata, JobRaw, JobRecord, JobSalary, JobTags
from crawlers.common.url_ledger import (
    UrlLedger,
    calculate_container_html_hash,
    clean_canonical_url,
)
from crawlers.common.utils import (
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


def _make_record(
    job_detail: dict[str, Any],
    fallback_url: str,
    *,
    batch_id: str = "batch_001",
    crawled_at: datetime | None = None,
) -> JobRecord:
    job_id = str(job_detail.get("id", ""))
    title = _clean_text(job_detail.get("title"))
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

    raw_salary_text = job_detail.get("salary_range_text") or job_detail.get("salary_text")
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

    desc_html = (
        job_detail.get("description_html")
        or job_detail.get("description")
        or job_detail.get("job_description_html")
    )
    req_html = (
        job_detail.get("other_requirement_html")
        or job_detail.get("other_requirement")
        or job_detail.get("job_requirement_html")
        or job_detail.get("requirements")
    )
    benefit_html = (
        job_detail.get("benefit_html")
        or job_detail.get("benefit")
        or job_detail.get("job_benefit_html")
        or job_detail.get("benefits")
    )

    description_list = text_to_clean_lines(str(desc_html)) if desc_html else []
    requirements_list = text_to_clean_lines(str(req_html)) if req_html else []
    benefits_list = text_to_clean_lines(str(benefit_html)) if benefit_html else []

    if not description_list:
        description_list = requirements_list if requirements_list else [title]

    experience_val = job_detail.get("experience_range") or job_detail.get("experience_text")
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
    """Crawler cho nguồn Vieclam24h theo mô hình 2 giai đoạn (UrlLedger & JobRecord)."""

    source_name = SOURCE
    crawler_version = CRAWLER_VERSION

    def __init__(
        self,
        checkpoint_dir: str | None = None,
        output_dir: str | None = None,
        max_items: int | None = 5,
        checkpoint_interval: int = 10,
        min_delay: float = 1.0,
        max_delay: float = 2.0,
        local_json_file: Path | str | None = None,
    ) -> None:
        target_output_dir = output_dir or "data/vieclam24h"
        super().__init__(
            checkpoint_dir=checkpoint_dir,
            output_dir=target_output_dir,
            checkpoint_interval=checkpoint_interval,
        )
        self.ledger = UrlLedger(
            source=self.source_name,
            storage_dir=str(Path(self.output_dir) / "url_ledger"),
        )
        
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
    def discover_urls(self, max_pages: int | None = None) -> int:
        """Quét toàn bộ danh mục Vieclam24h và ghi nhận vào UrlLedger."""
        log.info("[Vieclam24h] === Bắt đầu Pha 1: URL Discovery ===")
        total_discovered = 0

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
                    resp = self.client.get(page_url)
                    if resp.status_code >= 400:
                        log.warning("[Vieclam24h] HTTP Error %d tại trang %d danh mục %s", resp.status_code, page_idx, cat_name)
                        break

                    html = resp.text
                    soup = BeautifulSoup(html, "html.parser")
                    
                    detail_links_map: dict[str, dict[str, str]] = {}
                    for a in soup.find_all("a"):
                        href = a.get("href", "")
                        clean_href = href.split("?")[0]
                        if "-c" in clean_href and "id" in clean_href and clean_href.endswith(".html"):
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
        self.ledger.sync_to_minio()
        log.info("[Vieclam24h] Hoàn thành Pha 1. Tổng cộng %d URL đã ghi nhận vào %s", total_discovered, manifest_file)
        return total_discovered

    # ── PHA 2: DETAIL EXTRACTION ──────────────────────────────
    def crawl_details(self, limit: int | None = None) -> dict[str, int]:
        """Tải chi tiết, trích xuất dữ liệu theo định dạng raw_data và lưu ra file JSON tập trung."""
        log.info("[Vieclam24h] === Bắt đầu Pha 2: Detail Extraction (Xuất file raw_data JSON) ===")
        pending_records = self._get_target_records(recheck_days=21)
        log.info("[Vieclam24h] Tìm thấy %d link cần xử lý trong Ledger.", len(pending_records))

        stats = {"success": 0, "failed": 0, "skipped": 0, "repost": 0}
        extracted_jobs: list[dict[str, Any]] = []

        count = 0
        for item in pending_records:
            if limit is not None and count >= limit:
                break

            url = item["canonical_url"]
            url_hash = item["url_hash"]
            job_id = item["job_id"]

            try:
                log.info("[Vieclam24h] [%d/%d] Đang tải chi tiết: %s", count + 1, len(pending_records), url)
                resp = self.client.get(url)
                if resp.status_code >= 400:
                    log.warning("[Vieclam24h] HTTP Error %d tại URL: %s", resp.status_code, url)
                    self.ledger.mark_failed(url_hash, error_message=f"HTTP {resp.status_code}")
                    stats["failed"] += 1
                    continue

                html = resp.text
                if "404" in html or "Tin tuyển dụng này không tồn tại" in html:
                    self.ledger.mark_closed(url_hash)
                    stats["skipped"] += 1
                    continue

                # TÍNH TOÁN CLEAN CONTAINER HASH
                new_hash = None
                try:
                    new_hash = calculate_container_html_hash(html, container_selector=CONTAINER_SELECTOR)
                except Exception as exc:
                    log.debug("[Vieclam24h] Không thể băm với selector '%s': %s", CONTAINER_SELECTOR, exc)

                if not new_hash:
                    import hashlib
                    soup = BeautifulSoup(html, "html.parser")
                    container = soup.select_one(CONTAINER_SELECTOR) or soup.select_one("body") or soup
                    new_hash = hashlib.sha256(str(container).encode("utf-8")).hexdigest()

                # Kiểm tra Repost
                existing = self.ledger.find_by_content_hash(new_hash)
                if existing and existing["url_hash"] != url_hash:
                    log.info("[Vieclam24h] Phát hiện Repost: %s trùng nội dung với %s", url, existing["canonical_url"])
                    self.ledger.mark_done(url_hash, content_hash=new_hash, repost_of_url_hash=existing["url_hash"])
                    stats["repost"] += 1
                    count += 1
                    continue

                curr_ver = item.get("latest_version") or 0
                new_ver = curr_ver if (item.get("content_hash") == new_hash and curr_ver > 0) else curr_ver + 1

                # Trích xuất dữ liệu từ __NEXT_DATA__
                next_data = self._extract_next_data(html)
                d_api = next_data.get("props", {}).get("initialState", {}).get("api", {}) if next_data else {}
                job_detail = d_api.get("jobDetailHiddenContact", {}).get("data", {})

                soup = BeautifulSoup(html, "html.parser")

                # Bóc tách từng trường thông tin cụ thể
                title = clean_text(
                    job_detail.get("title")
                    or (soup.select_one("h1").get_text(strip=True) if soup.select_one("h1") else "Unknown")
                )

                comp_raw = (
                    job_detail.get("company_name")
                    or job_detail.get("user_display_name")
                    or job_detail.get("company", {})
                )
                if isinstance(comp_raw, dict):
                    company = clean_text(comp_raw.get("name") or comp_raw.get("display_name") or "") or "Unknown"
                else:
                    company = clean_text(str(comp_raw)) if comp_raw else "Unknown"

                salary_text = clean_text(job_detail.get("salary_text") or "Thoả thuận")
                salary_detail = parse_salary_detail(salary_text, title=title)

                desc_html = job_detail.get("description") or (
                    str(soup.select_one(".job-description")) if soup.select_one(".job-description") else f"<p>{title}</p>"
                )
                desc_text = strip_html_tags(desc_html)
                desc_list = text_to_clean_lines(desc_html or desc_text)

                req_html = job_detail.get("requirement") or ""
                req_text = strip_html_tags(req_html)
                req_list = text_to_clean_lines(req_html or req_text)

                ben_html = job_detail.get("benefit") or ""
                ben_text = strip_html_tags(ben_html)
                ben_list = text_to_clean_lines(ben_html or ben_text)

                loc_text = clean_text(job_detail.get("address") or "")
                deadline_text = clean_text(job_detail.get("expired_date") or "")
                seniority = clean_text(
                    job_detail.get("level", {}).get("name") if isinstance(job_detail.get("level"), dict) else ""
                )
                emp_type = clean_text(
                    job_detail.get("working_form", {}).get("name") if isinstance(job_detail.get("working_form"), dict) else ""
                )

                # Chuẩn hóa raw_data theo đúng định dạng yêu cầu
                raw_data = {
                    "title": title,
                    "company": company,
                    "salary": salary_detail,
                    "tags": {"requirements": None, "benefits": None, "skills": None},
                    "description_list": desc_list,
                    "requirements_list": req_list,
                    "benefits_list": ben_list,
                    "location_text": loc_text,
                    "deadline_text": deadline_text,
                    "posted_date_text": "",
                    "employment_type_text": emp_type,
                    "seniority_text": seniority,
                    "extra": job_detail,
                }

                extracted_jobs.append(raw_data)

                # Cập nhật UrlLedger
                self.ledger.mark_done(url_hash, content_hash=new_hash, new_version=new_ver)
                stats["success"] += 1
                count += 1

            except Exception as exc:
                log.error("[Vieclam24h] Lỗi cào %s: %s. Safe Skip.", url, exc)
                self.ledger.mark_failed(url_hash, error_message=str(exc))
                stats["failed"] += 1

        # Lưu danh sách công việc trích xuất được ra 1 file JSON tập trung
        if extracted_jobs:
            out_path = Path(self.output_dir)
            out_path.mkdir(parents=True, exist_ok=True)
            output_file = out_path / "batch_001.json"
            
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(extracted_jobs, f, ensure_ascii=False, indent=4)
            log.info("[Vieclam24h] Đã xuất thành công %d bản ghi ra file: %s", len(extracted_jobs), output_file)

        self.ledger.save_catalog()
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
    parser = argparse.ArgumentParser(description="Vieclam24h Job Crawler (UrlLedger & JobRecord)")
    parser.add_argument("--phase", type=str, choices=["all", "discovery", "details"], default="all", help="Pha cần chạy: discovery, details, all")
    parser.add_argument("--max-pages", type=int, default=None, help="Số trang danh mục tối đa cần quét ở Pha 1")
    parser.add_argument("--max-items", type=int, default=None, help="Số tin tối đa cần cào ở Pha 2")
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
        max_items=args.max_items,
    )

    if args.phase == "discovery":
        total = crawler.discover_urls(max_pages=args.max_pages)
        print(f"Pha 1 Discovery hoàn thành. Tổng số URL ghi nhận: {total}")
    elif args.phase == "details":
        stats = crawler.crawl_details(limit=args.max_items)
        print("Pha 2 Detail Extraction hoàn thành:", stats)
    else:
        crawler.discover_urls(max_pages=args.max_pages)
        stats = crawler.crawl_details(limit=args.max_items)
        print("Crawl hoàn tất:", stats)


if __name__ == "__main__":
    main()