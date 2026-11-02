"""Helpers for uploading crawler outputs directly to Cloudflare R2 Cloud Lakehouse."""

from __future__ import annotations

import os
from pathlib import Path


def resolve_r2_endpoint(explicit: str | None = None, required: bool = True) -> str:
    """Return the R2 endpoint from the argument or the environment (.env is loaded).

    Lookup order: explicit, R2_ENDPOINT_URL, S3_ENDPOINT_URL, R2_ACCOUNT_ID.
    Raises ValueError if nothing is configured, unless required=False.
    """
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    endpoint = explicit or os.getenv("R2_ENDPOINT_URL") or os.getenv("S3_ENDPOINT_URL")
    account_id = os.getenv("R2_ACCOUNT_ID")
    if not endpoint and account_id:
        endpoint = f"https://{account_id}.r2.cloudflarestorage.com"
    if not endpoint and required:
        raise ValueError(
            "Chưa cấu hình Cloudflare R2 endpoint: đặt R2_ENDPOINT_URL hoặc R2_ACCOUNT_ID trong .env."
        )
    return endpoint or ""


def resolve_r2_bucket(explicit: str | None = None) -> str:
    """Tên bucket: tham số, R2_BUCKET_NAME, S3_BUCKET_NAME, mặc định vn-it-jobs."""
    return explicit or os.getenv("R2_BUCKET_NAME") or os.getenv("S3_BUCKET_NAME") or "vn-it-jobs"


def get_r2_client(
    endpoint_url: str | None = None,
    access_key: str | None = None,
    secret_key: str | None = None,
):
    """Initialize and return a boto3 S3 client configured for Cloudflare R2."""
    import boto3
    from botocore.client import Config

    endpoint = resolve_r2_endpoint(endpoint_url)
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
# Tầng có thư mục con theo nguồn: <tầng>/<nguồn>/...
SOURCE_LAYERS = ("raw", "url_ledger", "staging")
# Giữ khớp với SUPPORTED_SOURCES trong run.py
LAKEHOUSE_SOURCES = ("topdev", "vietnamworks", "itviec", "careerviet", "vieclam24h", "topcv", "glints", "jobsgo")


def normalize_legacy_key(object_key: str) -> str:
    """Đưa key theo layout cũ về layout chuẩn; key khác giữ nguyên.

    Layout cũ lưu raw theo ngày trước, nguồn sau trong thư mục ``crawling/``. Hàm canonicalize cũ đảo
    ``crawling/raw/...`` thành ``raw/crawling/...`` vì coi ``crawling`` là tên nguồn, nên R2 còn các key:
        * raw/crawling/<ngày>/<nguồn>/<file>        -> raw/<nguồn>/<ngày>/<file>
        * crawling/raw/<ngày>/<nguồn>/<file>        -> raw/<nguồn>/<ngày>/<file>
        * raw/url_ledger/<ngày>/<nguồn>/<file>      -> url_ledger/<nguồn>/snapshots/<ngày>/<file>
    """
    key = str(object_key).strip().replace("\\", "/").lstrip("/")
    parts = key.split("/")
    if len(parts) >= 5 and parts[3] in LAKEHOUSE_SOURCES:
        if (parts[0], parts[1]) in (("raw", "crawling"), ("crawling", "raw")):
            return "/".join(["raw", parts[3], parts[2], *parts[4:]])
        if (parts[0], parts[1]) == ("raw", "url_ledger"):
            return "/".join(["url_ledger", parts[3], "snapshots", parts[2], *parts[4:]])
    return key


def canonicalize_lakehouse_key(object_key: str) -> str:
    """Đảm bảo mọi object_key đẩy lên R2/R2 luôn tuân thủ chuẩn 4 phân tầng Lakehouse.

    - Tự động chuẩn hóa các key bị đảo ngược:
        * <source>/raw/...        -> raw/<source>/...
        * <source>/url_ledger/... -> url_ledger/<source>/...
        * <source>/staging/...    -> staging/<source>/...
    - Từ chối tuyệt đối các tệp cache/tạm/nhạy cảm: .browser_profile, router_state.json, *.tmp, checkpoints.
    """
    key = normalize_legacy_key(object_key)
    parts = key.split("/")

    # 1. Phát hiện file rác / ephemeral local cache
    for p in parts:
        if p.startswith(".") or p in ("checkpoints", "__pycache__", "router_state.json"):
            raise ValueError(f"Không được phép upload tệp cache/tạm lên Lakehouse: {object_key}")
    if parts[-1].endswith((".tmp", ".lock", ".swp")) or parts[-1] == "router_state.json":
        raise ValueError(f"Không được phép upload tệp cache/tạm lên Lakehouse: {object_key}")

    # 2. Đã đúng chuẩn 4 tầng; tầng theo nguồn phải có tên nguồn thật ở cấp 2
    if any(key.startswith(pfx) for pfx in CANONICAL_PREFIXES):
        if parts[0] in SOURCE_LAYERS and (len(parts) < 3 or parts[1] not in LAKEHOUSE_SOURCES):
            raise ValueError(f"Key thiếu tên nguồn hợp lệ ở cấp 2 (<tầng>/<nguồn>/...): {object_key}")
        return key

    # 3. Bị đảo ngược: <source>/<layer>/... (e.g. topcv/raw/... -> raw/topcv/...)
    if len(parts) >= 3 and parts[1] in SOURCE_LAYERS and parts[0] in LAKEHOUSE_SOURCES:
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


