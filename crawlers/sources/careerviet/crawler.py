# -*- coding: utf-8 -*-
"""Crawler nguồn CareerViet (https://careerviet.vn) — Phiên bản chuẩn Data Contract Schema v1.

Hỗ trợ 2 chế độ thu thập:
1. Online: Duyệt danh mục IT (/viec-lam/cntt-phan-mem-c1-vi.html) và tải trang chi tiết via HttpClient.
2. Offline (--local-html-dir): Tải nhanh từ các file HTML đã lưu để test và kiểm thử hồi quy không phụ thuộc mạng.
"""

import argparse
import glob
import hashlib
import logging
import os
import re
from collections.abc import Generator
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from crawlers.base.base_crawler import BaseCrawler
from crawlers.common.http_client import DelayConfig, HttpClient
from crawlers.common.schema import JobRecord
from crawlers.common.url_ledger import UrlLedger, clean_canonical_url
from crawlers.common.utils import (
    clean_text,
    detect_language,
    parse_salary_detail,
    strip_html_tags,
    text_to_clean_lines,
    classify_job_tags,
)

log = logging.getLogger("careerviet.crawler")

SOURCE = "careerviet"
CRAWLER_VERSION = "0.5.0"
BASE_URL = "https://careerviet.vn"
CATEGORY_PATH = "/viec-lam/cntt-phan-mem-c1-vi.html"
MAX_PAGES = 30


def extract_job_id(url: str) -> str:
    """Trích xuất ID job duy nhất từ URL của CareerViet."""
    match = re.search(r"\.([A-Z0-9]{6,12})\.html", url)
    if match:
        return match.group(1)
    match2 = re.search(r"/(\d{5,12})(?:\.html)?$", url)
    if match2:
        return match2.group(1)
    return hashlib.md5(url.encode()).hexdigest()[:8].upper()


