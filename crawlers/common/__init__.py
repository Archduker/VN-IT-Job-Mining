"""
crawlers.common
~~~~~~~~~~~~~~~
Shared modules dùng chung cho tất cả crawlers.

Exports:
    schema      — Pydantic models: JobMetadata, JobRaw, JobRecord
    http_client — HttpClient với retry + delay + User-Agent rotation
    logger      — Structured logging setup
    utils       — URL normalize, hash, slug helpers
    url_ledger  — Quản lý URL Ledger, 2 Pha cào, Re-crawl 21 ngày & Clean Container Hash
"""

from crawlers.common.schema import JobMetadata, JobRaw, JobRecord
from crawlers.common.http_client import HttpClient
from crawlers.common.logger import get_logger
from crawlers.common import utils
from crawlers.common.url_ledger import (
    UrlLedger,
    UrlLedgerRecord,
    clean_canonical_url,
    generate_url_hash,
    generate_identity_key,
    calculate_container_html_hash,
    is_due_for_recrawl,
)

__all__ = [
    "JobMetadata",
    "JobRaw",
    "JobRecord",
    "HttpClient",
    "get_logger",
    "utils",
    "UrlLedger",
    "UrlLedgerRecord",
    "clean_canonical_url",
    "generate_url_hash",
    "generate_identity_key",
    "calculate_container_html_hash",
    "is_due_for_recrawl",
]
