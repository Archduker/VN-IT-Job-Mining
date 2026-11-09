# -*- coding: utf-8 -*-
"""Unit tests for Multi-Tier Deduplication in UrlLedger (URL Hash + Job ID)."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import tempfile
import pytest

from collection.common.url_ledger import (
    UrlLedger,
    clean_canonical_url,
    generate_url_hash,
)


@pytest.fixture
def temp_ledger(tmp_path: Path) -> UrlLedger:
    """Khởi tạo UrlLedger trong thư mục tạm độc lập."""
    storage_dir = tmp_path / "test_ledger"
    return UrlLedger(source="test_source", storage_dir=str(storage_dir))


def test_exact_url_deduplication(temp_ledger: UrlLedger):
    """Kiểm tra phát hiện trùng lặp Tầng 1: Trùng URL Hash."""
    raw_url = "https://www.topcv.vn/viec-lam/python-dev/12345.html?utm_source=fb"
    job_id = "12345"

    # Đăng ký lần đầu
    rec1 = temp_ledger.register_url(raw_url=raw_url, job_id=job_id, preliminary_title="Python Developer")
    assert rec1.status == "PENDING"
    assert rec1.job_id == "12345"
    assert temp_ledger.is_known(raw_url, job_id=job_id)

    # Kiểm tra trùng lặp với URL có thêm query param rác
    alt_url = "https://www.topcv.vn/viec-lam/python-dev/12345.html?ref=topcv&utm_campaign=ads"
    is_dup, match_type, existing = temp_ledger.check_duplicate(alt_url, job_id=job_id)
    assert is_dup is True
    assert match_type == "URL_HASH"
    assert existing["job_id"] == "12345"

    # Đăng ký lại không làm đổi trạng thái
    rec2 = temp_ledger.register_url(raw_url=alt_url, job_id=job_id)
    assert rec2.url_hash == rec1.url_hash
    assert rec2.status == "PENDING"


def test_job_id_deduplication_different_url(temp_ledger: UrlLedger):
    """Kiểm tra phát hiện trùng lặp Tầng 2: Cùng Job ID nhưng URL bị đổi slug."""
    url_v1 = "https://www.topcv.vn/viec-lam/python-dev/99999.html"
    job_id = "99999"

    # Lần đầu đăng ký và giả lập đã cào xong (status = DONE)
    rec1 = temp_ledger.register_url(raw_url=url_v1, job_id=job_id, preliminary_title="Python Dev")
    url_hash_v1 = rec1.url_hash
    temp_ledger.records[url_hash_v1]["status"] = "DONE"
    temp_ledger.records[url_hash_v1]["last_scraped_at"] = datetime.now(timezone.utc).isoformat()
    temp_ledger.save_catalog()

    # Recruiter đổi tiêu đề và slug URL nhưng job_id giữ nguyên 99999
    url_v2 = "https://www.topcv.vn/viec-lam/senior-python-lead-hcm/99999.html"
    is_dup, match_type, existing = temp_ledger.check_duplicate(url_v2, job_id=job_id)

    assert is_dup is True
    assert match_type == "JOB_ID"
    assert existing["job_id"] == "99999"

    # Đăng ký URL mới với cùng Job ID: Phải bảo toàn status DONE (không reset về PENDING)
    rec2 = temp_ledger.register_url(raw_url=url_v2, job_id=job_id, preliminary_title="Senior Python Lead")
    assert rec2.job_id == "99999"
    assert rec2.status == "DONE"  # Đảm bảo KHÔNG bị cào lại oan
    assert "senior-python-lead-hcm" in rec2.canonical_url

    # Tra cứu bằng Job ID
    found_by_id = temp_ledger.get_record(job_id=job_id)
    assert found_by_id is not None
    assert found_by_id.job_id == "99999"


def test_truly_new_job_registration(temp_ledger: UrlLedger):
    """Kiểm tra đăng ký tin mới hoàn toàn."""
    url = "https://www.topcv.vn/viec-lam/data-engineer/88888.html"
    job_id = "88888"

    is_dup, match_type, _ = temp_ledger.check_duplicate(url, job_id=job_id)
    assert is_dup is False
    assert match_type == "NONE"

    rec = temp_ledger.register_url(raw_url=url, job_id=job_id, preliminary_title="Data Engineer")
    assert rec.status == "PENDING"
    assert rec.job_id == "88888"


def test_recrawl_due_after_21_days(temp_ledger: UrlLedger):
    """Kiểm tra tự động chuyển trạng thái RECHECK_DUE khi tin cũ quá 21 ngày."""
    url = "https://www.topcv.vn/viec-lam/golang-dev/77777.html"
    job_id = "77777"

    rec = temp_ledger.register_url(raw_url=url, job_id=job_id)
    u_hash = rec.url_hash

    # Giả lập đã cào xong cách đây 25 ngày
    old_time = (datetime.now(timezone.utc) - timedelta(days=25)).isoformat()
    temp_ledger.records[u_hash]["status"] = "DONE"
    temp_ledger.records[u_hash]["last_scraped_at"] = old_time
    temp_ledger.save_catalog()

    # Quét lại ở Pha 1 hôm nay
    rec_updated = temp_ledger.register_url(raw_url=url, job_id=job_id)
    assert rec_updated.status == "RECHECK_DUE"


def test_canonicalize_lakehouse_key():
    """Kiểm tra hàm chuẩn hóa khóa S3/R2 chống tạo thư mục rác trên Lakehouse."""
    from collection.common.r2_storage import canonicalize_lakehouse_key

    # 1. Đã đúng chuẩn
    assert canonicalize_lakehouse_key("raw/topcv/2026-10-20/123_v1.json") == "raw/topcv/2026-10-20/123_v1.json"
    assert canonicalize_lakehouse_key("url_ledger/jobsgo/catalog_master.json") == "url_ledger/jobsgo/catalog_master.json"

    # 2. Bị đảo ngược (nguồn trước, layer sau) -> tự động đưa layer lên đầu
    assert canonicalize_lakehouse_key("topcv/raw/2026-10-20/123_v1.json") == "raw/topcv/2026-10-20/123_v1.json"
    assert canonicalize_lakehouse_key("jobsgo/url_ledger/catalog_master.json") == "url_ledger/jobsgo/catalog_master.json"
    assert canonicalize_lakehouse_key("itviec/staging/itviec_staging.parquet") == "silver/itviec/itviec_staging.parquet"

    # 2b. Tên tầng cũ và prefix mới đều được nhận, luôn ra prefix mới
    assert canonicalize_lakehouse_key("raw/topcv/2026-10-20/123_v1.json") == "raw/topcv/2026-10-20/123_v1.json"
    assert canonicalize_lakehouse_key("staging/topcv/preprocessing/02_integration.parquet") == "silver/topcv/preprocessing/02_integration.parquet"
    assert canonicalize_lakehouse_key("silver/topcv/a.parquet") == "silver/topcv/a.parquet"
    assert canonicalize_lakehouse_key("curated/preprocessing/features.parquet") == "gold/preprocessing/features.parquet"
    assert canonicalize_lakehouse_key("gold/preprocessing/features.parquet") == "gold/preprocessing/features.parquet"
    with pytest.raises(ValueError):
        canonicalize_lakehouse_key("raw/unknown/a.json")
    with pytest.raises(ValueError):
        canonicalize_lakehouse_key("integration/x.json")

    # 3. Chặn tệp rác / cache
    with pytest.raises(ValueError):
        canonicalize_lakehouse_key("topcv/.browser_profile/manifest.json")

    with pytest.raises(ValueError):
        canonicalize_lakehouse_key("topcv/router_state.json")

    with pytest.raises(ValueError):
        canonicalize_lakehouse_key("data/checkpoints/checkpoint.json")

    # 4. Layout cũ theo ngày trước, nguồn sau được đưa về đúng chuẩn
    assert canonicalize_lakehouse_key("raw/crawling/2026-10-15/topcv/1_v1.json") == "raw/topcv/2026-10-15/1_v1.json"
    assert canonicalize_lakehouse_key("crawling/raw/2026-10-15/topcv/1_v1.json") == "raw/topcv/2026-10-15/1_v1.json"
    assert (canonicalize_lakehouse_key("raw/url_ledger/2026-11-02/careerviet/catalog_master.json")
            == "url_ledger/careerviet/snapshots/2026-11-02/catalog_master.json")

    # 5. Không coi thư mục lạ là tên nguồn
    with pytest.raises(ValueError):
        canonicalize_lakehouse_key("crawling/raw/foo.json")
    with pytest.raises(ValueError):
        canonicalize_lakehouse_key("raw/unknown/2026-10-15/a.json")


def test_sync_paths_handle_legacy_layout(tmp_path):
    import importlib
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    sync = importlib.import_module("sync_cloud_lakehouse")

    assert sync.s3_key_to_local_path("raw/crawling/2026-10-15/topcv/1_v1.json", tmp_path) == tmp_path / "topcv/raw/2026-10-15/1_v1.json"
    assert sync.s3_key_to_local_path("raw/topcv/2026-10-15/1_v1.json", tmp_path) == tmp_path / "topcv/raw/2026-10-15/1_v1.json"
    assert sync.s3_key_to_local_path("raw/topcv/2026-10-15/1_v1.json", tmp_path) == tmp_path / "topcv/raw/2026-10-15/1_v1.json"
    assert sync.local_path_to_s3_key(tmp_path / "crawling/raw/2026-10-15/itviec/a_v1.json", tmp_path) == "raw/itviec/2026-10-15/a_v1.json"
    assert sync.local_path_to_s3_key(tmp_path / "topcv/raw/2026-10-15/a_v1.json", tmp_path) == "raw/topcv/2026-10-15/a_v1.json"
    assert sync.local_path_to_s3_key(tmp_path / "crawling/raw/a.json", tmp_path) is None


def test_migrate_local_layout(tmp_path):
    import importlib
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    migrate = importlib.import_module("migrate_lakehouse_layout")

    legacy = tmp_path / "crawling" / "raw" / "2026-10-15"
    for name, body in (("topcv/a_v1.json", "A"), ("topcv/b_v1.json", "B"), ("itviec/c_v1.json", "C")):
        (legacy / name).parent.mkdir(parents=True, exist_ok=True)
        (legacy / name).write_text(body)
    (tmp_path / "topcv/raw/2026-10-15").mkdir(parents=True)
    (tmp_path / "topcv/raw/2026-10-15/b_v1.json").write_text("B")       # trùng hệt
    (tmp_path / "itviec/raw/2026-10-15").mkdir(parents=True)
    (tmp_path / "itviec/raw/2026-10-15/c_v1.json").write_text("khác")   # khác nội dung

    dry = migrate.migrate_local(tmp_path, apply=False)
    assert dry["stats"] == {"moved": 1, "duplicate_removed": 1, "conflict_skipped": 1}
    assert (legacy / "topcv/a_v1.json").exists()

    migrate.migrate_local(tmp_path, apply=True)
    assert (tmp_path / "topcv/raw/2026-10-15/a_v1.json").read_text() == "A"
    assert not (legacy / "topcv").exists()
    assert (legacy / "itviec/c_v1.json").read_text() == "C"
    assert (tmp_path / "itviec/raw/2026-10-15/c_v1.json").read_text() == "khác"


def _ledger_with_two(tmp_path):
    led = UrlLedger("topcv", storage_dir=str(tmp_path))
    led.register_url("https://www.topcv.vn/viec-lam/a/1.html", job_id="1", preliminary_title="a")
    led.register_url("https://www.topcv.vn/viec-lam/b/2.html", job_id="2", preliminary_title="b")
    led.save_catalog()
    return led, list(led.records)


def _disk(tmp_path):
    return json.loads((tmp_path / "catalog_master.json").read_text(encoding="utf-8"))


def test_failed_and_closed_survive_save(tmp_path):
    """Trước 03/11/2026 save_catalog để bản PENDING trên đĩa đè FAILED/CLOSED, nên 8 ledger đều có 0 FAILED."""
    led, (h1, h2) = _ledger_with_two(tmp_path)
    led.mark_failed(h1, "HTTP 500")
    led.mark_closed(h2)
    led.save_catalog()
    disk = _disk(tmp_path)
    assert disk[h1]["status"] == "FAILED" and disk[h1]["retry_count"] == 1
    assert disk[h2]["status"] == "CLOSED"


def test_latest_status_change_wins_between_workers(tmp_path):
    led, (h1, _) = _ledger_with_two(tmp_path)
    worker_a = UrlLedger("topcv", storage_dir=str(tmp_path))
    worker_b = UrlLedger("topcv", storage_dir=str(tmp_path))
    worker_a.mark_done(h1, content_hash="h")
    worker_b.mark_failed(h1, "timeout")      # đổi sau A
    worker_a.save_catalog()
    worker_b.save_catalog()
    assert _disk(tmp_path)[h1]["status"] == "FAILED"

    worker_c = UrlLedger("topcv", storage_dir=str(tmp_path))
    worker_d = UrlLedger("topcv", storage_dir=str(tmp_path))
    worker_c.mark_failed(h1, "timeout")
    worker_d.mark_done(h1, content_hash="h2")  # đổi sau C
    worker_d.save_catalog()
    worker_c.save_catalog()                    # C lưu sau nhưng thay đổi của C cũ hơn
    assert _disk(tmp_path)[h1]["status"] == "DONE"


def test_records_without_updated_at_keep_old_merge_rule(tmp_path):
    led, (h1, _) = _ledger_with_two(tmp_path)
    disk = _disk(tmp_path)
    disk[h1].update({"status": "DONE", "last_scraped_at": "2026-10-01T00:00:00+00:00"})
    (tmp_path / "catalog_master.json").write_text(json.dumps(disk), encoding="utf-8")
    led.records[h1].update({"status": "PENDING", "last_scraped_at": None})
    led.records[h1].pop("updated_at", None)
    led.save_catalog()
    assert _disk(tmp_path)[h1]["status"] == "DONE"


class _FakeS3:
    """S3 trong bộ nhớ, đủ cho migrate_prefixes."""

    def __init__(self, objects):
        self.objects = dict(objects)
        self.deleted = []

    def get_paginator(self, _):
        outer = self

        class P:
            def paginate(self, Bucket, Prefix):
                yield {"Contents": [{"Key": k, "Size": len(v), "ETag": f'"{hash(v)}"'}
                                    for k, v in sorted(outer.objects.items()) if k.startswith(Prefix)]}
        return P()

    def head_object(self, Bucket, Key):
        if Key not in self.objects:
            raise KeyError(Key)
        v = self.objects[Key]
        return {"ContentLength": len(v), "ETag": f'"{hash(v)}"'}

    def copy_object(self, Bucket, Key, CopySource):
        self.objects[Key] = self.objects[CopySource["Key"]]

    def delete_object(self, Bucket, Key):
        self.objects.pop(Key)
        self.deleted.append(Key)


def test_migrate_prefixes_dry_run_then_apply():
    import importlib
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    migrate = importlib.import_module("migrate_lakehouse_layout")

    objs = {"raw/topcv/2026-10-15/a_v1.json": "A", "url_ledger/topcv/catalog_master.json": "L",
            "staging/topcv/preprocessing/x.parquet": "S", "curated/preprocessing/f.parquet": "G",
            "staging/itviec/preprocessing/b.parquet": "B", "silver/itviec/preprocessing/b.parquet": "B",      # đích trùng hệt
            "staging/topdev/preprocessing/c.parquet": "C", "silver/topdev/preprocessing/c.parquet": "khác"}   # đích khác nội dung
    s3 = _FakeS3(objs)
    dry = migrate.migrate_prefixes(s3, "b", apply=False)
    assert s3.objects == objs and not s3.deleted
    assert dry["stats"] == {"moved": 2, "duplicate_removed": 1, "conflict_skipped": 1, "unmapped": 2}

    migrate.migrate_prefixes(s3, "b", apply=True)
    assert s3.objects["raw/topcv/2026-10-15/a_v1.json"] == "A"            # raw/ giữ nguyên
    assert s3.objects["url_ledger/topcv/catalog_master.json"] == "L"      # url_ledger/ giữ nguyên
    assert s3.objects["silver/topcv/preprocessing/x.parquet"] == "S"
    assert s3.objects["gold/preprocessing/f.parquet"] == "G"
    assert "staging/itviec/preprocessing/b.parquet" not in s3.objects
    assert s3.objects["staging/topdev/preprocessing/c.parquet"] == "C"    # xung đột: giữ nguyên cả hai
    assert s3.objects["silver/topdev/preprocessing/c.parquet"] == "khác"
