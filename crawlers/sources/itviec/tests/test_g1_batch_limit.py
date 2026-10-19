# -*- coding: utf-8 -*-
"""Unit tests OFFLINE cho G1: --max-items = số URL TIN HỢP LỆ xử lý (rác không đốt ngân sách).

KHÔNG gọi mạng/MinIO (stub fetcher + sync). Chạy:
  python crawlers/sources/itviec/tests/test_g1_batch_limit.py
  pytest  crawlers/sources/itviec/tests/test_g1_batch_limit.py -q
"""

import contextlib
import json
import os
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from crawlers.sources.itviec import parser
from crawlers.sources.itviec.crawler import ItviecCrawler

V1 = "https://itviec.com/viec-lam-it/job-mot-100"
V2 = "https://itviec.com/viec-lam-it/job-hai-200"
V3 = "https://itviec.com/viec-lam-it/job-ba-300"
V4 = "https://itviec.com/viec-lam-it/job-bon-400"
BAD1 = "https://itviec.com/viec-lam-it/api"
BAD2 = "https://itviec.com/viec-lam-it/java/ha-noi"
BAD3 = "https://itviec.com/viec-lam-it/devops"


def _html(tok):
    jp = {"@context": "http://schema.org", "@type": "JobPosting", "title": "J" + tok, "skills": "Py",
          "baseSalary": {"@type": "MonetaryAmount", "currency": "VND",
                         "value": {"@type": "QuantitativeValue", "minValue": 1, "maxValue": 2, "unitText": "MONTH"}},
          "description": "d", "validThrough": "2026-12-31"}
    return ("<html><body><main><section class='job-content'><h2>Mô tả</h2><p>" + tok +
            "</p></section></main><script type='application/ld+json'>" + json.dumps(jp, ensure_ascii=False) +
            "</script></body></html>")


def _crawler(urls):
    d = tempfile.mkdtemp()
    a = ItviecCrawler(output_dir=d, min_delay=0.0, max_delay=0.0)
    for u in urls:
        a.ledger.register_url(u, parser.extract_job_id(u), "T", "C")
    a.ledger.save_catalog()
    b = ItviecCrawler(output_dir=d, min_delay=0.0, max_delay=0.0)

    @contextlib.contextmanager
    def ff():
        def fetch(url):
            return (_html(url.rsplit("/", 1)[-1]), 200)
        yield fetch
    b._fetcher = ff
    b.ledger.sync_to_minio = lambda *a2, **k: True      # không đụng MinIO
    b.ledger.export_daily_manifest = lambda *a2, **k: __import__("io").BytesIO()
    return b


def _run(b, limit):
    orig = parser.remote_catalog_count
    try:
        parser.remote_catalog_count = lambda led: 0     # tránh gọi mạng khi guard check remote
        return b.crawl_details(limit=limit)
    finally:
        parser.remote_catalog_count = orig


def test_batch_mixed_rac_khong_dot_ngan_sach():
    b = _crawler([BAD1, V1, V2, V3])
    s = _run(b, limit=2)
    assert s["crawled_new"] == 2, s            # 2 TIN HỢP LỆ
    assert s["non_job_url"] == 1, s            # BAD1 thống kê, không đốt limit
    assert s["scanned"] >= 3, s                # đã lướt qua cả BAD1
    assert s["errors"] == 0, s


def test_batch_toan_rac_khong_crawl():
    b = _crawler([BAD1, BAD2, BAD3])
    s = _run(b, limit=2)
    assert s["crawled_new"] == 0, s
    assert s["non_job_url"] == 3, s            # gộp cả 3 vẫn chỉ là non_job_url, không crawl
    assert s["errors"] == 0, s


def test_limit_dung_dung_so_tin_hop_le():
    b = _crawler([V1, V2, V3, V4])
    s = _run(b, limit=2)
    assert s["crawled_new"] == 2, s


def test_batch_tiep_tuc_khong_crawl_lai():
    b = _crawler([V1, V2, V3, V4])
    s1 = _run(b, limit=2)
    s2 = _run(b, limit=2)
    assert s1["crawled_new"] == 2 and s2["crawled_new"] == 2, (s1, s2)


def test_dup_job_id_van_dem_ngan_sach():
    b = _crawler([V1, V1 + "?page=2"])          # 2 URL, cùng job_id
    s = _run(b, limit=5)
    assert s["crawled_new"] == 1, s
    assert s["dup_job_id"] == 1, s


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
    print(f"\n{passed}/{len(fns)} G1 batch-limit tests passed.")
    sys.exit(0 if passed == len(fns) else 1)
