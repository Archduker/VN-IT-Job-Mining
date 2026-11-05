# -*- coding: utf-8 -*-
"""SCRAPE-4: raw và ledger không được lệch nhau.

reconcile_ledger_from_raw dựng lại ledger từ raw, push_raw_to_r2 không để ledger cũ đè bản mới hơn,
và UrlLedger.sync_final báo lỗi thay vì im lặng.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import push_raw_to_r2  # noqa: E402
import reconcile_ledger_from_raw as reconcile  # noqa: E402
from collection.common.url_ledger import LedgerSyncError, UrlLedger, clean_canonical_url, generate_url_hash  # noqa: E402

OLD = "2026-10-21T09:00:00+00:00"


def url(job_id):
    return f"https://topdev.vn/viec-lam/job-{job_id}"


def record(job_id, status="DONE", **extra):
    canon = clean_canonical_url(url(job_id))
    return generate_url_hash(canon), {"url_hash": generate_url_hash(canon), "canonical_url": canon, "job_id": job_id,
                                      "status": status, "last_scraped_at": OLD, "content_hash": "old",
                                      "latest_version": 1, **extra}


def raw(data, job_id, day, version=1, scraped=None):
    path = data / "topdev" / "raw" / day / f"{job_id}_v{version}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = {"job_id": job_id, "source": "topdev", "source_url": url(job_id), "version": version,
            "scraped_at": scraped or f"{day}T06:00:00+00:00", "content_hash": f"h-{job_id}-{version}"}
    path.write_text(json.dumps({"metadata": meta, "raw_payload": {"title": job_id}}), encoding="utf-8")


@pytest.fixture
def data(tmp_path):
    data = tmp_path / "data"
    ledger_dir = data / "topdev" / "url_ledger"
    ledger_dir.mkdir(parents=True)
    records = dict([record("A"), record("C", status="CLOSED"), record("R", repost_of_url_hash="x"), record("S"),
                    record("Q", repost_of_url_hash="y")])
    (ledger_dir / "catalog_master.json").write_text(json.dumps(records), encoding="utf-8")
    raw(data, "A", "2026-11-01", version=2)         # ledger cũ hơn -> cập nhật
    raw(data, "B", "2026-11-01")                    # không có trong ledger -> tạo mới
    raw(data, "C", "2026-11-01")                    # CLOSED -> không đụng
    raw(data, "R", "2026-10-21", scraped=OLD)      # repost, không có lần cào mới -> không đụng
    raw(data, "Q", "2026-11-01")                    # repost nhưng lần cào sau đã lưu raw -> cập nhật, bỏ dấu repost
    raw(data, "S", "2026-10-21", scraped="2026-10-21T09:30:00+00:00")  # chỉ lệch 30 phút -> không đổi
    batch = data / "topdev" / "raw" / "2026-10-20" / "batch_001.json"
    batch.parent.mkdir(parents=True)
    batch.write_text(json.dumps([{"metadata": {"job_id": "Z"}, "raw_payload": {}}]), encoding="utf-8")
    return data


def load(data):
    return {r["job_id"]: r for r in json.loads(
        (data / "topdev" / "url_ledger" / "catalog_master.json").read_text(encoding="utf-8")).values()}


def test_dry_run_does_not_write(data):
    before = load(data)
    counts = reconcile.run_source("topdev", data, apply=False, push=False)
    assert counts == {"create": 1, "update": 2, "skip_closed": 1, "skip_repost": 1}
    assert load(data) == before


def test_apply_updates_creates_and_is_idempotent(data):
    reconcile.run_source("topdev", data, apply=True, push=False)
    led = load(data)
    assert led["A"]["status"] == "DONE" and led["A"]["last_scraped_at"].startswith("2026-11-01")
    assert led["A"]["latest_version"] == 2 and led["A"]["content_hash"] == "h-A-2"
    assert led["B"]["status"] == "DONE" and led["B"]["canonical_url"] == clean_canonical_url(url("B"))
    assert led["C"]["status"] == "CLOSED" and led["C"]["last_scraped_at"] == OLD
    assert led["R"]["last_scraped_at"] == OLD and led["R"]["repost_of_url_hash"] == "x"
    assert led["Q"]["last_scraped_at"].startswith("2026-11-01") and "repost_of_url_hash" not in led["Q"]
    assert led["S"]["content_hash"] == "old"
    assert "Z" not in led  # file batch cũ bị bỏ qua
    again = reconcile.run_source("topdev", data, apply=True, push=False)
    assert again["create"] == 0 and again["update"] == 0


def test_push_decision_never_overwrites_newer_remote():
    local = {"h1": {"last_scraped_at": "2026-11-01T00:00:00"}}
    assert push_raw_to_r2.ledger_push_decision(local, None) == (True, "ok")
    assert push_raw_to_r2.ledger_push_decision(local, {"h1": {"last_scraped_at": "2026-10-01"}})[0] is True
    assert push_raw_to_r2.ledger_push_decision({}, None)[0] is False
    assert push_raw_to_r2.ledger_push_decision(local, {"h1": {"last_scraped_at": "2026-11-02"}})[0] is False
    newer_url = {"h1": {"last_scraped_at": "2026-10-01"}, "h2": {"last_scraped_at": "2026-10-01"}}
    assert push_raw_to_r2.ledger_push_decision(local, newer_url)[0] is False


def test_sync_final_raises_when_sync_fails(tmp_path, monkeypatch):
    ledger = UrlLedger(source="topdev", storage_dir=str(tmp_path / "ledger"))
    monkeypatch.setattr(ledger, "sync_to_r2", lambda: False)
    with pytest.raises(LedgerSyncError):
        ledger.sync_final()
    monkeypatch.setattr(ledger, "sync_to_r2", lambda: True)
    ledger.sync_final()


def test_sync_to_r2_returns_false_on_client_error(tmp_path, monkeypatch):
    """Trước đây storage_label gán trong try nên lỗi tạo client thành UnboundLocalError."""
    import boto3

    ledger = UrlLedger(source="topdev", storage_dir=str(tmp_path / "ledger"))

    def boom(*a, **k):
        raise RuntimeError("no network")

    monkeypatch.setattr(boto3, "client", boom)
    assert ledger.sync_to_r2(endpoint_url="https://x.r2.cloudflarestorage.com") is False


SYNC_SOURCES = {
    "topcv": ("collection.sources.topcv.crawler", "TopCVCrawler"),
    "topdev": ("collection.sources.topdev.crawler", "TopDevCrawler"),
    "vietnamworks": ("collection.sources.vietnamworks.crawler", "VietnamWorksCrawler"),
    "careerviet": ("collection.sources.careerviet.crawler", "CareerVietCrawler"),
    "vieclam24h": ("collection.sources.vieclam24h.crawler", "ViecLam24hCrawler"),
    "itviec": ("collection.sources.itviec.crawler", "ItviecCrawler"),
    "jobsgo": ("collection.sources.jobsgo.crawler", "JobsGORawCrawler"),
}


@pytest.mark.parametrize("sync", [False, True])
@pytest.mark.parametrize("source", sorted(SYNC_SOURCES))
def test_run_crawler_passes_sync_r2(source, sync, monkeypatch, tmp_path):
    """SCRAPE-9: run.py từng tạo crawler không truyền sync_r2, nên Airflow không bao giờ đồng bộ R2."""
    import importlib

    import run

    module_name, cls_name = SYNC_SOURCES[source]
    seen = {}

    class Fake:
        def __init__(self, **kwargs):
            seen.update(kwargs)

        def discover_urls(self, max_pages=None):
            return []

    monkeypatch.setattr(importlib.import_module(module_name), cls_name, Fake)
    kwargs = {} if not sync else {"sync_r2": True}
    run.run_crawler(source=source, phase="discover", output_dir=str(tmp_path), **kwargs)
    assert seen.get("sync_r2") is sync


def test_airflow_operator_always_syncs_r2():
    source = (ROOT / "airflow" / "plugins" / "crawler_operators.py").read_text(encoding="utf-8")
    call = source[source.index("stats = run_crawler("):]
    call = call[: call.index("\n        )") ]
    assert "sync_r2=True" in call


@pytest.mark.parametrize("sync", [True, False])
def test_crawling_page_trigger_passes_sync_r2(sync, monkeypatch):
    """Ô "Đồng bộ R2" trên trang Crawling: bật thì run.py nhận --sync-r2, tắt thì không."""
    import asyncio

    from app.services import crawler_service as module
    from app.services.crawler_service import CrawlerService

    seen = {}

    class FakeProc:
        pid, returncode, stdout = 1, None, None

    async def fake_exec(*cmd, **kwargs):
        seen["cmd"] = list(cmd)
        return FakeProc()

    monkeypatch.setattr(module.asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setattr(module.asyncio, "create_task", lambda coro: coro.close())
    asyncio.run(CrawlerService().trigger_crawler("topdev", phase="detail", max_items=2, sync_r2=sync))
    assert ("--sync-r2" in seen["cmd"]) is sync


def test_trigger_request_defaults_to_sync():
    from app.schemas.crawling import TriggerCrawlRequest

    assert TriggerCrawlRequest().sync_r2 is True


def test_final_sync_follows_crawler_setting():
    """CareerViet từng gọi sync_final dưới `if sync_r2:` (tham số hàm, mặc định False), nên run.py --sync-r2
    đẩy raw nhưng không đẩy ledger. Cuối pha phải theo self.sync_r2."""
    import ast

    offenders = []
    for path in sorted((ROOT / "collection" / "sources").glob("*/crawler.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.If) and isinstance(node.test, ast.Name) and node.test.id == "sync_r2":
                if any(isinstance(n, ast.Attribute) and n.attr == "sync_final" for n in ast.walk(node)):
                    offenders.append(f"{path.parent.name}:{node.lineno}")
    assert not offenders, f"sync_final phụ thuộc tham số sync_r2 thay vì self.sync_r2: {offenders}"


# raw_batch.json cũ của VietnamWorks: tin chưa có file riêng và chưa có trong ledger thì đăng ký PENDING để cào lại
def batch_data(tmp_path):
    data = tmp_path / "data"
    src = data / "vietnamworks"
    (src / "url_ledger").mkdir(parents=True)
    vurl = lambda j: f"https://www.vietnamworks.com/job-{j}-jv"  # noqa: E731
    canon = clean_canonical_url(vurl("L"))
    ledger = {generate_url_hash(canon): {"url_hash": generate_url_hash(canon), "canonical_url": canon, "job_id": "L",
                                         "status": "DONE", "last_scraped_at": OLD, "content_hash": "x", "latest_version": 1}}
    (src / "url_ledger" / "catalog_master.json").write_text(json.dumps(ledger), encoding="utf-8")
    single = src / "raw" / "2026-10-20" / "F_v1.json"   # đã có file riêng (đã lên R2)
    single.parent.mkdir(parents=True)
    single.write_text(json.dumps({"metadata": {"job_id": "F", "source_url": vurl("F"), "scraped_at": OLD, "version": 1},
                                  "raw_payload": {}}), encoding="utf-8")
    batch = src / "raw" / "2026-10-16" / "raw_batch.json"
    batch.parent.mkdir(parents=True)
    batch.write_text(json.dumps([
        {"metadata": {"job_id": j, "source_url": vurl(j), "scraped_at": "2026-10-16T15:00:00+00:00"},
         "raw_payload": {"jobTitle": f"Tin {j}"}} for j in ("F", "L", "N")]), encoding="utf-8")
    return data, batch


def test_batch_missing_dry_run_lists_only_new_jobs(tmp_path):
    data, batch = batch_data(tmp_path)
    before = (data / "vietnamworks" / "url_ledger" / "catalog_master.json").read_text(encoding="utf-8")
    found = reconcile.register_batch_missing("vietnamworks", data, batch, apply=False, push=False)
    assert [item["job_id"] for item in found] == ["N"]
    assert (data / "vietnamworks" / "url_ledger" / "catalog_master.json").read_text(encoding="utf-8") == before


def test_batch_missing_apply_registers_pending_without_hash(tmp_path):
    data, batch = batch_data(tmp_path)
    reconcile.register_batch_missing("vietnamworks", data, batch, apply=True, push=False)
    led = {r["job_id"]: r for r in json.loads(
        (data / "vietnamworks" / "url_ledger" / "catalog_master.json").read_text(encoding="utf-8")).values()}
    assert led["N"]["status"] == "PENDING" and not led["N"].get("content_hash")
    assert led["N"]["preliminary_title"] == "Tin N" and led["N"]["registered_from_batch"].endswith("raw_batch.json")
    assert led["L"]["status"] == "DONE" and "F" not in led
    assert reconcile.register_batch_missing("vietnamworks", data, batch, apply=True, push=False) == []
