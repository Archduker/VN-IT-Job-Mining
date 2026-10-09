"""
crawlers.common.schema
~~~~~~~~~~~~~~~~~~~~~~~
Pydantic models định nghĩa Data Contract cho toàn bộ pipeline.

Mỗi crawler phải xuất ra dữ liệu theo cấu trúc:
    {
        "_meta": JobMetadata,
        "raw":   JobRaw
    }

Tầng này là **Raw Zone** — giữ nguyên văn gốc, không chuẩn hoá.
Việc chuẩn hoá (lương, kỹ năng, địa điểm) được thực hiện ở ETL layer.

Classes:
    JobMetadata  — Metadata về quá trình crawl (_meta section)
    JobRaw       — Dữ liệu thô từ trang tuyển dụng (raw section)
    JobRecord    — Wrapper chứa cả hai phần trên

Functions:
    validate_record(data: dict) -> JobRecord
        Parse và validate một dict thô thành JobRecord.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

from pydantic import BaseModel, Field, field_validator, model_validator


# ─────────────────────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────────────────────

def _normalize_url(url: str) -> str:
    """Chuẩn hoá URL: bỏ utm_* params, trailing slash, fragment.

    Args:
        url: URL gốc cần chuẩn hoá.

    Returns:
        URL đã được chuẩn hoá.

    Examples:
        >>> _normalize_url("https://topdev.vn/jobs/123?utm_source=home#apply")
        'https://topdev.vn/jobs/123'
    """
    parsed = urlparse(url.strip())

    # Loại bỏ utm_* và các tracking params
    _TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term",
                        "utm_content", "src", "medium", "ref", "referrer"}
    query_params = parse_qs(parsed.query, keep_blank_values=False)
    filtered = {k: v for k, v in query_params.items() if k.lower() not in _TRACKING_PARAMS}

    # Rebuild query string (giữ thứ tự alphabet để deterministic)
    new_query = urlencode(sorted(filtered.items()), doseq=True)

    # Bỏ trailing slash trong path (trừ root "/")
    path = parsed.path.rstrip("/") or "/"

    # Bỏ fragment (#...)
    normalized = urlunparse((
        parsed.scheme,
        parsed.netloc,
        path,
        parsed.params,
        new_query,
        "",  # no fragment
    ))
    return normalized


def _make_dedup_key(source: str, source_job_id: str) -> str:
    """Tạo deduplication key theo format chuẩn.

    Args:
        source: Tên nguồn (ví dụ: "topdev", "itviec").
        source_job_id: ID job trên trang gốc.

    Returns:
        Chuỗi dedup key dạng "<source>:<source_job_id>".

    Examples:
        >>> _make_dedup_key("topdev", "abc123")
        'topdev:abc123'
    """
    return f"{source.lower().strip()}:{source_job_id.strip()}"


def _hash_url(url: str) -> str:
    """Tạo hash ngắn (8 ký tự) từ URL để dùng làm fallback source_job_id.

    Args:
        url: URL cần hash.

    Returns:
        Hex string 8 ký tự (MD5 truncated).

    Examples:
        >>> len(_hash_url("https://topdev.vn/jobs/123"))
        8
    """
    return hashlib.md5(url.encode("utf-8")).hexdigest()[:8]


# ─────────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────────

class JobMetadata(BaseModel):
    """Metadata về quá trình crawl — bắt buộc giống nhau trên tất cả các nguồn.

    Phần này giúp theo dõi nguồn gốc dữ liệu, phát hiện trùng lặp,
    và audit trail khi cần trích xuất lại.

    Attributes:
        source: Tên nguồn tuyển dụng (ví dụ: "topdev", "itviec").
        source_job_id: ID duy nhất của job trên trang gốc.
            Nếu không có ID rõ ràng, dùng _hash_url(url) làm fallback.
        url: URL chi tiết job đã được chuẩn hoá (bỏ utm_*, trailing slash).
        dedup_key: Khoá khử trùng lặp, format "<source>:<source_job_id>".
        crawled_at: Thời điểm crawl (ISO 8601, UTC+7).
        batch_id: ID của batch chạy, format "YYYY-MM-DD_<source>_<seq>".
        crawler_version: Version của crawler script (semantic versioning).
    """

    source: str = Field(
        ...,
        description="Tên nguồn tuyển dụng (lowercase, no spaces)",
        pattern=r"^[a-z][a-z0-9_]*$",
        examples=["topdev", "itviec", "careerviet"],
    )
    source_job_id: str = Field(
        ...,
        description="ID duy nhất của job trên trang gốc, hoặc hash URL nếu không có ID",
        min_length=1,
        examples=["2136579", "abc-123", "a1b2c3d4"],
    )
    url: str = Field(
        ...,
        description="URL chi tiết job (đã chuẩn hoá, bỏ tracking params)",
        examples=["https://topdev.vn/viec-lam/senior-backend-developer-fpt-2136579"],
    )
    dedup_key: str = Field(
        ...,
        description="Khoá khử trùng: '<source>:<source_job_id>'",
        examples=["topdev:2136579"],
    )
    crawled_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Thời điểm crawl (timezone-aware, UTC)",
    )
    batch_id: str = Field(
        ...,
        description="ID của batch chạy, format: YYYY-MM-DD_<source>_<seq>",
        pattern=r"^\d{4}-\d{2}-\d{2}_[a-z][a-z0-9_]*_\d{3}$",
        examples=["2026-10-07_topdev_001"],
    )
    crawler_version: str = Field(
        default="0.1.0",
        description="Semantic version của crawler (MAJOR.MINOR.PATCH)",
        pattern=r"^\d+\.\d+\.\d+$",
        examples=["0.1.0", "1.0.0"],
    )
    language: str = Field(
        default="vi",
        description="Ngôn ngữ bài đăng (vi hoặc en)",
        pattern=r"^(vi|en)$",
        examples=["vi", "en"],
    )

    @field_validator("url")
    @classmethod
    def normalize_url(cls, v: str) -> str:
        """Tự động chuẩn hoá URL khi khởi tạo model."""
        normalized = _normalize_url(v)
        if not normalized.startswith(("http://", "https://")):
            raise ValueError(f"URL phải bắt đầu bằng http:// hoặc https://, nhận: {v!r}")
        return normalized

    @field_validator("dedup_key")
    @classmethod
    def validate_dedup_key_format(cls, v: str) -> str:
        """Kiểm tra dedup_key đúng format '<source>:<id>'."""
        if ":" not in v:
            raise ValueError(f"dedup_key phải có dạng '<source>:<id>', nhận: {v!r}")
        return v

    @model_validator(mode="after")
    def check_dedup_key_matches_source(self) -> "JobMetadata":
        """Đảm bảo dedup_key bắt đầu bằng đúng source name."""
        expected_prefix = f"{self.source}:"
        if not self.dedup_key.startswith(expected_prefix):
            raise ValueError(
                f"dedup_key '{self.dedup_key}' không khớp với source '{self.source}'. "
                f"Phải bắt đầu bằng '{expected_prefix}'"
            )
        return self

    @classmethod
    def create(
        cls,
        source: str,
        source_job_id: str,
        url: str,
        batch_id: str,
        crawler_version: str = "0.1.0",
        language: str = "vi",
    ) -> "JobMetadata":
        """Factory method: tạo JobMetadata với dedup_key tự động.

        Args:
            source: Tên nguồn (ví dụ: "topdev").
            source_job_id: ID job trên trang gốc.
            url: URL chi tiết job (chưa cần chuẩn hoá, validator sẽ xử lý).
            batch_id: ID batch chạy.
            crawler_version: Version crawler.
            language: Ngôn ngữ bài đăng ("vi" hoặc "en"). Default: "vi".

        Returns:
            JobMetadata đã validate.

        Examples:
            >>> meta = JobMetadata.create(
            ...     source="topdev",
            ...     source_job_id="2136579",
            ...     url="https://topdev.vn/viec-lam/senior-backend-2136579?utm_source=home",
            ...     batch_id="2026-10-07_topdev_001",
            ...     language="vi",
            ... )
            >>> meta.dedup_key
            'topdev:2136579'
            >>> "utm_source" not in meta.url
            True
            >>> meta.language
            'vi'
        """
        return cls(
            source=source,
            source_job_id=source_job_id,
            url=url,  # sẽ được normalize bởi validator
            dedup_key=_make_dedup_key(source, source_job_id),
            batch_id=batch_id,
            crawler_version=crawler_version,
            language=language,
        )


class JobSalary(BaseModel):
    """Cấu trúc mức lương ngữ nghĩa chi tiết.

    Attributes:
        salary_text: Chuỗi hiển thị mức lương gốc (ví dụ: '15-25 triệu', 'Thỏa thuận').
        salary_min: Mức lương tối thiểu (float).
        salary_max: Mức lương tối đa (float).
        salary_currency: Đơn vị tiền tệ ('VND', 'USD').
        pay_period: Chu kỳ trả lương ('month', 'year', 'day', 'hour'). Mặc định: 'month'.
        is_negotiable: Có phải mức lương thỏa thuận không (True/False).
        has_commission: Có hoa hồng, thưởng KPI, thu nhập không giới hạn không (True/False).
    """

    salary_text: Optional[str] = Field(default=None, description="Chuỗi hiển thị mức lương gốc")
    salary_min: Optional[float] = Field(default=None, description="Lương tối thiểu (số thực)")
    salary_max: Optional[float] = Field(default=None, description="Lương tối đa (số thực)")
    salary_currency: Optional[str] = Field(default=None, description="Đơn vị tiền tệ (VND, USD)")
    pay_period: Optional[str] = Field(default="month", description="Chu kỳ trả: month, year, day, hour")
    is_negotiable: bool = Field(default=False, description="Mức lương thỏa thuận (true/false)")
    has_commission: bool = Field(default=False, description="Có hoa hồng / thu nhập biến đổi (true/false)")

    model_config = {"extra": "allow"}


class JobTags(BaseModel):
    """Phân nhóm thẻ tag trực quan theo 3 nhóm: Yêu cầu, Quyền lợi, Chuyên môn.

    Attributes:
        requirements: Danh sách thẻ tag yêu cầu (null nếu không có trên trang).
        benefits: Danh sách thẻ tag quyền lợi (null nếu không có trên trang).
        skills: Danh sách thẻ tag chuyên môn kỹ thuật/vị trí (null nếu không có trên trang).
    """

    requirements: Optional[list[str]] = Field(default=None, description="Thẻ tag yêu cầu (nhóm Yêu cầu / Requirements)")
    benefits: Optional[list[str]] = Field(default=None, description="Thẻ tag quyền lợi (nhóm Quyền lợi / Benefits) - null nếu không có")
    skills: Optional[list[str]] = Field(default=None, description="Thẻ tag chuyên môn (nhóm Chuyên môn / Specialization)")

    model_config = {"extra": "allow"}

    # Thuộc tính tương thích ngược cho code cũ
    @property
    def technical_skills(self) -> list[str]:
        return self.skills or []

    @property
    def job_roles(self) -> list[str]:
        return []

    @property
    def attributes(self) -> dict:
        return {}


class JobRaw(BaseModel):
    """Dữ liệu thô từ trang tuyển dụng theo Data Contract tinh gọn mới.

    Các trường bắt buộc:
    - title, company, description_list

    Các trường cấu trúc:
    - salary: Đối tượng mức lương có cấu trúc (JobSalary)
    - tags: Đối tượng phân loại thẻ tags (JobTags)
    - requirements_list: Danh sách các mục yêu cầu ứng viên (list[str])
    - benefits_list: Danh sách các mục quyền lợi ứng viên (list[str])

    Attributes:
        title: Tiêu đề job (nguyên văn từ trang).
        company: Tên công ty tuyển dụng.
        description_list: Danh sách các đoạn mô tả công việc (list[str]).
        salary: Đối tượng mức lương có cấu trúc ngữ nghĩa (JobSalary).
        tags: Đối tượng phân loại tags chuyên môn (JobTags).
        requirements_list: Danh sách các mục yêu cầu ứng viên (list[str]).
        benefits_list: Danh sách các mục quyền lợi ứng viên (list[str]).
        location_text: Địa điểm làm việc dạng text.
        deadline_text: Hạn nộp hồ sơ dạng text.
        posted_date_text: Ngày đăng tuyển dạng text.
        employment_type_text: Loại hình công việc ("Fulltime", "Parttime", ...).
        seniority_text: Cấp bậc ("Senior", "Junior", "Intern", ...).
        extra: Dict chứa các trường bổ sung tuỳ nguồn (không bắt buộc).
    """

    # ── Bắt buộc ────────────────────────────────────────────
    title: str = Field(
        ...,
        description="Tiêu đề job (nguyên văn từ trang)",
        min_length=1,
        examples=["Senior Backend Developer", "Kỹ sư Phần mềm (Python)"],
    )
    company: str = Field(
        ...,
        description="Tên công ty tuyển dụng",
        min_length=1,
        examples=["FPT Software", "VNG Corporation"],
    )
    description_list: list[str] = Field(
        default_factory=list,
        description="Mô tả công việc dạng danh sách chuỗi (list of strings)",
    )

    # ── Tuỳ chọn có cấu trúc ────────────────────────────────
    salary: Optional[JobSalary] = Field(
        default=None,
        description="Đối tượng mức lương ngữ nghĩa chi tiết",
    )
    tags: Optional[JobTags] = Field(
        default=None,
        description="Đối tượng phân loại thẻ tags chuyên môn, vai trò, phúc lợi",
    )
    requirements_list: list[str] = Field(
        default_factory=list,
        description="Danh sách các mục yêu cầu ứng viên (list of strings)",
    )
    benefits_list: list[str] = Field(
        default_factory=list,
        description="Danh sách các mục quyền lợi ứng viên (list of strings)",
    )

    # ── Thông tin phụ trợ nguyên bản ────────────────────────
    location_text: Optional[str] = Field(
        default=None,
        description="Địa điểm làm việc (nguyên văn từ trang)",
        examples=["Hồ Chí Minh", "Quận Bình Thạnh, Hồ Chí Minh", "Remote"],
    )
    deadline_text: Optional[str] = Field(
        default=None,
        description="Hạn nộp hồ sơ dạng text",
        examples=["31/10/2026", "30 days"],
    )
    posted_date_text: Optional[str] = Field(
        default=None,
        description="Ngày đăng tuyển dạng text gốc",
        examples=["03/10/2026", "2 ngày trước", "1 tuần trước"],
    )
    employment_type_text: Optional[str] = Field(
        default=None,
        description="Loại hình công việc",
        examples=["Fulltime", "Parttime", "Contract", "Freelance"],
    )
    seniority_text: Optional[str] = Field(
        default=None,
        description="Cấp bậc / kinh nghiệm yêu cầu",
        examples=["Senior", "Junior", "Intern", "Mid-level", "Fresher"],
    )
    extra: Optional[dict] = Field(
        default=None,
        description="Các trường bổ sung tuỳ nguồn (không bắt buộc)",
    )

    @field_validator("title", "company")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        """Strip leading/trailing whitespace."""
        return v.strip()

    @property
    def description_text(self) -> str:
        """Thuộc tính tương thích ngược cho các đoạn mã đọc mô tả dạng text."""
        return "\n".join(self.description_list)

    @property
    def requirements_text(self) -> str:
        """Thuộc tính tương thích ngược cho yêu cầu dạng text."""
        return "\n".join(self.requirements_list)

    @property
    def benefits_text(self) -> str:
        """Thuộc tính tương thích ngược cho phúc lợi dạng text."""
        return "\n".join(self.benefits_list)

    @property
    def salary_min(self) -> Optional[float]:
        """Thuộc tính tương thích ngược cho mức lương tối thiểu."""
        return self.salary.salary_min if self.salary else None

    @property
    def salary_max(self) -> Optional[float]:
        """Thuộc tính tương thích ngược cho mức lương tối đa."""
        return self.salary.salary_max if self.salary else None

    @property
    def salary_text(self) -> Optional[str]:
        """Thuộc tính tương thích ngược cho text mức lương."""
        return self.salary.salary_text if self.salary else None

    @property
    def salary_currency(self) -> Optional[str]:
        """Thuộc tính tương thích ngược cho đơn vị tiền tệ."""
        return self.salary.salary_currency if self.salary else None

    @property
    def skills_text(self) -> Optional[str]:
        """Thuộc tính tương thích ngược cho danh sách kỹ năng dạng text."""
        if self.tags and self.tags.skills:
            return ", ".join(self.tags.skills)
        if self.tags and self.tags.technical_skills:
            return ", ".join(self.tags.technical_skills)
        return None

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_fields(cls, data: Any) -> Any:
        """Bộ thích ứng tương thích ngược thông minh cho các nguồn crawler khác và dữ liệu cũ."""
        if not isinstance(data, dict):
            return data

        d = dict(data)

        # 1. Chuyển đổi description_text / description_html -> description_list nếu chưa có
        if "description_list" not in d or not d["description_list"]:
            raw_desc = d.get("description_text") or d.get("description_html")
            if raw_desc:
                # Strip HTML tags nếu có
                clean_desc = re.sub(r"<[^>]+>", "", str(raw_desc))
                lines = [line.strip() for line in clean_desc.split("\n") if line.strip()]
                d["description_list"] = lines

        if not d.get("description_list"):
            raise ValueError("description_list không được để trống")

        # 2. Đóng gói salary phẳng thành object salary nếu chưa có
        if "salary" not in d or d["salary"] is None:
            if any(k in d for k in ["salary_text", "salary_min", "salary_max", "salary_currency"]):
                d["salary"] = {
                    "salary_text": d.get("salary_text"),
                    "salary_min": d.get("salary_min"),
                    "salary_max": d.get("salary_max"),
                    "salary_currency": d.get("salary_currency"),
                }

        # 3. Chuyển đổi requirements_text -> requirements_list nếu chưa có
        if "requirements_list" not in d or not d["requirements_list"]:
            req_text = d.get("requirements_text")
            if req_text:
                d["requirements_list"] = [line.strip() for line in str(req_text).split("\n") if line.strip()]

        # 4. Chuyển đổi benefits_text -> benefits_list nếu chưa có
        if "benefits_list" not in d or not d["benefits_list"]:
            ben_text = d.get("benefits_text")
            if ben_text:
                d["benefits_list"] = [line.strip() for line in str(ben_text).split("\n") if line.strip()]

        # 5. Chuyển đổi skills_text -> tags nếu chưa có
        if "tags" not in d or not d["tags"]:
            skills_raw = d.get("skills_text")
            if skills_raw:
                skills_items = [s.strip() for s in re.split(r"[,|;/]+", str(skills_raw)) if s.strip()]
                d["tags"] = {"skills": skills_items}
        elif isinstance(d["tags"], dict):
            # Nếu tags có technical_skills nhưng chưa có skills
            if "skills" not in d["tags"] and "technical_skills" in d["tags"]:
                d["tags"]["skills"] = d["tags"].get("technical_skills")

        # 6. Xóa các trường cũ khỏi dict để không lọt vào extra hoặc output
        for legacy_key in [
            "description_html",
            "description_text",
            "salary_text",
            "salary_min",
            "salary_max",
            "salary_currency",
            "requirements_text",
            "benefits_text",
            "skills_text",
        ]:
            d.pop(legacy_key, None)

        return d

    model_config = {"extra": "allow"}


class JobRecord(BaseModel):
    """Wrapper model chứa đầy đủ một job record theo Data Contract.

    Cấu trúc chuẩn của mỗi dòng trong file JSONL:
        {
            "_meta": { ... },  # JobMetadata
            "raw":   { ... }   # JobRaw
        }

    Attributes:
        meta: Metadata về quá trình crawl (field name "_meta" trong JSON).
        raw: Dữ liệu thô từ trang tuyển dụng.
    """

    meta: JobMetadata = Field(..., alias="_meta")
    raw: JobRaw

    model_config = {
        "populate_by_name": True,   # Cho phép dùng cả alias "_meta" và field name "meta"
    }

    def to_jsonl_dict(self) -> dict:
        """Xuất ra dict theo format JSONL chuẩn cho pipeline.

        Returns:
            Dict với key "_meta" và "raw", crawled_at ở dạng ISO string.

        Examples:
            >>> record.to_jsonl_dict().keys()
            dict_keys(['_meta', 'raw'])
        """
        return {
            "_meta": self.meta.model_dump(mode="json"),
            "raw": self.raw.model_dump(mode="json", exclude_none=False),
        }

    @classmethod
    def create(
        cls,
        source: str,
        source_job_id: str,
        url: str,
        batch_id: str,
        raw_data: dict,
        crawler_version: str = "0.1.0",
        language: str = "vi",
    ) -> "JobRecord":
        """Factory method: tạo JobRecord đầy đủ từ raw data dict.

        Args:
            source: Tên nguồn (ví dụ: "topdev").
            source_job_id: ID job trên trang gốc.
            url: URL chi tiết job.
            batch_id: ID batch chạy.
            raw_data: Dict chứa dữ liệu thô từ trang (title, company, ...).
            crawler_version: Version crawler.
            language: Ngôn ngữ bài đăng ("vi" hoặc "en"). Default: "vi".

        Returns:
            JobRecord đã validate đầy đủ.

        Raises:
            pydantic.ValidationError: Nếu raw_data thiếu trường bắt buộc.

        Examples:
            >>> record = JobRecord.create(
            ...     source="topdev",
            ...     source_job_id="2136579",
            ...     url="https://topdev.vn/viec-lam/senior-backend-2136579",
            ...     batch_id="2026-10-07_topdev_001",
            ...     language="vi",
            ...     raw_data={
            ...         "title": "Senior Backend Developer",
            ...         "company": "FPT Software",
            ...         "description_html": "<div>Mô tả công việc</div>",
            ...         "description_text": "Mô tả công việc",
            ...     },
            ... )
        """
        meta = JobMetadata.create(
            source=source,
            source_job_id=source_job_id,
            url=url,
            batch_id=batch_id,
            crawler_version=crawler_version,
            language=language,
        )
        raw = JobRaw(**raw_data)
        return cls(**{"_meta": meta, "raw": raw})


# ─────────────────────────────────────────────────────────────
# Module-level helper
# ─────────────────────────────────────────────────────────────

def validate_record(data: dict) -> JobRecord:
    """Parse và validate một raw dict thành JobRecord.

    Tiện ích để validate dữ liệu nhận từ crawler trước khi ghi vào JSONL.

    Args:
        data: Dict với structure {"_meta": {...}, "raw": {...}}.

    Returns:
        JobRecord đã validate.

    Raises:
        pydantic.ValidationError: Nếu data không hợp lệ.

    Examples:
        >>> record = validate_record({
        ...     "_meta": {
        ...         "source": "topdev",
        ...         "source_job_id": "123",
        ...         "url": "https://topdev.vn/viec-lam/xyz-123",
        ...         "dedup_key": "topdev:123",
        ...         "batch_id": "2026-10-07_topdev_001",
        ...     },
        ...     "raw": {
        ...         "title": "Backend Dev",
        ...         "company": "FPT",
        ...         "description_html": "<p>desc</p>",
        ...         "description_text": "desc",
        ...     }
        ... })
    """
    return JobRecord.model_validate(data)


# Re-export helpers for convenience
make_dedup_key = _make_dedup_key
hash_url = _hash_url
normalize_url = _normalize_url
