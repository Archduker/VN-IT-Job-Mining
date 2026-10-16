#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tool tự động sinh khung mã nguồn Crawler chuẩn 2 pha (Discovery & Detail Extraction)
cho bất kỳ nguồn tuyển dụng nào.

Sử dụng:
    python .agents/skills/crawling-architect/scripts/scaffold_crawler.py --source itviec
"""

import argparse
import sys
from pathlib import Path


CRAWLER_TEMPLATE = '''"""Crawler 2 pha cho sàn {source_name}.
Tự động sinh bởi crawling-architect skill.

Pha 1: discover_urls() — Quét danh mục, chuẩn hóa URL, ghi vào UrlLedger.
Pha 2: crawl_details() — Đọc link PENDING hoặc RECHECK_DUE (>= 21 ngày), tải HTML, tính container hash, lưu raw JSON.
"""

import logging
import time
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup

from crawlers.common.http_client import HttpClient
from crawlers.common.url_ledger import (
    UrlLedger,
    calculate_container_html_hash,
    clean_canonical_url,
)

logger = logging.getLogger(__name__)

# TODO: Thay đổi container selector phù hợp với {source_name}
CONTAINER_SELECTOR = "body"


class {class_name}Crawler:
    """Crawler 2 pha cho {source_name}."""

    def __init__(self, storage_dir: Optional[str] = None):
        self.source = "{source_id}"
        self.ledger = UrlLedger(source=self.source, storage_dir=storage_dir)
        self.client = HttpClient()

    # ── PHA 1: URL DISCOVERY ──────────────────────────────────
    def discover_urls(self, max_pages: Optional[int] = None) -> int:
        """Quét sạch toàn bộ link bài đăng từ trang danh mục (không giới hạn thời gian)."""
        logger.info(f"[{source_name}] Bắt đầu Pha 1: URL Discovery...")
        page = 1
        total_discovered = 0

        while True:
            if max_pages and page > max_pages:
                break

            # TODO: Cập nhật URL tìm kiếm thực tế của {source_name}
            list_url = f"https://example.com/{source_id}/jobs?page={{page}}"
            logger.info(f"[{source_name}] Đang quét trang danh mục {{page}}: {{list_url}}")

            try:
                resp = self.client.get(list_url, timeout=15)
                if resp.status_code != 200:
                    logger.warning(f"Dừng quét danh mục tại trang {{page}} (HTTP {{resp.status_code}})")
                    break

                soup = BeautifulSoup(resp.text, "html.parser")
                # TODO: Cập nhật selector bài viết trên trang danh mục
                job_links = soup.select("a.job-link")
                if not job_links:
                    logger.info(f"[{source_name}] Hết bài đăng tại trang {{page}}.")
                    break

                for link_el in job_links:
                    href = link_el.get("href")
                    if not href:
                        continue
                    canonical = clean_canonical_url(href)
                    job_id = canonical.split("/")[-1].replace(".html", "")
                    title = link_el.get_text(strip=True)

                    # Ghi nhận vào Ledger (nếu đã có thì chỉ cập nhật last_seen_at)
                    self.ledger.register_url(
                        raw_url=canonical,
                        job_id=job_id,
                        preliminary_title=title,
                    )
                    total_discovered += 1

                page += 1
                time.sleep(1.5)
            except Exception as e:
                logger.error(f"Lỗi khi quét trang {{page}}: {{e}}")
                break

        self.ledger.save_catalog()
        manifest_path = self.ledger.export_daily_manifest()
        logger.info(f"[{source_name}] Hoàn thành Pha 1. Đã ghi nhận {{total_discovered}} link vào {{manifest_path}}")
        return total_discovered

    # ── PHA 2: DETAIL EXTRACTION ──────────────────────────────
    def crawl_details(self, limit: Optional[int] = None) -> Dict[str, int]:
        """Đọc danh sách link cần cào từ Ledger, tải HTML, băm Clean Container Hash và lưu raw."""
        logger.info(f"[{source_name}] Bắt đầu Pha 2: Detail Extraction (Chu kỳ Re-crawl 21 ngày)...")
        pending_records = self.ledger.get_pending_or_due_records(recheck_days=21)
        logger.info(f"[{source_name}] Có {{len(pending_records)}} link cần xử lý.")

        stats = {{"success": 0, "failed": 0, "skipped": 0, "repost": 0}}
        count = 0

        for item in pending_records:
            if limit and count >= limit:
                break

            url = item["canonical_url"]
            url_hash = item["url_hash"]
            job_id = item["job_id"]

            try:
                # Tải chi tiết bài viết
                resp = self.client.get(url, timeout=15)
                if resp.status_code == 404:
                    logger.warning(f"Bài đăng đã bị gỡ (404): {{url}}")
                    self.ledger.mark_closed(url_hash)
                    stats["skipped"] += 1
                    continue
                elif resp.status_code != 200:
                    raise Exception(f"HTTP Status {{resp.status_code}}")

                # Băm Clean Container HTML Hash
                new_hash = calculate_container_html_hash(resp.text, container_selector=CONTAINER_SELECTOR)

                # Kiểm tra Repost (URL mới nhưng content trùng tin cũ)
                existing_repost = self.ledger.find_by_content_hash(new_hash)
                if existing_repost and existing_repost["url_hash"] != url_hash:
                    logger.info(f"Phát hiện Repost: {{url}} trùng nội dung với {{existing_repost['canonical_url']}}")
                    self.ledger.mark_done(url_hash, content_hash=new_hash, repost_of_url_hash=existing_repost["url_hash"])
                    stats["repost"] += 1
                    count += 1
                    continue

                # TODO: Bóc tách 100% trường dữ liệu thô nguyên bản của {source_name}
                soup = BeautifulSoup(resp.text, "html.parser")
                raw_payload = {{
                    "url": url,
                    "title": soup.select_one("h1").get_text(strip=True) if soup.select_one("h1") else "",
                    "html": resp.text,
                }}

                # Tăng version nếu nội dung bị sửa đổi
                current_ver = item.get("latest_version") or 0
                new_version = current_ver if (item.get("content_hash") == new_hash and current_ver > 0) else current_ver + 1

                # Đánh dấu DONE trong Ledger
                self.ledger.mark_done(url_hash, content_hash=new_hash, new_version=new_version)
                stats["success"] += 1
                count += 1
                time.sleep(1.5)

            except Exception as e:
                # Safe Skip: Bắt lỗi an toàn, không ngắt quãng cả batch
                logger.error(f"Lỗi khi cào {{url}}: {{e}}. Skip qua link tiếp theo.")
                self.ledger.mark_failed(url_hash, error_message=str(e))
                stats["failed"] += 1

        self.ledger.save_catalog()
        logger.info(f"[{source_name}] Hoàn thành Pha 2: {{stats}}")
        return stats
'''


def main():
    parser = argparse.ArgumentParser(description="Sinh khung mã nguồn crawler 2 pha.")
    parser.add_argument("--source", required=True, help="Tên sàn tuyển dụng (ví dụ: itviec, careerviet)")
    args = parser.parse_args()

    source_id = args.source.lower().strip()
    source_name = source_id.capitalize()
    class_name = source_id.capitalize()

    code = CRAWLER_TEMPLATE.format(
        source_id=source_id,
        source_name=source_name,
        class_name=class_name,
    )

    out_dir = Path(f"crawlers/sources/{source_id}")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "crawler_scaffold.py"

    with open(out_file, "w", encoding="utf-8") as f:
        f.write(code)

    print(f"✅ Đã tạo scaffold crawler 2 pha thành công tại: {out_file}")


if __name__ == "__main__":
    main()
