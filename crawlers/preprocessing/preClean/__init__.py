# -*- coding: utf-8 -*-
"""crawlers.preprocessing.preClean
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Gói xử lý sơ chế sơ bộ:
- Chuẩn hóa text (Unicode NFC, loại bỏ rác/HTML tags).
- Gán Unified ID (source_id).
- Bóc tách định lượng tiền lương (min, max, currency, type).
- Phát hiện mẫu dị biệt / nhiều null (Anomaly Detector).
- Điều phối hợp nhất các batch thành dataset sạch phục vụ EDA.
"""

from crawlers.preprocessing.preClean.schema import CleanedJobRecord
from crawlers.preprocessing.preClean.text_cleaner import clean_text, generate_unified_id, normalize_unicode_nfc
from crawlers.preprocessing.preClean.salary_parser import parse_salary_to_numbers
from crawlers.preprocessing.preClean.anomaly_detector import detect_anomalous_sample
from crawlers.preprocessing.preClean.pipeline import PreCleanPipeline

__all__ = [
    "CleanedJobRecord",
    "clean_text",
    "generate_unified_id",
    "normalize_unicode_nfc",
    "parse_salary_to_numbers",
    "detect_anomalous_sample",
    "PreCleanPipeline",
]
