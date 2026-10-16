# -*- coding: utf-8 -*-
"""Offline tests for the two-phase Glints/JobsGO pipeline; no live HTTP/MinIO."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from crawlers.sources.glints.raw_pipeline import GlintsRawPipeline
from crawlers.sources.jobsgo.crawler import JobsGORawCrawler


class FakeStore:
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def get_bytes(self, key):
        return self.objects.get(key)

    def get_json(self, key):
        payload = self.get_bytes(key)
        return json.loads(payload.decode("utf-8")) if payload is not None else None

    def put_bytes(self, key, data, content_type="application/octet-stream"):
        self.objects[key] = data

    def put_text(self, key, text, content_type="text/plain; charset=utf-8"):
        self.put_bytes(key, text.encode("utf-8"), content_type)

    def put_json(self, key, value):
        self.put_bytes(key, json.dumps(value, ensure_ascii=False, default=str).encode("utf-8"), "application/json")

    def put_file(self, key, path: Path, content_type="application/octet-stream"):
        self.put_bytes(key, Path(path).read_bytes(), content_type)


class FakeResponse:
    def __init__(self, *, status_code=200, text="", data=None, url="", headers=None):
        self.status_code = status_code
        self.text = text
        self._data = data
        self.url = url
        self.headers = headers or {"Content-Type": "text/html; charset=utf-8"}

    def json(self):
        return self._data


class FakeSession:
    def __init__(self, *, listing_body=None, html_by_url=None, pages=None):
        self.headers = {}
        self.listing_body = listing_body
        self.html_by_url = html_by_url or {}
        self.pages = pages or {}
        self.get_calls = []
        self.post_calls = []

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return FakeResponse(status_code=200, data=self.listing_body, url=url,
                            headers={"Content-Type": "application/json"})

    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        if url in self.pages:
            status, html = self.pages[url]
        elif url in self.html_by_url:
            status, html = 200, self.html_by_url[url]
        else:
            status, html = 404, ""
        return FakeResponse(status_code=status, text=html, url=url)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = FakeStore()

    def test_glints_discover_and_store_raw_snapshot(self):
        listing = {
            "data": {"searchJobsV3": {
                "jobsInPage": [{
                    "id": "g-1", "title": "Backend Engineer",
                    "company": {"id": "c-1", "name": "Company A", "brandName": "Company A"},
                    "salaries": [{"minAmount": 10000000, "maxAmount": 20000000, "CurrencyCode": "VND"}],
                    "skills": [{"mustHave": True, "skill": {"name": "Python"}}],
                }],
                "hasMore": False,
            }}
        }
        detail_html = "<html><body><main><h1>Backend Engineer</h1><p>Python distributed systems</p></main></body></html>"
        session = FakeSession(listing_body=listing, html_by_url={
            "https://glints.com/vn/opportunities/jobs/backend-engineer/g-1": detail_html,
        })
        crawler = GlintsRawPipeline(
            max_items=5, storage_dir=str(Path(self.temp.name) / "glints"),
            minio_store=self.store, http_client=session, delay_min=0, delay_max=0,
        )
        count = crawler.discover_urls()
        self.assertEqual(count, 1)
        self.assertTrue(any(k.startswith("url_ledger/glints/manifests/manifest_") for k in self.store.objects))
        self.assertTrue(any(k.startswith("raw/glints/_listing/" ) and k.endswith("page_0001.json") for k in self.store.objects))
        stats = crawler.crawl_details()
        self.assertEqual(stats["new"], 1)
        snapshots = [k for k in self.store.objects if k.startswith("raw/glints/202") and k.endswith("_v1.json")]
        self.assertEqual(len(snapshots), 1)
        snapshot = json.loads(self.store.objects[snapshots[0]].decode("utf-8"))
        self.assertEqual(snapshot["raw"]["html"], detail_html)
        self.assertEqual(snapshot["_meta"]["status"], "NEW")

    def test_jobsgo_discovers_pagination_and_crawls_detail(self):
        page1_url = "https://jobsgo.vn/viec-lam-cong-nghe-thong-tin.html"
        page2_url = page1_url + "?page=2"
        job_url = "https://jobsgo.vn/viec-lam/backend-engineer-123456.html"
        page1 = f"""
        <html><body><main>
          <div class='job-card'><h3><a href='{job_url}'>Backend Engineer</a></h3>
          <a href='/cong-ty/company-a.html'>Công Ty Company A</a><p>20 - 30 triệu VNĐ | Hồ Chí Minh</p></div>
          <div class='pagination'><a href='{page2_url}'>2</a></div>
        </main></body></html>"""
        page2 = "<html><body><main><p>Empty second page</p></main></body></html>"
        detail = "<html><body><main><h1>Backend Engineer</h1><h2>Chi Tiết Công Việc</h2><p>Python, Docker, Kubernetes</p></main></body></html>"
        session = FakeSession(pages={
            page1_url: (200, page1), page2_url: (200, page2), job_url: (200, detail),
        })
        crawler = JobsGORawCrawler(
            max_items=5, storage_dir=str(Path(self.temp.name) / "jobsgo"),
            minio_store=self.store, http_client=session, delay_min=0, delay_max=0,
        )
        count = crawler.discover_urls()
        self.assertEqual(count, 1)
        self.assertEqual(len([c for c in session.get_calls if "cong-nghe-thong-tin" in c[0]]), 2)
        stats = crawler.crawl_details()
        self.assertEqual(stats["new"], 1)
        snapshot_keys = [k for k in self.store.objects if k.startswith("raw/jobsgo/202") and k.endswith("_v1.json")]
        self.assertEqual(len(snapshot_keys), 1)
        snapshot = json.loads(self.store.objects[snapshot_keys[0]].decode("utf-8"))
        self.assertEqual(snapshot["raw"]["html"], detail)


    def _make_glints_crawler(self, listing, html_by_url, suffix="cdc"):
        session = FakeSession(listing_body=listing, html_by_url=html_by_url)
        crawler = GlintsRawPipeline(
            max_items=10, storage_dir=str(Path(self.temp.name) / f"glints-{suffix}"),
            minio_store=self.store, http_client=session, delay_min=0, delay_max=0,
        )
        return crawler, session

    @staticmethod
    def _make_listing(*jobs):
        return {"data": {"searchJobsV3": {"jobsInPage": list(jobs), "hasMore": False}}}

    def test_changed_detail_creates_next_version(self):
        from crawlers.sources.glints.crawler import slugify
        job = {"id": "g-version", "title": "Platform Engineer", "company": {"name": "Acme"}}
        url = f"https://glints.com/vn/opportunities/jobs/{slugify(job['title'])}/{job['id']}"
        first_html = "<html><body><main><h1>Platform Engineer</h1><p>Python APIs</p></main></body></html>"
        second_html = "<html><body><main><h1>Platform Engineer</h1><p>Python APIs and distributed systems</p></main></body></html>"
        crawler, session = self._make_glints_crawler(self._make_listing(job), {url: first_html}, "version")
        crawler.discover_urls()
        first_stats = crawler.crawl_details()
        self.assertEqual(first_stats["new"], 1)
        row = next(iter(crawler.ledger.records.values()))
        row["last_scraped_at"] = (datetime.now(timezone.utc) - timedelta(days=22)).isoformat()
        row["status"] = "DONE"
        crawler._persist_catalog(include_parquet=False)
        session.html_by_url[url] = second_html
        second_stats = crawler.crawl_details()
        self.assertEqual(second_stats["updated"], 1)
        versions = sorted(k for k in self.store.objects if k.startswith("raw/glints/202") and k.endswith(("_v1.json", "_v2.json")))
        self.assertTrue(any(k.endswith("_v1.json") for k in versions))
        self.assertTrue(any(k.endswith("_v2.json") for k in versions))

    def test_unchanged_detail_does_not_create_duplicate_snapshot(self):
        from crawlers.sources.glints.crawler import slugify
        job = {"id": "g-unchanged", "title": "QA Engineer", "company": {"name": "Acme"}}
        url = f"https://glints.com/vn/opportunities/jobs/{slugify(job['title'])}/{job['id']}"
        html = "<html><body><main><h1>QA Engineer</h1><p>Automation tests</p></main></body></html>"
        crawler, _ = self._make_glints_crawler(self._make_listing(job), {url: html}, "unchanged")
        crawler.discover_urls()
        crawler.crawl_details()
        row = next(iter(crawler.ledger.records.values()))
        row["last_scraped_at"] = (datetime.now(timezone.utc) - timedelta(days=22)).isoformat()
        row["status"] = "DONE"
        crawler._persist_catalog(include_parquet=False)
        stats = crawler.crawl_details()
        self.assertEqual(stats["unchanged"], 1)
        snapshots = [k for k in self.store.objects if k.startswith("raw/glints/202") and k.endswith("_v1.json") and "g-unchanged" in k]
        self.assertEqual(len(snapshots), 1)
        self.assertFalse(any(k.startswith("raw/glints/202") and k.endswith("_v2.json") and "g-unchanged" in k for k in self.store.objects))

    def test_same_content_under_new_url_is_linked_as_repost(self):
        from crawlers.sources.glints.crawler import slugify
        jobs = [
            {"id": "g-repost-1", "title": "Backend Engineer", "company": {"name": "Acme"}},
            {"id": "g-repost-2", "title": "Backend Engineer", "company": {"name": "Acme"}},
        ]
        html = "<html><body><main><h1>Backend Engineer</h1><p>Build backend services</p></main></body></html>"
        html_by_url = {f"https://glints.com/vn/opportunities/jobs/{slugify(j['title'])}/{j['id']}": html for j in jobs}
        crawler, _ = self._make_glints_crawler(self._make_listing(*jobs), html_by_url, "repost")
        crawler.discover_urls()
        stats = crawler.crawl_details()
        self.assertEqual(stats["new"], 1)
        self.assertEqual(stats["reposts"], 1)
        records = list(crawler.ledger.records.values())
        repost_rows = [r for r in records if r.get("repost_of_url_hash")]
        self.assertEqual(len(repost_rows), 1)
        self.assertEqual(repost_rows[0]["latest_version"], 0)

    def test_failed_url_does_not_stop_next_url(self):
        listing = {
            "data": {"searchJobsV3": {
                "jobsInPage": [
                    {"id": "g-1", "title": "Job One", "company": {"name": "A"}},
                    {"id": "g-2", "title": "Job Two", "company": {"name": "B"}},
                ], "hasMore": False,
            }}
        }
        from crawlers.sources.glints.crawler import slugify
        urls = {
            f"https://glints.com/vn/opportunities/jobs/{slugify(title)}/{job_id}": html
            for title, job_id, html in [
                ("Job One", "g-1", ""),
                ("Job Two", "g-2", "<html><body><main><h1>Job Two details</h1></main></body></html>"),
            ]
        }
        session = FakeSession(listing_body=listing, html_by_url=urls)
        # Simulate the first detail request returning HTTP 500 and the second working.
        original_get = session.get
        def get(url, **kwargs):
            if url.endswith("/g-1"):
                session.get_calls.append((url, kwargs))
                return FakeResponse(status_code=500, text="server error", url=url)
            return original_get(url, **kwargs)
        session.get = get
        crawler = GlintsRawPipeline(
            max_items=5, storage_dir=str(Path(self.temp.name) / "glints-errors"),
            minio_store=self.store, http_client=session, delay_min=0, delay_max=0,
        )
        crawler.discover_urls()
        stats = crawler.crawl_details()
        self.assertEqual(stats["failed"], 1)
        self.assertEqual(stats["new"], 1)


if __name__ == "__main__":
    unittest.main()
