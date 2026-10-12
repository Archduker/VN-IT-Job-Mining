"""Crawler nguồn TopCV (https://www.topcv.vn) — Phiên bản 2 giai đoạn (Listing -> Detail).

Cơ chế hoạt động:
1. Giai đoạn 1 (Listing): Sử dụng Google Chrome headless với persistent context để quét danh sách
   việc làm IT từ https://www.topcv.vn/viec-lam-it, lấy danh sách Job IDs & Job URLs.
2. Giai đoạn 2 (Detail): Truy cập từng trang chi tiết tin tuyển dụng, tải toàn bộ mã HTML,
   lưu file HTML ({job_id}.html) phục vụ phân tích / cache và trích xuất đầy đủ 100% dữ liệu
   (mô tả chi tiết, yêu cầu ứng viên, quyền lợi, hạn nộp hồ sơ, kỹ năng, địa điểm, lịch làm việc).
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
from crawlers.common.schema import JobRecord, JobSalary, JobTags
from crawlers.common.utils import (
    clean_text,
    detect_language,
    parse_salary,
    parse_salary_detail,
    strip_html_tags,
    text_to_clean_lines,
    classify_job_tags,
)

log = logging.getLogger("topcv.crawler")

SOURCE = "topcv"
CRAWLER_VERSION = "0.5.0"
BASE_URL = "https://www.topcv.vn"
BASE_LISTING_URL = "https://www.topcv.vn/tim-viec-lam-cong-nghe-thong-tin-cr257"
START_URL = BASE_LISTING_URL


class TopCVCrawler(BaseCrawler):
    """Crawler cho nguồn TopCV sử dụng Playwright / Chrome browser theo mô hình 2 giai đoạn."""

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
        """Pha 1 (URL Harvesting): Quét toàn bộ các trang danh sách và thu thập tất cả Job URLs vào hàng đợi."""
        import random
        import time

        job_targets = []
        seen_ids = set()
        current_page = 1
        max_pages_limit = 60

        while True:
            if self.max_items and len(job_targets) >= self.max_items:
                break
            if current_page > max_pages_limit:
                log.info("[TopCV] Đã đạt giới hạn quét tối đa %d trang. Dừng Pha 1.", max_pages_limit)
                break

            page_url = f"{BASE_LISTING_URL}?page={current_page}"
            log.info("[TopCV] [Pha 1] Đang thu hoạch trang listing %d: %s", current_page, page_url)

            cards = []
            for attempt in range(1, 4):
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1920, "height": 1080},
                )
                page = context.new_page()
                try:
                    page.goto(page_url, wait_until="domcontentloaded", timeout=35000)
                    for _ in range(6):
                        title = page.title()
                        if "Cloudflare" not in title and "Just a moment" not in title:
                            break
                        log.warning("[TopCV] Phát hiện Cloudflare ở trang %d. Đang chờ giải mã... (%s)", current_page, title)
                        page.wait_for_timeout(2500)

                    content = page.content()
                    soup = BeautifulSoup(content, "html.parser")
                    cards = soup.select(".job-item-search-result, .job-item, div[data-job-id]")
                    if cards:
                        break
                    else:
                        log.warning("[TopCV] Trang %d chưa có cards ở lượt %d/3. Chờ thử lại...", current_page, attempt)
                        time.sleep(3.0 * attempt)
                except Exception as exc:
                    log.warning("[TopCV] Lỗi tải trang listing %d ở lượt %d/3: %s", current_page, attempt, exc)
                    time.sleep(3.0 * attempt)
                finally:
                    page.close()
                    context.close()

            if not cards:
                log.info("[TopCV] Không còn job cards nào ở trang %d sau 3 lượt thử. Hoàn tất Pha 1.", current_page)
                break

            new_on_page = 0
            for card in cards:
                job_id = card.get("data-job-id")
                a_tag = None
                for a in card.select("a[href*='/viec-lam/']"):
                    href = a.get("href", "")
                    if clean_text(a.text) and not any(k in href for k in ["viec-lam-it", "tag"]):
                        a_tag = a
                        break

                if not a_tag:
                    continue

                raw_url = a_tag.get("href", "")
                if not job_id and raw_url:
                    m = re.search(r"[-_/](\d+)\.html", raw_url)
                    job_id = m.group(1) if m else None

                if not job_id or str(job_id) in seen_ids:
                    continue

                if str(job_id) in self.checkpoint.seen_ids:
                    continue

                comp_tag = card.select_one(".company, .company-name, a.company, a[href*='/cong-ty/']")
                comp = clean_text(comp_tag.text) if comp_tag else "Unknown"
                sal_tag = card.select_one(".salary, .title-salary, span.salary")
                sal = clean_text(sal_tag.text) if sal_tag else "Thương lượng"

                seen_ids.add(str(job_id))
                full_url = urljoin(BASE_URL, raw_url)
                job_targets.append({
                    "job_id": str(job_id),
                    "url": full_url,
                    "title": clean_text(a_tag.text),
                    "company": comp,
                    "salary": sal,
                    "html_snippet": str(card),
                })
                new_on_page += 1

                if self.max_items and len(job_targets) >= self.max_items:
                    break

            log.info(
                "[TopCV] [Pha 1] Trang %d thu được %d candidates mới (Tổng hàng đợi: %d)",
                current_page,
                new_on_page,
                len(job_targets),
            )
            current_page += 1
            # Polite sleep giữa các trang listing để chống chặn WAF
            time.sleep(random.uniform(2.0, 3.5))

        return job_targets

    def _sync_fetch_with_playwright(self) -> list[dict[str, Any]]:
        """Pha 2 (Detail Crawling & Retry Queue): Tải toàn bộ HTML chi tiết qua hàng đợi có cơ chế thử lại."""
        from playwright.sync_api import sync_playwright
        import random
        import time

        items: list[dict[str, Any]] = []

        # Chế độ đọc file HTML cục bộ (Offline testing / fast validation)
        if self.local_html_dir and os.path.exists(self.local_html_dir):
            log.info("[TopCV] Loading local HTML files from %s", self.local_html_dir)
            pattern = os.path.join(self.local_html_dir, "*.html")
            for fpath in sorted(glob.glob(pattern)):
                fname = os.path.basename(fpath)
                m = re.match(r"(\d+)\.html", fname)
                if not m:
                    continue
                job_id = m.group(1)
                with open(fpath, encoding="utf-8") as f:
                    html_content = f.read()
                items.append({
                    "job_id": job_id,
                    "url": f"https://www.topcv.vn/viec-lam/{job_id}.html",
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
                        "--disable-dev-shm-usage",
                    ],
                )

                # Giai đoạn 1: Thu hoạch toàn bộ URLs
                targets = self._fetch_listing_urls(browser)
                log.info(
                    "[TopCV] Đã hoàn thành Pha 1. Tổng URLs thu hoạch: %d. Bắt đầu Pha 2 (Detail Crawling)...",
                    len(targets),
                )

                # Giai đoạn 2: Cào chi tiết với Hàng đợi Chính (Main Queue) & Hàng đợi Thử lại (Retry Queue)
                main_queue = list(targets)
                retry_queue: list[dict[str, Any]] = []

                def fetch_detail(target: dict[str, Any], is_retry: bool = False) -> dict[str, Any] | None:
                    job_id = target["job_id"]
                    clean_job_url = target["url"].split("?")[0]
                    dest_file = os.path.join(self.html_storage_dir, f"{job_id}.html")

                    # Tái sử dụng HTML đã lưu trong cache nếu có
                    if os.path.exists(dest_file):
                        with open(dest_file, encoding="utf-8") as f:
                            content = f.read()
                        if len(content) > 10000:
                            return {
                                "job_id": job_id,
                                "url": clean_job_url,
                                "html_content": content,
                            }

                    # Polite sleep chống chặn IP
                    delay = random.uniform(3.0, 5.5) if is_retry else random.uniform(2.0, 3.5)
                    time.sleep(delay)

                    detail_context = browser.new_context(
                        user_agent=(
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                        ),
                        viewport={"width": 1920, "height": 1080},
                    )
                    detail_page = detail_context.new_page()
                    content = ""
                    try:
                        detail_page.goto(clean_job_url, wait_until="domcontentloaded", timeout=30000)
                        detail_page.wait_for_timeout(3000)
                        if "Cloudflare" in detail_page.title():
                            detail_page.wait_for_timeout(5000)
                        content = detail_page.content()

                        if self.save_html and "Attention Required" not in content and len(content) > 10000:
                            with open(dest_file, "w", encoding="utf-8") as f:
                                f.write(content)
                    except Exception as err:
                        log.warning("[TopCV] Lỗi tải URL chi tiết %s: %s", clean_job_url, err)
                    finally:
                        detail_page.close()
                        detail_context.close()

                    if content and "Attention Required" not in content and len(content) > 10000:
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
                        log.warning("[TopCV] Chi tiết %s thất bại ở Lượt 1. Đẩy vào Retry Queue.", target["job_id"])
                        retry_queue.append(target)

                    if idx % 10 == 0:
                        log.info("[TopCV] Tiến độ Pha 2: %d/%d (Thành công: %d, Cần retry: %d)", idx, len(main_queue), len(items), len(retry_queue))

                # Lượt 2: Cào lại Retry Queue nếu còn link lỗi
                if retry_queue:
                    log.info("[TopCV] Bắt đầu cào lại %d jobs trong Retry Queue...", len(retry_queue))
                    time.sleep(5.0)  # Nghỉ hồi phục
                    for target in retry_queue:
                        item = fetch_detail(target, is_retry=True)
                        if item:
                            items.append(item)
                            log.info("[TopCV] Cào lại thành công cho Job %s!", target["job_id"])
                        else:
                            # Fallback card nếu detail hoàn toàn không truy cập được
                            log.warning("[TopCV] Job %s vẫn không tải được detail sau retry. Dùng listing fallback.", target["job_id"])
                            items.append({
                                "job_id": target["job_id"],
                                "url": target["url"].split("?")[0],
                                "title": target.get("title"),
                                "company": target.get("company"),
                                "salary": target.get("salary"),
                                "html_snippet": target.get("html_snippet"),
                            })

                browser.close()
        except Exception as exc:
            log.error("[TopCV] Error in Playwright crawling: %s", exc, exc_info=True)

        return items

    def fetch_items(self) -> Generator[dict[str, Any], None, None]:
        """Fetch items từ Playwright và yield từng item."""
        yield from self._sync_fetch_with_playwright()

    def parse_item(self, item: dict[str, Any]) -> JobRecord | None:
        """Bóc tách toàn diện dữ liệu từ HTML chi tiết sang JobRecord chuẩn."""
        job_id = item.get("job_id")
        job_url = item.get("url")
        html_content = item.get("html_content") or item.get("html_snippet")

        if not job_id or not job_url:
            return None

        soup = BeautifulSoup(html_content, "html.parser") if html_content else None

        # 1. Tiêu đề công việc
        title = None
        if soup:
            t_el = soup.select_one(".box-header-job__title, h1.box-header-job__title, h1")
            if t_el:
                title = clean_text(t_el.get_text(separator=" ", strip=True))
                title = re.sub(r"Nhà tuyển dụng\s+đã được xác thực:.*", "", title, flags=re.DOTALL).strip()
        if not title:
            title = clean_text(item.get("title", ""))

        if not title:
            return None

        # 2. Tên công ty (Xử lý bỏ qua thẻ logo rỗng)
        company = None
        if soup:
            c_el = soup.select_one(".company-name-label a, .company-name-label")
            if not c_el:
                for a in soup.select(".box-company-info a[href*='/cong-ty/']"):
                    txt = clean_text(a.get_text(strip=True))
                    if txt and not any(ign in txt.lower() for ign in ["xem trang", "tuyển dụng"]):
                        c_el = a
                        break
            if c_el:
                company = clean_text(c_el.get_text(strip=True))
        if not company:
            company = clean_text(item.get("company", "")) or "Unknown"

        # 3. Mức lương
        salary_text = None
        if soup:
            s_el = soup.select_one(".box-header-job__salary--title, .box-header-job__salary")
            if s_el:
                salary_text = clean_text(s_el.get_text(strip=True))
        if not salary_text:
            salary_text = clean_text(item.get("salary", "")) or "Thoả thuận"

        # Phân tích mức lương chi tiết (chu kỳ trả lương, hoa hồng, thỏa thuận)
        salary_detail = parse_salary_detail(salary_text, title=title)
        sal_min = salary_detail["salary_min"]
        sal_max = salary_detail["salary_max"]
        sal_currency = salary_detail["salary_currency"]

        # 4. Hạn nộp hồ sơ (Deadline)
        d_el = soup.select_one(".box-applied-cv .date, .date")
        deadline_text = clean_text(d_el.get_text(strip=True)) if d_el else None

        # 5. Các khối chi tiết (Hỗ trợ song ngữ Tiếng Việt & Tiếng Anh)
        sections: dict[str, dict[str, str]] = {}
        for sec in soup.select(".box-job-information-detail-item"):
            h2 = sec.select_one(".box-job-information-detail-item__title--title, h2")
            if not h2:
                continue
            h2_title = h2.get_text(strip=True).lower()
            content_box = (
                sec.select_one(
                    ".box-job-information-detail-item__content, .job-description__item--content, .box-job-information-detail-item__text"
                )
                or sec
            )
            raw_html = str(content_box)
            clean_desc = content_box.get_text(separator="\n", strip=True)
            lines = [line.strip() for line in clean_desc.split("\n") if line.strip()]
            if lines and lines[0].lower() == h2_title:
                lines = lines[1:]
            clean_desc = "\n".join(lines)
            sections[h2_title] = {"html": raw_html, "text": clean_desc}

        def get_sec(keywords: list[str], return_html: bool = False) -> str | None:
            for k, v in sections.items():
                if any(kw in k for kw in keywords):
                    return v["html"] if return_html else v["text"]
            return None

        desc_html = get_sec(["job description", "mô tả công việc"], return_html=True) or item.get("html_snippet") or f"<p>{title}</p>"
        desc_text = get_sec(["job description", "mô tả công việc"]) or (strip_html_tags(desc_html) if desc_html else title)
        req_html = get_sec(["candidate requirements", "yêu cầu ứng viên", "yêu cầu"], return_html=True)
        req_text = get_sec(["candidate requirements", "yêu cầu ứng viên", "yêu cầu"])
        ben_html = get_sec(["benefits", "quyền lợi ứng viên", "quyền lợi"], return_html=True)
        ben_text = get_sec(["benefits", "quyền lợi ứng viên", "quyền lợi"])

        # Chuẩn hóa văn bản thành mảng dòng sạch (list[str])
        desc_list = text_to_clean_lines(desc_html or desc_text)
        req_list = text_to_clean_lines(req_html or req_text)
        ben_list = text_to_clean_lines(ben_html or ben_text)

        # 6. Thông tin chung (Key-Value)
        general_info: dict[str, str] = {}
        if soup:
            for item_node in soup.select(".box-job-information-general-info-list__item"):
                parts = [p.strip() for p in item_node.get_text(separator="\n", strip=True).split("\n") if p.strip()]
                if len(parts) >= 2:
                    general_info[parts[0]] = parts[1]

        seniority = general_info.get("Cấp bậc")
        emp_type = general_info.get("Loại hình làm việc") or general_info.get("Hình thức làm việc")

        # 7. Thẻ tags theo 3 nhóm cốt lõi: Yêu cầu, Quyền lợi, Chuyên môn
        tag_requirements: list[str] = []
        tag_benefits: list[str] = []
        tag_skills: list[str] = []
        found_benefits_group = False

        if soup:
            for group in soup.select(".job-tags .job-tags__group"):
                g_name_el = group.select_one(".job-tags__group-name")
                g_name = g_name_el.get_text(strip=True).lower() if g_name_el else ""
                group_items = []
                for a in group.select(".item"):
                    txt = clean_text(a.get_text(strip=True))
                    if txt and not txt.startswith("+") and txt not in group_items:
                        group_items.append(txt)

                if any(kw in g_name for kw in ["yêu cầu", "requirement"]):
                    tag_requirements.extend(group_items)
                elif any(kw in g_name for kw in ["quyền lợi", "benefit", "phúc lợi"]):
                    found_benefits_group = True
                    tag_benefits.extend(group_items)
                elif any(kw in g_name for kw in ["chuyên môn", "specialization", "skill"]):
                    tag_skills.extend(group_items)
                else:
                    tag_skills.extend(group_items)

            # Fallback cho layout không dùng .job-tags__group (như thẻ flat tag cũ)
            if not tag_requirements and not tag_skills and not found_benefits_group:
                flat_tags = []
                for tag_node in soup.select(".job-tags .item, .tag .item-tag, .tag-quickview .item-tag"):
                    txt = clean_text(tag_node.get_text(strip=True))
                    if txt and not txt.startswith("+") and txt not in flat_tags:
                        flat_tags.append(txt)
                if flat_tags:
                    classified_fallback = classify_job_tags(flat_tags)
                    tag_requirements = classified_fallback.get("requirements") or []
                    tag_benefits = classified_fallback.get("benefits") or []
                    found_benefits_group = bool(tag_benefits)
                    tag_skills = classified_fallback.get("skills") or []

        tags_data = {
            "requirements": tag_requirements if tag_requirements else None,
            "benefits": tag_benefits if (found_benefits_group and tag_benefits) else None,
            "skills": tag_skills if tag_skills else None,
        }

        # 8. Địa điểm làm việc & Lịch làm việc
        loc_item = (
            soup.select_one(
                ".box-job-information-address-and-time-list__item:-soup-contains('Location'), "
                ".box-job-information-address-and-time-list__item:-soup-contains('Địa điểm')"
            )
            if soup
            else None
        )
        if loc_item:
            loc_content = loc_item.select_one(".box-job-information-address-and-time-list__item--content")
            loc_text = clean_text(loc_content.get_text(separator=" ", strip=True)) if loc_content else None
        else:
            loc_header = soup.select_one(".box-header-job a[href*='/tim-viec-lam-moi-nhat-tai-']")
            loc_text = clean_text(loc_header.get_text(strip=True)) if loc_header else None

        sched_item = soup.select_one(
            ".box-job-information-address-and-time-list__item:-soup-contains('Work Schedule'), "
            ".box-job-information-address-and-time-list__item:-soup-contains('Thời gian')"
        )
        sched_text = (
            clean_text(sched_item.select_one(".box-job-information-address-and-time-list__item--content").get_text(separator=" ", strip=True))
            if sched_item
            else None
        )

        # 9. Kinh nghiệm & Học vấn
        exp_text = general_info.get("Kinh nghiệm")
        if not exp_text and tag_requirements:
            for t in tag_requirements:
                if any(w in t.lower() for w in ["kinh nghiệm", "experience", "năm"]):
                    exp_text = t
                    break
        edu_text = general_info.get("Học vấn")
        if not edu_text and tag_requirements:
            for t in tag_requirements:
                if any(w in t.lower() for w in ["đại học", "cao đẳng", "thạc sĩ"]):
                    edu_text = t
                    break

        raw_data = {
            "title": title,
            "company": company,
            "salary": salary_detail,
            "tags": tags_data,
            "description_list": desc_list,
            "requirements_list": req_list,
            "benefits_list": ben_list,
            "location_text": loc_text,
            "deadline_text": deadline_text,
            "posted_date_text": "",
            "employment_type_text": emp_type,
            "seniority_text": seniority,
            "extra": {
                "work_schedule": sched_text,
                "education": edu_text,
                "hiring_quantity": general_info.get("Số lượng tuyển"),
                "workplace_type": general_info.get("Hình thức làm việc"),
                "experience": exp_text,
            },
        }

        # Ưu tiên nhận diện ngôn ngữ trên phần nội dung mô tả công việc
        lang = detect_language(desc_text) if desc_text else detect_language(f"{title} {company}")

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
    parser = argparse.ArgumentParser(description="TopCV IT Job Two-Phase Crawler")
    parser.add_argument("--max-items", type=int, default=5, help="Số tin tối đa cần cào")
    parser.add_argument("--output-dir", type=str, default="data", help="Thư mục xuất dữ liệu JSON/JSONL")
    parser.add_argument("--checkpoint-dir", type=str, default=None, help="Thư mục lưu checkpoint")
    parser.add_argument("--save-html", action="store_true", default=False, help="Lưu file HTML chi tiết vào thư mục crawler (mặc định tắt)")
    parser.add_argument("--local-html-dir", type=str, default=None, help="Thư mục chứa HTML cục bộ để parse nhanh không cần mạng")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    crawler = TopCVCrawler(
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
