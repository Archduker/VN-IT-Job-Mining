# -*- coding: utf-8 -*-
"""Unit test cho co che CHON danh sach (_select_pending) va che do DUNG khi bi chan
(429/403/captcha -> GIU PENDING) cua crawler CareerViet.

Dung UrlLedger + tmp_path, KHONG doc data/ cuc bo, KHONG goi mang.
Bao phu:
- loc dung nhom source_category (giu thu tu chen);
- xao tat dinh (cung seed -> cung thu tu; khac seed -> khac thu tu);
- mac dinh (khong co co) = thu tu chen ledger, khong doi; cat limit = N dau;
- nhom khong ton tai -> ValueError (dung, khong goi mang);
- 429/403 -> KHONG mark_failed, record van PENDING, vong lap dung, record sau khong bi dong;
- loi khong phai chan (500) -> van mark_failed + tiep tuc (Safe Skip).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import requests

from crawlers.common.url_ledger import UrlLedger
from crawlers.sources.careerviet.crawler import CareerVietCrawler


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _crawler(tmp_path: Path) -> CareerVietCrawler:
    return CareerVietCrawler(
        max_items=None,
        output_dir=str(tmp_path / "out"),
        checkpoint_dir=str(tmp_path / "ckpt"),
        ledger_dir=str(tmp_path / "ledger"),
        raw_dir=str(tmp_path / "raw"),
    )


def _url(jid: str) -> str:
    return f"https://careerviet.vn/vi/tim-viec-lam/x.{jid}.html"


def _seed(ledger: UrlLedger, jids: list[str]) -> None:
    """Dang ky n job_id moi (mac dinh PENDING) roi luu catalog."""
    for j in jids:
        ledger.register_url(_url(j), job_id=j)
    ledger.save_catalog()


class _FakeClient:
    """Client gia: moi lan get_html dem len va raise exc duoc dinh san."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc
        self.calls = 0

    def get_html(self, url, headers=None, **kw):  # noqa: D401 - test stub
        self.calls += 1
        raise self._exc

    def close(self) -> None:
        pass


def _http_error(status: int) -> requests.HTTPError:
    resp = requests.Response()
    resp.status_code = status
    return requests.HTTPError(response=resp)


# --------------------------------------------------------------------------
# _select_pending
# --------------------------------------------------------------------------
def test_filter_by_source_category(tmp_path):
    led = UrlLedger(source="careerviet", storage_dir=str(tmp_path / "led"))
    ids_c1 = [f"C1_{i:03d}" for i in range(5)]
    ids_c37 = [f"C37_{i:03d}" for i in range(4)]
    _seed(led, ids_c1 + ids_c37)
    cat_map = {**{j: "c1" for j in ids_c1},
               **{j: "c37_digital_mkt" for j in ids_c37}}
    cr = _crawler(tmp_path)

    sel = [r["job_id"] for r in
           cr._select_pending(led, cat_map, source_categories=["c37_digital_mkt"])]
    assert sel == ids_c37  # dung nhom, giu thu tu chen


def test_shuffle_is_deterministic(tmp_path):
    led = UrlLedger(source="careerviet", storage_dir=str(tmp_path / "led"))
    ids = [f"JOB{i:03d}" for i in range(20)]
    _seed(led, ids)
    cat_map = {j: "c1" for j in ids}
    cr = _crawler(tmp_path)

    a = [r["job_id"] for r in cr._select_pending(led, cat_map, shuffle=True, seed=20261016)]
    b = [r["job_id"] for r in cr._select_pending(led, cat_map, shuffle=True, seed=20261016)]
    c = [r["job_id"] for r in cr._select_pending(led, cat_map, shuffle=True, seed=999)]
    assert a == b                    # cung seed -> cung thu tu
    assert sorted(a) == sorted(ids)  # xao khong lam mat/trim phan tu
    assert a != ids                  # thu tu thuc su bi dao
    assert c != a                    # khac seed -> khac thu tu


