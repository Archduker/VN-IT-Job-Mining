# -*- coding: utf-8 -*-
"""Unit tests for crawlers.common.job_catalog."""

from pathlib import Path
import pytest
from crawlers.common.job_catalog import (
    JobStateCatalog,
    STATUS_DISCOVERED,
    STATUS_SUCCESS,
    STATUS_FAILED_RETRY,
)


@pytest.fixture
def temp_catalog(tmp_path: Path) -> JobStateCatalog:
    db_file = tmp_path / "test_catalog.db"
    return JobStateCatalog(db_path=db_file)


def test_catalog_initialization(temp_catalog: JobStateCatalog):
    assert temp_catalog.db_path.exists()
    stats = temp_catalog.get_catalog_stats()
    assert stats["total"] == 0


def test_register_new_jobs(temp_catalog: JobStateCatalog):
    harvested = [
        {"job_id": "1001", "job_url": "https://example.com/job/1001.html"},
        {"job_id": "1002", "job_url": "https://example.com/job/1002.html"},
    ]
    queue, skipped = temp_catalog.register_harvested_jobs("topcv", harvested)

    assert len(queue) == 2
    assert skipped == 0
    assert queue[0]["job_id"] == "1001"
    assert queue[0]["dispatch_reason"] == "NEW_DISCOVERED"

    stats = temp_catalog.get_catalog_stats("topcv")
    assert stats["total"] == 2
    assert stats["discovered"] == 2


def test_mark_success_and_deduplicate(temp_catalog: JobStateCatalog):
    harvested = [
        {"job_id": "1001", "job_url": "https://example.com/job/1001.html"},
    ]
    queue, _ = temp_catalog.register_harvested_jobs("topcv", harvested)
    assert len(queue) == 1

    # Mark success
    temp_catalog.mark_job_success("topcv", "1001", "data/topcv/dt=2026-10-12/batch_001.json")

    stats = temp_catalog.get_catalog_stats("topcv")
    assert stats["success"] == 1
    assert stats["discovered"] == 0

    # Next run harvest again -> should be skipped!
    queue2, skipped2 = temp_catalog.register_harvested_jobs("topcv", harvested)
    assert len(queue2) == 0
    assert skipped2 == 1


def test_mark_failed_and_deferred_retry(temp_catalog: JobStateCatalog):
    harvested = [
        {"job_id": "2001", "job_url": "https://example.com/job/2001.html"},
    ]
    temp_catalog.register_harvested_jobs("careerviet", harvested)

    # In current run, job 2001 fails
    temp_catalog.mark_job_failed_for_next_run("careerviet", "2001", "Navigation timeout 15000ms")

    stats = temp_catalog.get_catalog_stats("careerviet")
    assert stats["failed_retry"] == 1

    failed_list = temp_catalog.get_failed_retry_jobs("careerviet")
    assert len(failed_list) == 1
    assert failed_list[0]["job_id"] == "2001"
    assert failed_list[0]["retry_count"] == 1
    assert "timeout" in failed_list[0]["last_error"].lower()

    # In next scheduled run (4 days later), full harvest detects 2001 again
    queue_next, skipped_next = temp_catalog.register_harvested_jobs("careerviet", harvested)
    assert len(queue_next) == 1
    assert skipped_next == 0
    assert queue_next[0]["dispatch_reason"] == "RETRY_PREVIOUS_FAILURE"
    assert queue_next[0]["retry_count"] == 1


def test_sync_from_batches(temp_catalog: JobStateCatalog, tmp_path: Path):
    import json
    data_dir = tmp_path / "mock_data"
    batch_dir = data_dir / "vietnamworks" / "dt=2026-10-12"
    batch_dir.mkdir(parents=True)
    batch_file = batch_dir / "batch_001.json"

    mock_records = [
        {
            "_meta": {
                "source": "vietnamworks",
                "source_job_id": "99901",
                "url": "https://vietnamworks.com/job/99901",
                "scraped_at": "2026-10-12T10:00:00Z",
            },
            "raw": {"title": "Python Dev"},
        },
        {
            "_meta": {
                "source": "vietnamworks",
                "source_job_id": "99902",
                "url": "https://vietnamworks.com/job/99902",
                "scraped_at": "2026-10-12T10:00:00Z",
            },
            "raw": {"title": "Java Dev"},
        },
    ]
    with open(batch_file, "w", encoding="utf-8") as f:
        json.dump(mock_records, f)

    res = temp_catalog.sync_from_batches(data_dir=data_dir)
    assert res["total_synced"] == 2
    assert res["files_scanned"] == 1
    assert res["by_source"]["vietnamworks"] == 2

    stats = temp_catalog.get_catalog_stats("vietnamworks")
    assert stats["total"] == 2
    assert stats["success"] == 2
    assert stats["failed_retry"] == 0

    # Lọc trùng sau khi sync
    harvested = [
        {"job_id": "99901", "job_url": "https://vietnamworks.com/job/99901"},
        {"job_id": "99903", "job_url": "https://vietnamworks.com/job/99903"},
    ]
    queue, skipped = temp_catalog.register_harvested_jobs("vietnamworks", harvested)
    assert len(queue) == 1
    assert queue[0]["job_id"] == "99903"
    assert skipped == 1