class CareerVietCrawler(BaseCrawler):
    """Crawler cho nguồn CareerViet kế thừa BaseCrawler chuẩn hóa Data Contract v1."""

    source_name = SOURCE
    crawler_version = CRAWLER_VERSION

    def __init__(
        self,
        checkpoint_dir: str | None = None,
        output_dir: str | None = None,
        max_items: int | None = 30,
        checkpoint_interval: int = 10,
        http_client: HttpClient | None = None,
        save_html: bool = False,
        html_storage_dir: str | None = None,
        local_html_dir: str | None = None,
    ) -> None:
        super().__init__(
            checkpoint_dir=checkpoint_dir,
            output_dir=output_dir,
            max_items=max_items,
            checkpoint_interval=checkpoint_interval,
        )
        self.http_client = http_client or HttpClient(
            source=self.source_name,
            delay_config=DelayConfig(min_seconds=1.0, max_seconds=2.5),
            timeout=25,
        )
        self.save_html = save_html
        self.html_storage_dir = html_storage_dir or os.path.dirname(__file__)
        self.local_html_dir = local_html_dir
        self.ledger = UrlLedger(
            source=self.source_name,
            storage_dir=os.path.join(self.output_dir or "data/careerviet", "url_ledger"),
        )

    def discover_urls(self, max_pages: int | None = None) -> list[str]:
        """Pha 1: Quét danh mục việc làm CNTT CareerViet, lưu vào UrlLedger & MinIO."""
        log.info("[CareerViet] === Bắt đầu Pha 1: URL Discovery ===")
        discovered_urls: list[str] = []
        pages_to_crawl = max_pages or 5

        for page in range(1, pages_to_crawl + 1):
            page_url = self._build_page_url(page)
            try:
                resp = self.http_client.get(page_url)
                soup = BeautifulSoup(resp.text, "html.parser")
                job_items = soup.select("div.job-item, div.figure")
                if not job_items:
                    break
                for item in job_items:
                    a_tag = item.select_one("a.job_link, a.job-title, h3 a, a[href*='.html']")
                    if not a_tag or not a_tag.get("href"):
                        continue
                    raw_href = a_tag["href"]
                    if not any(k in raw_href for k in ["/tim-viec-lam/", "/viec-lam/"]):
                        continue
                    clean_url = clean_canonical_url(urljoin(BASE_URL, raw_href))
                    job_id = extract_job_id(clean_url)
                    title = clean_text(a_tag.text)
                    comp_tag = item.select_one("a.company-name, .company, .name")
                    company = clean_text(comp_tag.text) if comp_tag else ""
                    self.ledger.register_url(
                        raw_url=clean_url,
                        job_id=job_id,
                        preliminary_title=title,
                        preliminary_company=company,
                    )
                    discovered_urls.append(clean_url)
            except Exception as exc:
                log.warning("[CareerViet] Safe Skip trang listing %d: %s", page, exc)
                continue

        self.ledger.save_catalog()
        self.ledger.export_daily_manifest()
        log.info("[CareerViet] Pha 1 hoàn thành: phát hiện %d URLs.", len(discovered_urls))
        return discovered_urls

    def crawl_details(self, limit: int | None = None) -> dict[str, int]:
        """Pha 2: Bóc tách SSR HTML chi tiết với Safe Skip và chu kỳ Re-crawl 21 ngày."""
        log.info("[CareerViet] === Bắt đầu Pha 2: Detail Extraction (Chu kỳ Re-crawl 21 ngày) ===")
        pending = self.ledger.get_pending_or_due_records(recheck_days=21)
        log.info("[CareerViet] Tìm thấy %d tin cần crawl chi tiết trong Ledger.", len(pending))
        stats = {"success": 0, "failed": 0, "skipped": 0}
        count = 0

        for item in pending:
            if limit and count >= limit:
                break
            url = item["canonical_url"]
            url_hash = item["url_hash"]
            job_id = item["job_id"]
            try:
                # Safe Skip block
                resp = self.http_client.get(url)
                if not resp or resp.status_code != 200:
                    raise RuntimeError(f"HTTP Error {resp.status_code if resp else 'No response'} for {url}")
                record = self.parse_item({
                    "job_id": job_id,
                    "url": url,
                    "html": resp.text,
                })
                if not record:
                    raise ValueError(f"Không thể parse JobRecord cho {url}")

                raw_out_dir = Path(self.output_dir or "data/careerviet") / "raw"
                raw_out_dir.mkdir(parents=True, exist_ok=True)
                snapshot_file = raw_out_dir / f"{job_id}_v1.json"
                with open(snapshot_file, "w", encoding="utf-8") as f:
                    json.dump(record.model_dump(), f, ensure_ascii=False, indent=2)

                content_hash = hashlib.md5(json.dumps(record.raw.model_dump(), sort_keys=True).encode()).hexdigest()
                self.ledger.mark_scraped(url_hash=url_hash, content_hash=content_hash, version=1, http_status=200)
                stats["success"] += 1
                count += 1
            except Exception as exc:
                log.warning("[CareerViet] Safe Skip lỗi cào chi tiết %s (ID %s): %s", url, job_id, exc)
                self.ledger.mark_failed(url_hash=url_hash, error_message=str(exc))
                stats["failed"] += 1
                continue

        self.ledger.save_catalog()
        log.info("[CareerViet] Pha 2 hoàn tất: %s", stats)
        return stats

    def _build_page_url(self, page: int) -> str:
        if page <= 1:
            return f"{BASE_URL}{CATEGORY_PATH}"
        return f"{BASE_URL}/viec-lam/cntt-phan-mem-c1-trang-{page}-vi.html"

    def fetch_items(self) -> Generator[dict[str, Any], None, None]:
        """Thu thập danh sách items từ web trực tuyến hoặc từ thư mục HTML cục bộ."""
        # 1. Chế độ đọc file HTML cục bộ (Offline testing / fast validation)
        if self.local_html_dir and os.path.exists(self.local_html_dir):
            log.info("[CareerViet] Loading local HTML files from %s", self.local_html_dir)
            pattern = os.path.join(self.local_html_dir, "*.html")
            yielded = 0
            for fpath in sorted(glob.glob(pattern)):
                fname = os.path.basename(fpath)
                m = re.search(r"([A-Z0-9]{6,12})\.html", fname)
                job_id = m.group(1) if m else fname.replace(".html", "")
                with open(fpath, encoding="utf-8") as f:
                    html_content = f.read()

                yield {
                    "job_id": job_id,
                    "url": f"{BASE_URL}/vi/tim-viec-lam/job.{job_id}.html",
                    "html": html_content,
                }
                yielded += 1
                if self.max_items and yielded >= self.max_items:
                    break
            return

        # 2. Chế độ cào trực tuyến từ web
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

            log.info("[CareerViet] Found %d candidate job links on page %d", len(job_links), page)
            for jurl in job_links:
                jid = extract_job_id(jurl)
                if self.checkpoint.is_seen(jid):
                    self.skipped_count += 1
                    continue

                # Tải trang chi tiết
                try:
                    detail_html = self.http_client.get_html(jurl, headers=headers)
                    if self.save_html and detail_html and len(detail_html) > 5000:
                        save_path = os.path.join(self.html_storage_dir, f"{jid}.html")
                        with open(save_path, "w", encoding="utf-8") as f:
                            f.write(detail_html)
                        log.info("[CareerViet] Saved detail HTML to %s", save_path)

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
                log.info("[CareerViet] Reached last page according to pagination.")
                break

    def parse_item(self, item: dict[str, Any]) -> JobRecord | None:
        """Bóc tách HTML chi tiết thành JobRecord chuẩn Data Contract Schema v1."""
        job_id = item.get("job_id")
        job_url = item.get("url")
        html = item.get("html")
        if not job_id or not job_url or not html:
            return None

        soup = BeautifulSoup(html, "html.parser")
        page = soup.find(class_="job-detail-page") or soup

        # 1. Tiêu đề công việc
        title_el = (
            page.find("h1")
            or page.select_one(".title, .job-title")
            or page.find("h2")
        )
        title = clean_text(title_el.text) if title_el else ""
        if not title:
            t_tag = soup.find("title")
            title = clean_text(t_tag.text.split("-")[0]) if t_tag else "Unknown IT Job"

        # 2. Tên công ty tuyển dụng
        comp_tag = page.select_one("a.employer, a.job-company-name, .company-name, a.company")
        if not comp_tag and title_el:
            comp_tag = title_el.find_next("a")
        company = clean_text(comp_tag.text) if comp_tag else "Unknown"

        # 3. Trích xuất metadata từ detail-box (Key-Value list)
        salary_text = "Thương lượng"
        location_text = ""
        exp_text = ""
        seniority_text = ""
        job_type_text = ""
        posted_date_text = ""
        deadline_text = ""

        for li in page.select(".detail-box li, .job-detail-content li, .box-item li, ul.list-info li"):
            text_full = clean_text(li.get_text(separator=" ", strip=True))
            text_lower = text_full.lower()
            p_tag = li.find("p")
            val = clean_text(p_tag.text) if p_tag else text_full

            if "lương" in text_lower:
                val_clean = val.replace("Lương:", "").replace("Lương", "").strip().lstrip(":").strip()
                salary_text = val_clean or val
            elif "địa điểm" in text_lower and not location_text:
                location_text = val.replace("Địa điểm:", "").replace("Địa điểm", "").strip() or val
            elif "kinh nghiệm" in text_lower and not exp_text:
                exp_text = val.replace("Kinh nghiệm:", "").replace("Kinh nghiệm", "").strip() or val
            elif "cấp bậc" in text_lower and not seniority_text:
                seniority_text = val.replace("Cấp bậc:", "").replace("Cấp bậc", "").strip() or val
            elif "hình thức" in text_lower and not job_type_text:
                job_type_text = val.replace("Hình thức:", "").replace("Hình thức", "").strip() or val
            elif "ngày cập nhật" in text_lower and not posted_date_text:
                posted_date_text = val.replace("Ngày cập nhật:", "").replace("Ngày cập nhật", "").strip() or val
            elif any(k in text_lower for k in ["hết hạn nộp", "hạn nộp"]) and not deadline_text:
                deadline_text = val.replace("Hết hạn nộp:", "").replace("Hết hạn nộp", "").strip() or val

        # Fallback địa điểm từ div.map nếu có
        map_link = page.select_one("div.map p a, div.map")
        if not location_text and map_link:
            location_text = clean_text(map_link.text)

        # 4. Phân tích mức lương lồng nhau (JobSalary)
        salary_detail = parse_salary_detail(salary_text, title=title)

        # 5. Các khối chi tiết (Sections): Mô tả, Yêu cầu, Phúc lợi
        desc_raw = ""
        req_raw = ""
        ben_raw = ""
        extra_info: dict[str, str] = {}

        sections = page.select(".detail-row, .job-description, .job-detail-content .row")
        for s in sections:
            header = s.find(["h2", "h3", "h4"])
            htext = header.get_text(strip=True).lower() if header else ""

            if any(k in htext for k in ["mô tả", "job description"]):
                desc_raw = str(s)
            elif any(k in htext for k in ["yêu cầu", "requirements", "requirement"]):
                req_raw = str(s)
            elif any(k in htext for k in ["phúc lợi", "quyền lợi", "benefits", "benefit"]):
                ben_raw = str(s)
            elif any(k in htext for k in ["thông tin khác", "other info"]):
                for li_item in s.find_all("li"):
                    txt = clean_text(li_item.get_text(separator=" ", strip=True))
                    if ":" in txt:
                        k, v = txt.split(":", 1)
                        extra_info[clean_text(k)] = clean_text(v)

        if not desc_raw:
            desc_raw = f"<p>{title} at {company}</p>"

        # Làm sạch danh sách dòng văn bản (list[str]) loại bỏ bullet rác
        desc_list = text_to_clean_lines(desc_raw)
        req_list = text_to_clean_lines(req_raw) if req_raw else None
        ben_list = text_to_clean_lines(ben_raw) if ben_raw else None

        # 6. Thẻ tags theo 3 nhóm cốt lõi: Yêu cầu, Quyền lợi, Chuyên môn
        tag_items = []
        for a in page.select(".job-tags a, .tag-item a, .tag-item, .job-tags li"):
            txt = clean_text(a.get_text(strip=True))
            if txt and txt not in tag_items and not txt.startswith("+"):
                tag_items.append(txt)

        # Phân loại tags
        classified_tags = classify_job_tags(tag_items) if tag_items else {}
        tag_requirements = classified_tags.get("requirements") or None
        tag_benefits = classified_tags.get("benefits") or None
        tag_skills = classified_tags.get("skills") or (tag_items if tag_items else None)

        tags_data = {
            "requirements": tag_requirements,
            "benefits": tag_benefits,  # Bắt buộc null nếu không có thẻ phúc lợi riêng
            "skills": tag_skills,
        }

        # 7. Nhận diện ngôn ngữ
        desc_sample = " ".join(desc_list[:3]) if desc_list else f"{title} {company}"
        lang = detect_language(desc_sample)

        raw_data = {
            "title": title,
            "company": company,
            "salary": salary_detail,
            "tags": tags_data,
            "description_list": desc_list,
            "requirements_list": req_list or [],
            "benefits_list": ben_list or [],
            "location_text": location_text or None,
            "deadline_text": deadline_text or None,
            "posted_date_text": posted_date_text or "",
            "employment_type_text": job_type_text or None,
            "seniority_text": seniority_text or None,
            "extra": {
                "experience": exp_text or extra_info.get("Kinh nghiệm"),
                "education": extra_info.get("Bằng cấp"),
                "age": extra_info.get("Độ tuổi"),
                "other_info": extra_info if extra_info else None,
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
    parser = argparse.ArgumentParser(description="CareerViet IT Job Crawler")
    parser.add_argument("--max-items", type=int, default=30, help="Số tin tối đa cần cào")
    parser.add_argument("--output-dir", type=str, default="data", help="Thư mục xuất dữ liệu")
    parser.add_argument("--checkpoint-dir", type=str, default=None, help="Thư mục lưu checkpoint")
    parser.add_argument("--save-html", action="store_true", default=False, help="Lưu file HTML chi tiết")
    parser.add_argument("--local-html-dir", type=str, default=None, help="Thư mục chứa HTML cục bộ")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    crawler = CareerVietCrawler(
        checkpoint_dir=args.checkpoint_dir,
        output_dir=args.output_dir,
        max_items=args.max_items,
        save_html=args.save_html,
        local_html_dir=args.local_html_dir,
    )
    result = crawler.run()
    print("Crawl completed:", result)


if __name__ == "__main__":
    main()
