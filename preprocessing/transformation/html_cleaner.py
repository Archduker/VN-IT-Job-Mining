# -*- coding: utf-8 -*-
"""preprocessing.transformation.html_cleaner
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Module làm sạch mã rác HTML và CSS inline chuyên sâu (đặc biệt cho TopDev và VietnamWorks).
"""

from __future__ import annotations

import html
import re
from typing import Optional


_BLOCK_TAG = re.compile(r"</?(?:br|p|div|li|ul|ol|tr|table|h[1-6]|hr|section|article)\b[^<>]*>", re.IGNORECASE)
_ANY_TAG = re.compile(r"</?[A-Za-z!][^<>]*>")


def strip_html_tags(raw_text: Optional[str]) -> Optional[str]:
    """Loại bỏ 100% thẻ HTML, inline CSS và giải mã các thực thể HTML entities."""
    if not raw_text or not str(raw_text).strip():
        return None

    s = str(raw_text)

    # 1. Thẻ khối (mở hoặc đóng) -> xuống dòng; thẻ inline -> bỏ hẳn, không chèn khoảng trắng.
    #    "<" chỉ là thẻ khi theo sau là chữ cái, "/" hoặc "!" (giữ "<->", "< 3", "a<b").
    s = _BLOCK_TAG.sub("\n", s)
    s = _ANY_TAG.sub("", s)

    # 2. Giải mã entity, lặp tối đa 2 lần cho entity mã hóa hai lần (&amp;nbsp;)
    for _ in range(2):
        u = html.unescape(s)
        if u == s:
            break
        s = u

    # 4. Thay thế non-breaking spaces và ký tự lạ
    s = s.replace("\xa0", " ").replace("\u200b", "")

    # 5. Làm sạch khoảng trắng dư thừa trong từng dòng
    lines = []
    for line in s.splitlines():
        line_clean = re.sub(r"[ \t]+", " ", line).strip()
        if line_clean:
            lines.append(line_clean)

    return "\n".join(lines) if lines else None
