"""Crawler nguồn JobsGO (https://jobsgo.vn) — Ngành Công Nghệ Thông Tin.

Cơ chế hoạt động 2 giai đoạn (Listing -> Detail):
1. Giai đoạn 1 (Listing): Sử dụng Google Chrome headless với init script bypass Cloudflare Turnstile
   để duyệt qua các trang danh sách việc làm IT từ https://jobsgo.vn/viec-lam-cong-nghe-thong-tin.html,
   hỗ trợ duyệt cho đến trang cuối cùng hoặc đạt giới hạn max_items.
2. Giai đoạn 2 (Detail): Truy cập từng trang chi tiết tin tuyển dụng, trích xuất đầy đủ dữ liệu
   theo Data Contract chuẩn VN-IT-Job-Mining (tiêu đề, công ty, mức lương lồng nhau, danh sách mô tả,
   yêu cầu, quyền lợi, kỹ năng chuyên môn, và các trường mở rộng trong extra).
"""

import argparse
import glob
import logging
import os
import re
from collections.abc import Generator
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from crawlers.base.base_crawler import BaseCrawler
from crawlers.common.schema import JobRecord
from crawlers.common.utils import (
    clean_text,
    detect_language,
    parse_salary_detail,
    strip_html_tags,
    text_to_clean_lines,
)

log = logging.getLogger("jobsgo.crawler")

SOURCE = "jobsgo"
CRAWLER_VERSION = "0.1.0"
BASE_URL = "https://jobsgo.vn"
BASE_LISTING_URL = "https://jobsgo.vn/viec-lam-cong-nghe-thong-tin.html"


