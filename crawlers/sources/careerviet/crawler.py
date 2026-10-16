# -*- coding: utf-8 -*-
"""Crawler nguồn CareerViet (https://careerviet.vn) — Phiên bản Raw As-Is & CDC Versioning (Giai đoạn 1).

LƯU Ý HIỆU NĂNG:
JsonWriter ghi lại toàn bộ mảng JSON sau mỗi bản ghi (flush_per_record=True với atomic replace)
để đảm bảo không bị hỏng file khi crash/mất điện giữa chừng. Tuy nhiên, thao tác này có thể chậm
khi số lượng tin lớn (> 1.000 tin). Nếu cào quy mô lớn trong tương lai, nhóm có thể chuyển sang định dạng JSONL.

TRIẾT LÝ SCHEMA-ON-READ (Giai đoạn 1 theo TASKS.md):
- Cào thô 100% (Raw As-Is): Bảo toàn toàn bộ văn bản gốc trên web, không ép kiểu số, không gọt bullet.
- Lưu cả text lẫn inner HTML cho mô tả (description), yêu cầu (requirements), phúc lợi (benefits).
- Gom toàn bộ cặp nhãn-giá trị phụ vào other_info_raw.
- CDC Versioning: Tính content_hash SHA-256 từ các trường nghiệp vụ thô, tự động phát hiện tin cập nhật
  để nâng version trong cdc_catalog.json và ghi bản ghi mới vào batch JSON.

CHIẾN LƯỢC THU HOẠCH URL (Phase 1):
- Hai danh mục: c1 (Phần mềm) và c61 (Phần cứng/Mạng).
- max_items chia đều cho các danh mục (per_cat_limit = ceil(max_items / n_cats)) để tránh lệch mẫu.
- Nếu một danh mục cạn URL trước hạn, phần còn thiếu được bù từ danh mục tiếp theo.
- CDC (batch_seen_ids + cdc_catalog) đảm bảo không trùng job_id kể cả khi 1 tin xuất hiện ở 2 danh mục.

DANH SÁCH TRƯỜNG THAM GIA CONTENT_HASH:
1. title_raw
2. company_raw
3. salary_raw
4. location_raw
5. experience_raw
6. seniority_raw
7. employment_type_raw
8. deadline_raw
9. description_raw
10. requirements_raw
11. benefits_raw
12. tags_raw (chuẩn hoá khoảng trắng, sắp xếp tăng dần trước khi hash)
13. other_info_raw (chuẩn hoá khoảng trắng, sắp xếp key tăng dần trước khi hash)

(Loại trừ: job_id, url, crawled_at, version, content_hash, batch_id).
"""

import argparse
import glob
import hashlib
import json
import logging
import os
import re
from collections.abc import Generator
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from crawlers.base.base_crawler import BaseCrawler
from crawlers.common.http_client import DelayConfig, HttpClient
from crawlers.common.json_writer import JsonWriter

try:
    from .url_provider import BaseUrlProvider, LocalFileUrlProvider
except ImportError:
    from crawlers.sources.careerviet.url_provider import BaseUrlProvider, LocalFileUrlProvider

log = logging.getLogger("careerviet.crawler")

SOURCE = "careerviet"
CRAWLER_VERSION = "1.0.0-raw-cdc"
BASE_URL = "https://careerviet.vn"
MAX_PAGES = 100


def get_next_batch_seq(output_dir: str | Path, source_name: str, run_date: date) -> int:
    """Xác định số thứ tự batch tiếp theo để đảm bảo lần chạy mới
    nối tiếp số thứ tự file mới, không bao giờ ghi đè file batch cũ.
    """
    partition_dir = Path(output_dir) / source_name / f"dt={run_date.isoformat()}"
    if not partition_dir.exists():
        return 1

    existing_seqs: list[int] = []
    for fn in os.listdir(partition_dir):
        m = re.match(r"^batch_(\d+)\.json$", fn)
        if m:
            seq = int(m.group(1))
            fp = partition_dir / fn
            try:
                if fp.stat().st_size > 0:
                    with open(fp, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list) and len(data) > 0:
                            existing_seqs.append(seq)
            except Exception:
                existing_seqs.append(seq)

    if not existing_seqs:
        return 1
    return max(existing_seqs) + 1


def extract_job_id(url: str) -> str:
    """Trích xuất ID job duy nhất từ URL của CareerViet."""
    match = re.search(r"\.([A-Z0-9]{6,12})\.html", url)
    if match:
        return match.group(1)
    match2 = re.search(r"/(\d{5,12})(?:\.html)?$", url)
    if match2:
        return match2.group(1)
    return hashlib.md5(url.encode()).hexdigest()[:8].upper()


