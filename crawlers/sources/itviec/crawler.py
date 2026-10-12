# -*- coding: utf-8 -*-
"""Crawler nguồn ITviec (https://itviec.com) — Data Contract v0.5.0.

Owner: Phát

Kế thừa BaseCrawler (crawlers/base/base_crawler.py):
    - fetch_items():  duyệt listing theo config.LISTING_LOCATIONS + phân trang,
                      yield từng job card {url, source_job_id}.
    - parse_item():   tải detail HTML → gọi parser → trả JobRecord.

Sử dụng common modules:
    - HttpClient + DelayConfig + RetryConfig (crawlers/common/http_client.py)
    - CheckpointManager (crawlers/common/checkpoint.py)
    - JsonWriter với validate_schema=True mặc định (crawlers/common/json_writer.py)

Cách chạy:
    .venv/bin/python run.py --source itviec --max-items 3 -v
    .venv/bin/python -m crawlers.sources.itviec.crawler --max-items 3 -v
"""

import argparse
import logging
import os
import sys
from collections.abc import Generator
from typing import Any, Dict, Optional

from crawlers.base.base_crawler import BaseCrawler
from crawlers.common.http_client import HttpClient, DelayConfig, RetryConfig
from crawlers.common.schema import JobRecord
from crawlers.common.utils import detect_language

repo_root = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
)
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

try:
    from . import config, parser as job_parser
except ImportError:  # pragma: no cover
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import config
    import parser as job_parser

log = logging.getLogger("itviec.crawler")


class ItviecCrawler(BaseCrawler):
    """Crawler nguồn ITviec — kế thừa BaseCrawler."""

    source_name = config.SOURCE
    crawler_version = config.CRAWLER_VERSION

    def __init__(
        self,
        checkpoint_dir: Optional[str] = None,
        output_dir: Optional[str] = None,
        max_items: Optional[int] = config.DEFAULT_MAX_ITEMS,
        checkpoint_interval: int = config.CHECKPOINT_INTERVAL,
    ) -> None:
        super().__init__(
            checkpoint_dir=checkpoint_dir or f"data/{config.SOURCE}",
            output_dir=output_dir,
            max_items=max_items,
            checkpoint_interval=checkpoint_interval,
        )
        self.http_client = HttpClient(
            source=config.SOURCE,
            timeout=config.REQUEST_TIMEOUT,
            delay_config=DelayConfig(
                min_seconds=config.REQUEST_DELAY_MIN,
                max_seconds=config.REQUEST_DELAY_MAX,
            ),
            retry_config=RetryConfig(
                max_retries=config.MAX_RETRIES,
                backoff_factor=1.0,
            ),
            extra_headers={
                # ITviec server trả Brotli (br) nhưng requests không giải
                # nén được nếu thiếu package brotli → chỉ nhận gzip/deflate.
                "Accept-Encoding": "gzip, deflate",
            },
        )

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _listing_url(location_path: str, page: int) -> str:
        url = config.BASE_URL + location_path
        if page > 1:
            url += f"?page={page}"
        return url

    def _fetch_html(self, url: str) -> Optional[str]:
        """Tải HTML từ URL. Return None nếu lỗi."""
        try:
            resp = self.http_client.get(url)
            return resp.text
        except Exception as exc:
            log.error("Lỗi tải %s: %s", url, exc)
            return None

    # ---------------------------------------------------------------- BaseCrawler

    def fetch_items(self) -> Generator[Dict[str, Any], None, None]:
        """Duyệt listing pages, yield từng job card {url, source_job_id}."""
        for location in config.LISTING_LOCATIONS:
            for page in range(1, config.MAX_LISTING_PAGES + 1):
                if (
                    self.max_items is not None
                    and self.crawled_count >= self.max_items
                ):
                    return

                url = self._listing_url(location, page)
                html = self._fetch_html(url)
                if not html:
                    log.warning("Bỏ qua trang listing lỗi: %s", url)
                    break

                jobs = job_parser.parse_listing(html)
                if not jobs:
                    log.info("Hết trang listing (trang %d trống).", page)
                    break

                log.info(
                    "Listing %s trang %d: %d tin.", location, page, len(jobs)
                )
                for job in jobs:
                    if self.checkpoint.is_seen(job["source_job_id"]):
                        continue
                    yield job

    def parse_item(self, item: Dict[str, Any]) -> Optional[JobRecord]:
        """Tải detail HTML → parse → trả JobRecord theo Data Contract v0.5.0.

        Nếu item có sẵn key "html" (offline/test mode), dùng luôn không fetch.
        """
        url = item["url"]
        source_job_id = item["source_job_id"]

        html = item.get("html") or self._fetch_html(url)
        if not html:
            return None

        try:
            raw_data = job_parser.parse_detail(html)
        except Exception as exc:
            log.error("Parse lỗi %s: %s", url, exc, exc_info=True)
            return None

        # Loại bỏ language khỏi raw_data (nó thuộc _meta, không thuộc raw)
        lang = raw_data.pop("language", "vi")

        # description_text dùng cho language detection nếu cần
        desc_text = "\n".join(raw_data.get("description_list", []))
        if desc_text:
            lang = detect_language(desc_text)

        return JobRecord.create(
            source=self.source_name,
            source_job_id=source_job_id,
            url=url,
            batch_id=self.batch_id,
            raw_data=raw_data,
            crawler_version=self.crawler_version,
            language=lang,
        )


# ---------------------------------------------------------------- CLI


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Crawler ITviec — Data Contract v0.5.0 (BaseCrawler)."
    )
    ap.add_argument(
        "--max-items", type=int, default=config.DEFAULT_MAX_ITEMS,
        help="Số tin mới tối đa trong 1 batch (mặc định 30).",
    )
    ap.add_argument(
        "--output-dir", type=str, default="data",
        help="Thư mục gốc lưu dữ liệu.",
    )
    ap.add_argument(
        "--checkpoint-dir", type=str, default=None,
        help="Thư mục lưu checkpoint.",
    )
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    crawler = ItviecCrawler(
        checkpoint_dir=args.checkpoint_dir,
        output_dir=args.output_dir,
        max_items=args.max_items,
    )
    stats = crawler.run()
    print(f"\nTóm tắt: {stats}")
    return 0 if stats.get("errors", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
