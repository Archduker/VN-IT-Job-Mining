# -*- coding: utf-8 -*-
"""Unit test Two-Phase (discover_urls + crawl_details) cho CareerViet.

Dung HTML MINI trong tmp_path, KHONG doc data/ cuc bo, KHONG goi mang.
Bao phu:
- discover offline tu file urls_*.json -> ledger PENDING.
- crawl_details offline: ghi envelope v1, status DONE.
- Idempotent: chay lan 2 khong sinh file moi, khong doi version.
- Tin ngoai ledger -> not_in_ledger (khong xu ly).
- Safe Skip: file hong (khong doc duoc UTF-8) -> mark_failed, tiep tuc.
- Repost: 2 tin cung noi dung -> tin sau mark repost, khong ghi file moi.
- Re-crawl 21 ngay (thoi gian gia): noi dung doi + last_scraped_at cu -> v2,
  KHONG ghi de v1.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from crawlers.sources.careerviet.crawler import CareerVietCrawler


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _mini_html(job_id: str, jd_text: str = "Build backend APIs",
               update_date: str = "15/10/2026", deadline: str = "27/10/2026") -> str:
    return f"""<!DOCTYPE html><html><body>
<div class="job-detail-page">
  <h1 class="title">Dev {job_id}</h1>
  <a class="employer job-company-name">ABC Tech</a>
  <ul class="detail-box">
    <li><strong>Ngày cập nhật</strong><p>{update_date}</p></li>
    <li><strong>Lương</strong><p>Cạnh tranh</p></li>
    <li><strong>Ngành nghề</strong><p>CNTT - Phần mềm</p></li>
    <li><strong>Hết hạn nộp</strong><p>{deadline}</p></li>
  </ul>
  <div class="detail-row"><h2>Mô tả Công việc</h2><p>{jd_text}</p></div>
  <div class="map"><p><a>Hà Nội</a></p></div>
  <div class="job-tags"><a class="tag-item">Python</a></div>
  <script id="job-posting-schema" type="application/ld+json">
    {{"@context":"http://schema.org","@type":"JobPosting","title":"Dev {job_id}"}}
  </script>
