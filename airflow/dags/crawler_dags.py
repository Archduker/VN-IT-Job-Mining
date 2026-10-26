# -*- coding: utf-8 -*-
"""Airflow DAGs configuration for Two-Phase Decoupled IT job scraping:

1. Daily Discovery DAG (`dag_discovery_daily` - 05:00 AM UTC+7):
   - Cố định mỗi ngày cào 1 lần: Quét 1-2 trang mới nhất (sắp xếp theo sort=new) của cả 8 sàn tuyển dụng.
   - Nạp các URL mới vào UrlLedger với status='PENDING'.
   - Phân bổ Pool riêng cho từng nguồn (`pool_{source}`, slots=1) để cách ly triệt để với Phase 2.

2. Weekend-Focused Detail DAGs (`crawler_detail_{source}` - Ca 09:00, 14:00, 18:00, 21:00, 22:00 UTC+7):
   - Khống chế cứng hạn ngạch: Đúng 30 tin / lần cào (thời gian chạy ~1.5 - 2 phút).
   - Tối ưu hóa chi phí EC2 On-Demand & Tránh Cloudflare Rate-Limit qua `AdaptiveRouteCheckOperator`:
     * IDLE (pending = 0): Bỏ qua ngay lập tức trong 0.05 giây.
     * NGÀY THƯỜNG (T2-T6): Ban ngày tự động Skip; chỉ chạy 1 ca tối duy nhất (21:00) bảo trì 30 tin.
     * CUỐI TUẦN (Thứ 7 - CN): Chế độ xả hàng đợi tập trung (5 ca: 09h, 14h, 18h, 21h, 22h), mỗi ca 30 tin, nghỉ 55 phút Cooldown giữa các ca.
   - Pipeline 4 bước: Route Check >> Crawl Detail (30 tin) >> Data Quality >> Preprocess (Staging).
   - Dùng chung `pool_{source}` với Discovery để đảm bảo 2 Phase KHÔNG BAO GIỜ đụng nhau.
"""

from datetime import datetime, timedelta
import sys
from pathlib import Path

plugins_dir = str(Path(__file__).resolve().parents[1] / "plugins")
if plugins_dir not in sys.path:
    sys.path.insert(0, plugins_dir)

from airflow import DAG
from crawler_operators import (
    JobCrawlerOperator,
    DataQualityOperator,
    DataPreprocessOperator,
    AdaptiveRouteCheckOperator,
)

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
# 1. PHA 1: DAILY URL DISCOVERY DAG (Cố định 05:00 sáng hàng ngày - 1 lần/ngày)
# ==============================================================================
with DAG(
    dag_id="dag_discovery_daily",
    default_args=default_args,
    description="Daily URL Discovery for all 8 IT job boards (Lấy link mới nhất 1 lần/ngày)",
    schedule="0 5 * * *",
    start_date=START_DATE,
    catchup=False,
    max_active_runs=1,
    tags=["collection", "discovery", "daily"],
) as discovery_dag:
    
    disc_topdev = JobCrawlerOperator(
        task_id="discover_topdev",
        source="topdev",
        phase="discover",
        max_pages=2,
        pool="pool_topdev",
        execution_timeout=timedelta(minutes=3),
    )
    disc_vietnamworks = JobCrawlerOperator(
        task_id="discover_vietnamworks",
        source="vietnamworks",
        phase="discover",
        max_pages=2,
        pool="pool_vietnamworks",
        execution_timeout=timedelta(minutes=3),
    )
    disc_careerviet = JobCrawlerOperator(
        task_id="discover_careerviet",
        source="careerviet",
        phase="discover",
        max_pages=2,
        pool="pool_careerviet",
        execution_timeout=timedelta(minutes=3),
    )
    disc_vieclam24h = JobCrawlerOperator(
        task_id="discover_vieclam24h",
        source="vieclam24h",
        phase="discover",
        max_pages=2,
        pool="pool_vieclam24h",
        execution_timeout=timedelta(minutes=3),
    )
    disc_itviec = JobCrawlerOperator(
        task_id="discover_itviec",
        source="itviec",
        phase="discover",
        max_pages=2,
        pool="pool_itviec",
        execution_timeout=timedelta(minutes=3),
    )
    disc_topcv = JobCrawlerOperator(
        task_id="discover_topcv",
        source="topcv",
        phase="discover",
        max_pages=2,
        pool="pool_topcv",
        execution_timeout=timedelta(minutes=4),
    )
    disc_jobsgo = JobCrawlerOperator(
        task_id="discover_jobsgo",
        source="jobsgo",
        phase="discover",
        max_pages=2,
        pool="pool_jobsgo",
        execution_timeout=timedelta(minutes=4),
    )
    disc_glints = JobCrawlerOperator(
        task_id="discover_glints",
        source="glints",
        phase="discover",
        max_pages=2,
        pool="pool_glints",
        execution_timeout=timedelta(minutes=4),
    )

    # Chạy thành 2 luồng song song nhẹ nhàng (mỗi luồng 4 nguồn nối tiếp)
    [disc_topdev >> disc_careerviet >> disc_itviec >> disc_glints]
    [disc_vietnamworks >> disc_vieclam24h >> disc_topcv >> disc_jobsgo]


