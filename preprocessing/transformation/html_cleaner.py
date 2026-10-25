# -*- coding: utf-8 -*-
"""preprocessing.transformation.html_cleaner
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Module làm sạch mã rác HTML và CSS inline chuyên sâu (đặc biệt cho TopDev và VietnamWorks).
"""

from __future__ import annotations

import html
import re
from typing import Optional


def strip_html_tags(raw_text: Optional[str]) -> Optional[str]:
    """Loại bỏ 100% thẻ HTML, inline CSS và giải mã các thực thể HTML entities."""
    if not raw_text or not str(raw_text).strip():
        return None

    s = str(raw_text)

    # 1. Thay thế các thẻ ngắt dòng bằng ký tự xuống dòng thực tế
    s = re.sub(r"<\s*br\s*/?>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"<\s*/p\s*>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"<\s*/li\s*>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"<\s*/tr\s*>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"<\s*/div\s*>", "\n", s, flags=re.IGNORECASE)

    # 2. Xóa toàn bộ thẻ HTML còn lại (bao gồm cả thuộc tính style, class, data)
    s = re.sub(r"<[^>]+>", " ", s)

    # 3. Giải mã HTML entities: &nbsp; -> space, &amp; -> &, &lt; -> <, &gt; -> >
    s = html.unescape(s)

    # 4. Thay thế non-breaking spaces và ký tự lạ
    s = s.replace("\xa0", " ").replace("\u200b", "")

    # 5. Làm sạch khoảng trắng dư thừa trong từng dòng
    lines = []
    for line in s.splitlines():
        line_clean = re.sub(r"[ \t]+", " ", line).strip()
        if line_clean:
            lines.append(line_clean)

    return "\n".join(lines) if lines else None