class JobsGOCrawler(BaseCrawler):
    """Crawler cho nguồn JobsGO kế thừa BaseCrawler chuẩn dự án."""

    source_name = SOURCE
    crawler_version = CRAWLER_VERSION

    def __init__(
        self,
        checkpoint_dir: str | None = None,
        output_dir: str | None = None,
        max_items: int | None = 5,
        checkpoint_interval: int = 10,
        chrome_path: str = "/usr/bin/google-chrome",
        headless: bool = True,
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
        self.chrome_path = chrome_path
        self.headless = headless
        self.save_html = save_html
        self.html_storage_dir = html_storage_dir or os.path.dirname(__file__)
        self.local_html_dir = local_html_dir

    def _fetch_listing_urls(self, browser) -> list[dict[str, str]]:
        """Pha 1 (URL Harvesting): Quét toàn bộ các trang danh sách JobsGO và thu thập Job URLs vào hàng đợi."""
        import random
        import time

        job_targets: list[dict[str, str]] = []
        seen_ids: set[str] = set()
        current_page = 1
        max_pages_limit = 60

        while True:
            if self.max_items and len(job_targets) >= self.max_items:
                break
            if current_page > max_pages_limit:
                log.info("[JobsGO] Đạt giới hạn an toàn %d trang. Dừng Pha 1.", max_pages_limit)
                break

            page_url = (
                BASE_LISTING_URL
                if current_page == 1
                else f"{BASE_LISTING_URL}?page={current_page}"
            )
            log.info("[JobsGO] [Pha 1] Đang thu hoạch trang listing %d: %s", current_page, page_url)

            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
            )
            context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
            page = context.new_page()

            content = ""
            try:
                page.goto(page_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(3000)
                if "Just a moment..." in page.title() or "Attention Required" in page.content():
                    log.warning("[JobsGO] Cloudflare challenge ở trang %d! Chờ giải mã...", current_page)
                    page.wait_for_timeout(5000)
                content = page.content()
            except Exception as exc:
                log.warning("[JobsGO] Lỗi tải trang listing %d: %s", current_page, exc)
            finally:
                page.close()
                context.close()

            if not content:
                break

            soup = BeautifulSoup(content, "html.parser")
            links = soup.select("a[href*='/viec-lam/']")
            if not links:
                log.info("[JobsGO] Không tìm thấy link bài tuyển dụng nào ở trang %d. Hoàn tất Pha 1.", current_page)
                break

            new_on_page = 0
            for a in links:
                raw_href = a.get("href", "")
                if not raw_href or any(
                    x in raw_href for x in ["viec-lam-cong-nghe-thong-tin", "viec-lam.html", "tim-viec"]
                ):
                    continue

                m = re.search(r"[-_/](\d+)\.html", raw_href)
                if not m:
                    continue

                job_id = m.group(1)
                if str(job_id) in seen_ids:
                    continue

                if self.checkpoint.is_seen(str(job_id)):
                    continue

                seen_ids.add(str(job_id))
                clean_url = urljoin(BASE_URL, raw_href.split("?")[0])

                card_parent = a.find_parent("div", class_=lambda c: c and ("card" in c or "col-grid" in c))
                title_text = clean_text(a.get_text(strip=True))
                comp_tag = card_parent.select_one(".job-company, a[href*='/tuyen-dung/']") if card_parent else None
                comp_name = clean_text(comp_tag.get_text(strip=True)) if comp_tag else "Unknown"

                job_targets.append({
                    "job_id": str(job_id),
                    "url": clean_url,
                    "title": title_text,
                    "company": comp_name,
                    "html_snippet": str(card_parent) if card_parent else "",
                })
                new_on_page += 1

                if self.max_items and len(job_targets) >= self.max_items:
                    break

            log.info(
                "[JobsGO] [Pha 1] Trang %d thu được %d việc làm mới (Tổng hàng đợi: %d)",
                current_page,
                new_on_page,
                len(job_targets),
            )

            if new_on_page == 0:
                log.info("[JobsGO] Không còn tin mới ở trang %d. Dừng phân trang.", current_page)
                break

            current_page += 1
            # Polite sleep giữa các trang listing
            time.sleep(random.uniform(2.0, 3.5))

        return job_targets

    def _sync_fetch_with_playwright(self) -> list[dict[str, Any]]:
        """Pha 2 (Detail Crawling & Retry Queue): Tải mã HTML chi tiết qua hàng đợi có cơ chế thử lại."""
        from playwright.sync_api import sync_playwright
        import random
        import time

        items: list[dict[str, Any]] = []

        # Chế độ đọc file HTML cục bộ (Offline validation / Fast testing)
        if self.local_html_dir and os.path.exists(self.local_html_dir):
            log.info("[JobsGO] Đang tải các file HTML cục bộ từ %s", self.local_html_dir)
            pattern = os.path.join(self.local_html_dir, "*.html")
            files = sorted(glob.glob(pattern))
            if not files and os.path.exists(os.path.join(self.local_html_dir, "jobsgo.md")):
                files = [os.path.join(self.local_html_dir, "jobsgo.md")]

            for fpath in files:
                fname = os.path.basename(fpath)
                m = re.search(r"(\d+)", fname)
                job_id = m.group(1) if m else "29277790532"
                with open(fpath, encoding="utf-8") as f:
                    html_content = f.read()
                items.append({
                    "job_id": job_id,
                    "url": f"https://jobsgo.vn/viec-lam/job-{job_id}.html",
                    "html_content": html_content,
                })
                if self.max_items and len(items) >= self.max_items:
                    break
            return items

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    executable_path=self.chrome_path,
                    headless=self.headless,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-infobars",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                    ],
                )

                # Giai đoạn 1: Thu hoạch toàn bộ URLs
                targets = self._fetch_listing_urls(browser)
                log.info(
                    "[JobsGO] Đã hoàn thành Pha 1. Tổng URLs thu hoạch: %d. Bắt đầu Pha 2 (Detail Crawling)...",
                    len(targets),
                )

                # Giai đoạn 2: Cào chi tiết với Main Queue & Retry Queue
                main_queue = list(targets)
                retry_queue: list[dict[str, Any]] = []

                def fetch_detail(target: dict[str, Any], is_retry: bool = False) -> dict[str, Any] | None:
                    job_id = target["job_id"]
                    clean_job_url = target["url"]
                    dest_file = os.path.join(self.html_storage_dir, f"{job_id}.html")

                    if os.path.exists(dest_file):
                        with open(dest_file, encoding="utf-8") as f:
                            content = f.read()
                        if len(content) > 5000:
                            return {
                                "job_id": job_id,
                                "url": clean_job_url,
                                "html_content": content,
                            }

                    delay = random.uniform(3.0, 5.0) if is_retry else random.uniform(2.0, 3.5)
                    time.sleep(delay)

                    detail_context = browser.new_context(
                        user_agent=(
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
                        ),
                        viewport={"width": 1920, "height": 1080},
                    )
                    detail_context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
                    detail_page = detail_context.new_page()
                    content = ""
                    try:
                        detail_page.goto(clean_job_url, wait_until="domcontentloaded", timeout=30000)
                        detail_page.wait_for_timeout(2500)
                        if "Just a moment..." in detail_page.title() or "Attention Required" in detail_page.content():
                            detail_page.wait_for_timeout(5000)
                        content = detail_page.content()

                        if self.save_html and "Attention Required" not in content and len(content) > 5000:
                            with open(dest_file, "w", encoding="utf-8") as f:
                                f.write(content)
                    except Exception as err:
                        log.warning("[JobsGO] Lỗi tải chi tiết %s: %s", clean_job_url, err)
                    finally:
                        detail_page.close()
                        detail_context.close()

                    if content and "Attention Required" not in content and len(content) > 5000:
                        return {
                            "job_id": job_id,
                            "url": clean_job_url,
                            "html_content": content,
                        }
                    return None

                # Lượt 1: Cào Main Queue
                for idx, target in enumerate(main_queue, 1):
                    item = fetch_detail(target, is_retry=False)
                    if item:
                        items.append(item)
                    else:
                        log.warning("[JobsGO] Chi tiết %s thất bại Lượt 1. Đưa vào Retry Queue.", target["job_id"])
                        retry_queue.append(target)

                    if idx % 10 == 0:
                        log.info("[JobsGO] Tiến độ Pha 2: %d/%d (Thành công: %d, Cần retry: %d)", idx, len(main_queue), len(items), len(retry_queue))

                # Lượt 2: Cào lại Retry Queue nếu còn link lỗi
                if retry_queue:
                    log.info("[JobsGO] Bắt đầu cào lại %d jobs trong Retry Queue...", len(retry_queue))
                    time.sleep(5.0)
                    for target in retry_queue:
                        item = fetch_detail(target, is_retry=True)
                        if item:
                            items.append(item)
                            log.info("[JobsGO] Cào lại thành công cho Job %s!", target["job_id"])
                        else:
                            log.warning("[JobsGO] Job %s vẫn không tải được sau retry. Dùng listing fallback.", target["job_id"])
                            items.append({
                                "job_id": target["job_id"],
                                "url": target["url"],
                                "title": target.get("title"),
                                "company": target.get("company"),
                                "html_snippet": target.get("html_snippet"),
                            })

                browser.close()
        except Exception as exc:
            log.error("[JobsGO] Lỗi trong quá trình cào Playwright: %s", exc, exc_info=True)

        return items

    def fetch_items(self) -> Generator[dict[str, Any], None, None]:
        """Fetch items từ Playwright và yield từng item."""
        yield from self._sync_fetch_with_playwright()

    def parse_item(self, item: dict[str, Any]) -> JobRecord | None:
        """Bóc tách dữ liệu từ HTML chi tiết sang JobRecord chuẩn Data Contract."""
        job_id = item.get("job_id")
        job_url = item.get("url")
        html_content = item.get("html_content") or item.get("html_snippet")

        if not job_id or not job_url:
            return None

        soup = BeautifulSoup(html_content, "html.parser") if html_content else None

        # 1. Tiêu đề công việc
        title = None
        if soup:
            t_el = soup.select_one("h1.job-title, h1")
            if t_el:
                title = clean_text(t_el.get_text(separator=" ", strip=True))
        if not title:
            title = clean_text(item.get("title", ""))
        if not title:
            return None

        # 2. Tên công ty
        company = None
        if soup:
            comp_el = soup.select_one(
                ".card-company h6, .company-logo + div h6, h6.fw-semibold, .job-company"
            )
            if comp_el:
                company = clean_text(comp_el.get_text(strip=True))
        if not company:
            company = clean_text(item.get("company", "")) or "Unknown"

        # 3. Mức lương (Lồng nhau JobSalary)
        salary_text = None
        if soup:
            s_el = soup.select_one(
                "ul.job-info-list li:-soup-contains('Mức lương') strong, .job-info-list li:nth-child(1) strong"
            )
            if s_el:
                salary_text = clean_text(s_el.get_text(strip=True))
        if not salary_text:
            salary_text = "Thoả thuận"

        salary_detail = parse_salary_detail(salary_text, title=title)

        # 4. Địa điểm làm việc
        location_text = None
        detailed_location = None
        if soup:
            loc_el = soup.select_one("ul.job-info-list li:-soup-contains('Địa điểm') strong")
            if loc_el:
                location_text = clean_text(loc_el.get_text(strip=True))

            places_el = soup.select_one("#places .list-place")
            if places_el:
                loc_lines = []
                for p in places_el.select(".location-extra"):
                    span = p.select_one("span")
                    if span:
                        txt = clean_text(span.get_text(strip=True))
                        txt = re.sub(r"^\d+\.\s*", "", txt)
                        if txt and txt not in loc_lines:
                            loc_lines.append(txt)
                if loc_lines:
                    detailed_location = ", ".join(loc_lines)
                else:
                    detailed_location = location_text

        # 5. Kinh nghiệm & Bằng cấp
        exp_text = None
        edu_text = None
        if soup:
            exp_el = soup.select_one("ul.job-info-list li:-soup-contains('Kinh nghiệm') strong")
            if exp_el:
                exp_text = clean_text(exp_el.get_text(strip=True))

            edu_el = soup.select_one("ul.job-info-list li:-soup-contains('Bằng cấp') strong")
            if edu_el:
                edu_text = clean_text(edu_el.get_text(strip=True))

        # 6. Hạn nộp hồ sơ (Deadline)
        deadline_text = None
        if soup:
            dl_label = soup.find(string=re.compile(r"Hạn nộp hồ sơ"))
            if dl_label:
                dl_container = dl_label.find_parent(["p", "div", "li"])
                dl_strong = dl_container.find("strong") if dl_container else None
                if dl_strong:
                    dl_val = clean_text(dl_strong.get_text(strip=True))
                    deadline_text = re.sub(r"\(.*?\)", "", dl_val).strip()

        # 7. Lịch làm việc
        work_schedule = None
        if soup:
            sched_label = soup.find(string=re.compile(r"Thời gian làm việc"))
            if sched_label:
                sched_container = sched_label.find_parent(["div", "p", "li"])
                sched_strong = sched_container.find("strong") if sched_container else None
                if sched_strong:
                    work_schedule = clean_text(sched_strong.get_text(strip=True))

        # 8. Sidebar Thông tin chung (Loại hình, Cấp bậc, Ngày đăng tuyển, Số lượng tuyển)
        general_info: dict[str, str] = {}
        if soup:
            for item_node in soup.select(".job-card .col-12.d-flex.align-items-center, .card .row.gy-3 .col-12"):
                lbl = item_node.select_one("span.text-muted")
                val = item_node.select_one("strong")
                if lbl and val:
                    key = clean_text(lbl.get_text(strip=True)).rstrip(":")
                    general_info[key] = clean_text(val.get_text(strip=True))

        emp_type = general_info.get("Loại hình")
        seniority = general_info.get("Cấp bậc")
        posted_date = general_info.get("Ngày đăng tuyển")
        hiring_quantity = general_info.get("Số lượng tuyển")

        # 9. Thông tin công ty mở rộng (Lĩnh vực, Địa chỉ)
        industry = None
        company_address = None
        if soup:
            ind_label = soup.find(string=re.compile(r"Lĩnh vực"))
            if ind_label:
                val_span = ind_label.find_next(class_="fw-500") or ind_label.find_next("strong")
                industry = clean_text(val_span.get_text(strip=True)) if val_span else None

            addr_label = soup.find(string=re.compile(r"Địa chỉ"))
            if addr_label:
                val_span = addr_label.find_next(class_="fw-500") or addr_label.find_next("strong")
                company_address = clean_text(val_span.get_text(strip=True)) if val_span else None

        # 10. Các khối nội dung: Mô tả công việc, Yêu cầu công việc, Quyền lợi, Kỹ năng, Ngành nghề
        desc_list: list[str] = []
        req_list: list[str] = []
        ben_list: list[str] = []
        skills: list[str] = []
        career: str | None = None

        card = soup.select_one(".job-detail-card") if soup else None
        if card:
            for h3 in card.select("h3.section-title"):
                h3_text = h3.get_text(strip=True).lower()
                content_box = h3.find_next_sibling("div")
                if not content_box:
                    continue
                lines = text_to_clean_lines(str(content_box))
                if any(kw in h3_text for kw in ["mô tả", "description"]):
                    desc_list = lines
                elif any(kw in h3_text for kw in ["yêu cầu", "requirement"]):
                    req_list = lines
                elif any(kw in h3_text for kw in ["quyền lợi", "benefit", "phúc lợi"]):
                    ben_list = lines

            # Thẻ chips Kỹ năng
            skills_el = card.find(lambda e: e.name == "div" and "Kỹ năng:" in e.text)
            if skills_el:
                for s in skills_el.select("strong span, span"):
                    s_txt = clean_text(s.get_text(strip=True))
                    if s_txt and s_txt not in skills and s_txt != ",":
                        skills.append(s_txt)

            # Ngành nghề
            career_el = card.find(lambda e: e.name == "div" and "Ngành nghề:" in e.text)
            if career_el:
                c_strong = career_el.select_one("strong")
                career = clean_text(c_strong.get_text(strip=True)) if c_strong else None

        # Fallback nếu desc_list rỗng
        if not desc_list:
            desc_list = [title]

        # Phân nhóm JobTags:
        # QUY TẮC BẮT BUỘC: Nếu không có badge nhóm quyền lợi -> benefits: null
        tags_data = {
            "requirements": None,
            "benefits": None,
            "skills": skills if skills else None,
        }

        raw_data = {
            "title": title,
            "company": company,
            "salary": salary_detail,
            "tags": tags_data,
            "description_list": desc_list,
            "requirements_list": req_list,
            "benefits_list": ben_list,
            "location_text": location_text,
            "deadline_text": deadline_text,
            "posted_date_text": posted_date or "",
            "employment_type_text": emp_type,
            "seniority_text": seniority,
            "extra": {
                "work_schedule": work_schedule,
                "education": edu_text,
                "experience": exp_text,
                "hiring_quantity": hiring_quantity,
                "industry": industry,
                "company_address": company_address,
                "career": career,
                "detailed_location": detailed_location or location_text,
            },
        }

        lang = detect_language(" ".join(desc_list)) if desc_list else detect_language(f"{title} {company}")

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
    parser = argparse.ArgumentParser(description="JobsGO IT Job Crawler")
    parser.add_argument("--max-items", type=int, default=5, help="Số tin tối đa cần cào (bỏ trống hoặc None để cào hết)")
    parser.add_argument("--output-dir", type=str, default="data", help="Thư mục xuất dữ liệu JSON/JSONL")
    parser.add_argument("--checkpoint-dir", type=str, default=None, help="Thư mục lưu checkpoint")
    parser.add_argument("--save-html", action="store_true", default=False, help="Lưu file HTML chi tiết (mặc định tắt)")
    parser.add_argument("--local-html-dir", type=str, default=None, help="Thư mục chứa HTML cục bộ để parse nhanh")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    crawler = JobsGOCrawler(
        checkpoint_dir=args.checkpoint_dir,
        output_dir=args.output_dir,
        max_items=args.max_items,
        save_html=args.save_html,
        local_html_dir=args.local_html_dir,
    )
    result = crawler.run()
    print("JobsGO crawl completed:", result)


if __name__ == "__main__":
    main()
