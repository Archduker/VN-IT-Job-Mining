# -*- coding: utf-8 -*-
"""Thu thập dữ liệu việc làm TopDev từ API v2 theo các category được chọn."""

from __future__ import annotations

import argparse
import getpass
import json
import logging
import os
import re
import tempfile
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
import warnings
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API_BASE_URL = "https://api.topdev.vn/td/v2"
LISTING_URL = f"{API_BASE_URL}/jobs"
DETAIL_URL = f"{API_BASE_URL}/jobs/{{job_id}}"
DEFAULT_OUTPUT = Path(__file__).resolve().with_name("topdev_jobs.json")
PAGE_SIZE = 100
PROGRESS_INTERVAL = 50
JOB_CATEGORY_IDS = (1, 14, 27, 33, 50, 61)
DETAIL_FIELDS = (
    "id,content,requirements_arr,requirements_original,responsibilities,"
    "responsibilities_original,benefits_v2"
)
LISTING_FIELDS = (
    "id,slug,title,salary,company,skills_str,skills_arr,job_types_str,"
    "job_levels_str,job_levels_arr,experiences_str,contract_types_str,"
    "addresses,detail_url,published,is_salary_visible"
)
log = logging.getLogger("topdev.crawler")


class TopDevAPIError(RuntimeError):
    """Lỗi phản hồi hoặc giao tiếp với API TopDev."""


@dataclass
class CrawlResult:
    jobs: dict[str, dict[str, Any]] = field(default_factory=dict)
    pages_processed: int = 0
    pages_failed: int = 0
    detail_failures: int = 0
    skipped_listings: int = 0
    categories_processed: list[int] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "metadata": {
                "source": "topdev",
                "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
                "category_ids": list(JOB_CATEGORY_IDS),
                "categories_processed": self.categories_processed,
                "pages_processed": self.pages_processed,
                "pages_failed": self.pages_failed,
                "detail_failures": self.detail_failures,
                "skipped_listings": self.skipped_listings,
                "jobs_count": len(self.jobs),
                "errors": self.errors,
            },
            "jobs": list(self.jobs.values()),
        }


def _build_session(cookie: str | None = None) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/json",
            "Accept-Language": "vi,en;q=0.8",
            "Origin": "https://topdev.vn",
            "Referer": "https://topdev.vn/jobs/search",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        }
    )
    if cookie and cookie.strip():
        session.headers["Cookie"] = cookie.strip()

    retry = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def _clean_value(value: Any) -> Any:
    """Làm sạch HTML/giá trị rỗng đệ quy mà không đổi kiểu dữ liệu còn lại."""
    if value is None:
        return None
    if isinstance(value, str):
        soup = BeautifulSoup(value, "html.parser")
        for element in soup(("script", "style")):
            element.decompose()
        text = re.sub(r"\s+", " ", soup.get_text(separator=" ", strip=True)).strip()
        return text or None
    if isinstance(value, list):
        cleaned = [_clean_value(item) for item in value]
        return cleaned or None
    if isinstance(value, Mapping):
        cleaned = {str(key): _clean_value(item) for key, item in value.items()}
        return cleaned or None
    return value


def _response_data(payload: Any, endpoint: str) -> dict[str, Any]:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        raise TopDevAPIError(f"API trả sai cấu trúc data object tại {endpoint}.")
    return payload["data"]


