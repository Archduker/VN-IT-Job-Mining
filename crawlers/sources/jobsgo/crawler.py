# -*- coding: utf-8 -*-
"""JobsGO Vietnam raw-first crawler (SSR HTML listing/detail pages)."""
from __future__ import annotations

import base64
import logging
import re
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from crawlers.common.minio_raw_pipeline import TwoPhaseRawCrawler, safe_object_part
from crawlers.common.url_ledger import clean_canonical_url

logger = logging.getLogger(__name__)

SOURCE = "jobsgo"
LISTING_URL = "https://jobsgo.vn/viec-lam-cong-nghe-thong-tin.html"
JOB_PATH_RE = re.compile(r"^/viec-lam/[^/]+-([0-9]+)\.html$", re.IGNORECASE)


class JobsGORawCrawler(TwoPhaseRawCrawler):
    """Two-phase JobsGO crawler preserving SSR HTML without early normalization."""

    source = SOURCE
    default_listing_url = LISTING_URL
    detail_selectors = (
        ".job-detail",
        "#job-detail",
        "main",
        "body",
    )

    def __init__(self, max_items: Optional[int] = 30, http_client: Any = None, listing_url: str = LISTING_URL, **kwargs: Any) -> None:
        super().__init__(max_items=max_items, http_client=http_client or requests.Session(), **kwargs)
        self.listing_url = listing_url
        self.http_client.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "identity",
            "Referer": "https://jobsgo.vn/",
        })

    @staticmethod
    def _job_id(url: str) -> str:
        match = JOB_PATH_RE.match(urlparse(url).path)
        return match.group(1) if match else __import__("hashlib").md5(url.encode("utf-8")).hexdigest()[:12]

    @staticmethod
    def _is_job_url(href: str) -> bool:
        parsed = urlparse(href)
        return parsed.netloc.lower() in {"jobsgo.vn", "www.jobsgo.vn"} and bool(JOB_PATH_RE.match(parsed.path))

    @staticmethod
    def _listing_page_links(html: str, base_url: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        base_path = urlparse(base_url).path
        links: list[str] = []
        for anchor in soup.select("a[href]"):
            text = anchor.get_text(" ", strip=True)
            href = urljoin(base_url, anchor.get("href", ""))
            parsed = urlparse(href)
            if parsed.netloc.lower() not in {"jobsgo.vn", "www.jobsgo.vn"}:
                continue
            # JobsGO's pagination uses links on the same category route, with a
            # page parameter or a pagination container. Do not follow all SEO links.
            inside_pagination = bool(anchor.find_parent(class_=re.compile("pagination|paging|page-list", re.I)))
            same_route = parsed.path == base_path
            has_page_param = any(k.lower() in {"page", "p", "trang"} for k in parse_qs(parsed.query))
            is_number = text.isdigit() or text in {"«", "»", "‹", "›", "Previous", "Next", "Trước", "Sau"}
            if same_route and (inside_pagination or has_page_param or (is_number and parsed.query)):
                clean = clean_canonical_url(href)
                if clean != clean_canonical_url(base_url) and clean not in links:
                    links.append(clean)
        return links

    @staticmethod
    def _card_for_anchor(anchor) -> Any:
        node = anchor
        for _ in range(6):
            node = getattr(node, "parent", None)
            if node is None:
                break
            classes = " ".join(node.get("class", [])) if getattr(node, "get", None) else ""
            text = node.get_text(" ", strip=True) if getattr(node, "get_text", None) else ""
            if len(text) > 25 and (re.search(r"job|viec|item|card|result", classes, re.I) or re.search(r"triệu|thỏa thuận|thoả thuận|full.time|kinh nghiệm", text, re.I)):
                return node
        return anchor.parent or anchor

    @staticmethod
    def _extract_card_payload(anchor, canonical_url: str) -> Tuple[str, str, Dict[str, Any]]:
        title = anchor.get_text(" ", strip=True)
        card = JobsGORawCrawler._card_for_anchor(anchor)
        card_text = card.get_text("\n", strip=True) if getattr(card, "get_text", None) else title
        company = ""
        for candidate in card.select("a[href]") if getattr(card, "select", None) else []:
            candidate_text = candidate.get_text(" ", strip=True)
            candidate_url = candidate.get("href", "")
            if candidate is not anchor and candidate_text and (
                "cong-ty" in candidate_url.lower() or "company" in candidate_url.lower()
                or candidate_text.lower().startswith(("công ty", "cty", "company"))
            ):
                company = candidate_text
                break
        if not company:
            lines = [x.strip() for x in card_text.splitlines() if x.strip()]
            company = next((x for x in lines if x.lower().startswith(("công ty", "cty", "company"))), "")
        payload = {
            "title": title,
            "company": company,
            "card_text": card_text,
            "raw_anchor_html": str(anchor),
            "raw_card_html": str(card),
            "canonical_url": canonical_url,
        }
        return title, company, payload

    def discover_urls(self, max_pages: Optional[int] = None) -> int:
        queue = [clean_canonical_url(self.listing_url)]
        visited_pages: set[str] = set()
        seen_jobs: set[str] = set()
        self._discovered_hashes.clear()
        self._manifest_entries.clear()
        full_scan = True
        page_count = 0
        reported_total = None
        last_range_end = None

        failed_pages: list[tuple[str, str]] = []
        while queue and (max_pages is None or page_count < max_pages):
            page_url = queue.pop(0)
            if page_url in visited_pages:
                continue
            visited_pages.add(page_url)
            page_count += 1
            try:
                self._sleep()
                response = self.http_client.get(page_url, timeout=25, headers={"Accept-Encoding": "identity"})
                status = int(getattr(response, "status_code", 0))
                if status != 200:
                    raise RuntimeError(f"HTTP {status}")
                html = response.text
                if isinstance(html, bytes):
                    html = html.decode("utf-8", errors="replace")
                if not isinstance(html, str) or not html:
                    raise RuntimeError("Empty listing HTML")
            except Exception as exc:
                logger.exception("JobsGO listing page failed: %s", page_url)
                failed_pages.append((page_url, str(exc)))
                full_scan = False
                continue

            page_key = f"raw/jobsgo/_listing/{self._run_date}/page_{page_count:04d}.html"
            self.store.put_text(page_key, html, "text/html; charset=utf-8")
            raw_body = getattr(response, "content", None)
            if isinstance(raw_body, (bytes, bytearray)):
                # Save the exact response body bytes alongside decoded HTML.
                self.store.put_text(
                    page_key + ".body_base64.txt",
                    base64.b64encode(raw_body).decode("ascii"),
                    "text/plain; charset=us-ascii",
                )
            soup = BeautifulSoup(html, "html.parser")
            visible_listing_text = soup.get_text(" ", strip=True)
            count_match = re.search(r"Việc\s+(\d+)\s*[-–]\s*(\d+)\s*/\s*([\d.,]+)", visible_listing_text, re.IGNORECASE)
            if count_match:
                last_range_end = int(count_match.group(2))
                try:
                    reported_total = int(count_match.group(3).replace(".", "").replace(",", ""))
                except ValueError:
                    pass
            page_jobs = 0
            for anchor in soup.select("a[href]"):
                absolute = clean_canonical_url(urljoin(page_url, anchor.get("href", "")))
                if not self._is_job_url(absolute):
                    continue
                job_id = self._job_id(absolute)
                if job_id in seen_jobs:
                    continue
                title, company, payload = self._extract_card_payload(anchor, absolute)
                if not title:
                    continue
                seen_jobs.add(job_id)
                self.register_discovered(absolute, job_id, title, company, payload, page_key=page_key)
                page_jobs += 1
            for next_url in self._listing_page_links(html, page_url):
                if next_url not in visited_pages and next_url not in queue:
                    queue.append(next_url)

        # JobsGO pagination does not expose a structured hasMore flag. Any run
        # with an explicit page limit is treated as partial to avoid false CLOSED.
        if max_pages is not None and page_count >= max_pages:
            full_scan = False
        # If page metadata says more results exist but pagination links were not
        # discovered, do not call this a complete scan or increment absence counts.
        if reported_total is not None and last_range_end is not None and last_range_end < reported_total and not queue and max_pages is None:
            full_scan = False
            logger.warning("JobsGO listing reports %s results but pagination ended at %s; no CLOSED decisions this run.", reported_total, last_range_end)
        if failed_pages and not seen_jobs:
            self._finish_discovery(full_scan=False)
            failed_url, reason = failed_pages[0]
            raise RuntimeError(
                "JobsGO discovery failed: "
                f"{len(failed_pages)} listing page(s) failed, "
                "0 job URLs discovered. "
                f"First URL: {failed_url}; reason: {reason}"
            )

        self._finish_discovery(full_scan=full_scan)
        logger.info("JobsGO discovery: %d unique job URLs; pages=%d; full_scan=%s", len(seen_jobs), page_count, full_scan)
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
