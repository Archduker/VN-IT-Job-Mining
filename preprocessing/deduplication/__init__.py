"""Deduplication and record-linkage utilities for VN-IT-Job-Mining."""

from preprocessing.deduplication.record_linkage import (
    LinkageConfig,
    jaro_winkler_similarity,
    link_duplicate_records,
    normalize_company_name,
    render_deduplication_report,
)
from preprocessing.deduplication.golden_record_resolver import resolve_golden_records

__all__ = [
    "LinkageConfig",
    "jaro_winkler_similarity",
    "link_duplicate_records",
    "normalize_company_name",
    "render_deduplication_report",
    "resolve_golden_records",
]