def normalize_text_for_hash(val: Any) -> str:
    """Chuẩn hóa khoảng trắng và định dạng trước khi tính hash."""
    if val is None:
        return ""
    if isinstance(val, str):
        return re.sub(r"\s+", " ", val).strip()
    if isinstance(val, list):
        cleaned = [normalize_text_for_hash(x) for x in val if x is not None]
        return ",".join(sorted(cleaned))
    if isinstance(val, dict):
        pairs = [f"{normalize_text_for_hash(k)}:{normalize_text_for_hash(v)}" for k, v in sorted(val.items())]
        return ";".join(pairs)
    return str(val).strip()


def compute_content_hash(raw_fields: dict[str, Any]) -> str:
    """Tính mã SHA-256 từ các trường nội dung nghiệp vụ thô.

    Danh sách trường tham gia hash:
        - title_raw
        - company_raw
        - salary_raw
        - location_raw
        - experience_raw
        - seniority_raw
        - employment_type_raw
        - deadline_raw
        - description_raw
        - requirements_raw
        - benefits_raw
        - tags_raw (sắp xếp tăng dần trước khi hash)
        - other_info_raw (sắp xếp key tăng dần trước khi hash)

    Loại trừ: job_id, url, crawled_at, version, content_hash, batch_id.
    """
    hash_fields = [
        "title_raw",
        "company_raw",
        "salary_raw",
        "location_raw",
        "experience_raw",
        "seniority_raw",
        "employment_type_raw",
        "deadline_raw",
        "description_raw",
        "requirements_raw",
        "benefits_raw",
        "tags_raw",
        "other_info_raw",
    ]
    parts = [normalize_text_for_hash(raw_fields.get(fld)) for fld in hash_fields]
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def clean_short_text(el_or_text: Any) -> str:
    """Lấy văn bản và chuẩn hóa khoảng trắng, tránh dính chữ do thẻ con hoặc comment HTML."""
    if not el_or_text:
        return ""
    if hasattr(el_or_text, "get_text"):
        raw = el_or_text.get_text(separator=" ", strip=True)
    else:
        raw = str(el_or_text)
    return re.sub(r"\s+", " ", raw).strip()


