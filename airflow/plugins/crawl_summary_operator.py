# -*- coding: utf-8 -*-
"""
airflow.plugins.crawl_summary_operator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Operator Airflow tổng hợp kết quả từ tất cả crawl tasks trong 1 DAG run.

File này ĐỘC LẬP hoàn toàn với crawler_operators.py — không import chéo,
không conflict với Task 1.

Chức năng:
  - Đọc XCom stats từ từng crawl task
  - Tổng hợp: total_new_jobs, total_skipped, total_errors
  - Ghi JSON report vào logs/crawl_reports/crawl_report_<run_date>.json

Cách import:
  from crawl_summary_operator import CrawlSummaryOperator
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Đảm bảo project root trong sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from airflow.models import BaseOperator
from airflow.utils.context import Context

logger = logging.getLogger("airflow.operators.crawl_summary")

REPORTS_DIR = PROJECT_ROOT / "logs" / "crawl_reports"


class CrawlSummaryOperator(BaseOperator):
    """
    Operator tổng hợp kết quả từ tất cả crawl tasks và ghi báo cáo JSON.

    Đọc XCom từ các crawl tasks (JobCrawlerOperator hoặc DetailCrawlerQueueOperator)
    và ghi tổng hợp vào:
        logs/crawl_reports/crawl_report_<run_date>.json

    Ví dụ dùng trong DAG:
        from crawl_summary_operator import CrawlSummaryOperator

        summary = CrawlSummaryOperator(
            task_id="weekly_summary",
            source_task_ids=["crawl_topdev", "crawl_careerviet", ...],
        )
        [crawl_topdev, crawl_careerviet, ...] >> summary

    Attributes:
        source_task_ids: Danh sách task_id của các crawl tasks cần tổng hợp.
    """

    template_fields = ("source_task_ids",)

    def __init__(
        self,
        source_task_ids: List[str],
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.source_task_ids = source_task_ids

    def execute(self, context: Context) -> Dict[str, Any]:
        run_date = context["ds"]  # YYYY-MM-DD
        dag_id   = context["dag"].dag_id
        exec_ts  = str(context.get("execution_date", datetime.now(timezone.utc)))

        logger.info(
            "[CrawlSummary] Bắt đầu tổng hợp kết quả %d crawl tasks | dag=%s | run_date=%s",
            len(self.source_task_ids),
            dag_id,
            run_date,
        )

        report: Dict[str, Any] = {
            "run_date": run_date,
            "dag_id": dag_id,
            "execution_date": exec_ts,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_new_jobs": 0,
            "total_skipped": 0,
            "total_errors": 0,
            "sources": {},
        }

        for task_id in self.source_task_ids:
            # Thử đọc XCom — tương thích với cả JobCrawlerOperator và DetailCrawlerQueueOperator
            raw_stats: Optional[Dict[str, Any]] = None
            try:
                raw_stats = context["ti"].xcom_pull(
                    task_ids=task_id,
                    key="return_value",
                )
            except Exception as exc:
                logger.warning("[CrawlSummary] Không đọc được XCom từ task %s: %s", task_id, exc)

            if raw_stats is None:
                raw_stats = {}

            # Chuẩn hóa key (tương thích cả JobCrawlerOperator lẫn DetailCrawlerQueueOperator)
            new_jobs  = (
                raw_stats.get("crawled", 0)         # JobCrawlerOperator
                or raw_stats.get("crawled_count", 0) # DetailCrawlerQueueOperator
            )
            skipped   = raw_stats.get("skipped", 0)
            errors    = (
                raw_stats.get("errors", 0)
                or raw_stats.get("failed_count", 0)
            )
            total_seen = raw_stats.get("total_seen", 0)
            output_file = raw_stats.get("output_file")

            # Lấy tên source từ task_id (bỏ prefix "crawl_")
            source_name = task_id.replace("crawl_detail_", "").replace("crawl_", "")

            report["sources"][source_name] = {
                "task_id":              task_id,
                "new_jobs":             new_jobs,
                "skipped":              skipped,
                "errors":               errors,
                "total_seen_checkpoint": total_seen,
                "output_file":          output_file,
            }

            report["total_new_jobs"] += new_jobs
            report["total_skipped"]  += skipped
            report["total_errors"]   += errors

            logger.info(
                "[CrawlSummary] %-20s → new=%-5d  skip=%-5d  err=%-3d  file=%s",
                source_name,
                new_jobs,
                skipped,
                errors,
                output_file or "—",
            )

        # Ghi report ra file
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report_path = REPORTS_DIR / f"crawl_report_{run_date}.json"

        try:
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False, default=str)
            logger.info(
                "[CrawlSummary] ✅ Report đã ghi → %s | total_new=%d  skip=%d  err=%d",
                report_path,
                report["total_new_jobs"],
                report["total_skipped"],
                report["total_errors"],
            )
        except Exception as exc:
            logger.error("[CrawlSummary] Lỗi khi ghi report file %s: %s", report_path, exc)
            # Không raise — summary failure không nên làm hỏng toàn bộ DAG
            report["write_error"] = str(exc)

        return report
