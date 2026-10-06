"""
parser.py - Module bóc tách HTML DOM & trích xuất JSON schema
Xử lý toàn bộ logic parsing từ page_source thô sang cấu trúc dữ liệu chuẩn.
"""

import re
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _safe_text(element: Optional[Tag], default: str = "") -> str:
    """Lấy text từ Tag, trả về default nếu None."""
    if element is None:
        return default
    return element.get_text(separator=" ", strip=True)


def _safe_attr(element: Optional[Tag], attr: str, default: str = "") -> str:
    """Lấy attribute từ Tag, trả về default nếu None."""
    if element is None:
        return default
    return element.get(attr, default) or default


def _normalize_url(url: str, base_url: str = "https://careerviet.vn") -> str:
    """Chuẩn hóa URL (thêm base nếu thiếu scheme)."""
    if not url:
        return ""
    url = url.strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return base_url + url
    return url


def extract_job_id(url: str) -> str:
    """
    Bóc tách job_id từ URL CareerViet.
    Ví dụ: https://careerviet.vn/vi/tim-viec-lam/data-engineer.35C541AE.html
           → "35C541AE"
    Fallback: MD5 hash 8 ký tự của URL nếu không parse được.
    """
    # Pattern: chuỗi ký tự chữ-số viết HOA trước .html
    match = re.search(r'\.([A-Z0-9]{6,12})\.html', url)
    if match:
        return match.group(1)

    # Pattern thứ 2: số ID đơn thuần ở cuối đường dẫn
    match2 = re.search(r'/(\d{5,12})(?:\.html)?$', url)
    if match2:
        return match2.group(1)

    # Fallback: hash URL
    return hashlib.md5(url.encode()).hexdigest()[:8].upper()


def extract_job_links_from_listing(html: str, base_url: str = "https://careerviet.vn") -> list[str]:
    """
    Bóc tách toàn bộ link việc làm từ trang listing (kết quả tìm kiếm).
    Trả về danh sách URL đầy đủ.
    """
    soup = BeautifulSoup(html, "lxml")
    links = []

    # Selector 1: Thẻ a có class job-title trong div.job-item
    for a_tag in soup.select("div.job-item a.job-title"):
        href = _safe_attr(a_tag, "href")
        if href and "/tim-viec-lam/" in href:
            links.append(_normalize_url(href, base_url))

    # Selector 2: Fallback – tìm bất kỳ link nào có pattern URL job
    if not links:
        for a_tag in soup.select("a[href*='/tim-viec-lam/']"):
            href = _safe_attr(a_tag, "href")
            if href and re.search(r'\.[A-Z0-9]{6,12}\.html', href):
                links.append(_normalize_url(href, base_url))

    # Selector 3: Fallback thứ 3 – a có class job-item__title
    if not links:
        for a_tag in soup.select("a.job-item__title, h3.title a, h2.title a"):
            href = _safe_attr(a_tag, "href")
            if href:
                links.append(_normalize_url(href, base_url))

    # Loại bỏ trùng lặp trong listing (giữ thứ tự)
    seen = set()
    unique_links = []
    for link in links:
        if link and link not in seen:
            seen.add(link)
            unique_links.append(link)

    return unique_links


def has_next_page(html: str) -> bool:
    """Kiểm tra trang listing có trang tiếp theo không."""
    soup = BeautifulSoup(html, "lxml")

    # Kiểm tra nút next-page của CareerViet
    next_btn = soup.select_one("li.next-page")
    if next_btn:
        classes = next_btn.get("class", [])
        return "disabled" not in classes

    if soup.select("a.page-link[rel='next'], a[rel='next']"):
        return True

    return False


# ============================================================
# MAIN PARSER: Bóc tách nội dung chi tiết job
# ============================================================

