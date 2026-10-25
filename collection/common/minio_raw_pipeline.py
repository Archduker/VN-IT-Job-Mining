# -*- coding: utf-8 -*-
"""Shared Raw-As-Is, MinIO URL Ledger and CDC pipeline primitives.

This module deliberately stores source HTML/GraphQL payloads before any schema
normalization. It uses the project's UrlLedger for lifecycle tracking and MinIO
(S3-compatible API) as the durable state/object store.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from collection.common.url_ledger import (
    UrlLedger,
    calculate_container_html_hash,
    clean_canonical_url,
    generate_url_hash,
    is_due_for_recrawl,
)

logger = logging.getLogger(__name__)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def safe_object_part(value: Any) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "unknown")).strip("._")
    return text[:180] or "unknown"


def choose_container_selector(html: str, candidates: Sequence[str]) -> str:
    """Return the first selector present in HTML, or body as a safe fallback."""
    soup = BeautifulSoup(html or "", "html.parser")
    for selector in candidates:
        try:
            if soup.select_one(selector):
                return selector
        except Exception:
            logger.debug("Invalid selector ignored: %s", selector, exc_info=True)
    return "body"


def stable_html_hash(html: str, selectors: Sequence[str] = ("main", "body")) -> str:
    """SHA-256 of the main visible content, excluding volatile markup/text.

    The raw HTML itself is never modified; this cleaning only feeds the hash.
    Relative-time labels and view counters are removed to reduce false updates.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    target = None
    for selector in selectors:
        try:
            target = soup.select_one(selector)
        except Exception:
            target = None
        if target is not None:
            break
    target = target or soup.body or soup

    for tag in target(["script", "style", "iframe", "noscript", "svg"]):
        tag.decompose()

    text = re.sub(r"\s+", " ", target.get_text(separator=" ", strip=True))
    volatile_patterns = (
        r"\b\d+\s*(?:seconds?|minutes?|hours?|days?)\s+ago\b",
        r"\b\d+\s*(?:giây|phút|giờ|ngày)\s+trước\b",
        r"\b(?:views?|lượt xem)\s*:?\s*\d+\b",
    )
    for pattern in volatile_patterns:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def combined_content_hash(html: str, listing_payload: Optional[Dict[str, Any]], selectors: Sequence[str]) -> str:
    """Hash stable detail text plus stable listing metadata (excluding IDs/times)."""
    html_hash = stable_html_hash(html, selectors)
    if not isinstance(listing_payload, dict):
        return html_hash
    # Only stable, semantically meaningful listing fields. Keep the complete
    # listing payload in MinIO separately; this projection is used only for CDC.
    stable_keys = (
        "title", "company", "country", "location", "salaries", "skills",
        "hierarchicalJobCategory", "minYearsOfExperience", "maxYearsOfExperience",
        "type", "workArrangementOption", "educationLevel",
    )
    stable = {key: listing_payload.get(key) for key in stable_keys if key in listing_payload}
    serialized = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256((html_hash + "\n" + serialized).encode("utf-8")).hexdigest()