# ==============================================================================
# 2. PHA 2: ADAPTIVE DETAIL CRAWLERS (Linh hoạt theo pending: 08:00 đến 22:00)
# Pipeline: Route Check >> Crawl Detail (30 tin) >> Data Quality >> Preprocess
# ==============================================================================

# 2.1. TopDev
with DAG(
    dag_id="crawler_detail_topdev",
    default_args=default_args,
    description="Adaptive Detail Queue Draining & Preprocessing for TopDev",
    schedule="0 9,14,18,21,22 * * *",
    start_date=START_DATE,
    catchup=False,
    max_active_runs=1,
    tags=["collection", "detail", "topdev"],
) as topdev_dag:
    check_topdev = AdaptiveRouteCheckOperator(
        task_id="check_route_topdev",
        source="topdev",
        pool="pool_topdev",
    )
    crawl_topdev = JobCrawlerOperator(
        task_id="crawl_topdev_detail",
        source="topdev",
        phase="detail",
        max_items=30,
        pool="pool_topdev",
        execution_timeout=timedelta(minutes=4),
    )
    quality_topdev = DataQualityOperator(
        task_id="check_quality_topdev",
        source_task_id="crawl_topdev_detail",
    )
    preprocess_topdev = DataPreprocessOperator(
        task_id="preprocess_topdev",
        source="topdev",
        pool="pool_topdev",
    )
    check_topdev >> crawl_topdev >> quality_topdev >> preprocess_topdev

# 2.2. VietnamWorks
with DAG(
    dag_id="crawler_detail_vietnamworks",
    default_args=default_args,
    description="Adaptive Detail Queue Draining & Preprocessing for VietnamWorks",
    schedule="0 9,14,18,21,22 * * *",
    start_date=START_DATE,
    catchup=False,
    max_active_runs=1,
    tags=["collection", "detail", "vietnamworks"],
) as vnw_dag:
    check_vnw = AdaptiveRouteCheckOperator(
        task_id="check_route_vietnamworks",
        source="vietnamworks",
        pool="pool_vietnamworks",
    )
    crawl_vnw = JobCrawlerOperator(
        task_id="crawl_vietnamworks_detail",
        source="vietnamworks",
        phase="detail",
        max_items=30,
        pool="pool_vietnamworks",
        execution_timeout=timedelta(minutes=4),
    )
    quality_vnw = DataQualityOperator(
        task_id="check_quality_vietnamworks",
        source_task_id="crawl_vietnamworks_detail",
    )
    preprocess_vnw = DataPreprocessOperator(
        task_id="preprocess_vietnamworks",
        source="vietnamworks",
        pool="pool_vietnamworks",
    )
    check_vnw >> crawl_vnw >> quality_vnw >> preprocess_vnw

# 2.3. CareerViet
with DAG(
    dag_id="crawler_detail_careerviet",
    default_args=default_args,
    description="Adaptive Detail Queue Draining & Preprocessing for CareerViet",
    schedule="0 9,14,18,21,22 * * *",
    start_date=START_DATE,
    catchup=False,
    max_active_runs=1,
    tags=["collection", "detail", "careerviet"],
) as cv_dag:
    check_cv = AdaptiveRouteCheckOperator(
        task_id="check_route_careerviet",
        source="careerviet",
        pool="pool_careerviet",
    )
    crawl_cv = JobCrawlerOperator(
        task_id="crawl_careerviet_detail",
        source="careerviet",
        phase="detail",
        max_items=30,
        pool="pool_careerviet",
        execution_timeout=timedelta(minutes=4),
    )
    quality_cv = DataQualityOperator(
        task_id="check_quality_careerviet",
        source_task_id="crawl_careerviet_detail",
    )
    preprocess_cv = DataPreprocessOperator(
        task_id="preprocess_careerviet",
        source="careerviet",
        pool="pool_careerviet",
    )
    check_cv >> crawl_cv >> quality_cv >> preprocess_cv

# 2.4. ViecLam24h
with DAG(
    dag_id="crawler_detail_vieclam24h",
    default_args=default_args,
    description="Adaptive Detail Queue Draining & Preprocessing for ViecLam24h",
    schedule="0 9,14,18,21,22 * * *",
    start_date=START_DATE,
    catchup=False,
    max_active_runs=1,
    tags=["collection", "detail", "vieclam24h"],
) as vl24h_dag:
    check_vl24h = AdaptiveRouteCheckOperator(
        task_id="check_route_vieclam24h",
        source="vieclam24h",
        pool="pool_vieclam24h",
    )
    crawl_vl24h = JobCrawlerOperator(
        task_id="crawl_vieclam24h_detail",
        source="vieclam24h",
        phase="detail",
        max_items=30,
        pool="pool_vieclam24h",
        execution_timeout=timedelta(minutes=4),
    )
    quality_vl24h = DataQualityOperator(
        task_id="check_quality_vieclam24h",
        source_task_id="crawl_vieclam24h_detail",
    )
    preprocess_vl24h = DataPreprocessOperator(
        task_id="preprocess_vieclam24h",
        source="vieclam24h",
        pool="pool_vieclam24h",
    )
    check_vl24h >> crawl_vl24h >> quality_vl24h >> preprocess_vl24h

