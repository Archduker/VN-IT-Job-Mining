import pytest
from crawlers.common.url_ledger import (
    calculate_json_canonical_hash,
    calculate_json_field_hashes,
    diff_json_versions,
)


def test_canonical_json_hash_key_order_independence():
    """Hai dictionary cùng key-value nhưng khác thứ tự chèn phải ra cùng 1 hash."""
    doc1 = {
        "title": "Backend Engineer",
        "company": "Tech Corp",
        "salary": "20 - 30 triệu",
        "skills": ["Python", "FastAPI", "Docker"],
    }
    doc2 = {
        "skills": ["Python", "FastAPI", "Docker"],
        "salary": "20 - 30 triệu",
        "title": "Backend Engineer",
        "company": "Tech Corp",
    }
    hash1 = calculate_json_canonical_hash(doc1)
    hash2 = calculate_json_canonical_hash(doc2)

    assert hash1 != ""
    assert hash1 == hash2, "Canonical hash phải độc lập với thứ tự khóa trong JSON"


def test_canonical_json_hash_excludes_runtime_metadata():
    """Metadata động như scraped_at không được làm thay đổi content hash."""
    doc1 = {
        "title": "Data Analyst",
        "salary": "15 triệu",
        "scraped_at": "2026-10-19T08:00:00Z",
    }
    doc2 = {
        "title": "Data Analyst",
        "salary": "15 triệu",
        "scraped_at": "2026-10-20T12:00:00Z",
    }
    hash1 = calculate_json_canonical_hash(doc1)
    hash2 = calculate_json_canonical_hash(doc2)

    assert hash1 == hash2, "scraped_at không được ảnh hưởng đến nội dung băm"


def test_field_hashes_and_diff_detection():
    """Khi chỉ thay đổi lương, chỉ salary_hash bị đổi và diff_json_versions định vị đúng."""
    v1 = {
        "title": "Frontend Developer",
        "salary": "15 - 20 triệu",
        "deadline": "2026-10-30",
        "requirements": "ReactJS, TypeScript",
    }
    v2 = {
        "title": "Frontend Developer",
        "salary": "20 - 25 triệu",
        "deadline": "2026-10-30",
        "requirements": "ReactJS, TypeScript",
    }

    f1 = calculate_json_field_hashes(v1)
    f2 = calculate_json_field_hashes(v2)

    assert f1["title"] == f2["title"]
    assert f1["deadline"] == f2["deadline"]
    assert f1["requirements"] == f2["requirements"]
    assert f1["salary"] != f2["salary"], "Chỉ salary_hash bị thay đổi khi lương được điều chỉnh"

    diff_res = diff_json_versions(v1, v2)
    assert diff_res["is_modified"] is True
    assert diff_res["changed_fields"] == ["salary"]
    assert diff_res["diff"]["changed"]["salary"] == {
        "before": "15 - 20 triệu",
        "after": "20 - 25 triệu",
    }
