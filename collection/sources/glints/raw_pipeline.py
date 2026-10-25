# -*- coding: utf-8 -*-
"""Glints two-phase raw crawler: GraphQL discovery -> MinIO -> HTML/CDC."""
from __future__ import annotations

import os
import json
import base64
import logging
import random
import re
import time
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import requests

from collection.common.minio_raw_pipeline import TwoPhaseRawCrawler
from collection.common.url_ledger import clean_canonical_url
from collection.sources.glints.crawler import (
    GRAPHQL_ENDPOINT,
    LISTING_URL,
    PAGE_SIZE,
    SEARCH_QUERY,
    IT_CATEGORY_IDS,
    is_it_job,
    slugify,
)

logger = logging.getLogger(__name__)

class _BrowserResponse:
    """Adapter để response từ Playwright tương thích với cách đọc response hiện tại."""

    def __init__(self, result):
        self.status_code = int(result["status"])
        self.status = self.status_code
        self.text = str(result.get("text") or "")
        self.content = self.text.encode("utf-8")
        self.headers = {
            str(key).lower(): str(value)
            for key, value in (result.get("headers") or {}).items()
        }

    def json(self):
        return json.loads(self.text)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

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
    def _get_glints_browser_page(self):
        """Mở trang danh mục Glints trong browser context."""
        if getattr(self, "_glints_page", None) is not None:
            return self._glints_page

        from playwright.sync_api import sync_playwright

        self._glints_playwright = sync_playwright().start()
        self._glints_browser = self._glints_playwright.chromium.launch(
            headless=False
        )
        self._glints_context = self._glints_browser.new_context(
            locale="vi-VN"
        )
        self._glints_page = self._glints_context.new_page()

        self._glints_page.goto(
            LISTING_URL,
            wait_until="domcontentloaded",
            timeout=60000,
        )
        self._glints_page.wait_for_timeout(5000)

        return self._glints_page

    def _post_glints_graphql_in_browser(self, payload):
        """Gửi request GraphQL trong ngữ cảnh trang Glints."""
        page = self._get_glints_browser_page()

        result = page.evaluate(
            """
            async ({endpoint, payload}) => {
                const response = await fetch(endpoint, {
                    method: "POST",
                    credentials: "include",
                    headers: {
                        "Accept": "application/json, text/plain, */*",
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify(payload)
                });

                return {
                    status: response.status,
                    text: await response.text(),
                    headers: Object.fromEntries(response.headers.entries())
                };
            }
            """,
            {
                "endpoint": GRAPHQL_ENDPOINT,
                "payload": payload,
            },
        )

        return _BrowserResponse(result)

    def _close_glints_browser(self):
        """Đóng browser sau lượt Discover."""
        browser = getattr(self, "_glints_browser", None)
        playwright = getattr(self, "_glints_playwright", None)

        try:
            if browser is not None:
                browser.close()
        finally:
            if playwright is not None:
                playwright.stop()

            self._glints_page = None
            self._glints_context = None
            self._glints_browser = None
            self._glints_playwright = None


    def _post_glints_discovery_request(self, payload):
        """Gửi GraphQL và chuẩn hóa tuple từ test double thành Response."""
        use_browser = (
            os.getenv("GLINTS_BROWSER_DISCOVERY", "")
            .strip()
            .lower()
            in {"1", "true", "yes"}
        )

        if use_browser:
            return self._post_glints_graphql_in_browser(payload)

        response = self.http_client.post(
            GRAPHQL_ENDPOINT,
            json=payload,
            timeout=25,
            headers={
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json",
                "Origin": "https://glints.com",
                "Referer": LISTING_URL,
                "Accept-Encoding": "identity",
            },
        )

        # Một số mock trong unit test trả về (status_code, body).
        if isinstance(response, tuple):
            if len(response) < 2:
                raise TypeError(
                    "HTTP client tuple must contain status and response body"
                )

            status_code = response[0]
            body = response[1]
            headers = {}

            if len(response) >= 3 and isinstance(response[2], dict):
                headers = response[2]

            if hasattr(body, "json") and hasattr(body, "status_code"):
                return body

            if isinstance(body, bytes):
                text = body.decode("utf-8", errors="replace")
            elif isinstance(body, str):
                text = body
            else:
                text = json.dumps(body, ensure_ascii=False)

            return _BrowserResponse({
                "status": status_code,
                "text": text,
                "headers": headers,
            })

        # Response thật của requests được giữ nguyên.
        return response


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
        skipped_out_of_scope = 0
        full_scan = False
        scan_error: Optional[str] = None
        self._discovered_hashes.clear()
        self._manifest_entries.clear()

        while max_pages is None or page <= max_pages:
            self._sleep()
            payload = {
                    "operationName": "searchJobsV3",
                    "variables": {
                    "data": {
                        "CountryCode": "VN",
                        "HierarchicalJobCategoryIds": list(IT_CATEGORY_IDS),
                        "includeExternalJobs": True,
                        "pageSize": PAGE_SIZE,
                        "page": page,
                    }
                },
                "query": SEARCH_QUERY,
            }
            response = None
            logger.info(
                "Glints outgoing variables.data=%r",
                payload.get("variables", {}).get("data", {}),
            )

            try:
                response = self._post_glints_discovery_request(payload)
                status = int(getattr(response, "status_code", 200))
                if status != 200:
                    try:
                        error_detail = response.json()
                    except ValueError:
                        error_detail = response.text

                    logger.error(
                        "Glints GraphQL HTTP %s; response body: %s",
                        status,
                        str(error_detail)[:2000],
                    )
                    if status == 403:
                        logger.warning(
                            "Glints page %s requires login (HTTP 403). "
                            "Preserving partial discoveries; scan is incomplete.",
                            page,
                        )
                        raise RuntimeError(
                            f"HTTP 403 on page {page}: login required; discovery incomplete"
                        )
                body = response.json()
                if not isinstance(body, dict) or body.get("errors"):
                    raise RuntimeError(f"GraphQL response invalid/errors: {body.get('errors') if isinstance(body, dict) else type(body)}")
            except Exception as exc:
                scan_error = f"page {page}: {exc}"
                logger.exception("Glints discovery failed at page %d; not marking scan complete", page)
                # Preserve a failed response when available, without logging request secrets.
                try:
                    failed_response = response
                    if failed_response is not None:
                        failed_key = f"raw/glints/_listing_failures/{self._run_date}/page_{page:04d}.json"
                        self.store.put_json(failed_key, {
                            "source": self.source, "page": page, "url": GRAPHQL_ENDPOINT,
                            "captured_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                            "http_status": int(getattr(failed_response, "status_code", 0) or 0),
                            "error": str(exc),
                            "response_text": str(getattr(failed_response, "text", ""))[:100000],
                        })
                except Exception:
                    logger.debug("Could not archive failed Glints listing response", exc_info=True)
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
                scan_error = f"page {page}: unexpected GraphQL response shape"
                logger.error(
                    "Glints discovery got an unexpected GraphQL shape on page %d; "
                    "not marking the scan complete.", page
                )
                break
            jobs = result.get("jobsInPage") or []

            logger.info(
                "Glints API page=%s; returned=%s; hasMore=%s; "
                "requested_category_ids=%s",
                page,
                len(jobs),
                result.get("hasMore"),
                list(IT_CATEGORY_IDS),
            )

            for debug_job in jobs[:10]:
                category = debug_job.get("hierarchicalJobCategory") or {}
                parents = category.get("parents") or []
                skills = [
                    (entry.get("skill") or {}).get("name")
                    for entry in (debug_job.get("skills") or [])
                    if isinstance(entry, dict)
                ]

                logger.info(
                    "Glints API item: id=%s title=%r category_id=%r "
                    "category=%r parents=%r skills=%r",
                    debug_job.get("id"),
                    debug_job.get("title"),
                    category.get("id"),
                    category.get("name"),
                    [parent.get("name") for parent in parents],
                   skills[:8],
                )

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

                if not is_it_job(job):
                    skipped_out_of_scope += 1
                    logger.debug(
                    "Glints skipped out-of-scope job: id=%s title=%r",
                    job_id,
                    title,
                    )
                    continue

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

        # Tam tat auto-close trong giai doan chuyen catalog sang pham vi IT.
        # Catalog cu van co the chua tin ngoai pham vi.
        closure_scan_safe = False
        self._close_glints_browser()
        self._finish_discovery(full_scan=closure_scan_safe)

        logger.info(
            "Glints discovery: %d URLs registered; "
            "skipped_out_of_scope=%d; graphql_full_scan=%s; "
            "closure_scan_safe=%s",
            len(self._discovered_hashes),
            skipped_out_of_scope,
            full_scan,
            closure_scan_safe,
        )
        if scan_error:
            raise RuntimeError(
                f"Glints discovery incomplete after {len(self._discovered_hashes)} URL(s): {scan_error}"
            )
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
