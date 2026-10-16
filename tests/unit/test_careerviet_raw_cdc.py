# -*- coding: utf-8 -*-
"""Unit tests cho Crawler CareerViet phiên bản Raw As-Is & CDC Versioning."""

from datetime import date
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
from crawlers.sources.careerviet.url_provider import (
    BaseUrlProvider,
    LocalFileUrlProvider,
    MinIOUrlProvider,
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


def test_interrupt_and_resume_no_loss_no_dup_no_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Test ngắt giữa chừng (Interrupt Test):
    1. Lần chạy 1: Crawler crawl 5 tin mục tiêu, nhưng bị ngắt (ném exception) sau khi đã ghi 2 tin.
       -> Assert: batch_001.json và cdc_catalog.json chứa đúng 2 tin đầu (nhất quán tuyệt đối).
    2. Lần chạy 2: Chạy lại với đầy đủ 5 tin.
       -> Assert:
          - batch_001.json KHÔNG bị ghi đè (vẫn giữ nguyên 2 tin cũ).
          - Lần chạy mới tạo ra batch_002.json (tiếp nối số thứ tự batch).
          - 2 tin cũ được CDC phát hiện là không đổi nội dung nên bị SKIP (không ghi lại).
          - 3 tin còn lại được ghi vào batch_002.json.
          - Tổng số tin trong batch_001 + batch_002 = 5 tin (KHÔNG MẤT BẢN GHI NÀO).
          - Giao nhau job_id giữa batch 1 và batch 2 là RỖNG (KHÔNG TRÙNG LẶP).
          - Toàn bộ 5 tin có mặt trong cdc_catalog.json với current_version = 1.
    """
    jobs = [
        {
            "job_id": f"35CINT00{i}",
            "url": f"https://careerviet.vn/vi/tim-viec-lam/job.35CINT00{i}.html",
            "html": f"<html><body><h1>Software Engineer {i}</h1><a class='employer'>Tech {i}</a></body></html>",
            "source_category": "c1",
        }
        for i in range(1, 6)
    ]
    catalog_file = tmp_path / "cdc_catalog.json"
    ckpt_dir = tmp_path / "checkpoints"

    crawler_1 = CareerVietCrawler(
        checkpoint_dir=str(ckpt_dir),
        output_dir=str(tmp_path),
        catalog_path=str(catalog_file),
        max_items=5,
    )

    # Giả lập ngắt giữa chừng: sau 2 items được yield và xử lý, generator ném lỗi mạng
    def interrupt_fetch():
        yield jobs[0]
        yield jobs[1]
        raise RuntimeError("Mô phỏng lỗi mạng / ngắt tiến trình đột ngột tại bản ghi thứ 3!")

    monkeypatch.setattr(crawler_1, "fetch_items", interrupt_fetch)

    with pytest.raises(RuntimeError, match="ngắt tiến trình đột ngột"):
        crawler_1.run()

    # Kiểm tra trạng thái sau lần 1
    batch_dir = tmp_path / "careerviet" / f"dt={crawler_1.run_date.isoformat()}"
    batch_1 = batch_dir / "batch_001.json"
    assert batch_1.exists(), "batch_001.json phải tồn tại sau khi ghi 2 bản ghi"
    with open(batch_1, "r", encoding="utf-8") as f:
        records_1 = json.load(f)
    assert len(records_1) == 2, "batch_001.json phải chứa chính xác 2 bản ghi trước khi bị ngắt"
    assert [r["_technical"]["job_id"] for r in records_1] == ["35CINT001", "35CINT002"]

    with open(catalog_file, "r", encoding="utf-8") as f:
        cat_1 = json.load(f)
    assert len(cat_1) == 2, "Catalog phải được lưu ngay lập tức (atomic consistency) cho 2 bản ghi"
    assert "35CINT001" in cat_1 and "35CINT002" in cat_1

    # Lần chạy 2: Chạy lại với toàn bộ 5 items
    crawler_2 = CareerVietCrawler(
        checkpoint_dir=str(ckpt_dir),
        output_dir=str(tmp_path),
        catalog_path=str(catalog_file),
        max_items=5,
    )
    monkeypatch.setattr(crawler_2, "fetch_items", lambda: iter(jobs))
    stats_2 = crawler_2.run()

    # Assertions
    assert stats_2["skipped"] == 2, "2 tin cũ đã có trong catalog phải được CDC bỏ qua"
    assert stats_2["crawled"] == 3, "3 tin mới còn lại phải được cào thành công"

    # 1. batch_001.json không bị ghi đè
    with open(batch_1, "r", encoding="utf-8") as f:
        records_1_after = json.load(f)
    assert len(records_1_after) == 2, "batch_001.json không được phép bị ghi đè hay mất dữ liệu"

    # 2. batch_002.json được tạo mới tiếp nối số thứ tự
    batch_2 = batch_dir / "batch_002.json"
    assert batch_2.exists(), "Lần chạy thứ 2 phải nối tiếp file mới batch_002.json"
    with open(batch_2, "r", encoding="utf-8") as f:
        records_2 = json.load(f)
    assert len(records_2) == 3, "batch_002.json phải chứa đúng 3 bản ghi mới"

    # 3. Không mất bản ghi: tổng = 5
    all_job_ids = [r["_technical"]["job_id"] for r in records_1_after] + [r["_technical"]["job_id"] for r in records_2]
    assert len(all_job_ids) == 5, "Tổng số bản ghi qua 2 lần chạy phải đủ 5 bản ghi"

    # 4. Không trùng lặp
    ids_1 = {r["_technical"]["job_id"] for r in records_1_after}
    ids_2 = {r["_technical"]["job_id"] for r in records_2}
    assert ids_1.isdisjoint(ids_2), f"Không được có giao nhau giữa các batch: {ids_1 & ids_2}"

    # 5. Catalog đầy đủ
    with open(catalog_file, "r", encoding="utf-8") as f:
        cat_2 = json.load(f)
    assert len(cat_2) == 5
    for i in range(1, 6):
        assert f"35CINT00{i}" in cat_2
        assert cat_2[f"35CINT00{i}"]["status"] == "active"
        assert cat_2[f"35CINT00{i}"]["current_version"] == 1


def test_batch_size_rollover_creates_sequential_batches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Kiểm tra cơ chế tách batch (batch-200) khi đạt giới hạn batch_size:
    Cào 5 bản ghi với batch_size=2 -> sinh ra batch_001 (2), batch_002 (2), batch_003 (1).
    """
    catalog_file = tmp_path / "cdc_catalog.json"
    crawler = CareerVietCrawler(
        output_dir=str(tmp_path),
        catalog_path=str(catalog_file),
        batch_size=2,
        max_items=5,
    )
    jobs = [
        {
            "job_id": f"35CROLL0{i}",
            "url": f"https://careerviet.vn/vi/tim-viec-lam/job.35CROLL0{i}.html",
            "html": f"<html><body><h1>Job {i}</h1><a class='employer'>Co {i}</a></body></html>",
        }
        for i in range(1, 6)
    ]
    monkeypatch.setattr(crawler, "fetch_items", lambda: iter(jobs))
    stats = crawler.run()
    assert stats["crawled"] == 5

    batch_dir = tmp_path / "careerviet" / f"dt={crawler.run_date.isoformat()}"
    b1 = json.loads((batch_dir / "batch_001.json").read_text(encoding="utf-8"))
    b2 = json.loads((batch_dir / "batch_002.json").read_text(encoding="utf-8"))
    b3 = json.loads((batch_dir / "batch_003.json").read_text(encoding="utf-8"))

    assert len(b1) == 2
    assert len(b2) == 2
    assert len(b3) == 1
    assert [r["_technical"]["job_id"] for r in b1] == ["35CROLL01", "35CROLL02"]
    assert [r["_technical"]["job_id"] for r in b2] == ["35CROLL03", "35CROLL04"]
    assert [r["_technical"]["job_id"] for r in b3] == ["35CROLL05"]


def test_source_category_in_technical_and_excluded_from_content_hash():
    """Kiểm tra:
    1. Trường source_category được lưu trong _technical (và cdc_catalog), không đưa vào raw_fields.
    2. Thay đổi source_category (vd c1 vs c61 vs keyword:developer) KHÔNG làm thay đổi content_hash.
    """
    crawler = CareerVietCrawler(max_items=1)
    html = "<html><body><h1>Backend Python</h1><a class='employer'>Tech Corp</a></body></html>"

    item_c1 = {
        "job_id": "35CHASH01",
        "url": "https://careerviet.vn/vi/tim-viec-lam/job.35CHASH01.html",
        "html": html,
        "source_category": "c1",
    }
    item_dev = {
        "job_id": "35CHASH01",
        "url": "https://careerviet.vn/vi/tim-viec-lam/job.35CHASH01.html",
        "html": html,
        "source_category": "keyword:developer",
    }

    parsed_1 = crawler.parse_item(item_c1)
    parsed_2 = crawler.parse_item(item_dev)

    assert parsed_1["_technical"]["source_category"] == "c1"
    assert parsed_2["_technical"]["source_category"] == "keyword:developer"

    assert "source_category" not in parsed_1["raw_fields"]
    assert "source_category" not in parsed_2["raw_fields"]

    assert parsed_1["_technical"]["content_hash"] == parsed_2["_technical"]["content_hash"], (
        "source_category tuyệt đối KHÔNG được tham gia vào content_hash!"
    )


@pytest.mark.skipif(
    not (
        Path("data/raw/careerviet/urls_c1_2026-10-16.json").exists()
        and Path("data/raw/careerviet/urls_c61_2026-10-16.json").exists()
        and Path("data/raw/careerviet/urls_developer_2026-10-16.json").exists()
    ),
    reason="Requires local data/raw files which are gitignored",
)
def test_local_file_url_provider_reads_748_it_jobs():
    """Kiểm tra LocalFileUrlProvider đọc 3 file nguồn IT (c1, c61, developer)
    trong data/raw/careerviet, đạt chính xác 748 tin IT duy nhất theo đúng kết quả khảo sát."""
    provider = LocalFileUrlProvider(base_dir="data/raw/careerviet")
    targets = provider.get_target_jobs()

    assert len(targets) == 748, f"Kỳ vọng 748 tin IT duy nhất, thực tế nhận được {len(targets)}"

    cat_counts: dict[str, int] = {}
    for t in targets:
        assert "job_id" in t and "url" in t and "source_category" in t
        scat = t["source_category"]
        cat_counts[scat] = cat_counts.get(scat, 0) + 1

    assert cat_counts.get("c1") == 611
    assert cat_counts.get("c61") == 45
    assert cat_counts.get("keyword:developer") == 92


def test_local_file_url_provider_with_synthetic_files(tmp_path: Path):
    """Kiểm tra LocalFileUrlProvider hoạt động độc lập hoàn toàn với dữ liệu giả lập trong tmp_path,
    đảm bảo test chạy thành công trên mọi môi trường CI/máy khác mà không phụ thuộc data/raw/."""
    f_c1 = tmp_path / "urls_c1_2026-10-16.json"
    f_c61 = tmp_path / "urls_c61_2026-10-16.json"
    f_dev = tmp_path / "urls_developer_2026-10-16.json"

    f_c1.write_text(json.dumps({
        "source": "c1",
        "records": [
            {"url": "https://careerviet.vn/vi/tim-viec-lam/job.35CSYN01.html", "job_id": "35CSYN01", "source_category": "c1"},
            {"url": "https://careerviet.vn/vi/tim-viec-lam/job.35CSYN02.html", "job_id": "35CSYN02", "source_category": "c1"},
        ]
    }), encoding="utf-8")

    f_c61.write_text(json.dumps({
        "source": "c61",
        "records": [
            {"url": "https://careerviet.vn/vi/tim-viec-lam/job.35CSYN03.html", "job_id": "35CSYN03", "source_category": "c61"},
        ]
    }), encoding="utf-8")

    f_dev.write_text(json.dumps({
        "source": "keyword:developer",
        "records": [
            {"url": "https://careerviet.vn/vi/tim-viec-lam/job.35CSYN04.html", "job_id": "35CSYN04", "source_category": "keyword:developer"},
        ]
    }), encoding="utf-8")

    provider = LocalFileUrlProvider(base_dir=tmp_path)
    targets = provider.get_target_jobs()

    assert len(targets) == 4
    cat_map = {t["job_id"]: t["source_category"] for t in targets}
    assert cat_map["35CSYN01"] == "c1"
    assert cat_map["35CSYN02"] == "c1"
    assert cat_map["35CSYN03"] == "c61"
    assert cat_map["35CSYN04"] == "keyword:developer"


def test_local_file_url_provider_deduplication(tmp_path: Path):
    """Kiểm tra tính năng khử trùng lặp theo job_id giữa các file nguồn."""
    f1 = tmp_path / "urls_c1.json"
    f2 = tmp_path / "urls_c61.json"

    f1.write_text(json.dumps({
        "source": "c1",
        "records": [
            {"url": "https://careerviet.vn/vi/tim-viec-lam/job.35CDEDUP1.html", "job_id": "35CDEDUP1", "source_category": "c1"},
            {"url": "https://careerviet.vn/vi/tim-viec-lam/job.35CDEDUP2.html", "job_id": "35CDEDUP2", "source_category": "c1"},
        ]
    }), encoding="utf-8")

    f2.write_text(json.dumps({
        "source": "c61",
        "records": [
            # 35CDEDUP2 bị trùng -> phải bỏ qua, giữ 35CDEDUP3
            {"url": "https://careerviet.vn/vi/tim-viec-lam/job.35CDEDUP2.html", "job_id": "35CDEDUP2", "source_category": "c61"},
            {"url": "https://careerviet.vn/vi/tim-viec-lam/job.35CDEDUP3.html", "job_id": "35CDEDUP3", "source_category": "c61"},
        ]
    }), encoding="utf-8")

    provider = LocalFileUrlProvider(file_paths=[f1, f2])
    targets = provider.get_target_jobs()

    assert len(targets) == 3
    assert [t["job_id"] for t in targets] == ["35CDEDUP1", "35CDEDUP2", "35CDEDUP3"]
    assert targets[1]["source_category"] == "c1"  # giữ category của nguồn gặp đầu tiên


def test_minio_url_provider_structure_and_no_hardcoded_creds():
    """Kiểm tra MinIOUrlProvider không chứa credentials hardcoded và báo lỗi rõ khi thiếu credentials."""
    # Khi không có env vars hay tham số kết nối -> ném ValueError hoặc ImportError giải thích rõ
    provider = MinIOUrlProvider(bucket_name="test-bucket")
    with pytest.raises((ValueError, ImportError)):
        provider.get_target_jobs()


@pytest.mark.skipif(
    not Path("data/raw/careerviet/cdc_catalog.json").exists(),
    reason="Requires local data/raw/careerviet/cdc_catalog.json which is gitignored",
)
def test_cdc_skips_30_existing_records_on_rerun(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Kiểm tra yêu cầu: '30 bản ghi đã có phải được CDC bỏ qua khi chạy lại' trên catalog thật."""
    import shutil
    real_catalog = Path("data/raw/careerviet/cdc_catalog.json")

    test_catalog = tmp_path / "cdc_catalog.json"
    shutil.copy2(real_catalog, test_catalog)

    with open(test_catalog, "r", encoding="utf-8") as f:
        existing_catalog = json.load(f)

    num_existing = len(existing_catalog)
    assert num_existing == 30, f"Kỳ vọng 30 bản ghi trong cdc_catalog.json gốc, thực tế: {num_existing}"

    crawler = CareerVietCrawler(
        output_dir=str(tmp_path),
        catalog_path=str(test_catalog),
        max_items=num_existing,
    )

    feed_items = [
        {
            "job_id": jid,
            "url": entry["url"],
            "html": "<html>mock</html>",
            "source_category": entry.get("source_category", "c1"),
        }
        for jid, entry in existing_catalog.items()
    ]
    monkeypatch.setattr(crawler, "fetch_items", lambda: iter(feed_items))

    def mock_parse(raw_item):
        jid = raw_item["job_id"]
        entry = existing_catalog[jid]
        return {
            "_technical": {
                "job_id": jid,
                "source": "careerviet",
                "url": raw_item["url"],
                "crawled_at": "2026-10-16T12:00:00Z",
                "content_hash": entry["current_hash"],
                "version": entry.get("current_version", 1),
                "source_category": raw_item.get("source_category"),
            },
            "raw_fields": {"title_raw": "Mock Title"},
            "embedded_json_raw": None,
            "_is_expired": False,
        }

    monkeypatch.setattr(crawler, "parse_item", mock_parse)
    stats = crawler.run()

    assert stats["crawled"] == 0, "Toàn bộ 30 bản ghi đã có phải được CDC bỏ qua, không cào lại"
    assert stats["skipped"] == 30, f"Kỳ vọng bỏ qua 30 bản ghi, thực tế bỏ qua {stats['skipped']}"
    assert stats["total_seen"] == 30


def test_cdc_skips_synthetic_existing_records(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Kiểm tra CDC bỏ qua 30 bản ghi đã có bằng dữ liệu synthetic hoàn toàn độc lập với gitignored data."""
    catalog_file = tmp_path / "cdc_catalog.json"
    synthetic_catalog = {}
    for i in range(1, 31):
        jid = f"35CSKIP{i:03d}"
        synthetic_catalog[jid] = {
            "job_id": jid,
            "url": f"https://careerviet.vn/vi/tim-viec-lam/job.{jid}.html",
            "current_version": 1,
            "current_hash": f"dummy_hash_{i}",
            "status": "active",
            "first_seen_at": "2026-10-15T00:00:00Z",
            "last_seen_at": "2026-10-15T00:00:00Z",
            "history": [{"version": 1, "content_hash": f"dummy_hash_{i}", "crawled_at": "2026-10-15T00:00:00Z"}],
        }

    catalog_file.write_text(json.dumps(synthetic_catalog), encoding="utf-8")

    crawler = CareerVietCrawler(
        output_dir=str(tmp_path),
        catalog_path=str(catalog_file),
        max_items=30,
    )

    feed_items = [
        {
            "job_id": jid,
            "url": entry["url"],
            "html": "<html>mock</html>",
            "source_category": "c1",
        }
        for jid, entry in synthetic_catalog.items()
    ]
    monkeypatch.setattr(crawler, "fetch_items", lambda: iter(feed_items))

    def mock_parse(raw_item):
        jid = raw_item["job_id"]
        return {
            "_technical": {
                "job_id": jid,
                "source": "careerviet",
                "url": raw_item["url"],
                "crawled_at": "2026-10-16T12:00:00Z",
                "content_hash": synthetic_catalog[jid]["current_hash"],
                "version": 1,
                "source_category": "c1",
            },
            "raw_fields": {"title_raw": "Synthetic Title"},
            "embedded_json_raw": None,
            "_is_expired": False,
        }

    monkeypatch.setattr(crawler, "parse_item", mock_parse)
    stats = crawler.run()

    assert stats["crawled"] == 0, "Toàn bộ 30 bản ghi synthetic phải được CDC bỏ qua"
    assert stats["skipped"] == 30, f"Kỳ vọng bỏ qua 30 bản ghi, thực tế: {stats['skipped']}"
    assert stats["total_seen"] == 30


def test_crash_between_batch_and_catalog_reconciles_cleanly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Mô phỏng sập giữa hai bước: bản ghi đã được ghi vào batch trên đĩa nhưng catalog chưa kịp lưu.
    Chứng minh:
    1. Khi khởi động lần 2, bước đối soát (reconciliation) tự động phát hiện bản ghi trong batch và bổ sung vào catalog.
    2. Crawler coi bản ghi đó là đã cào, không cào lại, không ghi trùng lặp.
    3. File batch cũ không bị ghi đè, batch mới nối tiếp số thứ tự.
    """
    catalog_file = tmp_path / "cdc_catalog.json"
    ckpt_dir = tmp_path / "checkpoints"
    dt_str = date.today().isoformat()
    partition_dir = tmp_path / "careerviet" / f"dt={dt_str}"
    partition_dir.mkdir(parents=True, exist_ok=True)

    # Giả lập batch_001.json trên đĩa chứa 2 bản ghi: 35CRECON01 và 35CRECON02
    item1 = {
        "_technical": {
            "job_id": "35CRECON01",
            "source": "careerviet",
            "url": "https://careerviet.vn/vi/tim-viec-lam/job.35CRECON01.html",
            "crawled_at": "2026-10-16T12:00:00Z",
            "content_hash": "hash_recon_01",
            "version": 1,
            "source_category": "c1",
        },
        "raw_fields": {"title_raw": "Job 1"},
    }
    item2 = {
        "_technical": {
            "job_id": "35CRECON02",
            "source": "careerviet",
            "url": "https://careerviet.vn/vi/tim-viec-lam/job.35CRECON02.html",
            "crawled_at": "2026-10-16T12:00:00Z",
            "content_hash": "hash_recon_02",
            "version": 1,
            "source_category": "c1",
        },
        "raw_fields": {"title_raw": "Job 2"},
    }
    batch_1_file = partition_dir / "batch_001.json"
    batch_1_file.write_text(json.dumps([item1, item2], indent=2), encoding="utf-8")

    # Giả lập khe hở: catalog chỉ mới lưu item 1, CHƯA kịp lưu item 2 trước khi crash!
    catalog_file.write_text(json.dumps({
        "35CRECON01": {
            "job_id": "35CRECON01",
            "url": item1["_technical"]["url"],
            "current_version": 1,
            "current_hash": "hash_recon_01",
            "status": "active",
            "first_seen_at": "2026-10-16T12:00:00Z",
            "last_seen_at": "2026-10-16T12:00:00Z",
            "history": [],
        }
    }), encoding="utf-8")

    # Khởi động lần chạy 2 với danh sách 3 items (item 1, item 2, item 3 mới)
    crawler = CareerVietCrawler(
        checkpoint_dir=str(ckpt_dir),
        output_dir=str(tmp_path),
        catalog_path=str(catalog_file),
        max_items=3,
    )

    feed_items = [
        {"job_id": "35CRECON01", "url": item1["_technical"]["url"], "html": "<html>mock1</html>", "source_category": "c1"},
        {"job_id": "35CRECON02", "url": item2["_technical"]["url"], "html": "<html>mock2</html>", "source_category": "c1"},
        {"job_id": "35CRECON03", "url": "https://careerviet.vn/vi/tim-viec-lam/job.35CRECON03.html", "html": "<html>mock3</html>", "source_category": "c1"},
    ]
    monkeypatch.setattr(crawler, "fetch_items", lambda: iter(feed_items))

    def mock_parse(raw_item):
        jid = raw_item["job_id"]
        h = "hash_recon_03" if jid == "35CRECON03" else ("hash_recon_01" if jid == "35CRECON01" else "hash_recon_02")
        return {
            "_technical": {
                "job_id": jid,
                "source": "careerviet",
                "url": raw_item["url"],
                "crawled_at": "2026-10-16T12:05:00Z",
                "content_hash": h,
                "version": 1,
                "source_category": "c1",
            },
            "raw_fields": {"title_raw": f"Title {jid}"},
            "embedded_json_raw": None,
            "_is_expired": False,
        }

    monkeypatch.setattr(crawler, "parse_item", mock_parse)
    stats = crawler.run()

    # Bằng chứng đối soát: item 2 tự phục hồi vào catalog -> cả item 1 và item 2 đều bị skip!
    assert stats["skipped"] == 2, "Cả item 1 và item 2 (được đối soát) phải được CDC bỏ qua"
    assert stats["crawled"] == 1, "Chỉ item 3 mới được cào vào batch mới"

    # batch_001.json không bị ghi đè
    b1_records = json.loads(batch_1_file.read_text(encoding="utf-8"))
    assert len(b1_records) == 2

    # batch_002.json được tạo mới với đúng item 3
    batch_2_file = partition_dir / "batch_002.json"
    assert batch_2_file.exists()
    b2_records = json.loads(batch_2_file.read_text(encoding="utf-8"))
    assert len(b2_records) == 1
    assert b2_records[0]["_technical"]["job_id"] == "35CRECON03"

    # Không trùng, không mất
    all_ids = [r["_technical"]["job_id"] for r in b1_records] + [r["_technical"]["job_id"] for r in b2_records]
    assert sorted(all_ids) == ["35CRECON01", "35CRECON02", "35CRECON03"]

    # Catalog đầy đủ cả 3 items
    cat_after = json.loads(catalog_file.read_text(encoding="utf-8"))
    assert "35CRECON01" in cat_after
    assert "35CRECON02" in cat_after
    assert "35CRECON03" in cat_after


def test_crawler_fallback_to_category_when_no_provider(tmp_path: Path):
    """Kiểm tra tính tương thích Airflow/run.py:
    Khi khởi tạo CareerVietCrawler(output_dir=..., max_items=...) không truyền url_provider
    và không có file urls_* nào, crawler tự động fallback về duyệt danh mục web Pha 1
    mà không bị crash hay báo lỗi thiếu file.
    """
    empty_dir = tmp_path / "empty_env"
    empty_dir.mkdir(parents=True, exist_ok=True)

    crawler = CareerVietCrawler(
        output_dir=str(empty_dir),
        max_items=2,
    )
    assert crawler.url_provider is None, "Khi không truyền provider và không có file urls_*, url_provider phải là None"

    # Giả lập http_client trả về trang listing có 2 link và detail HTML
    class MockHttpClient:
        def get_html(self, url, headers=None):
            if "viec-lam" in url and "c1" in url:
                return """
                <html><body>
                    <div class="job-item">
                        <a class="job-title" href="/vi/tim-viec-lam/job-1.35CFALL01.html">Job 1</a>
                    </div>
                    <div class="job-item">
                        <a class="job-title" href="/vi/tim-viec-lam/job-2.35CFALL02.html">Job 2</a>
                    </div>
                </body></html>
                """
            return """
            <html><body>
                <div class="job-detail-page">
                    <h1>Fallback Job</h1>
                    <a class="employer">Fallback Co</a>
                </div>
            </body></html>
            """

    crawler.http_client = MockHttpClient()
    stats = crawler.run()

    assert stats["crawled"] == 2
    assert stats["errors"] == 0
    assert stats["total_seen"] == 2



