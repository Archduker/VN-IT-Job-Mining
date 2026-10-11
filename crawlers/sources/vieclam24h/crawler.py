# -*- coding: utf-8 -*-
"""Thu thập việc làm Vieclam24h qua Selenium và BeautifulSoup, xuất dữ liệu theo Data Contract chuẩn."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
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
    clean_text,
    detect_language,
    text_to_clean_lines,
)

SITE_BASE_URL = "https://vieclam24h.vn"
DEFAULT_OUTPUT = Path(__file__).resolve().with_name("vieclam24h_jobs.json")
CRAWLER_VERSION = "0.2.0"
LOCAL_TIMEZONE = timezone(timedelta(hours=7))
TARGET_INDUSTRIES = ["IT Phần cứng - Mạng", "IT Phần mềm"]

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
) -> JobRecord:
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
            s_min_val = s_min_num / 1_000_000 if s_min_num >= 1000 else s_min_num
        except (ValueError, TypeError):
            pass
    if s_max is not None:
        try:
            s_max_num = float(s_max)
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
    skills_raw = job_detail.get("skills") or job_detail.get("tags") or []
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
    if job_detail.get("education"):
        extra["education"] = str(job_detail["education"])
    if job_detail.get("work_schedule"):
        extra["work_schedule"] = str(job_detail["work_schedule"])
    if job_detail.get("workplace_type"):
        extra["workplace_type"] = str(job_detail["workplace_type"])

    employment_type_text = (
        _clean_text(job_detail.get("type_working_text"))
        or _clean_text(job_detail.get("employment_type"))
        or _clean_text(job_detail.get("work_type"))
        or None
    )
    seniority_text = (
        _clean_text(job_detail.get("position_text"))
        or _clean_text(job_detail.get("level"))
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
        local_json_file: str | Path | None = None,
    ) -> None:
        super().__init__(
            checkpoint_dir=checkpoint_dir,
            output_dir=str(output_dir) if output_dir is not None else None,
            max_items=max_items,
            checkpoint_interval=checkpoint_interval,
        )
        self.max_pages = max_pages
        self.local_json_file = Path(local_json_file) if local_json_file else None
        self.driver: webdriver.Chrome | None = None
        self.wait: WebDriverWait | None = None

    def _init_driver(self) -> None:
        if self.driver is not None:
            return
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 15)

    def fetch_items(self) -> Generator[dict[str, Any], None, None]:
        """Điều hướng Selenium qua danh sách hoặc nạp từ file JSON offline."""
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

        self._init_driver()
        assert self.driver is not None
        assert self.wait is not None

        try:
            self.driver.get(SITE_BASE_URL)
            time.sleep(3)

            # Định vị ô input Ngành nghề
            try:
                industry_input_xpath = (
                    "//div[contains(@id, 'react-select') and contains(., 'Ngành nghề')]/following-sibling::div//input "
                    "| //input[contains(@id, 'react-select')]"
                )
                industry_input = self.wait.until(EC.presence_of_element_located((By.XPATH, industry_input_xpath)))
            except Exception:
                industry_container_xpath = (
                    "//div[contains(@id, 'react-select') and contains(., 'Ngành nghề')] | //div[text()='Ngành nghề']"
                )
                safe_click(self.driver, self.wait, (By.XPATH, industry_container_xpath))
                time.sleep(0.5)
                industry_input = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[id*='react-select']"))
                )

            # Nhập danh sách ngành nghề mục tiêu
            for industry in TARGET_INDUSTRIES:
                safe_click(self.driver, self.wait, industry_input)
                time.sleep(0.3)
                set_react_input(self.driver, industry_input, industry)
                time.sleep(0.5)
                industry_input.send_keys(Keys.ENTER)
                time.sleep(0.5)

            # Click tìm kiếm
            search_btn_xpath = (
                "//button[@data-test-id='common__button' and (contains(@class, 'bg-[#5A30B9]') or contains(@class, 'bg-primary'))]"
            )
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
            if self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass
                self.driver = None

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
    parser = argparse.ArgumentParser(description="Crawl việc làm Vieclam24h theo chuẩn dự án.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-pages", type=int, help="Giới hạn số trang cần crawl.")
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