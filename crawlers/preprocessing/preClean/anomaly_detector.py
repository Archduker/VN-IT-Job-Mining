# -*- coding: utf-8 -*-
"""crawlers.preprocessing.preClean.anomaly_detector
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Bộ phát hiện mẫu dữ liệu dị biệt hoặc quá nhiều NULL (Corrupted Anomalous Samples):
- Nhận diện các bản ghi bị Cloudflare chặn (tiêu đề 'www.topcv.vn', công ty 'Unknown').
- Nhận diện các bản ghi bị thiếu đồng thời nhiều trường thông tin cốt lõi.
- Đóng gói lý do để đưa vào hàng đợi cào lại (Recrawl Queue).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

DUMMY_TITLES = {
    "www.topcv.vn",
    "just a moment...",
    "topcv",
    "error",
    "unknown",
    "access denied",
    "attention required! | cloudflare",
}

DUMMY_COMPANIES = {
    "unknown",
    "n/a",
    "none",
    "chưa cập nhật",
}


def detect_anomalous_sample(record: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Kiểm tra xem một bản ghi tuyển dụng có phải mẫu dị biệt/hỏng hay không.

    Args:
        record: Bản ghi thô từ batch file (chứa '_meta' và 'raw').

    Returns:
        Tuple (is_anomalous: bool, reason: str | None)
    """
    raw = record.get("raw", {})
    if not isinstance(raw, dict):
        return True, "INVALID_RAW_PAYLOAD"

    title = str(raw.get("title") or "").strip().lower()
    company = str(raw.get("company") or "").strip().lower()
    desc_list: List[Any] = raw.get("description_list") or []
    req_list: List[Any] = raw.get("requirements_list") or []

    # 1. Tiêu đề rác hoặc rỗng
    if not title or title in DUMMY_TITLES or title.startswith("www."):
        return True, f"DUMMY_OR_EMPTY_TITLE: '{title}'"

    # 2. Công ty rác đồng thời thiếu cả nội dung
    if (not company or company in DUMMY_COMPANIES) and len(desc_list) <= 1 and len(req_list) == 0:
        return True, "DUMMY_COMPANY_AND_EMPTY_CONTENT"

    # 3. Thiếu hoàn toàn cả mô tả lẫn yêu cầu
    desc_text = "".join(str(x) for x in desc_list).strip()
    req_text = "".join(str(x) for x in req_list).strip()
    if not desc_text and not req_text:
        return True, "EMPTY_DESCRIPTION_AND_REQUIREMENTS"

    # 4. Nội dung quá ngắn bất thường (< 20 ký tự tổng cộng)
    if len(desc_text) + len(req_text) < 20:
        return True, "CONTENT_TOO_SHORT_UNDER_20_CHARS"

    return False, None
