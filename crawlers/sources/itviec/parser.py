# -*- coding: utf-8 -*-
"""Parse HTML ITviec → Python dict (Data Contract v0.5.0 tinh gọn).

Owner: Phát

Hai hàm chính:
    parse_listing(html) → list[dict]  (URL + slug của từng job card)
    parse_detail(html)  → dict        (phần `raw` theo Data Contract tinh gọn)

Output parse_detail khớp cấu trúc JobRaw (crawlers/common/schema.py):
    description_list, requirements_list, benefits_list : list[str]
    salary   : dict (JobSalary) — object lồng, không phẳng ở root
    tags     : dict (JobTags)  — {requirements, benefits, skills}
    extra    : dict|null

Selector được chọn dựa trên HTML thực tế (probe 2026-10-05):
    - Listing: div.job-card (20 card/trang).
    - Detail: script JSON-LD @type=JobPosting + section render div.paragraph.
"""

import hashlib
import json
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from crawlers.common.utils import (
    detect_language,
    normalize_skills_text,
    parse_salary_detail,
    classify_job_tags,
    text_to_clean_lines,
)

try:  # chạy như package (python -m ...) hoặc chạy trực tiếp từ shell
    from . import config
except ImportError:  # pragma: no cover
    import config

# ---------------------------------------------------------------- URL

# Param tracking/navigation bị loại khi chuẩn hóa URL.
_STRIP_PARAM_PREFIXES = ("utm_",)
_STRIP_PARAM_KEYS = {
    "lab_feature", "click_source", "source", "query", "job_index",
    "gclid", "fbclid", "ref", "ref_src",
}

_JOB_PATH_RE = re.compile(r"^/viec-lam-it/([^/?#]+)/?$")


def normalize_url(url):
    """Chuẩn hóa URL: bỏ fragment, bỏ param tracking, bỏ '/' cuối, hạ chữ host."""
    parsed = urlparse(url)
    path = parsed.path
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    kept = []
    for param in (parsed.query or "").split("&"):
        if not param:
            continue
        key = param.split("=", 1)[0]
        if key in _STRIP_PARAM_KEYS or key.startswith(_STRIP_PARAM_PREFIXES):
            continue
        kept.append(param)
    query = "&".join(kept)
    host = parsed.netloc.lower()
    out = f"{parsed.scheme or 'https'}://{host}{path}"
    if query:
        out += f"?{query}"
    return out


def slug_from_url(url):
    """Lấy source_job_id (slug) từ URL detail. None nếu không phải URL job."""
    match = _JOB_PATH_RE.match(urlparse(url).path)
    return match.group(1) if match else None


def stable_job_id(url):
    """Fallback source_job_id: SHA-256 ổn định của URL đã chuẩn hóa."""
    return hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- listing


def parse_listing(html):
    """Trích danh sách job từ trang listing.

    Return: list[dict{"url", "source_job_id", "title"}], đã khử trùng ID
    trong cùng trang, giữ thứ tự hiển thị.
    """
    soup = BeautifulSoup(html, "html.parser")
    jobs, seen = [], set()
    for card in soup.select("div.job-card"):
        slug = (card.get("data-search--job-selection-job-slug-value") or "").strip()
        title = None
        if slug:
            url = normalize_url(f"{config.BASE_URL}/viec-lam-it/{slug}")
        else:
            a = card.select_one("h3 a[href]")
            if not a:
                continue
            url = normalize_url(urljoin(config.BASE_URL, a["href"]))
            slug = slug_from_url(url) or ""
            title = a.get_text(" ", strip=True) or None
        source_job_id = slug or stable_job_id(url)
        if source_job_id in seen:
            continue
        seen.add(source_job_id)
        jobs.append({
            "url": url,
            "source_job_id": source_job_id,
            "title": title,
        })
    return jobs


# ---------------------------------------------------------------- detail

_SECTION_KEYS = {
    "description": ("mô tả công việc", "job description"),
    "requirements": ("yêu cầu công việc", "job requirements", "yêu cầu"),
    "benefits": ("quyền lợi", "tại sao bạn sẽ yêu thích", "phúc lợi", "benefits"),
}

_JSON_LD_TYPE = "JobPosting"


def _find_job_posting(soup):
    """Lấy dict JSON-LD @type=JobPosting (nguồn chính, server render)."""
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict) and data.get("@type") == _JSON_LD_TYPE:
            return data
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("@type") == _JSON_LD_TYPE:
                    return item
    return {}


def _company_url(soup):
    """URL nguyên văn (đã chuẩn hóa) tới trang công ty /nha-tuyen-dung/<slug>."""
    a = soup.find("a", href=re.compile(r"/nha-tuyen-dung/"))
    if a is None:
        return None
    return normalize_url(urljoin(config.BASE_URL, a["href"]))


