"""Helpers for uploading crawler outputs directly to Cloudflare R2 Cloud Lakehouse."""

from __future__ import annotations

import os
from pathlib import Path


def get_r2_client(
    endpoint_url: str | None = None,
    access_key: str | None = None,
    secret_key: str | None = None,
):
    """Initialize and return a boto3 S3 client configured for Cloudflare R2."""
    import boto3
    from botocore.client import Config

    endpoint = (
        endpoint_url
        or os.getenv("R2_ENDPOINT_URL")
        or os.getenv("S3_ENDPOINT_URL")
        or "https://bb8811262069cd3e4d244a9dc7bf6a84.r2.cloudflarestorage.com"
    )
    ak = (
        access_key
        or os.getenv("R2_ACCESS_KEY_ID")
        or os.getenv("AWS_ACCESS_KEY_ID")
    )
    sk = (
        secret_key
        or os.getenv("R2_SECRET_ACCESS_KEY")
        or os.getenv("AWS_SECRET_ACCESS_KEY")
    )

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=ak,
        aws_secret_access_key=sk,
        config=Config(signature_version="s3v4", connect_timeout=10, retries={"max_attempts": 3}),
        region_name="auto",
    )


CANONICAL_PREFIXES = ("url_ledger/", "raw/", "staging/", "curated/")


def canonicalize_lakehouse_key(object_key: str) -> str:
    """Đảm bảo mọi object_key đẩy lên R2/MinIO luôn tuân thủ chuẩn 4 phân tầng Lakehouse.

    - Tự động chuẩn hóa các key bị đảo ngược:
        * <source>/raw/...        -> raw/<source>/...
        * <source>/url_ledger/... -> url_ledger/<source>/...
        * <source>/staging/...    -> staging/<source>/...
    - Từ chối tuyệt đối các tệp cache/tạm/nhạy cảm: .browser_profile, router_state.json, *.tmp, checkpoints.
    """
    key = str(object_key).strip().replace("\\", "/").lstrip("/")
    parts = key.split("/")

    # 1. Phát hiện file rác / ephemeral local cache
    for p in parts:
        if p.startswith(".") or p in ("checkpoints", "__pycache__", "router_state.json"):
            raise ValueError(f"Không được phép upload tệp cache/tạm lên Lakehouse: {object_key}")
    if parts[-1].endswith((".tmp", ".lock", ".swp")) or parts[-1] == "router_state.json":
        raise ValueError(f"Không được phép upload tệp cache/tạm lên Lakehouse: {object_key}")

    # 2. Đã đúng chuẩn 4 tầng
    if any(key.startswith(pfx) for pfx in CANONICAL_PREFIXES):
        return key

    # 3. Bị đảo ngược: <source>/<layer>/... (e.g. topcv/raw/... -> raw/topcv/...)
    if len(parts) >= 2 and parts[1] in ("raw", "url_ledger", "staging"):
        source, layer = parts[0], parts[1]
        rest = "/".join(parts[2:])
        return f"{layer}/{source}/{rest}"

    raise ValueError(
        f"Object key không hợp lệ với chuẩn 4 tầng Lakehouse (phải thuộc raw/, url_ledger/, staging/, curated/): {object_key}"
    )


def upload_file_to_r2(
    file_path: str | Path,
    object_key: str,
    bucket_name: str | None = None,
    endpoint_url: str | None = None,
    access_key: str | None = None,
    secret_key: str | None = None,
) -> str:
    """Upload a local file directly to Cloudflare R2 and return its r2:// URI.

    Tự động chuẩn hóa object_key về chuẩn 4 phân tầng Lakehouse để ngăn ngừa tạo thư mục rác.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"R2 upload source file does not exist: {path}")

    canonical_key = canonicalize_lakehouse_key(object_key)

    bucket = (
        bucket_name
        or os.getenv("R2_BUCKET_NAME")
        or os.getenv("S3_BUCKET_NAME")
        or "vn-it-jobs"
    )

    s3 = get_r2_client(endpoint_url=endpoint_url, access_key=access_key, secret_key=secret_key)
    s3.upload_file(str(path), bucket, canonical_key)
    return f"r2://{bucket}/{canonical_key}"


# Backward compatibility alias
upload_file_to_minio = upload_file_to_r2
