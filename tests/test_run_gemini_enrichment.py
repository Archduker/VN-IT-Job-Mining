# -*- coding: utf-8 -*-
"""Unit tests for run_gemini_enrichment (Bước 5)."""

import json
from pathlib import Path
import pytest

from preprocessing.missing_outlier.run_gemini_enrichment import (
    main,
    run_enrichment_pipeline,
)


@pytest.fixture
def sample_jobs_file(tmp_path: Path) -> Path:
    """Tạo tệp JSON mẫu gồm 5 bản ghi."""
    records = [
        {
            "job_id_global": f"job_test_{i}",
            "source_platform": "topcv" if i % 2 == 0 else "itviec",
            "source_url": f"https://example.com/job/{i}",
            "job_title": f"Senior Python Developer {i}",
            "raw_description_text": "Tuyển dụng lập trình viên Python, Docker, AWS.",
            "raw_requirements_text": "Yêu cầu 3 năm kinh nghiệm. Kỹ năng làm việc nhóm tốt.",
            "salary_min": 25000000.0 if i == 0 else None,
            "salary_max": 40000000.0 if i == 0 else None,
            "salary_currency": "VND",
        }
        for i in range(5)
    ]
    p = tmp_path / "sample_input.json"
    p.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def test_run_gemini_enrichment_mock_pipeline(tmp_path: Path, sample_jobs_file: Path):
    """Kiểm tra luồng xử lý pipeline hoàn chỉnh ở chế độ mock."""
    ckpt_file = tmp_path / "checkpoint.jsonl"
    golden_file = tmp_path / "golden.json"
    flat_file = tmp_path / "flat.json"

    res = run_enrichment_pipeline(
        input_file=str(sample_jobs_file),
        checkpoint_file=str(ckpt_file),
        golden_output=str(golden_file),
        flat_output=str(flat_file),
        mock_mode=True,
        workers=2,
    )

    assert res["total_records"] == 5
    assert res["processed_count"] == 5
    assert res["errors_count"] == 0
    assert res["checkpoint_records"] == 5

    # Kiểm tra tệp Golden Master
    assert golden_file.exists()
    golden_data = json.loads(golden_file.read_text(encoding="utf-8"))
    assert len(golden_data) == 5
    for idx, rec in enumerate(golden_data):
        assert len(rec.keys()) == 11
        if idx == 0:
            assert rec["salary"]["salary_min"] == 25000000.0
            assert rec["salary"]["salary_source"] == "original"
            assert rec["salary"]["is_salary_negotiable"] is False
        else:
            assert rec["salary"]["salary_min"] is None
            assert rec["salary"]["salary_max"] is None
            assert rec["salary"]["salary_source"] == "negotiable"
            assert rec["salary"]["is_salary_negotiable"] is True

    # Kiểm tra tệp Flat
    assert flat_file.exists()
    flat_data = json.loads(flat_file.read_text(encoding="utf-8"))
    assert len(flat_data) == 5
    assert "job_title" in flat_data[0]
    assert "salary_min" in flat_data[0]


def test_run_gemini_enrichment_resumability(tmp_path: Path, sample_jobs_file: Path):
    """Kiểm tra cơ chế Resume không xử lý lại các bản ghi đã có trong checkpoint."""
    ckpt_file = tmp_path / "checkpoint_resumable.jsonl"

    # Lần 1: Chạy với limit=2
    res1 = run_enrichment_pipeline(
        input_file=str(sample_jobs_file),
        checkpoint_file=str(ckpt_file),
        limit=2,
        mock_mode=True,
    )
    assert res1["processed_count"] == 2
    assert res1["checkpoint_records"] == 2

    # Lần 2: Chạy toàn bộ (5 records) -> chỉ xử lý 3 bản ghi còn lại
    res2 = run_enrichment_pipeline(
        input_file=str(sample_jobs_file),
        checkpoint_file=str(ckpt_file),
        mock_mode=True,
    )
    assert res2["processed_count"] == 3
    assert res2["checkpoint_records"] == 5


def test_main_cli_execution(tmp_path: Path, sample_jobs_file: Path):
    """Kiểm tra thực thi hàm main thông qua CLI args."""
    ckpt_file = tmp_path / "cli_checkpoint.jsonl"
    golden_file = tmp_path / "cli_golden.json"
    flat_file = tmp_path / "cli_flat.json"

    exit_code = main([
        "--input", str(sample_jobs_file),
        "--checkpoint", str(ckpt_file),
        "--golden-output", str(golden_file),
        "--flat-output", str(flat_file),
        "--mock",
        "--limit", "3",
    ])

    assert exit_code == 0
    assert golden_file.exists()
    golden_data = json.loads(golden_file.read_text(encoding="utf-8"))
    assert len(golden_data) == 3
    assert flat_file.exists()
    flat_data = json.loads(flat_file.read_text(encoding="utf-8"))
    assert len(flat_data) == 3
