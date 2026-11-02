# -*- coding: utf-8 -*-
"""Kiểm thử API /monitor: chỉ trả số thật, thiếu dữ liệu thì trả null kèm lý do."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import pandas as pd
import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent / "monitoring" / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.core.r2_client import r2_client  # noqa: E402
from app.main import app  # noqa: E402
from app.services.airflow_service import airflow_service  # noqa: E402

client = TestClient(app)
VN = timezone(timedelta(hours=7))


def envelope(job_id, payload):
    return {"metadata": {"job_id": job_id, "source": "careerviet", "scraped_at": "2026-11-01T06:45:48+00:00"},
            "raw_payload": payload}


CAREERVIET = {
    "title": "Senior AI Engineer (2026TD450878)",
    "job-company-name": "Công ty TNHH ABC",
    "map": "Hà Nội",
    "detail-box": ["Ngày cập nhật 28/10/2026", "Ngày cập nhật 28/10/2026", "Lương Lương: 28 - 70 Triệu VND",
                   "Kinh nghiệm Trên 2 Năm", "Cấp bậc Nhân viên", "Hết hạn nộp 21/11/2026"],
    "job-tags": ["Kỹ sư viễn thông"],
}


@pytest.fixture
def empty_env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(settings, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(airflow_service, "get_run_history", lambda days=14: None)
    monkeypatch.setattr(r2_client, "get_client", lambda: None)
    monkeypatch.setattr(r2_client, "get_full_cloud_sync_status", lambda: {"connected": False})
    from app.services import ledger_service as ls
    monkeypatch.setattr(ls.ledger_service, "data_dir", tmp_path / "data")
    return tmp_path


def write_raw(root, source, day, name, content):
    folder = root / "data" / source / "raw" / day
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")


def test_collection_without_data_has_no_invented_numbers(empty_env):
    data = client.get("/api/v1/monitor/collection?days=7").json()
    assert data["has_data"] is False
    assert len(data["days"]) == 7
    assert data["kpi"]["total"] == 0
    assert data["queue"] == {"total": 0, "pending": 0, "done": 0, "recheck_due": 0, "failed": 0}
    assert data["kpi"]["runs_ok"] is None
    assert data["kpi"]["unique_total"] is None and data["kpi"]["unique_reason"]
    assert data["airflow_available"] is False and data["unavailable_reason"]
    assert all(c["status"] is None for d in data["days"] for c in d["by_source"].values())


def test_collection_counts_raw_and_merges_airflow_runs(empty_env, monkeypatch):
    now = datetime.now(VN)
    today = now.date().isoformat()
    write_raw(empty_env, "careerviet", today, "a_v1.json", envelope("a", CAREERVIET))
    write_raw(empty_env, "careerviet", today, "raw_batch.json", [envelope("b", CAREERVIET), envelope("c", CAREERVIET)])
    runs = [
        {"dag_id": "crawler_detail_careerviet", "state": "success", "start_date": now, "end_date": now},
        {"dag_id": "crawler_detail_careerviet", "state": "failed", "start_date": now, "end_date": now},
    ]
    monkeypatch.setattr(airflow_service, "get_run_history", lambda days=14: runs)
    data = client.get("/api/v1/monitor/collection?days=7").json()
    cell = data["days"][-1]["by_source"]["careerviet"]
    assert cell["count"] == 3
    assert cell["status"] == "partial" and cell["failed_runs"] == 1
    assert data["kpi"]["today"] == 3 and data["kpi"]["runs_total"] == 2
    assert data["count_origin"]["careerviet"] == "raw"


def test_collection_rejects_out_of_range_days(empty_env):
    assert client.get("/api/v1/monitor/collection?days=30").status_code == 422


def test_unknown_source_is_404(empty_env):
    assert client.get("/api/v1/monitor/sources/linkedin/report").status_code == 404


def test_report_without_files_keeps_targets_and_reason(empty_env):
    data = client.get("/api/v1/monitor/sources/careerviet/report").json()
    assert len(data["targets"]) == 8 and len(data["issues"]) == 8
    assert data["overview"]["completeness_pct"] is None
    assert data["unavailable_reason"]


def test_report_reads_integration_audit(empty_env):
    folder = empty_env / "reports" / "integration"
    folder.mkdir(parents=True)
    audit = {"job_title": {"completeness_pct": 100.0}, "raw_seniority_text": {"completeness_pct": 0.0}}
    (folder / "itviec_integration_report.json").write_text(
        json.dumps({"total_integrated_records": 691, "field_completeness_audit": audit}), encoding="utf-8")
    data = client.get("/api/v1/monitor/sources/itviec/report").json()
    assert data["overview"]["integrated_records"] == 691
    assert data["overview"]["weakest"].startswith("F6")
    assert data["issues"][0]["code"] == "F6"


def test_univariate_empty_then_real(empty_env):
    url = "/api/v1/monitor/sources/topcv/univariate/F4"
    assert client.get(url).json()["kind"] == "empty"
    folder = empty_env / "data" / "staging" / "topcv"
    folder.mkdir(parents=True)
    pd.DataFrame({"salary_min_vnd": [10e6, 20e6, None], "salary_max_vnd": [20e6, 30e6, None]}).to_parquet(
        folder / "topcv_flat_clean.parquet")
    data = client.get(url).json()
    assert data["kind"] == "num" and data["base"] == 2
    assert sum(i["count"] for i in data["items"]) == 2


@pytest.mark.parametrize("code,kind,column,values", [
    ("F1", "cat", "job_family", ["JF01_BACKEND", "JF01_BACKEND", None]),
    ("F5", "num", "raw_experience_text", ["Trên 2 năm", "Không yêu cầu", None]),
])
def test_univariate_other_kinds(empty_env, code, kind, column, values):
    folder = empty_env / "data" / "staging" / "topcv"
    folder.mkdir(parents=True)
    pd.DataFrame({column: values}).to_parquet(folder / "topcv_flat_clean.parquet")
    assert client.get(f"/api/v1/monitor/sources/topcv/univariate/{code}").json()["kind"] == kind


def test_sample_annotations_mark_features_and_duplicates(empty_env):
    write_raw(empty_env, "careerviet", "2026-11-01", "35C8B926_v1.json", envelope("35C8B926", CAREERVIET))
    assert client.get("/api/v1/monitor/sources/careerviet/samples").json()["items"][0]["id"] == "35C8B926"
    data = client.get("/api/v1/monitor/sources/careerviet/samples/35C8B926").json()
    assert data["raw"]["raw_payload"] == CAREERVIET
    assert ["raw_payload", "detail-box", 1] in [h["path"] for h in data["highlights"] if h["kind"] == "dup"]
    notes = {n["code"]: n for n in data["notes"]}
    assert notes["F4"]["status"] == "ok" and "28.000.000" in notes["F4"]["normalized"]
    assert notes["F5"]["normalized"].startswith("2 năm")
    assert notes["F7"]["status"] == "warn" and "SEO" in notes["F7"]["how"]


def test_missing_sample_is_404(empty_env):
    assert client.get("/api/v1/monitor/sources/topcv/samples/khong-co").status_code == 404
    assert client.get("/api/v1/monitor/sources/topcv/samples").json()["unavailable_reason"]