def _match_section(sections, keywords):
    """Tìm 1 section HTML theo keyword substring (không phân biệt hoa thường)."""
    for title, body in sections.items():
        low = title.lower()
        if any(k in low for k in keywords):
            return body
    return None


def _rendered_sections(soup):
    """Đọc các section render: {heading_text: inner_html}."""
    out = {}
    for div in soup.select("div.paragraph"):
        heading = div.find("h2")
        if heading is None:
            continue
        title = heading.get_text(" ", strip=True)
        body_parts = []
        for child in div.children:
            if getattr(child, "name", None) == "h2":
                continue
            body_parts.append(str(child))
        body = "".join(body_parts).strip()
        if title and body:
            out.setdefault(title, body)
    return out


# ---------------------------------------------------------------- salary


def _parse_base_salary(jp):
    """Trích (min, max, currency) từ JSON-LD baseSalary.

    Return: (float|None, float|None, str|None).
    """
    base_salary = jp.get("baseSalary")
    if not base_salary or not isinstance(base_salary, dict):
        return None, None, None

    currency = base_salary.get("currency")
    value_obj = base_salary.get("value", {})
    if not isinstance(value_obj, dict):
        return None, None, currency

    raw_value = value_obj.get("value", "")

    if isinstance(raw_value, str):
        try:
            num = float(raw_value.replace(",", ""))
            return num, num, currency
        except (ValueError, TypeError):
            return None, None, currency

    if isinstance(raw_value, (int, float)):
        num = float(raw_value)
        min_val = float(value_obj.get("minValue", num))
        max_val = float(value_obj.get("maxValue", num))
        return min_val, max_val, currency

    return None, None, currency


def _build_salary(salary_display_text, jp, title=None):
    """Xây dựng salary dict tương thích JobSalary.

    Kết hợp JSON-LD baseSalary (ưu tiên số) và text hiển thị trên trang.
    Text kiểu "Đăng nhập để xem mức lương" / "You'll love it" → min=max=null,
    is_negotiable=true.  Khi salary_min/max = null thì currency = null.
    """
    # Parse text hiển thị (utils.parse_salary_detail xử lý đầy đủ)
    text_parsed = parse_salary_detail(salary_display_text, title)

    # JSON-LD baseSalary override
    jld_min, jld_max, jld_currency = _parse_base_salary(jp)

    sal_min = text_parsed["salary_min"]
    sal_max = text_parsed["salary_max"]
    sal_currency = text_parsed["salary_currency"]
    pay_period = text_parsed["pay_period"]
    is_negotiable = text_parsed["is_negotiable"]
    has_commission = text_parsed["has_commission"]

    # Ưu tiên số từ JSON-LD nếu có
    if jld_min is not None or jld_max is not None:
        sal_min = jld_min
        sal_max = jld_max
        if jld_currency:
            sal_currency = jld_currency
        is_negotiable = False  # có con số cụ thể → không phải thỏa thuận

    # Rào cản: khi min/max = null → currency = null
    if sal_min is None and sal_max is None:
        sal_currency = None
        is_negotiable = True

    return {
        "salary_text": text_parsed["salary_text"],
        "salary_min": sal_min,
        "salary_max": sal_max,
        "salary_currency": sal_currency,
        "pay_period": pay_period,
        "is_negotiable": is_negotiable,
        "has_commission": has_commission,
    }


# ---------------------------------------------------------------- tags


def _build_tags(jp):
    """Xây dựng tags dict tương thích JobTags từ JSON-LD skills.

    Return: {requirements: list|null, benefits: list|null, skills: list|null}
    """
    skills_raw = jp.get("skills", "")
    skills_list = normalize_skills_text(skills_raw) if skills_raw else []
    if not skills_list:
        return {"requirements": None, "benefits": None, "skills": None}
    classified = classify_job_tags(skills_list)
    return {
        "requirements": classified.get("requirements"),
        "benefits": classified.get("benefits"),
        "skills": classified.get("skills"),
    }


# ---------------------------------------------------------------- main


def _clean_ws(value):
    """Bỏ khoảng trắng thừa đầu/cuối chuỗi."""
    if isinstance(value, str):
        return value.strip() or None
    return value


