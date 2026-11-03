# -*- coding: utf-8 -*-
"""preprocessing.transformation.date_parser
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Bóc tách ngày đăng và hạn nộp hồ sơ theo luật T3:
- Chuyển đổi định dạng ISO hoặc dd/mm/yyyy về chuẩn YYYY-MM-DD.
- Gắn cờ deadline_before_crawl nếu hạn nộp trước ngày cào (H3).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional, Tuple


def parse_date(date_str: Optional[str]) -> Optional[str]:
    """Chuyển đổi chuỗi ngày thô về dạng ISO 'YYYY-MM-DD'."""
    if not date_str or not str(date_str).strip():
        return None

    s = str(date_str).strip()

    # Dạng ISO có timestamp (ví dụ 2026-10-14T04:20:13.27873Z hoặc 2026-10-14T04:20:13)
    if "T" in s:
        try:
            return datetime.fromisoformat(s[:19]).strftime("%Y-%m-%d")
        except ValueError:
            pass

    # Dạng ISO ngày YYYY-MM-DD hoặc YYYY/MM/DD
    m_iso = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m_iso:
        try:
            d = datetime(int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3)))
            return d.strftime("%Y-%m-%d")
        except ValueError:
            pass

    # Dạng Việt Nam dd/mm/yyyy hoặc dd-mm-yyyy
    m_vn = re.match(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})", s)
    if m_vn:
        try:
            d = datetime(int(m_vn.group(3)), int(m_vn.group(2)), int(m_vn.group(1)))
            return d.strftime("%Y-%m-%d")
        except ValueError:
            pass

    return None


def process_dates(
    raw_posted: Optional[str],
    raw_deadline: Optional[str],
    crawled_at: Optional[str]
) -> Tuple[Optional[str], Optional[str], bool]:
    """Xử lý cả 2 ngày và kiểm tra cờ deadline_before_crawl."""
    posted = parse_date(raw_posted)
    deadline = parse_date(raw_deadline)
    crawl_date = parse_date(crawled_at)

    is_expired_before_crawl = False
    if deadline and crawl_date:
        if deadline < crawl_date:
            is_expired_before_crawl = True

    return posted, deadline, is_expired_before_crawl
