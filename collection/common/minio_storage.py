"""Helpers for uploading crawler outputs to MinIO's S3-compatible API."""

from __future__ import annotations

import os
from pathlib import Path


def upload_file_to_minio(
    file_path: str | Path,
    object_key: str,
    bucket_name: str | None = None,
    endpoint_url: str | None = None,
    access_key: str | None = None,
    secret_key: str | None = None,
) -> str:
    """Upload a local file and return its MinIO URI.

    Raises an exception if the file is missing or MinIO cannot accept the upload.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"MinIO upload source file does not exist: {path}")

    bucket = bucket_name or os.getenv("MINIO_BUCKET", "vn-it-jobs")
    endpoint = endpoint_url or os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
    ak = access_key or os.getenv("MINIO_ROOT_USER", "minioadmin")
    sk = secret_key or os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")

    import boto3
    from botocore.client import Config

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=ak,
        aws_secret_access_key=sk,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )
    s3.upload_file(str(path), bucket, object_key)
    return f"minio://{bucket}/{object_key}"
