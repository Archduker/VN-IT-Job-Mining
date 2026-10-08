# -*- coding: utf-8 -*-
"""Crawler nguồn CareerViet (https://careerviet.vn).

Owner: Tài (refactored to single file BaseCrawler architecture).
Duyệt qua danh mục việc làm CNTT - Phần mềm, tải listing và bóc tách trực tiếp trang chi tiết.
Sử dụng HttpClient tiêu chuẩn với delay, auto-retry và rotate User-Agent.
"""

import argparse
import hashlib
import logging
import re
import sys
from typing import Any, Dict, Generator, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from crawlers.base.base_crawler import BaseCrawler
from crawlers.common.http_client import DelayConfig, HttpClient
from crawlers.common.schema import JobRecord
from crawlers.common.utils import clean_text, strip_html_tags

log = logging.getLogger("careerviet.crawler")

SOURCE = "careerviet"
CRAWLER_VERSION = "0.2.0"
BASE_URL = "https://careerviet.vn"
CATEGORY_PATH = "/viec-lam/cntt-phan-mem-c1-vi.html"
MAX_PAGES = 30


def extract_job_id(url: str) -> str:
    """Trích xuất ID job từ URL của CareerViet."""
    match = re.search(r"\.([A-Z0-9]{6,12})\.html", url)
    if match:
        return match.group(1)
    match2 = re.search(r"/(\d{5,12})(?:\.html)?$", url)
    if match2:
        return match2.group(1)
    return hashlib.md5(url.encode()).hexdigest()[:8].upper()


