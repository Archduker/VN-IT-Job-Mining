# -*- coding: utf-8 -*-
"""preprocessing.missing_outlier
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Module bóc trần null markers, GenAI Imputer và xử lý ngoại lai IQR.
"""

from preprocessing.missing_outlier.sneaky_null_detector import is_val_null, detect_null_type, classify_salary_null
from preprocessing.missing_outlier.genai_text_imputer import GenAITextImputer
from preprocessing.missing_outlier.outlier_handler import (
    detect_iqr_outliers,
    winsorize_series,
    winsorize_with_capping,
    winsorize_by_source,
    fix_common_salary_input_errors,
    fix_salary_input_errors_detailed,
    apply_outlier_pipeline,
)
from preprocessing.missing_outlier.quality_rules import (
    add_quality_flags,
    compute_quality_score,
    summarize_quality,
)

__all__ = [
    "is_val_null",
    "detect_null_type",
    "classify_salary_null",
    "GenAITextImputer",
    "detect_iqr_outliers",
    "winsorize_series",
    "winsorize_with_capping",
    "winsorize_by_source",
    "fix_common_salary_input_errors",
    "fix_salary_input_errors_detailed",
    "apply_outlier_pipeline",
    "add_quality_flags",
    "compute_quality_score",
    "summarize_quality",
]
