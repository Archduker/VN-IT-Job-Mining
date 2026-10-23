# -*- coding: utf-8 -*-
"""Unit tests for DataPreprocessOperator."""

import json
from pathlib import Path
from unittest.mock import MagicMock

from airflow.plugins.crawler_operators import DataPreprocessOperator


def test_data_preprocess_operator_execution(tmp_path: Path):
    date_str = "2026-10-22"
    raw_dir = tmp_path / "topdev" / "raw" / date_str
    raw_dir.mkdir(parents=True, exist_ok=True)

    raw_file = raw_dir / "2139755_v1.json"
    raw_payload = {
        "metadata": {
            "source": "topdev",
            "job_id": "2139755",
            "content_hash": "abc123hash",
            "version": 1,
        },
        "raw_payload": {
            "title": "  Senior Python Backend Engineer  ",
            "company": "Tech Vietnam Corp.",
            "salary_raw": "25 - 45 triệu VND",
            "description_list": [
                "• Thiết kế và phát triển RESTful APIs & Microservices.",
                "• Tối ưu hóa hiệu năng PostgreSQL & Redis caching.",
            ],
            "requirements_list": [
                "* Tối thiểu 3 năm kinh nghiệm với Python & FastAPI/Django.",
                "* Thành thạo Docker, Kubernetes, CI/CD pipeline.",
            ],
            "benefits_list": [
                "- Thưởng tháng 13 + performance bonus hàng quý.",
                "- Bảo hiểm sức khỏe cao cấp cho nhân viên và gia đình.",
            ],
            "tags": ["Python", "FastAPI", "PostgreSQL", "Docker"],
            "location_text": "Quận 1, TP. Hồ Chí Minh",
            "deadline_text": "2026-11-30",
        },
    }

    with open(raw_file, "w", encoding="utf-8") as f:
        json.dump(raw_payload, f, ensure_ascii=False, indent=2)

    mock_context = {"ti": MagicMock()}

    operator = DataPreprocessOperator(
        task_id="preprocess_topdev",
        source="topdev",
        date_str=date_str,
        base_dir=str(tmp_path),
    )

    result = operator.execute(mock_context)

    assert result["source"] == "topdev"
    assert result["total_raw"] == 1
    assert result["total_cleaned"] == 1

    clean_file = tmp_path / "topdev" / "staging" / date_str / "2139755_clean.json"
    assert clean_file.exists()

    with open(clean_file, "r", encoding="utf-8") as f:
        clean_data = json.load(f)

    meta = clean_data["staging_metadata"]
    job = clean_data["cleaned_job"]

    assert meta["source"] == "topdev"
    assert meta["job_id"] == "2139755"
    assert job["title"] == "Senior Python Backend Engineer"
    assert job["company"] == "Tech Vietnam Corp."
    assert job["salary"]["salary_min"] == 25.0
    assert job["salary"]["salary_max"] == 45.0
    assert job["salary"]["salary_currency"] == "VND"
    assert "Python" in job["skills"]
    assert "FastAPI" in job["skills"]
    # Check bullet points are stripped
    assert not job["description_clean"][0].startswith("•")
    assert not job["requirements_clean"][0].startswith("*")