class CareerVietCrawler(BaseCrawler):
    """Crawler cho nguồn CareerViet lưu trữ Raw As-Is và quản lý CDC Versioning."""

    source_name = SOURCE
    crawler_version = CRAWLER_VERSION

    def __init__(
        self,
        checkpoint_dir: str | None = None,
        output_dir: str | None = "data/raw",
        max_items: int | None = 30,
        checkpoint_interval: int = 10,
        batch_size: int = 200,
        batch_seq: int | None = None,
        http_client: HttpClient | None = None,
        save_html: bool = False,
        html_storage_dir: str | None = None,
        local_html_dir: str | None = None,
        url_provider: BaseUrlProvider | None = None,
        url_files: list[str | Path] | None = None,
        max_pages: int | None = None,
        catalog_path: str | None = None,
    ) -> None:
        super().__init__(
            checkpoint_dir=checkpoint_dir,
            output_dir=output_dir,
            max_items=max_items,
            checkpoint_interval=checkpoint_interval,
        )
        self.output_dir = output_dir or "data/raw"
        self.batch_size = batch_size
        self.run_date = date.today()

        # Xác định batch_seq: nếu truyền vào thì ưu tiên, nếu không thì tự tính số tiếp theo
        if batch_seq is not None:
            self.batch_seq = batch_seq
        else:
            self.batch_seq = get_next_batch_seq(self.output_dir, self.source_name, self.run_date)

        # Tái sử dụng JsonWriter với validate_schema=False để xuất dữ liệu raw nguyên bản
        self.writer = JsonWriter(
            source=self.source_name,
            output_dir=self.output_dir,
            run_date=self.run_date,
            batch_seq=self.batch_seq,
            validate_schema=False,
            flush_per_record=True,
        )
        from crawlers.common.utils import make_batch_id
        self.batch_id = make_batch_id(self.source_name, seq=self.writer.batch_seq, run_date=self.writer.run_date)
        self.current_batch_records: int = len(self.writer.records)

        # Cấu hình URL Provider (nếu cung cấp)
        if url_provider is not None:
            self.url_provider: BaseUrlProvider | None = url_provider
        elif url_files is not None:
            self.url_provider = LocalFileUrlProvider(file_paths=url_files, base_dir=self.output_dir)
        else:
            self.url_provider = None

        self.max_pages = max_pages or MAX_PAGES
        self.http_client = http_client or HttpClient(
            source=self.source_name,
            delay_config=DelayConfig(min_seconds=2.0, max_seconds=5.0),
            timeout=25,
        )
        self.save_html = save_html
        self.html_storage_dir = html_storage_dir or os.path.join(self.output_dir, self.source_name, "html")
        self.local_html_dir = local_html_dir
        self.catalog_path = catalog_path or os.path.join(self.output_dir, self.source_name, "cdc_catalog.json")
        self.cdc_catalog: dict[str, Any] = {}

    def _write_record(self, record_to_write: dict[str, Any]) -> bool:
        """Ghi bản ghi vào batch file hiện tại.
        Nếu số bản ghi trong batch đạt batch_size (chuẩn batch-200),
        đóng file hiện tại và mở file batch kế tiếp (không bao giờ ghi đè file cũ).
        """
        if self.current_batch_records >= self.batch_size:
            if self.writer:
                self.writer.close()
            self.batch_seq += 1
            self.writer = JsonWriter(
                source=self.source_name,
                output_dir=self.output_dir,
                run_date=self.run_date,
                batch_seq=self.batch_seq,
                validate_schema=False,
                flush_per_record=True,
            )
            from crawlers.common.utils import make_batch_id
            self.batch_id = make_batch_id(self.source_name, seq=self.writer.batch_seq, run_date=self.writer.run_date)
            self.current_batch_records = len(self.writer.records)

        success = self.writer.write(record_to_write)
        if success:
            self.current_batch_records += 1
        return success

    def _load_cdc_catalog(self) -> None:
        """Nạp catalog CDC từ đĩa nếu tồn tại."""
        if os.path.exists(self.catalog_path):
            try:
                with open(self.catalog_path, "r", encoding="utf-8") as f:
                    self.cdc_catalog = json.load(f)
                log.info("[CareerViet] Đã nạp CDC catalog (%d entries) từ %s", len(self.cdc_catalog), self.catalog_path)
            except Exception as exc:
                log.warning("[CareerViet] Lỗi khi nạp CDC catalog: %s. Khởi tạo mới.", exc)
                self.cdc_catalog = {}
        else:
            self.cdc_catalog = {}

    def _reconcile_catalog_with_batches(self) -> int:
        """Đối soát tự động khi khởi động (Self-healing startup reconciliation):
        Quét toàn bộ các batch JSON đã có trên đĩa.
        Nếu phát hiện bản ghi nào (job_id, content_hash) đã nằm trong batch file
        nhưng catalog chưa kịp ghi nhận (do tiến trình bị ngắt/kill giữa hai bước
        ghi batch và ghi catalog), crawler sẽ tự động bổ sung bản ghi đó vào cdc_catalog
        với status='active', coi là đã cào để không bao giờ bị cào hoặc ghi trùng lặp ở lần chạy sau.
        """
        reconciled_count = 0
        search_dirs = [
            Path(self.output_dir) / self.source_name,
            Path(self.output_dir),
        ]
        scanned_dirs: set[Path] = set()

        for sdir in search_dirs:
            if not sdir.exists():
                continue
            for dt_dir in sdir.glob("dt=*"):
                if not dt_dir.is_dir() or dt_dir in scanned_dirs:
                    continue
                scanned_dirs.add(dt_dir)
                for batch_file in dt_dir.glob("batch_*.json"):
                    if not batch_file.is_file() or batch_file.stat().st_size == 0:
                        continue
                    try:
                        with open(batch_file, "r", encoding="utf-8") as bf:
                            records = json.load(bf)
                        if not isinstance(records, list):
                            continue
                        for rec in records:
                            tech = rec.get("_technical")
                            if not isinstance(tech, dict):
                                continue
                            job_id = tech.get("job_id")
                            content_hash = tech.get("content_hash")
                            if not job_id or not content_hash:
                                continue

                            if job_id not in self.cdc_catalog:
                                version = tech.get("version", 1)
                                crawled_at = tech.get("crawled_at") or datetime.now(timezone.utc).isoformat()
                                self.cdc_catalog[job_id] = {
                                    "job_id": job_id,
                                    "url": tech.get("url", ""),
                                    "source_category": tech.get("source_category"),
                                    "current_version": version,
                                    "current_hash": content_hash,
                                    "status": "active",
                                    "first_seen_at": crawled_at,
                                    "last_seen_at": crawled_at,
                                    "history": [
                                        {
                                            "version": version,
                                            "content_hash": content_hash,
                                            "crawled_at": crawled_at,
                                        }
                                    ],
                                }
                                self.checkpoint.mark_seen(job_id)
                                reconciled_count += 1
                    except Exception as exc:
                        log.warning("[CareerViet] Lỗi đọc batch file khi đối soát %s: %s", batch_file, exc)

        if reconciled_count > 0:
            log.info(
                "[CareerViet] Đối soát khởi động: Đã phục hồi và bổ sung %d bản ghi từ batch vào catalog",
                reconciled_count,
            )
            self._save_cdc_catalog()
            self.checkpoint.save()

        return reconciled_count

    def _save_cdc_catalog(self) -> None:
        """Ghi atomic catalog CDC xuống đĩa."""
        try:
            os.makedirs(os.path.dirname(self.catalog_path), exist_ok=True)
            tmp_path = f"{self.catalog_path}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.cdc_catalog, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.catalog_path)
        except Exception as exc:
            log.error("[CareerViet] Lỗi khi lưu atomic CDC catalog %s: %s", self.catalog_path, exc)

    def _save_raw_html(self, job_id: str, html: str) -> None:
        """Lưu full HTML bài đăng khi cờ save_html=True."""
        try:
            os.makedirs(self.html_storage_dir, exist_ok=True)
            file_path = os.path.join(self.html_storage_dir, f"{job_id}.html")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html)
        except Exception as exc:
            log.warning("[CareerViet] Không thể lưu file HTML cho job %s: %s", job_id, exc)

    def _build_page_url(self, page_fmt: str, base_path: str, page: int) -> str:
        if page <= 1:
            return f"{BASE_URL}{base_path}"
        return f"{BASE_URL}{page_fmt.format(page=page)}"

    def fetch_items(self) -> Generator[dict[str, Any], None, None]:
        """Thu thập danh sách items từ web trực tuyến hoặc từ thư mục HTML cục bộ."""
        # 1. Chế độ đọc file HTML cục bộ (Offline testing)
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
                    "source_category": "offline_test",
                }
                yielded += 1
                if self.max_items and yielded >= self.max_items:
                    break
            return

        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": BASE_URL,
        }

        # 2. Chế độ nạp danh sách URLs từ UrlProvider (urls_c1_*.json, urls_c61_*.json, urls_developer_*.json...)
        if self.url_provider:
            log.info("[CareerViet] ==================== NẠP URLs TỪ URL PROVIDER ====================")
            targets = self.url_provider.get_target_jobs()
            log.info("[CareerViet] UrlProvider cung cấp %d jobs mục tiêu", len(targets))
            yielded_total = 0
            for idx, target in enumerate(targets, start=1):
                jid = target["job_id"]
                jurl = target["url"]
                scat = target.get("source_category", "unknown")

                try:
                    detail_html = self.http_client.get_html(jurl, headers=headers)
                    if self.save_html and detail_html:
                        self._save_raw_html(jid, detail_html)

                    yield {
                        "job_id": jid,
                        "url": jurl,
                        "html": detail_html,
                        "source_category": scat,
                    }
                    yielded_total += 1
                    if self.max_items and yielded_total >= self.max_items:
                        return
                except Exception as exc:
                    log.error("[CareerViet] Lỗi tải job detail %s (%d/%d): %s", jurl, idx, len(targets), exc)
                    continue
            return

        # 3. Chế độ cào danh mục trực tuyến từ web (Fallback)
        categories = [
            {
                "name": "CNTT - Phần mềm",
                "code": "c1",
                "base": "/viec-lam/cntt-phan-mem-c1-vi.html",
                "page_fmt": "/viec-lam/cntt-phan-mem-c1-trang-{page}-vi.html",
            },
            {
                "name": "CNTT - Phần cứng / Mạng",
                "code": "c61",
                "base": "/viec-lam/cntt-phan-cung-mang-c61-vi.html",
                "page_fmt": "/viec-lam/cntt-phan-cung-mang-c61-trang-{page}-vi.html",
            },
        ]

        seen_urls = set()
        harvested_targets: list[dict[str, str]] = []

        # Chia đều max_items theo số danh mục để tránh lệch mẫu.
        # per_cat_limit = ceil(max_items / n_cats). Phần dư sẽ được bù bởi cat sau.
        import math
        n_cats = len(categories)
        per_cat_limit: int | None = None
        if self.max_items:
            per_cat_limit = math.ceil(self.max_items / n_cats)

        log.info("[CareerViet] ==================== BẮT ĐẦU PHA 1: THU HOẠCH URLs ====================")
        log.info("[CareerViet] max_items=%s, n_cats=%d, per_cat_limit=%s",
                 self.max_items, n_cats, per_cat_limit)

        for cat in categories:
            cat_name = cat["name"]
            cat_code = cat["code"]
            cat_urls: list[dict[str, str]] = []
            # Hạn trên cho danh mục này: per_cat_limit + phần bù nếu cat trước chưa đủ
            remaining = (self.max_items - len(harvested_targets)) if self.max_items else None
            cat_limit = min(per_cat_limit or remaining or 10**9, remaining or 10**9) if remaining is not None else None

            for page in range(1, self.max_pages + 1):
                page_url = self._build_page_url(cat["page_fmt"], cat["base"], page)
                try:
                    html = self.http_client.get_html(page_url, headers=headers)
                except Exception as exc:
                    log.error("[CareerViet] Failed to fetch page %d [%s]: %s", page, cat_name, exc)
                    break

                soup = BeautifulSoup(html, "html.parser")
                page_links = []
                for a_tag in soup.select("div.job-item a.job-title, a[href*='/tim-viec-lam/']"):
                    href = a_tag.get("href")
                    if href and re.search(r"\.[A-Z0-9]{6,12}\.html", href):
                        full_url = urljoin(BASE_URL, href)
                        if full_url not in seen_urls:
                            seen_urls.add(full_url)
                            page_links.append({"url": full_url, "source_category": cat_code})

                if not page_links:
                    break

                cat_urls.extend(page_links)
                if cat_limit and len(cat_urls) >= cat_limit:
                    break

            log.info("[CareerViet] Danh mục '%s': thu hoạch %d URLs", cat_name, len(cat_urls))
            harvested_targets.extend(cat_urls)

            # Nếu đã đủ max_items tổng thể thì dừng
            if self.max_items and len(harvested_targets) >= self.max_items:
                break

        log.info("[CareerViet] Tổng URLs thu hoạch được: %d", len(harvested_targets))
        log.info("[CareerViet] ==================== BẮT ĐẦU PHA 2: CÀO CHI TIẾT ====================")

        yielded_total = 0
        for idx, item_target in enumerate(harvested_targets, start=1):
            jurl = item_target["url"]
            scat = item_target.get("source_category", "c1")
            jid = extract_job_id(jurl)

            try:
                detail_html = self.http_client.get_html(jurl, headers=headers)
                if self.save_html and detail_html:
                    self._save_raw_html(jid, detail_html)

                yield {
                    "job_id": jid,
                    "url": jurl,
                    "html": detail_html,
                    "source_category": scat,
                }
                yielded_total += 1
                if self.max_items and yielded_total >= self.max_items:
                    return
            except Exception as exc:
                log.error("[CareerViet] Failed to fetch job detail %s (%d/%d): %s", jurl, idx, len(harvested_targets), exc)
                continue

    def parse_item(self, item: dict[str, Any]) -> dict[str, Any] | None:
        """Bóc tách dữ liệu thô nguyên bản (Raw As-Is) không ép schema."""
        job_id = item.get("job_id")
        job_url = item.get("url")
        html = item.get("html")
        if not job_id or not job_url or not html:
            return None

        source_category = item.get("source_category", "unknown")

        # Kiểm tra tin bị gỡ hoặc hết hạn
        html_lower = html.lower()
        is_expired = any(k in html_lower for k in [
            "việc làm đã hết hạn",
            "tin tuyển dụng không tồn tại",
            "công việc này đã ngưng nhận hồ sơ",
            "thông báo tuyển dụng này đã hết hạn",
        ])

        soup = BeautifulSoup(html, "html.parser")
        page = soup.find(class_="job-detail-page") or soup

        # 1. Tiêu đề công việc nguyên bản
        title_el = (
            page.find("h1")
            or page.select_one(".title, .job-title")
            or page.find("h2")
        )
        title_raw = clean_short_text(title_el)
        if not title_raw:
            t_tag = soup.find("title")
            title_raw = clean_short_text(t_tag).split("-")[0].strip() if t_tag else ""

        # 2. Tên công ty nguyên bản
        comp_tag = page.select_one("a.employer, a.job-company-name, .company-name, a.company")
        if not comp_tag and title_el:
            comp_tag = title_el.find_next("a")
        company_raw = clean_short_text(comp_tag)

        # 3. Các trường metadata trong .detail-box
        salary_raw = ""
        location_raw = ""
        experience_raw = ""
        seniority_raw = ""
        employment_type_raw = ""
        posted_date_raw = ""
        deadline_raw = ""
        other_info_raw: dict[str, str] = {}

        for li in page.select(".detail-box li, .box-item li, ul.list-info li"):
            text_full = clean_short_text(li)
            text_lower = text_full.lower()
            p_tag = li.find("p")
            val = clean_short_text(p_tag) if p_tag else text_full

            # Trích xuất nhãn
            label = ""
            for tag in li.find_all(["strong", "span", "b", "h4"]):
                if tag != p_tag:
                    label = clean_short_text(tag).rstrip(":")
                    break
            if not label and ":" in text_full:
                label = text_full.split(":", 1)[0].strip()

            if "lương" in text_lower:
                salary_raw = re.sub(r"^(lương\s*:?|:\s*)", "", val, flags=re.IGNORECASE).strip() or val
            elif "địa điểm" in text_lower and not location_raw:
                location_raw = re.sub(r"^(địa điểm\s*:?|:\s*)", "", val, flags=re.IGNORECASE).strip() or val
            elif "kinh nghiệm" in text_lower and not experience_raw:
                experience_raw = re.sub(r"^(kinh nghiệm\s*:?|:\s*)", "", val, flags=re.IGNORECASE).strip() or val
            elif "cấp bậc" in text_lower and not seniority_raw:
                seniority_raw = re.sub(r"^(cấp bậc\s*:?|:\s*)", "", val, flags=re.IGNORECASE).strip() or val
            elif "hình thức" in text_lower and not employment_type_raw:
                employment_type_raw = re.sub(r"^(hình thức\s*:?|:\s*)", "", val, flags=re.IGNORECASE).strip() or val
            elif "ngày cập nhật" in text_lower and not posted_date_raw:
                posted_date_raw = re.sub(r"^(ngày cập nhật\s*:?|:\s*)", "", val, flags=re.IGNORECASE).strip() or val
            elif any(k in text_lower for k in ["hết hạn nộp", "hạn nộp"]) and not deadline_raw:
                deadline_raw = re.sub(r"^(hết hạn nộp|hạn nộp)\s*:?", "", val, flags=re.IGNORECASE).strip() or val
            else:
                key_name = label or f"info_{len(other_info_raw) + 1}"
                other_info_raw[key_name] = val

        # Lấy địa điểm từ div.map (tất cả các tỉnh/thành qua <p>, nối dấu phẩy nếu nhiều tỉnh/thành)
        if not location_raw:
            map_p = page.select_one("div.map p")
            if map_p:
                a_tags = [clean_short_text(a) for a in map_p.find_all("a")]
                if a_tags:
                    location_raw = ", ".join(a_tags)
                else:
                    location_raw = clean_short_text(map_p)

        # 4. Các khối chi tiết (lưu cả text thô và inner HTML)
        desc_text_raw = ""
        desc_html_raw = ""
        req_text_raw = ""
        req_html_raw = ""
        ben_text_raw = ""
        ben_html_raw = ""

        sections = page.select(".detail-row, .job-description, .job-detail-content .row")
        for s in sections:
            header = s.find(["h2", "h3", "h4"])
            htext = header.get_text(strip=True).lower() if header else ""
            html_chunk = str(s)
            text_chunk = s.get_text(separator="\n", strip=True)

            if any(k in htext for k in ["mô tả", "job description"]):
                desc_text_raw = text_chunk
                desc_html_raw = html_chunk
            elif any(k in htext for k in ["yêu cầu", "requirements", "requirement"]):
                req_text_raw = text_chunk
                req_html_raw = html_chunk
            elif any(k in htext for k in ["phúc lợi", "quyền lợi", "benefits", "benefit"]):
                ben_text_raw = text_chunk
                ben_html_raw = html_chunk
            elif any(k in htext for k in ["thông tin khác", "other info"]):
                for li_item in s.find_all("li"):
                    txt = clean_short_text(li_item)
                    if ":" in txt:
                        k, v = txt.split(":", 1)
                        other_info_raw[clean_short_text(k)] = clean_short_text(v)
                    else:
                        other_info_raw[f"other_{len(other_info_raw) + 1}"] = txt
            else:
                if header and htext:
                    other_info_raw[header.get_text(strip=True)] = text_chunk

        # 5. Thẻ tags nguyên bản
        tags_raw = []
        for a in page.select(".job-tags a, .tag-item a, .tag-item, .job-tags li"):
            txt = clean_short_text(a)
            if txt and txt not in tags_raw and not txt.startswith("+"):
                tags_raw.append(txt)

        raw_fields = {
            "title_raw": title_raw,
            "company_raw": company_raw,
            "salary_raw": salary_raw,
            "location_raw": location_raw,
            "experience_raw": experience_raw,
            "seniority_raw": seniority_raw,
            "employment_type_raw": employment_type_raw,
            "posted_date_raw": posted_date_raw,
            "deadline_raw": deadline_raw,
            "description_raw": desc_text_raw,
            "description_html_raw": desc_html_raw,
            "requirements_raw": req_text_raw,
            "requirements_html_raw": req_html_raw,
            "benefits_raw": ben_text_raw,
            "benefits_html_raw": ben_html_raw,
            "tags_raw": tags_raw,
            "other_info_raw": other_info_raw,
        }

        # 6. Trích xuất JSON-LD JobPosting nguyên bản (nếu có)
        embedded_json_raw = None
        try:
            jp_script = soup.find("script", id="job-posting-schema")
            if not jp_script:
                for s in soup.find_all("script", type="application/ld+json"):
                    if s.string and '"JobPosting"' in s.string:
                        jp_script = s
                        break
            if jp_script and jp_script.string:
                loaded = json.loads(jp_script.string.strip())
                if isinstance(loaded, dict) and loaded.get("@type") == "JobPosting":
                    embedded_json_raw = loaded
                elif isinstance(loaded, list):
                    for el in loaded:
                        if isinstance(el, dict) and el.get("@type") == "JobPosting":
                            embedded_json_raw = el
                            break
                    if embedded_json_raw is None and loaded:
                        embedded_json_raw = loaded
                elif isinstance(loaded, dict):
                    embedded_json_raw = loaded
        except Exception as exc:
            log.debug("[CareerViet] Không thể nạp JSON-LD JobPosting cho job %s: %s", job_id, exc)
            embedded_json_raw = None

        content_hash = compute_content_hash(raw_fields)
        crawled_at = datetime.now(timezone.utc).isoformat()

        return {
            "_technical": {
                "job_id": job_id,
                "source": self.source_name,
                "url": job_url,
                "crawled_at": crawled_at,
                "content_hash": content_hash,
                "version": 1,
                "source_category": source_category,
            },
            "raw_fields": raw_fields,
            "embedded_json_raw": embedded_json_raw,
            "_is_expired": is_expired,
        }

    def run(self) -> dict[str, Any]:
        """Thực thi pipeline cào Raw As-Is với CDC Versioning."""
        log.info(
            "Starting CareerViet Raw CDC crawl (max_items=%s, output_dir=%s, batch_size=%s, batch_seq=%s)",
            self.max_items,
            self.output_dir,
            self.batch_size,
            self.batch_seq,
        )

        self._load_cdc_catalog()
        self._reconcile_catalog_with_batches()
        batch_seen_ids: set[str] = set()

        for raw_item in self.fetch_items():
            if self.max_items is not None and self.crawled_count >= self.max_items:
                log.info("Reached target max_items (%d). Stopping.", self.max_items)
                break

            job_id = raw_item.get("job_id")
            if not job_id:
                continue

            # Chống trùng lặp ngay trong cùng 1 lần cào (batch-level deduplication)
            if job_id in batch_seen_ids:
                self.skipped_count += 1
                continue
            batch_seen_ids.add(job_id)

            if self.save_html and raw_item.get("html"):
                self._save_raw_html(job_id, raw_item["html"])

            try:
                parsed = self.parse_item(raw_item)
                if not parsed:
                    self.skipped_count += 1
                    continue

                # 1. Xử lý tin bị gỡ hoặc hết hạn
                if parsed.get("_is_expired"):
                    if job_id in self.cdc_catalog:
                        self.cdc_catalog[job_id]["status"] = "expired"
                        self.cdc_catalog[job_id]["last_seen_at"] = datetime.now(timezone.utc).isoformat()
                        self._save_cdc_catalog()
                    self.skipped_count += 1
                    continue

                content_hash = parsed["_technical"]["content_hash"]
                crawled_at = parsed["_technical"]["crawled_at"]
                source_category = parsed["_technical"].get("source_category")

                # 2. Xử lý CDC
                if job_id not in self.cdc_catalog:
                    # Trường hợp 1: Tin mới
                    version = 1
                    parsed["_technical"]["version"] = version
                    self.cdc_catalog[job_id] = {
                        "job_id": job_id,
                        "url": parsed["_technical"]["url"],
                        "source_category": source_category,
                        "current_version": version,
                        "current_hash": content_hash,
                        "status": "active",
                        "first_seen_at": crawled_at,
                        "last_seen_at": crawled_at,
                        "history": [
                            {
                                "version": version,
                                "content_hash": content_hash,
                                "crawled_at": crawled_at,
                            }
                        ],
                    }
                    record_to_write = {
                        "_technical": parsed["_technical"],
                        "raw_fields": parsed["raw_fields"],
                        "embedded_json_raw": parsed.get("embedded_json_raw"),
                    }
                    self._write_record(record_to_write)
                    self.checkpoint.mark_seen(job_id)
                    self.crawled_count += 1

                    # Yêu cầu a: Ghi catalog & checkpoint ngay sau mỗi bản ghi được ghi vào batch (atomic consistency)
                    self._save_cdc_catalog()
                    self.checkpoint.save()

                elif self.cdc_catalog[job_id].get("current_hash") == content_hash:
                    # Trường hợp 2: Tin không đổi nội dung
                    self.cdc_catalog[job_id]["last_seen_at"] = crawled_at
                    self.cdc_catalog[job_id]["status"] = "active"
                    if source_category and not self.cdc_catalog[job_id].get("source_category"):
                        self.cdc_catalog[job_id]["source_category"] = source_category
                    self.checkpoint.mark_seen(job_id)
                    self.skipped_count += 1

                else:
                    # Trường hợp 3: Tin bị sửa nội dung -> tăng version
                    old_version = self.cdc_catalog[job_id].get("current_version", 1)
                    new_version = old_version + 1
                    parsed["_technical"]["version"] = new_version
                    self.cdc_catalog[job_id]["current_version"] = new_version
                    self.cdc_catalog[job_id]["current_hash"] = content_hash
                    self.cdc_catalog[job_id]["last_seen_at"] = crawled_at
                    self.cdc_catalog[job_id]["status"] = "active"
                    if source_category:
                        self.cdc_catalog[job_id]["source_category"] = source_category
                    self.cdc_catalog[job_id].setdefault("history", []).append({
                        "version": new_version,
                        "content_hash": content_hash,
                        "crawled_at": crawled_at,
                    })
                    record_to_write = {
                        "_technical": parsed["_technical"],
                        "raw_fields": parsed["raw_fields"],
                        "embedded_json_raw": parsed.get("embedded_json_raw"),
                    }
                    self._write_record(record_to_write)
                    self.checkpoint.mark_seen(job_id)
                    self.crawled_count += 1

                    # Yêu cầu a: Ghi catalog & checkpoint ngay sau mỗi bản ghi được ghi vào batch (atomic consistency)
                    self._save_cdc_catalog()
                    self.checkpoint.save()

                # Flush log tiến độ định kỳ
                if (self.crawled_count + self.skipped_count) % self.checkpoint_interval == 0:
                    log.info(
                        "[%s] Tiến độ: %d cào mới/cập nhật, %d bỏ qua",
                        self.source_name,
                        self.crawled_count,
                        self.skipped_count,
                    )

            except Exception as exc:
                self.error_count += 1
                log.error("[%s] Lỗi xử lý item %s: %s", self.source_name, job_id, exc, exc_info=True)

        # Kết thúc và đóng file an toàn
        self._save_cdc_catalog()
        self.checkpoint.save()
        if self.writer:
            self.writer.close()

        stats = {
            "source": self.source_name,
            "crawled": self.crawled_count,
            "skipped": self.skipped_count,
            "errors": self.error_count,
            "total_seen": len(self.cdc_catalog),
            "output_file": str(self.writer.file_path) if self.writer and self.writer.file_path else None,
        }
        log.info("[%s] Hoàn tất đợt cào: %s", self.source_name, stats)
        return stats


def main():
    parser = argparse.ArgumentParser(description="CareerViet Raw CDC IT Job Crawler")
    parser.add_argument("--max-items", type=int, default=30, help="Số tin tối đa cần cào")
    parser.add_argument("--output-dir", type=str, default="data/raw", help="Thư mục xuất dữ liệu raw")
    parser.add_argument("--checkpoint-dir", type=str, default=None, help="Thư mục lưu checkpoint")
    parser.add_argument("--save-html", action="store_true", default=False, help="Lưu file HTML chi tiết")
    parser.add_argument("--local-html-dir", type=str, default=None, help="Thư mục chứa HTML cục bộ")
    parser.add_argument("--batch-size", type=int, default=200, help="Số bản ghi tối đa trong một batch file")
    parser.add_argument("--url-files", nargs="*", default=None, help="Danh sách file URL nguồn (urls_c1_*.json...)")
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
        batch_size=args.batch_size,
        url_files=args.url_files,
    )
    result = crawler.run()
    print("Crawl completed:", result)


if __name__ == "__main__":
    main()
