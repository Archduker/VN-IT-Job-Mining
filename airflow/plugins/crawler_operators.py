# -*- coding: utf-8 -*-
"""Custom Airflow Operators for VN-IT-Job-Mining.

Bao gồm:
- JobCrawlerOperator: Điều khiển crawler theo từng nguồn.
- DataQualityOperator: Kiểm tra tính toàn vẹn và chất lượng sau mỗi lần cào.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from airflow.models import BaseOperator
from airflow.utils.context import Context

from crawlers.common.data_quality import DataQualityChecker
from crawlers.common.minio_storage import upload_file_to_minio
from run import run_crawler

logger = logging.getLogger("airflow.operators.vn_it_job")

SOURCE_PROFILES = {
    "topdev": {"max_items": 50, "max_pages": 2, "timeout_minutes": 3},
    "vietnamworks": {"max_items": 50, "max_pages": 2, "timeout_minutes": 3},
    "careerviet": {"max_items": 40, "max_pages": 2, "timeout_minutes": 4},
    "vieclam24h": {"max_items": 40, "max_pages": 2, "timeout_minutes": 4},
    "itviec": {"max_items": 35, "max_pages": 2, "timeout_minutes": 5},
    "topcv": {"max_items": 25, "max_pages": 2, "timeout_minutes": 6},
    "jobsgo": {"max_items": 25, "max_pages": 2, "timeout_minutes": 6},
    "glints": {"max_items": 20, "max_pages": 2, "timeout_minutes": 7},
}


class JobCrawlerOperator(BaseOperator):
    """Operator để chạy crawler của một nguồn cụ thể theo từng Pha (Phase)."""

    template_fields = ("source", "phase", "max_items", "max_pages")

    def __init__(
        self,
        source: str,
        phase: str = "detail",
        max_items: Optional[int] = None,
        max_pages: Optional[int] = None,
        output_dir: Optional[str] = "data",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.source = source.lower().strip()
        self.phase = phase.lower().strip()
        profile = SOURCE_PROFILES.get(self.source, {"max_items": 30, "max_pages": 2})
        self.max_items = max_items if max_items is not None else profile["max_items"]
        self.max_pages = max_pages if max_pages is not None else profile["max_pages"]
        self.output_dir = output_dir

    def execute(self, context: Context) -> dict[str, Any]:
        logger.info(
            "Executing JobCrawlerOperator for source='%s', phase='%s', max_items=%s, max_pages=%s",
            self.source,
            self.phase,
            self.max_items,
            self.max_pages,
        )

        stats = run_crawler(
            source=self.source,
            max_items=self.max_items,
            output_dir=self.output_dir or "data",
            phase=self.phase,
            max_pages=self.max_pages,
        )

        if stats.get("output_file"):
            output_path = Path(stats["output_file"])
            object_key = f"raw/{self.source}/{output_path.parent.name}/{output_path.name}"
            try:
                stats["minio_uri"] = upload_file_to_minio(
                    output_path,
                    object_key=object_key,
                )
                logger.info("Uploaded %s crawl output to %s", self.source, stats["minio_uri"])
            except Exception as up_err:
                logger.warning("Auto-upload to lakehouse skipped or failed for %s: %s", self.source, up_err)

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
