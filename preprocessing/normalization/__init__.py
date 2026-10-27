# -*- coding: utf-8 -*-
"""preprocessing.normalization
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Module chuẩn hóa thang đo số học, biến đổi Log, chuẩn hóa văn bản/taxonomy,
kỹ năng ESCO (SD3) và khử trùng lặp xuyên sàn.
"""

from preprocessing.normalization.log_transformer import log_transform_salary, robust_scale_series
from preprocessing.normalization.taxonomy_mapper import (
    JOB_FAMILIES,
    SENIORITY_LEVELS,
    classify_job_family,
    job_family_name,
    normalize_seniority,
    standardized_seniority,
)
from preprocessing.normalization.text_cleaner import (
    clean_job_title,
    clean_jd_text,
    detect_remote,
    normalize_city,
    normalize_work_locations,
    process_record_text,
)
from preprocessing.normalization.skill_normalizer import (
    SkillNormalizer,
    get_normalizer,
    normalize_skills,
    normalize_dataframe,
    process_record_skills,
)
from preprocessing.normalization.skill_extractor import (
    SkillExtractor,
    augment_record,
    extract_skills_from_text,
    get_extractor,
)
from preprocessing.normalization.cross_deduplicator import (
    normalize_company_name,
    compute_title_token_similarity,
    deduplicate_cross_platform_jobs,
)

__all__ = [
    "log_transform_salary",
    "robust_scale_series",
    "clean_job_title",
    "clean_jd_text",
    "detect_remote",
    "normalize_city",
    "normalize_work_locations",
    "process_record_text",
    "normalize_seniority",
    "standardized_seniority",
    "classify_job_family",
    "job_family_name",
    "JOB_FAMILIES",
    "SENIORITY_LEVELS",
    "SkillNormalizer",
    "get_normalizer",
    "normalize_skills",
    "normalize_dataframe",
    "process_record_skills",
    "SkillExtractor",
    "augment_record",
    "extract_skills_from_text",
    "get_extractor",
    "normalize_company_name",
    "compute_title_token_similarity",
    "deduplicate_cross_platform_jobs",
]
