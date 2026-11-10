"""Monitoring: API các bước pre-processing chỉ đọc báo cáo bước (docs/spec/monitoring/preprocessing_page_spec.md)."""

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
    assert [s["step"] for s in data] == ["01_clean", "01b_deduplication", "02_integration", "03_transformation", "04_normalization",
                                         "05_encoding"]
    assert data[0]["available"] and data[0]["output_rows"] == 8
    assert not data[1]["available"] and "--step deduplication" in data[1]["command"]


def test_stale_when_previous_step_newer(reports):
    reports("01_clean", "_all", "2026-11-03T12:00:00+00:00")
    reports("02_integration", "_all", "2026-11-03T11:00:00+00:00", inp=8, out=8)
    assert client.get("/api/v1/preprocessing/steps").json()[2]["stale"] is True


def test_unknown_step_or_source_is_404(reports):
    assert client.get("/api/v1/preprocessing/steps/99_x").status_code == 404
    assert client.get("/api/v1/preprocessing/steps/01_clean/abc").status_code == 404
    assert client.get("/api/v1/preprocessing/steps/..%2F..%2Fetc/topcv").status_code == 404


def test_source_report_or_unavailable(reports):
    reports("01_clean", "topcv", "2026-11-03T10:00:00+00:00")
    assert client.get("/api/v1/preprocessing/steps/01_clean/topcv").json()["report"]["output"]["rows"] == 8
    missing = client.get("/api/v1/preprocessing/steps/01_clean/topdev").json()
    assert missing["available"] is False and "--source topdev" in missing["command"]


class _FakeS3:
    """R2 giả: dict key -> (bytes, metadata)."""

    def __init__(self, objects):
        self.objects = objects

    def head_object(self, Bucket, Key):
        from botocore.exceptions import ClientError

        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "404"}}, "HeadObject")
        body, meta = self.objects[Key]
        return {"Metadata": meta, "ETag": f'"{hash(body)}"', "ContentLength": len(body)}

    def get_object(self, Bucket, Key):
        import io

        return {"Body": io.BytesIO(self.objects[Key][0])}


@pytest.fixture
def silver(tmp_path, monkeypatch):
    import io

    import pandas as pd

    from app.core.r2_client import r2_client
    from app.services import preprocessing_step_service as svc
    from preprocessing.common import r2_export

    data, reps = tmp_path / "data" / "preprocessing", tmp_path / "reports" / "preprocessing"
    monkeypatch.setattr(r2_export, "DATA", data)
    monkeypatch.setattr(r2_export, "REPORTS", reps)
    for c in (svc._storage_cache,):
        c.update(at=0.0, data=None)
    svc._r2_frames.clear()
    svc._heads.clear()
    svc._local_frames.clear()

    df = pd.DataFrame({"source_platform": ["topcv", "topcv", "itviec"], "job_title": ["A", "B", "C"],
                       "salary_max_vnd": [1.0, float("nan"), 3.0]})
    (data / "02_integration").mkdir(parents=True)
    df.to_parquet(data / "02_integration" / "all.parquet", index=False)
    (reps / "02_integration").mkdir(parents=True)
    (reps / "02_integration" / "_all.json").write_text(json.dumps({"generated_at": "2026-11-03T10:00:00+00:00"}))

    buf = io.BytesIO()
    df[df.source_platform == "topcv"].to_parquet(buf, index=False)
    fake = _FakeS3({"staging/topcv/preprocessing/02_integration.parquet":
                    (buf.getvalue(), {"generated-at": "2026-11-03T10:00:00+00:00", "rows": "2"})})
    monkeypatch.setattr(r2_client, "get_client", lambda: fake)
    return fake


def test_storage_compares_each_key(silver):
    items = {i["key"]: i["status"] for i in client.get("/api/v1/preprocessing/storage").json()["items"]}
    assert items == {"staging/topcv/preprocessing/02_integration.parquet": "khop",
                     "staging/itviec/preprocessing/02_integration.parquet": "chua_day"}


def test_rows_from_r2_or_local_fallback(silver):
    r = client.get("/api/v1/preprocessing/steps/02_integration/rows?source=topcv").json()
    assert (r["origin"], r["total"], r["rows"][1]["salary_max_vnd"]) == ("r2", 2, None)
    # itviec chưa có trên R2 -> đọc file trên máy, có ghi chú
    r = client.get("/api/v1/preprocessing/steps/02_integration/rows").json()
    assert (r["origin"], r["total"]) == ("local", 3) and r["note"]
    assert client.get("/api/v1/preprocessing/steps/02_integration/rows?source=abc").status_code == 404
    assert client.get("/api/v1/preprocessing/steps/02_integration/rows?limit=999").status_code == 422
    assert client.get("/api/v1/preprocessing/steps/01_clean/rows").status_code == 400
