# -*- coding: utf-8 -*-
"""Airflow DAGs configuration for rotating daily IT job scraping.

Schedule (DAG cũ — hoạt động ổn định, giữ nguyên):
- Monday (Thứ Hai 20:00)    : TopDev
- Tuesday (Thứ Ba 20:00)    : CareerViet
- Wednesday (Thứ Tư 20:00)  : ITviec
- Thursday (Thứ Năm 20:00)  : VietnamWorks
- Friday (Thứ Sáu 20:00)    : TopCV
- Saturday (Thứ Bảy 20:00)  : ViecLam24h
- Sunday (Chủ Nhật 20:00)   : Glints

DAG mới (Task 2):
- crawler_weekly_all: Chủ Nhật 22:00 — Chạy toàn bộ 7 nguồn song song
  (dùng để demo, dùng JobCrawlerOperator + CrawlSummaryOperator)
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Thêm plugins vào sys.path
PLUGINS_DIR = str(Path(__file__).resolve().parents[1] / "plugins")
if PLUGINS_DIR not in sys.path:
    sys.path.insert(0, PLUGINS_DIR)

from airflow import DAG
from crawler_operators import JobCrawlerOperator, DataQualityOperator
from crawl_summary_operator import CrawlSummaryOperator

log = logging.getLogger("airflow.dags.crawler_dags")

# ── Danh sách nguồn cho DAG weekly_all ────────────────────────────────────────
ALL_SOURCES = [
    "topdev",
    "careerviet",
    "itviec",
    "vietnamworks",
    "topcv",
    "vieclam24h",
    "glints",
]


# ── Callbacks: ghi log rõ ràng khi task hoàn tất ─────────────────────────────
def _on_crawl_success(context: dict) -> None:
    """Log khi crawl task thành công — hiển thị số tin MỚI / BỎ QUA."""
    ti = context.get("ti")
    if ti is None:
        return
    stats = ti.xcom_pull(key="return_value") or {}
    new_jobs  = stats.get("crawled", 0)
    skipped   = stats.get("skipped", 0)    # Tin đã có trong checkpoint → bỏ qua
    errors    = stats.get("errors", 0)
    out_file  = stats.get("output_file", "N/A")
    log.info(
        "✅ [%s] THÀNH CÔNG | Tin MỚI: %d | Bỏ qua (đã có): %d | Lỗi: %d | File: %s",
        ti.task_id, new_jobs, skipped, errors, out_file,
    )


def _on_crawl_failure(context: dict) -> None:
    """Log khi crawl task thất bại."""
    ti = context.get("ti")
    exc = context.get("exception")
    task_id = ti.task_id if ti else "unknown"
    attempt = ti.try_number if ti else "?"
    log.error(
        "❌ [%s] THẤT BẠI | Lần thử: %s | Lỗi: %s",
        task_id, attempt, exc,
    )


# ── Default args (dùng chung cho tất cả DAGs) ────────────────────────────────
default_args = {
    "owner": "vn_it_job_team",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "on_success_callback": _on_crawl_success,
    "on_failure_callback": _on_crawl_failure,
}

# =============================================================================
# 1. TopDev — Thứ Hai 20:00
# =============================================================================
with DAG(
    dag_id="crawler_topdev",
    default_args=default_args,
    description="Crawl tin MỚI từ TopDev (Thứ Hai 20:00)",
    schedule_interval="0 20 * * 1",
    start_date=datetime(2026, 10, 1),
    catchup=False,
    tags=["crawlers", "topdev"],
) as topdev_dag:
    crawl_topdev = JobCrawlerOperator(
        task_id="crawl_topdev",
        source="topdev",
        max_items=100,
    )
    quality_topdev = DataQualityOperator(
        task_id="check_quality_topdev",
        source_task_id="crawl_topdev",
    )
    crawl_topdev >> quality_topdev

# =============================================================================
# 2. CareerViet — Thứ Ba 20:00
# =============================================================================
with DAG(
    dag_id="crawler_careerviet",
    default_args=default_args,
    description="Crawl tin MỚI từ CareerViet (Thứ Ba 20:00)",
    schedule_interval="0 20 * * 2",
    start_date=datetime(2026, 10, 1),
    catchup=False,
    tags=["crawlers", "careerviet"],
) as careerviet_dag:
    crawl_careerviet = JobCrawlerOperator(
        task_id="crawl_careerviet",
        source="careerviet",
        max_items=100,
    )
    quality_careerviet = DataQualityOperator(
        task_id="check_quality_careerviet",
        source_task_id="crawl_careerviet",
    )
    crawl_careerviet >> quality_careerviet

# =============================================================================
# 3. ITviec — Thứ Tư 20:00  [FIX: thêm DataQualityOperator bị thiếu]
# =============================================================================
with DAG(
    dag_id="crawler_itviec",
    default_args=default_args,
    description="Crawl tin MỚI từ ITviec (Thứ Tư 20:00)",
    schedule_interval="0 20 * * 3",
    start_date=datetime(2026, 10, 1),
    catchup=False,
    tags=["crawlers", "itviec"],
) as itviec_dag:
    crawl_itviec = JobCrawlerOperator(
        task_id="crawl_itviec",
        source="itviec",
        max_items=100,
    )
    quality_itviec = DataQualityOperator(
        task_id="check_quality_itviec",
        source_task_id="crawl_itviec",
    )
    crawl_itviec >> quality_itviec  # FIX: đã nối pipeline đầy đủ

# =============================================================================
# 4. VietnamWorks — Thứ Năm 20:00
# =============================================================================
with DAG(
    dag_id="crawler_vietnamworks",
    default_args=default_args,
    description="Crawl tin MỚI từ VietnamWorks (Thứ Năm 20:00)",
    schedule_interval="0 20 * * 4",
    start_date=datetime(2026, 10, 1),
    catchup=False,
    tags=["crawlers", "vietnamworks"],
) as vietnamworks_dag:
    crawl_vietnamworks = JobCrawlerOperator(
        task_id="crawl_vietnamworks",
        source="vietnamworks",
        max_items=100,
    )
    quality_vietnamworks = DataQualityOperator(
        task_id="check_quality_vietnamworks",
        source_task_id="crawl_vietnamworks",
    )
    crawl_vietnamworks >> quality_vietnamworks

# =============================================================================
# 5. TopCV — Thứ Sáu 20:00
# =============================================================================
with DAG(
    dag_id="crawler_topcv",
    default_args=default_args,
    description="Crawl tin MỚI từ TopCV (Thứ Sáu 20:00)",
    schedule_interval="0 20 * * 5",
    start_date=datetime(2026, 10, 1),
    catchup=False,
    tags=["crawlers", "topcv"],
) as topcv_dag:
    crawl_topcv = JobCrawlerOperator(
        task_id="crawl_topcv",
        source="topcv",
        max_items=50,
    )
    quality_topcv = DataQualityOperator(
        task_id="check_quality_topcv",
        source_task_id="crawl_topcv",
    )
    crawl_topcv >> quality_topcv

# =============================================================================
# 6. ViecLam24h — Thứ Bảy 20:00
# =============================================================================
with DAG(
    dag_id="crawler_vieclam24h",
    default_args=default_args,
    description="Crawl tin MỚI từ ViecLam24h (Thứ Bảy 20:00)",
    schedule_interval="0 20 * * 6",
    start_date=datetime(2026, 10, 1),
    catchup=False,
    tags=["crawlers", "vieclam24h"],
) as vieclam24h_dag:
    crawl_vieclam24h = JobCrawlerOperator(
        task_id="crawl_vieclam24h",
        source="vieclam24h",
        max_items=100,
    )
    quality_vieclam24h = DataQualityOperator(
        task_id="check_quality_vieclam24h",
        source_task_id="crawl_vieclam24h",
    )
    crawl_vieclam24h >> quality_vieclam24h

# =============================================================================
# 7. Glints — Chủ Nhật 20:00
# =============================================================================
with DAG(
    dag_id="crawler_glints",
    default_args=default_args,
    description="Crawl tin MỚI từ Glints Vietnam (Chủ Nhật 20:00)",
    schedule_interval="0 20 * * 0",
    start_date=datetime(2026, 10, 1),
    catchup=False,
    tags=["crawlers", "glints"],
) as glints_dag:
    crawl_glints = JobCrawlerOperator(
        task_id="crawl_glints",
        source="glints",
        max_items=50,
    )
    quality_glints = DataQualityOperator(
        task_id="check_quality_glints",
        source_task_id="crawl_glints",
    )
    crawl_glints >> quality_glints

# =============================================================================
# 8. [MỚI] crawler_weekly_all — Chủ Nhật 22:00
#    Chạy toàn bộ 7 nguồn SONG SONG rồi tổng hợp báo cáo.
#    Dùng để demo cho thầy hoặc trigger thủ công bất kỳ lúc nào.
# =============================================================================
with DAG(
    dag_id="crawler_weekly_all",
    default_args=default_args,
    description=(
        "[MASTER] Crawl tin MỚI từ tất cả 7 nguồn SONG SONG — Chủ Nhật 22:00. "
        "Dùng để demo hoặc trigger thủ công."
    ),
    schedule_interval="0 22 * * 0",   # Chủ Nhật 22:00
    start_date=datetime(2026, 10, 1),
    catchup=False,
    max_active_runs=1,
    tags=["master", "weekly", "all-sources", "demo"],
) as weekly_dag:

    # Tạo crawl task + quality task cho từng nguồn (chạy song song nhau)
    weekly_crawl_tasks = []
    for src in ALL_SOURCES:
        t_crawl = JobCrawlerOperator(
            task_id=f"crawl_{src}",
            source=src,
            # 50 tin mới mỗi nguồn mỗi lần chạy — vì đã có checkpoint dedup,
            # số lượng này chỉ tính tin CHƯA CÓ trong checkpoint
            max_items=50,
        )
        t_quality = DataQualityOperator(
            task_id=f"check_quality_{src}",
            source_task_id=f"crawl_{src}",
        )
        t_crawl >> t_quality
        weekly_crawl_tasks.append(t_quality)  # Summary chờ quality xong

    # CrawlSummaryOperator: tổng hợp sau khi tất cả nguồn hoàn tất
    summary = CrawlSummaryOperator(
        task_id="weekly_summary",
        source_task_ids=[f"crawl_{s}" for s in ALL_SOURCES],
    )

    # Tất cả quality tasks >> summary
    weekly_crawl_tasks >> summary
