# -*- coding: utf-8 -*-
"""TopCV đạt tiêu chuẩn collection C1–C14 (xem collection/CLAUDE.md). Chạy offline với tests/fixtures/topcv/.

Mẫu là trang chi tiết thật lấy ngày 03/11/2026, đã bỏ script/style/svg và các khối crawler không đọc; mỗi mẫu cho
ra đúng content_hash như trang gốc. vip_brand_page là trang /brand/... của nhà tuyển dụng VIP, bố cục khác trang thường.
"""

import json
import shutil
from datetime import datetime, timezone

import pytest

from collection.common.url_ledger import LedgerSyncError, UrlLedger, clean_canonical_url, generate_url_hash
from collection.sources.topcv import crawler as module
from collection.sources.topcv.crawler import TopCVCrawler, build_raw_envelope
from tests.contract import standards

CASES = {
    "standard.html": ("1518603", "https://www.topcv.vn/viec-lam/unreal-engine-artist-tai-ho-chi-minh-luong-10tr-30tr-cv-tieng-anh-va-portfolio-file-video/1518603.html"),
    "negotiable_salary.html": ("1636894", "https://www.topcv.vn/viec-lam/senior-automation-aiops-consultant-presales/1636894.html"),
    "vip_brand_page.html": ("2321660", "https://www.topcv.vn/brand/thoitrangsixdo/tuyen-dung/chuyen-vien-phan-tich-du-lieu-ban-le-j2321660.html"),
}


@pytest.fixture
def folder(fixtures_dir):
    path = fixtures_dir / "topcv"
    standards.check_fixtures(path, CASES)
    return path


@pytest.fixture
def envelopes(folder):
    return [build_raw_envelope((folder / name).read_text(encoding="utf-8"), job_id=jid, url=url)
            for name, (jid, url) in CASES.items()]


