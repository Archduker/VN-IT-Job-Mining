# -*- coding: utf-8 -*-
"""tests/test_text_preprocessing_and_metrics.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Kiểm thử toàn diện các module xử lý văn bản, chỉ số đơn biến/đa biến,
và thực thi 2 Chính sách đã phê duyệt:
  - Chính sách 1.B: Loại bỏ hoàn toàn Stub JD < 30 từ.
  - Chính sách 2.B: Chuẩn hóa dịch thuật thuật ngữ tiếng Anh sang tiếng Việt.
"""

import json
import os
import pytest

from preprocessing.transformation.html_cleaner import strip_html_tags
from preprocessing.transformation.bullet_stitcher import stitch_fragmented_bullets
from preprocessing.transformation.text_metrics import (
    calculate_text_metrics,
    detect_language,
    standardize_to_vietnamese,
    filter_valid_clean_records,
)
from preprocessing.integration.json_flattener import flatten_raw_job_record


def test_strip_html_tags():
    """Kiểm tra làm sạch mã rác HTML và CSS inline của TopDev."""
    html_sample = (
        '<div class="job-description" style="color: red; font-size: 14px;">\n'
        '  <p>Tuyển dụng <strong>Senior Java Developer</strong> &nbsp;làm việc tại HCM.</p><br/>\n'
        '  <ul style="margin: 0; padding: 0;">\n'
        '    <li>Kinh nghiệm Spring Boot &amp; Microservices.</li>\n'
        '  </ul>\n'
        '</div>'
    )
    cleaned = strip_html_tags(html_sample)
    assert "<" not in cleaned
    assert ">" not in cleaned
    assert "style=" not in cleaned
    assert "&nbsp;" not in cleaned
    assert "&amp;" not in cleaned
    assert "Senior Java Developer" in cleaned
    assert "Spring Boot & Microservices" in cleaned


def test_stitch_fragmented_bullets():
    """Kiểm tra thuật toán nối câu đứt đoạn của Vieclam24h."""
    fragmented = [
        "Có",
        "kinh nghiệm làm việc",
        "tối thiểu 1 năm với Python",
        "• Thành thạo SQL và Docker",
        "• Có tinh thần",
        "trách nhiệm cao",
    ]
    stitched = stitch_fragmented_bullets(fragmented)
    assert len(stitched) < len(fragmented)
    assert "Có kinh nghiệm làm việc tối thiểu 1 năm với Python" in stitched[0]
    assert "Có tinh thần trách nhiệm cao" in stitched[-1]


def test_calculate_text_metrics_and_stub_detection():
    """Kiểm tra tính toán chỉ số đơn biến và phát hiện Stub JD (Chính sách 1.B)."""
    # 1. Stub JD (< 30 words)
    stub_text = "Tuyển lập trình viên web gấp. Lương cao inbox zalo 0987654321."
    m_stub = calculate_text_metrics(stub_text)
    assert m_stub["word_count"] < 30
    assert m_stub["is_stub_jd"] is True

    # 2. Valid standard JD (> 30 words)
    valid_text = (
        "Chúng tôi cần tuyển Senior Backend Developer có trên 3 năm kinh nghiệm làm việc với Python và Django. "
        "Ứng viên có kiến thức sâu về kiến trúc Microservices, cơ sở dữ liệu PostgreSQL, Redis caching, "
        "và quy trình triển khai CI/CD trên nền tảng AWS Docker Kubernetes. Môi trường làm việc trẻ trung năng động, "
        "chế độ đãi ngộ hấp dẫn với bảo hiểm sức khỏe cao cấp và lương tháng 13."
    )
    m_valid = calculate_text_metrics(valid_text)
    assert m_valid["word_count"] >= 30
    assert m_valid["is_stub_jd"] is False
    assert 0.0 < m_valid["lexical_diversity_ttr"] <= 1.0


def test_filter_valid_clean_records_policy_1b():
    """Kiểm tra thực thi Chính sách 1.B: Loại bỏ hoàn toàn Stub JD khỏi tập dữ liệu."""
    records = [
        {"job_id_global": "job_1", "raw_description_text": "Tuyển gấp dev."},
        {"job_id_global": "job_2", "raw_description_text": "Lập trình viên Java với hơn 3 năm kinh nghiệm làm việc tại Hà Nội hoặc Hồ Chí Minh. Thành thạo Spring Boot, Hibernate, MySQL và Microservices architecture. Chế độ lương thưởng hấp dẫn và cơ hội thăng tiến."},
        {"job_id_global": "job_3", "raw_description_text": "Inbox zalo."},
    ]
    valid, dropped = filter_valid_clean_records(records, min_words=20)
    assert dropped == 2
    assert len(valid) == 1
    assert valid[0]["job_id_global"] == "job_2"


def test_language_detection_and_vietnamese_standardization():
    """Kiểm tra nhận diện ngôn ngữ và chuẩn hóa thuật ngữ tiếng Anh sang tiếng Việt (Chính sách 2.B)."""
    en_sample = "Job Description: We are looking for Full-time Senior Developer. Key Responsibilities and Requirements: 3 years of experience. Benefits: Health insurance and 13th month salary."
    lang = detect_language(en_sample)
    assert lang == "en"

    standardized = standardize_to_vietnamese(en_sample)
    assert "mô tả công việc" in standardized
    assert "yêu cầu ứng viên" in standardized
    assert "quyền lợi và đãi ngộ" in standardized
    assert "bảo hiểm sức khỏe" in standardized
    assert "lương tháng 13" in standardized


def test_topdev_real_html_cleaning():
    """Kiểm tra trên file thật của TopDev: bảo đảm sau khi làm phẳng không còn thẻ HTML."""
    path = "data/topdev/raw/2026-10-20/2139491_v1.json"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        flat = flatten_raw_job_record(data)
        desc = flat.get("raw_description_text") or ""
        assert "<div" not in desc
        assert "<p" not in desc
        assert "style=" not in desc
