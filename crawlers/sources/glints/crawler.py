# -*- coding: utf-8 -*-
"""Crawler việc làm Glints Việt Nam.

Listing API: GraphQL searchJobsV3.
Chi tiết tin: JSON-LD JobPosting được nhúng trong HTML trang chi tiết.
"""

import json
import logging
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from bs4 import BeautifulSoup

from crawlers.base.base_crawler import BaseCrawler
from crawlers.common.http_client import DelayConfig, HttpClient
from crawlers.common.schema import JobRecord, RawJobEnvelope
from crawlers.common.url_ledger import (
    UrlLedger,
    clean_canonical_url,
    calculate_json_canonical_hash,
    calculate_json_field_hashes,
)
from crawlers.common.anti_blocking import (
    polite_sleep,
    human_like_interaction,
    handle_cloudflare_backoff,
    is_cloudflare_challenge,
)


SOURCE = "glints"
CRAWLER_VERSION = "0.2.0"
LISTING_URL = "https://glints.com/vn/job-category/computer-software"
GRAPHQL_ENDPOINT = "https://glints.com/api/v2-alc/graphql?op=searchJobsV3"
PAGE_SIZE = 30
# Category ID lấy từ request GraphQL của trang Computer & Software trên Glints.
IT_CATEGORY_IDS = (
    "9dd9bc4d-38d5-4b5e-876a-de19bc22da45",
)
# Phạm vi IT cho dự án VN-IT-Job-Mining.
# Dựa trên tên danh mục, tiêu đề và kỹ năng kỹ thuật
# mà GraphQL listing trả về.

_IT_CATEGORY_TERMS = (
    "computer & software",
    "software engineering",
    "software architect",
    "technical manager",
    "system analyst",
    "system administrator",
    "database administrator",
    "network engineer",
    "technical support engineer",
    "devops engineer",
    "system security",
    "cloud engineer",
    "cybersecurity",
    "it support",
    "data analyst",
    "data engineer",
    "data scientist",
    "data mining",
    "data warehouse",
    "qa engineer",
    "qa manager",
    "other testing positions",
    "manual tester",
    "test development",
    "mobile developer",
    "android developer",
    "frontend developer",
    "wordpress developer",
    "flutter developer",
    "backend developer",
    "full stack developer",
    "game developer",
    "ai engineer",
    "algorithm researcher",
    "embedded engineer",
    "hardware engineer",
    "driver developer",
    "ui/ux designer",
)

_IT_TITLE_TERMS = (
    "software engineer",
    "software developer",
    "web developer",
    "application developer",
    "backend",
    "back-end",
    "frontend",
    "front-end",
    "full stack",
    "fullstack",
    "programmer",
    "devops",
    "site reliability",
    "qa engineer",
    "quality assurance engineer",
    "software tester",
    "test automation",
    "data analyst",
    "data engineer",
    "data scientist",
    "database administrator",
    "network engineer",
    "cybersecurity",
    "cyber security",
    "security engineer",
    "cloud engineer",
    "system administrator",
    "systems administrator",
    "system analyst",
    "it support",
    "technical support engineer",
    "mobile developer",
    "android developer",
    "ios developer",
    "flutter developer",
    "game developer",
    "embedded engineer",
    "hardware engineer",
    "firmware engineer",
    "machine learning engineer",
    "artificial intelligence engineer",
    "ui/ux designer",
    "ux designer",
    "lập trình viên",
    "kỹ sư phần mềm",
    "kiểm thử phần mềm",
    "kỹ sư dữ liệu",
    "khoa học dữ liệu",
    "an ninh mạng",
    "quản trị hệ thống",
    "quản trị mạng",
    "hỗ trợ công nghệ thông tin",
    "trí tuệ nhân tạo",
    "kỹ sư nhúng",
)

_IT_SKILL_TERMS = (
    "python",
    "javascript",
    "typescript",
    "java",
    "c++",
    "c#",
    "golang",
    "rust",
    "php",
    "kotlin",
    "swift",
    "sql",
    "react",
    "node.js",
    "angular",
    "vue.js",
    "django",
    "flask",
    "spring boot",
    ".net",
    "docker",
    "kubernetes",
    "aws",
    "azure",
    "google cloud",
    "terraform",
    "linux",
    "automation-testing",
    "cypress",
    "playwright",
    "tensorflow",
    "pytorch",
    "postgresql",
    "mysql",
    "mongodb",
    "graphql",
    "rest api",
)


