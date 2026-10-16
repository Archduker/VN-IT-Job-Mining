from pathlib import Path
from unittest.mock import Mock

import boto3
import pytest

from crawlers.common.minio_storage import upload_file_to_minio


def test_upload_file_to_minio_uploads_and_returns_uri(tmp_path: Path, monkeypatch):
    source_file = tmp_path / "batch_001.json"
    source_file.write_text("[]", encoding="utf-8")
    s3_client = Mock()
    monkeypatch.setattr(boto3, "client", Mock(return_value=s3_client))

    uri = upload_file_to_minio(
        source_file,
        object_key="raw/vietnamworks/dt=2026-10-16/batch_001.json",
        endpoint_url="http://minio:9000",
        bucket_name="vn-it-jobs",
    )

    s3_client.upload_file.assert_called_once_with(
        str(source_file),
        "vn-it-jobs",
        "raw/vietnamworks/dt=2026-10-16/batch_001.json",
    )
    assert uri == "minio://vn-it-jobs/raw/vietnamworks/dt=2026-10-16/batch_001.json"


def test_upload_file_to_minio_raises_for_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="does not exist"):
        upload_file_to_minio(tmp_path / "missing.json", object_key="raw/missing.json")
