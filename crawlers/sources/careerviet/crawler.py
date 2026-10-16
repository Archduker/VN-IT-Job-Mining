# -*- coding: utf-8 -*-
"""Crawler nguồn CareerViet (https://careerviet.vn) — Phiên bản chuẩn Data Contract Schema v1.

Hỗ trợ 2 chế độ thu thập:
1. Online: Duyệt danh mục IT (/viec-lam/cntt-phan-mem-c1-vi.html) và tải trang chi tiết via HttpClient.
2. Offline (--local-html-dir): Tải nhanh từ các file HTML đã lưu để test và kiểm thử hồi quy không phụ thuộc mạng.
"""

import argparse
import glob
import hashlib
import json
import logging
import os
import random
import re
import tempfile
from collections import Counter
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from crawlers.base.base_crawler import BaseCrawler
from crawlers.common.http_client import DelayConfig, HttpClient
from crawlers.common.schema import JobRecord
from crawlers.common.url_ledger import UrlLedger
from crawlers.common.utils import (
    clean_text,
    detect_language,
    parse_salary_detail,
    strip_html_tags,
    text_to_clean_lines,
    classify_job_tags,
)
from crawlers.sources.careerviet.raw_envelope import (
    build_raw_envelope,
    container_text_for_hash,
    hash_container_text,
)

log = logging.getLogger("careerviet.crawler")

SOURCE = "careerviet"
CRAWLER_VERSION = "0.5.0"
BASE_URL = "https://careerviet.vn"
CATEGORY_PATH = "/viec-lam/cntt-phan-mem-c1-vi.html"
MAX_PAGES = 30

