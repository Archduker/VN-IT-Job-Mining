# -*- coding: utf-8 -*-
"""preprocessing.transformation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Module chuyển hóa dữ liệu, bóc tách dải lương, làm sạch HTML và tính toán chỉ số văn bản.
"""

from preprocessing.transformation.salary_parser import parse_salary_cascade, UniversalSalaryParser
from preprocessing.transformation.html_cleaner import strip_html_tags
from preprocessing.transformation.bullet_stitcher import stitch_fragmented_bullets
from preprocessing.transformation.text_metrics import (
    calculate_text_metrics,
    detect_language,
    standardize_to_vietnamese,
    filter_valid_clean_records,
)

__all__ = [
    "parse_salary_cascade",
    "UniversalSalaryParser",
    "strip_html_tags",
    "stitch_fragmented_bullets",
    "calculate_text_metrics",
    "detect_language",
    "standardize_to_vietnamese",
    "filter_valid_clean_records",
]
