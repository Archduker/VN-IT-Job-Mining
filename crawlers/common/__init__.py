"""
crawlers.common
~~~~~~~~~~~~~~~
Shared modules dùng chung cho tất cả crawlers.

Exports:
    schema      — Pydantic models: JobMetadata, JobRaw, JobRecord
    http_client — HttpClient với retry + delay + User-Agent rotation
    logger      — Structured logging setup
    utils       — URL normalize, hash, slug helpers
"""

from crawlers.common.schema import JobMetadata, JobRaw, JobRecord
from crawlers.common.http_client import HttpClient
from crawlers.common.logger import get_logger
from crawlers.common import utils

__all__ = [
    "JobMetadata",
    "JobRaw",
    "JobRecord",
    "HttpClient",
    "get_logger",
    "utils",
]
