# -*- coding: utf-8 -*-
"""Unit tests cho scripts/import_careerviet_urls_to_ledger.py.

Toàn bộ chạy trên dữ liệu giả trong tmp_path (không phụ thuộc data/ cục bộ),
dùng pathlib và so sánh đường dẫn dạng as_posix để chạy được cả Windows lẫn Linux.
"""

import json
from pathlib import Path

import pytest

from scripts.import_careerviet_urls_to_ledger import (
    CATEGORY_MAP_FILENAME,
    build_category_map,
    run_import,
)

BASE = "https://careerviet.vn/vi/tim-viec-lam"


def _write_urls_file(directory: Path, filename: str, records: list[dict]) -> Path:
    payload = {
        "generated_at": "2026-10-16T00:00:00+00:00",
        "source": "careerviet",
        "total": len(records),
        "records": records,
        "all_urls_sorted": sorted(r["url"] for r in records),
    }
    fp = directory / filename
    fp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return fp


def _rec(job_id: str, category: str) -> dict:
    return {
        "url": f"{BASE}/job-{job_id.lower()}.{job_id}.html",
        "job_id": job_id,
        "source_category": category,
    }


@pytest.fixture()
def fake_urls_dir(tmp_path, monkeypatch):
    """Tạo thư mục URL giả + trỏ CWD vào tmp_path để UrlLedger không thấy data/ thật."""
    monkeypatch.chdir(tmp_path)
    urls_dir = tmp_path / "urls_src"
    urls_dir.mkdir()
    _write_urls_file(urls_dir, "urls_c1_2026-10-16.json", [_rec("AAA111", "c1"), _rec("AAA222", "c1")])
    _write_urls_file(urls_dir, "urls_c61_2026-10-16.json", [_rec("BBB333", "c61")])
    _write_urls_file(
        urls_dir, "urls_developer_2026-10-16.json", [_rec("CCC444", "keyword:developer")]
    )
    # File c37 KHONG duoc nap — co mot job_id dac trưng SSDF999.
    _write_urls_file(urls_dir, "urls_c37_2026-10-16.json", [_rec("SSDF999", "c37_digital_mkt")])
    return urls_dir


def _storage(tmp_path: Path) -> Path:
    return tmp_path / "ledger_out"


def test_import_registers_all_and_writes_outputs(fake_urls_dir, tmp_path):
    stats = run_import(fake_urls_dir, _storage(tmp_path))

    assert stats["records_read"] == 4
    assert stats["registered_new"] == 4
    assert stats["already_present"] == 0
    assert stats["unique_job_ids"] == 4
    assert stats["total_ledger_records"] == 4
    assert stats["category_counts"] == {"c1": 2, "c61": 1, "keyword:developer": 1}
    assert stats["ledger_status_counts"] == {"PENDING": 4}
    assert stats["category_collisions"] == []
    assert stats["minio_synced"] is None

    # File c37 khong duoc doc
    assert all("urls_c37" not in f for f in stats["files_read"])

    # Catalog + manifest + category map ton tai dung cho
    catalog_path = Path(stats["catalog_path"])
    manifest_path = Path(stats["manifest_path"])
    category_path = Path(stats["category_map_path"])
    assert catalog_path.is_file()
    assert manifest_path.is_file()
    assert category_path.is_file()
    assert category_path.name == CATEGORY_MAP_FILENAME

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    assert len(catalog) == 4
    rec = next(r for r in catalog.values() if r["job_id"] == "AAA111")
    assert rec["status"] == "PENDING"
    assert rec["source"] == "careerviet"
    assert rec["canonical_url"] == f"{BASE}/job-aaa111.AAA111.html"

    cat_map = json.loads(category_path.read_text(encoding="utf-8"))
    assert cat_map["CCC444"] == "keyword:developer"
    assert "SSDF999" not in cat_map


def test_rerun_with_force_does_not_duplicate_records(fake_urls_dir, tmp_path):
    first = run_import(fake_urls_dir, _storage(tmp_path))
    second = run_import(fake_urls_dir, _storage(tmp_path), force=True)

    assert second["registered_new"] == 0
    assert second["already_present"] == first["records_read"]
    assert second["total_ledger_records"] == first["total_ledger_records"] == 4

    catalog = json.loads(Path(second["catalog_path"]).read_text(encoding="utf-8"))
    assert len(catalog) == 4


def test_existing_category_map_stops_without_force(fake_urls_dir, tmp_path):
    storage = _storage(tmp_path)
    run_import(fake_urls_dir, storage)

    category_path = storage / CATEGORY_MAP_FILENAME
    before = category_path.read_text(encoding="utf-8")
    catalog_path = storage / "catalog_master.json"
    catalog_before = catalog_path.read_text(encoding="utf-8")

    with pytest.raises(FileExistsError):
        run_import(fake_urls_dir, storage)

    # Khong co thay doi nao sau lan dung
    assert category_path.read_text(encoding="utf-8") == before
    assert catalog_path.read_text(encoding="utf-8") == catalog_before


def test_canonical_dedup_across_tracking_params(fake_urls_dir, tmp_path):
    dup_records = [
        {"url": f"{BASE}/job-ddd555.DDD555.html?utm_source=facebook", "job_id": "DDD555", "source_category": "c1"},
        {"url": f"{BASE}/job-ddd555.DDD555.html/", "job_id": "DDD555", "source_category": "c1"},
        {"url": f"{BASE}/job-ddd555.DDD555.html#apply", "job_id": "DDD555", "source_category": "c1"},
    ]
    _write_urls_file(fake_urls_dir, "urls_c1_2026-10-17.json", dup_records)

    stats = run_import(fake_urls_dir, _storage(tmp_path))
    # 3Bien the URL giong nhau -> chi 1 record moi, 2 lan da ton tai
    assert stats["registered_new"] == 5  # 4 fan goc + 1 DDD555
    assert stats["already_present"] == 2
    assert stats["total_ledger_records"] == 5
    assert stats["unique_job_ids"] == 5


def test_missing_url_files_raise(fake_urls_dir, tmp_path):
    empty_dir = tmp_path / "nothing_here"
    empty_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        run_import(empty_dir, _storage(tmp_path))


def test_build_category_map_detects_collisions():
    records = [
        {"job_id": "X1", "source_category": "c1"},
        {"job_id": "X1", "source_category": "c61"},
        {"job_id": "X2", "source_category": "c1"},
        {"job_id": "X2", "source_category": "c1"},
    ]
    mapping, collisions = build_category_map(records)
    assert mapping == {"X1": "c1", "X2": "c1"}
    assert collisions == ["X1: c1 vs c61"]
