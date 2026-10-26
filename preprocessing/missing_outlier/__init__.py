# -*- coding: utf-8 -*-
"""preprocessing.missing_outlier
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Module bóc trần null markers, GenAI Imputer và xử lý ngoại lai IQR.
"""

from preprocessing.missing_outlier.sneaky_null_detector import (
    is_val_null,
    detect_null_type,
    classify_salary_null,
    is_salary_negotiable_marker,
    clean_list_elements,
    detect_record_nulls,
    sanitize_flat_record,
)
from preprocessing.missing_outlier.genai_text_imputer import GenAITextImputer
from preprocessing.missing_outlier.outlier_handler import (
    detect_iqr_outliers,
    winsorize_series,
    fix_common_salary_input_errors,
)

__all__ = [
    "is_val_null",
    "detect_null_type",
    "classify_salary_null",
    "is_salary_negotiable_marker",
    "clean_list_elements",
    "detect_record_nulls",
    "sanitize_flat_record",
    "GenAITextImputer",
    "detect_iqr_outliers",
    "winsorize_series",
    "fix_common_salary_input_errors",
]
