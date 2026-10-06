"""
Unit tests cho crawlers.common.schema module.

Test coverage:
    - JobMetadata: creation, validation, URL normalization, dedup_key
    - JobRaw: required fields, optional fields, strip whitespace
    - JobRecord: factory method, to_jsonl_dict
    - Helper functions: normalize_url, make_dedup_key, hash_url
    - validate_record: end-to-end validation
"""

from __future__ import annotations

import pytest
from datetime import date, timezone
from pydantic import ValidationError

from crawlers.common.schema import (
    JobMetadata,
    JobRaw,
    JobRecord,
    validate_record,
    normalize_url,
    make_dedup_key,
    hash_url,
)


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def valid_metadata_dict() -> dict:
    """Dict hợp lệ cho JobMetadata."""
    return {
        "source": "topdev",
        "source_job_id": "2136579",
        "url": "https://topdev.vn/viec-lam/senior-backend-developer-fpt-2136579",
        "dedup_key": "topdev:2136579",
        "batch_id": "2026-10-07_topdev_001",
        "crawler_version": "0.1.0",
    }


@pytest.fixture
def valid_raw_dict() -> dict:
    """Dict hợp lệ cho JobRaw với các trường bắt buộc."""
    return {
        "title": "Senior Backend Developer",
        "company": "FPT Software",
        "description_html": "<div><p>Mô tả công việc chi tiết.</p></div>",
        "description_text": "Mô tả công việc chi tiết.",
    }


@pytest.fixture
def valid_record_dict(valid_metadata_dict, valid_raw_dict) -> dict:
    """Dict hợp lệ cho JobRecord."""
    return {
        "_meta": valid_metadata_dict,
        "raw": valid_raw_dict,
    }


# ─────────────────────────────────────────────────────────────
# Tests: normalize_url
# ─────────────────────────────────────────────────────────────

class TestNormalizeUrl:

    def test_removes_utm_params(self):
        url = "https://topdev.vn/viec-lam/job-123?utm_source=home&utm_medium=banner"
        result = normalize_url(url)
        assert "utm_source" not in result
        assert "utm_medium" not in result

    def test_removes_src_medium_params(self):
        url = "https://topdev.vn/jobs/123?src=topdev_home&medium=superhotjobs"
        result = normalize_url(url)
        assert "src=" not in result
        assert "medium=" not in result

    def test_removes_trailing_slash(self):
        url = "https://topdev.vn/viec-lam/job-123/"
        assert normalize_url(url) == "https://topdev.vn/viec-lam/job-123"

    def test_removes_fragment(self):
        url = "https://topdev.vn/jobs/123#apply-section"
        assert "#" not in normalize_url(url)

    def test_keeps_legitimate_params(self):
        url = "https://topdev.vn/jobs?page=2&category=backend"
        result = normalize_url(url)
        assert "page=2" in result
        assert "category=backend" in result

    def test_handles_url_without_params(self):
        url = "https://topdev.vn/viec-lam/senior-backend-123"
        assert normalize_url(url) == url

    def test_preserves_https_scheme(self):
        url = "https://topdev.vn/jobs/123"
        assert normalize_url(url).startswith("https://")


# ─────────────────────────────────────────────────────────────
# Tests: make_dedup_key
# ─────────────────────────────────────────────────────────────

class TestMakeDedupKey:

    def test_basic_format(self):
        result = make_dedup_key("topdev", "2136579")
        assert result == "topdev:2136579"

    def test_lowercase_source(self):
        result = make_dedup_key("TopDev", "123")
        assert result == "topdev:123"

    def test_strips_whitespace(self):
        result = make_dedup_key(" itviec ", " abc123 ")
        assert result == "itviec:abc123"

    def test_contains_colon_separator(self):
        result = make_dedup_key("careerviet", "job-456")
        assert ":" in result
        parts = result.split(":", 1)
        assert len(parts) == 2


