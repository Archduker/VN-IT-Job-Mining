# -*- coding: utf-8 -*-
"""Unit tests OFFLINE cho guard sync_to_minio (chống ghi đè ledger bằng catalog rỗng/nhỏ).

Không gọi mạng/MinIO (monkeypatch). Chạy:
  python crawlers/sources/itviec/tests/test_sync_guard.py
  pytest crawlers/sources/itviec/tests/test_sync_guard.py -q
"""

import os
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import boto3

from crawlers.common.url_ledger import UrlLedger
from crawlers.sources.itviec import parser
from crawlers.sources.itviec.crawler import ItviecCrawler


def _mk_crawler():
    return ItviecCrawler(output_dir=tempfile.mkdtemp(), min_delay=0.0, max_delay=0.0)


def test_can_upload_catalog_rules():
    assert parser.can_upload_catalog(0, None) is False      # local rỗng -> không ghi
    assert parser.can_upload_catalog(0, 5) is False
    assert parser.can_upload_catalog(5, None) is True       # chưa có remote -> cho ghi
    assert parser.can_upload_catalog(5, 3) is True          # local lớn hơn (merge) -> cho ghi
    assert parser.can_upload_catalog(5, 5) is True
    assert parser.can_upload_catalog(3, 5) is False         # local < remote -> chặn ghi đè


def test_url_ledger_blocks_empty_catalog_upload():
    led = UrlLedger(source="itviec", storage_dir=os.path.join(tempfile.mkdtemp(), "ul"))
    led.save_catalog()  # catalog rỗng {}
    calls = []
    orig = boto3.client

    class _S3:
        def head_bucket(self, **k): return {}
        def create_bucket(self, **k): pass
        def upload_file(self, fp, b, k): calls.append(k)

    boto3.client = lambda *a, **k: _S3()
    try:
        ok = led.sync_to_minio()
    finally:
        boto3.client = orig
    assert ok is False
    assert calls == []  # catalog rỗng KHÔNG được upload


def test_guard_simulation_no_sync():
    craw = _mk_crawler()
    craw.sync_mode = False
    called = []
    craw.ledger.sync_to_minio = lambda *a, **k: called.append(1)
    assert craw._guard_sync_minio() is False
    assert called == []


def test_guard_blocks_local_less_than_remote(monkeypatch=None):
    craw = _mk_crawler()
    craw.sync_mode = True
    orig = (parser.sync_mode, parser.local_catalog_count, parser.remote_catalog_count)
    called = []
    try:
        parser.sync_mode = lambda: True
        parser.local_catalog_count = lambda led: 2
        parser.remote_catalog_count = lambda led: 1000
        craw.ledger.sync_to_minio = lambda *a, **k: called.append(1)
        assert craw._guard_sync_minio() is False
        assert called == []
    finally:
        parser.sync_mode, parser.local_catalog_count, parser.remote_catalog_count = orig


def test_guard_allows_valid_upload():
    craw = _mk_crawler()
    craw.sync_mode = True
    orig = (parser.sync_mode, parser.local_catalog_count, parser.remote_catalog_count)
    called = []
    try:
        parser.sync_mode = lambda: True
        parser.local_catalog_count = lambda led: 1550
        parser.remote_catalog_count = lambda led: 1548
        craw.ledger.sync_to_minio = lambda *a, **k: called.append(1)
        assert craw._guard_sync_minio() is True
        assert called == [1]
    finally:
        parser.sync_mode, parser.local_catalog_count, parser.remote_catalog_count = orig


def test_guard_empty_local_catalog_blocks():
    craw = _mk_crawler()
    craw.sync_mode = True
    orig = (parser.sync_mode, parser.local_catalog_count)
    called = []
    try:
        parser.sync_mode = lambda: True
        parser.local_catalog_count = lambda led: 0
        craw.ledger.sync_to_minio = lambda *a, **k: called.append(1)
        assert craw._guard_sync_minio() is False   # local rỗng -> không đụng remote
        assert called == []
    finally:
        parser.sync_mode, parser.local_catalog_count = orig


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {fn.__name__}: {e}")
    print(f"\n{passed}/{len(fns)} sync-guard tests passed.")
    sys.exit(0 if passed == len(fns) else 1)
