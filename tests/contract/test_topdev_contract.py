# -*- coding: utf-8 -*-
"""TopDev đạt tiêu chuẩn collection C1–C14 (xem collection/CLAUDE.md). Chạy offline với tests/fixtures/topdev/.

Mẫu là phản hồi API chi tiết thật lấy ngày 03/11/2026: tin thường, tin lương thỏa thuận, tin ẩn lương.
TopDev không có cờ tin VIP nên mẫu thứ ba là tin ẩn lương.
"""

import json
from datetime import datetime, timezone

import pytest

from collection.common.url_ledger import LedgerSyncError, UrlLedger, calculate_json_canonical_hash
from collection.sources.topdev import crawler as module
from collection.sources.topdev.crawler import TopDevCrawler, build_raw_payload_from_api
from tests.contract import standards

FIXTURES = ("standard.json", "negotiable_salary.json", "hidden_salary.json")


@pytest.fixture
def items(fixtures_dir):
    folder = fixtures_dir / "topdev"
    standards.check_fixtures(folder, FIXTURES)
    return [json.loads((folder / name).read_text(encoding="utf-8")) for name in FIXTURES]


@pytest.fixture
def crawler(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "polite_sleep", lambda *a, **k: None)
    monkeypatch.setattr(UrlLedger, "pull_from_r2", lambda self, *a, **k: True)
    monkeypatch.setattr(UrlLedger, "sync_to_r2", lambda self, *a, **k: True)
    c = TopDevCrawler(output_dir=str(tmp_path), sync_r2=True)
    c._r2_store = standards.FakeR2Store()
    return c


def run_details(crawler, items, monkeypatch, sync_ok=True, broken_id=None):
    by_id = {str(i["id"]): i for i in items}
    for item in items:
        crawler.ledger.register_url(item["detail_url"], job_id=str(item["id"]), preliminary_title=item["title"])
    if broken_id:
        crawler.ledger.register_url(f"https://topdev.vn/viec-lam/broken-{broken_id}", job_id=broken_id, preliminary_title="x")

    def fetch(job_id):
        if job_id == broken_id:
            raise module.TopDevAPIError("API trả 500")
        return by_id[job_id]

    monkeypatch.setattr(crawler.api_crawler, "_fetch_detail_with_retries", fetch)
    monkeypatch.setattr(UrlLedger, "sync_to_r2", lambda self, *a, **k: sync_ok)
    return crawler.crawl_details()


def test_c1_two_phase():
    standards.check_two_phase(TopDevCrawler)


def test_c4_c11_envelope_and_features(crawler, items):
    envelopes = [crawler.parse_raw_envelope(i) for i in items]
    for env in envelopes:
        standards.check_envelope(env, "topdev")
    # F7: tag kỹ năng (skills_arr) có thể rỗng ở tin ngoài IT; theo dõi bằng audit chứ không chặn
    standards.check_feature_coverage(envelopes, "topdev", allow_missing={"F7": "skills_arr rỗng ở tin ngoài IT"})


def test_c5_hash_ignores_relative_dates(items):
    item = items[0]
    later = {**item, "published": {**(item.get("published") or {}), "since": "1 tháng trước"}}
    assert calculate_json_canonical_hash(build_raw_payload_from_api(item)) == \
        calculate_json_canonical_hash(build_raw_payload_from_api(later))


def test_c7_c8_safe_skip_and_r2_layout(crawler, items, monkeypatch):
    stats = run_details(crawler, items, monkeypatch, broken_id="999")
    assert stats["success"] == 3 and stats["failed"] == 1
    statuses = {r["job_id"]: r["status"] for r in crawler.ledger.records.values()}
    assert statuses["999"] == "FAILED" and all(statuses[str(i["id"])] == "DONE" for i in items)
    standards.check_r2_keys(crawler._r2_store.keys, "topdev")
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    assert {k.rsplit("/", 1)[-1] for k in crawler._r2_store.keys} == {f"{i['id']}_v1.json" for i in items}
    assert all(f"/{day}/" in k for k in crawler._r2_store.keys)


def test_c9_ledger_sync_failure_is_reported(crawler, items, monkeypatch):
    with pytest.raises(LedgerSyncError):
        run_details(crawler, items, monkeypatch, sync_ok=False)


def test_c10_random_pause():
    standards.check_random_pause(module)


def test_discovery_registers_all_jobs_without_it_filter(crawler, monkeypatch):
    """SCRAPE-15 (đã chốt 09/11): Discovery không lọc IT, bước Clean lọc; tin ngoài IT vẫn được đăng ký."""
    listing_payload = {
        "data": [
            {
                "id": 1001,
                "title": "Senior Golang Backend Engineer",
                "slug": "senior-golang-backend-engineer",
                "detail_url": "https://topdev.vn/viec-lam/senior-golang-1001",
                "skills_arr": [{"title": "Golang"}, {"title": "Docker"}],
            },
            {
                "id": 1002,
                "title": "Kế toán tổng hợp nội bộ",
                "slug": "ke-toan-tong-hop-1002",
                "detail_url": "https://topdev.vn/viec-lam/ke-toan-1002",
                "skills_arr": [],
                "skills_str": "kế toán, thuế",
            },
            {
                "id": 1003,
                "title": "Tài xế giao hàng xe máy",
                "slug": "tai-xe-giao-hang-1003",
                "detail_url": "https://topdev.vn/viec-lam/tai-xe-1003",
                "skills_arr": [],
            },
        ],
        "meta": {"current_page": 1, "last_page": 1, "total": 3},
    }
    monkeypatch.setattr(crawler.api_crawler, "_fetch_listing_with_retries", lambda page, **k: listing_payload)
    discovered = crawler.discover_urls(max_pages=1)
    assert len(discovered) == 3
    assert any("senior-golang-1001" in u for u in discovered)
    assert {r["job_id"] for r in crawler.ledger.records.values()} == {"1001", "1002", "1003"}


def test_c14_discovery_fails_when_all_pages_fail(crawler, monkeypatch):
    """C14: Pha discovery raise DiscoveryError khi không lấy được trang nào."""
    from collection.common.url_ledger import DiscoveryError

    def fail(*args, **kwargs):
        raise module.TopDevAPIError("TopDev API 500 error")

    monkeypatch.setattr(crawler.api_crawler, "_fetch_listing_with_retries", fail)
    with pytest.raises(DiscoveryError):
        crawler.discover_urls(max_pages=1)


def test_c14_discovery_partial_failure_is_ok(crawler, monkeypatch):
    """C14: Pha discovery thành công nếu lấy được ít nhất 1 trang."""
    listing_payload = {
        "data": [
            {
                "id": 2001,
                "title": "Java Spring Boot Developer",
                "slug": "java-spring-boot-2001",
                "detail_url": "https://topdev.vn/viec-lam/java-2001",
                "skills_arr": [{"title": "Java"}],
            }
        ],
        "meta": {"current_page": 1, "last_page": 2, "total": 2},
    }

    def fetch(page, **kwargs):
        if page == 1:
            return listing_payload
        raise module.TopDevAPIError("Page 2 timeout")

    monkeypatch.setattr(crawler.api_crawler, "_fetch_listing_with_retries", fetch)
    urls = crawler.discover_urls(max_pages=2)
    assert len(urls) == 1
    assert "java-2001" in urls[0]