</div>
</body></html>"""


def _url(jid: str) -> str:
    return f"https://careerviet.vn/vi/tim-viec-lam/job.{jid}.html"


def _make_crawler(tmp_path: Path) -> CareerVietCrawler:
    return CareerVietCrawler(
        max_items=None,
        output_dir=str(tmp_path / "out"),
        checkpoint_dir=str(tmp_path / "ckpt"),
        ledger_dir=str(tmp_path / "ledger"),
        raw_dir=str(tmp_path / "raw"),
    )


def _seed_ledger(crawler: CareerVietCrawler, tmp_path: Path, job_ids: list[str]) -> None:
    """Tao file urls_c1_*.json roi chay discover offline nap vao ledger tam."""
    urls_dir = tmp_path / "urls"
    urls_dir.mkdir(parents=True, exist_ok=True)
    records = [
        {"url": _url(j), "job_id": j, "source_category": "c1"} for j in job_ids
    ]
    (urls_dir / "urls_c1_probe.json").write_text(
        json.dumps({"records": records}, ensure_ascii=False), encoding="utf-8"
    )
    crawler.discover_urls(urls_dir=str(urls_dir))


def _write_html(local_dir: Path, jid: str, html: str) -> None:
    local_dir.mkdir(parents=True, exist_ok=True)
    (local_dir / f"{jid}.html").write_text(html, encoding="utf-8")


def _raw_files(crawler: CareerVietCrawler) -> list[str]:
    return sorted(p.name for p in Path(crawler.raw_dir).rglob("*.json"))


def _status(crawler: CareerVietCrawler, jid: str) -> str:
    for rec in crawler._get_ledger().records.values():
        if rec["job_id"] == jid:
            return rec["status"]
    return "ABSENT"


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------
def test_discover_offline_registers_pending(tmp_path):
    crawler = _make_crawler(tmp_path)
    _seed_ledger(crawler, tmp_path, ["AAAA11", "BBBB22"])
    ledger = crawler._get_ledger()
    assert len(ledger.records) == 2
    assert all(rec["status"] == "PENDING" for rec in ledger.records.values())
    # category map duoc luu vao ledger dir va nap lai duoc
    cat = crawler._load_category_map()
    assert cat.get("AAAA11") == "c1"


def test_crawl_details_offline_done_and_idempotent(tmp_path):
    crawler = _make_crawler(tmp_path)
    _seed_ledger(crawler, tmp_path, ["AAAA11"])
    local = tmp_path / "html"
    _write_html(local, "AAAA11", _mini_html("AAAA11"))

    stats = crawler.crawl_details(local_html_dir=str(local))
    assert stats["success"] == 1 and stats["failed"] == 0
    assert stats["files_written"] == 1 and stats["versions"] == {"1": 1}
    assert _status(crawler, "AAAA11") == "DONE"
    files_after_run1 = _raw_files(crawler)
    assert files_after_run1 == ["AAAA11_v1.json"]

    # Lan 2: da DONE, chua den 21 ngay -> khong sinh file moi, khong doi version
    stats2 = crawler.crawl_details(local_html_dir=str(local))
    assert stats2["success"] == 0 and stats2["skipped_not_due"] == 1
    assert stats2["files_written"] == 0 and _raw_files(crawler) == files_after_run1


def test_envelope_content_and_industry(tmp_path):
    crawler = _make_crawler(tmp_path)
    _seed_ledger(crawler, tmp_path, ["AAAA11"])
    local = tmp_path / "html"
    _write_html(local, "AAAA11", _mini_html("AAAA11"))
    crawler.crawl_details(local_html_dir=str(local))
    env_path = next(Path(crawler.raw_dir).rglob("AAAA11_v1.json"))
    env = json.loads(env_path.read_text(encoding="utf-8"))
    meta = env["metadata"]
    assert meta["source"] == "careerviet"
    assert meta["source_category"] == "c1"
    assert meta["version"] == 1
    assert meta["source_url"] == _url("AAAA11")
    # "Ngành nghề" NGUYÊN VĂN duoc luu o tang raw
    assert env["raw_payload"]["Ngành nghề"] == ["CNTT - Phần mềm"]


def test_not_in_ledger_is_reported_and_skipped(tmp_path):
    crawler = _make_crawler(tmp_path)
    _seed_ledger(crawler, tmp_path, ["AAAA11"])  # chi AAAA11 nam trong ledger
    local = tmp_path / "html"
    _write_html(local, "AAAA11", _mini_html("AAAA11"))
    _write_html(local, "ZZZZ99", _mini_html("ZZZZ99"))  # ngoai ledger

    stats = crawler.crawl_details(local_html_dir=str(local))
    assert "ZZZZ99" in stats["not_in_ledger"]
    assert stats["success"] == 1  # chi AAAA11 duoc xu ly
    assert _status(crawler, "ZZZZ99") == "ABSENT"


def test_safe_skip_marks_failed_on_unreadable_file(tmp_path):
    crawler = _make_crawler(tmp_path)
    _seed_ledger(crawler, tmp_path, ["AAAA11"])
    local = tmp_path / "html"
    local.mkdir(parents=True, exist_ok=True)
    # Byte khong hop le UTF-8 -> read_text ngoai le -> Safe Skip mark_failed
    (local / "AAAA11.html").write_bytes(b"\xff\xfe\x00invalid utf8 \x80\x81")

    stats = crawler.crawl_details(local_html_dir=str(local))
    assert stats["failed"] == 1 and stats["success"] == 0
    assert _status(crawler, "AAAA11") == "FAILED"


def test_repost_second_identical_content_no_new_file(tmp_path):
    crawler = _make_crawler(tmp_path)
    _seed_ledger(crawler, tmp_path, ["AAAA11", "CCCC33"])
    local = tmp_path / "html"
    same = _mini_html("FIXED", jd_text="Identical JD content")
    _write_html(local, "AAAA11", same)
    _write_html(local, "CCCC33", same)

    stats = crawler.crawl_details(local_html_dir=str(local))
    # Mot tin success, tin con lại repost (cung hash); chi 1 file envelope
    assert stats["success"] == 1 and stats["repost"] == 1
    assert stats["files_written"] == 1
    assert _raw_files(crawler) == ["AAAA11_v1.json"]
    assert _status(crawler, "CCCC33") == "DONE"


def test_recrawl_after_21_days_bumps_version_no_overwrite(tmp_path):
    crawler = _make_crawler(tmp_path)
    _seed_ledger(crawler, tmp_path, ["AAAA11"])
    local = tmp_path / "html"
    _write_html(local, "AAAA11", _mini_html("AAAA11", jd_text="OLD content"))
    crawler.crawl_details(local_html_dir=str(local))
    assert _raw_files(crawler) == ["AAAA11_v1.json"]

    # Gia lap: da cào 22 ngày trước -> chỉnh catalog trực tiếp
    catalog = Path(crawler.ledger_dir) / "catalog_master.json"
    data = json.loads(catalog.read_text(encoding="utf-8"))
    old_iso = (datetime.now(timezone.utc) - timedelta(days=22)).isoformat()
    for rec in data.values():
        rec["last_scraped_at"] = old_iso
    catalog.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    # Noi dung JD doi -> content_hash doi -> phai tao v2
    _write_html(local, "AAAA11", _mini_html("AAAA11", jd_text="NEW content different"))
    crawler2 = _make_crawler(tmp_path)  # doc lai ledger tu disk
    stats = crawler2.crawl_details(local_html_dir=str(local))
    assert stats["success"] == 1 and stats["versions"] == {"2": 1}
    files = _raw_files(crawler2)
    assert "AAAA11_v1.json" in files and "AAAA11_v2.json" in files

    # v1 KHONG bi ghi de (van la version 1); v2 la version 2
    v1_path = next(Path(crawler2.raw_dir).rglob("AAAA11_v1.json"))
    v2_path = next(Path(crawler2.raw_dir).rglob("AAAA11_v2.json"))
    v1 = json.loads(v1_path.read_text(encoding="utf-8"))
    v2 = json.loads(v2_path.read_text(encoding="utf-8"))
    assert v1["metadata"]["version"] == 1
    assert v2["metadata"]["version"] == 2
