# -*- coding: utf-8 -*-
"""Parse HTML ITviec → Python dict.

Owner: Phát

Hai hàm chính:
    parse_listing(html) → list[dict]  (URL + slug của từng job card)
    parse_detail(html)  → dict        (phần `raw` của data contract TASKS.md §4.1)

Nguyên tắc (TASKS.md §4.2 — giữ nguyên văn RAW, không chuẩn hóa):
    - raw gồm 11 field hợp đồng §4.1 + field RAW source-specific (nhóm A).
      KHÔNG có field dẫn xuất/normalized (skills list, seniority suy diễn,
      salary_min/max…) — thuộc tầng Curated do script ELT của Thuận làm.
    - description_html giữ NGUYÊN HTML gốc (không xóa tag).
    - description_text / requirements_text / benefits_text: plain text sạch,
      HTML đã strip + entity đã decode (theo đúng contract §4.2 strip tags).
    - Thiếu field → giá trị None, không crash, không suy diễn
      (seniority_text luôn None vì ITviec không công bố field này).
    - source_job_id: lấy ID trên trang (slug trong URL); nếu không có →
      SHA-256 ổn định của URL đã chuẩn hóa (TASKS.md §4.2).

Selector được chọn dựa trên HTML thực tế ngày 2026-10-05:
    - Listing: div.job-card (20 card/trang). Trong card lấy
      data-search--job-selection-job-slug-value (bền nhất), fallback về
      link tiêu đề h3 a. LƯU Ý: skill tag cũng dẫn tới /viec-lam-it/<skill>
      nên không được lấy mọi anchor trong card.
    - Detail: script JSON-LD @type=JobPosting (server render, ổn định nhất),
      bổ sung các section render div.paragraph có thẻ <h2>.
"""

import hashlib
import json
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

try:  # chạy như package (python -m ...) hoặc chạy trực tiếp từ shell
    from . import config
except ImportError:  # pragma: no cover
    import config

# ---------------------------------------------------------------- URL

# Param tracking/navigation bị loại khi chuẩn hóa URL (TASKS.md §4.2:
# bỏ utm_*, bỏ dấu / cuối, bỏ fragment). Giữ lại `page` để phân trang.
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
    """Fallback source_job_id theo TASKS.md §4.2: SHA-256 ổn định của
    URL đã chuẩn hóa. Dùng khi trang không công khai ID/slug nào."""
    return hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- listing


def parse_listing(html):
    """Trích danh sách job từ trang listing.

    Return: list[dict{"url", "source_job_id", "title"}], đã khử trùng ID
    trong cùng trang, giữ thứ tự hiển thị. Không bao giờ crash vì 1 card lỗi.
    source_job_id = slug của site; card không có slug → SHA-256 URL (fallback).
    """
    soup = BeautifulSoup(html, "html.parser")
    jobs, seen = [], set()
    for card in soup.select("div.job-card"):
        slug = (card.get("data-search--job-selection-job-slug-value") or "").strip()
        title = None
        if slug:
            url = normalize_url(f"{config.BASE_URL}/viec-lam-it/{slug}")
        else:
            # fallback: link tiêu đề trong thẻ h3 của card
            a = card.select_one("h3 a[href]")
            if not a:
                continue  # card không có định danh nào → bỏ qua
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

# Nhóm title của các section render (so khớp substring, không phân biệt hoa thường).
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


def _html_of(fragment):
    """Trả HTML gốc bên trong 1 node, loại bỏ thẻ <h2> tiêu đề của nó."""
    if fragment is None:
        return None
    parts = []
    for child in fragment.children:
        if getattr(child, "name", None) == "h2":
            continue
        parts.append(str(child))
    html = "".join(parts).strip()
    return html or None


def _rendered_sections(soup):
    """Đọc các section render: {heading_text: inner_html}."""
    out = {}
    for div in soup.select("div.paragraph"):
        heading = div.find("h2")
        if heading is None:
            continue
        title = heading.get_text(" ", strip=True)
        body = _html_of(div)
        if title and body:
            out.setdefault(title, body)  # giữ lần xuất hiện đầu tiên
    return out


def _match_section(sections, keywords):
    """Tìm 1 section theo keyword substring (không phân biệt hoa thường)."""
    for title, body in sections.items():
        low = title.lower()
        if any(k in low for k in keywords):
            return body
    return None


def _strip_tags(html_str):
    """Text thuần từ HTML (description_text/…_text phục vụ ML, TASKS.md §4.2).

    BS4 decode HTML entity trong quá trình parse → không còn escape sequence.
    """
    if not html_str:
        return None
    return BeautifulSoup(html_str, "html.parser").get_text("\n", strip=True) or None


def _clean_ws(value):
    """Bỏ khoảng trắng thừa đầu/cuối chuỗi (không đổi ý nghĩa nội dung,
    không chuẩn hóa — chỉ vệ sinh whitespace theo yêu cầu field text)."""
    if isinstance(value, str):
        return value.strip() or None
    return value