def _infer_posted_date(date_posted, valid_through):
    """Suy luận ngày đăng: ưu tiên datePosted, fallback = validThrough − 30 ngày."""
    if date_posted:
        return date_posted
    if not valid_through:
        return None
    try:
        from datetime import datetime, timedelta
        deadline = datetime.strptime(str(valid_through)[:10], "%Y-%m-%d")
        inferred = deadline - timedelta(days=30)
        return inferred.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def parse_detail(html):
    """Parse trang detail ITviec → dict phần `raw` (Data Contract v0.5.0 tinh gọn).

    Output khớp JobRaw schema:
        title, company, description_list, salary (JobSalary),
        tags (JobTags), requirements_list, benefits_list,
        location_text, deadline_text, posted_date_text,
        employment_type_text, seniority_text, extra.

    KHÔNG có field legacy ở root: description_html, description_text,
    salary_text/min/max/currency (phẳng), skills_text, requirements_text,
    benefits_text.
    """
    soup = BeautifulSoup(html, "html.parser")
    jp = _find_job_posting(soup)
    sections = _rendered_sections(soup)

    # ── Title ──
    h1 = soup.find("h1")
    title = _clean_ws(
        (jp.get("title") or (h1.get_text(" ", strip=True) if h1 else None)) or None
    )

    # ── Company ──
    org = jp.get("hiringOrganization") or {}
    company = _clean_ws(org.get("name"))
    company_url_val = _company_url(soup)

    # ── Location ──
    job_location = jp.get("jobLocation") or []
    if isinstance(job_location, dict):
        job_location = [job_location]
    location_text = None
    if job_location:
        addr = (job_location[0] or {}).get("address") or {}
        location_text = ", ".join(
            str(v).strip() for v in
            (addr.get("addressRegion"), addr.get("addressLocality")) if v
        ) or None

    # ── HTML sections ──
    desc_html = jp.get("description") or _match_section(
        sections, _SECTION_KEYS["description"]
    )
    requirements_html = _match_section(sections, _SECTION_KEYS["requirements"])
    benefits_html = (
        _match_section(sections, _SECTION_KEYS["benefits"])
        or jp.get("jobBenefits")
    )

    # ── List fields (text_to_clean_lines) ──
    description_list = text_to_clean_lines(desc_html)
    if not description_list and title:
        description_list = [title]
    requirements_list = text_to_clean_lines(requirements_html)
    benefits_list = text_to_clean_lines(benefits_html)

    # ── Salary (nested JobSalary object) ──
    salary_node = soup.select_one(".salary")
    salary_display = (
        salary_node.get_text(" ", strip=True) if salary_node else None
    )
    salary = _build_salary(salary_display, jp, title)

    # ── Tags (nested JobTags object) ──
    tags = _build_tags(jp)

    # ── Date fields ──
    deadline_text = _clean_ws(jp.get("validThrough"))
    posted_date = _infer_posted_date(
        _clean_ws(jp.get("datePosted")), deadline_text,
    )

    # ── Plain text for language detection ──
    desc_text = "\n".join(description_list) if description_list else ""
    req_text = "\n".join(requirements_list) if requirements_list else ""
    lang_sample = " ".join(filter(None, [title, desc_text, req_text]))
    language = detect_language(lang_sample)

    # ── Extra: source-specific metadata ──
    extra = {
        "industry": _clean_ws(jp.get("industry")),
        "company_url": company_url_val,
        "experience": jp.get("experienceRequirements"),
    }

    return {
        "title": title,
        "company": company,
        "description_list": description_list,
        "salary": salary,
        "tags": tags,
        "requirements_list": requirements_list,
        "benefits_list": benefits_list,
        "location_text": location_text,
        "deadline_text": deadline_text,
        "posted_date_text": posted_date,
        "employment_type_text": _clean_ws(jp.get("employmentType")),
        "seniority_text": None,  # ITviec không công bố → luôn None
        "extra": extra,
        # Language: dùng ở crawler khi gọi JobRecord.create()
        "language": language,
    }


# ---------------------------------------------------------------- validate

REQUIRED_META_KEYS = (
    "source", "source_job_id", "url", "dedup_key",
    "crawled_at", "batch_id", "crawler_version", "language",
)

IMPORTANT_RAW_KEYS = ("title", "company", "description_list")


def validate_record(record):
    """Return list[str] lỗi nghiêm trọng (rỗng = hợp lệ).

    Kiểm tra theo Data Contract v0.5.0: _meta đủ khoá, raw có title,
    description_list là list, salary là dict, _meta.language bắt buộc.
    """
    errors = []
    meta = record.get("_meta")
    raw = record.get("raw")
    if not isinstance(meta, dict):
        errors.append("_meta không phải dict")
    else:
        for key in REQUIRED_META_KEYS:
            if not meta.get(key):
                errors.append(f"_meta.{key} thiếu")
    if not isinstance(raw, dict):
        errors.append("raw không phải dict")
    else:
        if not raw.get("title"):
            errors.append("raw.title thiếu")
        if not isinstance(raw.get("description_list"), list):
            errors.append("raw.description_list không phải list")
        if raw.get("salary") is not None and not isinstance(raw["salary"], dict):
            errors.append("raw.salary không phải dict")
    return errors


def record_warnings(record):
    """Field quan trọng thiếu → danh sách tên (để log, không loại record)."""
    raw = record.get("raw") or {}
    return [k for k in IMPORTANT_RAW_KEYS if not raw.get(k)]
