# -*- coding: utf-8 -*-
"""Kiểm thử tự động các endpoints của Monitoring Backend API."""

import pytest
import sys
from pathlib import Path
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent / "monitoring" / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import app

client = TestClient(app)


def test_root_health():
    """Kiểm tra endpoint gốc."""
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "online"
    assert "VN-IT-Job-Mining" in data["system"]


def test_master_dashboard_endpoints():
    """Kiểm tra endpoint api/Dashboard và /api/v1/dashboard."""
    for url in ["/api/dashboard", "/api/v1/dashboard"]:
        res = client.get(url)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert "dataset_metadata" in data
        assert "platform_breakdown" in data
        assert "schema_convergence" in data
        assert "market_salary_benchmark_vnd" in data
        assert data["dataset_metadata"]["total_golden_unique"] > 0
        assert data["dataset_metadata"]["deduplication_rate_pct"] > 0


def test_collection_sources():
    """Kiểm tra danh sách 8 nguồn cào."""
    res = client.get("/api/v1/collection/crawling/sources")
    assert res.status_code == 200
    sources = res.json()
    assert len(sources) == 8
    source_ids = {s["id"] for s in sources}
    assert "topcv" in source_ids
    assert "itviec" in source_ids
    assert "topdev" in source_ids


def test_collection_eda_inventory():
    """Kiểm tra bảng kiểm kê trường dữ liệu thô."""
    res = client.get("/api/v1/collection/eda/topcv/inventory")
    assert res.status_code == 200
    items = res.json()
    assert len(items) > 0
    assert "field_name" in items[0]
    assert "null_rate_pct" in items[0]


def test_preprocessing_metrics():
    """Kiểm tra chỉ số tiền xử lý."""
    res = client.get("/api/v1/preprocessing/metrics")
    assert res.status_code == 200
    data = res.json()
    assert "parsing_rules" in data
    assert "null_reduction_comparison" in data


def test_processing_metrics():
    """Kiểm tra chỉ số tích hợp và khử trùng lặp."""
    res = client.get("/api/v1/processing/metrics")
    assert res.status_code == 200
    data = res.json()
    assert "deduplication_metrics" in data
    assert "schema_mapping_inventory" in data


def test_ml_spatial_3d():
    """Kiểm tra không gian vector 3D cho Machine Learning."""
    res = client.get("/api/v1/mining/spatial-3d/umap")
    assert res.status_code == 200
    data = res.json()
    assert data["algorithm"] == "umap_3d"
    assert len(data["points"]) > 0
    pt = data["points"][0]
    assert "x" in pt and "y" in pt and "z" in pt
    assert "job_family" in pt


def test_cloud_r2_status():
    """Kiểm tra endpoint trạng thái Cloudflare R2."""
    res = client.get("/api/v1/cloud/r2/status")
    assert res.status_code == 200
    data = res.json()
    assert "configured" in data
    assert data["bucket"] == "vn-it-jobs"


def test_airflow_status():
    """Kiểm tra endpoint trạng thái Airflow daemon."""
    res = client.get("/api/v1/airflow/status")
    assert res.status_code == 200
    data = res.json()
    assert "scheduler" in data
    assert "webserver" in data
    assert "database" in data
    assert "active_dags_count" in data


def test_airflow_dags():
    """Kiểm tra danh sách DAGs xoay vòng."""
    res = client.get("/api/v1/airflow/dags")
    assert res.status_code == 200
    dags = res.json()
    assert isinstance(dags, list)
    if len(dags) > 0:
        dag = dags[0]
        assert "dag_id" in dag
        assert "source" in dag
        assert "schedule_day" in dag


def test_decoupled_routes():
    """Kiểm tra các route decoupled /crawling và /eda độc lập."""
    crawl_res = client.get("/api/v1/crawling/sources")
    assert crawl_res.status_code == 200
    assert len(crawl_res.json()) >= 7

    eda_res = client.get("/api/v1/eda/topcv/inventory")
    assert eda_res.status_code == 200
    assert len(eda_res.json()) > 0


def test_cloud_r2_diff():
    """Kiểm tra Diff Engine của Cloudflare R2."""
    res = client.get("/api/v1/cloud/r2/diff/topcv")
    assert res.status_code == 200
    data = res.json()
    assert data["source"] == "topcv"
    assert "local_count" in data
    assert "cloud_count" in data
    assert "synced_pct" in data


def test_crawling_enum_summary():
    """Kiểm tra endpoint thống kê định lượng 5 trạng thái Enum vòng đời URL."""
    res = client.get("/api/v1/crawling/enum-summary")
    assert res.status_code == 200
    data = res.json()
    assert "total" in data
    assert data["total"] > 0
    for st in ["pending", "done", "recheck_due", "closed", "failed"]:
        assert st in data
        assert "count" in data[st]
        assert "pct" in data[st]
    assert "by_source" in data
    assert len(data["by_source"]) >= 8


def test_crawling_weekly_schedule():
    """Kiểm tra endpoint bảng lịch cào 7 ngày trong tuần."""
    res = client.get("/api/v1/crawling/weekly-schedule")
    assert res.status_code == 200
    data = res.json()
    assert data["total_projected_weekly"] > 0
    assert "days" in data
    assert len(data["days"]) >= 7
    first_day = data["days"][0]
    assert "day_of_week" in first_day
    assert "focal_source" in first_day
    assert "projected_quota" in first_day
    assert "actual_crawled" in first_day


def test_crawling_cloud_sync_status():
    """Kiểm tra endpoint kiểm toán đồng bộ Cloudflare R2 trong phân hệ Crawling."""
    res = client.get("/api/v1/crawling/cloud-sync-status")
    assert res.status_code == 200
    data = res.json()
    assert "connected" in data
    assert "overall_sync_pct" in data
    assert "sources" in data
    assert len(data["sources"]) >= 8


def test_system_alerts():
    """Kiểm tra endpoint cảnh báo trực tiếp trên Web Monitor."""
    res = client.get("/api/v1/alerts")
    assert res.status_code == 200
    data = res.json()
    assert "total_alerts" in data
    assert "critical_count" in data
    assert "warning_count" in data
    assert "alerts" in data

    if data["alerts"]:
        first_alert = data["alerts"][0]
        ack_res = client.post(f"/api/v1/alerts/{first_alert['id']}/acknowledge")
        assert ack_res.status_code == 200
        assert ack_res.json()["acknowledged"] is True

