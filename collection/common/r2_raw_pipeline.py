"""Cloudflare R2 Raw Pipeline Primitives.

Re-exports raw store and decoupled crawler classes configured for Cloudflare R2.
"""

from __future__ import annotations

from collection.common.minio_raw_pipeline import (
    MinioRawStore,
    TwoPhaseDecoupledCrawler,
    combined_content_hash,
    stable_html_hash,
    choose_container_selector,
    safe_object_part,
    utc_date,
    utc_now,
)

R2RawStore = MinioRawStore

__all__ = [
    "R2RawStore",
    "MinioRawStore",
    "TwoPhaseDecoupledCrawler",
    "combined_content_hash",
    "stable_html_hash",
    "choose_container_selector",
    "safe_object_part",
    "utc_date",
    "utc_now",
]
