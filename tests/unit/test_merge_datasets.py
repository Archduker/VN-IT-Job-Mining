# -*- coding: utf-8 -*-
"""Unit test cho scripts/merge_datasets.py."""

import json
from pathlib import Path
from scripts.merge_datasets import merge_datasets, parse_job_file


def test_merge_datasets(tmp_path: Path):
    # Tạo thư mục nguồn 1: topcv
    topcv_dir = tmp_path / "topcv" / "dt=2026-10-08"
    topcv_dir.mkdir(parents=True, exist_ok=True)
    batch_topcv = [
        {
            "_meta": {
                "source": "topcv",
                "source_job_id": "1001",
                "url": "https://topcv.vn/job/1001",
                "dedup_key": "topcv:1001",
                "crawled_at": "2026-10-08T10:00:00Z",
                "batch_id": "2026-10-08_topcv_001",
                "language": "vi",
            },
            "raw": {
                "title": "Python Developer",
                "company": "FPT",
                "description_html": "<p>Mô tả 1</p>",
                "description_text": "Mô tả 1",
                "salary_min": 15.0,
                "salary_max": 30.0,
                "salary_currency": "VND",
            },
        },
        {
            "_meta": {
                "source": "topcv",
                "source_job_id": "1002",
                "url": "https://topcv.vn/job/1002",
                "dedup_key": "topcv:1002",
                "crawled_at": "2026-10-08T10:05:00Z",
                "batch_id": "2026-10-08_topcv_001",
                "language": "en",
            },
            "raw": {
                "title": "Senior Go Engineer",
                "company": "VNG",
                "description_html": "<p>Golang backend</p>",
                "description_text": "Golang backend",
            },
        },
    ]
    with open(topcv_dir / "batch_001.json", "w", encoding="utf-8") as f:
        json.dump(batch_topcv, f, ensure_ascii=False)

    # Tạo thư mục nguồn 2: topdev với 1 job trùng dedup_key và 1 job mới
    topdev_dir = tmp_path / "topdev" / "dt=2026-10-08"
    topdev_dir.mkdir(parents=True, exist_ok=True)
    batch_topdev = [
        {
            "_meta": {
                "source": "topcv",
                "source_job_id": "1001",
                "url": "https://topcv.vn/job/1001",
                "dedup_key": "topcv:1001",
                "crawled_at": "2026-10-08T11:00:00Z",  # Mới hơn topcv crawl
                "batch_id": "2026-10-08_topcv_002",
                "language": "vi",
            },
            "raw": {
                "title": "Python Developer (Updated)",
                "company": "FPT",
                "description_html": "<p>Mô tả 1 updated</p>",
                "description_text": "Mô tả 1 updated",
                "salary_min": 18.0,
                "salary_max": 35.0,
                "salary_currency": "VND",
            },
        },
        {
            "_meta": {
                "source": "topdev",
                "source_job_id": "2001",
                "url": "https://topdev.vn/job/2001",
                "dedup_key": "topdev:2001",
                "crawled_at": "2026-10-08T10:00:00Z",
                "batch_id": "2026-10-08_topdev_001",
                "language": "vi",
            },
            "raw": {
                "title": "DevOps Engineer",
                "company": "Tiki",
                "description_html": "<p>CI/CD, Kubernetes</p>",
                "description_text": "CI/CD, Kubernetes",
            },
        },
    ]
    with open(topdev_dir / "batch_001.json", "w", encoding="utf-8") as f:
        json.dump(batch_topdev, f, ensure_ascii=False)

    out_file = tmp_path / "processed" / "combined_jobs.json"
    result = merge_datasets(input_dir=tmp_path, output_file=out_file)

    assert result["total_read"] == 4
    assert result["total_unique"] == 3
    assert result["duplicates_removed"] == 1
    assert result["sources"]["topcv"] == 2
    assert result["sources"]["topdev"] == 1
    assert out_file.exists()

    with open(out_file, "r", encoding="utf-8") as f:
        combined_data = json.load(f)

    assert isinstance(combined_data, list)
    assert len(combined_data) == 3

    # Kiểm tra job trùng đã được cập nhật bản ghi mới hơn
    job_1001 = next(item for item in combined_data if item["_meta"]["dedup_key"] == "topcv:1001")
    sal_min = job_1001["raw"].get("salary_min") or job_1001["raw"].get("salary", {}).get("salary_min")
    assert sal_min == 18.0
