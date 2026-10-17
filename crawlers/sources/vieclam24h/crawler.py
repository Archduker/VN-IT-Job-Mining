# -*- coding: utf-8 -*-
"""Thu thập việc làm Vieclam24h qua Next.js SSR (__NEXT_DATA__) và HttpClient, 
tích hợp đầy đủ Headers giả lập trình duyệt thật, tuân thủ Flowchart Pha 1 & Pha 2.
"""

from __future__ import annotations

import io
import argparse
import json
import logging
import hashlib
import re
import sys
import time
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse, parse_qsl, urljoin
from minio import Minio

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from bs4 import BeautifulSoup

from crawlers.base.base_crawler import BaseCrawler
from crawlers.common.http_client import DelayConfig, HttpClient, RetryConfig

SITE_BASE_URL = "https://vieclam24h.vn"
DEFAULT_OUTPUT = Path(__file__).resolve().with_name("vieclam24h_raw_jobs.json")
CRAWLER_VERSION = "0.5.5-raw"
LOCAL_TIMEZONE = timezone(timedelta(hours=7))

# Các danh mục IT mục tiêu trên Vieclam24h
TARGET_CATEGORIES = [
    {"name": "IT Phần mềm", "path": "/viec-lam-it-phan-mem-o8.html"},
    {"name": "IT Phần cứng - Mạng", "path": "/viec-lam-it-phan-cung-mang-o7.html"},
]

# Các tham số tracking/quảng cáo cần loại bỏ khi làm sạch URL
TRACKING_PARAMS = {
    "utm_source", "utm_campaign", "utm_medium", "utm_term", 
    "utm_content", "fbclid", "gclid", "ref", "source", "token"
}

log = logging.getLogger("vieclam24h.crawler")


class SimpleMeta:
    """Lớp lưu trữ metadata tối thiểu để tương thích với BaseCrawler."""
    def __init__(self, source_job_id: str, url: str):
        self.source_job_id = source_job_id
        self.url = url


class RawJobRecordWrapper:
    """Lớp bọc dữ liệu thô để BaseCrawler nhận diện được thuộc tính .meta."""
    def __init__(self, meta: SimpleMeta, raw: dict[str, Any]):
        self.meta = meta
        self.raw = raw


def clean_canonical_url(raw_url: str) -> str:
    """Làm sạch URL về dạng chính tắc (Canonical URL): loại bỏ các tham số tracking/quảng cáo."""
    if not raw_url:
        return ""
    try:
        parsed = urlparse(raw_url)
        query_params = parse_qsl(parsed.query, keep_blank_values=True)
        filtered_params = [(k, v) for k, v in query_params if k.lower() not in TRACKING_PARAMS]
        filtered_params.sort(key=lambda x: x[0])
        new_query = "&".join([f"{k}={v}" if v else k for k, v in filtered_params])
        clean_parsed = parsed._replace(query=new_query, fragment="")
        return urlunparse(clean_parsed)
    except Exception as exc:
        log.warning("Không thể chuẩn hóa URL '%s': %s", raw_url, exc)
        return raw_url


def compute_clean_container_hash(html_content: str) -> str:
    """Tính toán Clean Container HTML Hash (SHA-256) cho CDC Versioning."""
    if not html_content:
        return ""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        for selector in ["script", "style", "nav", "footer", ".advertisement", ".social-share", ".view-count", ".related-jobs"]:
            for el in soup.select(selector):
                el.decompose()
        container = soup.find("main") or soup.find("article") or soup.body or soup
        normalized_text = re.sub(r"\s+", " ", container.get_text()).strip()
        return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()
    except Exception as exc:
        log.warning("Lỗi tính toán Clean Container Hash: %s", exc)
        return ""


def _extract_next_data(html: str) -> dict[str, Any] | None:
    """Trích xuất state JSON từ thẻ script __NEXT_DATA__."""
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    if script and script.string:
        try:
            return json.loads(script.string)
        except Exception as exc:
            log.warning("Không giải mã được __NEXT_DATA__: %s", exc)
    return None


