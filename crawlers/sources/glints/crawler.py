# -*- coding: utf-8 -*-
"""Crawler việc làm Glints Việt Nam.

Listing API: GraphQL searchJobsV3.
Chi tiết tin: JSON-LD JobPosting được nhúng trong HTML trang chi tiết.
"""

import json
import logging
import re
import unicodedata
from datetime import datetime, timedelta
from html import unescape
from html.parser import HTMLParser
from typing import Any, Dict, Generator, List, Optional

from crawlers.base.base_crawler import BaseCrawler
from crawlers.common.http_client import DelayConfig, HttpClient
from crawlers.common.schema import JobRecord


SOURCE = "glints"
CRAWLER_VERSION = "0.2.0"
LISTING_URL = (
    "https://glints.com/vn/opportunities/jobs/explore"
    "?country=VN&category=software-engineering"
)
GRAPHQL_ENDPOINT = "https://glints.com/api/v2-alc/graphql?op=searchJobsV3"
PAGE_SIZE = 30

SEARCH_QUERY = r"""
query searchJobsV3($data: JobSearchConditionInput!) {
    searchJobsV3(data: $data) {
        jobsInPage {
            id
            title
            createdAt
            updatedAt
            workArrangementOption
            status
            educationLevel
            type
            jobSource
            minYearsOfExperience
            maxYearsOfExperience
            company {
                id
                name
                brandName
            }
            country {
                code
                name
            }
            location {
                id
                name
                formattedName
                parents {
                    id
                    name
                    formattedName
                    parents {
                        id
                        name
                        formattedName
                    }
                }
            }
            salaries {
                salaryType
                salaryMode
                minAmount
                maxAmount
                CurrencyCode
            }
            skills {
                mustHave
                skill {
                    id
                    name
                }
            }
            hierarchicalJobCategory {
                id
                level
                name
            }
        }
        hasMore
    }
}
"""


class _HTMLTextExtractor(HTMLParser):
    """Chuyển HTML thành văn bản, giữ ngắt dòng ở các phần tử cấu trúc."""

    _BLOCK_TAGS = {
        "address", "article", "blockquote", "div", "h1", "h2", "h3",
        "h4", "h5", "h6", "li", "ol", "p", "section", "ul",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []

    def _line_break(self) -> None:
        if not self.parts or not self.parts[-1].endswith("\n"):
            self.parts.append("\n")

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag == "br":
            self._line_break()
        elif tag in self._BLOCK_TAGS:
            self._line_break()
            if tag == "li":
                self.parts.append("- ")

    def handle_startendtag(self, tag: str, attrs) -> None:
        if tag.lower() == "br":
            self._line_break()

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._BLOCK_TAGS:
            self._line_break()

    def handle_data(self, data: str) -> None:
        if data:
            self.parts.append(data)


def clean_text(value: Any) -> str:
    """Loại bỏ tag HTML và khoảng trắng thừa trong một giá trị văn bản."""
    if value is None:
        return ""
    text = unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def html_to_text(value: Any) -> str:
    """Chuyển HTML thành văn bản thuần, ngắt dòng theo đoạn/danh sách."""
    if value is None:
        return ""
    source = unescape(str(value)).strip()
    if not source:
        return ""

    parser = _HTMLTextExtractor()
    try:
        parser.feed(source)
        parser.close()
        parsed = "".join(parser.parts)
    except Exception:
        # Fallback an toàn khi HTML không hoàn chỉnh.
        parsed = re.sub(
            r"(?i)<br\s*/?>|</(?:p|li|div|h[1-6]|ul|ol)\s*>",
            "\n",
            source,
        )
        parsed = re.sub(r"<[^>]+>", " ", parsed)

    lines: List[str] = []
    for raw_line in parsed.splitlines():
        line = clean_text(raw_line)
        line = re.sub(r"[\t\u00a0 ]+", " ", line).strip()
        if line and (not lines or line != lines[-1]):
            lines.append(line)
    return "\n".join(lines)


def html_to_text_list(value: Any) -> List[str]:
    """Trả nội dung HTML thành danh sách dòng không chứa HTML tag."""
    text = html_to_text(value)
    return [line.strip() for line in text.splitlines() if line.strip()]


def extract_jobposting(html_content: str) -> Dict[str, Any]:
    """Trích JSON-LD JobPosting từ HTML trang chi tiết Glints."""
    if not isinstance(html_content, str) or not html_content:
        return {}

    scripts = re.findall(
        r"<script\b([^>]*)>(.*?)</script\s*>",
        html_content,
        flags=re.IGNORECASE | re.DOTALL,
    )

    for attrs, script in scripts:
        type_match = re.search(
            r'''\btype\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))''',
            attrs,
            flags=re.IGNORECASE,
        )
        script_type = ""
        if type_match:
            script_type = next(
                (group for group in type_match.groups() if group), ""
            ).lower()

        # JobPosting đôi khi nằm trong @graph; ưu tiên thẻ JSON-LD.
        if script_type != "application/ld+json" and '"JobPosting"' not in script:
            continue

        try:
            data = json.loads(unescape(script.strip()))
        except (json.JSONDecodeError, TypeError):
            continue

        candidates = data if isinstance(data, list) else [data]
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            if _is_jobposting(candidate):
                return candidate
            graph = candidate.get("@graph", [])
            if isinstance(graph, list):
                for obj in graph:
                    if isinstance(obj, dict) and _is_jobposting(obj):
                        return obj
    return {}


def _is_jobposting(value: Dict[str, Any]) -> bool:
    kind = value.get("@type")
    return kind == "JobPosting" or (
        isinstance(kind, list) and "JobPosting" in kind
    )


def as_number(value: Any) -> Optional[float]:
    """Chuẩn hóa mức lương về số; không trả về NaN hoặc số không hợp lệ."""
    if value is None or value == "" or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    try:
        number = float(text)
        return number if number == number and abs(number) != float("inf") else None
    except (TypeError, ValueError):
        return None


def format_amount(value: Optional[float]) -> Optional[str]:
    """Hiển thị số tiền dễ đọc, tránh ký pháp khoa học như 9e+06."""
    if value is None:
        return None
    number = float(value)
    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.2f}".rstrip("0").rstrip(".")