# 2.5. ITviec
with DAG(
    dag_id="crawler_detail_itviec",
    default_args=default_args,
    description="Adaptive Detail Queue Draining & Preprocessing for ITviec",
    schedule="0 9,14,18,21,22 * * *",
    start_date=START_DATE,
    catchup=False,
    max_active_runs=1,
    tags=["collection", "detail", "itviec"],
) as itviec_dag:
    check_itviec = AdaptiveRouteCheckOperator(
        task_id="check_route_itviec",
        source="itviec",
        pool="pool_itviec",
    )
    crawl_itviec = JobCrawlerOperator(
        task_id="crawl_itviec_detail",
        source="itviec",
        phase="detail",
        max_items=30,
        pool="pool_itviec",
        execution_timeout=timedelta(minutes=5),
    )
    quality_itviec = DataQualityOperator(
        task_id="check_quality_itviec",
        source_task_id="crawl_itviec_detail",
    )
    preprocess_itviec = DataPreprocessOperator(
        task_id="preprocess_itviec",
        source="itviec",
        pool="pool_itviec",
    )
    check_itviec >> crawl_itviec >> quality_itviec >> preprocess_itviec

# 2.6. TopCV (Trọng điểm dồn ứ: Surge Duty-Cycle 30 tin / 1h Cooldown)
with DAG(
    dag_id="crawler_detail_topcv",
    default_args=default_args,
    description="Adaptive Detail Queue Draining & Preprocessing for TopCV",
    schedule="0 9,14,18,21,22 * * *",
    start_date=START_DATE,
    catchup=False,
    max_active_runs=1,
    tags=["collection", "detail", "topcv"],
) as topcv_dag:
    check_topcv = AdaptiveRouteCheckOperator(
        task_id="check_route_topcv",
        source="topcv",
        pool="pool_topcv",
    )
    crawl_topcv = JobCrawlerOperator(
        task_id="crawl_topcv_detail",
        source="topcv",
        phase="detail",
        max_items=30,
        pool="pool_topcv",
        execution_timeout=timedelta(minutes=5),
    )
    quality_topcv = DataQualityOperator(
        task_id="check_quality_topcv",
        source_task_id="crawl_topcv_detail",
    )
    preprocess_topcv = DataPreprocessOperator(
        task_id="preprocess_topcv",
        source="topcv",
        pool="pool_topcv",
    )
    check_topcv >> crawl_topcv >> quality_topcv >> preprocess_topcv

# 2.7. JobsGO
with DAG(
    dag_id="crawler_detail_jobsgo",
    default_args=default_args,
    description="Adaptive Detail Queue Draining & Preprocessing for JobsGO",
    schedule="0 9,14,18,21,22 * * *",
    start_date=START_DATE,
    catchup=False,
    max_active_runs=1,
    tags=["collection", "detail", "jobsgo"],
) as jobsgo_dag:
    check_jobsgo = AdaptiveRouteCheckOperator(
        task_id="check_route_jobsgo",
        source="jobsgo",
        pool="pool_jobsgo",
    )
    crawl_jobsgo = JobCrawlerOperator(
        task_id="crawl_jobsgo_detail",
        source="jobsgo",
        phase="detail",
        max_items=30,
        pool="pool_jobsgo",
        execution_timeout=timedelta(minutes=5),
    )
    quality_jobsgo = DataQualityOperator(
        task_id="check_quality_jobsgo",
        source_task_id="crawl_jobsgo_detail",
    )
    preprocess_jobsgo = DataPreprocessOperator(
        task_id="preprocess_jobsgo",
        source="jobsgo",
        pool="pool_jobsgo",
    )
    check_jobsgo >> crawl_jobsgo >> quality_jobsgo >> preprocess_jobsgo

# 2.8. Glints
with DAG(
    dag_id="crawler_detail_glints",
    default_args=default_args,
    description="Adaptive Detail Queue Draining & Preprocessing for Glints Vietnam",
    schedule="0 9,14,18,21,22 * * *",
    start_date=START_DATE,
    catchup=False,
    max_active_runs=1,
    tags=["collection", "detail", "glints"],
) as glints_dag:
    check_glints = AdaptiveRouteCheckOperator(
        task_id="check_route_glints",
        source="glints",
        pool="pool_glints",
    )
    crawl_glints = JobCrawlerOperator(
        task_id="crawl_glints_detail",
        source="glints",
        phase="detail",
        max_items=30,
        pool="pool_glints",
        execution_timeout=timedelta(minutes=5),
    )
    quality_glints = DataQualityOperator(
        task_id="check_quality_glints",
        source_task_id="crawl_glints_detail",
    )
    preprocess_glints = DataPreprocessOperator(
        task_id="preprocess_glints",
        source="glints",
        pool="pool_glints",
    )
    check_glints >> crawl_glints >> quality_glints >> preprocess_glints
