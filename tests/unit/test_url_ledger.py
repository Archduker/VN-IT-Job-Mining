"""Unit tests cho crawlers.common.url_ledger."""

import tempfile
from datetime import datetime, timezone, timedelta
from crawlers.common.url_ledger import (
    clean_canonical_url,
    generate_url_hash,
    generate_identity_key,
    calculate_container_html_hash,
    is_due_for_recrawl,
    UrlLedger,
)


def test_clean_canonical_url():
    raw_url = "https://www.topcv.vn/viec-lam/python-dev/12345.html?utm_source=facebook&utm_medium=cpc&ref=homepage#apply-now"
    clean = clean_canonical_url(raw_url)
    assert clean == "https://www.topcv.vn/viec-lam/python-dev/12345.html"
    assert "utm_source" not in clean
    assert "#apply-now" not in clean


def test_calculate_container_html_hash():
    html_1 = """
    <div class="job-container">
        <h1>Senior Python Engineer</h1>
        <p>Salary: 30 - 45 million</p>
        <script>var csrf = "dynamic_token_123";</script>
        <style>.ads { color: red; }</style>
        <span>Views: 1,420</span>
    </div>
    """
    html_2 = """
    <div class="job-container">
        <h1>Senior Python Engineer</h1>
        <p>Salary: 30 - 45 million</p>
        <script>var csrf = "DIFFERENT_TOKEN_999";</script>
        <style>.ads { color: blue; }</style>
        <span>Views: 9,999</span>
    </div>
    """
    # Hai HTML chỉ khác script/style/token, nội dung tuyển dụng giống nhau
    # Lưu ý: calculate_container_html_hash xóa script, style, svg, iframe
    hash_1 = calculate_container_html_hash(html_1, ".job-container")
    
    # Nếu nội dung tuyển dụng sửa đổi (ví dụ đổi mức lương lên 50 triệu)
    html_modified = """
    <div class="job-container">
        <h1>Senior Python Engineer</h1>
        <p>Salary: 35 - 50 million</p>
    </div>
    """
    hash_mod = calculate_container_html_hash(html_modified, ".job-container")
    assert hash_1 != hash_mod


def test_is_due_for_recrawl():
    # Chưa cào -> cần cào
    assert is_due_for_recrawl(None, days=21) is True

    # Cào cách đây 10 ngày -> chưa đến hạn 21 ngày (Skip)
    recent_date = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    assert is_due_for_recrawl(recent_date, days=21) is False

    # Cào cách đây 22 ngày -> đã đến hạn (Re-crawl)
    old_date = (datetime.now(timezone.utc) - timedelta(days=22)).isoformat()
    assert is_due_for_recrawl(old_date, days=21) is True


def test_url_ledger_workflow():
    with tempfile.TemporaryDirectory() as tmp_dir:
        ledger = UrlLedger(source="topcv", storage_dir=tmp_dir)

        # 1. Ghi nhận URL mới ở Phase 1
        record = ledger.register_url(
            raw_url="https://topcv.vn/job/python-dev?utm_campaign=hot",
            job_id="101",
            preliminary_title="Python Developer",
            preliminary_company="Tech Corp",
        )
        assert record.status == "PENDING"
        assert record.canonical_url == "https://topcv.vn/job/python-dev"

        # 2. Lấy link cần cào ở Phase 2
        pending_list = ledger.get_pending_or_due_records(recheck_days=21)
        assert len(pending_list) == 1
        assert pending_list[0]["job_id"] == "101"

        # 3. Cào thành công -> mark_done
        content_hash = "abc123hash"
        ledger.mark_done(record.url_hash, content_hash=content_hash, new_version=1)
        assert ledger.records[record.url_hash]["status"] == "DONE"
        assert ledger.records[record.url_hash]["latest_version"] == 1

        # 4. Khi quét lại lần 2, vì chưa đủ 21 ngày nên pending_list phải rỗng (Safe Skip)
        pending_again = ledger.get_pending_or_due_records(recheck_days=21)
        assert len(pending_again) == 0

        # 5. Kiểm tra phát hiện Repost
        repost_job = ledger.find_by_content_hash(content_hash)
        assert repost_job is not None
        assert repost_job["job_id"] == "101"

        # 6. Test Safe Skip khi cào lỗi
        ledger.mark_failed(record.url_hash, error_message="HTTP 500 Internal Server Error")
        assert ledger.records[record.url_hash]["status"] == "FAILED"
        assert ledger.records[record.url_hash]["retry_count"] == 1


def test_url_ledger_default_storage_dir():
    ledger = UrlLedger(source="topcv")
    normalized_path = str(ledger.base_dir).replace("\\", "/")
    assert normalized_path.endswith("data/topcv/url_ledger")


def test_url_ledger_sync_to_minio(monkeypatch):
    from unittest.mock import MagicMock
    with tempfile.TemporaryDirectory() as tmp_dir:
        ledger = UrlLedger(source="topcv", storage_dir=tmp_dir)
        ledger.register_url("https://topcv.vn/job/123", job_id="123")
        ledger.save_catalog()
        ledger.export_daily_manifest()

        # Mock boto3 client
        mock_s3 = MagicMock()
        monkeypatch.setattr("boto3.client", lambda *args, **kwargs: mock_s3)

        success = ledger.sync_to_minio(bucket_name="vn-it-jobs", endpoint_url="http://mock-minio:9000")
        assert success is True
        assert mock_s3.upload_file.call_count >= 2