class MinioRawStore:
    """Small MinIO/S3 adapter. Raises on connection/auth errors; missing keys return None."""

    def __init__(
        self,
        bucket: Optional[str] = None,
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        secure: Optional[bool] = None,
        client: Any = None,
        ensure_bucket: bool = True,
    ) -> None:
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
        self.bucket = bucket or os.getenv("MINIO_BUCKET", "vn-it-jobs")
        self.endpoint = endpoint or os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
        self.access_key = access_key or os.getenv("MINIO_ROOT_USER", "minioadmin")
        self.secret_key = secret_key or os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
        secure_env = os.getenv("MINIO_SECURE", "false").strip().lower() in {"1", "true", "yes"}
        if secure is not None:
            self.secure = secure
        elif self.endpoint.startswith("https://"):
            self.secure = True
        else:
            self.secure = secure_env

        region = "auto" if "r2.cloudflarestorage.com" in self.endpoint else "us-east-1"

        if client is None:
            import boto3
            from botocore.client import Config
            self.client = boto3.client(
                "s3",
                endpoint_url=self.endpoint,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                use_ssl=self.secure,
                region_name=region,
                config=Config(signature_version="s3v4", connect_timeout=5, read_timeout=30,
                              retries={"max_attempts": 3, "mode": "standard"}),
            )
        else:
            self.client = client
        if ensure_bucket:
            self.ensure_bucket()

    @staticmethod
    def _is_missing_error(exc: Exception) -> bool:
        response = getattr(exc, "response", {}) or {}
        error = response.get("Error", {}) if isinstance(response, dict) else {}
        code = str(error.get("Code", ""))
        status = str((response.get("ResponseMetadata", {}) or {}).get("HTTPStatusCode", ""))
        return code in {"NoSuchKey", "NoSuchBucket", "404", "NotFound"} or status == "404"

    def ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
            return
        except Exception as head_exc:
            # Bucket chưa có thì tạo; nếu head bị từ chối trên một số S3-compatible
            # deployments, thử create rồi xác minh lại trước khi báo lỗi.
            try:
                self.client.create_bucket(Bucket=self.bucket)
                return
            except Exception as create_exc:
                try:
                    self.client.head_bucket(Bucket=self.bucket)
                    return  # Bucket đã tồn tại nhưng create trả AlreadyOwned/Conflict.
                except Exception:
                    raise RuntimeError(
                        f"Không kết nối/khởi tạo được MinIO bucket '{self.bucket}' tại {self.endpoint}. "
                        "Kiểm tra docker-compose.minio.yml và biến MINIO_* trong .env."
                    ) from create_exc

    def get_bytes(self, key: str) -> Optional[bytes]:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            return response["Body"].read()
        except Exception as exc:
            if self._is_missing_error(exc):
                return None
            raise

    def get_json(self, key: str) -> Optional[Any]:
        data = self.get_bytes(key)
        if data is None:
            return None
        return json.loads(data.decode("utf-8"))

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    def put_text(self, key: str, text: str, content_type: str = "text/plain; charset=utf-8") -> None:
        self.put_bytes(key, text.encode("utf-8"), content_type)

    def put_json(self, key: str, value: Any) -> None:
        payload = json.dumps(value, ensure_ascii=False, indent=2, default=str).encode("utf-8")
        self.put_bytes(key, payload, "application/json; charset=utf-8")

    def put_file(self, key: str, path: Path, content_type: str = "application/octet-stream") -> None:
        with path.open("rb") as handle:
            self.put_bytes(key, handle.read(), content_type)

    def list_keys(self, prefix: str) -> List[str]:
        paginator = self.client.get_paginator("list_objects_v2")
        results: List[str] = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for item in page.get("Contents", []) or []:
                results.append(str(item["Key"]))
        return results


