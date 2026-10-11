# -*- coding: utf-8 -*-
"""Thu thập việc làm TopDev qua API v2, gồm dữ liệu danh sách và chi tiết."""

from __future__ import annotations

import argparse
import getpass
import json
import logging
import os
import re
import sys
import tempfile
import time
import unicodedata
from collections.abc import Generator
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from bs4 import BeautifulSoup
import requests
from pydantic import ValidationError
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from crawlers.base.base_crawler import BaseCrawler
from crawlers.common.http_client import DelayConfig, HttpClient
from crawlers.common.schema import JobMetadata, JobRaw, JobRecord, JobSalary, JobTags
from crawlers.common.utils import (
    detect_language,
    parse_salary_detail,
    text_to_clean_lines,
)

API_BASE_URL = "https://api.topdev.vn/td/v2"
LISTING_URL = f"{API_BASE_URL}/jobs"
DETAIL_URL = f"{API_BASE_URL}/jobs/{{job_id}}"
SITE_BASE_URL = "https://topdev.vn"
DEFAULT_OUTPUT = Path(__file__).resolve().with_name("job_list.json")
CRAWLER_VERSION = "0.1.0"
PAGE_SIZE = 100
REQUEST_ATTEMPTS = 3
JOB_CATEGORY_IDS = (
    1,  #IT
    14, #Business, Finance
    27, #Management
    33, #Manufacturing & Engineering
    50, #Service
    61, #Design, Creativity
)
LOCAL_TIMEZONE = timezone(timedelta(hours=7))

LISTING_FIELDS = ",".join(
    (
        "id",
        "slug",
        "title",
        "salary",
        "company",
        "skills_str",
        "skills_arr",
        "job_types_str",
        "job_levels_str",
        "job_levels_arr",
        "experiences_str",
        "contract_types_str",
        "addresses",
        "detail_url",
        "published",
        "is_salary_visible",
    )
)
DETAIL_FIELDS = ",".join(
    (
        "content",
        "requirements_arr",
        "requirements_original",
        "benefits_v2",
        "benefits_original",
        "recruitment_process_original",
        "valid_through",
    )
)
COMPANY_FIELDS = "display_name"
VISIBLE_EXTRA_FIELDS = {"experience", "job_type", "recruitment_process"}
VISIBLE_RAW_FIELDS = {
    "title",
    "company",
    "description_list",
    "salary",
    "tags",
    "requirements_list",
    "benefits_list",
    "location_text",
    "deadline_text",
    "posted_date_text",
    "employment_type_text",
    "seniority_text",
    "extra",
}
log = logging.getLogger("topdev.api_crawler")


class TopDevAPIError(RuntimeError):
    """Lỗi API hoặc dữ liệu phản hồi không phù hợp, cần dừng an toàn."""


@dataclass
class CrawlStats:
    pages_processed: int = 0
    pages_failed: int = 0
    jobs_collected: int = 0
    detail_requests: int = 0
    detail_failures: int = 0
    duplicate_jobs: int = 0
    skipped_jobs: int = 0
    failed: bool = False
    stop_reason: str = ""
    records: list[dict[str, Any]] = field(default_factory=list)


def _build_session(*, prompt_for_cookie: bool = False) -> requests.Session:
    """Tạo HTTP session với retry giới hạn cho lỗi kết nối và HTTP tạm thời."""
    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/json",
            "Accept-Language": "vi,en;q=0.8",
            "Origin": SITE_BASE_URL,
            "Referer": f"{SITE_BASE_URL}/jobs/search",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        }
    )
    cookie_header = _cookie_header_from_environment(
        prompt_if_missing=prompt_for_cookie
    )
    if cookie_header:
        session.headers["Cookie"] = cookie_header
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def _cookie_header_from_environment(
    *,
    prompt_if_missing: bool = False,
) -> str | None:
    """Đọc hoặc hỏi cookie ẩn trong terminal; không ghi nó vào log/file."""
    cookie_header = os.environ.get("TOPDEV_COOKIE", "").strip()
    already_prompted = os.environ.get("TOPDEV_COOKIE_PROMPTED") == "1"
    if (
        not cookie_header
        and prompt_if_missing
        and not already_prompted
        and sys.stdin.isatty()
    ):
        cookie_header = getpass.getpass(
            "Nhập Cookie header TopDev (Enter để chạy không cookie): "
        ).strip()
    if not cookie_header:
        return None
    if "\r" in cookie_header or "\n" in cookie_header:
        raise ValueError("TOPDEV_COOKIE không được chứa ký tự xuống dòng.")
    if cookie_header.lower().startswith("cookie:"):
        cookie_header = cookie_header.split(":", 1)[1].strip()
    return cookie_header or None


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def _text_identity(value: str) -> str:
    """Tạo khóa so sánh bỏ khác biệt hoa/thường, dấu câu và khoảng trắng."""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[^\w]+", "", normalized, flags=re.UNICODE)


def _deduplicate_texts(values: list[str]) -> list[str]:
    """Bỏ dòng trùng sau khi chuẩn hóa hình thức, giữ nguyên cách viết đầu tiên."""
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _clean_text(value)
        if not text:
            continue
        identity = _text_identity(text)
        if identity and identity not in seen:
            result.append(text)
            seen.add(identity)
    return result


def _url_identity(value: Any) -> str | None:
    url = _clean_text(value)
    if not url:
        return None
    parsed = urlsplit(url)
    if not parsed.netloc or not parsed.path:
        return None
    return f"{parsed.netloc.lower()}{parsed.path.rstrip('/')}"


