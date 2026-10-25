# -*- coding: utf-8 -*-
"""preprocessing.missing_outlier.sneaky_null_detector
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Bộ phát hiện và bóc trần Null Marker trá hình đa nguồn cho VN-IT-Job-Mining.

Các dạng null marker thực chiến:
  - Chuỗi rỗng: '', ' '
  - Chuỗi giữ chỗ: 'nan', 'none', 'null', 'n/a', 'na', '-', '…', '...'
  - Chuỗi cấu trúc rỗng: '[]', '{}', 'set()'
  - Ngụy trang số học: 0, 0.0, '0'
  - Ngụy trang thỏa thuận: 'thỏa thuận', 'thoả thuận', 'cạnh tranh', 'thương lượng'
"""

from __future__ import annotations

import math
from typing import Any, Set

SNEAKY_MARKERS: Set[str] = {
    "", " ", "nan", "none", "null", "n/a", "na", "[]", "{}", "-", "…", "...",
    "thỏa thuận", "thoả thuận", "cạnh tranh", "thương lượng", "không xác định",
    "chưa xác định", "đang cập nhật", "0", "0.0", "none", "chưa cập nhật"
}


def is_val_null(val: Any) -> bool:
    """Kiểm tra một giá trị có phải là Null (bao gồm cả null trá hình) hay không."""
    if val is None:
        return True

    # Float NaN
    if isinstance(val, float) and math.isnan(val):
        return True

    # Danh sách hoặc dict rỗng
    if isinstance(val, (list, dict, set, tuple)) and len(val) == 0:
        return True

    # Số 0 đơn lẻ (ngụy trang trong các trường lương như VietnamWorks salary=0)
    if isinstance(val, (int, float)) and val == 0:
        return True

    # Kiểm tra chuỗi
    s = str(val).strip().lower()
    return s in SNEAKY_MARKERS


def detect_null_type(val: Any) -> str:
    """Phân loại trạng thái null phục vụ báo cáo chất lượng."""
    if val is None:
        return "EXPLICIT_NONE"
    if isinstance(val, float) and math.isnan(val):
        return "EXPLICIT_NAN"
    if isinstance(val, (list, dict)) and len(val) == 0:
        return "EMPTY_CONTAINER"
    if isinstance(val, (int, float)) and val == 0:
        return "NUMERIC_ZERO"

    s = str(val).strip().lower()
    if s in {"", " "}:
        return "WHITESPACE_ONLY"
    if s in {"thỏa thuận", "thoả thuận", "cạnh tranh", "thương lượng"}:
        return "NEGOTIABLE_MARKER"
    if s in SNEAKY_MARKERS:
        return "TEXT_PLACEHOLDER"

    return "VALID"


def classify_salary_null(raw_salary_text: Any) -> bool:
    """Kiểm tra xem mức lương có phải là thỏa thuận/cạnh tranh/0/null hay không."""
    if is_val_null(raw_salary_text):
        return True
    s = str(raw_salary_text).strip().lower()
    return any(
        k in s
        for k in [
            "thỏa thuận",
            "thoả thuận",
            "cạnh tranh",
            "thương lượng",
            "deal",
            "negotiable",
            "competitive",
            "đăng nhập để xem",
        ]
    )