class CareerVietCrawler(BaseCrawler):
    """Crawler cho nguồn CareerViet."""

    source_name = SOURCE
    crawler_version = CRAWLER_VERSION

    def __init__(
        self,
        checkpoint_dir: Optional[str] = None,
        output_dir: Optional[str] = None,
        max_items: Optional[int] = 30,
        checkpoint_interval: int = 10,
        http_client: Optional[HttpClient] = None,
    ) -> None:
        super().__init__(
            checkpoint_dir=checkpoint_dir,
            output_dir=output_dir,
            max_items=max_items,
            checkpoint_interval=checkpoint_interval,
        )
        self.http_client = http_client or HttpClient(
            source=self.source_name,
            delay_config=DelayConfig(min_seconds=1.5, max_seconds=3.0),
            timeout=25,
        )

    def _build_page_url(self, page: int) -> str:
        if page <= 1:
            return f"{BASE_URL}{CATEGORY_PATH}"
        return f"{BASE_URL}/viec-lam/cntt-phan-mem-c1-trang-{page}-vi.html"

    def fetch_items(self) -> Generator[Dict[str, Any], None, None]:
        """Duyệt các trang kết quả tìm kiếm và tải HTML chi tiết từng việc làm."""
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": BASE_URL,
        }

        seen_urls = set()

        for page in range(1, MAX_PAGES + 1):
            page_url = self._build_page_url(page)
            log.info("[CareerViet] Fetching listing page %d: %s", page, page_url)

            try:
                html = self.http_client.get_html(page_url, headers=headers)
            except Exception as exc:
                log.error("[CareerViet] Failed to fetch page %d: %s", page, exc)
                break

            soup = BeautifulSoup(html, "html.parser")
            job_links = []
            for a_tag in soup.select("div.job-item a.job-title, a[href*='/tim-viec-lam/']"):
                href = a_tag.get("href")
                if href and re.search(r"\.[A-Z0-9]{6,12}\.html", href):
                    full_url = urljoin(BASE_URL, href)
                    if full_url not in seen_urls:
                        seen_urls.add(full_url)
                        job_links.append(full_url)

            if not job_links:
                log.info("[CareerViet] No job links found at page %d. Ending listing crawl.", page)
                break

            log.info("[CareerViet] Found %d job links on page %d", len(job_links), page)
            for jurl in job_links:
                jid = extract_job_id(jurl)
                if self.checkpoint.is_seen(jid):
                    self.skipped_count += 1
                    continue

                # Tải trang chi tiết
                try:
                    detail_html = self.http_client.get_html(jurl, headers=headers)
                    yield {
                        "job_id": jid,
                        "url": jurl,
                        "html": detail_html,
                    }
                except Exception as exc:
                    log.error("[CareerViet] Failed to fetch job detail %s: %s", jurl, exc)
                    continue

            # Kiểm tra phân trang tiếp theo
            next_btn = soup.select_one("li.next-page")
            if next_btn and "disabled" in next_btn.get("class", []):
                log.info("[CareerViet] Reached last page according to pagination button.")
                break

    def parse_item(self, item: Dict[str, Any]) -> Optional[JobRecord]:
        """Bóc tách nội dung HTML chi tiết thành JobRecord."""
        job_id = item.get("job_id")
        job_url = item.get("url")
        html = item.get("html")
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")
        page = soup.find(class_="job-detail-page") or soup

        # Title: Ưu tiên h1 hoặc class .title/.job-title trước khi fallback về h2
        title_el = (
            page.find("h1")
            or page.select_one(".title, .job-title")
            or page.find("h2")
        )
        title = clean_text(title_el.text) if title_el else ""
        if not title:
            # Fallback title from <title> tag
            t_tag = soup.find("title")
            title = clean_text(t_tag.text.split("-")[0]) if t_tag else "Unknown IT Job"

        # Company
        comp_tag = page.find("a", class_=lambda c: c and ("employer" in c or "company" in c))
        if not comp_tag and title_el:
            comp_tag = title_el.find_next("a")
        company = clean_text(comp_tag.text) if comp_tag else "Unknown"

        # Salary: Ưu tiên lấy từ box thông tin chi tiết (li chứa "Lương")
        salary_text = "Thương lượng"
        for li in page.find_all("li"):
            if "lương" in li.text.lower():
                p_tag = li.find("p")
                if p_tag and clean_text(p_tag.text):
                    salary_text = clean_text(p_tag.text)
                    break
        if salary_text == "Thương lượng":
            sal_tag = page.find("strong")
            if sal_tag and sal_tag.text.strip():
                st = clean_text(sal_tag.text)
                if not any(k in st.lower() for k in ["địa điểm", "ngày cập nhật", "ngành nghề", "hình thức"]):
                    salary_text = st

        # Sections: Mô tả, Yêu cầu, Phúc lợi, Thông tin khác
        desc_html = ""
        req_text = ""
        benefits_text = ""
        location_text = ""
        exp_text = ""
        seniority_text = ""
        job_type_text = ""
        posted_date_text = ""

        # Trích xuất metadata từ detail-box (CareerViet hiện đại)
        for li in page.find_all("li"):
            text_lower = li.text.lower()
            p_tag = li.find("p")
            val = clean_text(p_tag.text) if p_tag else ""
            if "địa điểm" in text_lower and not location_text and val:
                location_text = val
            elif "kinh nghiệm" in text_lower and not exp_text and val:
                exp_text = val
            elif "cấp bậc" in text_lower and not seniority_text and val:
                seniority_text = val
            elif "hình thức" in text_lower and not job_type_text and val:
                job_type_text = val
            elif "ngày cập nhật" in text_lower and not posted_date_text and val:
                posted_date_text = val

        # Fallback địa điểm từ div.map nếu có
        map_link = page.select_one("div.map p a")
        if not location_text and map_link:
            location_text = clean_text(map_link.text)

        # Tags / kỹ năng
        skill_tags = [clean_text(a.text) for a in page.select(".job-tags a, .tag-item a, .tag-item") if clean_text(a.text)]
        skills_text = ", ".join(skill_tags) if skill_tags else None

        sections = page.find_all(class_="detail-row")
        for s in sections:
            header = s.find(["h2", "h3", "h4"])
            htext = header.text.lower() if header else ""

            if "mô tả" in htext:
                desc_html = str(s)
            elif "yêu cầu" in htext:
                req_text = clean_text(s.text)
            elif "phúc lợi" in htext:
                benefits_text = clean_text(s.text)
            elif "thông tin khác" in htext:
                info_text = s.text
                if not location_text and "Địa điểm" in info_text:
                    loc_match = re.search(r"Địa điểm:\s*([^\n]+)", info_text)
                    if loc_match:
                        location_text = loc_match.group(1).strip()
                if not exp_text and "Kinh nghiệm" in info_text:
                    exp_match = re.search(r"Kinh nghiệm:\s*([^\n]+)", info_text)
                    if exp_match:
                        exp_text = exp_match.group(1).strip()

        if not desc_html:
            desc_html = f"<p>{title} at {company}</p>"
        desc_text = strip_html_tags(desc_html)

        raw_data = {
            "title": title,
            "company": company,
            "description_html": desc_html,
            "description_text": desc_text,
            "salary_text": salary_text,
            "location_text": location_text or None,
            "skills_text": skills_text,
            "experience_text": exp_text or None,
            "employment_type_text": job_type_text or None,
            "seniority_text": seniority_text or None,
            "requirements_text": req_text or None,
            "benefits_text": benefits_text or None,
            "posted_date_text": posted_date_text or "",
        }

        return JobRecord.create(
            source=self.source_name,
            source_job_id=job_id,
            url=job_url,
            batch_id=self.batch_id,
            raw_data=raw_data,
            crawler_version=self.crawler_version,
        )


def main():
    parser = argparse.ArgumentParser(description="CareerViet IT Job Crawler")
    parser.add_argument("--max-items", type=int, default=30, help="Số tin tối đa cần cào")
    parser.add_argument("--output-dir", type=str, default="data", help="Thư mục xuất dữ liệu")
    parser.add_argument("--checkpoint-dir", type=str, default=None, help="Thư mục lưu checkpoint")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    crawler = CareerVietCrawler(
        checkpoint_dir=args.checkpoint_dir,
        output_dir=args.output_dir,
        max_items=args.max_items,
    )
    result = crawler.run()
    print("Crawl completed:", result)


if __name__ == "__main__":
    main()
