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
    "parse_salary_detail",
    "text_to_clean_lines",
    "classify_job_tags",
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


def parse_salary_detail(
    salary_text: Optional[str],
    title: Optional[str] = None,
) -> dict:
    """Trích xuất và chuẩn hóa thông tin mức lương có ngữ nghĩa chi tiết.

    Phân tích dải lương, đơn vị tiền tệ, chu kỳ trả lương (pay_period),
    trạng thái thỏa thuận (is_negotiable), và cờ hoa hồng (has_commission).

    Args:
        salary_text: Chuỗi mức lương hiển thị (ví dụ: 'Tới 40 triệu', 'Thoả thuận').
        title: Tiêu đề công việc (dự phòng trường hợp mức lương được viết trong title).

    Returns:
        Dict tương thích với schema JobSalary.
    """
    raw_text = clean_text(salary_text or "")
    combined_context = f"{raw_text} {title or ''}".strip()
    lower_context = combined_context.lower()

    # 1. Phát hiện cờ hoa hồng / thu nhập biến đổi
    commission_keywords = [
        "hoa hồng", "commission", "không giới hạn", "thưởng doanh số", "thưởng kpi",
        "bonus theo doanh số", "+ hoa hồng", "+ commission"
    ]
    has_commission = any(k in lower_context for k in commission_keywords)

    # 2. Phát hiện trạng thái thỏa thuận
    negotiable_keywords = ["thỏa thuận", "thoả thuận", "thương lượng", "negotiable", "competitive"]
    is_raw_negotiable = any(k in raw_text.lower() for k in negotiable_keywords)

    # 3. Trích xuất dải số từ text hoặc fallback từ title nếu raw_text là thỏa thuận
    sal_to_parse = raw_text
    if is_raw_negotiable and title:
        m_sal = re.search(
            r"(?:lương|salary|thu nhập|upto|up to|tới|từ)?\s*(\d+(?:[.,]\d+)?\s*(?:-|–|to|đến)?\s*\d+(?:[.,]\d+)?\s*(?:triệu|tr|m|usd|\$)|upto\s*\d+\s*(?:triệu|tr|m|usd|\$)|up to\s*\d+\s*(?:triệu|tr|m|usd|\$)|tới\s*\d+\s*(?:triệu|tr|m|usd|\$))",
            title,
            re.IGNORECASE,
        )
        if m_sal:
            sal_to_parse = m_sal.group(0).strip()

    sal_to_parse_norm = re.sub(r"\bupto\b", "up to", sal_to_parse, flags=re.IGNORECASE)
    sal_min, sal_max, sal_currency = parse_salary(sal_to_parse_norm)

    # 4. Xác định chu kỳ trả lương (pay_period)
    pay_period: Optional[str] = None
    if any(k in lower_context for k in ["/năm", "/nam", "/year", "annual", "annually", "hàng năm"]):
        pay_period = "year"
    elif any(k in lower_context for k in ["/ngày", "/ngay", "/day", "daily", "hàng ngày"]):
        pay_period = "day"
    elif any(k in lower_context for k in ["/giờ", "/gio", "/hour", "hourly"]):
        pay_period = "hour"
    elif any(k in lower_context for k in ["/tháng", "/thang", "/month", "monthly", "hàng tháng", "triệu", "tr"]):
        pay_period = "month"
    elif sal_min is not None or sal_max is not None:
        # Đặc thù thị trường tuyển dụng IT Việt Nam, nếu có số tiền cụ thể thì mặc định là tháng
        pay_period = "month"

    # Nếu sau khi kiểm tra title mà tìm được số tiền thì không còn thuần thỏa thuận nữa
    is_negotiable = is_raw_negotiable if (sal_min is None and sal_max is None) else False

    return {
        "salary_text": raw_text or "Thoả thuận",
        "salary_min": sal_min,
        "salary_max": sal_max,
        "salary_currency": sal_currency,
        "pay_period": pay_period or ("month" if not is_negotiable else None),
        "is_negotiable": is_negotiable,
        "has_commission": has_commission,
    }


