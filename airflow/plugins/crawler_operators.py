# -*- coding: utf-8 -*-
"""Custom Airflow Operators for VN-IT-Job-Mining.

Bao gồm:
- JobCrawlerOperator: Điều khiển crawler theo từng nguồn (Legacy/Direct).
- HarvestListingOperator: Pha 1 - Thu hoạch toàn bộ listing, trích xuất (job_id, job_url),
  so khớp State Catalog để loại trùng O(1) và xuất file Hàng đợi (Queue).
- DetailCrawlerQueueOperator: Pha 2 - Nhận hàng đợi, cào chi tiết với polite delay,
  lưu raw batch file, đánh dấu SUCCESS hoặc FAILED_RETRY_NEXT_RUN.
- DataQualityOperator: Kiểm tra tính toàn vẹn và chất lượng sau mỗi lần cào.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from airflow.models import BaseOperator
from airflow.utils.context import Context

from crawlers.common.data_quality import DataQualityChecker
from crawlers.common.job_catalog import JobStateCatalog

logger = logging.getLogger("airflow.operators.vn_it_job")


class JobCrawlerOperator(BaseOperator):
    """Operator để chạy crawler của một nguồn cụ thể (Chế độ Direct)."""

    template_fields = ("source", "max_items")

    def __init__(
        self,
        source: str,
        max_items: int = 50,
        output_dir: Optional[str] = "data",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.source = source
        self.max_items = max_items
        self.output_dir = output_dir

    def execute(self, context: Context) -> dict[str, Any]:
        logger.info("Executing JobCrawlerOperator for source='%s', max_items=%d", self.source, self.max_items)

        crawler_cls = None
        if self.source == "topdev":
            from crawlers.sources.topdev.crawler import TopDevCrawler
            crawler_cls = TopDevCrawler
        elif self.source == "vietnamworks":
            from crawlers.sources.vietnamworks.crawler import VietnamWorksCrawler
            crawler_cls = VietnamWorksCrawler
        elif self.source == "careerviet":
            from crawlers.sources.careerviet.crawler import CareerVietCrawler
            crawler_cls = CareerVietCrawler
        elif self.source == "vieclam24h":
            from crawlers.sources.vieclam24h.crawler import ViecLam24hCrawler
            crawler_cls = ViecLam24hCrawler
        elif self.source == "topcv":
            from crawlers.sources.topcv.crawler import TopCVCrawler
            crawler_cls = TopCVCrawler
        elif self.source == "itviec":
            try:
                from crawlers.sources.itviec.crawler import ItviecCrawler
                crawler_cls = ItviecCrawler
            except ImportError:
                from crawlers.sources.itviec.crawler import crawl
                stats = crawl(max_items=self.max_items)
                return stats
        elif self.source == "glints":
            from crawlers.sources.glints.crawler import GlintsCrawler
            crawler_cls = GlintsCrawler
        elif self.source == "jobsgo":
            from crawlers.sources.jobsgo.crawler import JobsGOCrawler
            crawler_cls = JobsGOCrawler
        else:
            raise ValueError(f"Unknown source: {self.source}")

        crawler = crawler_cls(output_dir=self.output_dir, max_items=self.max_items)
        stats = crawler.run()

        # Push file path to XCom for quality check task
        if stats.get("output_file"):
            context["ti"].xcom_push(key="output_file", value=stats["output_file"])

        return stats


class HarvestListingOperator(BaseOperator):
    """Pha 1 Operator: Quét toàn bộ listing, trích xuất cặp (job_id, job_url),
    lọc trùng lặp với JobStateCatalog và xuất ra Hàng đợi chi tiết."""

    template_fields = ("source",)

    def __init__(
        self,
        source: str,
        catalog_db_path: Optional[str] = None,
        queue_dir: str = "data/queue",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.source = source.lower().strip()
        self.catalog_db_path = catalog_db_path
        self.queue_dir = Path(queue_dir)

    def execute(self, context: Context) -> dict[str, Any]:
        logger.info("[Pha 1 - Harvest] Bắt đầu thu hoạch toàn bộ listing cho source='%s'", self.source)
        catalog = JobStateCatalog(db_path=self.catalog_db_path)

        # Lấy crawler class tương ứng
        harvested_items: list[dict[str, str]] = []
        if self.source == "topdev":
            from crawlers.sources.topdev.crawler import TopDevCrawler
            crawler = TopDevCrawler()
            for raw in crawler.fetch_items():
                jid = str(raw.get("id") or raw.get("job_id") or "").strip()
                url = raw.get("job_url") or raw.get("url") or ""
                if not url and raw.get("slug"):
                    url = f"https://topdev.vn/viec-lam/{raw['slug']}-{jid}"
                if jid and url:
                    harvested_items.append({"job_id": jid, "job_url": url})

        elif self.source == "vietnamworks":
            from crawlers.sources.vietnamworks.crawler import VietnamWorksCrawler
            crawler = VietnamWorksCrawler()
            for raw in crawler.fetch_items():
                jid = str(raw.get("jobId") or raw.get("job_id") or "").strip()
                url = raw.get("jobUrl") or raw.get("url") or ""
                if jid and url:
                    harvested_items.append({"job_id": jid, "job_url": url})

        elif self.source == "careerviet":
            from crawlers.sources.careerviet.crawler import CareerVietCrawler
            crawler = CareerVietCrawler()
            for raw in crawler.fetch_items():
                jid = str(raw.get("job_id") or "").strip()
                url = raw.get("job_url") or raw.get("url") or ""
                if jid and url:
                    harvested_items.append({"job_id": jid, "job_url": url})

        elif self.source == "vieclam24h":
            from crawlers.sources.vieclam24h.crawler import ViecLam24hCrawler
            crawler = ViecLam24hCrawler()
            for raw in crawler.fetch_items():
                jid = str(raw.get("job_id") or "").strip()
                url = raw.get("job_url") or raw.get("url") or ""
                if jid and url:
                    harvested_items.append({"job_id": jid, "job_url": url})

        elif self.source == "itviec":
            from crawlers.sources.itviec.crawler import ItviecCrawler
            crawler = ItviecCrawler()
            for raw in crawler.fetch_items():
                jid = str(raw.get("job_id") or "").strip()
                url = raw.get("job_url") or raw.get("url") or ""
                if jid and url:
                    harvested_items.append({"job_id": jid, "job_url": url})

        elif self.source == "topcv":
            from crawlers.sources.topcv.crawler import TopCVCrawler
            crawler = TopCVCrawler()
            for raw in crawler.fetch_items():
                jid = str(raw.get("job_id") or "").strip()
                url = raw.get("job_url") or raw.get("url") or ""
                if jid and url:
                    harvested_items.append({"job_id": jid, "job_url": url})

        elif self.source == "jobsgo":
            from crawlers.sources.jobsgo.crawler import JobsGOCrawler
            crawler = JobsGOCrawler()
            for raw in crawler.fetch_items():
                jid = str(raw.get("job_id") or "").strip()
                url = raw.get("job_url") or raw.get("url") or ""
                if jid and url:
                    harvested_items.append({"job_id": jid, "job_url": url})

        elif self.source == "glints":
            from crawlers.sources.glints.crawler import GlintsCrawler
            crawler = GlintsCrawler()
            for raw in crawler.fetch_items():
                jid = str(raw.get("job_id") or raw.get("id") or "").strip()
                url = raw.get("job_url") or raw.get("url") or ""
                if jid and url:
                    harvested_items.append({"job_id": jid, "job_url": url})
        else:
            raise ValueError(f"Unknown source: {self.source}")

        # Lọc trùng và nạp tin lỗi kỳ trước
        queue_items, skipped_count = catalog.register_harvested_jobs(self.source, harvested_items)

        # Lưu file Hàng đợi
        run_date = datetime.now(timezone.utc).strftime("%Y%m%d")
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        queue_file = self.queue_dir / f"{self.source}_queue_{run_date}.json"

        queue_payload = {
            "source": self.source,
            "run_date": run_date,
            "total_harvested": len(harvested_items),
            "skipped_duplicates": skipped_count,
            "total_queue_items": len(queue_items),
            "items": queue_items,
        }
        with open(queue_file, "w", encoding="utf-8") as f:
            json.dump(queue_payload, f, ensure_ascii=False, indent=2)

        logger.info(
            "[%s] Pha 1 thành công: Đã ghi %d items vào hàng đợi %s (Bỏ qua %d tin trùng lặp)",
            self.source,
            len(queue_items),
            queue_file,
            skipped_count,
        )

        ti = context.get("ti")
        if ti:
            ti.xcom_push(key="queue_file", value=str(queue_file))
            ti.xcom_push(key="queue_count", value=len(queue_items))
            ti.xcom_push(key="skipped_count", value=skipped_count)

        return queue_payload


class DetailCrawlerQueueOperator(BaseOperator):
    """Pha 2 Operator: Đọc items từ Hàng đợi chi tiết, cào dữ liệu,
    lưu raw batch file, cập nhật State Catalog (SUCCESS hoặc FAILED_RETRY_NEXT_RUN)."""

    template_fields = ("source", "queue_file")

    def __init__(
        self,
        source: str,
        queue_file: Optional[str] = None,
        harvest_task_id: Optional[str] = None,
        output_dir: str = "data",
        catalog_db_path: Optional[str] = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.source = source.lower().strip()
        self.queue_file = queue_file
        self.harvest_task_id = harvest_task_id
        self.output_dir = output_dir
        self.catalog_db_path = catalog_db_path

    def execute(self, context: Context) -> dict[str, Any]:
        target_queue_file = self.queue_file
        ti = context.get("ti")
        if not target_queue_file and self.harvest_task_id and ti:
            target_queue_file = ti.xcom_pull(
                task_ids=self.harvest_task_id,
                key="queue_file",
            )

        if not target_queue_file or not os.path.exists(target_queue_file):
            logger.warning("[%s] Không tìm thấy queue file '%s', kết thúc task.", self.source, target_queue_file)
            return {"status": "skipped", "crawled_count": 0}

        with open(target_queue_file, "r", encoding="utf-8") as f:
            queue_data = json.load(f)

        items = queue_data.get("items", [])
        if not items:
            logger.info("[%s] Hàng đợi rỗng (không có tin mới hay tin cần retry). Bỏ qua Pha 2.", self.source)
            return {"status": "empty_queue", "crawled_count": 0}

        logger.info("[%s] Bắt đầu Pha 2 cào chi tiết cho %d items trong hàng đợi...", self.source, len(items))
        catalog = JobStateCatalog(db_path=self.catalog_db_path)

        # Sử dụng JobCrawlerOperator logic hoặc crawler detail method
        from crawlers.common.json_writer import JsonWriter
        writer = JsonWriter(source=self.source, output_dir=self.output_dir)

        # Khởi tạo crawler
        crawler_cls = None
        if self.source == "topdev":
            from crawlers.sources.topdev.crawler import TopDevCrawler
            crawler_cls = TopDevCrawler
        elif self.source == "vietnamworks":
            from crawlers.sources.vietnamworks.crawler import VietnamWorksCrawler
            crawler_cls = VietnamWorksCrawler
        elif self.source == "careerviet":
            from crawlers.sources.careerviet.crawler import CareerVietCrawler
            crawler_cls = CareerVietCrawler
        elif self.source == "vieclam24h":
            from crawlers.sources.vieclam24h.crawler import ViecLam24hCrawler
            crawler_cls = ViecLam24hCrawler
        elif self.source == "itviec":
            from crawlers.sources.itviec.crawler import ItviecCrawler
            crawler_cls = ItviecCrawler
        elif self.source == "topcv":
            from crawlers.sources.topcv.crawler import TopCVCrawler
            crawler_cls = TopCVCrawler
        elif self.source == "jobsgo":
            from crawlers.sources.jobsgo.crawler import JobsGOCrawler
            crawler_cls = JobsGOCrawler
        elif self.source == "glints":
            from crawlers.sources.glints.crawler import GlintsCrawler
            crawler_cls = GlintsCrawler
        else:
            raise ValueError(f"Unknown source: {self.source}")

        crawler = crawler_cls(output_dir=self.output_dir)
        crawled_count = 0
        failed_count = 0

        for idx, item in enumerate(items, start=1):
            job_id = item["job_id"]
            job_url = item["job_url"]

            try:
                # Chuẩn bị raw item với cả url và job_url
                raw_payload = {"job_id": job_id, "job_url": job_url, "url": job_url}
                if hasattr(crawler, "http_client"):
                    try:
                        raw_payload["html"] = crawler.http_client.get_html(job_url)
                    except Exception:
                        pass

                # Thử cào và parse
                record = crawler.parse_item(raw_payload)
                if record:
                    writer.write(record)
                    crawled_count += 1
                    catalog.mark_job_success(self.source, job_id, str(writer.file_path))
                else:
                    raise ValueError(f"Không thể parse chi tiết job {job_id}")
            except Exception as exc:
                failed_count += 1
                logger.warning("[%s] Job %s lỗi: %s -> Hoãn cào chu kỳ tới", self.source, job_id, exc)
                catalog.mark_job_failed_for_next_run(self.source, job_id, str(exc))

        writer.close()
        output_file = str(writer.file_path) if crawled_count > 0 else None
        if output_file and ti:
            ti.xcom_push(key="output_file", value=output_file)

        logger.info(
            "[%s] Pha 2 hoàn tất: %d thành công (SUCCESS), %d hoãn cào kỳ tới (FAILED_RETRY_NEXT_RUN)",
            self.source,
            crawled_count,
            failed_count,
        )

        return {
            "source": self.source,
            "crawled_count": crawled_count,
            "failed_count": failed_count,
            "output_file": output_file,
        }


class DataQualityOperator(BaseOperator):
    """Operator kiểm tra chất lượng dữ liệu của file JSON sinh ra từ crawler task."""

    template_fields = ("file_path",)

    def __init__(
        self,
        file_path: Optional[str] = None,
        source_task_id: Optional[str] = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.file_path = file_path
        self.source_task_id = source_task_id

    def execute(self, context: Context) -> dict[str, Any]:
        target_file = self.file_path

        if not target_file and self.source_task_id:
            target_file = context["ti"].xcom_pull(
                task_ids=self.source_task_id,
                key="output_file",
            )

        if not target_file:
            logger.warning("No output file specified for quality check, skipping.")
            return {"passed": True, "skipped": True}

        logger.info("Running DataQualityCheck on file: %s", target_file)
        checker = DataQualityChecker(target_file)
        report = checker.check()

        if not report["passed"]:
            logger.error("Data Quality check FAILED: %s", report)
            raise ValueError(f"Data quality check failed for {target_file}: {report}")

        return report