# ─────────────────────────────────────────────────────────────
# Tests: hash_url
# ─────────────────────────────────────────────────────────────

class TestHashUrl:

    def test_returns_8_char_string(self):
        result = hash_url("https://topdev.vn/jobs/123")
        assert len(result) == 8

    def test_deterministic(self):
        url = "https://topdev.vn/jobs/123"
        assert hash_url(url) == hash_url(url)

    def test_different_urls_different_hashes(self):
        assert hash_url("https://topdev.vn/jobs/1") != hash_url("https://topdev.vn/jobs/2")


# ─────────────────────────────────────────────────────────────
# Tests: JobMetadata
# ─────────────────────────────────────────────────────────────

class TestJobMetadata:

    def test_valid_creation(self, valid_metadata_dict):
        meta = JobMetadata(**valid_metadata_dict)
        assert meta.source == "topdev"
        assert meta.source_job_id == "2136579"
        assert meta.dedup_key == "topdev:2136579"

    def test_url_normalized_on_creation(self):
        meta = JobMetadata(
            source="topdev",
            source_job_id="123",
            url="https://topdev.vn/jobs/123?utm_source=home#apply",
            dedup_key="topdev:123",
            batch_id="2026-10-07_topdev_001",
        )
        assert "utm_source" not in meta.url
        assert "#" not in meta.url

    def test_invalid_source_with_spaces(self):
        with pytest.raises(ValidationError):
            JobMetadata(
                source="top dev",    # spaces không được phép
                source_job_id="123",
                url="https://topdev.vn/jobs/123",
                dedup_key="top dev:123",
                batch_id="2026-10-07_topdev_001",
            )

    def test_invalid_batch_id_format(self, valid_metadata_dict):
        valid_metadata_dict["batch_id"] = "bad-batch-id"
        with pytest.raises(ValidationError):
            JobMetadata(**valid_metadata_dict)

    def test_dedup_key_must_start_with_source(self, valid_metadata_dict):
        valid_metadata_dict["dedup_key"] = "itviec:2136579"   # wrong source
        with pytest.raises(ValidationError):
            JobMetadata(**valid_metadata_dict)

    def test_dedup_key_must_contain_colon(self, valid_metadata_dict):
        valid_metadata_dict["dedup_key"] = "topdev-2136579"   # no colon
        with pytest.raises(ValidationError):
            JobMetadata(**valid_metadata_dict)

    def test_invalid_url_without_scheme(self, valid_metadata_dict):
        valid_metadata_dict["url"] = "topdev.vn/jobs/123"
        with pytest.raises(ValidationError):
            JobMetadata(**valid_metadata_dict)

    def test_crawled_at_has_timezone(self, valid_metadata_dict):
        meta = JobMetadata(**valid_metadata_dict)
        assert meta.crawled_at.tzinfo is not None

    def test_factory_method_create(self):
        meta = JobMetadata.create(
            source="topdev",
            source_job_id="2136579",
            url="https://topdev.vn/jobs/2136579?utm_source=home",
            batch_id="2026-10-07_topdev_001",
        )
        assert meta.dedup_key == "topdev:2136579"
        assert "utm_source" not in meta.url

    def test_factory_method_default_version(self):
        meta = JobMetadata.create(
            source="itviec",
            source_job_id="abc",
            url="https://itviec.com/jobs/abc",
            batch_id="2026-10-07_itviec_001",
        )
        assert meta.crawler_version == "0.1.0"


# ─────────────────────────────────────────────────────────────
# Tests: JobRaw
# ─────────────────────────────────────────────────────────────

