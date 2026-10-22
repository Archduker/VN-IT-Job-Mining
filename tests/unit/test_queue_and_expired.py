# -*- coding: utf-8 -*-
"""Unit tests cho các tính năng hàng đợi ưu tiên PENDING/RECHECK_DUE và bộ lọc tin hết hạn."""

from datetime import date, timedelta
import tempfile
import pytest

from crawlers.common.url_ledger import UrlLedger
from crawlers.common.utils import is_job_closed_or_expired


class TestExpiredJobFilter:
    def test_http_status_codes(self):
        assert is_job_closed_or_expired(status_code=404) is True
        assert is_job_closed_or_expired(status_code=410) is True
        assert is_job_closed_or_expired(status_code=200) is False
        assert is_job_closed_or_expired(status_code=301) is False

    def test_deadline_date_comparison(self):
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        assert is_job_closed_or_expired(deadline_raw=yesterday) is True
        assert is_job_closed_or_expired(deadline_raw=tomorrow) is False
        assert is_job_closed_or_expired(deadline_raw="31/12/2020") is True
        assert is_job_closed_or_expired(deadline_raw="31/12/2030") is False

    def test_payload_dict_flags(self):
        assert is_job_closed_or_expired({"is_closed": True}) is True
        assert is_job_closed_or_expired({"is_active": False}) is True
        assert is_job_closed_or_expired({"status": "closed"}) is True
        assert is_job_closed_or_expired({"status": "expired"}) is True
        assert is_job_closed_or_expired({"valid_through": "2020-01-01"}) is True
        assert is_job_closed_or_expired({"status": "active", "valid_through": "2030-01-01"}) is False

    def test_dom_closed_keywords(self):
        assert is_job_closed_or_expired("<div>Tin tuyển dụng đã hết hạn</div>") is True
        assert is_job_closed_or_expired("<p>Hết hạn nộp hồ sơ từ ngày 15/10</p>") is True
        assert is_job_closed_or_expired("<span>Vị trí này đã đóng</span>") is True
        assert is_job_closed_or_expired("<div>This job is no longer available</div>") is True
        assert is_job_closed_or_expired("<div>Job has expired</div>") is True
        assert is_job_closed_or_expired("<h1>Tuyển dụng Senior Golang Developer</h1>") is False


class TestUrlLedgerPriorityQueue:
    def test_priority_ordering_and_closed_exclusion(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = UrlLedger("test_queue", storage_dir=tmpdir)

            # 1. Job mới phát hiện PENDING
            r1 = ledger.register_url("https://example.com/job1", "1", "Python Dev", "Company A")
            # 2. Job phát hiện sau PENDING
            r2 = ledger.register_url("https://example.com/job2", "2", "React Dev", "Company B")

            # 3. Job đã cào nhưng đã quá 21 ngày (RECHECK_DUE)
            r3 = ledger.register_url("https://example.com/job3", "3", "Java Dev", "Company C")
            ledger.mark_done(r3.url_hash, "hash3", new_version=1)
            ledger.records[r3.url_hash]["last_scraped_at"] = "2026-08-01T00:00:00Z"

            # 4. Job đã đóng (CLOSED)
            r4 = ledger.register_url("https://example.com/job4", "4", "DevOps", "Company D")
            ledger.mark_closed(r4.url_hash)

            # Kiểm tra tóm tắt hàng đợi
            summary = ledger.get_queue_summary()
            assert summary["total"] == 4
            assert summary["pending"] == 2
            assert summary["recheck_due"] == 1
            assert summary["closed"] == 1

            # Lấy queue: PENDING phải đứng trước RECHECK_DUE, CLOSED bị loại bỏ
            queue = ledger.get_pending_or_due_records(sort_newest=True)
            assert len(queue) == 3
            job_ids = [item["job_id"] for item in queue]
            assert "4" not in job_ids  # CLOSED bị loại bỏ hoàn toàn
            assert job_ids[0] in ("1", "2")  # PENDING đứng đầu
            assert job_ids[1] in ("1", "2")
            assert job_ids[2] == "3"  # RECHECK_DUE đứng cuối

            # Kiểm tra limit
            limited_queue = ledger.get_pending_or_due_records(limit=1, sort_newest=True)
            assert len(limited_queue) == 1
            assert limited_queue[0]["status"] == "PENDING"
