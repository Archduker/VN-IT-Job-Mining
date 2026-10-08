"""
Unit tests for crawlers.common.data_quality
"""

import json
from pathlib import Path
from crawlers.common.data_quality import DataQualityChecker


def test_data_quality_checker_json_array(tmp_path: Path):
    file_path = tmp_path / "batch_001.json"
    records = [
        {
            "_meta": {
                "source": "topdev",
                "source_job_id": f"job_{i}",
                "url": f"https://topdev.vn/job-{i}",
                "dedup_key": f"topdev:job_{i}",
                "crawled_at": "2026-10-08T12:00:00+07:00",
                "batch_id": "2026-10-08_topdev_001",
                "crawler_version": "0.1.0",
            },
            "raw": {
                "title": f"Software Engineer {i}",
                "company": "Tech Vietnam",
                "description_html": "<p>Job details here</p>",
                "description_text": "Job details here",
            },
        }
        for i in range(5)
    ]

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)

    checker = DataQualityChecker(file_path=file_path)
    res = checker.check()

    assert res["passed"] is True
    assert res["total_records"] == 5
    assert res["valid_schema_records"] == 5
    assert res["unique_keys"] == 5
    assert res["schema_valid_rate"] == 100.0


def test_data_quality_checker_jsonl_fallback(tmp_path: Path):
    file_path = tmp_path / "batch_001.jsonl"
    record = {
        "_meta": {
            "source": "topdev",
            "source_job_id": "job_1",
            "url": "https://topdev.vn/job-1",
            "dedup_key": "topdev:job_1",
            "crawled_at": "2026-10-08T12:00:00+07:00",
            "batch_id": "2026-10-08_topdev_001",
            "crawler_version": "0.1.0",
        },
        "raw": {
            "title": "Software Engineer",
            "company": "Tech Vietnam",
            "description_html": "<p>Job details here</p>",
            "description_text": "Job details here",
        },
    }

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    checker = DataQualityChecker(jsonl_path=file_path)
    res = checker.check()

    assert res["passed"] is True
    assert res["total_records"] == 1


def test_data_quality_checker_missing_file(tmp_path: Path):
    file_path = tmp_path / "nonexistent.json"
    checker = DataQualityChecker(file_path)
    res = checker.check()
    assert res["passed"] is False
    assert res["total_records"] == 0