def slugify(value: str) -> str:
    """Tạo slug gần với URL công khai của Glints."""
    value = value.replace("đ", "d").replace("Đ", "D")
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")


def _parse_date(value: Any) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _walk_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for nested in value.values():
            yield from _walk_strings(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            yield from _walk_strings(nested)


def _days_left(*values: Any) -> Optional[int]:
    patterns = (
        re.compile(r"\b(\d+)\s+days?\s+left\b", re.IGNORECASE),
        re.compile(r"\bcòn\s+(\d+)\s+ngày\b", re.IGNORECASE),
    )
    for value in values:
        for text in _walk_strings(value):
            for pattern in patterns:
                match = pattern.search(text)
                if match:
                    return int(match.group(1))
    return None


def _normalize_list(value: Any) -> List[str]:
    """Chuẩn hóa danh sách kỹ năng/phúc lợi từ chuỗi hoặc list."""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        candidates = list(value)
    else:
        candidates = re.split(r"[,;\n\r]+", str(value))
    result: List[str] = []
    seen = set()
    for candidate in candidates:
        name = clean_text(candidate)
        key = name.casefold()
        if name and key not in seen:
            seen.add(key)
            result.append(name)
    return result


def _append_unique(target: List[str], values: List[str]) -> None:
    seen = {value.casefold() for value in target}
    for value in values:
        if value and value.casefold() not in seen:
            target.append(value)
            seen.add(value.casefold())


def detect_language(title: str, company: str, description_text: str = "") -> str:
    """Ước lượng ngôn ngữ bài đăng, trả về 'vi' hoặc 'en'."""
    vietnamese_markers = (
        "nhân viên", "tuyển dụng", "kinh doanh", "kế toán", "lập trình",
        "chuyên viên", "thực tập sinh", "tư vấn", "việc làm", "hành chính",
        "nhân sự", "bán hàng", "kỹ thuật", "trách nhiệm", "yêu cầu ứng viên",
        "phúc lợi", "mô tả công việc", "chế độ", "lương thưởng",
    )
    english_markers = (
        "responsibilities", "requirements", "qualifications", "benefits",
        "we are looking", "what you will do", "about the role", "experience",
        "skills", "job description", "work with", "you will be responsible",
    )

    # Nội dung mô tả dài thường thể hiện ngôn ngữ bài đăng chính xác hơn tên công ty.
    primary = (description_text or "").casefold()
    if len(primary.strip()) >= 80:
        vi_score = sum(primary.count(marker) for marker in vietnamese_markers)
        en_score = sum(primary.count(marker) for marker in english_markers)
        accented = len(re.findall(
            r"[ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểệíìỉĩị"
            r"óòỏõọốồổỗộớờởỡợúùủũụứừửựýỳỷỹỵ]",
            primary,
        ))
        if accented >= 5 or vi_score > en_score:
            return "vi"
        return "en"

    fallback = f"{title} {company}".casefold()
    if any(marker in fallback for marker in vietnamese_markers):
        return "vi"
    if re.search(
        r"[ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểệíìỉĩị"
        r"óòỏõọốồổỗộớờởợúùủũụứừửựýỳỷỹỵ]",
        fallback,
    ):
        return "vi"
    return "en"


def _location_text(job_posting: Dict[str, Any], item: Dict[str, Any]) -> str:
    """Lấy địa điểm từ JSON-LD trước, sau đó fallback về listing."""
    parts: List[str] = []
    job_location = job_posting.get("jobLocation") or []
    if isinstance(job_location, dict):
        locations = [job_location]
    elif isinstance(job_location, list):
        locations = job_location
    else:
        locations = []

    for location in locations:
        if not isinstance(location, dict):
            continue
        address = location.get("address") or {}
        if isinstance(address, str):
            _append_unique(parts, [clean_text(address)])
            continue
        if not isinstance(address, dict):
            continue
        country = address.get("addressCountry") or ""
        if isinstance(country, dict):
            country = country.get("name") or country.get("identifier") or ""
        for field in ("addressLocality", "addressRegion", "addressCountry"):
            value = country if field == "addressCountry" else address.get(field)
            value = clean_text(value)
            if value:
                _append_unique(parts, [value])
        if parts:
            break

    if not parts:
        location_data = item.get("location") or {}
        if location_data.get("formattedName"):
            _append_unique(parts, [location_data["formattedName"]])
        elif location_data.get("name"):
            _append_unique(parts, [location_data["name"]])
        for parent in location_data.get("parents") or []:
            name = parent.get("formattedName") or parent.get("name")
            _append_unique(parts, [name] if name else [])
            for grandparent in parent.get("parents") or []:
                name = grandparent.get("formattedName") or grandparent.get("name")
                _append_unique(parts, [name] if name else [])
        country = item.get("country") or {}
        _append_unique(parts, [country.get("name", "")])

    return ", ".join(part for part in parts if part)


class GlintsCrawler(BaseCrawler):
    """Crawler Glints Vietnam, tương thích với BaseCrawler của dự án."""

    source_name = SOURCE
    crawler_version = CRAWLER_VERSION

    def __init__(
        self,
        checkpoint_dir=None,
        output_dir=None,
        max_items=30,
        checkpoint_interval=10,
        http_client=None,
    ):
        super().__init__(
            checkpoint_dir=checkpoint_dir,
            output_dir=output_dir,
            max_items=max_items,
            checkpoint_interval=checkpoint_interval,
        )
        self.http_client = http_client or HttpClient(
            source=self.source_name,
            delay_config=DelayConfig(min_seconds=1.5, max_seconds=3.0),
            timeout=25,
            extra_headers={
                "Accept": "application/json, text/html, */*",
                "Content-Type": "application/json",
                "Origin": "https://glints.com",
                "Referer": LISTING_URL,
                # Tránh nhận Brotli trong môi trường HttpClient chưa giải mã br.
                "Accept-Encoding": "identity",
            },
        )

    def fetch_items(self) -> Generator[Dict[str, Any], None, None]:
        """Lấy tin từ GraphQL, phân trang và tránh ID trùng trong một lượt."""
        page = 1
        seen_ids = set()
        fetched_count = 0

        while self.max_items is None or fetched_count < self.max_items:
            remaining = (
                PAGE_SIZE
                if self.max_items is None
                else max(1, min(PAGE_SIZE, self.max_items - fetched_count))
            )
            payload = {
                "operationName": "searchJobsV3",
                "variables": {
                    "data": {
                        "CountryCode": "VN",
                        "includeExternalJobs": True,
                        "pageSize": remaining,
                        "page": page,
                    }
                },
                "query": SEARCH_QUERY,
            }

            try:
                response = self.http_client.post(
                    GRAPHQL_ENDPOINT,
                    json=payload,
                    apply_delay=True,
                )
                response.raise_for_status()
                body = response.json()
            except Exception:
                logging.exception("Glints: lỗi tải trang danh sách %s", page)
                break

            if not isinstance(body, dict):
                logging.error("Glints: GraphQL trả về dữ liệu không hợp lệ.")
                break
            if body.get("errors"):
                logging.error("Glints GraphQL lỗi ở trang %s: %s", page, body["errors"])
                break

            result = ((body.get("data") or {}).get("searchJobsV3") or {})
            jobs = result.get("jobsInPage") or []
            if not jobs:
                break

            for job in jobs:
                if self.max_items is not None and fetched_count >= self.max_items:
                    break
                job_id = job.get("id")
                if not job_id or job_id in seen_ids:
                    continue
                seen_ids.add(job_id)
                fetched_count += 1
                yield job

            if not result.get("hasMore", False):
                break
            page += 1

    def fetch_jobposting_details(self, url: str) -> Dict[str, Any]:
        """Tải HTML chi tiết và đọc JSON-LD JobPosting."""
        try:
            response = self.http_client.get(url)
            response.raise_for_status()
            html_content = response.text
            if isinstance(html_content, bytes):
                html_content = html_content.decode("utf-8", errors="replace")
            if not isinstance(html_content, str) or not html_content:
                logging.warning("Glints: HTML chi tiết rỗng hoặc không hợp lệ: %s", url)
                return {}

            posting = extract_jobposting(html_content)
            if not posting:
                logging.warning("Glints: không tìm thấy JSON-LD JobPosting tại %s", url)
            return posting
        except Exception:
            logging.warning("Glints: lỗi tải chi tiết việc làm tại %s", url, exc_info=True)
            return {}

    def parse_item(self, item: Dict[str, Any]) -> Optional[JobRecord]:
        """Chuẩn hóa một tin Glints thành JobRecord."""
        job_id = item.get("id")
        listing_title = clean_text(item.get("title"))
        if not job_id or not listing_title:
            return None

        job_url = (
            f"https://glints.com/vn/opportunities/jobs/"
            f"{slugify(listing_title)}/{job_id}"
        )
        job_posting = self.fetch_jobposting_details(job_url)

        title = clean_text(job_posting.get("title") or listing_title)
        company_data = item.get("company") or {}
        hiring_org = job_posting.get("hiringOrganization") or {}
        company = clean_text(
            hiring_org.get("name")
            or company_data.get("brandName")
            or company_data.get("name")
            or "Unknown"
        )

        description_html = job_posting.get("description") or ""
        description_text = html_to_text(description_html)
        description_list = html_to_text_list(description_html)
        description_available = bool(description_text.strip())
        if not description_list:
            # Base schema yêu cầu description_list không rỗng.
            description_list = [
                "Description unavailable in the Glints job detail page."
            ]

        # Salary JSON-LD được ưu tiên; fallback sang GraphQL listing.
        base_salary = job_posting.get("baseSalary") or {}
        salary_value = base_salary.get("value") or {}
        if not isinstance(salary_value, dict):
            salary_value = {"value": salary_value}
        salary_listing = (item.get("salaries") or [{}])[0] or {}

        salary_min = as_number(
            salary_value.get("minValue", salary_listing.get("minAmount"))
        )
        salary_max = as_number(
            salary_value.get("maxValue", salary_listing.get("maxAmount"))
        )
        salary_currency = (
            base_salary.get("currency")
            or salary_listing.get("CurrencyCode")
        )
        pay_period = (
            salary_value.get("unitText")
            or salary_listing.get("salaryMode")
        )

        salary_text = None
        if salary_min is not None or salary_max is not None:
            if salary_min is not None and salary_max is not None:
                salary_text = f"{format_amount(salary_min)} - {format_amount(salary_max)}"
            elif salary_min is not None:
                salary_text = f"From {format_amount(salary_min)}"
            else:
                salary_text = f"Up to {format_amount(salary_max)}"
            if salary_currency:
                salary_text += f" {salary_currency}"
            if pay_period:
                salary_text += f" / {str(pay_period).lower()}"

        salary = None
        if salary_min is not None or salary_max is not None or salary_currency or salary_text:
            salary = {
                "salary_text": salary_text,
                "salary_min": salary_min,
                "salary_max": salary_max,
                "salary_currency": salary_currency,
                "pay_period": pay_period,
                "is_negotiable": False,
                "has_commission": False,
            }

        # Kỹ năng: hợp nhất GraphQL skills và schema.org skills.
        skills: List[str] = []
        requirements: List[str] = []
        for entry in item.get("skills") or []:
            if not isinstance(entry, dict):
                continue
            skill_name = clean_text((entry.get("skill") or {}).get("name"))
            if skill_name:
                _append_unique(skills, [skill_name])
                if entry.get("mustHave"):
                    _append_unique(requirements, [skill_name])
        _append_unique(skills, _normalize_list(job_posting.get("skills")))

        # Nếu JSON-LD không chia rõ yêu cầu bắt buộc, dùng mustHave từ listing.
        if not requirements:
            requirements = skills.copy()

        benefits = _normalize_list(job_posting.get("jobBenefits"))
        deadline_text = clean_text(
            job_posting.get("validThrough")
            or item.get("deadlineText")
            or item.get("deadline_text")
        )
        posted_date_text = clean_text(
            job_posting.get("datePosted") or item.get("createdAt") or ""
        )
        if not posted_date_text:
            days_left = _days_left(item, job_posting)
            deadline_dt = _parse_date(deadline_text)
            if days_left is not None and deadline_dt is not None:
                posted_date_text = (deadline_dt - timedelta(days=days_left)).date().isoformat()

        min_exp = item.get("minYearsOfExperience")
        max_exp = item.get("maxYearsOfExperience")
        seniority_parts = []
        if min_exp is not None and max_exp is not None:
            seniority_parts.append(f"{min_exp}-{max_exp} years of experience")
        elif min_exp is not None:
            seniority_parts.append(f"At least {min_exp} years of experience")
        elif max_exp is not None:
            seniority_parts.append(f"Up to {max_exp} years of experience")
        experience = job_posting.get("experienceRequirements") or {}
        months_exp = experience.get("monthsOfExperience")
        if not seniority_parts and months_exp is not None:
            seniority_parts.append(f"{months_exp} months of experience")

        employment_type = clean_text(
            job_posting.get("employmentType") or item.get("type") or ""
        )
        work_arrangement = clean_text(item.get("workArrangementOption") or "")
        if job_posting.get("jobLocationType") == "TELECOMMUTE" and not work_arrangement:
            work_arrangement = "REMOTE"

        location_text = _location_text(job_posting, item)
        language = detect_language(title, company, description_text)
        company_identifier = job_posting.get("identifier") or {}
        company_id = (
            company_identifier.get("value")
            or company_data.get("id")
        )

        industry = job_posting.get("industry")
        category = job_posting.get("occupationalCategory") or (
            (item.get("hierarchicalJobCategory") or {}).get("name")
        )

        raw_data = {
            "title": title,
            "company": company,
            # description_html giữ HTML gốc để truy vết; description_text đã bỏ toàn bộ tag.
            "description_html": description_html,
            "description_text": description_text,
            "description_list": description_list,
            "salary": salary,
            "tags": {
                "skills": skills,
                "requirements": requirements,
                "benefits": benefits,
            },
            "requirements_list": requirements,
            "benefits_list": benefits,
            "location_text": location_text,
            "deadline_text": deadline_text,
            "posted_date_text": posted_date_text,
            "employment_type_text": employment_type,
            "seniority_text": "; ".join(seniority_parts),
            "extra": {
                "company_id": company_id,
                "industry": industry,
                "job_type": employment_type,
                "work_arrangement": work_arrangement,
                "created_at": item.get("createdAt"),
                "updated_at": item.get("updatedAt"),
                "education_level": item.get("educationLevel"),
                "job_source": item.get("jobSource"),
                "category": category,
                "description_available": description_available,
                "description_source": "json_ld" if description_available else None,
                "valid_through": job_posting.get("validThrough"),
                "job_location_type": job_posting.get("jobLocationType"),
                "source_url": job_url,
            },
        }

        try:
            return JobRecord.create(
                source=self.source_name,
                source_job_id=str(job_id),
                url=job_url,
                batch_id=self.batch_id,
                raw_data=raw_data,
                crawler_version=self.crawler_version,
                language=language,
            )
        except Exception:
            logging.exception("Glints: không thể chuẩn hóa job id=%s", job_id)
            return None
