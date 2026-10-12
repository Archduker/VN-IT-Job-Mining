# -*- coding: utf-8 -*-
"""Airflow DAG: Thu thập tin tuyển dụng CNTT định kỳ mỗi 4-5 ngày.

Kiến trúc:
1. Harvest All Listing URLs (Full Listing) -> Trích xuất (job_id, job_url).
2. Deduplication O(1) qua SQLite JobStateCatalog -> Loại bỏ tin đã cào (SUCCESS).
3. Next-Run Retry: Tự động đưa tin lỗi kỳ trước (FAILED_RETRY_NEXT_RUN) vào Hàng đợi cào bù.
4. Detail Crawler Queue -> Cào chi tiết với polite delay, cập nhật trạng thái Catalog.
5. Data Quality Gate -> Xác thực tính toàn vẹn Data Contract v1.

Schedule:
- "0 2 */4 * *": Chạy lúc 02:00 AM mỗi 4 ngày.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Thêm plugins vào sys.path
PLUGINS_DIR = str(Path(__file__).resolve().parents[1] / "plugins")
if PLUGINS_DIR not in sys.path:
    sys.path.insert(0, PLUGINS_DIR)

from airflow import DAG
from crawler_operators import (
    HarvestListingOperator,
    DetailCrawlerQueueOperator,
    DataQualityOperator,
)

DEFAULT_ARGS = {
    "owner": "vn_it_job_team",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

SOURCES = [
    "topdev",
    "careerviet",
    "itviec",
    "vietnamworks",
    "vieclam24h",
    "topcv",
    "glints",
    "jobsgo",
]

with DAG(
    dag_id="periodic_it_job_mining_4days",
    default_args=DEFAULT_ARGS,
    description="Cào gia tăng định kỳ 4 ngày/lần với Hàng đợi 2 giai đoạn, State Catalog (job_id, url) & Next-Run Retry",
    schedule_interval="0 2 */4 * *",  # 02:00 AM mỗi 4 ngày
    start_date=datetime(2026, 10, 1),
    catchup=False,
    max_active_runs=1,
    tags=["crawlers", "periodic", "incremental", "queue", "state_catalog"],
) as dag:

    for src in SOURCES:
        harvest_task = HarvestListingOperator(
            task_id=f"harvest_{src}",
            source=src,
        )

        detail_task = DetailCrawlerQueueOperator(
            task_id=f"crawl_detail_{src}",
            source=src,
            harvest_task_id=f"harvest_{src}",
        )

        quality_task = DataQualityOperator(
            task_id=f"quality_check_{src}",
            source_task_id=f"crawl_detail_{src}",
        )

        harvest_task >> detail_task >> quality_task
