# -*- coding: utf-8 -*-
"""C14 cho 6 nguồn còn lại: không lấy được trang danh sách nào thì raise DiscoveryError (SCRAPE-11). Chạy offline."""

from __future__ import annotations

import contextlib
from types import SimpleNamespace

import pytest

from collection.common.url_ledger import DiscoveryError, UrlLedger
from collection.sources.careerviet import crawler as cv_mod
from collection.sources.itviec import crawler as it_mod
from collection.sources.jobsgo import crawler as jg_mod
from collection.sources.vieclam24h import crawler as v24_mod
from collection.sources.vietnamworks import crawler as vw_mod


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    for mod in (cv_mod, it_mod, jg_mod, v24_mod, vw_mod):
        monkeypatch.setattr(mod, "polite_sleep", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(UrlLedger, "pull_from_r2", lambda self, *a, **k: True)
    monkeypatch.setattr(UrlLedger, "sync_to_r2", lambda self, *a, **k: True)


def test_jobsgo_all_pages_fail(tmp_path, monkeypatch):
    c = jg_mod.JobsGoCrawler(output_dir=str(tmp_path), ledger_dir=str(tmp_path / "l"), raw_dir=str(tmp_path / "r"))
    monkeypatch.setattr(c, "_get_page_content", lambda url: "")
    with pytest.raises(DiscoveryError):
        c.discover_urls(online=True, max_pages=1)


def test_careerviet_all_pages_fail(tmp_path, monkeypatch):
    c = cv_mod.CareerVietCrawler(output_dir=str(tmp_path), ledger_dir=str(tmp_path / "l"), raw_dir=str(tmp_path / "r"))

    class Boom:
        def get_html(self, *a, **k):
            raise RuntimeError("HTTP 500")

        def close(self):
            pass

    monkeypatch.setattr(c, "_online_client", lambda: Boom())
    with pytest.raises(DiscoveryError):
        c.discover_urls(online=True, max_pages=1)


def test_vieclam24h_all_pages_fail(tmp_path, monkeypatch):
    c = v24_mod.ViecLam24hCrawler(output_dir=str(tmp_path))
    c.client = SimpleNamespace(get=lambda url, **k: SimpleNamespace(status_code=500, text=""))
    with pytest.raises(DiscoveryError):
        c.discover_urls(online=True, max_pages=1)


def test_itviec_all_pages_fail_and_no_sitemap(tmp_path, monkeypatch):
    c = it_mod.ItviecCrawler(output_dir=str(tmp_path), ledger_dir=str(tmp_path / "l"), raw_dir=str(tmp_path / "r"))

    @contextlib.contextmanager
    def fetcher(use_playwright=False):
        def fetch(url):
            raise RuntimeError("HTTP 500")

        yield fetch

    monkeypatch.setattr(c, "_fetcher", fetcher)
    monkeypatch.setattr(c, "_discover_from_sitemaps", lambda: 0)
    with pytest.raises(DiscoveryError):
        c.discover_urls(online=True, max_pages=1)


def test_vietnamworks_all_queries_fail(tmp_path, monkeypatch):
    class Boom:
        def post(self, *a, **k):
            raise RuntimeError("HTTP 500")

    c = vw_mod.VietnamWorksCrawler(output_dir=str(tmp_path), http_client=Boom(), max_items=1)
    with pytest.raises(DiscoveryError):
        c.discover_urls(online=True, max_pages=1)


def test_glints_all_pages_fail(tmp_path, monkeypatch):
    from collection.sources.glints.raw_pipeline import GlintsRawPipeline
    from tests.contract import standards

    class Store(standards.FakeR2Store):
        def get_json(self, key):
            return None

    p = GlintsRawPipeline(storage_dir=str(tmp_path), r2_store=Store(), delay_min=0, delay_max=0)
    monkeypatch.setattr(p, "_post_glints_discovery_request", lambda payload: SimpleNamespace(
        status_code=500, text="boom", json=lambda: {}, content=b""))
    monkeypatch.setattr(p, "_close_glints_browser", lambda: None)
    monkeypatch.setattr(p, "_finish_discovery", lambda full_scan=False: None)
    with pytest.raises(DiscoveryError):
        p.discover_urls(max_pages=1)