def text_to_clean_lines(content: Optional[str]) -> list[str]:
    """Chuyển đổi chuỗi text hoặc HTML thành danh sách các dòng sạch (list[str]).

    Tự động nhận diện danh sách <li> hoặc ngắt dòng \\n, loại bỏ các ký hiệu
    bullet point đầu dòng (-, *, •, +, 1., 2) và khoảng trắng thừa.

    Args:
        content: Chuỗi text hoặc đoạn mã HTML.

    Returns:
        List các chuỗi đã làm sạch.
    """
    if not content:
        return []

    if "<li" in content.lower():
        # Trích xuất nội dung giữa <li>...</li>
        li_matches = re.findall(r"<li[^>]*>(.*?)</li>", content, flags=re.DOTALL | re.IGNORECASE)
        lines = [strip_html_tags(m) for m in li_matches if m.strip()]
    else:
        text = strip_html_tags(content) if ("<" in content and ">" in content) else content
        lines = text.split("\n")

    clean_lines: list[str] = []
    for line in lines:
        l = clean_text(line)
        if not l:
            continue
        # Loại bỏ bullet points ở đầu dòng: •, -, *, +, 1., 2), v.v.
        l = re.sub(r"^(?:[\s•\-\*+–—]+|(?:\d+[\.\)]\s*))", "", l).strip()
        if len(l) >= 2 and not re.match(r"^[\s•\-\*+–—.,:;]+$", l):
            clean_lines.append(l)

    return clean_lines


def classify_job_tags(raw_tags: list[str]) -> dict:
    """Phân nhóm danh sách thẻ tag thành chuyên môn, chức danh, phúc lợi và thuộc tính.

    Args:
        raw_tags: Danh sách các tag thô lấy từ trang tuyển dụng.

    Returns:
        Dict chứa technical_skills, job_roles, benefits, attributes.
    """
    attributes: dict[str, str] = {}
    benefits: list[str] = []
    job_roles: list[str] = []
    technical_skills: list[str] = []

    role_keywords = [
        "developer", "engineer", "lập trình viên", "kỹ sư", "manager", "leader",
        "trưởng nhóm", "quản lý", "consultant", "analyst", "chuyên viên",
        "product owner", "scrum master", "tester", "qa", "qc", "devops", "sysadmin", "architect"
    ]
    benefit_keywords = [
        "bảo hiểm", "insurance", "du lịch", "travel", "team building", "thưởng", "bonus",
        "phụ cấp", "allowance", "đào tạo", "training", "xe đưa đón", "cơm trưa", "chăm sóc sức khỏe"
    ]

    for tag in raw_tags:
        t = clean_text(tag)
        if not t:
            continue
        lower_t = t.lower()

        # 1. Thuộc tính: Kinh nghiệm
        if any(k in lower_t for k in ["kinh nghiệm", "experience", "năm kn"]):
            attributes["experience"] = t
            continue

        # 2. Thuộc tính: Học vấn
        if any(k in lower_t for k in ["đại học", "cao đẳng", "thạc sĩ", "tiến sĩ", "degree", "university", "college"]):
            attributes["education"] = t
            continue

        # 3. Thuộc tính: Độ tuổi
        if "tuổi" in lower_t or "age" in lower_t:
            attributes["age"] = t
            continue

        # 4. Phúc lợi
        if any(b in lower_t for b in benefit_keywords):
            if t not in benefits:
                benefits.append(t)
            continue

        # 5. Chức danh / Vai trò
        if any(r in lower_t for r in role_keywords):
            if t not in job_roles:
                job_roles.append(t)
            continue

        # 6. Kỹ năng chuyên môn / công nghệ còn lại
        if t not in technical_skills:
            technical_skills.append(t)

    return {
        "technical_skills": technical_skills,
        "job_roles": job_roles,
        "benefits": benefits if benefits else None,
        "attributes": attributes,
        "skills": technical_skills + job_roles if (technical_skills or job_roles) else None,
        "requirements": list(attributes.values()) if attributes else None,
    }

