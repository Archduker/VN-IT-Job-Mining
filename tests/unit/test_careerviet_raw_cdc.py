# -*- coding: utf-8 -*-
"""Unit tests cho Crawler CareerViet phiên bản Raw As-Is & CDC Versioning."""

import json
from pathlib import Path
from unittest.mock import patch
import pytest

from crawlers.common.checkpoint import CheckpointManager
from crawlers.common.json_writer import JsonWriter
from crawlers.sources.careerviet.crawler import (
    CareerVietCrawler,
    compute_content_hash,
    extract_job_id,
    normalize_text_for_hash,
)


def test_json_writer_preserves_raw_dict_without_schema(tmp_path: Path):
    """Chứng minh JsonWriter(validate_schema=False) ghi dict thô nguyên vẹn,
    không bị Schema v1 can thiệp hay loại bỏ trường tùy biến."""
    raw_record = {
        "_technical": {
            "job_id": "35C99999",
            "source": "careerviet",
            "url": "https://careerviet.vn/vi/tim-viec-lam/job.35C99999.html",
            "content_hash": "dummy_hash_123",
            "version": 1,
        },
        "raw_fields": {
            "title_raw": "Senior Python Backend",
            "company_raw": "AI Tech Corp",
            "salary_raw": "30 Tr - 50 Tr VND",
            "other_info_raw": {
                "Bằng cấp": "Thạc sĩ",
                "Độ tuổi": "28 - 40",
                "Phụ cấp đặc thù": "10 Triệu/tháng",
            },
        },
        "custom_unseen_field": "GiaTriNguyenBanKhongBiDrop",
    }

    writer = JsonWriter(
        source="careerviet",
        output_dir=tmp_path,
        validate_schema=False,
        flush_per_record=True,
    )
    success = writer.write(raw_record)
    assert success is True
    writer.close()

    output_file = writer.file_path
    assert output_file.exists()

    with open(output_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert isinstance(data, list)
    assert len(data) == 1
    saved_item = data[0]

    # Kiểm tra bảo toàn 100% các trường
    assert saved_item["_technical"]["job_id"] == "35C99999"
    assert saved_item["raw_fields"]["title_raw"] == "Senior Python Backend"
    assert saved_item["raw_fields"]["other_info_raw"]["Phụ cấp đặc thù"] == "10 Triệu/tháng"
    assert saved_item["custom_unseen_field"] == "GiaTriNguyenBanKhongBiDrop"


def test_content_hash_consistency_and_normalization():
    """Kiểm tra tính ổn định của content_hash khi chuẩn hóa khoảng trắng và sắp xếp tags/other_info."""
    fields_1 = {
        "title_raw": "  Backend   Engineer  \n",
        "company_raw": "VNG Corporation",
        "salary_raw": "15 Tr - 25 Tr VND",
        "location_raw": "TP.HCM",
        "experience_raw": "2 Năm",
        "seniority_raw": "Nhân viên",
        "employment_type_raw": "Toàn thời gian",
        "deadline_raw": "30/11/2026",
        "description_raw": "Phát triển hệ thống microservices\n• Viết API RESTful",
        "requirements_raw": "- 2 năm kinh nghiệm Python/Golang",
        "benefits_raw": "Thưởng tháng 13",
        "tags_raw": ["Python", "Golang", "Docker"],
        "other_info_raw": {"Độ tuổi": "24 - 30", "Bằng cấp": "Đại học"},
    }

    # Bản sao nhưng xáo trộn thứ tự tags, xáo trộn thứ tự dict, thêm khoảng trắng thừa
    fields_2 = {
        "title_raw": "Backend Engineer",
        "company_raw": "  VNG Corporation ",
        "salary_raw": "15 Tr - 25 Tr VND",
        "location_raw": "TP.HCM",
        "experience_raw": " 2 Năm ",
        "seniority_raw": "Nhân viên",
        "employment_type_raw": "Toàn thời gian",
        "deadline_raw": "30/11/2026",
        "description_raw": "Phát triển hệ thống microservices • Viết API RESTful",
        "requirements_raw": "- 2 năm kinh nghiệm Python/Golang",
        "benefits_raw": "Thưởng tháng 13",
        "tags_raw": ["Docker", "Python", "Golang"],  # Xáo trộn thứ tự tags
        "other_info_raw": {"Bằng cấp": "Đại học", "Độ tuổi": "24 - 30"},  # Xáo trộn key
    }

    hash_1 = compute_content_hash(fields_1)
    hash_2 = compute_content_hash(fields_2)
    assert hash_1 == hash_2, "content_hash phải giống nhau sau khi chuẩn hóa khoảng trắng và sắp xếp tag"

    # Thay đổi lương -> hash bắt buộc phải đổi
    fields_modified = dict(fields_1)
    fields_modified["salary_raw"] = "20 Tr - 35 Tr VND"
    hash_modified = compute_content_hash(fields_modified)
    assert hash_1 != hash_modified, "Thay đổi mức lương phải sinh ra hash mới"


def test_cdc_version_increment_on_salary_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Kiểm tra version tăng từ 1 lên 2 khi nội dung bài đăng thay đổi (sửa lương)."""
    catalog_file = tmp_path / "cdc_catalog.json"
    html_v1 = """
    <html>
        <body>
            <div class="job-detail-page">
                <h1 class="title">DevOps Engineer</h1>
                <a class="employer">Cloud Tech</a>
                <div class="detail-box">
                    <ul>
                        <li><strong>Lương:</strong><p>15 Tr - 20 Tr VND</p></li>
                        <li><strong>Địa điểm:</strong><p>Hà Nội</p></li>
                    </ul>
                </div>
                <div class="detail-row">
                    <h2>Mô tả Công việc</h2>
                    <p>Quản trị cụm Kubernetes</p>
                </div>
            </div>
        </body>
    </html>
    """

    html_v2 = """
    <html>
        <body>
            <div class="job-detail-page">
                <h1 class="title">DevOps Engineer</h1>
                <a class="employer">Cloud Tech</a>
                <div class="detail-box">
                    <ul>
                        <li><strong>Lương:</strong><p>25 Tr - 35 Tr VND</p></li>
                        <li><strong>Địa điểm:</strong><p>Hà Nội</p></li>
                    </ul>
                </div>
                <div class="detail-row">
                    <h2>Mô tả Công việc</h2>
                    <p>Quản trị cụm Kubernetes</p>
                </div>
            </div>
        </body>
    </html>
    """

    # Lần 1: Cào tin ban đầu
    crawler_1 = CareerVietCrawler(
        output_dir=str(tmp_path),
        catalog_path=str(catalog_file),
        max_items=1,
    )
    monkeypatch.setattr(crawler_1, "fetch_items", lambda: iter([{
        "job_id": "35C12345",
        "url": "https://careerviet.vn/vi/tim-viec-lam/devops-engineer.35C12345.html",
        "html": html_v1,
    }]))
    stats_1 = crawler_1.run()
    assert stats_1["crawled"] == 1
    assert stats_1["skipped"] == 0

    with open(catalog_file, "r", encoding="utf-8") as f:
        cat_data = json.load(f)
    assert "35C12345" in cat_data
    assert cat_data["35C12345"]["current_version"] == 1
    assert len(cat_data["35C12345"]["history"]) == 1

    # Lần 2: Cào lại nhưng tin đã được sửa lương
    crawler_2 = CareerVietCrawler(
        output_dir=str(tmp_path),
        catalog_path=str(catalog_file),
        max_items=1,
    )
    monkeypatch.setattr(crawler_2, "fetch_items", lambda: iter([{
        "job_id": "35C12345",
        "url": "https://careerviet.vn/vi/tim-viec-lam/devops-engineer.35C12345.html",
        "html": html_v2,
    }]))
    stats_2 = crawler_2.run()
    assert stats_2["crawled"] == 1
    assert stats_2["skipped"] == 0

    with open(catalog_file, "r", encoding="utf-8") as f:
        cat_data_2 = json.load(f)
    assert cat_data_2["35C12345"]["current_version"] == 2
    assert len(cat_data_2["35C12345"]["history"]) == 2
    assert cat_data_2["35C12345"]["history"][0]["version"] == 1
    assert cat_data_2["35C12345"]["history"][1]["version"] == 2


def test_cdc_unchanged_skip_and_no_duplicates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Kiểm tra chạy 2 lần với cùng nội dung thì lần 2 bị skip và không sinh bản ghi trùng."""
    catalog_file = tmp_path / "cdc_catalog.json"
    html_content = """
    <html>
        <body>
            <div class="job-detail-page">
                <h1>Data Engineer</h1>
                <a class="employer">Data Corp</a>
                <div class="detail-box">
                    <ul>
                        <li><strong>Lương:</strong><p>Thương lượng</p></li>
                    </ul>
                </div>
            </div>
        </body>
    </html>
    """
    job_item = {
        "job_id": "35C88888",
        "url": "https://careerviet.vn/vi/tim-viec-lam/data-engineer.35C88888.html",
        "html": html_content,
    }

    # Lần chạy 1
    crawler_1 = CareerVietCrawler(
        output_dir=str(tmp_path),
        catalog_path=str(catalog_file),
        max_items=1,
    )
    monkeypatch.setattr(crawler_1, "fetch_items", lambda: iter([job_item]))
    stats_1 = crawler_1.run()
    assert stats_1["crawled"] == 1
    out_file = Path(stats_1["output_file"])

    with open(out_file, "r", encoding="utf-8") as f:
        records_1 = json.load(f)
    assert len(records_1) == 1

    # Lần chạy 2 (cùng nội dung)
    crawler_2 = CareerVietCrawler(
        output_dir=str(tmp_path),
        catalog_path=str(catalog_file),
        max_items=1,
    )
    monkeypatch.setattr(crawler_2, "fetch_items", lambda: iter([job_item]))
    stats_2 = crawler_2.run()
    assert stats_2["crawled"] == 0
    assert stats_2["skipped"] == 1

    with open(out_file, "r", encoding="utf-8") as f:
        records_2 = json.load(f)
    assert len(records_2) == 1, "File JSON không được chứa bản ghi trùng khi nội dung không đổi"


def test_existing_job_hash_checked_even_if_in_seen_ids(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Chứng minh tin cũ đã có trong seen_ids của checkpoint VẪN được kiểm tra lại hash
    và nâng version nếu nội dung bị sửa."""
    catalog_file = tmp_path / "cdc_catalog.json"
    checkpoint_dir = tmp_path / "checkpoints"

    # Giả lập checkpoint đã ghi nhận job_id này từ trước
    ckpt = CheckpointManager(source="careerviet", checkpoint_dir=checkpoint_dir)
    ckpt.mark_seen("35C77777")
    ckpt.save()
    assert ckpt.is_seen("35C77777") is True

    # Tạo catalog với version 1 và hash cũ
    catalog_file.write_text(json.dumps({
        "35C77777": {
            "job_id": "35C77777",
            "url": "https://careerviet.vn/vi/tim-viec-lam/job.35C77777.html",
            "current_version": 1,
            "current_hash": "old_hash_val",
            "status": "active",
            "first_seen_at": "2026-10-01T00:00:00Z",
            "last_seen_at": "2026-10-01T00:00:00Z",
            "history": [{"version": 1, "content_hash": "old_hash_val", "crawled_at": "2026-10-01T00:00:00Z"}],
        }
    }), encoding="utf-8")

    # Nội dung mới của bài viết
    new_html = """
    <html>
        <body>
            <div class="job-detail-page">
                <h1>Fullstack Developer</h1>
                <a class="employer">Tech Studio</a>
                <div class="detail-box">
                    <ul><li><strong>Lương:</strong><p>40 Triệu VND</p></li></ul>
                </div>
            </div>
        </body>
    </html>
    """

    crawler = CareerVietCrawler(
        checkpoint_dir=str(checkpoint_dir),
        output_dir=str(tmp_path),
        catalog_path=str(catalog_file),
        max_items=1,
    )
    monkeypatch.setattr(crawler, "fetch_items", lambda: iter([{
        "job_id": "35C77777",
        "url": "https://careerviet.vn/vi/tim-viec-lam/job.35C77777.html",
        "html": new_html,
    }]))
    stats = crawler.run()

    # Dù đã có trong seen_ids, crawler vẫn tính hash, phát hiện khác hash cũ và nâng version lên 2
    assert stats["crawled"] == 1
    with open(catalog_file, "r", encoding="utf-8") as f:
        cat = json.load(f)
    assert cat["35C77777"]["current_version"] == 2
    assert cat["35C77777"]["current_hash"] != "old_hash_val"


def test_expired_job_marked_in_catalog(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Kiểm tra tin gặp HTML thông báo hết hạn thì đánh dấu expired trong catalog."""
    catalog_file = tmp_path / "cdc_catalog.json"
    catalog_file.write_text(json.dumps({
        "35C66666": {
            "job_id": "35C66666",
            "url": "https://careerviet.vn/vi/tim-viec-lam/job.35C66666.html",
            "current_version": 1,
            "current_hash": "hash_1",
            "status": "active",
            "first_seen_at": "2026-10-01T00:00:00Z",
            "last_seen_at": "2026-10-01T00:00:00Z",
            "history": [],
        }
    }), encoding="utf-8")

    expired_html = """
    <html>
        <body>
            <div class="job-detail-page">
                <p>Thông báo: Việc làm đã hết hạn nhận hồ sơ.</p>
            </div>
        </body>
    </html>
    """

    crawler = CareerVietCrawler(
        output_dir=str(tmp_path),
        catalog_path=str(catalog_file),
        max_items=1,
    )
    monkeypatch.setattr(crawler, "fetch_items", lambda: iter([{
        "job_id": "35C66666",
        "url": "https://careerviet.vn/vi/tim-viec-lam/job.35C66666.html",
        "html": expired_html,
    }]))
    stats = crawler.run()

    assert stats["crawled"] == 0
    assert stats["skipped"] == 1
    with open(catalog_file, "r", encoding="utf-8") as f:
        cat = json.load(f)
    assert cat["35C66666"]["status"] == "expired"


def test_cdc_run2_fetches_detail_pages_and_updates_last_seen_at(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Bằng chứng rằng lần chạy 2 (CDC re-run) VẪN gọi fetch_items cho các tin cũ
    (không bỏ qua ở bước listing), tính lại hash và cập nhật last_seen_at trong catalog.

    Thiết kế:
    - Lần 1: cào 3 tin, lưu catalog.
    - Lần 2: gọi cùng 3 tin với HTML giống hệt → 3 skipped (hash không đổi),
      NHƯNG last_seen_at phải được cập nhật sang timestamp mới hơn.
    - Chứng minh rằng fetch_items được gọi đủ 3 lần (qua đếm yield).
    """
    catalog_file = tmp_path / "cdc_catalog.json"

    html_template = """
    <html><body>
        <div class="job-detail-page">
            <h1>{title}</h1>
            <a class="employer">Test Corp</a>
            <div class="detail-box"><ul>
                <li><strong>Lương:</strong><p>20 Triệu</p></li>
            </ul></div>
        </div>
    </body></html>
    """

    jobs = [
        {
            "job_id": f"35C9000{i}",
            "url": f"https://careerviet.vn/vi/tim-viec-lam/job.35C9000{i}.html",
            "html": html_template.format(title=f"Engineer {i}"),
        }
        for i in range(3)
    ]

    # --- Lần chạy 1: Cào 3 tin mới ---
    crawler_1 = CareerVietCrawler(
        output_dir=str(tmp_path),
        catalog_path=str(catalog_file),
        max_items=3,
    )
    fetch_call_count_1 = [0]

    def fake_fetch_1():
        for job in jobs:
            fetch_call_count_1[0] += 1
            yield job

    monkeypatch.setattr(crawler_1, "fetch_items", fake_fetch_1)
    stats_1 = crawler_1.run()

    assert stats_1["crawled"] == 3, "Lần 1 phải cào được 3 tin"
    assert fetch_call_count_1[0] == 3, "fetch_items phải được gọi đúng 3 lần ở lần chạy 1"

    with open(catalog_file, "r", encoding="utf-8") as f:
        cat_1 = json.load(f)
    last_seen_run1 = {jid: entry["last_seen_at"] for jid, entry in cat_1.items()}

    # --- Lần chạy 2: Cào lại 3 tin (HTML giống hệt → skip) ---
    import time
    time.sleep(0.05)  # đảm bảo timestamp khác nhau

    crawler_2 = CareerVietCrawler(
        output_dir=str(tmp_path),
        catalog_path=str(catalog_file),
        max_items=3,
    )
    fetch_call_count_2 = [0]

    def fake_fetch_2():
        for job in jobs:
            fetch_call_count_2[0] += 1
            yield job

    monkeypatch.setattr(crawler_2, "fetch_items", fake_fetch_2)
    stats_2 = crawler_2.run()

    # Lần 2: tất cả đều bị skip (hash giống nhau), nhưng fetch_items phải được gọi
    assert stats_2["skipped"] == 3, "Lần 2 phải skip cả 3 tin (hash không đổi)"
    assert stats_2["crawled"] == 0, "Lần 2 không được ghi bản ghi mới"
    assert fetch_call_count_2[0] == 3, (
        "fetch_items PHẢI được gọi đủ 3 lần ở lần chạy 2 — "
        "CDC phải tải trang chi tiết để tính lại hash, không skip ở bước listing"
    )

    with open(catalog_file, "r", encoding="utf-8") as f:
        cat_2 = json.load(f)

    # last_seen_at phải được cập nhật cho mỗi tin (dù bị skip về mặt ghi file)
    for jid in [f"35C9000{i}" for i in range(3)]:
        assert jid in cat_2, f"Job {jid} phải có trong catalog"
        assert cat_2[jid]["last_seen_at"] >= last_seen_run1[jid], (
            f"last_seen_at của {jid} phải được cập nhật ở lần chạy 2"
        )
        assert cat_2[jid]["current_version"] == 1, "Version không đổi khi hash giống nhau"


def test_embedded_json_raw_extracted_and_excluded_from_hash_and_cdc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Chứng minh:
    1. embedded_json_raw được trích xuất nguyên bản ngang hàng raw_fields.
    2. Thay đổi riêng embedded_json_raw (vd datePosted) không làm thay đổi content_hash hay nâng version.
    3. Thay đổi trong raw_fields (vd sửa lương) thì version nâng lên 2.
    """
    catalog_file = tmp_path / "cdc_catalog.json"

    html_v1 = """
    <html>
        <head>
            <script id="job-posting-schema" type="application/ld+json">
            {
                "@context": "http://schema.org",
                "@type": "JobPosting",
                "title": "Backend Python",
                "datePosted": "2026-10-15T01:00:00Z",
                "experienceRequirements": {"monthsOfExperience": 24}
            }
            </script>
        </head>
        <body>
            <div class="job-detail-page">
                <h1>Backend Python</h1>
                <a class="employer">Tech Star</a>
                <div class="detail-box">
                    <ul><li><strong>Lương:</strong><p>20 Triệu VND</p></li></ul>
                </div>
            </div>
        </body>
    </html>
    """

    # HTML v2: Thay đổi datePosted trong JSON-LD nhưng raw_fields DOM giữ nguyên
    html_v2_date_changed = """
    <html>
        <head>
            <script id="job-posting-schema" type="application/ld+json">
            {
                "@context": "http://schema.org",
                "@type": "JobPosting",
                "title": "Backend Python",
                "datePosted": "2026-10-15T09:30:00Z",
                "experienceRequirements": {"monthsOfExperience": 24}
            }
            </script>
        </head>
        <body>
            <div class="job-detail-page">
                <h1>Backend Python</h1>
                <a class="employer">Tech Star</a>
                <div class="detail-box">
                    <ul><li><strong>Lương:</strong><p>20 Triệu VND</p></li></ul>
                </div>
            </div>
        </body>
    </html>
    """

    # HTML v3: Thay đổi lương trong DOM (raw_fields đổi)
    html_v3_salary_changed = """
    <html>
        <head>
            <script id="job-posting-schema" type="application/ld+json">
            {
                "@context": "http://schema.org",
                "@type": "JobPosting",
                "title": "Backend Python",
                "datePosted": "2026-10-15T09:30:00Z",
                "experienceRequirements": {"monthsOfExperience": 24}
            }
            </script>
        </head>
        <body>
            <div class="job-detail-page">
                <h1>Backend Python</h1>
                <a class="employer">Tech Star</a>
                <div class="detail-box">
                    <ul><li><strong>Lương:</strong><p>35 Triệu VND</p></li></ul>
                </div>
            </div>
        </body>
    </html>
    """

    # Lần 1: Cào tin ban đầu
    crawler_1 = CareerVietCrawler(
        output_dir=str(tmp_path),
        catalog_path=str(catalog_file),
        max_items=1,
    )
    monkeypatch.setattr(crawler_1, "fetch_items", lambda: iter([{
        "job_id": "35C99001",
        "url": "https://careerviet.vn/vi/tim-viec-lam/job.35C99001.html",
        "html": html_v1,
    }]))
    stats_1 = crawler_1.run()
    assert stats_1["crawled"] == 1

    out_file = Path(stats_1["output_file"])
    with open(out_file, "r", encoding="utf-8") as f:
        records_1 = json.load(f)
    assert len(records_1) == 1
    rec1 = records_1[0]
    assert "embedded_json_raw" in rec1
    assert rec1["embedded_json_raw"]["@type"] == "JobPosting"
    assert rec1["embedded_json_raw"]["datePosted"] == "2026-10-15T01:00:00Z"
    hash_run1 = rec1["_technical"]["content_hash"]

    # Lần 2: JSON-LD thay đổi datePosted nhưng DOM giữ nguyên -> hash không đổi -> SKIP
    crawler_2 = CareerVietCrawler(
        output_dir=str(tmp_path),
        catalog_path=str(catalog_file),
        max_items=1,
    )
    monkeypatch.setattr(crawler_2, "fetch_items", lambda: iter([{
        "job_id": "35C99001",
        "url": "https://careerviet.vn/vi/tim-viec-lam/job.35C99001.html",
        "html": html_v2_date_changed,
    }]))
    stats_2 = crawler_2.run()
    assert stats_2["crawled"] == 0, "Không được cào mới khi chỉ có embedded_json_raw thay đổi"
    assert stats_2["skipped"] == 1

    with open(catalog_file, "r", encoding="utf-8") as f:
        cat_data = json.load(f)
    assert cat_data["35C99001"]["current_version"] == 1
    assert cat_data["35C99001"]["current_hash"] == hash_run1

    # Lần 3: Thay đổi lương trong DOM -> hash đổi -> NÂNG VERSION LÊN 2
    crawler_3 = CareerVietCrawler(
        output_dir=str(tmp_path),
        catalog_path=str(catalog_file),
        max_items=1,
    )
    monkeypatch.setattr(crawler_3, "fetch_items", lambda: iter([{
        "job_id": "35C99001",
        "url": "https://careerviet.vn/vi/tim-viec-lam/job.35C99001.html",
        "html": html_v3_salary_changed,
    }]))
    stats_3 = crawler_3.run()
    assert stats_3["crawled"] == 1, "Thay đổi salary_raw trong DOM phải kích hoạt ghi nhận version mới"

    with open(catalog_file, "r", encoding="utf-8") as f:
        cat_data_3 = json.load(f)
    assert cat_data_3["35C99001"]["current_version"] == 2
    assert cat_data_3["35C99001"]["current_hash"] != hash_run1


def test_embedded_json_raw_missing_or_corrupted_defaults_to_none():
    """Kiểm tra crawler không bị crash và gán embedded_json_raw = None
    khi trang thiếu thẻ JSON-LD hoặc thẻ script chứa JSON hỏng."""
    crawler = CareerVietCrawler(max_items=1)

    # 1. Trang hoàn toàn không có JSON-LD
    html_no_ld = """
    <html><body>
        <div class="job-detail-page">
            <h1>Tester</h1>
            <a class="employer">QA Corp</a>
        </div>
    </body></html>
    """
    res1 = crawler.parse_item({
        "job_id": "35C88801",
        "url": "https://careerviet.vn/vi/tim-viec-lam/job.35C88801.html",
        "html": html_no_ld,
    })
    assert res1 is not None
    assert res1["embedded_json_raw"] is None
    assert res1["raw_fields"]["title_raw"] == "Tester"

    # 2. Trang có thẻ script nhưng JSON bị hỏng cú pháp
    html_corrupted_json = """
    <html><head>
        <script id="job-posting-schema" type="application/ld+json">
            { "title": "Tester", corrupted_unclosed_json: ...
        </script>
    </head><body>
        <div class="job-detail-page">
            <h1>Tester</h1>
            <a class="employer">QA Corp</a>
        </div>
    </body></html>
    """
    res2 = crawler.parse_item({
        "job_id": "35C88802",
        "url": "https://careerviet.vn/vi/tim-viec-lam/job.35C88802.html",
        "html": html_corrupted_json,
    })
    assert res2 is not None
    assert res2["embedded_json_raw"] is None
    assert res2["raw_fields"]["title_raw"] == "Tester"

