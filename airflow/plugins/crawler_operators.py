# -*- coding: utf-8 -*-
"""Custom Airflow Operators for VN-IT-Job-Mining.

Bao gồm:
- JobCrawlerOperator: Điều khiển crawler theo từng nguồn.
- DataQualityOperator: Kiểm tra tính toàn vẹn và chất lượng sau mỗi lần cào.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from airflow.models import BaseOperator
from airflow.utils.context import Context

from crawlers.common.data_quality import DataQualityChecker

logger = logging.getLogger("airflow.operators.vn_it_job")


class JobCrawlerOperator(BaseOperator):
    """Operator để chạy crawler của một nguồn cụ thể."""

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
            from crawlers.sources.itviec.crawler import crawl
            stats = crawl(max_items=self.max_items)
            return stats
        else:
            raise ValueError(f"Unknown source: {self.source}")

        crawler = crawler_cls(output_dir=self.output_dir, max_items=self.max_items)
        stats = crawler.run()

        # Push file path to XCom for quality check task
        if stats.get("output_file"):
            context["ti"].xcom_push(key="output_file", value=stats["output_file"])

        return stats


class DataQualityOperator(BaseOperator):
    """Operator kiểm tra chất lượng dữ liệu của file JSONL sinh ra từ crawler task."""

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
