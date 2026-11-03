"""Monitoring: API các bước pre-processing chỉ đọc báo cáo bước (docs/monitoring/preprocessing_page_spec.md)."""

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[2] / "monitoring" / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


def report(step, source, generated_at, inp=10, out=8):
    return {"step": step, "source": source, "mode": "applied", "generated_at": generated_at,
            "input": {"path": None, "rows": inp}, "output": {"path": None, "rows": out},
            "dropped": [{"rule": "C1", "reason": "x", "rows": inp - out}], "rules": [], "fields": [], "api": {}}


@pytest.fixture
def reports(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "ROOT_DIR", tmp_path)
    root = tmp_path / "reports" / "preprocessing"

    def put(step, source, generated_at, **kw):
        path = root / step / f"{source}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report(step, source, generated_at, **kw)), encoding="utf-8")
    return put


def test_steps_in_order_and_missing(reports):
    reports("01_clean", "_all", "2026-11-03T10:00:00+00:00")
    data = client.get("/api/v1/preprocessing/steps").json()
    assert [s["step"] for s in data] == ["01_clean", "02_integration", "03_transformation", "04_normalization",
                                         "05_encoding"]
    assert data[0]["available"] and data[0]["output_rows"] == 8
    assert not data[1]["available"] and "--step integration" in data[1]["command"]


def test_stale_when_previous_step_newer(reports):
    reports("01_clean", "_all", "2026-11-03T12:00:00+00:00")
    reports("02_integration", "_all", "2026-11-03T11:00:00+00:00", inp=8, out=8)
    assert client.get("/api/v1/preprocessing/steps").json()[1]["stale"] is True


def test_unknown_step_or_source_is_404(reports):
    assert client.get("/api/v1/preprocessing/steps/99_x").status_code == 404
    assert client.get("/api/v1/preprocessing/steps/01_clean/abc").status_code == 404
    assert client.get("/api/v1/preprocessing/steps/..%2F..%2Fetc/topcv").status_code == 404


def test_source_report_or_unavailable(reports):
    reports("01_clean", "topcv", "2026-11-03T10:00:00+00:00")
    assert client.get("/api/v1/preprocessing/steps/01_clean/topcv").json()["report"]["output"]["rows"] == 8
    missing = client.get("/api/v1/preprocessing/steps/01_clean/topdev").json()
    assert missing["available"] is False and "--source topdev" in missing["command"]