class TwoPhaseRawCrawler:
    """Base for independent URL discovery and detail/CDC crawling phases."""

    source = ""
    default_listing_url = ""
    detail_selectors: Sequence[str] = ("main", "body")

    def __init__(
        self,
        max_items: Optional[int] = 30,
        storage_dir: Optional[str] = None,
        minio_store: Optional[MinioRawStore] = None,
        http_client: Any = None,
        recheck_days: int = 21,
        close_after_missing_cycles: int = 3,
        delay_min: Optional[float] = None,
        delay_max: Optional[float] = None,
    ) -> None:
        if not self.source:
            raise ValueError("source must be set on the crawler subclass")
        self.max_items = max_items
        self.recheck_days = int(os.getenv("CRAWL_RECHECK_DAYS", str(recheck_days)))
        self.close_after_missing_cycles = int(os.getenv("CRAWL_CLOSE_MISSING_CYCLES", str(close_after_missing_cycles)))
        self.storage_dir = Path(storage_dir or f"data/{self.source}/url_ledger")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.store = minio_store or MinioRawStore()
        self.http_client = http_client
        self.delay_min = float(os.getenv("CRAWL_DELAY_MIN", str(delay_min if delay_min is not None else 1.5)))
        self.delay_max = float(os.getenv("CRAWL_DELAY_MAX", str(delay_max if delay_max is not None else 3.0)))
        self._load_remote_catalog_before_ledger()
        self.ledger = UrlLedger(self.source, storage_dir=str(self.storage_dir))
        self._manifest_entries: Dict[str, Dict[str, Any]] = {}
        self._discovered_hashes: set[str] = set()
        self._run_date = utc_date()
        self._discovery_completed = False

    def _load_remote_catalog_before_ledger(self) -> None:
        """MinIO catalog is source of truth; a fresh machine pulls it before a run."""
        key = f"url_ledger/{self.source}/catalog_master.json"
        remote = self.store.get_json(key)
        if isinstance(remote, dict):
            local_path = self.storage_dir / "catalog_master.json"
            local_path.parent.mkdir(parents=True, exist_ok=True)
            temp = local_path.with_suffix(".json.tmp")
            temp.write_text(json.dumps(remote, ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(local_path)

    def _sleep(self) -> None:
        import random
        time.sleep(random.uniform(self.delay_min, max(self.delay_min, self.delay_max)))

    def _record_listing_payload(self, job_id: str, url: str, payload: Dict[str, Any], page_key: Optional[str] = None) -> None:
        safe_id = safe_object_part(job_id)
        date_prefix = f"raw/{self.source}/_listing/{self._run_date}"
        # Include capture time so re-running discovery on the same day never overwrites
        # the immutable listing payload from an earlier scan. The current/ object below
        # is only a replaceable convenience pointer.
        capture_stamp = datetime.now(timezone.utc).strftime("%H%M%S%f")
        historical_key = f"{date_prefix}/{safe_id}_{generate_url_hash(clean_canonical_url(url))}_{capture_stamp}.json"
        object_value = {
            "object_key": historical_key,
            "source": self.source,
            "source_job_id": str(job_id),
            "canonical_url": clean_canonical_url(url),
            "captured_at": utc_now(),
            "raw_listing_payload": payload,
            "source_page_object": page_key,
        }
        self.store.put_json(historical_key, object_value)
        # Current projection is a convenience pointer for Phase 2. Historical
        # listing snapshots above are immutable and remain available by date.
        self.store.put_json(f"raw/{self.source}/_listing/current/{safe_id}.json", object_value)

    def register_discovered(
        self,
        url: str,
        job_id: str,
        title: Optional[str],
        company: Optional[str],
        listing_payload: Dict[str, Any],
        page_key: Optional[str] = None,
    ) -> str:
        canonical = clean_canonical_url(url)
        record = self.ledger.register_url(
            canonical,
            str(job_id),
            preliminary_title=title or None,
            preliminary_company=company or None,
        )
        url_hash = record.url_hash
        # If an old URL becomes visible again, reopen its lifecycle instead of
        # leaving it permanently CLOSED. The previous content hash/version is kept
        # so Phase 2 can determine whether the reactivated posting actually changed.
        state = self.ledger.records.get(url_hash)
        if state and state.get("status") == "CLOSED":
            state["status"] = "PENDING"
            state["error_log"] = None
        self._discovered_hashes.add(url_hash)
        self._manifest_entries[url_hash] = dict(state) if state else record.to_dict()
        self._record_listing_payload(str(job_id), canonical, listing_payload, page_key)
        return url_hash

    def _persist_catalog(self, include_parquet: bool = False) -> None:
        """Persist JSON operational catalog atomically and optional Parquet mirror."""
        # Write through a temporary file and atomic replace; the JSON catalog is the
        # mutable source of truth used to bootstrap UrlLedger on another machine.
        catalog_path = self.ledger.catalog_file
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = catalog_path.with_suffix(catalog_path.suffix + ".tmp")
        temp_path.write_text(json.dumps(self.ledger.records, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        temp_path.replace(catalog_path)
        self.store.put_file(
            f"url_ledger/{self.source}/catalog_master.json",
            self.ledger.catalog_file,
            "application/json; charset=utf-8",
        )
        if include_parquet:
            # Parquet is a mirror for inspection/EDA; JSON remains the mutable
            # operational source of truth used to bootstrap the UrlLedger.
            # pyarrow is declared in project requirements. Missing engine is
            # non-fatal for crawling, but is logged so the environment can be fixed.
            try:
                import pandas as pd
                parquet_path = self.storage_dir / "catalog_master.parquet"
                pd.DataFrame(list(self.ledger.records.values())).to_parquet(parquet_path, index=False)
                self.store.put_file(
                    f"url_ledger/{self.source}/catalog_master.parquet",
                    parquet_path,
                    "application/vnd.apache.parquet",
                )
            except ImportError as exc:
                logger.warning(
                    "[%s] Could not refresh catalog_master.parquet (%s). Install requirements.txt/pyarrow; JSON catalog is saved.",
                    self.source, exc,
                )
            except Exception:
                logger.exception(
                    "[%s] Could not refresh catalog_master.parquet; JSON catalog is saved.",
                    self.source,
                )

    def _finish_discovery(self, full_scan: bool) -> None:
        """Write append-only daily manifest, optional K-cycle closure, and catalog."""
        manifest_key = f"url_ledger/{self.source}/manifests/manifest_{self._run_date}.jsonl"
        old_bytes = self.store.get_bytes(manifest_key) or b""
        existing_hashes: set[str] = set()
        for line in old_bytes.decode("utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
                if row.get("url_hash"):
                    existing_hashes.add(row["url_hash"])
            except json.JSONDecodeError:
                continue
        additions = []
        for url_hash, row in self._manifest_entries.items():
            if url_hash not in existing_hashes:
                additions.append(json.dumps(row, ensure_ascii=False, default=str))
        if additions:
            combined = old_bytes + (b"\n" if old_bytes and not old_bytes.endswith(b"\n") else b"")
            combined += ("\n".join(additions) + "\n").encode("utf-8")
            self.store.put_bytes(manifest_key, combined, "application/x-ndjson; charset=utf-8")

        # Track disappearance counts separately so old UrlLedgerRecord rows stay
        # backward-compatible with the dataclass schema already in the project.
        misses_key = f"url_ledger/{self.source}/discovery_miss_counts.json"
        miss_counts = self.store.get_json(misses_key) or {}
        if full_scan:
            for url_hash, row in self.ledger.records.items():
                if url_hash in self._discovered_hashes:
                    miss_counts[url_hash] = 0
                elif row.get("status") != "CLOSED":
                    miss_counts[url_hash] = int(miss_counts.get(url_hash, 0)) + 1
                    if miss_counts[url_hash] >= self.close_after_missing_cycles:
                        row["status"] = "CLOSED"
                        logger.info("[%s] Marked CLOSED after repeated absence: %s", self.source, row.get("canonical_url"))
            self.store.put_json(misses_key, miss_counts)

        self._persist_catalog(include_parquet=True)

    def discover_urls(self, max_pages: Optional[int] = None) -> int:
        raise NotImplementedError

    def fetch_detail(self, url: str) -> Dict[str, Any]:
        raise NotImplementedError

    def crawl_details(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """Crawl only pending, due, or retryable URLs, persisting every snapshot to MinIO."""
        limit = self.max_items if limit is None else limit
        pending = self.ledger.get_pending_or_due_records(recheck_days=self.recheck_days)
        for row in self.ledger.records.values():
            if row.get("status") == "FAILED" and int(row.get("retry_count", 0)) < 5 and row not in pending:
                pending.append(row)

        pending.sort(key=lambda row: (0 if row.get("status") == "PENDING" else 1, row.get("discovered_at") or ""))
        if limit is not None:
            pending = pending[:max(0, int(limit))]

        stats = {"source": self.source, "attempted": 0, "new": 0, "updated": 0,
                 "unchanged": 0, "reposts": 0, "closed": 0, "failed": 0, "skipped": 0}
        for row in pending:
            url_hash = row.get("url_hash", "")
            url = row.get("canonical_url", "")
            job_id = str(row.get("job_id", "unknown"))
            stats["attempted"] += 1
            try:
                result = self.fetch_detail(url)
                status_code = int(result.get("status_code", 0) or 0)
                if status_code in (404, 410):
                    self.ledger.mark_closed(url_hash)
                    stats["closed"] += 1
                    continue
                if status_code != 200:
                    raise RuntimeError(f"HTTP {status_code} khi tải {url}")
                html = result.get("html")
                if not isinstance(html, str) or not html.strip():
                    raise RuntimeError("Response HTML rỗng")

                safe_id = safe_object_part(job_id)
                listing_obj = self.store.get_json(f"raw/{self.source}/_listing/current/{safe_id}.json") or {}
                listing_payload = listing_obj.get("raw_listing_payload") if isinstance(listing_obj, dict) else None
                content_hash = combined_content_hash(html, listing_payload, self.detail_selectors)
                old_hash = row.get("content_hash")
                old_version = int(row.get("latest_version") or 0)

                if old_hash and old_hash == content_hash:
                    self.ledger.mark_done(url_hash, content_hash, new_version=old_version)
                    stats["unchanged"] += 1
                    continue

                repost = self.ledger.find_by_content_hash(content_hash)
                if repost and repost.get("url_hash") != url_hash:
                    self.ledger.mark_done(
                        url_hash,
                        content_hash,
                        new_version=old_version,
                        repost_of_url_hash=repost.get("url_hash"),
                    )
                    stats["reposts"] += 1
                    continue

                new_version = old_version + 1
                state = "NEW" if old_version == 0 else "UPDATED"
                snapshot = {
                    "_meta": {
                        "source": self.source,
                        "source_job_id": job_id,
                        "url": url,
                        "url_hash": url_hash,
                        "content_hash": content_hash,
                        "version": new_version,
                        "status": state,
                        "first_seen_at": row.get("first_seen_at") or row.get("discovered_at"),
                        "scraped_at": utc_now(),
                        "crawler_version": "0.3.0",
                        "http_status": status_code,
                        "final_url": result.get("final_url") or url,
                        "container_selector_for_hash": choose_container_selector(html, self.detail_selectors),
                    },
                    "raw": {
                        # Full unmodified response body. Parsing/normalization occurs later.
                        "html": html,
                        # Base64 preserves response body bytes for byte-exact replay when
                        # the HTTP library exposes them. The decoded HTML is kept as well
                        # for human inspection and stable-content hashing.
                        "body_bytes_base64": result.get("body_bytes_base64"),
                        "response_encoding": result.get("response_encoding"),
                        "listing_payload": listing_payload,
                        "listing_object_key": listing_obj.get("object_key"),
                        "response_content_type": result.get("content_type"),
                    },
                }
                object_key = f"raw/{self.source}/{utc_date()}/{safe_id}_v{new_version}.json"
                self.store.put_json(object_key, snapshot)
                self.ledger.mark_done(url_hash, content_hash, new_version=new_version)
                stats["new" if state == "NEW" else "updated"] += 1
            except Exception as exc:
                logger.exception("[%s] Failed URL; continue with next: %s", self.source, url)
                self.ledger.mark_failed(url_hash, str(exc))
                stats["failed"] += 1
            finally:
                # Persist after each URL to avoid losing progress after interruption.
                self._persist_catalog(include_parquet=False)
        # Refresh Parquet once per invocation instead of rewriting it for every URL.
        self._persist_catalog(include_parquet=True)
        stats["crawled"] = stats["new"] + stats["updated"]
        stats["skipped"] = stats["unchanged"] + stats["reposts"]
        stats["errors"] = stats["failed"]
        stats["total_seen"] = len(self.ledger.records)
        bucket = getattr(self.store, "bucket", os.getenv("MINIO_BUCKET", "vn-it-jobs"))
        stats["output_file"] = f"minio://{bucket}/raw/{self.source}/"
        return stats