class JobDetailParser:
    """
    Parse HTML của một trang chi tiết việc làm CareerViet
    → Trả về dict theo schema chuẩn.
    """

    def __init__(self, html: str, url: str, category_name: str):
        self.soup = BeautifulSoup(html, "lxml")
        self.url = url
        self.category_name = category_name
        self.job_id = extract_job_id(url)

    # ----------------------------------------------------------
    # PUBLIC METHOD
    # ----------------------------------------------------------
    def parse(self) -> dict:
        """
        Bóc tách toàn bộ thông tin, trả về dict theo schema yêu cầu.
        Bắt tất cả exception nội bộ, không để crash caller.
        """
        try:
            return self._build_record()
        except Exception as exc:
            logger.error(f"[Parser] Lỗi khi parse {self.url}: {exc}", exc_info=True)
            return self._empty_record()

    # ----------------------------------------------------------
    # INTERNAL BUILD
    # ----------------------------------------------------------
    def _build_record(self) -> dict:
        info_map = self._parse_info_block()

        return {
            "job_id":              self.job_id,
            "crawled_category":    self.category_name,
            "url":                 self.url,
            "title":               self._parse_title(),
            "company_name":        self._parse_company_name(),
            "company_url":         self._parse_company_url(),
            "salary_raw":          info_map.get("salary", ""),
            "location_city":       self._parse_location_city(),
            "location_address":    self._parse_location_address(),
            "posted_date":         info_map.get("posted_date") or self._parse_posted_date(),
            "deadline_date":       info_map.get("deadline", ""),
            "experience_raw":      info_map.get("experience", ""),
            "job_level":           info_map.get("job_level", ""),
            "employment_type":     info_map.get("employment_type", ""),
            "industries_raw":      info_map.get("industries", ""),
            "tags":                self._parse_tags(),
            "education_raw":       info_map.get("education", ""),
            "job_description_raw": self._parse_description_section(),
            "job_requirements_raw":self._parse_requirements_section(),
            "benefits_raw":        self._parse_benefits_section(),
            "crawled_at":          datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    def _empty_record(self) -> dict:
        """Record rỗng khi parse thất bại hoàn toàn."""
        return {
            "job_id":              self.job_id,
            "crawled_category":    self.category_name,
            "url":                 self.url,
            "title":               "",
            "company_name":        "",
            "company_url":         "",
            "salary_raw":          "",
            "location_city":       "",
            "location_address":    "",
            "posted_date":         "",
            "deadline_date":       "",
            "experience_raw":      "",
            "job_level":           "",
            "employment_type":     "",
            "industries_raw":      "",
            "tags":                [],
            "education_raw":       "",
            "job_description_raw": [],
            "job_requirements_raw":[],
            "benefits_raw":        [],
            "crawled_at":          datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "_parse_error":        True,
        }

    # ----------------------------------------------------------
    # TITLE
    # ----------------------------------------------------------
    def _parse_title(self) -> str:
        selectors = [
            "div.job-desc h1.title",
            "h1.title",
            "div.title-block h1",
            "h1",
        ]
        for sel in selectors:
            el = self.soup.select_one(sel)
            if el:
                return _safe_text(el)
        return ""

    # ----------------------------------------------------------
    # COMPANY
    # ----------------------------------------------------------
    def _parse_company_name(self) -> str:
        selectors = [
            "a.employer.job-company-name",
            "div.company-info a.company-name",
            "a.job-company-name",
            "div.employer-info a",
            "p.company-name a",
        ]
        for sel in selectors:
            el = self.soup.select_one(sel)
            if el:
                return _safe_text(el)
        return ""

    def _parse_company_url(self) -> str:
        selectors = [
            "a.employer.job-company-name",
            "div.company-info a.company-name",
            "a.job-company-name",
        ]
        for sel in selectors:
            el = self.soup.select_one(sel)
            if el:
                href = _safe_attr(el, "href")
                return _normalize_url(href)
        return ""

    # ----------------------------------------------------------
    # INFO BLOCK: Lương / Kinh nghiệm / Cấp bậc / Hạn nộp / ...
    # ----------------------------------------------------------
    # Mapping từ label (vi) → key trong output schema
    _INFO_LABEL_MAP = {
        # Ngày đăng / Cập nhật
        "ngày cập nhật":   "posted_date",
        "cập nhật":        "posted_date",
        "posted date":     "posted_date",
        # Lương
        "lương":           "salary",
        "mức lương":       "salary",
        "salary":          "salary",
        # Kinh nghiệm
        "kinh nghiệm":     "experience",
        "experience":      "experience",
        # Cấp bậc
        "cấp bậc":         "job_level",
        "job level":       "job_level",
        # Hình thức
        "hình thức làm việc": "employment_type",
        "hình thức":       "employment_type",
        "loại hình":       "employment_type",
        "job type":        "employment_type",
        # Hạn nộp
        "hạn nộp hồ sơ":  "deadline",
        "hạn nộp":        "deadline",
        "hết hạn nộp":    "deadline",
        "deadline":        "deadline",
        # Ngành nghề
        "ngành nghề":      "industries",
        "industry":        "industries",
        # Học vấn
        "học vấn":         "education",
        "bằng cấp":        "education",
        "education":       "education",
        # Địa điểm (thêm vào map phụ)
        "địa điểm":        "location",
    }

    def _parse_info_block(self) -> dict:
        """
        Quét các block li trong phần info summary (.bg-blue li hoặc ul.job-info li).
        Trả về dict: { "salary": "...", "experience": "...", ... }
        """
        result = {}
        selectors = [
            ".bg-blue li",
            "div.bg-blue li",
            "ul.job-info li",
            "div.job-summary li",
            "div.box-general li",
            "div.general-info li",
        ]

        items = []
        for sel in selectors:
            items = self.soup.select(sel)
            if items:
                break

        for li in items:
            label_el = li.select_one("strong, label, span.label, b, .title-label")
            # Ưu tiên p trước để tránh lấy trúng span con của strong
            value_el = li.find("p") or li.select_one("div.content, span:not(.label):not(.title-label)")

            if not label_el:
                # Thử split text theo ":" nếu không có thẻ label riêng
                full_text = _safe_text(li)
                if ":" in full_text:
                    parts = full_text.split(":", 1)
                    label_text = parts[0].strip().lower()
                    value_text = parts[1].strip()
                else:
                    continue
            else:
                label_text = _safe_text(label_el).lower().rstrip(":")
                # Value = text còn lại sau khi bỏ label
                value_text = _safe_text(li).replace(_safe_text(label_el), "", 1).strip()
                if value_el:
                    value_text = _safe_text(value_el)

            # Map label → key
            mapped_key = None
            for keyword, key in self._INFO_LABEL_MAP.items():
                if keyword in label_text:
                    mapped_key = key
                    break

            if mapped_key and value_text:
                result[mapped_key] = value_text

        # Fallback: tìm từng field riêng nếu info_block rỗng
        if not result:
            result = self._fallback_parse_info()

        return result

    def _fallback_parse_info(self) -> dict:
        """Fallback: tìm theo các selector riêng lẻ cho từng field."""
        result = {}

        # Salary
        for sel in ["span.salary-text", "div.salary", "p.salary"]:
            el = self.soup.select_one(sel)
            if el:
                result["salary"] = _safe_text(el)
                break

        # Experience
        for sel in ["span.exp-text", "div.experience", "li.exp"]:
            el = self.soup.select_one(sel)
            if el:
                result["experience"] = _safe_text(el)
                break

        return result

    # ----------------------------------------------------------
    # LOCATION
    # ----------------------------------------------------------
    def _parse_location_city(self) -> str:
        selectors = [
            "div.info-place-detail .place",
            "div.detail-row.info-place-detail .place",
            ".place",
            "div.detail-row.info-place-detail span.city",
            "div.info-place-detail span.city",
            "div.location span.city",
            "span.location-city",
        ]
        for sel in selectors:
            el = self.soup.select_one(sel)
            if el:
                return _safe_text(el)

        # Fallback: tìm trong info_block theo key "location"
        loc_els = self.soup.select("ul.job-info li, .bg-blue li")
        for li in loc_els:
            text = _safe_text(li).lower()
            if "địa điểm" in text or "location" in text:
                return _safe_text(li).split(":", 1)[-1].strip()

        return ""

    def _parse_location_address(self) -> str:
        # Ưu tiên lấy trực tiếp span trong info-place-detail
        addr_el = self.soup.select_one("div.info-place-detail span, div.detail-row.info-place-detail span")
        if addr_el:
            addr = _safe_text(addr_el)
            if addr:
                return addr

        selectors = [
            "div.detail-row.info-place-detail",
            "div.info-place-detail",
            "div.job-address",
            "div.work-location",
        ]
        for sel in selectors:
            el = self.soup.select_one(sel)
            if el:
                # Loại bỏ label "Địa điểm làm việc:"
                text = _safe_text(el)
                text = re.sub(r'^(Địa điểm làm việc|Địa điểm|Location)\s*[:\-]?\s*', '', text, flags=re.IGNORECASE).strip()
                if text:
                    return text
        return ""

    # ----------------------------------------------------------
    # DATES
    # ----------------------------------------------------------
    def _parse_posted_date(self) -> str:
        selectors = [
            "div.job-desc .posted-date",
            "span.posted-date",
            "div.post-date",
            "span.date-post",
            "div.deadline",
        ]
        for sel in selectors:
            el = self.soup.select_one(sel)
            if el:
                text = _safe_text(el)
                # Tìm pattern ngày tháng: dd/mm/yyyy
                date_match = re.search(r'\d{1,2}/\d{1,2}/\d{4}', text)
                if date_match:
                    return date_match.group()
                return text

        # Fallback: tìm trong meta tags
        meta = self.soup.find("meta", {"itemprop": "datePosted"})
        if meta:
            return _safe_attr(meta, "content")

        return ""

    # ----------------------------------------------------------
    # TAGS / KỸ NĂNG
    # ----------------------------------------------------------
    def _parse_tags(self) -> list[str]:
        selectors = [
            ".job-tags ul li a",
            ".tag-list li a",
            "div.skill-tags a",
            "div.tags a",
            "ul.skills li",
        ]
        tags = []
        for sel in selectors:
            els = self.soup.select(sel)
            if els:
                tags = [_safe_text(el) for el in els if _safe_text(el)]
                break

        return list(dict.fromkeys(tags))  # Giữ thứ tự, loại trùng

    # ----------------------------------------------------------
    # DESCRIPTION / REQUIREMENTS / BENEFITS
    # ----------------------------------------------------------
    def _parse_content_sections(self) -> dict:
        """
        Parse tất cả div.detail-row.reset-bullet, phân loại theo heading h2/h3.
        Trả về { "description": [...], "requirements": [...], "benefits": [...] }
        """
        sections = {
            "description":  [],
            "requirements": [],
            "benefits":     [],
        }

        # Keywords để phân loại heading
        SECTION_MAP = {
            "description":  ["mô tả công việc", "job description", "công việc cụ thể",
                             "mô tả", "trách nhiệm", "nhiệm vụ"],
            "requirements": ["yêu cầu công việc", "yêu cầu ứng viên", "requirements",
                             "yêu cầu", "kỹ năng cần có"],
            "benefits":     ["quyền lợi", "phúc lợi", "benefits", "chế độ đãi ngộ",
                             "chính sách"],
        }

        current_section = "description"  # Default section

        # Tìm tất cả các block nội dung
        content_blocks = self.soup.select(
            "div.detail-row.reset-bullet, "
            "div.job-detail-content, "
            "div.full-content section, "
            "div.job-description"
        )

        if not content_blocks:
            # Fallback: tìm các div có nội dung lớn
            content_blocks = self.soup.select("div.content-tab, div.tab-content")

        for block in content_blocks:
            heading = block.select_one("h2, h3, h4, .section-title")
            if heading:
                heading_text = _safe_text(heading).lower()
                for section_key, keywords in SECTION_MAP.items():
                    if any(kw in heading_text for kw in keywords):
                        current_section = section_key
                        break

            # Lấy các đoạn nội dung (li, p, div.item)
            paragraphs = self._extract_paragraphs(block)
            sections[current_section].extend(paragraphs)

        # Nếu không parse được gì, thử fallback selector
        if not any(sections.values()):
            sections = self._fallback_content_parse()

        # Loại bỏ trùng lặp trong từng section
        for key in sections:
            seen = set()
            unique = []
            for item in sections[key]:
                if item and item not in seen:
                    seen.add(item)
                    unique.append(item)
            sections[key] = unique

        return sections

    def _extract_paragraphs(self, block: Tag) -> list[str]:
        """Lấy text từ các thẻ li, p trong block."""
        results = []

        # Ưu tiên li items
        li_items = block.select("li")
        if li_items:
            for li in li_items:
                text = _safe_text(li)
                if text and len(text) > 3:
                    results.append(text)
        else:
            # Fallback: lấy p tags
            for p in block.select("p"):
                text = _safe_text(p)
                if text and len(text) > 3:
                    results.append(text)

            # Nếu không có p, lấy toàn bộ text của block
            if not results:
                full_text = _safe_text(block)
                if full_text and len(full_text) > 10:
                    # Split theo dấu xuống dòng
                    lines = [line.strip() for line in full_text.split("\n") if line.strip()]
                    results.extend(lines)

        return results

    def _fallback_content_parse(self) -> dict:
        """
        Fallback khi DOM không khớp selector chính.
        Tìm các section theo pattern h2/h3 + ul/ol tiếp theo.
        """
        sections = {"description": [], "requirements": [], "benefits": []}

        all_headings = self.soup.select("h2, h3")
        for heading in all_headings:
            heading_text = _safe_text(heading).lower()

            # Xác định section
            if any(kw in heading_text for kw in ["mô tả", "trách nhiệm", "job description"]):
                target = "description"
            elif any(kw in heading_text for kw in ["yêu cầu", "requirements"]):
                target = "requirements"
            elif any(kw in heading_text for kw in ["quyền lợi", "phúc lợi", "benefits"]):
                target = "benefits"
            else:
                continue

            # Lấy sibling ul/ol/p tiếp theo
            sibling = heading.find_next_sibling()
            while sibling and sibling.name not in ["h2", "h3"]:
                if sibling.name in ["ul", "ol"]:
                    for li in sibling.select("li"):
                        text = _safe_text(li)
                        if text:
                            sections[target].append(text)
                elif sibling.name == "p":
                    text = _safe_text(sibling)
                    if text:
                        sections[target].append(text)
                sibling = sibling.find_next_sibling()

        return sections

    def _parse_description_section(self) -> list[str]:
        return self._parse_content_sections()["description"]

    def _parse_requirements_section(self) -> list[str]:
        return self._parse_content_sections()["requirements"]

    def _parse_benefits_section(self) -> list[str]:
        return self._parse_content_sections()["benefits"]
