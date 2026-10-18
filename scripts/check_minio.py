#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Health check for local MinIO endpoint, credentials, bucket and sample objects."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

try:
    import boto3
    from botocore.client import Config
    from dotenv import load_dotenv
except ImportError as exc:
    print(f"[ERROR] Missing dependency: {exc}. Run: python -m pip install -r requirements.txt")
    raise SystemExit(1)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=False)
ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000").rstrip("/")
CONSOLE = os.getenv("MINIO_CONSOLE", "http://localhost:9001")
ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
BUCKET = os.getenv("MINIO_BUCKET", "vn-it-jobs")


def main() -> int:
    print("=" * 68)
    print("VN-IT-Job-Mining — MINIO HEALTH CHECK")
    print("=" * 68)
    try:
        with urlopen(ENDPOINT + "/minio/health/live", timeout=5) as response:
            if not (200 <= response.status < 300):
                raise RuntimeError(f"Health endpoint returned HTTP {response.status}")
            print(f"[OK] S3 health API: {ENDPOINT}/minio/health/live")
    except (URLError, TimeoutError, OSError, RuntimeError) as exc:
        print(f"[FAIL] Cannot reach MinIO API: {exc}")
        print("Run: docker compose -f docker-compose.minio.yml up -d --build")
        return 1

    try:
        with urlopen(CONSOLE, timeout=5) as response:
            if not (200 <= response.status < 400):
                raise RuntimeError(f"Console returned HTTP {response.status}")
            print(f"[OK] Console UI responds: {CONSOLE}")
    except (URLError, TimeoutError, OSError, RuntimeError) as exc:
        print(f"[WARN] Console UI not responding: {exc}")
        print("S3 API may still work; inspect the console port mapping and MinIO logs.")

    try:
        s3 = boto3.client(
            "s3", endpoint_url=ENDPOINT,
            aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY,
            config=Config(signature_version="s3v4", connect_timeout=5, read_timeout=10),
            region_name="us-east-1",
        )
        s3.head_bucket(Bucket=BUCKET)
        response = s3.list_objects_v2(Bucket=BUCKET, MaxKeys=10)
        objects = response.get("Contents", [])
        print(f"[OK] Authenticated access to bucket: {BUCKET}")
        print(f"[INFO] Sample object count: {len(objects)} (max 10 displayed)")
        for item in objects:
            print(f"  - {item['Key']} ({item['Size']:,} bytes)")
        print(f"[INFO] Console UI: {CONSOLE}")
        print("[OK] MinIO endpoint, credentials and bucket verified.")
        return 0
    except Exception as exc:
        print(f"[FAIL] S3 authentication/bucket check failed: {exc}")
        print("Check MINIO_ROOT_USER, MINIO_ROOT_PASSWORD and MINIO_BUCKET in .env.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
