# -*- coding: utf-8 -*-
"""Unit tests for crawlers.preprocessing.preClean."""

from pathlib import Path
import pytest

from crawlers.preprocessing.preClean.text_cleaner import (
    clean_text,
    clean_single_line_text,
    generate_unified_id,
    normalize_unicode_nfc,
)
from crawlers.preprocessing.preClean.salary_parser import parse_salary_to_numbers
from crawlers.preprocessing.preClean.anomaly_detector import detect_anomalous_sample
from crawlers.preprocessing.preClean.pipeline import PreCleanPipeline


def test_generate_unified_id():
    assert generate_unified_id("TopCV", "2305925") == "topcv_2305925"
    assert generate_unified_id("VietnamWorks", 2109062) == "vietnamworks_2109062"


def test_clean_text_and_unicode_nfc():
    raw_html = "<p>Tuyển&nbsp;<b>Lập trình viên</b> Python \u200b\r\n• Yêu cầu 2 năm kinh nghiệm</p>"
    cleaned = clean_text(raw_html)
    assert "<p>" not in cleaned
    assert "&nbsp;" not in cleaned
    assert "\u200b" not in cleaned
    assert "Tuyển Lập trình viên Python" in cleaned
    assert "Yêu cầu 2 năm kinh nghiệm" in cleaned


def test_salary_parser_vnd_millions():
    res = parse_salary_to_numbers("10 - 20 triệu")
    assert res["salary_min"] == 10_000_000
    assert res["salary_max"] == 20_000_000
    assert res["salary_currency"] == "VND"
    assert res["salary_type"] == "RANGE"


def test_salary_parser_dict_scaling():
    raw_dict = {
        "salary_text": "9 - 11 triệu",
        "salary_min": 9.0,
        "salary_max": 11.0,
        "salary_currency": "VND",
        "is_negotiable": False,
    }
    res = parse_salary_to_numbers(raw_dict)
    assert res["salary_min"] == 9_000_000
    assert res["salary_max"] == 11_000_000
    assert res["salary_currency"] == "VND"
    assert res["salary_type"] == "RANGE"


def test_salary_parser_usd_and_negotiable():
    usd_res = parse_salary_to_numbers("$ 700-2,000 /tháng")
    assert usd_res["salary_min"] == 700
    assert usd_res["salary_max"] == 2000
    assert usd_res["salary_currency"] == "USD"
    assert usd_res["salary_type"] == "RANGE"

    neg_res = parse_salary_to_numbers("Thoả thuận")
    assert neg_res["salary_min"] is None
    assert neg_res["salary_max"] is None
    assert neg_res["salary_type"] == "NEGOTIABLE"


def test_anomaly_detector():
    corrupted_sample = {
        "raw": {
            "title": "www.topcv.vn",
            "company": "Unknown",
            "description_list": ["TopCV tuyển dụng"],
            "requirements_list": [],
        }
    }
    is_bad, reason = detect_anomalous_sample(corrupted_sample)
    assert is_bad is True
    assert "DUMMY" in reason

    valid_sample = {
        "raw": {
            "title": "Senior Python Developer",
            "company": "FPT Software",
            "description_list": ["Phát triển hệ thống microservices backend"],
            "requirements_list": ["Từ 3 năm kinh nghiệm Python, FastAPI, Docker"],
        }
    }
    is_valid, _ = detect_anomalous_sample(valid_sample)
    assert is_valid is False


def test_preclean_pipeline_full_fidelity(tmp_path: Path):
    import json
    data_dir = tmp_path / "data"
    batch_dir = data_dir / "topcv" / "dt=2026-10-12"
    batch_dir.mkdir(parents=True)
    batch_file = batch_dir / "batch_001.json"

    records = [
        {
            "_meta": {"source": "topcv", "source_job_id": "101", "url": "https://topcv.vn/101"},
            "raw": {
                "title": "www.topcv.vn",  # Corrupted!
                "company": "Unknown",
                "description_list": [],
                "requirements_list": [],
            },
        },
        {
            "_meta": {
                "source": "topcv",
                "source_job_id": "102",
                "url": "https://topcv.vn/102",
                "crawled_at": "2026-10-12T10:00:00Z",
                "language": "vi",
            },
            "raw": {
                "title": "Backend Golang Engineer",
                "company": "Tech Corp",
                "salary": {"salary_text": "20 - 30 triệu", "salary_min": 20.0, "salary_max": 30.0, "salary_currency": "VND"},
                "description_list": ["Xây dựng API hiệu năng cao", "Tối ưu hóa Database"],
                "requirements_list": ["Thành thạo Golang", "Có kinh nghiệm Postgres"],
                "benefits_list": ["Lương tháng 13", "Bảo hiểm sức khỏe"],
                "tags": {
                    "skills": ["Golang", "Postgres"],
                    "requirements": ["Đại học"],
                    "benefits": ["Thưởng", "Bảo hiểm"],
                },
                "posted_date_text": "01/10/2026",
                "deadline_text": "30/10/2026",
                "seniority_text": "Senior",
                "extra": {"education": "Đại học", "company_size": "50-100"},
            },
        },
    ]
    with open(batch_file, "w", encoding="utf-8") as f:
        json.dump(records, f)

    out_clean_dir = tmp_path / "processed" / "preClean"
    queue_dir = tmp_path / "queue"
    catalog_db = tmp_path / "catalog.db"

    pipeline = PreCleanPipeline(
        data_dir=data_dir,
        output_clean_dir=out_clean_dir,
        queue_dir=queue_dir,
        catalog_db_path=catalog_db,
    )
    res = pipeline.run()

    assert res["total_processed"] == 2
    assert res["cleaned_count"] == 1
    assert res["corrupted_count"] == 1

    clean_file = out_clean_dir / "merged_jobs_clean.json"
    assert clean_file.exists()
    with open(clean_file) as f:
        clean_data = json.load(f)
    assert len(clean_data) == 1
    rec = clean_data[0]

    # Kiểm tra cấu trúc bản ghi hợp nhất
    assert rec["_meta"]["unified_id"] == "topcv_102"
    assert rec["title"] == "Backend Golang Engineer"
    assert rec["company"] == "Tech Corp"
    assert rec["salary"]["salary_min"] == 20_000_000
    assert rec["salary"]["salary_max"] == 30_000_000

    # Khẳng định giữ nguyên cấu trúc List (không sinh thêm trường _clean)
    assert isinstance(rec["description_list"], list)
    assert len(rec["description_list"]) == 2
    assert isinstance(rec["requirements_list"], list)
    assert len(rec["requirements_list"]) == 2
    assert isinstance(rec["benefits_list"], list)
    assert len(rec["benefits_list"]) == 2

    assert "description_clean" not in rec
    assert "requirements_clean" not in rec
    assert "title_clean" not in rec

    # Khẳng định bảo toàn tags, extra, dates
    assert rec["tags"]["skills"] == ["Golang", "Postgres"]
    assert rec["tags"]["benefits"] == ["Thưởng", "Bảo hiểm"]
    assert rec["posted_date_text"] == "01/10/2026"
    assert rec["extra"]["education"] == "Đại học"
