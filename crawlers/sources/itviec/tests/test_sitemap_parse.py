# -*- coding: utf-8 -*-
"""Unit tests OFFLINE cho sitemap discovery (không mạng).

Chạy:  python crawlers/sources/itviec/tests/test_sitemap_parse.py
   hoặc: pytest crawlers/sources/itviec/tests/test_sitemap_parse.py -q
"""

import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from crawlers.sources.itviec import config as C
from crawlers.sources.itviec import parser

SAMPLE_URLSET = (
    '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    "<url><loc>https://itviec.com/viec-lam-it/a-1?x=1</loc></url>"
    "<url><loc>https://itviec.com/nha-tuyen-dung/x</loc></url>"
    "<url><loc>  https://itviec.com/viec-lam-it/b-2  </loc></url>"
    "</urlset>"
)
SAMPLE_INDEX = (
    "<sitemapindex><sitemap><loc>https://itviec.com/twinnings_jobs_desc_vn.xml</loc></sitemap>"
    "<sitemap><loc>https://itviec.com/twinnings_companies_vn.xml</loc></sitemap></sitemapindex>"
)


def test_parse_sitemap_extracts_locs():
    assert parser.parse_sitemap(SAMPLE_URLSET) == [
        "https://itviec.com/viec-lam-it/a-1?x=1",
        "https://itviec.com/nha-tuyen-dung/x",
        "https://itviec.com/viec-lam-it/b-2",
    ]


def test_parse_sitemap_empty():
    assert parser.parse_sitemap("") == []
    assert parser.parse_sitemap(None) == []


def test_sitemap_index_filters_job_maps():
    children = parser.parse_sitemap(SAMPLE_INDEX)
    job_maps = [u for u in children if "job" in u.lower() and "_vn" in u.lower()]
    assert job_maps == ["https://itviec.com/twinnings_jobs_desc_vn.xml"]


def test_detail_only_and_job_id():
    jobs = [l for l in parser.parse_sitemap(SAMPLE_URLSET) if C.DETAIL_PATH_PREFIX in l]
    assert len(jobs) == 2
    assert parser.extract_job_id("https://itviec.com/viec-lam-it/senior-python-123") == "senior-python-123"


def test_config_constants():
    assert getattr(C, "SITEMAP_URL", "").endswith(".xml")
    assert C.DETAIL_PATH_PREFIX == "/viec-lam-it/"
    assert C.JD_HASH_CONTAINER == "section.job-content"


def test_is_job_url_true_for_real_jobs():
    assert parser.is_job_url("https://itviec.com/viec-lam-it/sap-public-cloud-datvietvac-5150")
    assert parser.is_job_url("https://itviec.com/viec-lam-it/data-business-analyst-id12287-vpbank-1219")


def test_is_job_url_false_for_category_pages():
    assert not parser.is_job_url("https://itviec.com/viec-lam-it")                     # listing root
    assert not parser.is_job_url("https://itviec.com/viec-lam-it/api")                  # trang kỹ năng
    assert not parser.is_job_url("https://itviec.com/viec-lam-it/a-b-testing/ho-chi-minh-hcm")  # skill/city
    assert not parser.is_job_url("https://itviec.com/viec-lam-it/backend-developer-java")  # khong co -so


def test_filter_job_urls_split():
    jobs, non = parser.filter_job_urls([
        "https://itviec.com/viec-lam-it/x-abbank-3801",
        "https://itviec.com/viec-lam-it/api",
        "https://itviec.com/viec-lam-it/api/ha-noi",
    ])
    assert jobs == ["https://itviec.com/viec-lam-it/x-abbank-3801"]
    assert len(non) == 2


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
    print(f"\n{passed}/{len(fns)} offline sitemap tests passed.")
    sys.exit(0 if passed == len(fns) else 1)
