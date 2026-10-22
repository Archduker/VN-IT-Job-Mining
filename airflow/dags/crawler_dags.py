# -*- coding: utf-8 -*-
"""Airflow DAGs configuration for Two-Phase Decoupled IT job scraping:

1. Daily Discovery DAG (`dag_discovery_daily` - 05:00 AM UTC+7):
   - Fast & lightweight: Quét 1-2 trang mới nhất của cả 8 sàn tuyển dụng.
   - Hoàn thành trong 2-3 phút, nạp các URL mới vào UrlLedger với status='PENDING'.

2. Staggered Daily Detail DAGs (`crawler_detail_{source}` - 20:00 to 23:00 UTC+7):
   - Chạy hàng ngày theo hạn mức quota kiểm soát (Queue Consumer) để tiêu thụ PENDING/RECHECK_DUE.
   - Giãn cách 25 phút giữa các nguồn để VPS không bao giờ bị nghẽn RAM / quá tải CPU.
"""

from datetime import datetime, timedelta
import sys
from pathlib import Path

plugins_dir = str(Path(__file__).resolve().parents[1] / "plugins")
if plugins_dir not in sys.path:
    sys.path.insert(0, plugins_dir)

from airflow import DAG
from crawler_operators import JobCrawlerOperator, DataQualityOperator

default_args = {
    "owner": "vn_it_job_team",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=3),
}

START_DATE = datetime(2026, 10, 1)

# ==============================================================================
# 1. PHA 1: DAILY URL DISCOVERY DAG (Chạy lúc 05:00 sáng hàng ngày)
# ==============================================================================
with DAG(
    dag_id="dag_discovery_daily",
    default_args=default_args,
    description="Daily URL Discovery for all 8 IT job boards (Lấy link mới nhất)",
    schedule_interval="0 5 * * *",
    start_date=START_DATE,
    catchup=False,
    tags=["crawlers", "discovery", "daily"],
) as discovery_dag:
    
    disc_topdev = JobCrawlerOperator(
        task_id="discover_topdev",
        source="topdev",
        phase="discover",
        max_pages=2,
        execution_timeout=timedelta(minutes=3),
    )
    disc_vietnamworks = JobCrawlerOperator(
        task_id="discover_vietnamworks",
        source="vietnamworks",
        phase="discover",
        max_pages=2,
        execution_timeout=timedelta(minutes=3),
    )
    disc_careerviet = JobCrawlerOperator(
        task_id="discover_careerviet",
        source="careerviet",
        phase="discover",
        max_pages=2,
        execution_timeout=timedelta(minutes=3),
    )
    disc_vieclam24h = JobCrawlerOperator(
        task_id="discover_vieclam24h",
        source="vieclam24h",
        phase="discover",
        max_pages=2,
        execution_timeout=timedelta(minutes=3),
    )
    disc_itviec = JobCrawlerOperator(
        task_id="discover_itviec",
        source="itviec",
        phase="discover",
        max_pages=2,
        execution_timeout=timedelta(minutes=3),
    )
    disc_topcv = JobCrawlerOperator(
        task_id="discover_topcv",
        source="topcv",
        phase="discover",
        max_pages=2,
        execution_timeout=timedelta(minutes=4),
    )
    disc_jobsgo = JobCrawlerOperator(
        task_id="discover_jobsgo",
        source="jobsgo",
        phase="discover",
        max_pages=2,
        execution_timeout=timedelta(minutes=4),
    )
    disc_glints = JobCrawlerOperator(
        task_id="discover_glints",
        source="glints",
        phase="discover",
        max_pages=2,
        execution_timeout=timedelta(minutes=4),
    )

    # Chạy thành 2 luồng song song nhẹ nhàng (mỗi luồng 4 nguồn nối tiếp)
    [disc_topdev >> disc_careerviet >> disc_itviec >> disc_glints]
    [disc_vietnamworks >> disc_vieclam24h >> disc_topcv >> disc_jobsgo]


# ==============================================================================
# 2. PHA 2: STAGGERED DAILY DETAIL CRAWLERS (Giãn cách 25 phút hàng đêm)
# ==============================================================================

# 2.1. TopDev (20:00 - Quota: 50 tin, Timeout: 3 phút)
with DAG(
    dag_id="crawler_detail_topdev",
    default_args=default_args,
    description="Daily Detail Queue Draining for TopDev",
    schedule_interval="0 20 * * *",
    start_date=START_DATE,
    catchup=False,
    tags=["crawlers", "detail", "topdev"],
) as topdev_dag:
    crawl_topdev = JobCrawlerOperator(
        task_id="crawl_topdev_detail",
        source="topdev",
        phase="detail",
        max_items=50,
        execution_timeout=timedelta(minutes=3),
    )
    quality_topdev = DataQualityOperator(
        task_id="check_quality_topdev",
        source_task_id="crawl_topdev_detail",
    )
    crawl_topdev >> quality_topdev

# 2.2. VietnamWorks (20:25 - Quota: 50 tin, Timeout: 3 phút)
with DAG(
    dag_id="crawler_detail_vietnamworks",
    default_args=default_args,
    description="Daily Detail Queue Draining for VietnamWorks",
    schedule_interval="25 20 * * *",
    start_date=START_DATE,
    catchup=False,
    tags=["crawlers", "detail", "vietnamworks"],
) as vnw_dag:
    crawl_vnw = JobCrawlerOperator(
        task_id="crawl_vietnamworks_detail",
        source="vietnamworks",
        phase="detail",
        max_items=50,
        execution_timeout=timedelta(minutes=3),
    )
    quality_vnw = DataQualityOperator(
        task_id="check_quality_vietnamworks",
        source_task_id="crawl_vietnamworks_detail",
    )
    crawl_vnw >> quality_vnw

