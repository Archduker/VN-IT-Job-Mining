# -*- coding: utf-8 -*-
"""Unit tests cho module Khử trùng lặp ngữ nghĩa xuyên sàn (Cross-Platform Deduplicator)."""

import pandas as pd
import pytest

from preprocessing.normalization.cross_deduplicator import (
    normalize_company_name,
    compute_title_token_similarity,
    deduplicate_cross_platform_jobs,
)


def test_normalize_company_name():
    """Kiểm tra khả năng loại bỏ tiền tố/hậu tố pháp nhân và chuẩn hóa."""
    assert normalize_company_name("Công ty Cổ phần FPT Software") == "fpt software"
    assert normalize_company_name("CÔNG TY TNHH WIR GROUP VIỆT NAM") == "wir"
    assert normalize_company_name("Shopee Vietnam Co., Ltd.") == "shopee"
    assert normalize_company_name("Tập đoàn Công nghệ CMC") == "công nghệ cmc"


def test_compute_title_token_similarity():
    """Kiểm tra tính toán tương đồng tiêu đề dựa trên token Jaccard."""
    t1 = "Senior Software Engineer (ODOO)"
    t2 = "Senior Odoo Software Engineer"
    sim = compute_title_token_similarity(t1, t2)
    assert sim >= 0.8  # Rất tương đồng

    t3 = "Kế toán viên tổng hợp"
    assert compute_title_token_similarity(t1, t3) == 0.0


def test_cross_platform_deduplication_fusion():
    """Kiểm tra gom cụm và hợp nhất bản ghi vàng (Golden Record Fusion)."""
    raw_data = [
        {
            "job_id_global": "careerviet_1001",
            "source_platform": "careerviet",
            "job_title": "Senior Software Engineer (ODOO)",
            "company_name": "Công ty TNHH WIR Group",
            "primary_city": "Hồ Chí Minh",
            "raw_salary_text": "Thỏa thuận",
            "salary_min_vnd": None,
            "salary_max_vnd": None,
            "salary_source": None,
            "raw_description_text": "Phát triển các module ERP Odoo, viết Python, Postgres, Docker.",
            "skills_list": ["Python", "Odoo", "PostgreSQL"],
            "benefits_list": ["Bảo hiểm full lương"],
        },
        {
            "job_id_global": "vietnamworks_2002",
            "source_platform": "vietnamworks",
            "job_title": "Senior Odoo Software Engineer",
            "company_name": "WIR GROUP VIETNAM",
            "primary_city": "Hồ Chí Minh",
            "raw_salary_text": "35 - 50 triệu",
            "salary_min_vnd": 35000000.0,
            "salary_max_vnd": 50000000.0,
            "salary_source": "header_regex",
            "raw_description_text": "Tuyển Senior Odoo Software Engineer. Tham gia dự án ERP quy mô lớn, làm việc với Python, Docker, Odoo framework.",
            "skills_list": ["Docker", "ERP", "Python"],
            "benefits_list": ["Lương tháng 13", "Macbook Pro"],
        },
        {
            "job_id_global": "topcv_3003",
            "source_platform": "topcv",
            "job_title": "HR Manager - Trưởng phòng Nhân sự",
            "company_name": "Công ty TNHH WIR Group",
            "primary_city": "Hồ Chí Minh",
            "raw_salary_text": "25 - 30 triệu",
            "salary_min_vnd": 25000000.0,
            "salary_max_vnd": 30000000.0,
            "salary_source": "header_regex",
            "raw_description_text": "Quản lý tuyển dụng, xây dựng chính sách nhân sự cho công ty IT.",
            "skills_list": ["HR", "Recruitment"],
            "benefits_list": ["Thưởng hiệu quả"],
        },
    ]

    df = pd.DataFrame(raw_data)
    curated_df, metrics = deduplicate_cross_platform_jobs(df)

    # 3 bài đăng ban đầu -> 2 bài đăng sau khi khử trùng lặp (2 bài Odoo được gộp thành 1)
    assert len(curated_df) == 2
    assert metrics["total_input_records"] == 3
    assert metrics["total_golden_records"] == 2
    assert metrics["duplicates_removed"] == 1
    assert metrics["deduplication_rate_pct"] == round(1 / 3 * 100, 2)
    assert metrics["cross_platform_cluster_count"] == 1

    # Kiểm tra bản ghi Odoo đã được hợp nhất
    odoo_rec = curated_df[curated_df["job_title"].str.contains("Odoo|ODOO")].iloc[0]
    assert bool(odoo_rec["is_golden_merged"]) is True
    assert int(odoo_rec["duplicate_count"]) == 2
    assert set(odoo_rec["duplicate_platforms"]) == {"careerviet", "vietnamworks"}

    # Kiểm tra bổ sung lương: Bản ghi gốc CareerViet không có lương nhưng bản ghi gộp được bù lương từ VietnamWorks
    assert odoo_rec["salary_max_vnd"] == 50000000.0

    # Kiểm tra hợp nhất Kỹ năng và Quyền lợi
    skills = set(odoo_rec["skills_list"])
    assert "Python" in skills
    assert "Odoo" in skills
    assert "Docker" in skills
    assert "ERP" in skills

    benefits = set(odoo_rec["benefits_list"])
    assert "Bảo hiểm full lương" in benefits
    assert "Macbook Pro" in benefits
