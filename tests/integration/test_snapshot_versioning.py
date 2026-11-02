# -*- coding: utf-8 -*-
"""Tiêu chuẩn C12: cào lại mà hash đổi thì ghi _v<N+1>, không đổi thì không ghi file mới.

TopCV và JobsGO trước 02/11/2026 luôn ghi _v1. Hàm bóc tách HTML được thay bằng bản giả để test chỉ kiểm
logic version trong crawl_details; việc bóc tách thật thuộc contract test với fixtures.
"""

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from collection.common.url_ledger import UrlLedger, clean_canonical_url, generate_url_hash

OLD = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
RECENT = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

# job_id -> (trạng thái, last_scraped_at, content_hash, latest_version) trong ledger, và hash lần cào này
CASES = {
    "1001": (("PENDING", None, None, 0), "h-new"),          # tin mới -> _v1
    "1002": (("DONE", OLD, "h-same", 1), "h-same"),         # cào lại, hash giống -> không file mới, giữ v1
    "1003": (("DONE", OLD, "h-old", 1), "h-changed"),       # cào lại, hash khác -> _v2
    "1004": (("DONE", RECENT, "h-dup", 1), None),           # tin gốc của repost, chưa đến hạn
    "1005": (("PENDING", None, None, 0), "h-dup"),          # repost của 1004 -> không file mới
}

SOURCES = {
    "topcv": ("collection.sources.topcv.crawler", "https://www.topcv.vn/viec-lam/x/{}.html"),
    "jobsgo": ("collection.sources.jobsgo.crawler", "https://jobsgo.vn/viec-lam/x-{}.html"),
}


def make_crawler(source, tmp_path):
    if source == "topcv":
        from collection.sources.topcv.crawler import TopCVCrawler

        return TopCVCrawler(ledger_dir=str(tmp_path / "ledger"), raw_root=str(tmp_path / "raw"),
                            local_html_dir=str(tmp_path / "html"), min_delay=0, max_delay=0)
    from collection.sources.jobsgo.crawler import JobsGoCrawler

    return JobsGoCrawler(output_dir=str(tmp_path / "jobsgo"), ledger_dir=str(tmp_path / "ledger"),
                         raw_dir=str(tmp_path / "raw"), local_html_dir=str(tmp_path / "html"),
                         engine="playwright", min_delay=0, max_delay=0)


@pytest.fixture(params=sorted(SOURCES))
def crawled(request, tmp_path, monkeypatch):
    source = request.param
    module_name, url_tpl = SOURCES[source]
    module = __import__(module_name, fromlist=["x"])
    records = {}
    (tmp_path / "html").mkdir()
    for job_id, ((status, scraped, old_hash, version), _) in CASES.items():
        url = clean_canonical_url(url_tpl.format(job_id))
        records[generate_url_hash(url)] = {
            "url_hash": generate_url_hash(url), "canonical_url": url, "source": source, "job_id": job_id,
            "status": status, "last_scraped_at": scraped, "content_hash": old_hash, "latest_version": version,
        }
        (tmp_path / "html" / f"{job_id}.html").write_text("<html></html>", encoding="utf-8")
    (tmp_path / "ledger").mkdir()
    (tmp_path / "ledger" / "catalog_master.json").write_text(json.dumps(records), encoding="utf-8")

    def fake_envelope(html, job_id, url, **kwargs):
        meta = {"job_id": job_id, "source": source, "source_url": url, "version": 1,
                "scraped_at": datetime.now(timezone.utc).isoformat(), "content_hash": CASES[job_id][1]}
        return SimpleNamespace(metadata=meta, raw_payload={"title": f"Job {job_id}"},
                               model_dump=lambda **k: {"metadata": meta, "raw_payload": {"title": f"Job {job_id}"}})

    monkeypatch.setattr(module, "build_raw_envelope", fake_envelope)
    monkeypatch.setattr(module, "polite_sleep", lambda *a, **k: None, raising=False)
    crawler = make_crawler(source, tmp_path)
    stats = crawler.crawl_details(online=False)
    ledger = {r["job_id"]: r for r in UrlLedger(source, storage_dir=str(tmp_path / "ledger")).records.values()}
    files = sorted(p.name for p in (tmp_path / "raw" / TODAY).glob("*.json"))
    return source, stats, ledger, files


def test_new_job_writes_v1(crawled):
    _, _, ledger, files = crawled
    assert "1001_v1.json" in files and ledger["1001"]["latest_version"] == 1


def test_unchanged_recrawl_writes_nothing_and_keeps_version(crawled):
    _, stats, ledger, files = crawled
    assert not any(f.startswith("1002_") for f in files)
    assert ledger["1002"]["latest_version"] == 1 and ledger["1002"]["status"] == "DONE"
    assert ledger["1002"]["last_scraped_at"] != OLD  # đã được đánh dấu cào lại
    assert stats.get("unchanged") == 1


def test_changed_recrawl_writes_next_version(crawled):
    _, _, ledger, files = crawled
    assert "1003_v2.json" in files and "1003_v1.json" not in files
    assert ledger["1003"]["latest_version"] == 2 and ledger["1003"]["content_hash"] == "h-changed"


def test_repost_writes_nothing(crawled):
    _, _, ledger, files = crawled
    assert not any(f.startswith("1005_") for f in files)
    assert ledger["1005"].get("repost_of_url_hash")


def test_next_version_treats_recheck_due_as_done():
    assert UrlLedger.next_version({"status": "RECHECK_DUE", "content_hash": "h", "latest_version": 3}, "h") == (False, 3)
    assert UrlLedger.next_version({"status": "RECHECK_DUE", "content_hash": "h", "latest_version": 3}, "x") == (True, 4)
    assert UrlLedger.next_version({"status": "PENDING"}, "h") == (True, 1)
    assert UrlLedger.next_version({"status": "FAILED", "content_hash": "h", "latest_version": 1}, "h") == (True, 2)