def _salary_display_text(soup):
    """Chuỗi lương hiển thị trên page.

    ITviec gate lương sau đăng ký: thường là 'Đăng nhập để xem mức lương'.
    Giữ nguyên văn, không suy diễn.
    """
    node = soup.select_one(".salary")
    if node is None:
        return None
    return node.get_text(" ", strip=True) or None


def _company_url(soup):
    """URL nguyên văn (đã chuẩn hóa) tới trang công ty /nha-tuyen-dung/<slug>."""
    a = soup.find("a", href=re.compile(r"/nha-tuyen-dung/"))
    if a is None:
        return None
    return normalize_url(urljoin(config.BASE_URL, a["href"]))


def parse_detail(html):
    """Parse trang detail ITviec → dict phần `raw` của data contract.

    11 field hợp đồng TASKS.md §4.1 đứng trước (đúng thứ tự tên), sau đó là
    field RAW source-specific nhóm A (nguyên văn JSON-LD/HTML của trang).
    Field dẫn xuất/normalized (skills list, salary_min/max, seniority suy
    diễn…) KHÔNG có ở tầng RAW — thuộc tầng Curated.
    Thiếu field → None/[] để crawler ghi log cảnh báo. Không crash.
    """
    soup = BeautifulSoup(html, "html.parser")
    jp = _find_job_posting(soup)
    sections = _rendered_sections(soup)

    h1 = soup.find("h1")
    title = _clean_ws((jp.get("title") or (h1.get_text(" ", strip=True) if h1 else None)) or None)

    org = jp.get("hiringOrganization") or {}
    company = _clean_ws(org.get("name"))
    company_url = _company_url(soup)

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

    skills_text = _clean_ws(jp.get("skills"))

    desc_html = jp.get("description") or _match_section(sections, _SECTION_KEYS["description"])
    requirements_html = _match_section(sections, _SECTION_KEYS["requirements"])
    benefits_html = (
        _match_section(sections, _SECTION_KEYS["benefits"])
        or jp.get("jobBenefits")
    )

    return {
        # ---------- 11 field hợp đồng (TASKS.md §4.1) ----------
        "title": title,
        "company": company,
        # ITviec gate lương sau đăng nhập; /sign_in có reCAPTCHA → KHÔNG tự
        # động đăng nhập/bypass. salary_text giữ nguyên văn chuỗi hiển thị;
        # nếu source hiển thị lương thật thì selector này tự lấy đúng giá trị.
        "salary_text": _clean_ws(_salary_display_text(soup)),
        "location_text": location_text,
        "skills_text": skills_text,
        "posted_date_text": _clean_ws(jp.get("datePosted")),
        "employment_type_text": _clean_ws(jp.get("employmentType")),
        # ITviec không công bố field seniority nào → luôn None.
        # KHÔNG suy diễn từ title hay experienceRequirements (TASKS.md §4.2).
        "seniority_text": None,
        # description_html: HTML GỐC, không xóa tag (bắt buộc §4.2).
        "description_html": desc_html,
        "description_text": _strip_tags(desc_html),
        "requirements_text": _strip_tags(requirements_html),
        # ---------- Field RAW source-specific (nhóm A: nguyên văn từ trang) ----------
        "company_url": company_url,                    # href gốc của link công ty
        "salary_jsonld": jp.get("baseSalary"),         # baseSalary JSON-LD nguyên văn
        "job_location": job_location,                  # address JSON-LD nguyên văn
        "industry": _clean_ws(jp.get("industry")),
        "valid_through_text": _clean_ws(jp.get("validThrough")),
        "experience_requirements_jsonld": jp.get("experienceRequirements"),
        "requirements_html": requirements_html,       # HTML gốc section yêu cầu
        "benefits_html": benefits_html,
        "benefits_text": _strip_tags(benefits_html),
        # Toàn bộ section render để sau này trích xuất lại, không mất dữ liệu.
        "sections_html": sections or None,
    }


# ---------------------------------------------------------------- validate
# Mô phỏng common/schema.py (chưa tồn tại). _meta bắt buộc theo TASKS.md §4.1.
REQUIRED_META_KEYS = (
    "source", "source_job_id", "url", "dedup_key",
    "crawled_at", "batch_id", "crawler_version",
)

# Crawler ghi warning nếu thiếu, nhưng KHÔNG loại record (raw mỗi nguồn tự quyết).
IMPORTANT_RAW_KEYS = ("title", "company", "description_html")


def validate_record(record):
    """Return list[str] lỗi nghiêm trọng (rỗng = hợp lệ).

    Lỗi nghiêm trọng: _meta thiếu khóa / raw không phải dict /
    cả title lẫn description_html đều trống (bản ghi rác).
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
    elif not raw.get("title") and not raw.get("description_html"):
        errors.append("cả title và description_html đều trống")
    return errors


def record_warnings(record):
    """Field quan trọng thiếu → danh sách tên (để log, không loại record)."""
    raw = record.get("raw") or {}
    return [k for k in IMPORTANT_RAW_KEYS if not raw.get(k)]