def _normalized_job_url(job: dict[str, Any]) -> str:
    """Tạo URL bài đăng ổn định từ slug và ID trả về bởi API."""
    job_id = _clean_text(job.get("id"))
    slug = _clean_text(job.get("slug"))
    detail_url = _clean_text(job.get("detail_url"))
    if not job_id:
        raise TopDevAPIError("Tin API thiếu id.")

    if detail_url:
        path = urlsplit(detail_url).path.rstrip("/")
        slug_from_url = path.rsplit("/", 1)[-1]
        if slug_from_url:
            slug = re.sub(rf"-{re.escape(job_id)}$", "", slug_from_url)
    if not slug:
        raise TopDevAPIError(f"Tin {job_id} thiếu slug/detail_url.")

    slug = re.sub(rf"-{re.escape(job_id)}$", "", slug)
    return f"{SITE_BASE_URL}/detail-jobs/{slug}-{job_id}"


def _api_request(
    session: requests.Session,
    url: str,
    *,
    params: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
    """Gửi GET tới API; không ghi body hay thông tin phiên vào log."""
    try:
        if isinstance(session, HttpClient):
            response = session.get(url, params=params)
        else:
            response = session.get(url, params=params, timeout=timeout)
    except requests.RequestException as exc:
        raise TopDevAPIError(
            f"Request API thất bại ({type(exc).__name__}) tại {urlsplit(url).path}."
        ) from exc

    if response.status_code >= 400:
        raise TopDevAPIError(
            f"TopDev API trả HTTP {response.status_code} tại {urlsplit(response.url).path}."
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise TopDevAPIError(
            f"API trả về nội dung không phải JSON tại {urlsplit(response.url).path}."
        ) from exc
    if not isinstance(payload, dict):
        raise TopDevAPIError(
            f"API trả sai cấu trúc JSON tại {urlsplit(response.url).path}."
        )
    return payload


def _detail_html(detail: dict[str, Any], *keys: str) -> str:
    """Ghép các trường HTML tương đương, bỏ giá trị rỗng và trùng nhau."""
    values: list[str] = []
    for key in keys:
        value = detail.get(key)
        if isinstance(value, str) and value.strip() and value not in values:
            values.append(value)
    return "\n".join(values)


def _benefits_html(detail: dict[str, Any]) -> str:
    """Lấy HTML quyền lợi từ cả cấu trúc mới và trường legacy của API."""
    values: list[str] = []
    for key in ("benefits_v2", "benefits_original"):
        field_value = detail.get(key)
        if isinstance(field_value, str) and field_value.strip():
            values.append(field_value)
        elif isinstance(field_value, list):
            for item in field_value:
                if isinstance(item, dict):
                    html = item.get("description") or item.get("value")
                    if isinstance(html, str) and html.strip():
                        values.append(html)
                elif isinstance(item, str) and item.strip():
                    values.append(item)
    return "\n".join(dict.fromkeys(values))


def _requirements_html(detail: dict[str, Any]) -> str:
    """Lấy HTML yêu cầu từ các trường API có thể có."""
    values = [
        detail.get("requirements_original"),
        detail.get("requirements"),
    ]
    return "\n".join(
        value for value in values if isinstance(value, str) and value.strip()
    )


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str):
            text = _clean_text(item)
        elif isinstance(item, dict):
            text = _clean_text(
                item.get("text")
                or item.get("name")
                or item.get("name_vi")
                or item.get("name_en")
                or item.get("skill_name")
                or item.get("skillName")
                or item.get("title")
                or item.get("value")
            )
        else:
            text = None
        if text:
            result.append(text)
    return _deduplicate_texts(result)


def _list_text(values: list[str]) -> str | None:
    return ", ".join(values) if values else None


def _as_bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes"}:
            return True
        if normalized in {"0", "false", "no"}:
            return False
    return None


def _reported_page_count(meta: dict[str, Any], page_size: int) -> int:
    """Ước lượng đủ số trang từ cả last_page và tổng số tin API công bố."""
    candidates: list[int] = []
    last_page = meta.get("last_page")
    if isinstance(last_page, int) and not isinstance(last_page, bool) and last_page >= 0:
        candidates.append(last_page)

    total = meta.get("total")
    if isinstance(total, int) and not isinstance(total, bool) and total >= 0:
        candidates.append((total + page_size - 1) // page_size)

    if not candidates:
        raise TopDevAPIError("API không trả last_page hoặc total hợp lệ.")
    return max(candidates)


def _parse_salary_amount(value: str, currency: Any) -> float | None:
    text = re.sub(r"\s+", "", value).strip()
    if not text or "*" in text:
        return None

    suffix = ""
    suffix_match = re.search(r"(triệu|tr|million|m|k)$", text, re.IGNORECASE)
    if suffix_match:
        suffix = suffix_match.group(1).casefold()
        text = text[: suffix_match.start()]

    if "," in text and "." in text:
        decimal_separator = "," if text.rfind(",") > text.rfind(".") else "."
        thousands_separator = "." if decimal_separator == "," else ","
        decimal_part = text.rsplit(decimal_separator, 1)[1]
        if len(decimal_part) == 3:
            text = text.replace(",", "").replace(".", "")
        else:
            text = text.replace(thousands_separator, "").replace(decimal_separator, ".")
    elif "," in text or "." in text:
        separator = "," if "," in text else "."
        groups = text.split(separator)
        if len(groups) > 1 and all(len(group) == 3 for group in groups[1:]):
            text = "".join(groups)
        elif len(groups) == 2 and len(groups[1]) == 3 and len(groups[0]) <= 3:
            text = "".join(groups)
        else:
            text = separator.join(groups[:-1]) + "." + groups[-1]

    try:
        amount = float(text)
    except ValueError:
        return None

    if suffix in {"triệu", "tr", "million", "m"}:
        return amount
    if suffix == "k":
        amount *= 1_000
    if _clean_text(currency) and _clean_text(currency).upper() == "VND":
        if abs(amount) >= 1_000_000:
            amount /= 1_000_000
    return amount


def _salary_text_amounts(
    salary_text: str | None,
    currency: Any,
) -> tuple[float | None, float | None]:
    if not salary_text or re.search(r"\*+", salary_text):
        return None, None
    tokens = re.findall(r"(?<![\w])\d+(?:[.,]\d+)*(?:\s*(?:triệu|tr|million|m|k))?", salary_text, re.IGNORECASE)
    amounts = [
        amount
        for token in tokens
        if (amount := _parse_salary_amount(token, currency)) is not None
    ]
    if not amounts:
        return None, None

    lower_text = salary_text.casefold()
    is_max_only = any(term in lower_text for term in ("up to", "upto", "lên đến", "tới"))
    is_min_only = any(term in lower_text for term in ("từ", "from", "trên"))
    is_range = (
        len(amounts) >= 2
        and not is_max_only
        and not is_min_only
        and bool(re.search(r"(?:-|–|—|\bto\b|\bđến\b)", lower_text))
    )
    if is_range:
        return amounts[0], amounts[1]
    if is_max_only:
        return None, amounts[-1]
    if is_min_only:
        return amounts[0], None
    if len(amounts) >= 2:
        return amounts[0], amounts[1]
    return amounts[0], amounts[0]


def _salary_number(value: Any, currency: Any) -> float | None:
    if value is None:
        return None
    text = _clean_text(value)
    return _parse_salary_amount(text, currency) if text else None


def _benefit_list(detail: dict[str, Any], benefits_html: str) -> list[str]:
    benefits = text_to_clean_lines(benefits_html)
    if not benefits:
        benefits = _string_list(detail.get("benefits_v2"))
    return _deduplicate_texts(benefits)


def _description_summary(
    content_html: str,
    *,
    exclude_texts: tuple[str | None, ...] = (),
) -> list[str]:
    """Lấy phần giới thiệu trong box nội dung trước khi bắt đầu các mục chi tiết."""
    headings = {
        _text_identity(value)
        for value in (
            "description",
            "job description",
            "about the role",
            "mô tả công việc",
            "mô tả",
        )
    }
    metadata_prefixes = tuple(
        _text_identity(value)
        for value in (
            "địa điểm làm việc",
            "thời gian làm việc",
            "vị trí tuyển dụng",
            "đơn vị tuyển dụng",
            "số lượng tuyển dụng",
            "thu nhập",
            "mức lương",
            "hạn nộp hồ sơ",
            "work location",
            "working time",
            "job title",
            "company",
            "salary",
        )
    )
    repeated_texts = {
        _text_identity(text)
        for text in exclude_texts
        if text
    }

    def is_summary(text: str) -> bool:
        identity = _text_identity(text)
        return (
            bool(identity)
            and identity not in headings
            and identity not in repeated_texts
            and not any(identity.startswith(prefix) for prefix in metadata_prefixes)
        )

    soup = BeautifulSoup(content_html, "html.parser")
    role_heading = re.compile(
        r"your\s+role\s*(?:&|and)\s*responsibilities",
        flags=re.IGNORECASE,
    )
    for container in soup.select(".border-text-200"):
        intro = container.select_one(".text-text-600")
        if intro is None:
            continue

        result: list[str] = []
        for paragraph in intro.find_all("p"):
            text = _clean_text(paragraph.get_text(" ", strip=True))
            if not text:
                continue
            if role_heading.search(text):
                break
            result.append(text)
        if result:
            return result

    paragraphs = re.findall(
        r"<p\b[^>]*>(.*?)</p\s*>",
        content_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    for paragraph in paragraphs:
        lines = text_to_clean_lines(paragraph)
        text = _clean_text(" ".join(lines))
        if text and is_summary(text):
            return [text]

    lines = text_to_clean_lines(content_html)
    for line in lines:
        if is_summary(line):
            return [line]
    return []


def _salary_text(detail: dict[str, Any]) -> str | None:
    salary = detail.get("salary")
    if not isinstance(salary, dict):
        return None
    value = _clean_text(salary.get("value"))
    if value:
        return value
    if str(salary.get("is_negotiable", "")).lower() in {"1", "true", "yes"}:
        return "Thương lượng"
    return None


def _salary_period(value: Any) -> str | None:
    period = _clean_text(value)
    if not period:
        return None
    normalized = period.casefold()
    for token, result in (
        ("month", "month"),
        ("monthly", "month"),
        ("tháng", "month"),
        ("year", "year"),
        ("annual", "year"),
        ("năm", "year"),
        ("day", "day"),
        ("daily", "day"),
        ("ngày", "day"),
        ("hour", "hour"),
        ("hourly", "hour"),
        ("giờ", "hour"),
    ):
        if token in normalized:
            return result
    return None


def _posted_date_text(detail: dict[str, Any]) -> str | None:
    published = detail.get("published")
    if isinstance(published, dict):
        relative = _clean_text(published.get("since"))
        if relative:
            return relative
        raw_date = _clean_text(published.get("date"))
        if raw_date:
            return _calendar_date_text(raw_date)
    return _date_value(detail, "published_at")


def _calendar_date_text(value: str) -> str:
    text = _clean_text(value)
    if not text:
        return value
    for date_format in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%H:%M:%S %d-%m-%Y"):
        try:
            return datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        pass
    return text


def _location_text(detail: dict[str, Any]) -> str | None:
    addresses = detail.get("addresses")
    if not isinstance(addresses, dict):
        return None
    return (
        _clean_text(addresses.get("address_short_region_list"))
        or _clean_text(addresses.get("address_region_list"))
        or _clean_text(addresses.get("sort_addresses"))
        or _list_text(_string_list(addresses.get("full_addresses")))
    )


def _date_value(detail: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = detail.get(key)
        if isinstance(value, dict):
            text = _clean_text(value.get("date") or value.get("datetime") or value.get("since"))
            if text:
                return _calendar_date_text(text)
        elif text := _clean_text(value):
            return _calendar_date_text(text)
    return None


def _make_record(
    listing_job: dict[str, Any],
    detail: dict[str, Any],
    *,
    batch_id: str,
    crawled_at: datetime,
) -> dict[str, Any]:
    """Ghép dữ liệu list/detail thành Data Contract của dự án."""
    job = {**listing_job, **detail}
    listing_salary = listing_job.get("salary")
    if not isinstance(job.get("salary"), dict) and isinstance(listing_salary, dict):
        job["salary"] = listing_salary
    if job.get("is_salary_visible") is None:
        job["is_salary_visible"] = listing_job.get("is_salary_visible")
    job_id = _clean_text(job.get("id"))
    title = _clean_text(job.get("title"))
    company_info = job.get("company")
    if not isinstance(company_info, dict):
        company_info = {}
    company = _clean_text(company_info.get("display_name") or company_info.get("name"))
    if not job_id or not title or not company:
        raise TopDevAPIError("Bản ghi API thiếu id, title hoặc tên công ty.")

    job_url = _normalized_job_url(job)
    content_html = _detail_html(job, "content")
    requirements_html = _requirements_html(job)
    benefits_html = _benefits_html(job)
    recruitment_process_html = _detail_html(job, "recruitment_process_original")
    description_list = _description_summary(
        content_html,
        exclude_texts=(title, company),
    )
    requirements_list = _deduplicate_texts(text_to_clean_lines(requirements_html))
    if not requirements_list:
        requirements_list = _deduplicate_texts(_string_list(job.get("requirements_arr")))
    benefits_list = _benefit_list(job, benefits_html)
    seen_section_lines = {
        _text_identity(line) for line in description_list
    }
    requirements_list = [
        line
        for line in requirements_list
        if _text_identity(line) not in seen_section_lines
    ]
    seen_section_lines.update(_text_identity(line) for line in requirements_list)
    benefits_list = [
        line for line in benefits_list if _text_identity(line) not in seen_section_lines
    ]
    skills = _string_list(job.get("skills_arr") or job.get("skills"))
    if not skills:
        skills_str = _clean_text(job.get("skills_str"))
        skills = [part.strip() for part in re.split(r"[,;|]", skills_str or "") if part.strip()]

    salary_api = job.get("salary") if isinstance(job.get("salary"), dict) else {}
    salary_text = _salary_text(job)
    salary_visible = _as_bool_or_none(job.get("is_salary_visible"))
    salary = None
    if salary_text or (salary_visible is True and salary_api):
        salary_fields = parse_salary_detail(salary_text, title=title) if salary_text else {}
        salary_is_masked = bool(salary_text and re.search(r"\*+", salary_text))
        salary_min = salary_fields.get("salary_min")
        salary_max = salary_fields.get("salary_max")
        if salary_is_masked:
            salary_min = None
            salary_max = None
        elif salary_text:
            text_min, text_max = _salary_text_amounts(
                salary_text,
                salary_fields.get("salary_currency") or salary_api.get("currency"),
            )
            if text_min is not None or text_max is not None:
                salary_min, salary_max = text_min, text_max
        if not salary_is_masked and salary_visible is True:
            if salary_min is None:
                salary_min = _salary_number(salary_api.get("min"), salary_api.get("currency"))
            if salary_max is None:
                salary_max = _salary_number(salary_api.get("max"), salary_api.get("currency"))

        api_negotiable = _as_bool_or_none(salary_api.get("is_negotiable"))
        salary = JobSalary(
            salary_text=salary_text,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=(
                salary_fields.get("salary_currency")
                or _clean_text(salary_api.get("currency"))
            ),
            pay_period=(
                salary_fields.get("pay_period")
                or _salary_period(salary_api.get("unit"))
            ),
            is_negotiable=(
                api_negotiable
                if api_negotiable is not None
                else bool(salary_fields.get("is_negotiable", False))
            ),
            has_commission=bool(salary_fields.get("has_commission", False)),
        )

    tags = JobTags(
        requirements=None,
        benefits=None,
        skills=skills or None,
    )
    raw_text = " ".join(value for value in (title, company, *description_list) if value)
    language = detect_language(raw_text)

    raw_values = dict(
        title=title,
        company=company,
        description_list=description_list or None,
        salary=salary,
        tags=tags,
        requirements_list=requirements_list,
        benefits_list=benefits_list,
        location_text=_location_text(job),
        deadline_text=_date_value(job, "valid_through", "validThrough", "deadline"),
        posted_date_text=_posted_date_text(job),
        employment_type_text=_clean_text(job.get("contract_types_str")),
        seniority_text=(
            _clean_text(job.get("job_levels_str"))
            or _list_text(
                _string_list(job.get("job_levels_arr") or job.get("levels"))
            )
            or _clean_text(job.get("levels"))
        ),
        extra={
            "experience": _clean_text(job.get("experiences_str")),
            "job_type": _clean_text(job.get("job_types_str")),
            "recruitment_process": (
                _deduplicate_texts(text_to_clean_lines(recruitment_process_html))
                or None
            ),
        },
    )
    meta = JobMetadata(
        source="topdev",
        source_job_id=job_id,
        url=job_url,
        dedup_key=f"topdev:{job_id}",
        crawled_at=crawled_at,
        batch_id=batch_id,
        crawler_version=CRAWLER_VERSION,
        language=language,
    )
    if description_list:
        record = JobRecord(_meta=meta, raw=JobRaw(**raw_values))
    else:
        # Shared schema requires a description; keep source records in TopDev output without inventing one.
        raw = JobRaw.model_construct(**raw_values)
        record = JobRecord.model_construct(_meta=meta, raw=raw)
    return record.to_jsonl_dict()


def _load_existing(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TopDevAPIError(
            f"Không đọc được JSON hiện có tại {path}; không ghi đè file."
        ) from exc
    if not isinstance(existing, list):
        raise TopDevAPIError(
            f"JSON hiện có tại {path} không phải array; không ghi đè file."
        )

    records: dict[str, dict[str, Any]] = {}
    seen_urls: set[str] = set()
    for record in existing:
        if not isinstance(record, dict):
            raise TopDevAPIError(
                f"JSON hiện có tại {path} chứa record không hợp lệ; không ghi đè file."
            )
        meta = record.get("_meta")
        if (
            not isinstance(meta, dict)
            or not meta.get("source_job_id")
            or meta.get("source") != "topdev"
        ):
            raise TopDevAPIError(
                f"JSON hiện có tại {path} không phải dữ liệu TopDev hợp lệ; "
                "không ghi đè file."
            )
        source_job_id = str(meta["source_job_id"])
        projected = _omit_unrequested_fields(record)
        job_url_key = _url_identity(meta.get("url"))
        if source_job_id in records or (job_url_key and job_url_key in seen_urls):
            continue
        records[source_job_id] = projected
        if job_url_key:
            seen_urls.add(job_url_key)
    return records


def _omit_unrequested_fields(record: dict[str, Any]) -> dict[str, Any]:
    """Chỉ giữ các trường hiển thị trên trang tuyển dụng."""
    result = dict(record)
    raw = result.get("raw")
    if isinstance(raw, dict):
        raw = {key: value for key, value in raw.items() if key in VISIBLE_RAW_FIELDS}
        salary = raw.get("salary")
        if isinstance(salary, dict):
            allowed_salary_fields = {
                "salary_text",
                "salary_min",
                "salary_max",
                "salary_currency",
                "pay_period",
                "is_negotiable",
                "has_commission",
            }
            salary = {
                key: value
                for key, value in salary.items()
                if key in allowed_salary_fields
            }
            salary_text = _clean_text(salary.get("salary_text"))
            if salary_text and re.search(r"\*+", salary_text):
                salary["salary_min"] = None
                salary["salary_max"] = None
            raw["salary"] = salary
        for key in ("description_list", "requirements_list", "benefits_list"):
            if isinstance(raw.get(key), list):
                raw[key] = _deduplicate_texts(raw[key])
        tags = raw.get("tags")
        if isinstance(tags, dict):
            raw["tags"] = {
                key: _deduplicate_texts(value) if isinstance(value, list) else value
                for key, value in tags.items()
                if key in {"requirements", "benefits", "skills"}
            }
        extra = raw.get("extra")
        if isinstance(extra, dict):
            raw["extra"] = {
                key: value if value not in ("", []) else None
                for key, value in extra.items()
                if key in VISIBLE_EXTRA_FIELDS
            }
        result["raw"] = raw
    return result


def _atomic_write(path: Path, records: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_name = temp_file.name
            json.dump(list(records.values()), temp_file, ensure_ascii=False, indent=2)
            temp_file.write("\n")
            temp_file.flush()
            os.fsync(temp_file.fileno())
        for attempt in range(3):
            try:
                os.replace(temp_name, path)
                break
            except PermissionError:
                if attempt == 2:
                    raise
                time.sleep(0.2 * (attempt + 1))
    except PermissionError as exc:
        raise TopDevAPIError(
            f"Windows không thể thay thế file JSON '{path}' (WinError "
            f"{getattr(exc, 'winerror', None) or exc.errno}). File đích có thể "
            "đang được ứng dụng khác giữ mở hoặc thiếu quyền đổi tên/xóa. "
            "Đóng ứng dụng đang dùng file rồi thử lại, hoặc chọn đường dẫn "
            "khác bằng --output. File hiện có được giữ nguyên."
        ) from exc
    except OSError as exc:
        raise TopDevAPIError(f"Không thể ghi JSON an toàn tại {path}: {exc}") from exc
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


class TopDevAPICrawler:
    """Duyệt API phân trang và lấy chi tiết để xuất Data Contract JSON."""

    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        timeout: float = 25.0,
        delay: float = 0.5,
        page_size: int = PAGE_SIZE,
        locale: str = "vi_VN",
        keyword: str | None = None,
        sleeper: Any = time.sleep,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout phải lớn hơn 0.")
        if delay < 0:
            raise ValueError("delay không được âm.")
        if not 1 <= page_size <= PAGE_SIZE:
            raise ValueError(f"page_size phải nằm trong khoảng 1..{PAGE_SIZE}.")
        self.session = session or _build_session(prompt_for_cookie=True)
        self.timeout = timeout
        self.delay = delay
        self.page_size = page_size
        self.locale = locale
        self.keyword = keyword
        self.sleeper = sleeper

    def _fetch_listing(self, page: int) -> dict[str, Any]:
        params: dict[str, Any] = {
            "page": page,
            "page_size": self.page_size,
            "job_categories_ids": ",".join(map(str, JOB_CATEGORY_IDS)),
            "locale": self.locale,
            "fields[job]": LISTING_FIELDS,
        }
        if self.keyword:
            params["keyword"] = self.keyword
        payload = _api_request(self.session, LISTING_URL, params=params, timeout=self.timeout)
        data = payload.get("data")
        meta = payload.get("meta")
        if not isinstance(data, list) or not isinstance(meta, dict):
            raise TopDevAPIError(
                "API danh sách thiếu data[] hoặc meta; dừng vì cấu trúc phản hồi thay đổi."
            )
        return payload

    def _fetch_listing_with_retries(self, page: int) -> dict[str, Any]:
        last_error: TopDevAPIError | None = None
        for attempt in range(REQUEST_ATTEMPTS):
            try:
                payload = self._fetch_listing(page)
                meta = payload["meta"]
                if meta.get("current_page") != page:
                    raise TopDevAPIError(
                        f"API trả current_page={meta.get('current_page')!r} "
                        f"khi yêu cầu trang {page}."
                    )
                reported_pages = _reported_page_count(meta, self.page_size)
                if not payload["data"] and reported_pages >= page:
                    raise TopDevAPIError(
                        f"Trang {page} rỗng dù API báo còn {reported_pages} trang."
                    )
                return payload
            except TopDevAPIError as exc:
                last_error = exc
                if attempt + 1 < REQUEST_ATTEMPTS and self.delay:
                    self.sleeper(self.delay)

        assert last_error is not None
        raise last_error

    def _fetch_detail(self, job_id: str) -> dict[str, Any]:
        params = {
            "locale": self.locale,
            "fields[job]": DETAIL_FIELDS,
            "fields[company]": COMPANY_FIELDS,
        }
        payload = _api_request(
            self.session,
            DETAIL_URL.format(job_id=job_id),
            params=params,
            timeout=self.timeout,
        )
        detail = payload.get("data")
        if not isinstance(detail, dict):
            raise TopDevAPIError(f"API chi tiết job {job_id} thiếu data object.")
        return detail

    def _fetch_detail_with_retries(self, job_id: str) -> dict[str, Any]:
        last_error: TopDevAPIError | None = None
        for attempt in range(REQUEST_ATTEMPTS):
            try:
                return self._fetch_detail(job_id)
            except TopDevAPIError as exc:
                last_error = exc
                if attempt + 1 < REQUEST_ATTEMPTS and self.delay:
                    self.sleeper(self.delay)

        assert last_error is not None
        raise last_error

    def crawl(
        self,
        *,
        output_path: Path = DEFAULT_OUTPUT,
        max_pages: int | None = None,
        max_jobs: int | None = None,
    ) -> CrawlStats:
        if max_pages is not None and max_pages < 1:
            raise ValueError("max_pages phải lớn hơn 0.")
        if max_jobs is not None and max_jobs < 1:
            raise ValueError("max_jobs phải lớn hơn 0.")

        output_path = Path(output_path)
        all_records = _load_existing(output_path)
        stats = CrawlStats()
        current_batch_time = datetime.now(LOCAL_TIMEZONE)
        batch_id = f"{current_batch_time:%Y-%m-%d}_topdev_001"
        seen_ids: set[str] = set()
        seen_urls: set[str] = set()
        known_urls = {
            url_key: job_id
            for job_id, record in all_records.items()
            if (url_key := _url_identity(record.get("_meta", {}).get("url")))
        }

        try:
            first_payload = self._fetch_listing_with_retries(1)
            last_page = _reported_page_count(first_payload["meta"], self.page_size)
            if last_page == 0:
                stats.stop_reason = "API không có kết quả."

            page = 1
            payload = first_payload
            while page <= last_page:
                if max_pages is not None and stats.pages_processed >= max_pages:
                    stats.stop_reason = f"Đã đạt giới hạn --max-pages={max_pages}."
                    break
                if page > 1:
                    if self.delay:
                        self.sleeper(self.delay)
                    try:
                        payload = self._fetch_listing_with_retries(page)
                    except TopDevAPIError as exc:
                        stats.failed = True
                        stats.pages_failed += 1
                        log.error("Bỏ qua trang %d sau lỗi API: %s", page, exc)
                        page += 1
                        continue

                meta = payload["meta"]
                actual_page = meta.get("current_page")
                if actual_page != page:
                    stats.failed = True
                    stats.pages_failed += 1
                    log.error(
                        "Bỏ qua trang %d: API trả current_page=%r.",
                        page,
                        actual_page,
                    )
                    page += 1
                    continue
                response_last_page = _reported_page_count(meta, self.page_size)
                if response_last_page >= page:
                    last_page = max(last_page, response_last_page)
                page_jobs = payload["data"]
                if not page_jobs:
                    stats.failed = True
                    stats.pages_failed += 1
                    log.warning(
                        "Trang %d rỗng; tiếp tục các trang còn lại đến %d.",
                        page,
                        last_page,
                    )
                    page += 1
                    continue

                page_new = 0
                for listing_job in page_jobs:
                    if not isinstance(listing_job, dict):
                        stats.skipped_jobs += 1
                        continue
                    job_id = _clean_text(listing_job.get("id"))
                    if not job_id:
                        stats.skipped_jobs += 1
                        continue
                    if job_id in seen_ids:
                        stats.duplicate_jobs += 1
                        continue
                    seen_ids.add(job_id)

                    if max_jobs is not None and stats.jobs_collected >= max_jobs:
                        break
                    try:
                        listing_url_key = _url_identity(_normalized_job_url(listing_job))
                    except TopDevAPIError as exc:
                        log.warning("Bỏ qua job %s: %s", job_id, exc)
                        stats.skipped_jobs += 1
                        continue
                    if listing_url_key in seen_urls:
                        stats.duplicate_jobs += 1
                        continue
                    existing_id = known_urls.get(listing_url_key)
                    if existing_id is not None and existing_id != job_id:
                        stats.duplicate_jobs += 1
                        continue
                    if stats.detail_requests and self.delay:
                        self.sleeper(self.delay)
                    seen_urls.add(listing_url_key)

                    stats.detail_requests += 1
                    try:
                        detail = self._fetch_detail_with_retries(job_id)
                    except TopDevAPIError as exc:
                        stats.failed = True
                        stats.detail_failures += 1
                        log.warning(
                            "Không lấy được chi tiết job %s; giữ dữ liệu danh sách và "
                            "để trống các trường chi tiết: %s",
                            job_id,
                            exc,
                        )
                        detail = {}
                    try:
                        record = _omit_unrequested_fields(
                            _make_record(
                                listing_job,
                                detail,
                                batch_id=batch_id,
                                crawled_at=datetime.now(LOCAL_TIMEZONE),
                            )
                        )
                    except (TopDevAPIError, ValueError, ValidationError) as exc:
                        stats.failed = True
                        stats.skipped_jobs += 1
                        log.warning("Bỏ qua job %s, tiếp tục crawl: %s", job_id, exc)
                        continue

                    all_records[job_id] = record
                    known_urls[listing_url_key] = job_id
                    stats.records.append(record)
                    stats.jobs_collected += 1
                    page_new += 1

                stats.pages_processed += 1
                _atomic_write(output_path, all_records)
                log.info(
                    "Trang %d/%d: %d tin mới; trùng %d, bỏ qua %d.",
                    page,
                    last_page,
                    page_new,
                    stats.duplicate_jobs,
                    stats.skipped_jobs,
                )

                if max_jobs is not None and stats.jobs_collected >= max_jobs:
                    stats.stop_reason = f"Đã đạt giới hạn --max-jobs={max_jobs}."
                    break
                if page >= last_page:
                    stats.stop_reason = f"Đã xử lý đến trang cuối ({last_page})."
                    break
                page += 1
        except TopDevAPIError as exc:
            stats.failed = True
            stats.stop_reason = str(exc)
            log.error("%s", stats.stop_reason)

        if not stats.stop_reason:
            stats.stop_reason = f"Đã kết thúc đến trang {page}."
        if stats.pages_failed or stats.detail_failures or stats.skipped_jobs:
            stats.stop_reason += (
                f" Có {stats.pages_failed} trang lỗi và "
                f"{stats.detail_failures} lỗi chi tiết, "
                f"{stats.skipped_jobs} tin không thể nhận diện; crawler đã tiếp tục "
                "các trang còn lại."
            )
        stats.jobs_collected = len(stats.records)
        return stats


class TopDevCrawler(BaseCrawler):
    """Adapter dùng API TopDev bên trong pipeline chuẩn của repository."""

    source_name = "topdev"
    crawler_version = CRAWLER_VERSION

    def __init__(
        self,
        checkpoint_dir: str | None = None,
        output_dir: str | Path | None = None,
        max_items: int | None = None,
        checkpoint_interval: int = 10,
        http_client: HttpClient | None = None,
        timeout: float = 25.0,
        page_size: int = PAGE_SIZE,
        keyword: str | None = None,
    ) -> None:
        super().__init__(
            checkpoint_dir=checkpoint_dir,
            output_dir=str(output_dir) if output_dir is not None else None,
            max_items=max_items,
            checkpoint_interval=checkpoint_interval,
        )
        extra_headers = {
            "Accept": "application/json",
            "Origin": SITE_BASE_URL,
            "Referer": f"{SITE_BASE_URL}/jobs/search",
        }
        cookie_header = _cookie_header_from_environment()
        if cookie_header:
            extra_headers["Cookie"] = cookie_header
        self.http_client = http_client or HttpClient(
            source=self.source_name,
            timeout=int(timeout),
            delay_config=DelayConfig(min_seconds=1.5, max_seconds=3.0),
            extra_headers=extra_headers,
        )
        self.api_crawler = TopDevAPICrawler(
            session=self.http_client,
            timeout=timeout,
            delay=0,
            page_size=page_size,
            keyword=keyword,
        )

    def fetch_items(self) -> Generator[dict[str, Any], None, None]:
        """Yield từng job sau khi ghép response danh sách và API chi tiết."""
        page = 1
        yielded_ids: set[str] = set()
        yielded_urls: set[str] = set()
        attempted_count = 0
        try:
            payload = self.api_crawler._fetch_listing_with_retries(page)
        except TopDevAPIError as exc:
            self.error_count += 1
            log.error("Không lấy được trang đầu TopDev; không thể xác định số trang: %s", exc)
            return

        try:
            last_page = _reported_page_count(payload["meta"], self.api_crawler.page_size)
        except TopDevAPIError as exc:
            self.error_count += 1
            log.error("API không trả số trang hợp lệ; không thể phân trang: %s", exc)
            return

        while page <= last_page:
            if self.max_items is not None and attempted_count >= self.max_items:
                return
            if page > 1:
                try:
                    payload = self.api_crawler._fetch_listing_with_retries(page)
                except TopDevAPIError as exc:
                    self.error_count += 1
                    log.error("Bỏ qua trang %d sau lỗi API; tiếp tục: %s", page, exc)
                    page += 1
                    continue

            meta = payload["meta"]
            if meta.get("current_page") != page:
                self.error_count += 1
                log.error(
                    "Bỏ qua trang %d: API trả current_page=%r; tiếp tục.",
                    page,
                    meta.get("current_page"),
                )
                page += 1
                continue
            response_last_page = _reported_page_count(meta, self.api_crawler.page_size)
            if response_last_page >= page:
                last_page = max(last_page, response_last_page)
            page_jobs = payload["data"]
            if not page_jobs:
                self.error_count += 1
                log.warning("Trang %d rỗng; tiếp tục đến trang %d.", page, last_page)
                page += 1
                continue

            for listing_job in page_jobs:
                if self.max_items is not None and attempted_count >= self.max_items:
                    return
                if not isinstance(listing_job, dict):
                    self.skipped_count += 1
                    continue
                job_id = _clean_text(listing_job.get("id"))
                if not job_id:
                    self.skipped_count += 1
                    continue
                if job_id in yielded_ids:
                    continue
                yielded_ids.add(job_id)
                try:
                    url_key = _url_identity(_normalized_job_url(listing_job))
                except TopDevAPIError as exc:
                    self.skipped_count += 1
                    log.warning("Bỏ qua job %s: %s", job_id, exc)
                    continue
                if url_key in yielded_urls:
                    continue
                yielded_urls.add(url_key)
                attempted_count += 1

                try:
                    detail = self.api_crawler._fetch_detail_with_retries(job_id)
                except TopDevAPIError as exc:
                    self.error_count += 1
                    log.error(
                        "Không lấy được chi tiết job %s; giữ dữ liệu danh sách và "
                        "để trống các trường chi tiết: %s",
                        job_id,
                        exc,
                    )
                    detail = {}

                yield {**listing_job, **detail}
            page += 1

    def parse_item(self, item: dict[str, Any]) -> JobRecord | None:
        """Chuyển dữ liệu API đã ghép thành JobRecord chuẩn."""
        try:
            record = _make_record(
                item,
                item,
                batch_id=self.batch_id,
                crawled_at=datetime.now(LOCAL_TIMEZONE),
            )
            if record["raw"].get("description_list") is None:
                raw_data = dict(record["raw"])
                if isinstance(raw_data.get("salary"), dict):
                    raw_data["salary"] = JobSalary.model_validate(raw_data["salary"])
                if isinstance(raw_data.get("tags"), dict):
                    raw_data["tags"] = JobTags.model_validate(raw_data["tags"])
                return JobRecord.model_construct(
                    _meta=JobMetadata.model_validate(record["_meta"]),
                    raw=JobRaw.model_construct(**raw_data),
                )
            return JobRecord.model_validate(record)
        except (TopDevAPIError, ValueError, ValidationError) as exc:
            log.warning("Bỏ qua job không hợp lệ: %s", exc)
            return None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crawl danh sách và nội dung việc làm TopDev qua API v2."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-pages", type=int, help="Giới hạn trang để chạy thử.")
    parser.add_argument("--max-jobs", type=int, help="Giới hạn số tin để chạy thử.")
    parser.add_argument("--page-size", type=int, default=PAGE_SIZE)
    parser.add_argument("--keyword", help="Từ khóa tìm kiếm API, ví dụ Java hoặc Backend.")
    parser.add_argument("--delay", type=float, default=0.5, help="Khoảng nghỉ giữa request (giây).")
    parser.add_argument("--timeout", type=float, default=25.0)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )
    session = _build_session(prompt_for_cookie=True)
    try:
        crawler = TopDevAPICrawler(
            session=session,
            timeout=args.timeout,
            delay=args.delay,
            page_size=args.page_size,
            keyword=args.keyword,
        )
        stats = crawler.crawl(
            output_path=args.output,
            max_pages=args.max_pages,
            max_jobs=args.max_jobs,
        )
    except (TopDevAPIError, OSError, ValueError) as exc:
        log.error("%s", exc)
        return 1
    finally:
        session.close()

    print(
        f"TopDev: {stats.pages_processed} trang, {stats.jobs_collected} tin mới, "
        f"{stats.duplicate_jobs} trùng, {stats.skipped_jobs} bỏ qua."
    )
    if stats.failed:
        print(f"Cảnh báo: {stats.stop_reason}", file=sys.stderr)
    if stats.records or args.output.exists():
        print(f"JSON: {args.output.resolve()}")
    return 1 if stats.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())