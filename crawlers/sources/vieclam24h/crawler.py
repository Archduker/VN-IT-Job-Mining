# -*- coding: utf-8 -*-
"""Thu thập việc làm Vieclam24h qua Next.js SSR (__NEXT_DATA__) và HttpClient, xuất dữ liệu theo Data Contract chuẩn.

Hoàn toàn loại bỏ Selenium, hoạt động thuần HTTP nhanh chóng, ổn định và an toàn trên môi trường CI/Airflow.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from bs4 import BeautifulSoup
from pydantic import ValidationError

from crawlers.base.base_crawler import BaseCrawler
from crawlers.common.http_client import DelayConfig, HttpClient, RetryConfig
from crawlers.common.schema import JobMetadata, JobRaw, JobRecord, JobSalary, JobTags
from crawlers.common.utils import (
    clean_text,
    detect_language,
    text_to_clean_lines,
)

SITE_BASE_URL = "https://vieclam24h.vn"
DEFAULT_OUTPUT = Path(__file__).resolve().with_name("vieclam24h_jobs.json")
CRAWLER_VERSION = "0.3.0"
LOCAL_TIMEZONE = timezone(timedelta(hours=7))

# Các danh mục IT mục tiêu trên Vieclam24h
TARGET_CATEGORIES = [
    {"name": "IT Phần mềm", "path": "/viec-lam-it-phan-mem-o8.html"},
    {"name": "IT Phần cứng - Mạng", "path": "/viec-lam-it-phan-cung-mang-o7.html"},
]

log = logging.getLogger("vieclam24h.crawler")


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


def _extract_next_data(html: str) -> dict[str, Any] | None:
    """Trích xuất state JSON từ thẻ script __NEXT_DATA__."""
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    if script and script.string:
        try:
            return json.loads(script.string)
        except Exception as exc:
            log.warning("Không giải mã được __NEXT_DATA__: %s", exc)
    return None


def _make_record(
    job_detail: dict[str, Any],
    fallback_url: str,
    *,
    batch_id: str,
    crawled_at: datetime,
) -> JobRecord:
    job_id = str(job_detail.get("id", ""))
    title = _clean_text(job_detail.get("title"))
    employer = job_detail.get("employer_info", {})
    company = _clean_text(employer.get("name") if isinstance(employer, dict) else None)

    if not title or not company:
        raise ViecLam24hAPIError("Bản ghi thiếu tiêu đề hoặc tên công ty.")

    title_slug = job_detail.get("title_slug", "")
    job_url = fallback_url or f"{SITE_BASE_URL}/{title_slug}-id{job_id}.html"

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
        crawled_at=crawled_at,
        batch_id=batch_id,
        crawler_version=CRAWLER_VERSION,
        language=language,
    )
    return JobRecord(_meta=meta, raw=JobRaw(**raw_values))


class ViecLam24hCrawler(BaseCrawler):
    """Crawler thuần HTTP cho Vieclam24h dựa trên Next.js SSR (__NEXT_DATA__)."""

    source_name = "vieclam24h"
    crawler_version = CRAWLER_VERSION

    def __init__(
        self,
        checkpoint_dir: str | None = None,
        output_dir: str | Path | None = None,
        max_items: int | None = None,
        max_pages: int | None = None,
        checkpoint_interval: int = 10,
        local_json_file: str | Path | None = None,
    ) -> None:
        super().__init__(
            checkpoint_dir=checkpoint_dir,
            output_dir=str(output_dir) if output_dir is not None else None,
            max_items=max_items,
            checkpoint_interval=checkpoint_interval,
        )
        self.max_pages = max_pages or 5
        self.local_json_file = Path(local_json_file) if local_json_file else None
        self.client = HttpClient(
            source=self.source_name,
            delay_config=DelayConfig(min_seconds=0.5, max_seconds=1.5),
            retry_config=RetryConfig(max_retries=3, backoff_factor=1.0),
        )

    def _fetch_page_next_data(self, url: str) -> dict[str, Any] | None:
        """Tải mã HTML của một URL và bóc tách __NEXT_DATA__."""
        try:
            resp = self.client.get(url)
            return _extract_next_data(resp.text)
        except Exception as exc:
            log.warning("Lỗi tải trang %s: %s", url, exc)
            return None

    def fetch_items(self) -> Generator[dict[str, Any], None, None]:
        """Duyệt listing qua các danh mục IT và tải detail từng tin tuyển dụng."""
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

        collected_count = 0
        seen_ids: set[str] = set()

        for category in TARGET_CATEGORIES:
            cat_name = category["name"]
            cat_path = category["path"]
            log.info("[Vieclam24h] Bắt đầu quét ngành: %s (%s)", cat_name, cat_path)

            for page_idx in range(1, self.max_pages + 1):
                if self.max_items is not None and collected_count >= self.max_items:
                    return

                page_url = f"{SITE_BASE_URL}{cat_path}?page={page_idx}" if page_idx > 1 else f"{SITE_BASE_URL}{cat_path}"
                log.info("[Vieclam24h] Đang tải danh sách trang %d: %s", page_idx, page_url)

                try:
                    resp = self.client.get(page_url)
                    html = resp.text
                except Exception as exc:
                    log.warning("[Vieclam24h] Lỗi tải trang listing %s: %s", page_url, exc)
                    break

                soup = BeautifulSoup(html, "html.parser")
                next_data = _extract_next_data(html)
                if not next_data:
                    log.warning("[Vieclam24h] Không tìm thấy __NEXT_DATA__ tại trang %s", page_url)
                    break

                # Trích xuất danh sách link thẻ a từ DOM HTML
                detail_links_map: dict[str, str] = {}
                for a in soup.find_all("a"):
                    href = a.get("href", "")
                    clean_href = href.split("?")[0]
                    if "-c" in clean_href and "id" in clean_href and clean_href.endswith(".html"):
                        m = re.search(r"id(\d+)\.html", clean_href)
                        if m:
                            jid = m.group(1)
                            detail_links_map[jid] = urljoin(SITE_BASE_URL, clean_href)

                api_state = next_data.get("props", {}).get("initialState", {}).get("api", {})
                listing_items = api_state.get("getJobList", {}).get("data", {}).get("items", [])
                if not listing_items:
                    log.info("[Vieclam24h] Hết tin tại trang %d ngành %s", page_idx, cat_name)
                    break

                for item_summary in listing_items:
                    if self.max_items is not None and collected_count >= self.max_items:
                        return

                    jid = str(item_summary.get("id", ""))
                    if not jid or jid in seen_ids or self.checkpoint.is_seen(jid):
                        continue
                    seen_ids.add(jid)

                    # Tìm URL chi tiết
                    detail_url = detail_links_map.get(jid)
                    title_slug = item_summary.get("title_slug", "")
                    if not detail_url and title_slug:
                        detail_url = f"{SITE_BASE_URL}/{title_slug}-id{jid}.html"

                    job_detail = None
                    if detail_url:
                        try:
                            detail_next_data = self._fetch_page_next_data(detail_url)
                            if detail_next_data:
                                d_api = detail_next_data.get("props", {}).get("initialState", {}).get("api", {})
                                job_detail = d_api.get("jobDetailHiddenContact", {}).get("data", {})
                        except Exception as exc:
                            log.warning("[Vieclam24h] Không tải được detail %s: %s", detail_url, exc)

                    # Fallback dùng thông tin tóm tắt từ listing nếu detail page bị chặn hoặc rỗng
                    if not job_detail:
                        job_detail = item_summary

                    collected_count += 1
                    yield {"job_detail": job_detail, "url": detail_url or ""}

    def parse_item(self, item: dict[str, Any]) -> JobRecord | None:
        try:
            if not isinstance(item, dict):
                return None
            job_detail = item.get("job_detail") if isinstance(item.get("job_detail"), dict) else item
            url = item.get("url", "") if isinstance(item.get("url"), str) else ""

            return _make_record(
                job_detail,
                url,
                batch_id=self.batch_id,
                crawled_at=datetime.now(LOCAL_TIMEZONE),
            )
        except (ViecLam24hAPIError, ValueError, ValidationError) as exc:
            log.warning("Bỏ qua job không hợp lệ: %s", exc)
            self.skipped_count += 1
            return None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crawl việc làm Vieclam24h thuần HTTP theo chuẩn dự án.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-pages", type=int, default=5, help="Giới hạn số trang cần crawl.")
    parser.add_argument("--max-jobs", type=int, help="Giới hạn số lượng tin tuyển dụng.")
    parser.add_argument("--local-json-file", type=Path, help="Đường dẫn file JSON mẫu để chạy offline.")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    crawler = ViecLam24hCrawler(
        output_dir=args.output.parent,
        max_items=args.max_jobs,
        max_pages=args.max_pages,
        local_json_file=args.local_json_file,
    )

    try:
        stats = crawler.run()
        print(f"Vieclam24h: Hoàn tất thu thập. Thống kê: {stats}")
    except Exception as exc:
        log.error("Lỗi khi chạy crawler: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())