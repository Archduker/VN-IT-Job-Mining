# -*- coding: utf-8 -*-
"""Glints two-phase raw crawler: GraphQL discovery -> MinIO -> HTML/CDC."""
from __future__ import annotations

import base64
import logging
import random
import re
import time
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import requests

from crawlers.common.minio_raw_pipeline import TwoPhaseRawCrawler
from crawlers.common.url_ledger import clean_canonical_url
from crawlers.sources.glints.crawler import (
    GRAPHQL_ENDPOINT,
    LISTING_URL,
    PAGE_SIZE,
    SEARCH_QUERY,
    slugify,
)

logger = logging.getLogger(__name__)


class GlintsRawPipeline(TwoPhaseRawCrawler):
    """Raw-first pipeline for Glints. Does not convert or drop source fields."""

    source = "glints"
    default_listing_url = LISTING_URL
    detail_selectors = (
        ".job-detail",
        "[data-testid*='job-detail']",
        "main",
        "body",
    )

    def __init__(self, max_items: Optional[int] = 30, http_client: Any = None, **kwargs: Any) -> None:
        super().__init__(max_items=max_items, http_client=http_client or requests.Session(), **kwargs)
        self.http_client.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129 Safari/537.36",
            "Accept": "application/json, text/html, */*",
            "Content-Type": "application/json",
            "Origin": "https://glints.com",
            "Referer": LISTING_URL,
            "Accept-Encoding": "identity",
        })

    @staticmethod
    def _job_url(job: Dict[str, Any]) -> str:
        job_id = str(job.get("id", "")).strip()
        title = str(job.get("title", "")).strip()
        return f"https://glints.com/vn/opportunities/jobs/{slugify(title)}/{job_id}"

    def discover_urls(self, max_pages: Optional[int] = None) -> int:
        page = 1
        seen_ids: set[str] = set()
        new_discovered = 0
        full_scan = False
        self._discovered_hashes.clear()
        self._manifest_entries.clear()

        while max_pages is None or page <= max_pages:
            self._sleep()
            payload = {
                "operationName": "searchJobsV3",
                "variables": {
                    "data": {
                        "CountryCode": "VN",
                        "includeExternalJobs": True,
                        "pageSize": PAGE_SIZE,
                        "page": page,
                    }
                },
                "query": SEARCH_QUERY,
            }
            try:
                response = self.http_client.post(
                    GRAPHQL_ENDPOINT,
                    json=payload,
                    timeout=25,
                )
                body = response.json()
                status = int(getattr(response, "status_code", 200))
                if status != 200:
                    raise RuntimeError(f"HTTP {status}")
                if not isinstance(body, dict) or body.get("errors"):
                    raise RuntimeError(f"GraphQL response invalid/errors: {body.get('errors') if isinstance(body, dict) else type(body)}")
            except Exception:
                logger.exception("Glints discovery failed at page %d; not marking scan complete", page)
                break

            page_key = f"raw/glints/_listing/{self._run_date}/page_{page:04d}.json"
            self.store.put_json(page_key, {
                "source": self.source,
                "captured_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                "request": {"url": GRAPHQL_ENDPOINT, "operationName": payload["operationName"], "variables": payload["variables"], "query": SEARCH_QUERY},
                "http_status": status,
                "response_encoding": getattr(response, "encoding", None),
                "raw_response_body_base64": (
                    base64.b64encode(response.content).decode("ascii")
                    if isinstance(getattr(response, "content", None), (bytes, bytearray))
                    else None
                ),
                "raw_response": body,
            })

            result = (body.get("data") or {}).get("searchJobsV3")
            if (
                not isinstance(result, dict)
                or not isinstance(result.get("jobsInPage"), list)
                or "hasMore" not in result
            ):
                logger.error(
                    "Glints discovery got an unexpected GraphQL shape on page %d; "
                    "not marking the scan complete.", page
                )
                break
            jobs = result["jobsInPage"]
            if not jobs:
                full_scan = not bool(result.get("hasMore"))
                break
            for job in jobs:
                if not isinstance(job, dict):
                    continue
                job_id = str(job.get("id") or "").strip()
                title = str(job.get("title") or "").strip()
                if not job_id or not title or job_id in seen_ids:
                    continue
                seen_ids.add(job_id)
                url = clean_canonical_url(self._job_url(job))
                before = len(self._manifest_entries)
                self.register_discovered(
                    url=url,
                    job_id=job_id,
                    title=title,
                    company=(job.get("company") or {}).get("brandName") or (job.get("company") or {}).get("name"),
                    listing_payload=job,
                    page_key=page_key,
                )
                if len(self._manifest_entries) > before:
                    new_discovered += 1

            has_more = bool(result.get("hasMore"))
            if not has_more:
                full_scan = True
                break
            page += 1

        self._finish_discovery(full_scan=full_scan)
        logger.info("Glints discovery: %d unique URLs seen; full_scan=%s", len(self._discovered_hashes), full_scan)
        return len(self._discovered_hashes)

    def fetch_detail(self, url: str) -> Dict[str, Any]:
        self._sleep()
        response = self.http_client.get(url, timeout=25, headers={"Accept-Encoding": "identity"})
        body = response.text
        if isinstance(body, bytes):
            body = body.decode("utf-8", errors="replace")
        return {
            "status_code": int(getattr(response, "status_code", 0)),
            "html": body,
            "final_url": getattr(response, "url", url),
            "content_type": getattr(response, "headers", {}).get("Content-Type"),
            "response_encoding": getattr(response, "encoding", None),
            "body_bytes_base64": (
                base64.b64encode(response.content).decode("ascii")
                if isinstance(getattr(response, "content", None), (bytes, bytearray))
                else None
            ),
        }