class TestJobRaw:

    def test_valid_with_required_fields_only(self, valid_raw_dict):
        raw = JobRaw(**valid_raw_dict)
        assert raw.title == "Senior Backend Developer"
        assert raw.company == "FPT Software"

    def test_optional_fields_default_to_none(self, valid_raw_dict):
        raw = JobRaw(**valid_raw_dict)
        assert raw.salary_text is None
        assert raw.location_text is None
        assert raw.skills_text is None
        assert raw.seniority_text is None

    def test_title_stripped(self):
        raw = JobRaw(
            title="  Senior Backend Developer  ",
            company="FPT",
            description_html="<p>desc</p>",
            description_text="desc",
        )
        assert raw.title == "Senior Backend Developer"

    def test_company_stripped(self):
        raw = JobRaw(
            title="Dev",
            company="  FPT Software  ",
            description_html="<p>desc</p>",
            description_text="desc",
        )
        assert raw.company == "FPT Software"

    def test_missing_title_raises_error(self, valid_raw_dict):
        del valid_raw_dict["title"]
        with pytest.raises(ValidationError):
            JobRaw(**valid_raw_dict)

    def test_missing_description_html_raises_error(self, valid_raw_dict):
        del valid_raw_dict["description_html"]
        with pytest.raises(ValidationError):
            JobRaw(**valid_raw_dict)

    def test_full_optional_fields(self, valid_raw_dict):
        full_raw = {
            **valid_raw_dict,
            "salary_text": "15-25 triệu",
            "location_text": "Hồ Chí Minh",
            "skills_text": "Java, Spring Boot, MySQL",
            "posted_date_text": "03/10/2026",
            "employment_type_text": "Fulltime",
            "seniority_text": "Senior",
            "requirements_text": "3+ năm kinh nghiệm Java",
            "benefits_text": "Bảo hiểm sức khoẻ",
            "deadline_text": "31/10/2026",
        }
        raw = JobRaw(**full_raw)
        assert raw.salary_text == "15-25 triệu"
        assert raw.skills_text == "Java, Spring Boot, MySQL"


# ─────────────────────────────────────────────────────────────
# Tests: JobRecord
# ─────────────────────────────────────────────────────────────

class TestJobRecord:

    def test_valid_creation(self, valid_record_dict):
        record = JobRecord.model_validate(valid_record_dict)
        assert record.meta.source == "topdev"
        assert record.raw.title == "Senior Backend Developer"

    def test_to_jsonl_dict_has_correct_keys(self, valid_record_dict):
        record = JobRecord.model_validate(valid_record_dict)
        d = record.to_jsonl_dict()
        assert "_meta" in d
        assert "raw" in d

    def test_to_jsonl_dict_meta_content(self, valid_record_dict):
        record = JobRecord.model_validate(valid_record_dict)
        d = record.to_jsonl_dict()
        assert d["_meta"]["source"] == "topdev"
        assert d["_meta"]["dedup_key"] == "topdev:2136579"

    def test_factory_method_create(self, valid_raw_dict):
        record = JobRecord.create(
            source="topdev",
            source_job_id="2136579",
            url="https://topdev.vn/viec-lam/senior-backend-2136579",
            batch_id="2026-10-07_topdev_001",
            raw_data=valid_raw_dict,
        )
        assert record.meta.source == "topdev"
        assert record.raw.title == "Senior Backend Developer"

    def test_factory_missing_required_raw_field(self):
        with pytest.raises(ValidationError):
            JobRecord.create(
                source="topdev",
                source_job_id="123",
                url="https://topdev.vn/jobs/123",
                batch_id="2026-10-07_topdev_001",
                raw_data={
                    "title": "Dev",
                    # thiếu company, description_html, description_text
                },
            )


# ─────────────────────────────────────────────────────────────
# Tests: validate_record (end-to-end)
# ─────────────────────────────────────────────────────────────

class TestValidateRecord:

    def test_valid_record(self, valid_record_dict):
        record = validate_record(valid_record_dict)
        assert isinstance(record, JobRecord)

    def test_invalid_record_missing_meta(self, valid_raw_dict):
        with pytest.raises(ValidationError):
            validate_record({"raw": valid_raw_dict})

    def test_invalid_record_missing_raw(self, valid_metadata_dict):
        with pytest.raises(ValidationError):
            validate_record({"_meta": valid_metadata_dict})
