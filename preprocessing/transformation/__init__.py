# -*- coding: utf-8 -*-
"""preprocessing.transformation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Module chuyển hóa dữ liệu, bóc tách dải lương, làm sạch HTML và tính toán chỉ số văn bản.
"""

from preprocessing.transformation.bullet_stitcher import stitch_fragmented_bullets
from preprocessing.transformation.html_cleaner import strip_html_tags
from preprocessing.transformation.record_transformer import (
    coerce_number,
    extract_raw_salary_bounds,
    is_empty_stub_record,
    normalize_employment_type,
    normalize_work_mode,
    parse_date_to_iso,
    to_flat_record,
    transform_job_record,
)
from preprocessing.transformation.salary_parser import UniversalSalaryParser, parse_salary_cascade
from preprocessing.transformation.text_metrics import (
    calculate_text_metrics,
    detect_language,
    filter_valid_clean_records,
    standardize_to_vietnamese,
)

__all__ = [
    "parse_salary_cascade",
    "UniversalSalaryParser",
    "strip_html_tags",
    "stitch_fragmented_bullets",
    "coerce_number",
    "normalize_employment_type",
    "normalize_work_mode",
    "parse_date_to_iso",
    "transform_job_record",
    "extract_raw_salary_bounds",
    "is_empty_stub_record",
    "to_flat_record",
    "calculate_text_metrics",
    "detect_language",
    "standardize_to_vietnamese",
    "filter_valid_clean_records",
]
