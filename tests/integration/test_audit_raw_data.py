# -*- coding: utf-8 -*-
"""scripts/audit_raw_data.py finds layout, ledger, duplicate and scrape-quality problems from local files only."""

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import audit_raw_data  # noqa: E402
from app.core.config import settings  # noqa: E402

TODAY = date(2026, 11, 2)


def envelope(job_id, payload, day="2026-11-01"):
    return {"metadata": {"job_id": job_id, "source": "careerviet", "scraped_at": f"{day}T06:00:00+00:00",
                         "source_url": f"https://careerviet.vn/{job_id}.html"}, "raw_payload": payload}


GOOD = {"title": "Kỹ sư Python", "job-company-name": "Công ty A", "map": "Hà Nội",
        "detail-box": ["Lương Lương: 20 - 30 Triệu VND", "Kinh nghiệm 2 Năm"],
        "detail-row": {"Mô tả Công việc": "Phát triển API " * 40}, "job-tags": ["Python"]}


def write(path: Path, content) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content if isinstance(content, str) else json.dumps(content, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def result(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIR", settings.DATA_DIR)
    data = tmp_path / "data"
    raw = data / "careerviet" / "raw"
    write(raw / "2026-10-29" / "A_v1.json", envelope("A", GOOD, "2026-10-29"))
    write(raw / "2026-11-01" / "A_v2.json", envelope("A", GOOD))
    write(raw / "2026-11-01" / "B_v1.json", envelope("B", {"title": "Just a moment... captcha"}))
    write(raw / "2026-11-01" / "C_v1.json", envelope("C", {}))
    write(raw / "2026-11-01" / "broken.json", "{not json")
    write(raw / "2026-11-01" / "error_log.json", {"error": "timeout"})
    write(raw / "_index" / "x.json", envelope("D", GOOD))
    # JD thật có nhắc "captcha" thì không phải trang chặn bot
    write(raw / "2026-11-01" / "G_v1.json", envelope("G", {**GOOD, "detail-row": {"Mô tả": "Viết captcha resolver. " * 60}}))
    # File batch cũ gom nhiều tin, A đã có file riêng
    write(raw / "2026-11-01" / "batch_001.json", [envelope("A", GOOD), envelope("H", GOOD)])
    write(data / "crawling" / "raw" / "2026-10-19" / "itviec" / "job_v1.json", envelope("E", GOOD))
    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    write(data / "careerviet" / "url_ledger" / "catalog_master.json", {
        "h1": {"job_id": "A", "status": "DONE", "last_scraped_at": old},
        "h2": {"job_id": "Z", "status": "DONE", "last_scraped_at": old},
        "h3": {"job_id": "F", "status": "FAILED", "error_log": "403 Forbidden"},
        "h4": {"job_id": "R", "status": "DONE", "last_scraped_at": old, "repost_of_url_hash": "h1"},
        "h5": {"job_id": "G", "status": "DONE", "last_scraped_at": "2026-11-01T07:00:00+00:00"},
        # H chỉ có trong file batch cũ, được đăng ký PENDING để cào lại: không phải ledger chậm hơn raw
        "h6": {"job_id": "H", "status": "PENDING", "registered_from_batch": "batch_001.json"},
    })
    return audit_raw_data.run(data, tmp_path / "out", today=TODAY)


def by_source(result, src):
    return next(s for s in result["sources"] if s["source"] == src)


def test_layout_problems(result):
    assert result["layout"]["unexpected_dirs"] == {"crawling": 1}
    assert result["layout"]["misplaced_by_source"] == {"itviec": 1}
    assert result["layout"]["raw_outside_date_folder"]["careerviet"]["count"] == 1


def test_raw_file_and_scrape_quality(result):
    s = by_source(result, "careerviet")
    assert s["raw"]["parse_errors"] == 1
    assert s["raw"]["files_without_envelope"] == 1
    assert s["raw"]["empty_payload"] == 1
    assert s["suspect"]["blocked_page"] == 1  # B; G chỉ nhắc captcha trong JD
    assert s["duplicates"]["job_id_in_many_files"] == 1  # A_v1 và A_v2; file batch không tính
    assert s["raw"]["legacy_batch_files"] == 1
    assert s["raw"]["batch_job_ids_also_single"] == 1
    assert s["timeline"]["gap_days"] == ["2026-10-30", "2026-10-31"]


def test_ledger_consistency(result):
    led = by_source(result, "careerviet")["ledger"]
    assert led["status"] == {"DONE": 4, "FAILED": 1, "PENDING": 1}
    assert led["done_due_for_recrawl"] == 3
    assert led["reposts"] == 1
    assert led["done_without_raw"] == 1  # Z; repost R cố ý không có snapshot
    assert led["raw_not_in_ledger"] == 3  # B, C, D
    assert led["ledger_behind_raw"] == 1  # A cào lại 2026-11-01 nhưng ledger vẫn ghi 30 ngày trước; H trong batch không tính
    assert led["top_failed_reasons"][0][0] == "403 Forbidden"


def test_features_and_report_files(result, tmp_path):
    feats = by_source(result, "careerviet")["features"]
    assert feats["F1"] == 87.5  # 8 envelope, chỉ C rỗng
    md = (tmp_path / "out" / "data_audit_2026-11-02.md").read_text(encoding="utf-8")
    assert "data/crawling/" in md and "### Mức cao" in md
    assert any(i["source"] == "topcv" and "không có file raw" in i["text"] for i in result["issues"])


def test_r2_layout_check():
    r2 = audit_raw_data.check_r2_layout(["raw/topcv/2026-11-01/a.json", "raw/crawling/2026-10-19/itviec/b.json",
                                         "silver/x.parquet", "url_ledger/topcv/catalog_master.json"])
    assert r2["keys_outside_source_folders"] == {"raw/crawling": 1}
    assert r2["non_canonical_layers"] == {"silver": 1}
