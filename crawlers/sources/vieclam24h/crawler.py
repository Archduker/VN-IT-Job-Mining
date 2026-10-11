# -*- coding: utf-8 -*-
"""Thu thập việc làm Vieclam24h qua Selenium và BeautifulSoup, xuất dữ liệu theo Data Contract chuẩn."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import tempfile
import time
import unicodedata
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from bs4 import BeautifulSoup
from pydantic import ValidationError
from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    StaleElementReferenceException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from crawlers.base.base_crawler import BaseCrawler
from crawlers.common.schema import JobMetadata, JobRaw, JobRecord, JobSalary, JobTags
from crawlers.common.utils import (
    detect_language,
    parse_salary_detail,
    text_to_clean_lines,
)

SITE_BASE_URL = "https://vieclam24h.vn"
DEFAULT_OUTPUT = Path(__file__).resolve().with_name("vieclam24h_jobs.json")
CRAWLER_VERSION = "0.1.0"
LOCAL_TIMEZONE = timezone(timedelta(hours=7))
TARGET_INDUSTRIES = ["IT Phần cứng - Mạng", "IT Phần mềm"]

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
VISIBLE_EXTRA_FIELDS = {"work_schedule", "education", "hiring_quantity", "workplace_type", "experience", "address_components"}

log = logging.getLogger("vieclam24h.crawler")


class ViecLam24hAPIError(RuntimeError):
    """Lỗi xử lý dữ liệu hoặc DOM tại Vieclam24h."""


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def _text_identity(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[^\w]+", "", normalized, flags=re.UNICODE)


def _deduplicate_texts(values: list[str]) -> list[str]:
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


def _parse_html_to_list(html_content: Any) -> list[str]:
    if not html_content:
        return []
    soup = BeautifulSoup(str(html_content), "html.parser")
    items = []
    for li in soup.find_all("li"):
        text = li.get_text(strip=True)
        if text:
            items.append(text)
    if not items:
        for p in soup.find_all(["p", "div"]):
            text = p.get_text(strip=True)
            if text and text not in items:
                items.append(text)
    if not items:
        text = soup.get_text(separator="\n", strip=True)
        items = [line.strip() for line in text.split("\n") if line.strip()]
    return _deduplicate_texts(items)


def set_react_input(driver: webdriver.Chrome, element: Any, value: str) -> None:
    js_script = """
        var element = arguments[0];
        var value = arguments[1];
        var valueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        element.focus();
        valueSetter.call(element, value);
        element.dispatchEvent(new Event('input', { bubbles: true }));
        element.dispatchEvent(new Event('change', { bubbles: true }));
        element.dispatchEvent(new KeyboardEvent('keydown', { bubbles: true, key: 'Enter' }));
        element.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: 'Enter' }));
    """
    driver.execute_script(js_script, element, value)


def safe_click(driver: webdriver.Chrome, wait: WebDriverWait, locator_or_element: Any, retries: int = 3) -> bool:
    for attempt in range(retries):
        try:
            if isinstance(locator_or_element, tuple):
                element = wait.until(EC.element_to_be_clickable(locator_or_element))
            else:
                element = locator_or_element

            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(0.3)
            driver.execute_script("arguments[0].click();", element)
            return True
        except (StaleElementReferenceException, ElementClickInterceptedException):
            time.sleep(0.5)
            if attempt == retries - 1:
                raise
    return False


def _make_record(
    job_detail: dict[str, Any],
    fallback_url: str,
    *,
    batch_id: str,
    crawled_at: datetime,
) -> dict[str, Any]:
    job_id = str(job_detail.get("id", ""))
    title = _clean_text(job_detail.get("title"))
    employer = job_detail.get("employer_info", {})
    company = _clean_text(employer.get("name") if isinstance(employer, dict) else None)

    if not title or not company:
        raise ViecLam24hAPIError("Bản ghi thiếu tiêu đề hoặc tên công ty.")

    title_slug = job_detail.get("title_slug", "")
    job_url = f"{SITE_BASE_URL}/{title_slug}-id{job_id}.html" if job_id and title_slug else fallback_url

    # Xử lý địa chỉ
    street_address, address_locality, address_region, address_country = None, None, None, None
    places = job_detail.get("places", [])
    if places and isinstance(places[0], dict):
        p_info = places[0]
        street_address = _clean_text(p_info.get("address"))
        address_locality = _clean_text(p_info.get("city_name"))

    location_parts = [p for p in [street_address, address_locality, address_region, address_country] if p]
    location_text = ", ".join(location_parts) if location_parts else None

    # Xử lý lương
    s_min = job_detail.get("salary_min")
    s_max = job_detail.get("salary_max")
    s_min_val, s_max_val = None, None
    if s_min is not None:
        s_min_val = float(s_min) / 1000000 if s_min >= 1000 else float(s_min)
    if s_max is not None:
        s_max_val = float(s_max) / 1000000 if s_max >= 1000 else float(s_max)

    if s_min_val is not None and s_max_val is not None:
        salary_text = f"{int(s_min_val)} - {int(s_max_val)} triệu"
        is_neg = False
    else:
        salary_text = "Thoả thuận"
        is_neg = True

    salary = JobSalary(
        salary_text=salary_text,
        salary_min=s_min_val,
        salary_max=s_max_val,
        salary_currency="VND" if s_min is not None else None,
        pay_period="month",
        is_negotiable=is_neg,
        has_commission=False,
    )

    desc_html = job_detail.get("description_html") or job_detail.get("description")
    req_html = job_detail.get("other_requirement_html") or job_detail.get("other_requirement")
    benefit_html = job_detail.get("benefit_html") or job_detail.get("benefit")

    description_list = _parse_html_to_list(desc_html)
    requirements_list = _parse_html_to_list(req_html)
    benefits_list = _parse_html_to_list(benefit_html)

    experience_val = job_detail.get("experience_range")
    experience_text = f"{experience_val} năm kinh nghiệm chuyên môn" if experience_val else "Không yêu cầu kinh nghiệm"

    tags = JobTags(
        requirements=requirements_list or None,
        benefits=benefits_list or None,
        skills=None,
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
        location_text=location_text,
        deadline_text=_format_timestamp(job_detail.get("resume_apply_expired")),
        posted_date_text=_format_timestamp(job_detail.get("created_at")),
        employment_type_text="Toàn thời gian",
        seniority_text="Nhân viên",
        extra={
            "work_schedule": "Thứ 2 - Thứ 6",
            "education": "Đại Học trở lên",
            "hiring_quantity": f"{job_detail.get('vacancy_quantity', 1)} người",
            "workplace_type": "Làm việc tại văn phòng / Onsite",
            "experience": experience_text,
            "address_components": {
                "streetAddress": street_address,
                "addressLocality": address_locality,
                "addressRegion": address_region,
                "addressCountry": address_country,
            },
        },
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
    record = JobRecord(_meta=meta, raw=JobRaw(**raw_values))
    return record.to_jsonl_dict()


def _load_existing(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ViecLam24hAPIError(f"Không đọc được JSON hiện có tại {path}") from exc
    if not isinstance(existing, list):
        raise ViecLam24hAPIError(f"JSON hiện có tại {path} không phải array.")

    records: dict[str, dict[str, Any]] = {}
    for record in existing:
        if not isinstance(record, dict):
            continue
        meta = record.get("_meta", {})
        job_id = str(meta.get("source_job_id", ""))
        if job_id:
            records[job_id] = record
    return records


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
        os.replace(temp_name, path)
    except Exception as exc:
        raise ViecLam24hAPIError(f"Không thể ghi file JSON an toàn tại {path}: {exc}") from exc
    finally:
        if temp_name and os.path.exists(temp_name):
            try:
                os.unlink(temp_name)
            except OSError:
                pass


class ViecLam24hCrawler(BaseCrawler):
    """Crawler tích hợp Selenium cho Vieclam24h theo chuẩn BaseCrawler của hệ thống."""

    source_name = "vieclam24h"
    crawler_version = CRAWLER_VERSION

    def __init__(
        self,
        checkpoint_dir: str | None = None,
        output_dir: str | Path | None = None,
        max_items: int | None = None,
        max_pages: int | None = None,
        checkpoint_interval: int = 10,
    ) -> None:
        super().__init__(
            checkpoint_dir=checkpoint_dir,
            output_dir=str(output_dir) if output_dir is not None else None,
            max_items=max_items,
            checkpoint_interval=checkpoint_interval,
        )
        self.max_pages = max_pages
        self.driver = webdriver.Chrome()
        self.wait = WebDriverWait(self.driver, 15)

    def fetch_items(self) -> Generator[dict[str, Any], None, None]:
        """Điều hướng Selenium qua danh sách, tìm kiếm ngành IT và trích xuất chi tiết tin."""
        try:
            self.driver.get(SITE_BASE_URL)
            time.sleep(3)

            # Định vị ô input Ngành nghề
            try:
                industry_input_xpath = "//div[contains(@id, 'react-select') and contains(., 'Ngành nghề')]/following-sibling::div//input | //input[contains(@id, 'react-select')]"
                industry_input = self.wait.until(EC.presence_of_element_located((By.XPATH, industry_input_xpath)))
            except Exception:
                industry_container_xpath = "//div[contains(@id, 'react-select') and contains(., 'Ngành nghề')] | //div[text()='Ngành nghề']"
                safe_click(self.driver, self.wait, (By.XPATH, industry_container_xpath))
                time.sleep(0.5)
                industry_input = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[id*='react-select']")))

            # Nhập danh sách ngành nghề mục tiêu
            for industry in TARGET_INDUSTRIES:
                safe_click(self.driver, self.wait, industry_input)
                time.sleep(0.3)
                set_react_input(self.driver, industry_input, industry)
                time.sleep(0.5)
                industry_input.send_keys(Keys.ENTER)
                time.sleep(0.5)

            # Click tìm kiếm
            search_btn_xpath = "//button[@data-test-id='common__button' and (contains(@class, 'bg-[#5A30B9]') or contains(@class, 'bg-primary'))]"
            safe_click(self.driver, self.wait, (By.XPATH, search_btn_xpath))
            time.sleep(3)

            page_index = 1
            yielded_ids: set[str] = set()
            collected_count = 0

            while True:
                if self.max_pages is not None and page_index > self.max_pages:
                    break

                log.info("Đang xử lý trang danh sách số %d", page_index)
                main_window = self.driver.current_window_handle

                job_cards_xpath = "//a[@data-job-id and contains(@href, '.html')]"
                job_links = self.driver.find_elements(By.XPATH, job_cards_xpath)
                
                job_urls = []
                seen_urls = set()
                for link in job_links:
                    u = link.get_attribute("href")
                    if u and u not in seen_urls:
                        seen_urls.add(u)
                        job_urls.append(u)

                for url in job_urls:
                    if self.max_items is not None and collected_count >= self.max_items:
                        return
                    try:
                        self.driver.execute_script("window.open(arguments[0], '_blank');", url)
                        time.sleep(1.5)
                        self.driver.switch_to.window(self.driver.window_handles[-1])
                        time.sleep(2)

                        soup = BeautifulSoup(self.driver.page_source, "html.parser")
                        script_tag = soup.find("script", id="__NEXT_DATA__")
                        job_detail = None

                        if script_tag and script_tag.string:
                            try:
                                next_data = json.loads(script_tag.string)
                                job_detail = (
                                    next_data.get("props", {})
                                    .get("initialState", {})
                                    .get("api", {})
                                    .get("jobDetailHiddenContact", {})
                                    .get("data", {})
                                )
                                if not job_detail:
                                    page_props = next_data.get("props", {}).get("pageProps", {})
                                    for k, v in page_props.items():
                                        if isinstance(v, dict) and "id" in v and "title" in v:
                                            job_detail = v
                                            break
                            except Exception:
                                pass

                        if job_detail:
                            job_id = str(job_detail.get("id", ""))
                            if job_id and job_id in yielded_ids:
                                self.driver.close()
                                self.driver.switch_to.window(main_window)
                                continue
                            if job_id:
                                yielded_ids.add(job_id)
                            
                            collected_count += 1
                            yield {"job_detail": job_detail, "url": url}

                        self.driver.close()
                        time.sleep(0.5)
                        self.driver.switch_to.window(main_window)
                        time.sleep(1)
                    except Exception as exc:
                        log.warning("Lỗi cào chi tiết bài viết %s: %s", url, exc)
                        if len(self.driver.window_handles) > 1:
                            self.driver.close()
                        self.driver.switch_to.window(main_window)
                        time.sleep(1)

                # Chuyển trang tiếp theo qua rel="next"
                try:
                    next_btn_xpath = "//a[@rel='next']"
                    next_buttons = self.driver.find_elements(By.XPATH, next_btn_xpath)
                    if next_buttons:
                        next_btn = next_buttons[0]
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_btn)
                        time.sleep(0.5)
                        self.driver.execute_script("arguments[0].click();", next_btn)
                        page_index += 1
                        time.sleep(3)
                    else:
                        break
                except Exception:
                    break
        finally:
            try:
                self.driver.quit()
            except Exception:
                pass

    def parse_item(self, item: dict[str, Any]) -> JobRecord | None:
        try:
            job_detail = item.get("job_detail")
            url = item.get("url", "")
            if not isinstance(job_detail, dict):
                return None
            
            record_dict = _make_record(
                job_detail,
                url,
                batch_id=self.batch_id,
                crawled_at=datetime.now(LOCAL_TIMEZONE),
            )
            return JobRecord.model_validate(record_dict)
        except (ViecLam24hAPIError, ValueError, ValidationError) as exc:
            log.warning("Bỏ qua job không hợp lệ: %s", exc)
            self.skipped_count += 1
            return None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crawl việc làm Vieclam24h theo chuẩn dự án.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-pages", type=int, help="Giới hạn số trang cần crawl.")
    parser.add_argument("--max-jobs", type=int, help="Giới hạn số lượng tin tuyển dụng.")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    output_path = args.output
    all_records = _load_existing(output_path)
    
    crawler = ViecLam24hCrawler(
        max_items=args.max_jobs,
        max_pages=args.max_pages,
    )

    new_count = 0
    try:
        for record in crawler.run():
            record_dict = record.to_jsonl_dict()
            meta = record_dict.get("_meta", {})
            job_id = str(meta.get("source_job_id", ""))
            if job_id:
                all_records[job_id] = record_dict
            else:
                all_records[meta.get("url", str(len(all_records)))] = record_dict
            new_count += 1
            _atomic_write(output_path, all_records)
    except Exception as exc:
        log.error("Lỗi khi chạy crawler: %s", exc)
        return 1

    print(f"Vieclam24h: Hoàn tất thu thập {new_count} tin mới. Lưu tại: {output_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())