class TopDevCrawler:
    """Crawl và lưu riêng dữ liệu listing/detail của từng job."""

    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        cookie: str | None = None,
        timeout: float = 25,
        delay: float = 0.5,
        page_size: int = PAGE_SIZE,
        sleeper: Any = time.sleep,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout phải lớn hơn 0.")
        if delay < 0:
            raise ValueError("delay không được âm.")
        if not 1 <= page_size <= PAGE_SIZE:
            raise ValueError(f"page_size phải nằm trong khoảng 1..{PAGE_SIZE}.")
        self.session = session or _build_session(cookie)
        self.timeout = timeout
        self.delay = delay
        self.page_size = page_size
        self.sleeper = sleeper

    def _get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise TopDevAPIError(
                f"Request API lỗi tại {url}: {type(exc).__name__}."
            ) from exc
        except ValueError as exc:
            raise TopDevAPIError(f"API trả JSON không hợp lệ tại {url}.") from exc
        if not isinstance(payload, dict):
            raise TopDevAPIError(f"API trả sai cấu trúc JSON tại {url}.")
        return payload

    def _fetch_listing(self, category_id: int, page: int) -> tuple[list[Any], dict[str, Any]]:
        payload = self._get_json(
            LISTING_URL,
            {
                "page": page,
                "page_size": self.page_size,
                "job_categories_ids": category_id,
                "locale": "vi_VN",
                "fields[job]": LISTING_FIELDS,
            },
        )
        data = payload.get("data")
        meta = payload.get("meta")
        if not isinstance(data, list) or not isinstance(meta, dict):
            raise TopDevAPIError("API listing thiếu data[] hoặc meta object.")
        return data, meta

    def _fetch_detail(self, job_id: str) -> dict[str, Any]:
        payload = self._get_json(
            DETAIL_URL.format(job_id=job_id),
            {"fields[job]": DETAIL_FIELDS, "locale": "vi_VN"},
        )
        data = _response_data(payload, DETAIL_URL.format(job_id=job_id))
        cleaned = _clean_value(data)
        if not isinstance(cleaned, dict):
            raise TopDevAPIError(f"API detail job {job_id} không có dữ liệu object.")
        for field_name in DETAIL_FIELDS.split(","):
            cleaned.setdefault(field_name, None)
        return cleaned

    def crawl(
        self,
        *,
        output_path: Path = DEFAULT_OUTPUT,
        max_pages: int | None = None,
        max_jobs: int | None = None,
    ) -> CrawlResult:
        if max_pages is not None and max_pages < 1:
            raise ValueError("max_pages phải lớn hơn 0.")
        if max_jobs is not None and max_jobs < 1:
            raise ValueError("max_jobs phải lớn hơn 0.")

        result = CrawlResult()
        for category_id in JOB_CATEGORY_IDS:
            if max_jobs is not None and len(result.jobs) >= max_jobs:
                break
            try:
                first_page, meta = self._fetch_listing(category_id, 1)
            except TopDevAPIError as exc:
                result.pages_failed += 1
                result.errors.append(f"category {category_id}, page 1: {exc}")
                log.error("Lỗi category %d trang đầu: %s", category_id, exc)
                continue

            last_page = meta.get("last_page")
            if not isinstance(last_page, int) or last_page < 1:
                result.pages_failed += 1
                result.errors.append(f"category {category_id}: meta.last_page không hợp lệ")
                log.error("Category %d không có meta.last_page hợp lệ.", category_id)
                continue

            result.categories_processed.append(category_id)
            page = 1
            page_data = first_page
            while page <= last_page:
                if max_pages is not None and page > max_pages:
                    break
                if max_jobs is not None and len(result.jobs) >= max_jobs:
                    break
                if page > 1:
                    if self.delay:
                        self.sleeper(self.delay)
                    try:
                        page_data, meta = self._fetch_listing(category_id, page)
                    except TopDevAPIError as exc:
                        result.pages_failed += 1
                        result.errors.append(f"category {category_id}, page {page}: {exc}")
                        log.error("Lỗi category %d trang %d: %s", category_id, page, exc)
                        page += 1
                        continue

                    response_last_page = meta.get("last_page")
                    if isinstance(response_last_page, int) and response_last_page >= page:
                        last_page = max(last_page, response_last_page)

                result.pages_processed += 1
                if not page_data:
                    result.pages_failed += 1
                    result.errors.append(f"category {category_id}, page {page}: trang rỗng")
                    log.warning("Category %d trang %d rỗng.", category_id, page)

                for listing in page_data:
                    if max_jobs is not None and len(result.jobs) >= max_jobs:
                        break
                    if not isinstance(listing, dict):
                        result.skipped_listings += 1
                        continue
                    listing_clean = _clean_value(listing)
                    if not isinstance(listing_clean, dict):
                        result.skipped_listings += 1
                        continue
                    job_id = listing_clean.get("id")
                    if job_id is None:
                        result.skipped_listings += 1
                        continue
                    job_key = str(job_id)

                    existing = result.jobs.get(job_key)
                    if existing is not None:
                        if category_id not in existing["category_ids"]:
                            existing["category_ids"].append(category_id)
                        continue

                    if self.delay:
                        self.sleeper(self.delay)
                    try:
                        detail = self._fetch_detail(job_key)
                    except TopDevAPIError as exc:
                        detail = None
                        result.detail_failures += 1
                        result.errors.append(f"job {job_key} detail: {exc}")
                        log.error("Không lấy được detail job %s: %s", job_key, exc)

                    result.jobs[job_key] = {
                        "category_ids": [category_id],
                        "listing_response": listing_clean,
                        "detail_response": detail,
                    }
                    collected_count = len(result.jobs)
                    if collected_count % PROGRESS_INTERVAL == 0:
                        print(
                            f"Đã xử lý {collected_count} job duy nhất...",
                            flush=True,
                        )
                page += 1

        _atomic_write(Path(output_path), result.to_json())
        return result


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = stream.name
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    except OSError as exc:
        raise TopDevAPIError(f"Không thể ghi JSON tại {path}: {exc}") from exc
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crawl TopDev jobs through the v2 API.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-pages", type=int, help="Maximum pages per category.")
    parser.add_argument("--max-jobs", type=int, help="Maximum unique jobs for a test run.")
    parser.add_argument("--page-size", type=int, default=PAGE_SIZE)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--timeout", type=float, default=25)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )
    cookie = getpass.getpass("TopDev Cookie (press Enter to continue without login): ")
    crawler = TopDevCrawler(
        cookie=cookie,
        timeout=args.timeout,
        delay=args.delay,
        page_size=args.page_size,
    )
    try:
        result = crawler.crawl(
            output_path=args.output,
            max_pages=args.max_pages,
            max_jobs=args.max_jobs,
        )
    except (TopDevAPIError, OSError, ValueError) as exc:
        log.error("%s", exc)
        return 1
    log.info(
        "Hoàn tất: %d job, %d trang lỗi, %d lỗi detail. JSON: %s",
        len(result.jobs),
        result.pages_failed,
        result.detail_failures,
        args.output.resolve(),
    )
    print(args.output.resolve())
    return 1 if result.pages_failed or result.detail_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())