# 2.3. CareerViet (20:50 - Quota: 40 tin, Timeout: 4 phút)
with DAG(
    dag_id="crawler_detail_careerviet",
    default_args=default_args,
    description="Daily Detail Queue Draining for CareerViet",
    schedule_interval="50 20 * * *",
    start_date=START_DATE,
    catchup=False,
    tags=["crawlers", "detail", "careerviet"],
) as cv_dag:
    crawl_cv = JobCrawlerOperator(
        task_id="crawl_careerviet_detail",
        source="careerviet",
        phase="detail",
        max_items=40,
        execution_timeout=timedelta(minutes=4),
    )
    quality_cv = DataQualityOperator(
        task_id="check_quality_careerviet",
        source_task_id="crawl_careerviet_detail",
    )
    crawl_cv >> quality_cv

# 2.4. ViecLam24h (21:15 - Quota: 40 tin, Timeout: 4 phút)
with DAG(
    dag_id="crawler_detail_vieclam24h",
    default_args=default_args,
    description="Daily Detail Queue Draining for ViecLam24h",
    schedule_interval="15 21 * * *",
    start_date=START_DATE,
    catchup=False,
    tags=["crawlers", "detail", "vieclam24h"],
) as vl24h_dag:
    crawl_vl24h = JobCrawlerOperator(
        task_id="crawl_vieclam24h_detail",
        source="vieclam24h",
        phase="detail",
        max_items=40,
        execution_timeout=timedelta(minutes=4),
    )
    quality_vl24h = DataQualityOperator(
        task_id="check_quality_vieclam24h",
        source_task_id="crawl_vieclam24h_detail",
    )
    crawl_vl24h >> quality_vl24h

# 2.5. ITviec (21:40 - Quota: 35 tin, Timeout: 5 phút)
with DAG(
    dag_id="crawler_detail_itviec",
    default_args=default_args,
    description="Daily Detail Queue Draining for ITviec",
    schedule_interval="40 21 * * *",
    start_date=START_DATE,
    catchup=False,
    tags=["crawlers", "detail", "itviec"],
) as itviec_dag:
    crawl_itviec = JobCrawlerOperator(
        task_id="crawl_itviec_detail",
        source="itviec",
        phase="detail",
        max_items=35,
        execution_timeout=timedelta(minutes=5),
    )
    quality_itviec = DataQualityOperator(
        task_id="check_quality_itviec",
        source_task_id="crawl_itviec_detail",
    )
    crawl_itviec >> quality_itviec

# 2.6. TopCV (22:05 - Quota: 25 tin, Timeout: 6 phút)
with DAG(
    dag_id="crawler_detail_topcv",
    default_args=default_args,
    description="Daily Detail Queue Draining for TopCV",
    schedule_interval="5 22 * * *",
    start_date=START_DATE,
    catchup=False,
    tags=["crawlers", "detail", "topcv"],
) as topcv_dag:
    crawl_topcv = JobCrawlerOperator(
        task_id="crawl_topcv_detail",
        source="topcv",
        phase="detail",
        max_items=25,
        execution_timeout=timedelta(minutes=6),
    )
    quality_topcv = DataQualityOperator(
        task_id="check_quality_topcv",
        source_task_id="crawl_topcv_detail",
    )
    crawl_topcv >> quality_topcv

# 2.7. JobsGO (22:30 - Quota: 25 tin, Timeout: 6 phút)
with DAG(
    dag_id="crawler_detail_jobsgo",
    default_args=default_args,
    description="Daily Detail Queue Draining for JobsGO",
    schedule_interval="30 22 * * *",
    start_date=START_DATE,
    catchup=False,
    tags=["crawlers", "detail", "jobsgo"],
) as jobsgo_dag:
    crawl_jobsgo = JobCrawlerOperator(
        task_id="crawl_jobsgo_detail",
        source="jobsgo",
        phase="detail",
        max_items=25,
        execution_timeout=timedelta(minutes=6),
    )
    quality_jobsgo = DataQualityOperator(
        task_id="check_quality_jobsgo",
        source_task_id="crawl_jobsgo_detail",
    )
    crawl_jobsgo >> quality_jobsgo

# 2.8. Glints (22:55 - Quota: 20 tin, Timeout: 7 phút)
with DAG(
    dag_id="crawler_detail_glints",
    default_args=default_args,
    description="Daily Detail Queue Draining for Glints Vietnam",
    schedule_interval="55 22 * * *",
    start_date=START_DATE,
    catchup=False,
    tags=["crawlers", "detail", "glints"],
) as glints_dag:
    crawl_glints = JobCrawlerOperator(
        task_id="crawl_glints_detail",
        source="glints",
        phase="detail",
        max_items=20,
        execution_timeout=timedelta(minutes=7),
    )
    quality_glints = DataQualityOperator(
        task_id="check_quality_glints",
        source_task_id="crawl_glints_detail",
    )
    crawl_glints >> quality_glints
