# -*- coding: utf-8 -*-
"""Unit tests cho TopCV Crawler đạt chuẩn Modern Data Stack."""

import json
from pathlib import Path

import pytest

from crawlers.sources.topcv.crawler import (
    TopCVCrawler,
    build_raw_envelope,
    build_raw_payload,
    extract_job_id,
)

SAMPLE_HTML_PATH = Path("crawlers/sources/topcv/samples/2323906.html")
SAMPLE_JSON_PATH = Path("crawlers/sources/topcv/samples/2323906_v1.json")


def test_extract_job_id():
    """Kiểm tra trích xuất ID từ nhiều định dạng TopCV URL."""
    assert (
        extract_job_id(
            "https://www.topcv.vn/viec-lam/chuyen-vien-cao-cap-san-pham-mobile-app/2323906.html?ta_source=JobSearchList_LinkDetail"
        )
        == "2323906"
    )
    assert extract_job_id("https://www.topcv.vn/viec-lam/senior-developer/123456.html") == "123456"
    assert extract_job_id("https://www.topcv.vn/viec-lam/ky-su-phan-mem-7891011.html") == "7891011"


def test_build_raw_payload_completeness():
    """Kiểm tra bóc tách 100% trường dữ liệu theo necessary.md từ tin mẫu 2323906."""
    if not SAMPLE_HTML_PATH.is_file():
        pytest.skip(f"File mẫu {SAMPLE_HTML_PATH} đã được dọn dẹp khỏi repo")
    html = SAMPLE_HTML_PATH.read_text(encoding="utf-8")
    payload = build_raw_payload(html)

    # 1. Header fields
    assert payload["title"] == "Chuyên Viên Cao Cấp Sản Phẩm Mobile App"
    assert payload["salary_raw"] == "30 - 50 triệu"
    assert "Hà Nội" in payload["location"]
    assert "5 năm" in payload["experience"]
    assert "06/11/2026" in payload["deadline_raw"]

    # 2. Overview tags
    assert "Yêu cầu" in payload["overview_tags"]
    assert "5 năm kinh nghiệm chuyên môn" in payload["overview_tags"]["Yêu cầu"]
    assert "Quyền lợi" in payload["overview_tags"]
    assert "Bảo hiểm xã hội" in payload["overview_tags"]["Quyền lợi"]
    assert "Chuyên môn" in payload["overview_tags"]
    assert "Chăm sóc khách hàng" in payload["overview_tags"]["Chuyên môn"]

    # 3. Bullets
    assert len(payload["description_bullets"]) >= 5
    assert len(payload["requirements_bullets"]) >= 5
    assert len(payload["benefits_bullets"]) >= 5

    # 4. Tags chuyên biệt
    assert "Ngân hàng" in payload["industry_knowledge"]
    assert "Quản Lý Sản Phẩm" in payload["required_skills"]
    assert "Bảo hiểm xã hội" in payload["welfare_tags"]
    assert "Ăn trưa" in payload["allowance_tags"]

    # 5. Working place & time
    assert len(payload["working_places"]) >= 1
    assert "Thứ 2 - Thứ 6" in payload["working_time"]
    assert "Ứng tuyển" in payload["apply_method"]

    # 6. General info & Company info
    assert payload["general_info"]["Cấp bậc"] == "Nhân viên"
    assert payload["general_info"]["Loại hình làm việc"] == "Toàn thời gian"
    assert "AEON" in payload["company"]
    assert "1000+" in payload["company_scale"]
    assert "Hà Nội" in payload["company_address"]
    assert "tiền tệ" in payload["company_industry"]


def test_build_raw_envelope_metadata_constraints():
    """Kiểm tra chỉ lưu DUY NHẤT 1 trường content_hash và có trường language."""
    html = (
        SAMPLE_HTML_PATH.read_text(encoding="utf-8")
        if SAMPLE_HTML_PATH.is_file()
        else "<div class='job-header'><h1 class='title'>Chuyên Viên Mobile App</h1></div>"
    )
    url = "https://www.topcv.vn/viec-lam/chuyen-vien-cao-cap-san-pham-mobile-app/2323906.html"
    env = build_raw_envelope(html, job_id="2323906", url=url)

    metadata = env.metadata
    assert metadata["job_id"] == "2323906"
    assert metadata["source"] == "topcv"
    assert metadata["language"] in ["vi", "en"]
    assert "content_hash" in metadata
    assert len(metadata["content_hash"]) == 64

    # Ràng buộc nghiêm ngặt: KHÔNG có các trường hash dư thừa
    assert "canonical_hash" not in metadata, "Metadata không được chứa canonical_hash"
    assert "field_hashes" not in metadata, "Metadata không được chứa field_hashes"


def test_content_hash_determinism():
    """Kiểm tra tính tất định của mã SHA-256 từ canonical raw_payload."""
    html = (
        SAMPLE_HTML_PATH.read_text(encoding="utf-8")
        if SAMPLE_HTML_PATH.is_file()
        else "<div class='job-header'><h1 class='title'>Chuyên Viên Mobile App</h1></div>"
    )
    env1 = build_raw_envelope(html, "2323906", "https://url1")
    env2 = build_raw_envelope(html, "2323906", "https://url2")
    assert env1.metadata["content_hash"] == env2.metadata["content_hash"]


def test_two_phase_crawler_interface():
    """Kiểm tra crawler kế thừa BaseCrawler và có đủ 2 pha."""
    crawler = TopCVCrawler()
    assert hasattr(crawler, "discover_urls")
    assert hasattr(crawler, "crawl_details")
    assert crawler.source_name == "topcv"