def make_crawler(tmp_path, folder, monkeypatch, sync_ok=True, broken_id=None):
    html_dir = tmp_path / "html"
    html_dir.mkdir()
    records = {}
    for name, (jid, url) in CASES.items():
        shutil.copy(folder / name, html_dir / f"{jid}.html")
    entries = list(CASES.values()) + ([(broken_id, f"https://www.topcv.vn/viec-lam/x/{broken_id}.html")] if broken_id else [])
    for jid, url in entries:
        canon = clean_canonical_url(url)
        records[generate_url_hash(canon)] = {"url_hash": generate_url_hash(canon), "canonical_url": canon,
                                             "source": "topcv", "job_id": jid, "status": "PENDING"}
    (tmp_path / "ledger").mkdir()
    (tmp_path / "ledger" / "catalog_master.json").write_text(json.dumps(records), encoding="utf-8")
    monkeypatch.setattr(module, "polite_sleep", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(UrlLedger, "pull_from_r2", lambda self, *a, **k: True)
    monkeypatch.setattr(UrlLedger, "sync_to_r2", lambda self, *a, **k: sync_ok)
    crawler = TopCVCrawler(ledger_dir=str(tmp_path / "ledger"), raw_root=str(tmp_path / "raw"),
                           local_html_dir=str(html_dir), sync_r2=True, min_delay=0, max_delay=0)
    crawler._r2_store = standards.FakeR2Store()
    return crawler


def test_c1_two_phase():
    standards.check_two_phase(TopCVCrawler)


def test_c4_c11_envelope_and_features(envelopes):
    for env in envelopes:
        standards.check_envelope(env, "topcv")
    standards.check_feature_coverage(envelopes, "topcv")


def test_c5_hash_is_stable(folder):
    name, (jid, url) = next(iter(CASES.items()))
    html = (folder / name).read_text(encoding="utf-8")
    assert build_raw_envelope(html, job_id=jid, url=url).metadata["content_hash"] == \
        build_raw_envelope(html, job_id=jid, url=url).metadata["content_hash"]


def test_c7_c8_safe_skip_and_r2_layout(tmp_path, folder, monkeypatch):
    crawler = make_crawler(tmp_path, folder, monkeypatch, broken_id="9999999")
    stats = crawler.crawl_details(online=False)
    assert stats["success"] == 3 and stats["failed"] == 1
    ledger = {r["job_id"]: r for r in crawler._get_ledger().records.values()}
    assert ledger["9999999"]["status"] == "FAILED"
    assert all(ledger[jid]["status"] == "DONE" and ledger[jid]["latest_version"] == 1 for jid, _ in CASES.values())
    standards.check_r2_keys(crawler._r2_store.keys, "topcv")
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    assert sorted(p.name for p in (tmp_path / "raw" / day).glob("*.json")) == sorted(f"{jid}_v1.json" for jid, _ in CASES.values())


def test_c9_ledger_sync_failure_is_reported(tmp_path, folder, monkeypatch):
    crawler = make_crawler(tmp_path, folder, monkeypatch, sync_ok=False)
    with pytest.raises(LedgerSyncError):
        crawler.crawl_details(online=False)


def test_c10_random_pause():
    standards.check_random_pause(module)


def test_scrape10_default_engine_is_curl_cffi(tmp_path, monkeypatch):
    import run

    assert TopCVCrawler(ledger_dir=str(tmp_path / "l"), raw_root=str(tmp_path / "r")).engine == "curl_cffi"
    seen = {}

    class Fake:
        def __init__(self, **kwargs):
            seen.update(kwargs)

        def discover_urls(self, max_pages=None, online=True):
            return []

    monkeypatch.setattr(module, "TopCVCrawler", Fake)
    run.run_crawler(source="topcv", phase="discover", output_dir=str(tmp_path))
    assert seen.get("engine", "curl_cffi") == "curl_cffi"


LISTING = "<html><body>" + "x" * 3000 + '<a href="/viec-lam/lap-trinh-vien-python/1234567.html">Lập trình viên Python</a></body></html>'


def _discover_with_pages(tmp_path, monkeypatch, pages):
    """pages: danh sách HTML hoặc Exception cho từng trang danh sách."""
    monkeypatch.setattr(module, "polite_sleep", lambda *a, **k: None, raising=False)
    crawler = TopCVCrawler(ledger_dir=str(tmp_path / "l"), raw_root=str(tmp_path / "r"), min_delay=0, max_delay=0)
    queue = list(pages)

    def fake_get(url):
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(crawler, "_get_page_content", fake_get)
    return crawler.discover_urls(online=True, max_pages=len(pages))


def test_c14_discovery_fails_when_no_listing_page_works(tmp_path, monkeypatch):
    from collection.common.url_ledger import DiscoveryError

    with pytest.raises(DiscoveryError):
        _discover_with_pages(tmp_path, monkeypatch, [RuntimeError("No CloakBrowser license key")])


def test_c14_partial_listing_failure_is_ok(tmp_path, monkeypatch):
    urls = _discover_with_pages(tmp_path, monkeypatch, [LISTING + "page=2", RuntimeError("timeout")])
    assert urls == ["https://www.topcv.vn/viec-lam/lap-trinh-vien-python/1234567.html"]


def test_c14_listing_without_new_jobs_is_ok(tmp_path, monkeypatch):
    assert _discover_with_pages(tmp_path, monkeypatch, ["<html>" + "x" * 3000 + "</html>"]) == []


def test_c14_run_py_exit_code_on_discovery_error(tmp_path, monkeypatch):
    import sys

    import run
    from collection.common.url_ledger import DiscoveryError

    def boom(**kwargs):
        raise DiscoveryError("không lấy được trang nào")

    monkeypatch.setattr(run, "run_crawler", boom)
    monkeypatch.setattr(sys, "argv", ["run.py", "--source", "topcv", "--phase", "discover"])
    assert run.main() == 1


def test_scrape16_empty_jd_fallback_recovery():
    """SCRAPE-16: Khôi phục mô tả công việc (JD) khi DOM không có class chuẩn hoặc viết hoa."""
    html_custom_dom = """
    <html><body>
        <h1 class="title">Embedded Systems Engineer</h1>
        <div class="salary">20 - 35 triệu</div>
        <h2>MÔ TẢ CÔNG VIỆC:</h2>
        <div>
            <p>- Thiết kế và phát triển firmware cho vi điều khiển STM32/ESP32.</p>
            <p>- Giao tiếp các chuẩn UART, SPI, I2C, CAN bus.</p>
        </div>
        <h2>YÊU CẦU ỨNG VIÊN:</h2>
        <ul>
            <li>Tốt nghiệp ĐH chuyên ngành Điện tử, CNTT hoặc liên quan.</li>
            <li>Có từ 2 năm kinh nghiệm lập trình C/C++ Embedded.</li>
        </ul>
        <h2>QUYỀN LỢI ĐƯỢC HƯỞNG:</h2>
        <ul>
            <li>Lương tháng 13 + thưởng hiệu quả dự án.</li>
        </ul>
    </body></html>
    """
    env = build_raw_envelope(html_custom_dom, job_id="9999", url="https://topcv.vn/viec-lam/embedded/9999.html")
    assert len(env.raw_payload["description_bullets"]) >= 2
    assert "STM32/ESP32" in env.raw_payload["description_bullets"][0]
    assert len(env.raw_payload["requirements_bullets"]) >= 2
    assert "C/C++" in env.raw_payload["requirements_bullets"][1]
    assert len(env.raw_payload["benefits_bullets"]) >= 1


def test_scrape16_jsonld_fallback():
    """SCRAPE-16: Fallback trích xuất JD từ schema.org JobPosting JSON-LD khi body DOM bị rỗng."""
    html_with_jsonld = """
    <html><body>
        <h1 class="box-header-job__title">Senior Python Developer</h1>
        <script type="application/ld+json">
        {
            "@context": "http://schema.org/",
            "@type": "JobPosting",
            "title": "Senior Python Developer",
            "description": "<h2>Mô tả công việc</h2><ul><li>Phát triển microservices bằng FastAPI và Python.</li><li>Thiết kế database PostgreSQL và Redis cache.</li></ul><h2>Yêu cầu ứng viên</h2><ul><li>3+ năm kinh nghiệm Python.</li><li>Thành thạo Docker, Kubernetes.</li></ul>",
            "jobBenefits": "<ul><li>Thưởng quý và bảo hiểm sức khỏe VIP.</li></ul>"
        }
        </script>
    </body></html>
    """
    env = build_raw_envelope(html_with_jsonld, job_id="8888", url="https://topcv.vn/viec-lam/python/8888.html")
    assert len(env.raw_payload["description_bullets"]) == 2
    assert "FastAPI" in env.raw_payload["description_bullets"][0]
    assert len(env.raw_payload["requirements_bullets"]) == 2
    assert "Docker" in env.raw_payload["requirements_bullets"][1]
    assert len(env.raw_payload["benefits_bullets"]) == 1
