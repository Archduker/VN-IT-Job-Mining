# -*- coding: utf-8 -*-
"""Unit tests for Multi-Tier Deduplication in UrlLedger (URL Hash + Job ID)."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
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
    assert canonicalize_lakehouse_key("itviec/staging/itviec_staging.parquet") == "staging/itviec/itviec_staging.parquet"

    # 3. Chặn tệp rác / cache
    with pytest.raises(ValueError):
        canonicalize_lakehouse_key("topcv/.browser_profile/manifest.json")

    with pytest.raises(ValueError):
        canonicalize_lakehouse_key("topcv/router_state.json")

    with pytest.raises(ValueError):
        canonicalize_lakehouse_key("data/checkpoints/checkpoint.json")
