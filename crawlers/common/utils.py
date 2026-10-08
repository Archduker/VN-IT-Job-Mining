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
    "detect_language",
    "parse_salary",
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
        - Bỏ toàn bộ tags (<div>, <p>, <span>, <br>, <li>, ...)
        - Thay thế <br>, <p>, <li>, <div> bằng newline trước khi strip
        - Tách dòng sạch đẹp các mục phân cách bởi dấu phẩy trước ngắt dòng (ví dụ 'AA,<br>BB' -> 'AA,\nBB')
        - Decode HTML entities đầy đủ (&amp; → &, &lt; → <, &iacute; → í, ...)
        - Xoá whitespace thừa nhưng giữ ngắt dòng hợp lý

    Args:
        html: HTML string cần strip.

    Returns:
        Plain text đã được làm sạch.

    Examples:
        >>> strip_html_tags("<p>Senior <strong>Backend</strong> Developer</p>")
        'Senior Backend Developer'
        >>> strip_html_tags("<ul><li>Python</li><li>Django</li></ul>")
        'Python\\nDjango'
        >>> strip_html_tags("<p>Yêu cầu:</p>AA,<br>BB")
        'Yêu cầu:\\nAA,\\nBB'
    """
    if not html:
        return ""

    # Chuẩn hóa ngắt dòng cho thẻ <br>, block elements
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<(?:p|div|li|h[1-6]|tr)[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</(?:p|div|li|h[1-6]|tr)>", "\n", text, flags=re.IGNORECASE)

    # Bỏ toàn bộ tags còn lại
    text = re.sub(r"<[^>]+>", "", text)

    # Decode HTML entities đầy đủ
    text = html_lib.unescape(text)

    # Xử lý các trường hợp dòng chứa nhiều mục phân cách dấu phẩy dính liền ngắt dòng
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        cleaned_line = clean_text(line)
        if cleaned_line:
            cleaned_lines.append(cleaned_line)

    return "\n".join(cleaned_lines)


def detect_language(text: str) -> str:
    """Nhận diện ngôn ngữ của văn bản ('vi' hoặc 'en').

    Sử dụng kết hợp ký tự tiếng Việt có dấu đặc trưng và từ khóa thông dụng.

    Args:
        text: Văn bản cần nhận diện.

    Returns:
        'vi' nếu là tiếng Việt, ngược lại 'en'.

    Examples:
        >>> detect_language("Tuyển dụng lập trình viên Python kinh nghiệm 2 năm")
        'vi'
        >>> detect_language("Senior Software Engineer required with 5 years experience")
        'en'
    """
    if not text:
        return "vi"

    # Tập ký tự đặc trưng tiếng Việt có dấu
    vietnamese_chars = set("àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ"
                           "ÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ")
    
    # Đếm số ký tự tiếng Việt có dấu
    vn_char_count = sum(1 for ch in text if ch in vietnamese_chars)
    if vn_char_count >= 2:
        return "vi"

    # Kiểm tra các stop words tiếng Việt phổ biến
    lower_text = text.lower()
    vn_words = {
        "và", "của", "các", "cho", "được", "trong", "có", "với", "tuyển", "dụng",
        "công", "việc", "kinh", "nghiệm", "mức", "lương", "yêu", "cầu", "quyền", "lợi"
    }
    tokens = re.findall(r"\b[a-zA-Zà-ỹÀ-ỸđĐ]+\b", lower_text)
    if not tokens:
        return "vi"

    vn_matches = sum(1 for token in tokens if token in vn_words)
    if vn_matches >= 2 or (vn_matches >= 1 and len(tokens) <= 5):
        return "vi"

    # Nếu có ít nhất 1 ký tự có dấu
    if vn_char_count >= 1:
        return "vi"

    return "en"


def parse_salary(salary_text: Optional[str]) -> tuple[Optional[float], Optional[float], Optional[str]]:
    """Bóc tách mức lương từ text sang (salary_min, salary_max, salary_currency).

    Args:
        salary_text: Chuỗi text mức lương (ví dụ: '15 - 35 triệu', 'Thỏa thuận', '1000 - 2000 USD').

    Returns:
        Tuple (salary_min, salary_max, salary_currency).

    Examples:
        >>> parse_salary("15 - 35 triệu")
        (15.0, 35.0, 'VND')
        >>> parse_salary("Lên đến 50 triệu")
        (None, 50.0, 'VND')
        >>> parse_salary("Từ 20 triệu")
        (20.0, None, 'VND')
        >>> parse_salary("$1,000 - $2,500")
        (1000.0, 2500.0, 'USD')
        >>> parse_salary("Thỏa thuận")
        (None, None, None)
    """
    if not salary_text:
        return None, None, None

    text = salary_text.strip()
    lower_text = text.lower()

    if any(neg in lower_text for neg in ["thỏa thuận", "thương lượng", "thoả thuận", "negotiable", "cạnh tranh"]):
        return None, None, None

    currency = "VND"
    if "$" in text or "usd" in lower_text:
        currency = "USD"
    elif "vnd" in lower_text or "vnđ" in lower_text or "triệu" in lower_text or "tr" in lower_text:
        currency = "VND"

    # Tìm các số (có thể có dấu phẩy hoặc chấm thập phân)
    # Xử lý dấu phẩy trong số hàng nghìn USD (1,500)
    cleaned = text.replace(",", ".")
    # Nhưng nếu là dạng $1,000 thì 1,000 -> 1000
    cleaned_num_text = re.sub(r"(\d),(\d{3})", r"\1\2", text)

    # Tìm tất cả các số trong chuỗi
    numbers = re.findall(r"\d+(?:\.\d+)?", cleaned_num_text)
    if not numbers:
        return None, None, None

    nums = [float(n) for n in numbers]

    # Kiểm tra ngữ cảnh: range, min only (từ / trên), max only (lên đến / tới / dưới)
    is_range = any(sep in text for sep in ["-", "–", "đến", "tới", "to"]) and len(nums) >= 2
    is_up_to = any(w in lower_text for w in ["lên đến", "tới", "up to", "dưới", "<="]) and not is_range
    is_from = any(w in lower_text for w in ["từ", "trên", "from", ">="]) and not is_range

    if is_range:
        return nums[0], nums[1], currency
    elif is_up_to:
        return None, nums[0], currency
    elif is_from:
        return nums[0], None, currency
    else:
        if len(nums) == 1:
            return nums[0], nums[0], currency
        elif len(nums) >= 2:
            return nums[0], nums[1], currency

    return None, None, currency


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