def is_it_job(job):
    """Trả về True nếu tin phù hợp phạm vi IT của dự án."""
    if not isinstance(job, dict):
        return False

    title = str(job.get("title") or "").casefold()

    category_obj = job.get("hierarchicalJobCategory") or {}
    if isinstance(category_obj, dict):
        category = str(category_obj.get("name") or "").casefold()
    else:
        category = ""

    if any(term in category for term in _IT_CATEGORY_TERMS):
        return True

    if any(term in title for term in _IT_TITLE_TERMS):
        return True

    skill_names = []
    for entry in job.get("skills") or []:
        if not isinstance(entry, dict):
            continue

        skill_obj = entry.get("skill") or {}
        if isinstance(skill_obj, dict):
            name = skill_obj.get("name")
            if name:
                skill_names.append(str(name).casefold())

    skill_text = " | ".join(skill_names)
    return any(term in skill_text for term in _IT_SKILL_TERMS)


SEARCH_QUERY = r"""
query searchJobsV3($data: JobSearchConditionInput!) {
    searchJobsV3(data: $data) {
        jobsInPage {
            id
            title
            workArrangementOption
            status
            createdAt
            updatedAt
            isHot
            isApplied
            shouldShowSalary
            educationLevel
            type
            fraudReportFlag
            company {
                ...CompanyFields
                __typename
            }
            citySubDivision {
                id
                name
                __typename
            }
            city {
                ...CityFields
                __typename
            }
            country {
                ...CountryFields
                __typename
            }
            salaries {
                ...SalaryFields
                __typename
            }
            location {
                ...LocationFields
                __typename
            }
            minYearsOfExperience
            maxYearsOfExperience
            source
            jobSource
            hierarchicalJobCategory {
                id
                level
                name
                children {
                    name
                    level
                    id
                    __typename
                }
                parents {
                    id
                    level
                    name
                    __typename
                }
                __typename
            }
            skills {
                skill {
                    id
                    name
                    __typename
                }
                mustHave
                __typename
            }
            traceInfo
            __typename
        }
        expInfo
        hasMore
        __typename
    }
}

fragment CompanyFields on Company {
  id
  name
  brandName
  logo
  status
  isVIP
  IndustryId
  industry {
    id
    name
    __typename
  }
  verificationTier {
    type
    userName
    __typename
  }
  __typename
}

fragment CityFields on City {
  id
  name
  __typename
}

fragment CountryFields on Country {
  code
  name
  __typename
}

fragment SalaryFields on JobSalary {
  id
  salaryType
  salaryMode
  maxAmount
  minAmount
  CurrencyCode
  __typename
}

fragment LocationFields on HierarchicalLocation {
  id
  name
  administrativeLevelName
  formattedName
  level
  slug
  latitude
  longitude
  parents {
    id
    name
    administrativeLevelName
    formattedName
    level
    slug
    CountryCode: countryCode
    parents {
      level
      formattedName
      slug
      __typename
    }
    __typename
  }
  __typename
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


def extract_raw_envelope_from_html(
    html: str,
    job_id: str,
    url: str,
    scraper_version: str = "2.0.0",
) -> RawJobEnvelope:
    """Bóc tách dữ liệu DOM thô và JSON-LD của Glints thành RawJobEnvelope chuẩn SD1 (Zero Information Loss)."""
    soup = BeautifulSoup(html or "", "html.parser")

    # 1. Trích xuất JSON-LD JobPosting nguyên bản (nếu có)
    job_posting_jsonld = None
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            raw_text = script.string or script.get_text()
            if not raw_text:
                continue
            loaded = json.loads(raw_text.strip())
            if isinstance(loaded, dict) and loaded.get("@type") == "JobPosting":
                job_posting_jsonld = loaded
                break
            elif isinstance(loaded, list):
                for item in loaded:
                    if isinstance(item, dict) and item.get("@type") == "JobPosting":
                        job_posting_jsonld = item
                        break
                if job_posting_jsonld:
                    break
        except Exception:
            continue

    # 2. Bóc tách các thành phần DOM theo đúng CSS Class name nguyên bản của Glints
    title_el = soup.select_one("h1.job-title, h1[class*='JobTitle'], h1")
    title = clean_text(title_el.get_text(strip=True)) if title_el else ""

    comp_el = soup.select_one(".company-name, [class*='CompanyName'], a[href*='/companies/'], .hiring-organization")
    company = clean_text(comp_el.get_text(strip=True)) if comp_el else ""

    salary_el = soup.select_one("[class*='SalaryJobOverview'], .salary-text, .salary:not(.negotiable-salary), .job-salary, .badge-salary")
    salary_raw = clean_text(salary_el.get_text(strip=True)) if salary_el else "Thương lượng"

    desc_el = soup.select_one(".description, [class*='JobDescription'], [data-testid='job-description'], .job-posting-container .description")
    description = desc_el.get_text(separator="\n", strip=True) if desc_el else ""

    req_el = soup.select_one(".requirements, [class*='JobRequirements'], [data-testid='job-requirements'], .job-posting-container .requirements")
    requirements = req_el.get_text(separator="\n", strip=True) if req_el else ""

    benefits_el = soup.select_one(".benefits, [class*='BenefitsContainer'], .job-posting-container .benefits")
    benefits = benefits_el.get_text(separator="\n", strip=True) if benefits_el else ""

    skills_el = soup.select_one(".skills-tags, [class*='SkillsContainer'], .job-posting-container .skills-tags")
    skills = skills_el.get_text(separator=" | ", strip=True) if skills_el else ""

    container_el = soup.select_one(".job-posting-container, .job-detail, main, body")
    container_text = container_el.get_text(separator=" ", strip=True) if container_el else ""

    raw_payload = {
        "job-title": title,
        "company-name": company,
        "salary": salary_raw,
        "description": description,
        "requirements": requirements,
        "benefits": benefits,
        "skills": skills,
        "container_content": container_text[:5000],
    }
    if job_posting_jsonld:
        raw_payload["job_posting_jsonld"] = job_posting_jsonld

    now_iso = datetime.now(timezone.utc).isoformat()
    content_hash = calculate_json_canonical_hash(raw_payload)
    field_hashes = calculate_json_field_hashes(raw_payload)
    lang = detect_language(title=title, company=company, description_text=description)

    metadata = {
        "job_id": str(job_id),
        "source": SOURCE,
        "source_url": url,
        "scraped_at": now_iso,
        "scraper_version": scraper_version,
        "version": 1,
        "language": lang,
        "content_hash": content_hash,
        "field_hashes": field_hashes,
        "http_status": 200,
        "status": "DONE",
    }
    return RawJobEnvelope(metadata=metadata, raw_payload=raw_payload)


class GlintsCrawler(BaseCrawler):
    """Crawler Glints Vietnam, tương thích với BaseCrawler của dự án và chuẩn Raw Envelope SD1."""

    source_name = SOURCE
    crawler_version = CRAWLER_VERSION

    def __init__(
        self,
        checkpoint_dir=None,
        output_dir=None,
        max_items=30,
        checkpoint_interval=10,
        http_client=None,
        headless: bool = True,
        chrome_path: str = "/usr/bin/google-chrome",
        use_playwright: bool = True,
        sync_minio: bool = True,
    ):
        super().__init__(
            checkpoint_dir=checkpoint_dir,
            output_dir=output_dir,
            max_items=max_items,
            checkpoint_interval=checkpoint_interval,
        )
        self.headless = headless
        self.chrome_path = chrome_path
        self.use_playwright = use_playwright
        self.sync_minio = sync_minio
        self._minio_store_inst = None
        self.http_client = http_client or HttpClient(
            source=self.source_name,
            delay_config=DelayConfig(min_seconds=1.5, max_seconds=3.0),
            timeout=25,
            extra_headers={
                "Accept": "application/json, text/html, */*",
                "Content-Type": "application/json",
                "Origin": "https://glints.com",
                "Referer": LISTING_URL,
                "Accept-Encoding": "identity",
            },
        )
        base_dir = Path(output_dir or f"data/{self.source_name}")
        if base_dir.name != self.source_name:
            base_dir = base_dir / self.source_name
        self.source_dir = base_dir
        self.ledger = UrlLedger(
            source=self.source_name,
            storage_dir=str(self.source_dir / "url_ledger"),
        )

    def _get_minio_store(self):
        """Trả về instance MinioRawStore (kết nối S3/MinIO bucket vn-it-jobs)."""
        if self._minio_store_inst is None and self.sync_minio:
            try:
                from crawlers.common.minio_raw_pipeline import MinioRawStore
                self._minio_store_inst = MinioRawStore()
            except Exception as e:
                logging.warning("[Glints] Chưa thể khởi tạo MinioRawStore: %s", e)
                self._minio_store_inst = None
        return self._minio_store_inst

    def _create_browser_context(self, playwright):
        """Khởi tạo browser context Playwright có bypass Cloudflare WAF."""
        exec_path = self.chrome_path if os.path.exists(self.chrome_path) else None
        browser = playwright.chromium.launch(
            headless=self.headless,
            executable_path=exec_path,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="vi-VN",
            viewport={"width": 1280, "height": 800},
        )
        wd_prop = "web" + "driver"
        context.add_init_script(f"Object.defineProperty(navigator, '{wd_prop}', {{get: () => undefined}})")
        return browser, context

    def discover_urls(self, max_pages: int | None = None) -> list[str]:
        """Pha 1: Quét danh mục Glints bằng Playwright (tương tác trực tiếp Web UI + In-Browser GraphQL).
        Ghi nhận vào UrlLedger với status='PENDING' và content_hash=None (chưa có hash).
        Tự động phân trang sâu tới khi hết bài (hasMore=False hoặc 2 trang liên tiếp rỗng).
        Sau đó UP URL LEDGER LÊN MINIO LAKEHOUSE.
        """
        logging.info("[Glints] === Bắt đầu Pha 1: URL Discovery (Playwright Web Interaction) ===")
        discovered_urls: list[str] = []

        if self.use_playwright:
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    browser, context = self._create_browser_context(p)
                    browser_page = context.new_page()

                    page_idx = 1
                    has_more_global = True
                    consecutive_empty = 0

                    while has_more_global:
                        if max_pages is not None and page_idx > max_pages:
                            logging.info("[Glints] Đã đạt giới hạn max_pages=%d quy định. Dừng Discovery.", max_pages)
                            break

                        page_url = f"{LISTING_URL}?page={page_idx}" if page_idx > 1 else LISTING_URL
                        logging.info("[Glints] Playwright đang duyệt trang danh mục %d: %s", page_idx, page_url)
                        try:
                            browser_page.goto(page_url, wait_until="domcontentloaded", timeout=35000)
                            browser_page.wait_for_timeout(2000)
                            human_like_interaction(browser_page, scroll_times=2)

                            # 1. Trích xuất thẻ việc làm thực tế từ DOM trang web
                            card_data = browser_page.evaluate('''() => {
                                const items = [];
                                const anchors = Array.from(document.querySelectorAll('a[href*="/opportunities/jobs/"]'));
                                for (const a of anchors) {
                                    const href = a.href;
                                    const titleEl = a.querySelector('h2, h3, [class*="JobTitle"], [class*="title"]') || a;
                                    const title = titleEl ? titleEl.innerText.trim() : '';
                                    const card = a.closest('[class*="Card"], [class*="Item"], article') || a.parentElement;
                                    const compEl = card ? card.querySelector('[class*="Company"], a[href*="/companies/"]') : null;
                                    const comp = compEl ? compEl.innerText.trim() : '';
                                    if (title && !items.some(x => x.href === href)) {
                                        items.push({ href, title, company: comp });
                                    }
                                }
                                return items;
                            }''')

                            # 2. Đồng thời gọi GraphQL nội bộ trình duyệt để bổ sung các bài trong trang
                            payload = {
                                "operationName": "searchJobsV3",
                                "variables": {
                                    "data": {
                                        "CountryCode": "VN",
                                        "HierarchicalJobCategoryIds": list(IT_CATEGORY_IDS),
                                        "includeExternalJobs": True,
                                        "pageSize": PAGE_SIZE,
                                        "page": page_idx,
                                    }
                                },
                                "query": SEARCH_QUERY,
                            }
                            gql_result = None
                            try:
                                gql_result = browser_page.evaluate(
                                    """
                                    async ({endpoint, payload}) => {
                                        const resp = await fetch(endpoint, {
                                            method: 'POST',
                                            headers: {
                                                'Accept': 'application/json, text/plain, */*',
                                                'Content-Type': 'application/json'
                                            },
                                            body: JSON.stringify(payload)
                                        });
                                        return { status: resp.status, body: await resp.json() };
                                    }
                                    """,
                                    {"endpoint": GRAPHQL_ENDPOINT, "payload": payload},
                                )
                                gql_data = gql_result.get("body", {}).get("data", {}).get("searchJobsV3", {})
                                gql_jobs = gql_data.get("jobsInPage", [])
                                if not gql_data.get("hasMore", True):
                                    has_more_global = False
                                    logging.info("[Glints] GraphQL thông báo đã đến trang cuối (hasMore=False).")

                                for gj in gql_jobs:
                                    g_id = str(gj.get("id"))
                                    g_slug = slugify(gj.get("title", ""))
                                    g_url = f"https://glints.com/vn/opportunities/jobs/{g_slug}/{g_id}"
                                    if not any(cd["href"].endswith(g_id) for cd in card_data):
                                        card_data.append({
                                            "href": g_url,
                                            "title": clean_text(gj.get("title", "")),
                                            "company": clean_text((gj.get("company") or {}).get("name", "")),
                                        })
                            except Exception as gql_err:
                                logging.debug("[Glints] In-browser GraphQL phụ trợ lỗi (%s), dùng DOM cards", gql_err)

                            if not card_data:
                                consecutive_empty += 1
                                if consecutive_empty >= 2:
                                    logging.info("[Glints] 2 trang liên tiếp không tìm thấy bài đăng mới. Hoàn tất Discovery.")
                                    break
                            else:
                                consecutive_empty = 0

                            # 3. Ghi nhận URL vào Ledger (Mới đầu CHƯA CÓ HASH, status = PENDING)
                            new_registered = 0
                            for c in card_data:
                                clean_url = clean_canonical_url(c["href"])
                                job_id = clean_url.split("/")[-1]
                                title = clean_text(c.get("title", ""))
                                company = clean_text(c.get("company", ""))
                                rec = self.ledger.register_url(
                                    raw_url=clean_url,
                                    job_id=job_id,
                                    preliminary_title=title,
                                    preliminary_company=company,
                                )
                                rec_status = getattr(rec, "status", None) if not isinstance(rec, dict) else rec.get("status")
                                if rec_status == "PENDING":
                                    new_registered += 1
                                if clean_url not in discovered_urls:
                                    discovered_urls.append(clean_url)

                            logging.info("[Glints] Trang %d: ghi nhận %d jobs từ DOM/GraphQL (mới: %d)", page_idx, len(card_data), new_registered)
                            page_idx += 1
                            polite_sleep(2.0, 3.8, reason="Chuyển trang danh mục Glints")
                        except Exception as exc:
                            logging.warning("[Glints] Safe Skip Playwright trang listing %d: %s", page_idx, exc)
                            page_idx += 1
                            continue
                    browser.close()
            except Exception as exc:
                logging.warning("[Glints] Không thể chạy Playwright Discovery (%s), chuyển sang HTTP fallback...", exc)

        # Lưu catalog master & daily manifest cục bộ
        self.ledger.save_catalog()
        self.ledger.export_daily_manifest()

        # UP TOÀN BỘ URL LEDGER LÊN MINIO LAKEHOUSE
        if self.sync_minio:
            logging.info("[Glints] Đang đẩy URL Ledger lên MinIO Lakehouse...")
            self.ledger.sync_to_minio()

        logging.info("[Glints] Pha 1 hoàn tất: phát hiện %d URLs (đã đồng bộ MinIO).", len(discovered_urls))
        return discovered_urls

    def crawl_details(self, limit: int | None = None, retry_failed: bool = False) -> dict[str, int]:
        """Pha 2: Bóc tách bài đăng chi tiết.
        1. Kéo URL từ MinIO về để lấy danh sách cần cào.
        2. Nếu cào lỗi -> đưa vào Queue lỗi (FAILED Queue) để bữa khác cào lại.
        3. Cào xong -> Băm Canonical JSON Hash trên document vừa cào (lúc này mới có hash).
        4. Lọc trùng Repost.
        5. Checkpoint Sync định kỳ mỗi 15 bài cào thành công lên MinIO Lakehouse.
        6. Lưu ngược hash vào Raw Snapshot (up lên MinIO) và URL Ledger (up lên MinIO).
        """
        logging.info("[Glints] === Bắt đầu Pha 2: Detail Extraction (Chu kỳ Re-crawl 21 ngày & MinIO Sync) ===")

        # BƯỚC 1: Kéo URL Ledger mới nhất từ MinIO về local
        if self.sync_minio:
            logging.info("[Glints] Đang kéo URL Ledger từ MinIO Lakehouse về...")
            self.ledger.pull_from_minio()

        # BƯỚC 2: Lấy danh sách cần cào
        if retry_failed:
            to_crawl = [
                r for r in self.ledger.records.values()
                if r.get("status") == "FAILED" and int(r.get("retry_count", 0)) < 5
            ]
            logging.info("[Glints] Chế độ RETRY FAILED: Tìm thấy %d bài trong hàng đợi lỗi.", len(to_crawl))
        else:
            pending = self.ledger.get_pending_or_due_records(recheck_days=21)
            failed_queue = [
                r for r in self.ledger.records.values()
                if r.get("status") == "FAILED" and int(r.get("retry_count", 0)) < 5 and r not in pending
            ]
            to_crawl = pending + failed_queue
            logging.info(
                "[Glints] Tìm thấy %d tin cần xử lý (PENDING/DUE: %d, FAILED Queue: %d).",
                len(to_crawl),
                len(pending),
                len(failed_queue),
            )

        stats = {"success": 0, "failed": 0, "skipped": 0, "repost": 0, "closed": 0}
        count = 0

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        raw_storage_dir = self.source_dir / "raw" / today_str
        raw_storage_dir.mkdir(parents=True, exist_ok=True)
        store = self._get_minio_store()

        playwright_obj = None
        browser = None
        browser_page = None
        if self.use_playwright:
            try:
                from playwright.sync_api import sync_playwright
                playwright_obj = sync_playwright().start()
                browser, context = self._create_browser_context(playwright_obj)
                browser_page = context.new_page()
            except Exception as e:
                logging.warning("[Glints] Không thể khởi tạo Playwright cho Pha 2 (%s), dùng HTTP fallback", e)
                playwright_obj = None

        try:
            for item in to_crawl:
                if limit and count >= limit:
                    break
                url = item["canonical_url"]
                url_hash = item["url_hash"]
                job_id = item["job_id"]
                try:
                    html_content = ""
                    if browser_page is not None:
                        logging.info("[Glints] [%d/%d] Đang tải chi tiết qua Playwright: %s", count + 1, len(to_crawl), url)
                        browser_page.goto(url, wait_until="domcontentloaded", timeout=35000)
                        human_like_interaction(browser_page, scroll_times=1)
                        html_content = browser_page.content()

                        if is_cloudflare_challenge(html_content):
                            logging.warning("[Glints] Gặp Cloudflare Challenge tại %s, kích hoạt backoff...", url)
                            if handle_cloudflare_backoff(browser_page, retry_attempt=1):
                                html_content = browser_page.content()
                            else:
                                raise RuntimeError("Cloudflare challenge block")

                        if "Không tìm thấy" in browser_page.title() or "404" in browser_page.title():
                            logging.info("[Glints] Bài viết đã bị đóng hoặc 404: %s", url)
                            self.ledger.mark_closed(url_hash)
                            stats["closed"] += 1
                            continue
                    else:
                        resp = self.http_client.get(url)
                        resp.raise_for_status()
                        html_content = resp.text

                    if not html_content or len(html_content) < 100:
                        raise ValueError(f"HTML rỗng hoặc quá ngắn cho {url}")

                    # BƯỚC 3: Bóc tách Raw Envelope chuẩn SD1 (Zero Information Loss)
                    envelope = extract_raw_envelope_from_html(html_content, job_id=job_id, url=url)

                    # BƯỚC 4: BÂY GIỜ MỚI CÓ HASH (Băm toàn bộ JSON document sau cào)
                    new_hash = calculate_json_canonical_hash(envelope.raw_payload)
                    field_hashes = calculate_json_field_hashes(envelope.raw_payload)
                    envelope.metadata["content_hash"] = new_hash
                    envelope.metadata["field_hashes"] = field_hashes

                    # BƯỚC 5: Lọc trùng Repost
                    existing = self.ledger.find_by_content_hash(new_hash)
                    if existing and existing.get("url_hash") != url_hash:
                        logging.info("[Glints] Phát hiện Repost: %s trùng nội dung với %s", url, existing["canonical_url"])
                        self.ledger.mark_done(url_hash, content_hash=new_hash, repost_of_url_hash=existing["url_hash"])
                        stats["repost"] += 1
                        count += 1
                        continue

                    # BƯỚC 6: Quản lý phiên bản CDC
                    curr_ver = item.get("latest_version") or 0
                    new_ver = curr_ver if (item.get("content_hash") == new_hash and curr_ver > 0) else curr_ver + 1
                    envelope.metadata["version"] = new_ver

                    # BƯỚC 7: Lưu snapshot raw cục bộ & UP TRỰC TIẾP LÊN MINIO
                    snapshot_file = raw_storage_dir / f"{job_id}_v{new_ver}.json"
                    with open(snapshot_file, "w", encoding="utf-8") as f:
                        json.dump(envelope.model_dump(), f, ensure_ascii=False, indent=2)

                    if store:
                        s3_key = f"raw/{self.source_name}/{today_str}/{job_id}_v{new_ver}.json"
                        try:
                            store.put_json(s3_key, envelope.model_dump())
                            logging.info("[Glints] Đã lưu snapshot trực tiếp lên MinIO: %s", s3_key)
                        except Exception as s3_err:
                            logging.warning("[Glints] Không thể lưu snapshot lên MinIO (%s): %s", s3_key, s3_err)

                    # BƯỚC 8: Lưu ngược hash và status='DONE' vào URL Ledger
                    self.ledger.mark_done(url_hash, content_hash=new_hash, new_version=new_ver)
                    stats["success"] += 1
                    count += 1

                    # BƯỚC CHECKPOINT SYNC ĐỊNH KỲ: Cứ mỗi 15 bài đăng thành công, đồng bộ Ledger lên MinIO
                    if self.sync_minio and count > 0 and count % 15 == 0:
                        logging.info("[Glints] [Checkpoint Sync] Đã cào %d bài thành công, đồng bộ Ledger lên MinIO...", count)
                        self.ledger.save_catalog()
                        self.ledger.sync_to_minio()

                    polite_sleep(2.0, 4.0, reason="Nghỉ giữa 2 bài chi tiết Glints")
                except Exception as exc:
                    # BƯỚC XỬ LÝ LỖI: Lưu vào Queue lỗi (FAILED Queue) để bữa khác cào lại
                    logging.warning("[Glints] Safe Skip lỗi cào chi tiết %s (ID %s): %s. Đưa vào Queue lỗi.", url, job_id, exc)
                    self.ledger.mark_failed(url_hash=url_hash, error_message=str(exc))
                    stats["failed"] += 1
                    continue
        finally:
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass
            if playwright_obj is not None:
                try:
                    playwright_obj.stop()
                except Exception:
                    pass

        # BƯỚC 9: Lưu catalog master cục bộ & UP TOÀN BỘ SỔ CÁI ĐÃ CẬP NHẬT LÊN MINIO
        self.ledger.save_catalog()
        if self.sync_minio:
            logging.info("[Glints] Đang đẩy URL Ledger đã cập nhật lên MinIO Lakehouse...")
            self.ledger.sync_to_minio()

        logging.info("[Glints] Pha 2 hoàn tất: %s", stats)
        return stats

    def crawl_single_url(self, url: str) -> RawJobEnvelope | None:
        """Thử nghiệm bóc tách trực tiếp 1 URL đơn lẻ (hỗ trợ kiểm thử live probe)."""
        clean_url = clean_canonical_url(url)
        job_id = clean_url.split("/")[-1]
        html_content = ""
        if self.use_playwright:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser, context = self._create_browser_context(p)
                page = context.new_page()
                page.goto(clean_url, wait_until="domcontentloaded", timeout=30000)
                human_like_interaction(page, scroll_times=1)
                html_content = page.content()
                browser.close()
        else:
            resp = self.http_client.get(clean_url)
            html_content = resp.text

        if not html_content:
            return None
        return extract_raw_envelope_from_html(html_content, job_id=job_id, url=clean_url)

    def parse_raw_envelope(self, item: Dict[str, Any]) -> RawJobEnvelope:
        """Ánh xạ một item thô (từ HTML hoặc API) thành RawJobEnvelope chuẩn SD1."""
        html = item.get("html") or ""
        job_id = str(item.get("id") or item.get("job_id") or "unknown")
        url = item.get("url") or item.get("source_url") or ""
        if html:
            return extract_raw_envelope_from_html(html, job_id=job_id, url=url)

        # Fallback từ payload GraphQL
        title_val = item.get("title", "")
        comp_val = (item.get("company") or {}).get("name", "")
        lang = detect_language(title=title_val, company=comp_val)
        raw_payload = {
            "title": title_val,
            "company": comp_val,
            "salaries": item.get("salaries") or [],
            "skills": item.get("skills") or [],
            "graphql_listing": item,
        }
        now_iso = datetime.now(timezone.utc).isoformat()
        return RawJobEnvelope(
            metadata={
                "job_id": job_id,
                "source": SOURCE,
                "source_url": url,
                "scraped_at": now_iso,
                "scraper_version": "2.0.0",
                "version": 1,
                "language": lang,
                "content_hash": calculate_json_canonical_hash(raw_payload),
                "field_hashes": calculate_json_field_hashes(raw_payload),
                "http_status": 200,
                "status": "DONE",
            },
            raw_payload=raw_payload,
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
                        "HierarchicalJobCategoryIds": list(IT_CATEGORY_IDS),
                        "includeExternalJobs": True,
                        "pageSize": PAGE_SIZE,
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


if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Glints Two-Phase Crawler with Playwright UI & MinIO Lakehouse Sync"
    )
    parser.add_argument(
        "--phase",
        choices=["discovery", "detail", "details", "sync", "view", "all"],
        default="all",
        help="Pha thu thập dữ liệu (discovery: Pha 1 lấy URL; detail/details: Pha 2 cào chi tiết; sync: đồng bộ MinIO; view: xem thống kê; all: chạy trọn gói)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Số trang listing tối đa trong Pha 1 (None = quét tự động toàn bộ cho đến khi hết bài)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Số lượng bài viết chi tiết tối đa cần cào trong Pha 2 (None = cào hết bài PENDING)",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        default=False,
        help="Chỉ cào lại các URL đang nằm trong hàng đợi lỗi (FAILED Queue)",
    )
    parser.add_argument(
        "--online",
        action="store_true",
        default=True,
        help="Cho phép kết nối mạng bên ngoài để cào trực tiếp (mặc định: True)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Chạy trình duyệt ngầm (mặc định: True)",
    )
    parser.add_argument(
        "--no-headless",
        dest="headless",
        action="store_false",
        help="Mở trực tiếp cửa sổ trình duyệt Chrome UI trên màn hình",
    )
    parser.add_argument(
        "--no-minio",
        dest="sync_minio",
        action="store_false",
        default=True,
        help="Tắt đồng bộ MinIO Lakehouse (chỉ lưu cục bộ)",
    )
    args = parser.parse_args()

    crawler = GlintsCrawler(
        use_playwright=True,
        headless=args.headless,
        sync_minio=args.sync_minio,
    )

    if args.phase == "view":
        recs = crawler.ledger.records
        pending = sum(1 for r in recs.values() if r.get("status") == "PENDING")
        done = sum(1 for r in recs.values() if r.get("status") == "DONE")
        failed = sum(1 for r in recs.values() if r.get("status") == "FAILED")
        repost = sum(1 for r in recs.values() if r.get("repost_of_url_hash"))
        logging.info("[Glints Sổ cái URL Ledger] Tổng: %d | PENDING: %d | DONE: %d | FAILED: %d | REPOST: %d", len(recs), pending, done, failed, repost)
        sys.exit(0)

    if args.phase == "sync":
        logging.info("[Glints] Đang đẩy Sổ cái URL Ledger lên MinIO Lakehouse...")
        crawler.ledger.save_catalog()
        crawler.ledger.sync_to_minio()
        logging.info("[Glints] Đồng bộ MinIO hoàn tất.")
        sys.exit(0)

    if args.phase in ("discovery", "all"):
        page_desc = f"{args.max_pages} trang" if args.max_pages else "TOÀN BỘ trang IT"
        logging.info("[CLI] === BẮT ĐẦU PHA 1: URL DISCOVERY (%s) ===", page_desc)
        discovered = crawler.discover_urls(max_pages=args.max_pages)
        logging.info("[CLI] [+] Pha 1 hoàn thành. Tìm thấy %d URLs.", len(discovered))

    if args.phase in ("detail", "details", "all"):
        limit_desc = f"limit={args.limit}" if args.limit else "CÀO TOÀN BỘ PENDING"
        logging.info("[CLI] === BẮT ĐẦU PHA 2: DETAIL EXTRACTION (%s, retry_failed=%s) ===", limit_desc, args.retry_failed)
        stats = crawler.crawl_details(limit=args.limit, retry_failed=args.retry_failed)
        logging.info("[CLI] [+] Pha 2 hoàn thành. Thống kê: %s", stats)

