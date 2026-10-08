# -*- coding: utf-8 -*-
"""Airflow DAGs configuration for rotating daily IT job scraping.

Schedule:
- Monday (Thứ Hai 20:00)    : TopDev
- Tuesday (Thứ Ba 20:00)    : CareerViet
- Wednesday (Thứ Tư 20:00)  : ITviec
- Thursday (Thứ Năm 20:00)  : VietnamWorks
- Friday (Thứ Sáu 20:00)    : TopCV
- Saturday (Thứ Bảy 20:00)  : ViecLam24h
"""

from datetime import datetime, timedelta
from airflow import DAG
from crawler_operators import JobCrawlerOperator, DataQualityOperator

default_args = {
    "owner": "vn_it_job_team",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# 1. TopDev (Thứ Hai 20:00)
with DAG(
    dag_id="crawler_topdev",
    default_args=default_args,
    description="Crawl IT jobs from TopDev",
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

# 2. CareerViet (Thứ Ba 20:00)
with DAG(
    dag_id="crawler_careerviet",
    default_args=default_args,
    description="Crawl IT jobs from CareerViet",
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

# 3. ITviec (Thứ Tư 20:00)
with DAG(
    dag_id="crawler_itviec",
    default_args=default_args,
    description="Crawl IT jobs from ITviec",
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
    crawl_itviec

# 4. VietnamWorks (Thứ Năm 20:00)
with DAG(
    dag_id="crawler_vietnamworks",
    default_args=default_args,
    description="Crawl IT jobs from VietnamWorks",
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

# 5. TopCV (Thứ Sáu 20:00)
with DAG(
    dag_id="crawler_topcv",
    default_args=default_args,
    description="Crawl IT jobs from TopCV",
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

# 6. ViecLam24h (Thứ Bảy 20:00)
with DAG(
    dag_id="crawler_vieclam24h",
    default_args=default_args,
    description="Crawl IT jobs from ViecLam24h",
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
