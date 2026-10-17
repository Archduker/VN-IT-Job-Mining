"""Unit tests cho scripts.view_urls."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from scripts.view_urls import load_local_ledger, load_minio_ledger, render_dashboard, export_data


def test_load_local_ledger_existing(tmp_path, monkeypatch):
    source_dir = tmp_path / "data" / "topcv" / "url_ledger"
    source_dir.mkdir(parents=True)
    catalog = source_dir / "catalog_master.json"
    data = {
        "hash1": {
            "url_hash": "hash1",
            "job_id": "123",
            "status": "PENDING",
            "canonical_url": "https://topcv.vn/job/123",
            "preliminary_title": "Python Dev",
            "preliminary_company": "FPT",
        }
    }
    with open(catalog, "w", encoding="utf-8") as f:
        json.dump(data, f)

    # Change working dir to tmp_path
    monkeypatch.chdir(tmp_path)
    res = load_local_ledger("topcv")
    assert res["exists"] is True
    assert "hash1" in res["records"]
    assert res["records"]["hash1"]["preliminary_title"] == "Python Dev"


def test_load_minio_ledger_mock(monkeypatch):
    mock_s3 = MagicMock()
    mock_body = MagicMock()
    mock_body.read.return_value = json.dumps({
        "hash_s3": {
            "url_hash": "hash_s3",
            "job_id": "999",
            "status": "DONE",
            "canonical_url": "https://topcv.vn/job/999",
        }
    }).encode("utf-8")
    mock_s3.get_object.return_value = {"Body": mock_body}

    monkeypatch.setattr("boto3.client", lambda *args, **kwargs: mock_s3)
    res = load_minio_ledger("topcv", endpoint="http://mock:9000")
    assert res["exists"] is True
    assert "hash_s3" in res["records"]


def test_render_dashboard_does_not_crash(capsys):
    records = {
        "h1": {
            "url_hash": "h1",
            "job_id": "1001",
            "status": "PENDING",
            "canonical_url": "https://topcv.vn/job/1001",
            "preliminary_title": "Frontend Engineer",
            "preliminary_company": "VNG",
            "discovered_at": "2026-10-16T10:00:00Z",
        },
        "h2": {
            "url_hash": "h2",
            "job_id": "1002",
            "status": "FAILED",
            "canonical_url": "https://topcv.vn/job/1002",
            "error_log": "Timeout 30s",
        }
    }
    render_dashboard(records, source="topcv", source_path="data/topcv/url_ledger", show_errors=True)
    captured = capsys.readouterr()
    assert "BÁO CÁO KIỂM KÊ URL LEDGER" in captured.out
    assert "Frontend Engineer" in captured.out
    assert "Timeout 30s" in captured.out


def test_export_data(tmp_path):
    records = [{"job_id": "1", "status": "DONE", "canonical_url": "https://example.com"}]
    json_out = tmp_path / "out.json"
    csv_out = tmp_path / "out.csv"

    export_data(records, json_path=str(json_out), csv_path=str(csv_out))
    assert json_out.exists()
    assert csv_out.exists()
