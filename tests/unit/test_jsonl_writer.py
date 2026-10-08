"""
Unit tests for crawlers.common.jsonl_writer (tương thích ngược với JsonWriter)
"""

import json
from datetime import date
from pathlib import Path
from crawlers.common.jsonl_writer import JsonlWriter
from crawlers.common.schema import JobRecord


def test_jsonl_writer_creates_partition_directory(tmp_path: Path):
    d = date(2026, 10, 8)
    writer = JsonlWriter(source="topdev", output_dir=tmp_path, run_date=d, batch_seq=1)
    expected_dir = tmp_path / "topdev" / "dt=2026-10-08"
    assert expected_dir.exists()
    assert writer.file_path == expected_dir / "batch_001.json"


def test_jsonl_writer_writes_valid_job_record(tmp_path: Path):
    writer = JsonlWriter(source="topdev", output_dir=tmp_path, batch_seq=1)
    record = JobRecord.create(
        source="topdev",
        source_job_id="test_001",
        url="https://topdev.vn/viec-lam/python-dev-123456",
        batch_id="2026-10-08_topdev_001",
        raw_data={
            "title": "Python Developer",
            "company": "Tech Corp",
            "description_html": "<div>Backend developer with Python</div>",
            "description_text": "Backend developer with Python",
        },
    )

    with writer:
        success = writer.write(record)
        assert success is True

    assert writer.records_written == 1
    assert writer.file_path.exists()

    with open(writer.file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["_meta"]["source"] == "topdev"
        assert data[0]["_meta"]["source_job_id"] == "test_001"
        assert data[0]["raw"]["title"] == "Python Developer"


def test_jsonl_writer_invalid_record_rejected(tmp_path: Path):
    writer = JsonlWriter(source="topdev", output_dir=tmp_path, batch_seq=1, validate_schema=True)
    with writer:
        # Missing required raw fields
        success = writer.write({"_meta": {}, "raw": {}})
        assert success is False
    assert writer.records_written == 0