class ViecLam24hRawCrawler(BaseCrawler):
    """Crawler thuần HTTP tích hợp đầy đủ Browser Headers giả lập trình duyệt thật, tuân thủ Flowchart Pha 1 & Pha 2."""

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
        minio_endpoint: str = "localhost:9000",
        minio_access_key: str = "minioadmin",
        minio_secret_key: str = "minioadmin",
    ) -> None:
        super().__init__(
            checkpoint_dir=checkpoint_dir,
            output_dir=str(output_dir) if output_dir is not None else None,
            max_items=max_items,
            checkpoint_interval=checkpoint_interval,
        )
        self.max_pages = max_pages
        self.local_json_file = Path(local_json_file) if local_json_file else None
        
        # Khởi tạo HttpClient
        self.client = HttpClient(
            source=self.source_name,
            delay_config=DelayConfig(min_seconds=1.0, max_seconds=2.0),
            retry_config=RetryConfig(max_retries=3, backoff_factor=1.0),
        )
        
        # Bổ sung đầy đủ các trường Header giả lập trình duyệt thật (Modern Browser Headers)
        browser_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.9",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            "Referer": "https://vieclam24h.vn/",
        }
        
        # Cập nhật headers trực tiếp vào session của HttpClient nếu tồn tại
        if hasattr(self.client, "session") and hasattr(self.client.session, "headers"):
            self.client.session.headers.update(browser_headers)

        self.minio_client = Minio(
            minio_endpoint,
            access_key=minio_access_key,
            secret_key=minio_secret_key,
            secure=False
        )
        self.bucket_name = "vn-it-jobs"

    def _fetch_page_with_safe_skip(self, url: str) -> tuple[str, dict[str, Any] | None]:
        """Bọc Safe Skip: tự động log cảnh báo và bỏ qua khi gặp lỗi HTTP hoặc timeout."""
        try:
            # Cập nhật linh hoạt Referer theo trang hiện tại để trông tự nhiên nhất
            headers = {"Referer": url}
            resp = self.client.get(url)
            
            if resp.status_code >= 400:
                log.warning("[Safe Skip] HTTP Error %d tại URL: %s -> Bỏ qua", resp.status_code, url)
                return "", None
                
            html = resp.text
            next_data = _extract_next_data(html)
            return html, next_data
        except Exception as exc:
            log.warning("[Safe Skip] Lỗi kết nối / timeout tại URL '%s': %s -> Bỏ qua", url, exc)
            return "", None

    def discover_urls(self) -> list[str]:
        """PHA 1: VÉT SẠCH URL (DISCOVERY) - Quét toàn bộ phân trang danh mục, không giới hạn thời gian."""
        discovered_urls: set[str] = set()

        for category in TARGET_CATEGORIES:
            cat_name = category["name"]
            cat_path = category["path"]
            log.info("[Phase 1 - URL Discovery] Quét danh mục: %s (%s)", cat_name, cat_path)

            page_idx = 1
            while True:
                if self.max_pages is not None and page_idx > self.max_pages:
                    break

                page_url = f"{SITE_BASE_URL}{cat_path}?page={page_idx}" if page_idx > 1 else f"{SITE_BASE_URL}{cat_path}"
                html, next_data = self._fetch_page_with_safe_skip(page_url)
                if not next_data:
                    log.warning("[URL Discovery] Dừng phân trang tại trang %d ngành %s (Không tìm thấy __NEXT_DATA__ hoặc bị chặn)", page_idx, cat_name)
                    break

                soup = BeautifulSoup(html, "html.parser")
                detail_links_map: dict[str, str] = {}
                for a in soup.find_all("a"):
                    href = a.get("href", "")
                    clean_href = href.split("?")[0]
                    if "-c" in clean_href and "id" in clean_href and clean_href.endswith(".html"):
                        m = re.search(r"id(\d+)\.html", clean_href)
                        if m:
                            jid = m.group(1)
                            full_url = urljoin(SITE_BASE_URL, clean_href)
                            detail_links_map[jid] = clean_canonical_url(full_url)

                api_state = next_data.get("props", {}).get("initialState", {}).get("api", {})
                listing_items = api_state.get("getJobList", {}).get("data", {}).get("items", [])
                
                if not listing_items:
                    log.warning("[URL Discovery] Hết tin tại trang %d ngành %s", page_idx, cat_name)
                    break

                for item_summary in listing_items:
                    jid = str(item_summary.get("id", ""))
                    title_slug = item_summary.get("title_slug", "")
                    detail_url = detail_links_map.get(jid)
                    if not detail_url and title_slug:
                        detail_url = clean_canonical_url(f"{SITE_BASE_URL}/{title_slug}-id{jid}.html")
                    
                    if detail_url:
                        discovered_urls.add(detail_url)

                page_idx += 1

        url_list = list(discovered_urls)
        log.info("[Phase 1 - URL Discovery] Tổng số URL chính tắc độc nhất: %d", len(url_list))
        
        # Ghi nhận danh sách URL vào MinIO URL Ledger dạng manifest phân vùng ngày
        self._save_ledger_to_minio(url_list)
        return url_list

    def _save_ledger_to_minio(self, url_list: list[str]) -> None:
        """Làm sạch Canonical URL & ghi vào MinIO dưới dạng manifest_<YYYY-MM-DD>.jsonl."""
        today_str = datetime.now(LOCAL_TIMEZONE).strftime("%Y-%m-%d")
        manifest_key = f"manifests/manifest_{today_str}.jsonl"
        try:
            lines = [json.dumps({"url": u, "source": self.source_name, "discovered_at": datetime.now(LOCAL_TIMEZONE).isoformat()}, ensure_ascii=False) for u in url_list]
            data_bytes = ("\n".join(lines)).encode("utf-8")
            self.minio_client.put_object(
                bucket_name=self.bucket_name,
                object_name=manifest_key,
                data=io.BytesIO(data_bytes),
                length=len(data_bytes),
                content_type="application/x-ndjson"
            )
            log.info("[MinIO Ledger] Đã lưu manifest URL vào: s3://%s/%s", self.bucket_name, manifest_key)
        except Exception as exc:
            log.error("[MinIO Ledger Error] Lỗi ghi manifest: %s", exc)

    def fetch_items(self) -> Generator[dict[str, Any], None, None]:
        """PHA 2: CÀO CHI TIẾT & RE-CRAWL 21 NGÀY (Sử dụng CheckpointManager an toàn)."""
        if self.local_json_file and self.local_json_file.exists():
            log.info("Đang đọc dữ liệu offline từ: %s", self.local_json_file)
            content = self.local_json_file.read_text(encoding="utf-8")
            data = json.loads(content)
            items = data if isinstance(data, list) else [data]
            for it in items:
                yield it if isinstance(it, dict) else {"job_detail": it}
            return

        all_urls = self.discover_urls()
        collected_count = 0
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=21)

        # Đọc lịch sử thời gian crawl từ checkpoint extra an toàn
        seen_timestamps: dict[str, str] = self.checkpoint.get_extra("seen_timestamps", {})

        for detail_url in all_urls:
            if self.max_items is not None and collected_count >= self.max_items:
                return

            m = re.search(r"id(\d+)\.html", detail_url)
            job_id = m.group(1) if m else detail_url

            # Kiểm tra quy tắc Re-crawl 21 ngày qua CheckpointManager
            if self.checkpoint.is_seen(job_id):
                last_seen_str = seen_timestamps.get(job_id)
                if last_seen_str:
                    try:
                        last_seen_dt = datetime.fromisoformat(last_seen_str)
                        if last_seen_dt > cutoff_date:
                            continue
                    except ValueError:
                        pass

            html, next_data = self._fetch_page_with_safe_skip(detail_url)
            if not html or not next_data:
                continue

            content_hash = compute_clean_container_hash(html)

            d_api = next_data.get("props", {}).get("initialState", {}).get("api", {})
            job_detail = d_api.get("jobDetailHiddenContact", {}).get("data", {})
            
            if not job_detail:
                continue

            actual_job_id = str(job_detail.get("id", job_id))
            self.checkpoint.mark_seen(actual_job_id)
            seen_timestamps[actual_job_id] = datetime.now(timezone.utc).isoformat()
            self.checkpoint.set_extra("seen_timestamps", seen_timestamps, auto_save=False)

            collected_count += 1
            yield {
                "url": detail_url,
                "crawled_at": datetime.now(LOCAL_TIMEZONE).isoformat(),
                "content_hash": content_hash,
                "job_detail": job_detail
            }

    def parse_item(self, item: dict[str, Any]) -> RawJobRecordWrapper | None:
        """Bọc dữ liệu thô vào wrapper tương thích chuẩn với BaseCrawler."""
        if not isinstance(item, dict):
            return None
        
        job_detail = item.get("job_detail") if isinstance(item.get("job_detail"), dict) else item
        job_id = str(job_detail.get("id", ""))
        url = item.get("url", "")
        
        meta = SimpleMeta(source_job_id=job_id, url=url)
        return RawJobRecordWrapper(meta=meta, raw=item)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crawl raw việc làm Vieclam24h không fix schema.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-pages", type=int, help="Giới hạn số trang.")
    parser.add_argument("--max-jobs", type=int, help="Giới hạn số lượng tin.")
    parser.add_argument("--local-json-file", type=Path, help="File JSON mẫu chạy offline.")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    crawler = ViecLam24hRawCrawler(
        output_dir=args.output.parent,
        max_items=args.max_jobs,
        max_pages=args.max_pages,
        local_json_file=args.local_json_file,
    )

    try:
        stats = crawler.run()
        print(f"Vieclam24h Raw Crawler: Hoàn tất thu thập thành công. Thống kê: {stats}")
    except Exception as exc:
        log.error("Lỗi khi chạy crawler: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())