def test_default_order_unchanged(tmp_path):
    led = UrlLedger(source="careerviet", storage_dir=str(tmp_path / "led"))
    ids = [f"JOB{i:03d}" for i in range(10)]
    _seed(led, ids)
    cat_map = {j: "c1" for j in ids}
    cr = _crawler(tmp_path)

    base = [r["job_id"] for r in led.get_pending_or_due_records(21)]
    sel = [r["job_id"] for r in cr._select_pending(led, cat_map)]
    assert sel == base == ids  # thu tu chen, khong loc, khong xao
    # limit = cat N dau theo thu tu chen
    first3 = [r["job_id"] for r in cr._select_pending(led, cat_map, limit=3)]
    assert first3 == ids[:3]


def test_filter_then_shuffle_then_limit(tmp_path):
    """Ba buoc dung thu tu: loc -> xao -> cat (khong phai xao toan bo roi moi loc)."""
    led = UrlLedger(source="careerviet", storage_dir=str(tmp_path / "led"))
    all_ids = [f"J{i:04d}" for i in range(30)]
    _seed(led, all_ids)
    cat_map = {j: ("c37_digital_mkt" if int(j[1:]) % 2 else "c1") for j in all_ids}
    cr = _crawler(tmp_path)

    sel = cr._select_pending(led, cat_map,
                             source_categories=["c37_digital_mkt"],
                             shuffle=True, seed=7, limit=5)
    assert len(sel) == 5
    assert all(cat_map[r["job_id"]] == "c37_digital_mkt" for r in sel)


def test_invalid_category_raises(tmp_path):
    led = UrlLedger(source="careerviet", storage_dir=str(tmp_path / "led"))
    _seed(led, [f"J{i}" for i in range(3)])
    cat_map = {f"J{i}": "c1" for i in range(3)}
    cr = _crawler(tmp_path)

    with pytest.raises(ValueError):
        cr._select_pending(led, cat_map, source_categories=["khong_ton_tai"])


# --------------------------------------------------------------------------
# Che do DUNG khi bi chan (online) + preview khong luu ledger
# --------------------------------------------------------------------------
def test_blocking_keeps_pending_and_stops(tmp_path):
    cr = _crawler(tmp_path)
    led = cr._get_ledger()
    ids = [f"JOB{i:03d}" for i in range(5)]
    _seed(led, ids)

    fake = _FakeClient(_http_error(429))
    cr._online_client = lambda: fake
    stats = cr.crawl_details(online=True, limit=3)

    assert fake.calls == 1            # dung ngay o tin dau bi chan
    assert stats["files"] == 1
    assert stats["failed"] == 0       # 429 KHONG bi tinh failed
    # Khong record nao bi FAILED: tat ca van PENDING (ke ca tin bi chan va 2 tin sau)
    for rec in cr._get_ledger().records.values():
        assert rec["status"] == "PENDING"


def test_non_blocking_error_marks_failed_and_continues(tmp_path):
    """Loi KHONG phai chan/5xx (connection) van theo Safe Skip: mark_failed + tiep tuc.

    (Duoc doi tu _http_error(500) sang ConnectionError: duoi Phuong an B, 500 la
    5xx nen 3 lan lien tiep se thanh 'bao' -> break + giu PENDING, khong con
    FAILED. ConnectionError moi giu dung hanh vi 'loi khac' can kiem chung.)
    """
    cr = _crawler(tmp_path)
    led = cr._get_ledger()
    ids = [f"JOB{i:03d}" for i in range(3)]
    _seed(led, ids)

    fake = _FakeClient(requests.ConnectionError("network down"))
    cr._online_client = lambda: fake
    stats = cr.crawl_details(online=True, limit=3)

    assert fake.calls == 3
    assert stats["failed"] == 3
    statuses = [rec["status"] for rec in cr._get_ledger().records.values()]
    assert statuses == ["FAILED", "FAILED", "FAILED"]


def test_preview_does_not_write_ledger(tmp_path):
    """Khong --online, khong --local-html-dir -> preview: khong luu catalog."""
    cr = _crawler(tmp_path)
    led = cr._get_ledger()
    _seed(led, [f"JOB{i:03d}" for i in range(4)])
    catalog = Path(cr.ledger_dir) / "catalog_master.json"
    before = catalog.read_bytes()

    stats = cr.crawl_details(limit=2)  # preview
    assert catalog.read_bytes() == before  # file ledger khong bi ghi
    assert stats["selected"] and stats["files"] == 0
    assert stats["success"] == 0 and stats["failed"] == 0
