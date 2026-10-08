"""
crawlers.common.utils
~~~~~~~~~~~~~~~~~~~~~~
Utility functions dùng chung: URL normalization, hashing, text cleaning.

Functions:
    normalize_url(url)           — Bỏ utm_*, trailing slash, fragment
    extract_job_id_from_url(url) — Trích job ID từ URL pattern
    hash_url(url)                — Hash MD5 ngắn (8 ký tự) từ URL
    strip_html_tags(html)        — Bỏ HTML tags, trả về plain text
    make_batch_id(source, seq)   — Tạo batch ID chuẩn
    clean_text(text)             — Xoá whitespace thừa, normalize unicode
"""

from __future__ import annotations

import hashlib
import html as html_lib
import re
import unicodedata
from datetime import date
from typing import Optional
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

# Reuse normalize_url từ schema module (single source of truth)
from crawlers.common.schema import normalize_url, hash_url


__all__ = [
    "normalize_url",
    "hash_url",
    "extract_job_id_from_url",
    "strip_html_tags",
    "make_batch_id",
    "clean_text",
    "normalize_skills_text",
]


def extract_job_id_from_url(url: str, pattern: str = r"[-_/](\d{6,})\b") -> Optional[str]:
    """Trích job ID (dạng số) từ URL bằng regex pattern.

    Args:
        url: URL cần trích ID.
        pattern: Regex pattern để tìm ID. Default: tìm số 6+ chữ số sau dấu - hoặc _.
            Ví dụ topdev URL: `/viec-lam/senior-backend-developer-fpt-2136579`
            → ID: "2136579"

    Returns:
        Job ID string nếu tìm thấy, None nếu không tìm thấy.

    Examples:
        >>> extract_job_id_from_url("https://topdev.vn/viec-lam/senior-backend-2136579")
        '2136579'
        >>> extract_job_id_from_url("https://topdev.vn/it-jobs") is None
        True
    """
    match = re.search(pattern, url)
    return match.group(1) if match else None


def strip_html_tags(html: str) -> str:
    """Bỏ tất cả HTML tags và trả về plain text.

    Xử lý:
        - Bỏ toàn bộ tags (<div>, <p>, <br>, ...)
        - Thay thế <br>, <p>, <li> bằng newline trước khi strip
        - Decode HTML entities cơ bản (&amp; → &, &lt; → <, ...)
        - Xoá whitespace thừa

    Args:
        html: HTML string cần strip.

    Returns:
        Plain text đã được làm sạch.

    Examples:
        >>> strip_html_tags("<p>Senior <strong>Backend</strong> Developer</p>")
        'Senior Backend Developer'
        >>> strip_html_tags("<ul><li>Python</li><li>Django</li></ul>")
        'Python\\nDjango'
    """
    if not html:
        return ""

    # Thay block elements bằng newline để giữ cấu trúc
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</p>|</div>|</li>|</h[1-6]>", "\n", text, flags=re.IGNORECASE)

    # Bỏ toàn bộ tags
    text = re.sub(r"<[^>]+>", "", text)

    # Decode HTML entities đầy đủ (bao gồm ký tự tiếng Việt có dấu &iacute;, &aacute;, v.v.)
    text = html_lib.unescape(text)

    return clean_text(text)


def clean_text(text: str) -> str:
    """Xoá whitespace thừa và chuẩn hoá Unicode.

    Xử lý:
        - Strip leading/trailing whitespace
        - Normalize non-breaking space (\\xa0)
        - Collapse multiple spaces/tabs thành 1 space
        - Collapse multiple newlines thành tối đa 2 newlines
        - Normalize unicode (NFC form)

    Args:
        text: Text cần làm sạch.

    Returns:
        Text đã được làm sạch.

    Examples:
        >>> clean_text("  Senior   Backend   Developer  ")
        'Senior Backend Developer'
        >>> clean_text("Python\\n\\n\\n\\nDjango")
        'Python\\n\\nDjango'
    """
    if not text:
        return ""

    # Unicode normalization (NFC)
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\xa0", " ").replace("\u200b", "")

    # Collapse multiple spaces/tabs (nhưng giữ newlines)
    lines = text.split("\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in lines]

    # Collapse multiple blank lines thành tối đa 2
    result_lines: list[str] = []
    blank_count = 0
    for line in lines:
        if line == "":
            blank_count += 1
            if blank_count <= 2:
                result_lines.append(line)
        else:
            blank_count = 0
            result_lines.append(line)

    return "\n".join(result_lines).strip()


def make_batch_id(source: str, seq: int = 1, run_date: Optional[date] = None) -> str:
    """Tạo batch ID chuẩn theo format YYYY-MM-DD_<source>_<seq>.

    Args:
        source: Tên nguồn (ví dụ: "topdev").
        seq: Số thứ tự batch trong ngày (default: 1, format: 001).
        run_date: Ngày chạy (default: hôm nay).

    Returns:
        Batch ID string.

    Examples:
        >>> from datetime import date
        >>> make_batch_id("topdev", seq=1, run_date=date(2026, 10, 7))
        '2026-10-07_topdev_001'
        >>> make_batch_id("careerviet", seq=2, run_date=date(2026, 10, 8))
        '2026-10-08_careerviet_002'
    """
    if run_date is None:
        run_date = date.today()
    return f"{run_date.isoformat()}_{source.lower()}_{seq:03d}"


def normalize_skills_text(skills_text: str) -> list[str]:
    """Parse danh sách kỹ năng từ text thành list.

    Hỗ trợ nhiều delimiter: dấu phẩy, pipe, slash, chấm phẩy.

    Args:
        skills_text: Chuỗi kỹ năng (ví dụ: "Java, Python | Docker").

    Returns:
        List các kỹ năng đã được strip whitespace.

    Examples:
        >>> normalize_skills_text("Java, Spring Boot, MySQL")
        ['Java', 'Spring Boot', 'MySQL']
        >>> normalize_skills_text("Python | Django | PostgreSQL")
        ['Python', 'Django', 'PostgreSQL']
        >>> normalize_skills_text("Docker/Kubernetes;CI-CD")
        ['Docker', 'Kubernetes', 'CI-CD']
    """
    if not skills_text:
        return []

    # Split bởi common delimiters
    skills = re.split(r"[,|;/]+", skills_text)
    skills = [s.strip() for s in skills if s.strip()]
    return skills
