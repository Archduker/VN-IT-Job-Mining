# -*- coding: utf-8 -*-
"""preprocessing.missing_outlier.sneaky_null_detector
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Bộ phát hiện và bóc trần Null Marker trá hình đa nguồn cho VN-IT-Job-Mining.

Tuân thủ nguyên tắc EDA-First & Zero Information Loss:
  - Nhận diện các null markers ngụy trang: '', ' ', 'nan', 'none', 'null', 'n/a', '-', '…', '...', '[]', '{}'.
  - Context-Aware: Phân biệt theo source_platform + field + type.
  - Bảo toàn giá trị hợp lệ:
      * min_experience_years = 0.0 là hợp lệ (Fresher / không yêu cầu kinh nghiệm).
      * Booleans (False/True) không phải null.
      * Số 0 trong mức lương (như VietnamWorks salaryMin=0, salaryMax=0) được bóc trần là lương thỏa thuận/thiếu.
      * Khác biệt hóa các trạng thái lương: Thỏa thuận (negotiable), Cạnh tranh (competitive), Ẩn/Đăng nhập (hidden).
      * Phân tích văn bản dài (JD): Không coi JD là null chỉ vì chứa từ 'null' hoặc dấu ba chấm.
      * Bảo toàn danh sách: Giữ phần tử hợp lệ trong list, chỉ loại bỏ các phần tử rỗng/marker.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Bộ markers văn bản giữ chỗ tiêu chuẩn (toàn chuỗi, chuẩn hóa lowercase + strip)
STANDARD_TEXT_MARKERS: Set[str] = {
    "",
    " ",
    "nan",
    "none",
    "null",
    "n/a",
    "na",
    "[]",
    "{}",
    "set()",
    "-",
    "--",
    "---",
    "…",
    "...",
    "không xác định",
    "chưa xác định",
    "đang cập nhật",
    "chưa cập nhật",
    "none of the above",
    "undefined",
    "nil",
}

# Các marker đặc thù cho trạng thái lương thỏa thuận (Negotiable)
SALARY_NEGOTIABLE_MARKERS: Set[str] = {
    "thỏa thuận",
    "thoả thuận",
    "thương lượng",
    "thuong luong",
    "thoa thuan",
    "negotiable",
    "deal",
    "trao đổi khi phỏng vấn",
    "trao đổi trực tiếp khi phỏng vấn",
    "trao đổi khi pv",
    "thỏa thuận khi phỏng vấn",
}

# Các marker lương cạnh tranh (Competitive)
SALARY_COMPETITIVE_MARKERS: Set[str] = {
    "cạnh tranh",
    "canh tranh",
    "competitive",
    "competitive salary",
    "mức lương cạnh tranh",
}

# Các marker lương bị ẩn / yêu cầu đăng nhập (Hidden / Login required)
SALARY_HIDDEN_MARKERS: Set[str] = {
    "đăng nhập để xem",
    "dang nhap de xem",
    "đăng nhập để xem mức lương",
    "đăng nhập để xem lương",
    "công ty không công khai thông tin này",
    "confidential",
    "open",
    "bảo mật",
    "chưa công bố",
}

# Tổng hợp tất cả các marker lương khuyết thiếu
ALL_SALARY_NULL_MARKERS: Set[str] = (
    STANDARD_TEXT_MARKERS
    | SALARY_NEGOTIABLE_MARKERS
    | SALARY_COMPETITIVE_MARKERS
    | SALARY_HIDDEN_MARKERS
)

# Tập hợp các trường kinh nghiệm (0 và 0.0 là hợp lệ)
EXPERIENCE_FIELDS: Set[str] = {
    "min_experience_years",
    "max_experience_years",
    "experience_years",
    "min_exp",
    "max_exp",
}

# Tập hợp các trường mức lương
SALARY_FIELDS: Set[str] = {
    "raw_salary_text",
    "salary_min_vnd",
    "salary_max_vnd",
    "salary_min",
    "salary_max",
    "salary_min_original",
    "salary_max_original",
}

# Tập hợp các trường danh sách
LIST_FIELDS: Set[str] = {
    "skills_list",
    "benefits_list",
    "working_locations",
}


def is_val_null(
    val: Any,
    field: Optional[str] = None,
    source_platform: Optional[str] = None,
) -> bool:
    """Kiểm tra một giá trị có phải là Null (bao gồm cả null trá hình) hay không.

    Hàm có tính tương thích ngữ cảnh (Context-Aware):
      - field: Tên trường đang kiểm tra (ví dụ 'min_experience_years', 'raw_salary_text', 'skills_list').
      - source_platform: Nguồn tuyển dụng (ví dụ 'vietnamworks', 'careerviet', 'glints').
    """
    # 1. Kiểm tra None tường minh
    if val is None:
        return True

    # 2. Boolean (False/True) KHÔNG PHẢI LÀ NULL (isinstance(False, int) là True trong Python)
    if isinstance(val, bool):
        return False

    # 3. Float NaN an toàn (không gọi trên list/dict để tránh lỗi truth-value)
    if isinstance(val, float) and math.isnan(val):
        return True

    # 4. Container rỗng (list, dict, set, tuple)
    if isinstance(val, (list, dict, set, tuple)):
        if len(val) == 0:
            return True
        # Nếu là list chuỗi, kiểm tra xem có phải toàn bộ phần tử đều là marker rỗng hay không
        if isinstance(val, list):
            valid_items = [item for item in val if not is_val_null(item, field=None)]
            return len(valid_items) == 0
        return False

    # 5. Giá trị số học (int, float)
    if isinstance(val, (int, float)):
        # Đối với các trường kinh nghiệm, 0 và 0.0 là giá trị HỢP LỆ (Fresher / không yêu cầu)
        if field and field in EXPERIENCE_FIELDS:
            return False

        # Đối với các trường lương: số 0 là null marker ngụy trang (ví dụ VietnamWorks salaryMin=0, salaryMax=0)
        if field and field in SALARY_FIELDS:
            return val == 0 or val == 0.0

        # Nếu không truyền field: giữ tương thích ngược với pipeline hiện có (0 được coi là null)
        if field is None and val == 0:
            return True

        return False

    # 6. Chuỗi ký tự (str)
    if isinstance(val, str):
        s_clean = val.strip()
        if not s_clean:
            return True

        s_lower = s_clean.lower()

        # Kiểm tra văn bản dài (JD / Description / Requirements)
        # Chỉ coi là null nếu toàn bộ chuỗi khớp chính xác một null marker
        if len(s_clean) > 80:
            # Văn bản dài không thể là placeholder marker đơn thuần
            return False

        # Nếu là trường kinh nghiệm và giá trị là "0" hoặc "0.0" -> HỢP LỆ
        if field and field in EXPERIENCE_FIELDS and s_lower in {"0", "0.0"}:
            return False

        # Nếu là trường lương: kiểm tra các marker lương đặc thù
        if field and field in SALARY_FIELDS:
            if s_lower in ALL_SALARY_NULL_MARKERS or s_lower in {"0", "0.0"}:
                return True

        # Kiểm tra các marker tiêu chuẩn
        if s_lower in STANDARD_TEXT_MARKERS:
            return True

        # Kiểm tra "0" hoặc "0.0" khi field không được chỉ định
        if s_lower in {"0", "0.0"}:
            if field and field in EXPERIENCE_FIELDS:
                return False
            return True

        # Kiểm tra các marker lương khi field là None (giữ tương thích)
        if field is None and (s_lower in SALARY_NEGOTIABLE_MARKERS or s_lower in SALARY_COMPETITIVE_MARKERS):
            return True

    return False


def detect_null_type(
    val: Any,
    field: Optional[str] = None,
    source_platform: Optional[str] = None,
) -> str:
    """Phân loại trạng thái null phục vụ báo cáo chất lượng và kiểm toán dữ liệu.

    Returns một trong các nhãn:
      - 'EXPLICIT_NONE': None tường minh.
      - 'EXPLICIT_NAN': Float NaN.
      - 'EMPTY_CONTAINER': Danh sách hoặc từ điển rỗng.
      - 'WHITESPACE_ONLY': Chuỗi chỉ gồm khoảng trắng.
      - 'TEXT_PLACEHOLDER': Dấu giữ chỗ ('nan', 'null', 'n/a', '-', '…', '...', v.v.).
      - 'NEGOTIABLE_MARKER': Marker lương thỏa thuận ('thỏa thuận', 'thương lượng').
      - 'COMPETITIVE_MARKER': Marker lương cạnh tranh ('cạnh tranh', 'competitive').
      - 'HIDDEN_SALARY_MARKER': Marker lương ẩn ('đăng nhập để xem', 'bảo mật').
      - 'NUMERIC_ZERO': Số 0 ngụy trang trong trường không cho phép 0 (ví dụ lương).
      - 'VALID': Dữ liệu hợp lệ.
    """
    if val is None:
        return "EXPLICIT_NONE"

    if isinstance(val, bool):
        return "VALID"

    if isinstance(val, float) and math.isnan(val):
        return "EXPLICIT_NAN"

    if isinstance(val, (list, dict, set, tuple)):
        if len(val) == 0:
            return "EMPTY_CONTAINER"
        if isinstance(val, list):
            valid_items = [item for item in val if not is_val_null(item, field=None)]
            if len(valid_items) == 0:
                return "EMPTY_CONTAINER"
        return "VALID"

    if isinstance(val, (int, float)):
        if field and field in EXPERIENCE_FIELDS:
            return "VALID"
        if val == 0:
            if field and field in SALARY_FIELDS:
                return "NUMERIC_ZERO"
            if field is None:
                return "NUMERIC_ZERO"
        return "VALID"

    if isinstance(val, str):
        s_clean = val.strip()
        if not s_clean:
            return "WHITESPACE_ONLY"

        s_lower = s_clean.lower()

        # Không đánh giá văn bản dài là marker
        if len(s_clean) > 80:
            return "VALID"

        if field and field in EXPERIENCE_FIELDS and s_lower in {"0", "0.0"}:
            return "VALID"

        if s_lower in SALARY_NEGOTIABLE_MARKERS:
            return "NEGOTIABLE_MARKER"

        if s_lower in SALARY_COMPETITIVE_MARKERS:
            return "COMPETITIVE_MARKER"

        if s_lower in SALARY_HIDDEN_MARKERS:
            return "HIDDEN_SALARY_MARKER"

        if s_lower in {"0", "0.0"}:
            if field and field in EXPERIENCE_FIELDS:
                return "VALID"
            return "NUMERIC_ZERO"

        if s_lower in STANDARD_TEXT_MARKERS:
            return "TEXT_PLACEHOLDER"

    return "VALID"


def classify_salary_null(raw_salary_text: Any) -> bool:
    """Kiểm tra xem mức lương có phải là thỏa thuận/cạnh tranh/ẩn/0/null hay không.

    Hàm hỗ trợ phát hiện toàn diện mọi trạng thái thiếu lương ở header.
    """
    if is_val_null(raw_salary_text, field="raw_salary_text"):
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
            "dang nhap de xem",
            "trao đổi khi phỏng vấn",
            "confidential",
            "open",
        ]
    )


def is_salary_negotiable_marker(raw_salary_text: Any) -> bool:
    """Kiểm tra nghiêm ngặt xem mức lương có thực sự là THỎA THUẬN (Negotiable) hay không.

    Chỉ bật cờ is_salary_negotiable khi văn bản thực sự thể hiện thỏa thuận,
    không đánh đồng với 'đăng nhập để xem' (lương ẩn) hoặc 'cạnh tranh'.
    """
    if raw_salary_text is None:
        return False

    s = str(raw_salary_text).strip().lower()
    if s in SALARY_NEGOTIABLE_MARKERS:
        return True

    return any(
        k in s
        for k in [
            "thỏa thuận",
            "thoả thuận",
            "thương lượng",
            "thuong luong",
            "thoa thuan",
            "negotiable",
            "deal",
            "trao đổi khi phỏng vấn",
        ]
    )


def clean_list_elements(items: Any, field: Optional[str] = None) -> List[str]:
    """Làm sạch các phần tử trong danh sách:

    - Loại bỏ các null markers ngụy trang ('', '-', '…', 'null', 'nan').
    - Chuẩn hóa khoảng trắng.
    - Bảo toàn các phần tử hợp lệ và duy trì thứ tự xuất hiện ban đầu.
    - Luôn trả về kiểu list[str] (danh sách rỗng là []).
    """
    if not isinstance(items, list):
        return []

    cleaned: List[str] = []
    seen: Set[str] = set()

    for item in items:
        if item is None:
            continue
        s = str(item).strip()
        if not s:
            continue
        # Kiểm tra nếu item khớp chính xác null marker
        if is_val_null(s, field=field):
            continue

        s_key = s.lower()
        if s_key not in seen:
            seen.add(s_key)
            cleaned.append(s)

    return cleaned


def detect_record_nulls(
    record: Dict[str, Any],
    source_platform: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """Kiểm tra toàn diện tất cả các trường trong một flat record.

    Trả về từ điển chẩn đoán chi tiết theo từng trường:
    {
        field_name: {
            "value": raw_val,
            "is_null": bool,
            "null_type": str,
        }
    }
    """
    if not isinstance(record, dict):
        raise TypeError(f"Record đầu vào phải là dict, nhận được kiểu {type(record).__name__}")

    source = source_platform or record.get("source_platform")
    diagnosis: Dict[str, Dict[str, Any]] = {}

    for field, val in record.items():
        is_null = is_val_null(val, field=field, source_platform=source)
        null_type = detect_null_type(val, field=field, source_platform=source)
        diagnosis[field] = {
            "value": val,
            "is_null": is_null,
            "null_type": null_type,
        }

    return diagnosis


def sanitize_flat_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Tạo bản sao làm sạch của flat record mà KHÔNG làm thay đổi record đầu vào:

    - Làm sạch các phần tử null marker bên trong skills_list, benefits_list, working_locations.
    - Bảo toàn nguyên vẹn mọi trường raw_* (Zero Information Loss) để phục vụ kiểm toán.
    - Bảo toàn kiểu dữ liệu list[str] (không chuyển thành NaN/None/chuỗi).
    """
    if not isinstance(record, dict):
        raise TypeError(f"Record đầu vào phải là dict, nhận được kiểu {type(record).__name__}")

    sanitized = dict(record)

    # Làm sạch các cột danh sách
    for col in LIST_FIELDS:
        if col in sanitized and isinstance(sanitized[col], list):
            sanitized[col] = clean_list_elements(sanitized[col], field=col)
        elif col in sanitized and sanitized[col] is None:
            sanitized[col] = []

    return sanitized