# mac dinh thu muc cho Phase 1/2 (Ledger & raw envelope) — dat duoi data/careerviet/
DEFAULT_LEDGER_DIR = os.path.join("data", "careerviet", "url_ledger")
DEFAULT_RAW_DIR = os.path.join("data", "careerviet", "raw")
CATEGORY_MAP_FILENAME = "category_by_job_id.json"
# Chi nap 3 nhom IT (c1/c61/keyword:developer); c37 Digital Marketing loai bo o Buoc 1.
URL_FILE_GLOBS = ("urls_c1_*.json", "urls_c61_*.json", "urls_developer_*.json")


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
        ledger_dir: str | None = None,
        raw_dir: str | None = None,
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
        # Phase 1/2 (Ledger + raw envelope). Lazy: KHONG tao dir/doi catalog
        # khi instantiate (tranh phoi nhiễm data/ trong unit test cu).
        self.ledger_dir = ledger_dir or DEFAULT_LEDGER_DIR
        self.raw_dir = raw_dir or DEFAULT_RAW_DIR
        self._ledger: UrlLedger | None = None

    def _get_ledger(self) -> UrlLedger:
        """Trả (và cache) UrlLedger của nguồn. Mức lưu = self.ledger_dir."""
        if self._ledger is None:
            self._ledger = UrlLedger(source=self.source_name, storage_dir=self.ledger_dir)
        return self._ledger

    def _online_client(self) -> HttpClient:
        """Client cho MỌI chế độ ONLINE: delay ngẫu nhiên 2-5s (quy định nhóm),
        một luồng (requests.Session), timeout 25s. HttpClient tự áp delay + retry;
        4xx/5xx raise (raise_on_status=True) để tầng gọi quyết định dừng an toàn."""
        return HttpClient(
            source=self.source_name,
            delay_config=DelayConfig(min_seconds=2.0, max_seconds=5.0),
            timeout=25,
        )

    @staticmethod
    def _is_blocking(exc: Exception) -> bool:
        """429/403 (rate-limit / chặn) -> nên DỪNG cả đợt, không bắn tiếp."""
        resp = getattr(exc, "response", None)
        status = getattr(resp, "status_code", None) if resp is not None else None
        return status in (429, 403)

    @staticmethod
    def _detect_block(html: str) -> tuple[bool, str]:
        """Phat hien trang bi CHAN. Tra ve (blocked, ly_do).

        Chi coi la chan KHI: trang THIEU khoi .job-detail-page DONG THOI co dau hien
        chan ro ret (tieu de 'Access Denied'/'Just a moment', hop captcha, hoac phan
        text hien thi chua cac cum tu do). Chu 'captcha' nam trong <script>/<style>
        cua trang TOT (van con .job-detail-page) se KHONG bi tinh.
        """
        if not html or not html.strip():
            return True, "HTML rong"
        soup = BeautifulSoup(html, "html.parser")
        if soup.select_one(".job-detail-page") is not None:
            return False, ""
        title_el = soup.find("title")
        title_txt = (title_el.get_text() if title_el else "").strip().lower()
        for t in soup(["script", "style", "noscript"]):
            t.decompose()
        body_txt = soup.get_text(" ", strip=True).lower()
        captcha_box = soup.select_one(
            ".g-recaptcha,#captcha,[id^='captcha'],[class*='captcha'],"
            "[class*='cf-challenge'],[id*='cf-challenge']")
        phrases = ("access denied", "just a moment", "too many requests")
        if title_txt and any(ph in title_txt for ph in phrases):
            return True, f"thieu .job-detail-page + tieu de '{title_txt[:60]}'"
        if captcha_box is not None:
            return True, "thieu .job-detail-page + hop captcha"
        if any(ph in body_txt for ph in phrases):
            return True, "thieu .job-detail-page + text hien thi co tu khoa chan"
        return False, ""

    @classmethod
    def _looks_blocked(cls, html: str) -> bool:
        """Tuong thich nguoc: tra ve bool theo _detect_block."""
        return cls._detect_block(html)[0]

    def _dump_blocked_page(self, job_id: str, html: str, reason: str):
        """Luu trang nghi chan ra data/careerviet/_blocked/<job_id>.html (KHONG ghi de,
        KHONG dua vao raw). Tra ve duong dan hoac None neu loi."""
        dest = Path(self.raw_dir).parent / "_blocked" / f"{job_id}.html"
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "x", encoding="utf-8") as fh:  # mode 'x' = khong ghi de
                fh.write(html or "")
            log.warning("[CareerViet] Luu trang NGHI chan %s -> %s (ly do: %s)",
                        job_id, dest, reason)
            return dest
        except FileExistsError:
            log.warning("[CareerViet] _blocked/%s.html da ton tai -> khong ghi de (ly do: %s)",
                        job_id, reason)
            return dest
        except Exception as exc:  # pragma: no cover - disk side
            log.error("[CareerViet] Khong luu duoc _blocked/%s: %s", job_id, exc)
            return None

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

    # ------------------------------------------------------------------
    # PHASE 1 — URL DISCOVERY (khuôn TopCV). Mặc định OFFLINE, không gọi mạng.
    # ------------------------------------------------------------------
    def _load_category_map(self, category_map_path: str | None = None) -> dict[str, str]:
        """Doc category_by_job_id.json (job_id -> source_category). Khong crash."""
        candidates = []
        if category_map_path:
            candidates.append(Path(category_map_path))
        candidates.append(Path(self.ledger_dir) / CATEGORY_MAP_FILENAME)
        for cp in candidates:
            if cp.exists():
                try:
                    return json.loads(cp.read_text(encoding="utf-8"))
                except Exception as exc:  # pragma: no cover - defensive
                    log.warning("[CareerViet] Khong doc duoc category map %s: %s", cp, exc)
        return {}

    @staticmethod
    def _job_id_from_name(filename: str) -> str:
        m = re.search(r"([A-Z0-9]{6,12})\.html?$", filename)
        if m:
            return m.group(1)
        return filename.replace(".html", "")

    def _register_from_urls_dir(
        self, urls_dir: Path, category_map_path: str | None = None
    ) -> int:
        """Offline: nap URL tu cac file urls_c1/c61/developer_*.json (chi doc, khong
        sua file dau vao). Ghi/cap nhat category_by_job_id.json vao THU MUC LEDGER.
        Tra ve so job_id dang ky.
        """
        ledger = self._get_ledger()
        cats: dict[str, str] = self._load_category_map(category_map_path)
        registered_ids: set[str] = set()
        for pattern in URL_FILE_GLOBS:
            for fp in sorted(Path(urls_dir).glob(pattern)):
                try:
                    payload = json.loads(fp.read_text(encoding="utf-8"))
                except Exception as exc:
                    log.warning("[CareerViet] Bo qua file URL %s: %s", fp, exc)
                    continue
                for r in payload.get("records", []):
                    url = r.get("url")
                    jid = r.get("job_id")
                    sc = r.get("source_category")
                    if not url or not jid:
                        continue
                    ledger.register_url(raw_url=url, job_id=jid)
                    registered_ids.add(jid)
                    if sc:
                        cats[jid] = sc
        # Luu category map vao ledger dir (derived output, ghi nguyen tu).
        dest_map = Path(self.ledger_dir) / CATEGORY_MAP_FILENAME
        self._atomic_write_json(dest_map, cats, overwrite=True)
        log.info(
            "[CareerViet] Discovery offline: %d job_id dang ky tu %s", len(registered_ids), urls_dir
        )
        return len(registered_ids)

    def _discover_online(self, max_pages: int | None = None) -> int:
        """[KHONG chay trong dry-run] Duyệt danh mục IT TRÊN MẠNG và ghi URL vào ledger.

        Chỉ được gọi khi có cờ --online tường minh. Một luồng (requests.Session),
        polite delay 2-5s (DelayConfig mà HttpClient tự áp), dừng an toàn khi
        HttpClient raise (429/403 qua raise_for_status) hoặc thấy captcha.
        """
        ledger = self._get_ledger()
        client = self._online_client()
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": BASE_URL,
        }
        pages = max_pages or MAX_PAGES
        added = 0
        try:
            for page in range(1, pages + 1):
                page_url = self._build_page_url(page)
                try:
                    html = client.get_html(page_url, headers=headers)
                except Exception as exc:
                    log.error("[CareerViet] Discovery page %d loi (%s) -> dung an toan.", page, exc)
                    break
                low = (html or "").lower()
                if not html or any(k in low for k in ("captcha", "access denied", "too many requests")):
                    log.warning("[CareerViet] Chan/bot nghi ngờ page %d -> dung an toan.", page)
                    break
                soup = BeautifulSoup(html, "html.parser")
                pairs = []
                for a in soup.select("div.job-item a.job-title, a[href*='/tim-viec-lam/']"):
                    href = a.get("href")
                    if href and re.search(r"\.[A-Z0-9]{6,12}\.html", href):
                        pairs.append((urljoin(BASE_URL, href), a.get_text(strip=True) or None))
                if not pairs:
                    break
                for lu, ttl in pairs:
                    jid = extract_job_id(lu)
                    ledger.register_url(raw_url=lu, job_id=jid, preliminary_title=ttl)
                    added += 1
        finally:
            client.close()
        return added

    def discover_urls(
        self,
        online: bool = False,
        urls_dir: str | None = None,
        category_map_path: str | None = None,
        max_pages: int | None = None,
        sync_minio: bool = False,
    ) -> int:
        """Phase 1: nap/nhat URL vao UrlLedger. Mac Dinh OFFLINE (khong goi mang).

        - offline: neu co urls_dir -> nap tu urls_*.json; nguoc lai giu ledger da nap
          o Buoc 1 (UrlLedger tu doc catalog_master.json khi khoi tao).
        - online (can co=False->True tuong minh): duyet danh muc IT qua _discover_online.
        Ket thuc: save_catalog + export_daily_manifest (+ sync_minio neu bat).
        Tra ve tong so record trong ledger.
        """
        ledger = self._get_ledger()
        if online:
            self._discover_online(max_pages=max_pages)
        elif urls_dir:
            self._register_from_urls_dir(Path(urls_dir), category_map_path=category_map_path)
        ledger.save_catalog()
        ledger.export_daily_manifest()
        if sync_minio:
            ledger.sync_to_minio()
        log.info("[CareerViet] discover_urls hoan tat: %d record trong ledger.", len(ledger.records))
        return len(ledger.records)

    # ------------------------------------------------------------------
    # PHASE 2 — DETAIL EXTRACTION + Raw Envelope. Safe Skip + versioning.
    # ------------------------------------------------------------------
    def _atomic_write_json(self, dest: Path, obj: Any, overwrite: bool = False) -> Path | None:
        """Ghi JSON nguyen tu (temp + os.replace). Mac dinh KHONG ghi de file cu."""
        if dest.exists() and not overwrite:
            return None
        dest.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(dest.parent), prefix=dest.name + ".", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(obj, f, ensure_ascii=False, indent=2)
            os.replace(tmp, dest)
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise
        return dest

    def _process_detail_record(
        self,
        rec: dict[str, Any],
        html: str,
        cat_map: dict[str, str],
        exclude_volatile_dates: bool,
        date_str: str,
    ) -> dict[str, Any]:
        """Xu ly 1 record: tinh hash ( cung co nhu Buoc 2), phat hiện repost, tan
        version, ghi envelope nguyen tu, mark_done. Tra ve dict ket qua.
        """
        ledger = self._get_ledger()
        jid = rec["job_id"]
        cleaned = container_text_for_hash(html, exclude_volatile_dates=exclude_volatile_dates)
        content_hash = hash_container_text(cleaned)

        # Repost: cung content_hash voi MOT tin DONE khac -> khong ghi file moi.
        existing = ledger.find_by_content_hash(content_hash)
        if existing and existing.get("url_hash") != rec.get("url_hash"):
            ledger.mark_done(
                rec["url_hash"],
                content_hash=content_hash,
                repost_of_url_hash=existing["url_hash"],
            )
            return {"tag": "repost", "version": rec.get("latest_version") or 0, "written": False, "path": None}

        curr_ver = int(rec.get("latest_version") or 0)
        same_content = rec.get("content_hash") == content_hash
        new_ver = curr_ver if (same_content and curr_ver > 0) else curr_ver + 1

        source_url = rec.get("canonical_url") or f"{BASE_URL}/vi/tim-viec-lam/job.{jid}.html"
        env = build_raw_envelope(
            html,
            jid,
            source_url,
            source_category=cat_map.get(jid),
            version=new_ver,
            exclude_volatile_dates=exclude_volatile_dates,
        )
        dest = Path(self.raw_dir) / date_str / f"{jid}_v{new_ver}.json"
        written = self._atomic_write_json(dest, env)
        ledger.mark_done(rec["url_hash"], content_hash=content_hash, new_version=new_ver)
        return {
            "tag": "success",
            "version": new_ver,
            "written": written is not None,
            "path": str(dest),
        }

    def _select_pending(
        self,
        ledger: UrlLedger,
        cat_map: dict[str, str],
        source_categories: list[str] | None = None,
        shuffle: bool = False,
        seed: int | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Chon record PENDING/RECHECK_DUE: loc nhom -> xao (seed) -> cat limit.

        Thu tu mac dinh (khong loc, khong xao) = thu tu chen cua ledger, GIU NGUYEN.
        Xao dung random.Random(seed) RIENG, khong dong seed toan cuc.
        Loi --shuffle thieu --seed duoc chan o tang CLI (main), o day seed=None chi
        tao mot rng khong duoc xac dinh -> khong dung trong duong mac dinh.
        Ngu source_category khong khop nhom nao co record duoc chon -> ValueError.
        """
        pending = list(ledger.get_pending_or_due_records(21))
        if source_categories:
            wanted = set(source_categories)
            filtered = [r for r in pending if cat_map.get(r["job_id"]) in wanted]
            if not filtered:
                avail = sorted({c for c in (cat_map.get(r["job_id"]) for r in pending) if c})
                raise ValueError(
                    "source_category %s khong khop voi nhom nao co record duoc chon. "
                    "Cac nhom kha dung: %s" % (sorted(wanted), avail))
            selected = filtered
        else:
            selected = pending
        if shuffle:
            selected = list(selected)
            random.Random(seed).shuffle(selected)
        if limit is not None:
            selected = selected[:limit]
        return selected

    def crawl_details(
        self,
        limit: int | None = None,
        local_html_dir: str | None = None,
        category_map_path: str | None = None,
        exclude_volatile_dates: bool = True,
        online: bool = False,
        sync_minio: bool = False,
        source_categories: list[str] | None = None,
        shuffle: bool = False,
        seed: int | None = None,
    ) -> dict[str, Any]:
        """Phase 2: trich xuat raw envelope cho cac URL PENDING/RECHECK_DUE (21 ngay).

        - OFFLINE (co local_html_dir): duyet theo file HTML co san; moi file can job_id
          nam trong ledger; ngoai ledger -> bao ro, khong xu ly; trong ledger nhung
          chua den han (DONE <21d) -> bo qua.
        - ONLINE (can --online tuong minh): tai trang theo canonical_url cua ledger.
        Safe Skip: loi 1 tin -> mark_failed roi tiep tuc, khong dung ca dot.
        """
        ledger = self._get_ledger()
        cat_map = self._load_category_map(category_map_path)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        stats: dict[str, Any] = {
            "files": 0,
            "success": 0,
            "failed": 0,
            "repost": 0,
            "skipped_not_due": 0,
            "not_in_ledger": [],
            "files_written": 0,
            "versions": {},
        }

        def _tally(outcome: dict[str, Any]) -> None:
            stats["success"] += 1
            if outcome["written"]:
                stats["files_written"] += 1
            v = str(outcome["version"])
            stats["versions"][v] = stats["versions"].get(v, 0) + 1

        # ---- CHON DANH SACH: loc theo nhom -> xao (seed) -> cat limit ----
        try:
            candidates = self._select_pending(
                ledger, cat_map, source_categories, shuffle, seed, limit)
        except ValueError as exc:
            log.error("[CareerViet] %s -> DUNG, khong goi mang, khong luu ledger.", exc)
            print("[CareerViet] DUNG: " + str(exc))
            stats["selection_error"] = str(exc)
            return stats

        sel_ids = [r["job_id"] for r in candidates]
        sel_cat_dist = dict(Counter(cat_map.get(j) for j in sel_ids))
        _mode = "online" if online else ("offline" if local_html_dir else "preview")
        print("[CareerViet] SELECTION mode=%s so_it=%d" % (_mode, len(sel_ids)))
        print("[CareerViet] SELECTION job_ids=%s" % sel_ids)
        print("[CareerViet] SELECTION category_distribution=%s" % sel_cat_dist)
        stats["selected"] = sel_ids
        stats["selected_category_distribution"] = sel_cat_dist

        if local_html_dir:
            job_index = {r["job_id"]: r for r in ledger.records.values()}
            due_ids = {r["job_id"] for r in ledger.get_pending_or_due_records(21)}
            for fp in sorted(Path(local_html_dir).glob("*.html")):
                if limit is not None and (stats["success"] + stats["failed"] + stats["repost"]) >= limit:
                    break
                stats["files"] += 1
                jid = self._job_id_from_name(fp.name)
                rec = job_index.get(jid)
                if rec is None:
                    stats["not_in_ledger"].append(jid)
                    continue
                if jid not in due_ids:
                    stats["skipped_not_due"] += 1
                    continue
                try:
                    html = fp.read_text(encoding="utf-8")
                    outcome = self._process_detail_record(rec, html, cat_map, exclude_volatile_dates, date_str)
                    if outcome["tag"] == "repost":
                        stats["repost"] += 1
                    else:
                        _tally(outcome)
                except Exception as exc:
                    ledger.mark_failed(rec["url_hash"], str(exc))
                    stats["failed"] += 1
                    log.error("[CareerViet] Safe Skip %s: %s", jid, exc)
        elif online:
            headers = {"Accept": "text/html,application/xhtml+xml,*/*;q=0.8", "Referer": BASE_URL}
            client = self._online_client()
            try:
                for rec in candidates:
                    stats["files"] += 1
                    try:
                        html = client.get_html(rec["canonical_url"], headers=headers)
                    except Exception as exc:
                        if self._is_blocking(exc):
                            # 429/403: KHONG mark_failed -> giu PENDING de dot sau thu lai
                            resp = getattr(exc, "response", None)
                            txt = getattr(resp, "text", None) if resp is not None else None
                            if txt:
                                self._dump_blocked_page(
                                    rec["job_id"], txt,
                                    f"HTTP {getattr(resp, 'status_code', '?')}")
                            log.error("[CareerViet] GAP 429/403 %s -> DUNG an toan, GIU PENDING "
                                      "(khong mark_failed): %s", rec["job_id"], exc)
                            break
                        ledger.mark_failed(rec["url_hash"], str(exc))
                        stats["failed"] += 1
                        log.error("[CareerViet] Safe Skip (online fetch) %s: %s", rec["job_id"], exc)
                        continue
                    blocked, reason = self._detect_block(html)
                    if blocked:
                        # nghi chan (thieu container + dau hien ro): KHONG mark_failed -> giu PENDING
                        self._dump_blocked_page(rec["job_id"], html, reason)
                        log.warning("[CareerViet] Nghi bi CHAN %s (%s) -> DUNG an toan, GIU PENDING "
                                    "(khong mark_failed).", rec["job_id"], reason)
                        break
                    try:
                        outcome = self._process_detail_record(rec, html, cat_map, exclude_volatile_dates, date_str)
                        if outcome["tag"] == "repost":
                            stats["repost"] += 1
                        else:
                            _tally(outcome)
                    except Exception as exc:
                        ledger.mark_failed(rec["url_hash"], str(exc))
                        stats["failed"] += 1
                        log.error("[CareerViet] Safe Skip (online parse) %s: %s", rec["job_id"], exc)
            finally:
                client.close()
        else:
            log.info("[CareerViet] PREVIEW (khong --online/khong --local-html-dir): in danh sach "
                     "se xu ly, KHONG goi mang, KHONG luu ledger.")
            return stats

        ledger.save_catalog()
        if sync_minio:
            ledger.sync_to_minio()
        return stats

    def view_ledger(self) -> dict[str, int]:
        """Tom tat trang thai ledger (dung cho CLI --phase view)."""
        ledger = self._get_ledger()
        counts: dict[str, int] = {}
        for rec in ledger.records.values():
            st = rec.get("status", "?")
            counts[st] = counts.get(st, 0) + 1
        print(f"Ledger {self.source_name}: {len(ledger.records)} record; status={counts}")
        return counts


def main():
    parser = argparse.ArgumentParser(description="CareerViet IT Job Crawler (Two-Phase)")
    parser.add_argument(
        "--phase", choices=["discovery", "details", "view"], default="details",
        help="Phase 1 (discovery) / Phase 2 (details) / xem ledger (view)",
    )
    parser.add_argument("--limit", type=int, default=None, help="So chi tiet toi da (details)")
    parser.add_argument("--local-html-dir", type=str, default=None,
                        help="Thu muc HTML cuc bo -> chay offline, KHONG goi mang")
    parser.add_argument("--ledger-dir", type=str, default=DEFAULT_LEDGER_DIR,
                        help="Thu muc UrlLedger")
    parser.add_argument("--raw-dir", type=str, default=DEFAULT_RAW_DIR,
                        help="Thu muc ghi raw envelope (data/careerviet/raw/<date>/...)")
    parser.add_argument("--urls-dir", type=str, default=None,
                        help="Discovery offline: nap tu urls_*.json trong thu muc nay")
    parser.add_argument("--category-map", type=str, default=None,
                        help="Duong dan category_by_job_id.json (optional)")
    parser.add_argument("--max-pages", type=int, default=None, help="Gioi han trang khi --online discovery")
    parser.add_argument("--online", action="store_true", default=False,
                        help="Tuong minh cho phep GOI MANG (mac dinh KHONG)")
    parser.add_argument("--sync-minio", action="store_true", default=False, help="Sync ledger len MinIO")
    parser.add_argument("--exclude-volatile-dates", action=argparse.BooleanOptionalAction,
                        default=True,
                        help="Mac Dinh TRUE: tam bo nhan 'Ngay cap nhat'/'Het han nop' khi bam hash. "
                             "Dung --no-exclude-volatile-dates de bat buoc bam CA 2 nhan.")
    parser.add_argument("--source-category", dest="source_categories", action="append", metavar="CAT",
                        help="Chi chon record thuoc nhom source_category nay (lap duoc nhieu lan, "
                             "vd: --source-category c37_digital_mkt)")
    parser.add_argument("--shuffle", action="store_true",
                        help="Xao tron danh sach da loc TRUOC khi cat --limit (tat dinh theo --seed)")
    parser.add_argument("--seed", type=int, default=None,
                        help="Seed nguyen cho --shuffle (BAT BUOC khi dung --shuffle)")
    # Legacy (giu nguyen de tuong thich, KHONG mac dinh goi mang nua)
    parser.add_argument("--max-items", type=int, default=30, help="[legacy] so tin toi da")
    parser.add_argument("--output-dir", type=str, default="data", help="[legacy] thu muc xuat du lieu")
    parser.add_argument("--checkpoint-dir", type=str, default=None, help="Thu muc checkpoint")
    parser.add_argument("--save-html", action="store_true", default=False, help="[legacy] luu HTML chi tiet")
    args = parser.parse_args()
    if args.shuffle and args.seed is None:
        parser.error("--shuffle can kem --seed <so_nguyen>")

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
        ledger_dir=args.ledger_dir,
        raw_dir=args.raw_dir,
    )

    if args.phase == "discovery":
        if not args.online and not args.urls_dir:
            log.info("[CareerViet] Discovery OFFLINE: khong co --urls-dir -> giu ledger da nap (Buoc 1).")
        total = crawler.discover_urls(
            online=args.online,
            urls_dir=args.urls_dir,
            category_map_path=args.category_map,
            max_pages=args.max_pages,
            sync_minio=args.sync_minio,
        )
        print(f"[discovery] Tong so record trong ledger: {total} (online={args.online})")
    elif args.phase == "details":
        if not args.local_html_dir and not args.online:
            print("[details] PREVIEW (khong --online/khong --local-html-dir): chi in danh sach se "
                  "xu ly, khong goi mang, khong luu ledger.")
        stats = crawler.crawl_details(
            limit=args.limit,
            local_html_dir=args.local_html_dir,
            category_map_path=args.category_map,
            exclude_volatile_dates=args.exclude_volatile_dates,
            online=args.online,
            sync_minio=args.sync_minio,
            source_categories=args.source_categories,
            shuffle=args.shuffle,
            seed=args.seed,
        )
        print("[details] stats =", json.dumps(stats, ensure_ascii=False))
    else:  # view
        crawler.view_ledger()


if __name__ == "__main__":
    main()
