# -*- coding: utf-8 -*-
"""Pre-processing, Processing, Master Dashboard and EDA read pipeline reports and never invent numbers."""

import json
import sys
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "monitoring" / "backend"))

from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)

CURATED = {
    "generated_at": "2026-10-25T18:03:17+00:00",
    "total_staging_records": 100,
    "total_golden_records": 80,
    "deduplication_metrics": {"total_input_records": 100, "total_golden_records": 80, "duplicates_removed": 20,
                              "deduplication_rate_pct": 20.0, "cross_platform_cluster_count": 7},
    "salary_metrics": {"salary_coverage_pct": 50.0, "salary_q1_vnd": 10e6, "salary_median_vnd": 15e6,
                       "salary_q3_vnd": 25e6, "salary_p1_vnd": 3e6, "salary_p99_vnd": 90e6},
    "platform_breakdown": {"topcv": 60, "itviec": 20},
    "job_family_breakdown": {"JF01_BACKEND": 50, "JF02_FRONTEND": 30},
    "seniority_breakdown": {"Senior": 40},
    "top_cities": {"Hà Nội": 70},
}
TOPCV_CARD = {
    "audit_timestamp": "2026-10-25T18:03:05+00:00", "total_raw_envelopes": 120, "stub_jds_removed_policy_1b": 20,
    "total_clean_records": 100, "salary_metrics": {"salary_coverage_pct": 62.0},
    "imputation_metrics": {"records_imputed_by_genai": 30, "imputation_rate_pct": 30.0},
    "language_distribution": {"vi": 90, "en": 10},
}


@pytest.fixture
def empty_root(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path / "data")
    return tmp_path


@pytest.fixture
def reports_root(empty_root):
    (empty_root / "reports" / "topcv").mkdir(parents=True)
    (empty_root / "reports" / "integration").mkdir(parents=True)
    (empty_root / "reports" / "curated_golden_dataset_health_card.json").write_text(json.dumps(CURATED))
    (empty_root / "reports" / "topcv" / "topcv_quality_health_card.json").write_text(json.dumps(TOPCV_CARD))
    audit = {"raw_salary_text": {"filled_count": 9, "missing_count": 1, "completeness_pct": 90.0},
             "raw_experience_text": {"filled_count": 5, "missing_count": 5, "completeness_pct": 50.0}}
    report = {"total_integrated_records": 110, "field_completeness_audit": audit}
    (empty_root / "reports" / "integration" / "master_integration_report.json").write_text(json.dumps(report))
    (empty_root / "reports" / "integration" / "topcv_integration_report.json").write_text(json.dumps(report))
    return empty_root


def test_pages_report_missing_files_instead_of_numbers(empty_root):
    dashboard = client.get("/api/v1/dashboard").json()
    assert dashboard["available"] is False and dashboard["totals"] is None
    assert "run_staging_integration_pipeline" in dashboard["unavailable_reason"]
    pre = client.get("/api/v1/preprocessing/metrics").json()
    assert pre["available"] is False and pre["totals"]["clean_records"] is None
    proc = client.get("/api/v1/processing/metrics").json()
    assert proc["dedup"] is None and proc["field_completeness"] == []
    charts = client.get("/api/v1/eda/topcv/charts").json()
    assert charts["available"] is False and charts["salary_histogram"] == []
    summary = client.get("/api/v1/eda/topcv/summary").json()
    assert summary["total_records"] == 0 and summary["salary_parse_rate_pct"] is None


def test_dashboard_reads_curated_card(reports_root):
    data = client.get("/api/v1/dashboard").json()
    assert data["totals"]["golden_records"] == 80
    assert data["totals"]["integrated_records"] == 110
    assert data["platform_breakdown"][0] == {"source": "topcv", "golden_records": 60, "share_pct": 75.0}
    assert data["salary_vnd_million"]["median"] == 15.0
    assert [row["records"] for row in data["lineage"]] == [110, 100, 80]


def test_preprocessing_and_processing_read_reports(reports_root):
    pre = client.get("/api/v1/preprocessing/metrics").json()
    topcv = next(r for r in pre["sources"] if r["source"] == "topcv")
    assert (topcv["stub_removed"], topcv["imputed_records"]) == (20, 30)
    assert pre["totals"]["clean_records"] == 100
    assert next(r for r in pre["sources"] if r["source"] == "glints")["available"] is False
    proc = client.get("/api/v1/processing/metrics").json()
    assert proc["dedup"]["duplicates_removed"] == 20
    assert proc["field_completeness"][0]["field"] == "raw_salary_text"
    compare = client.get("/api/v1/eda/compare").json()
    row = next(r for r in compare["sources"] if r["source"] == "topcv")
    assert (row["salary_text_pct"], row["salary_numeric_pct"], row["completeness_pct"]) == (90.0, 62.0, 70.0)


def test_eda_charts_from_staging_parquet(empty_root):
    folder = empty_root / "data" / "staging" / "topcv"
    folder.mkdir(parents=True)
    pd.DataFrame({
        "salary_min_vnd": [10e6, 20e6, None], "salary_max_vnd": [20e6, 30e6, None],
        "skills_list": [["Python", "SQL"], ["Python"], []], "primary_city": ["Hà Nội", "Hà Nội", "Đà Nẵng"],
        "is_salary_negotiable_declared": [0, 0, 1],
    }).to_parquet(folder / "topcv_flat_clean.parquet")
    charts = client.get("/api/v1/eda/topcv/charts").json()
    assert charts["records"] == 3 and charts["salary_records"] == 2
    assert {b["bin"]: b["count"] for b in charts["salary_histogram"]}["10–20M"] == 1
    assert charts["skills_pareto"][0] == {"label": "Python", "count": 2, "cumulative_pct": 66.7}
    assert charts["locations"][0] == {"label": "Hà Nội", "count": 2}
    assert client.get("/api/v1/eda/topcv/summary").json()["negotiable_salary_pct"] == 33.33
