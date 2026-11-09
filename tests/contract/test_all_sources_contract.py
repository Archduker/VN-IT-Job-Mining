# -*- coding: utf-8 -*-
"""Kiểm tra tuân thủ các tiêu chuẩn C1–C14 trên cả 8 nguồn sàn tuyển dụng.

Dự án: VN-IT-Job-Mining
8 sàn: topdev, topcv, vietnamworks, careerviet, vieclam24h, itviec, glints, jobsgo.
"""

from __future__ import annotations

import importlib
from datetime import datetime, timezone

import pytest

from collection.common.r2_storage import canonicalize_lakehouse_key
from collection.common.url_ledger import (
    DiscoveryError,
    UrlLedger,
    clean_canonical_url,
    generate_url_hash,
)
from collection.sources.careerviet.crawler import CareerVietCrawler
from collection.sources.glints.crawler import GlintsCrawler
from collection.sources.itviec.crawler import ItviecCrawler
from collection.sources.jobsgo.crawler import JobsGoCrawler
from collection.sources.topcv.crawler import TopCVCrawler
from collection.sources.topdev.crawler import TopDevCrawler
from collection.sources.vieclam24h.crawler import ViecLam24hCrawler
from collection.sources.vietnamworks.crawler import VietnamWorksCrawler
from tests.contract import standards

ALL_CRAWLERS = {
    "topcv": TopCVCrawler,
    "topdev": TopDevCrawler,
    "vietnamworks": VietnamWorksCrawler,
    "careerviet": CareerVietCrawler,
    "vieclam24h": ViecLam24hCrawler,
    "itviec": ItviecCrawler,
    "glints": GlintsCrawler,
    "jobsgo": JobsGoCrawler,
}

MODULE_NAMES = {
    "topcv": "collection.sources.topcv.crawler",
    "topdev": "collection.sources.topdev.crawler",
    "vietnamworks": "collection.sources.vietnamworks.crawler",
    "careerviet": "collection.sources.careerviet.crawler",
    "vieclam24h": "collection.sources.vieclam24h.crawler",
    "itviec": "collection.sources.itviec.crawler",
    "glints": "collection.sources.glints.crawler",
    "jobsgo": "collection.sources.jobsgo.crawler",
}


@pytest.mark.parametrize("source,crawler_cls", ALL_CRAWLERS.items())
def test_c1_all_crawlers_two_phase(source, crawler_cls):
    """C1: Cả 8 nguồn đều cung cấp đầy đủ hàm discover_urls() và crawl_details()."""
    standards.check_two_phase(crawler_cls)


@pytest.mark.parametrize("source,mod_name", MODULE_NAMES.items())
def test_c10_all_crawlers_random_pause(source, mod_name):
    """C10: Cả 8 nguồn đều cài đặt thời gian nghỉ ngẫu nhiên (polite_sleep / uniform / DelayConfig)."""
    mod = importlib.import_module(mod_name)
    standards.check_random_pause(mod)


@pytest.mark.parametrize("source", ALL_CRAWLERS.keys())
def test_c8_all_sources_r2_layout(source):
    """C8: Layout key R2 của cả 8 nguồn đúng chuẩn raw/<source>/<YYYY-MM-DD>/<job_id>_v<N>.json."""
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sample_key = f"raw/{source}/{day}/123456_v1.json"
    standards.check_r2_keys([sample_key], source)
    assert canonicalize_lakehouse_key(sample_key) == sample_key


def test_c2_clean_canonical_url():
    """C2: URL làm sạch bỏ toàn bộ tracking query params (utm_*, ref, source)."""
    dirty_url = "https://www.topcv.vn/viec-lam/python-lead/9999.html?utm_source=facebook&utm_medium=cpc&ref=search&source=recommend"
    clean = clean_canonical_url(dirty_url)
    assert clean == "https://www.topcv.vn/viec-lam/python-lead/9999.html"
    assert "utm_source" not in clean
    assert "ref" not in clean


def test_c3_ledger_lifecycle(tmp_path):
    """C3: Vòng đời ledger PENDING -> DONE -> (21 ngày) RECHECK_DUE."""
    ledger = UrlLedger(source="test_src", storage_dir=str(tmp_path / "ledger"))
    rec1 = ledger.register_url("https://example.com/job/1", job_id="1", preliminary_title="Test Job")
    assert rec1.status == "PENDING"
    assert ledger.records[rec1.url_hash]["status"] == "PENDING"

    # Detail hoàn thành
    ledger.mark_done(rec1.url_hash, "hash_v1", new_version=1)
    assert ledger.records[rec1.url_hash]["status"] == "DONE"

    # Chưa đến 21 ngày: không nằm trong pending_or_due
    due = ledger.get_pending_or_due_records(recheck_days=21)
    assert len(due) == 0

    # Lỗi: mark_failed
    rec2 = ledger.register_url("https://example.com/job/2", job_id="2", preliminary_title="Failed Job")
    ledger.mark_failed(rec2.url_hash, error_message="HTTP 500")
    assert ledger.records[rec2.url_hash]["status"] == "FAILED"

    # Retry failed chỉ lấy tin FAILED
    failed = [r for r in ledger.records.values() if r.get("status") == "FAILED"]
    assert len(failed) == 1
    assert failed[0]["job_id"] == "2"


def test_c6_repost_handling(tmp_path):
    """C6: Tin repost trùng content_hash với tin khác thì chỉ đánh dấu repost, không tạo file mới."""
    ledger = UrlLedger(source="test_src", storage_dir=str(tmp_path / "ledger"))
    rec1 = ledger.register_url("https://example.com/job/1", job_id="1", preliminary_title="Original Job")
    ledger.mark_done(rec1.url_hash, "shared_hash_abc", new_version=1)

    rec2 = ledger.register_url("https://example.com/job/2", job_id="2", preliminary_title="Reposted Job")
    ledger.mark_done(rec2.url_hash, "shared_hash_abc", repost_of_url_hash=rec1.url_hash)
    assert ledger.records[rec2.url_hash]["status"] == "DONE"
    assert ledger.records[rec2.url_hash]["repost_of_url_hash"] == rec1.url_hash


def test_c14_discovery_error_type():
    """C14: Lớp ngoại lệ DiscoveryError tồn tại và kế thừa RuntimeError."""
    err = DiscoveryError("Không có trang danh sách nào hoạt động")
    assert isinstance(err, RuntimeError)
    assert "Không có trang danh sách nào" in str(err)
