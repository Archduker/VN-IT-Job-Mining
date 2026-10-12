# -*- coding: utf-8 -*-
"""crawlers.preprocessing.preClean.text_cleaner
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Bộ công cụ làm sạch chuỗi văn bản:
- Chuẩn hóa Unicode NFC (bảo toàn tiếng Việt có dấu và tiếng Anh).
- Loại bỏ mã HTML, ký tự tàng hình (zero-width), escape rác (\r, \t).
- Sinh mã định danh hợp nhất (Unified ID).
"""

from __future__ import annotations

import html
import re
import unicodedata
from typing import List, Optional

HTML_TAG_REGEX = re.compile(r"<[^>]+>")
WHITESPACE_REGEX = re.compile(r"[ \t\f\v]+")
NEWLINE_REGEX = re.compile(r"\r\n|\r")
BULLET_PREFIX_REGEX = re.compile(r"^[\s•\-*▪►–—]+\s*")


def normalize_unicode_nfc(text: Optional[str]) -> str:
    """Chuẩn hóa chuỗi văn bản về định dạng chuẩn Unicode NFC."""
    if not text:
        return ""
    return unicodedata.normalize("NFC", str(text))


def clean_text(text: Optional[str]) -> str:
    """Làm sạch văn bản tổng quát:
    - Unescape HTML entities (&amp;, &nbsp;, &lt;, etc.)
    - Loại bỏ thẻ HTML tags
    - Loại bỏ ký tự zero-width (\u200b, \ufeff, \u200e)
    - Chuẩn hóa Unicode NFC
    - Chuẩn hóa khoảng trắng và dòng trống
    """
    if not text:
        return ""

    s = str(text)
    # Unescape HTML entities
    s = html.unescape(s)
    # Gỡ bỏ thẻ HTML
    s = HTML_TAG_REGEX.sub(" ", s)
    # Loại bỏ ký tự zero-width và space đặc biệt
    s = s.replace("\u200b", "").replace("\ufeff", "").replace("\u200e", "").replace("\xa0", " ")
    # Chuẩn hóa ngắt dòng
    s = NEWLINE_REGEX.sub("\n", s)
    # Chuẩn hóa Unicode NFC
    s = unicodedata.normalize("NFC", s)
    # Chuẩn hóa khoảng trắng từng dòng
    lines: List[str] = []
    for line in s.split("\n"):
        line_clean = WHITESPACE_REGEX.sub(" ", line).strip()
        # Gỡ bỏ ký tự bullet ở đầu dòng nếu có
        line_clean = BULLET_PREFIX_REGEX.sub("", line_clean)
        if line_clean:
            lines.append(line_clean)

    return "\n".join(lines).strip()


def clean_single_line_text(text: Optional[str]) -> str:
    """Làm sạch chuỗi ngắn một dòng (Title, Company, Location)."""
    if not text:
        return ""
    cleaned = clean_text(text)
    # Gộp toàn bộ dòng thành 1 dòng duy nhất
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def generate_unified_id(source: str, job_id: str) -> str:
    """Tạo mã định danh duy nhất hợp nhất: f'{source}_{job_id}'."""
    src = str(source).lower().strip()
    jid = str(job_id).strip()
    return f"{src}_{jid}"
