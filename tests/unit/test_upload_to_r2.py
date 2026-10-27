"""Unit tests cho script upload_to_r2.py."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.upload_to_r2 import (
    _extract_source_from_path,
    resolve_r2_key,
    run_upload,
    upload_single_file,
    validate_json_file,
)


def test_validate_json_file_valid(tmp_path: Path):
    """Test xác thực file JSON hợp lệ."""
    valid_file = tmp_path / "test_valid.json"
    data = [{"title": "Software Engineer", "company": "Tech Corp"}]
    valid_file.write_text(json.dumps(data), encoding="utf-8")

    is_valid, err_msg, count = validate_json_file(valid_file)
    assert is_valid is True
    assert err_msg is None
    assert count == 1


def test_validate_json_file_invalid(tmp_path: Path):
    """Test phát hiện file JSON lỗi cú pháp."""
    invalid_file = tmp_path / "test_invalid.json"
    invalid_file.write_text("{\"title\": \"Broken JSON", encoding="utf-8")

    is_valid, err_msg, count = validate_json_file(invalid_file)
    assert is_valid is False
    assert "Lỗi cú pháp JSON" in str(err_msg)
    assert count == 0


def test_validate_json_file_empty(tmp_path: Path):
    """Test phát hiện file rỗng 0 bytes."""
    empty_file = tmp_path / "empty.json"
    empty_file.write_text("", encoding="utf-8")

    is_valid, err_msg, count = validate_json_file(empty_file)
    assert is_valid is False
    assert "File rỗng" in str(err_msg)


def test_validate_json_file_not_found(tmp_path: Path):
    """Test file không tồn tại."""
    missing_file = tmp_path / "non_existent.json"
    is_valid, err_msg, count = validate_json_file(missing_file)
    assert is_valid is False
    assert "File không tồn tại" in str(err_msg)


def test_resolve_r2_key():
    """Test xác định R2 key chuẩn Lakehouse."""
    # Custom dest
    p = Path("some/arbitrary/path/file.json")
    assert resolve_r2_key(p, custom_dest="custom/key/target.json") == "custom/key/target.json"

    # Samples key
    sample_path = Path("crawlers/sources/topcv/samples/sample_standard_job.json")
    assert resolve_r2_key(sample_path, source="topcv") == "samples/topcv/sample_standard_job.json"

    # Test file key
    test_path = Path("crawlers/sources/vietnamworks/test_5_jobs.json")
    assert resolve_r2_key(test_path, source="vietnamworks") == "test/vietnamworks/test_5_jobs.json"

    # URL ledger
    ledger_path = Path("data/topcv/url_ledger/catalog_master.json")
    assert resolve_r2_key(ledger_path, source="topcv") == "url_ledger/topcv/catalog_master.json"

    # Silver dataset key
    silver_path = Path("data/silver/silver_master_dataset.json")
    assert resolve_r2_key(silver_path) == "silver/silver_master_dataset.json"


def test_extract_source_from_path():
    """Test trích xuất tên sàn từ đường dẫn."""
    assert _extract_source_from_path("crawlers/sources/vieclam24h/test_5_jobs.json") == "vieclam24h"
    assert _extract_source_from_path("data/raw/topcv/2026-10-15/job.json") == "topcv"
    assert _extract_source_from_path("unknown/path/random.json") == "unknown"


def test_upload_single_file_dry_run(tmp_path: Path):
    """Test chế độ dry-run không gọi S3 client."""
    test_file = tmp_path / "test.json"
    test_file.write_text(json.dumps([{"id": 1}]), encoding="utf-8")

    mock_s3 = MagicMock()
    success, size, msg = upload_single_file(
        s3_client=mock_s3,
        bucket="vn-it-jobs",
        local_path=test_file,
        r2_key="raw/topcv/test.json",
        dry_run=True,
    )

    assert success is True
    assert size > 0
    assert "[DRY-RUN]" in msg
    mock_s3.upload_file.assert_not_called()


def test_upload_single_file_mocked_s3(tmp_path: Path):
    """Test upload qua S3 client được mock."""
    test_file = tmp_path / "test.json"
    test_file.write_text(json.dumps([{"id": 1}]), encoding="utf-8")

    mock_s3 = MagicMock()
    success, size, msg = upload_single_file(
        s3_client=mock_s3,
        bucket="vn-it-jobs",
        local_path=test_file,
        r2_key="raw/topcv/test.json",
        dry_run=False,
    )

    assert success is True
    assert size > 0
    assert "Đã tải lên" in msg
    mock_s3.upload_file.assert_called_once_with(
        Filename=str(test_file),
        Bucket="vn-it-jobs",
        Key="raw/topcv/test.json",
        ExtraArgs={"ContentType": "application/json; charset=utf-8"},
    )


def test_run_upload_dry_run(tmp_path: Path):
    """Test run_upload ở chế độ dry-run với file cụ thể."""
    test_file = tmp_path / "sample.json"
    test_file.write_text(json.dumps({"key": "val"}), encoding="utf-8")

    code = run_upload(file_path=str(test_file), dry_run=True)
    assert code == 0
