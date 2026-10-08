"""
Unit tests for crawlers.common.json_writer
"""

import json
from datetime import date
from pathlib import Path
from crawlers.common.json_writer import JsonWriter
from crawlers.common.jsonl_writer import JsonlWriter
from crawlers.common.schema import JobRecord


def test_json_writer_creates_partition_directory(tmp_path: Path):
    d = date(2026, 10, 8)
    writer = JsonWriter(source="topdev", output_dir=tmp_path, run_date=d, batch_seq=1)
    expected_dir = tmp_path / "topdev" / "dt=2026-10-08"
    assert expected_dir.exists()
    assert writer.file_path == expected_dir / "batch_001.json"


def test_json_writer_writes_valid_job_record(tmp_path: Path):
    writer = JsonWriter(source="topdev", output_dir=tmp_path, batch_seq=1)
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


def test_json_writer_invalid_record_rejected(tmp_path: Path):
    writer = JsonWriter(source="topdev", output_dir=tmp_path, batch_seq=1, validate_schema=True)
    with writer:
        # Missing required raw fields
        success = writer.write({"_meta": {}, "raw": {}})
        assert success is False
    assert writer.records_written == 0


def test_json_writer_atomic_write_multiple_records(tmp_path: Path):
    writer = JsonWriter(source="topdev", output_dir=tmp_path, batch_seq=2)
    for i in range(3):
        rec = JobRecord.create(
            source="topdev",
            source_job_id=f"job_{i}",
            url=f"https://topdev.vn/job-{i}",
            batch_id="2026-10-08_topdev_002",
            raw_data={
                "title": f"Dev {i}",
                "company": "Tech Corp",
                "description_html": f"<div>Desc {i}</div>",
                "description_text": f"Desc {i}",
            },
        )
        assert writer.write(rec) is True

    writer.close()

    assert not (writer.file_path.with_name(f"{writer.file_path.name}.tmp")).exists()
    with open(writer.file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert isinstance(data, list)
        assert len(data) == 3
        assert [x["_meta"]["source_job_id"] for x in data] == ["job_0", "job_1", "job_2"]


def test_jsonl_writer_compatibility_alias(tmp_path: Path):
    assert JsonlWriter is JsonWriter
