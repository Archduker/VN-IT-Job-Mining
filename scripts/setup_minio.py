#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check/init the local MinIO Lakehouse bucket and layer marker objects."""
from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    import boto3
    from botocore.client import Config
    from botocore.exceptions import ClientError
    from dotenv import load_dotenv
except ImportError as exc:
    print(f"[ERROR] Missing dependency: {exc}. Run: python -m pip install -r requirements.txt")
    raise SystemExit(1)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=False)
ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
BUCKET = os.getenv("MINIO_BUCKET", "vn-it-jobs")
PREFIXES = ("url_ledger/", "raw/", "staging/", "curated/")


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        config=Config(signature_version="s3v4", connect_timeout=5, read_timeout=10,
                      retries={"max_attempts": 3, "mode": "standard"}),
        region_name="us-east-1",
    )


def setup_minio_lake() -> int:
    print(f"[MinIO] Endpoint: {ENDPOINT}")
    print(f"[MinIO] Bucket:   {BUCKET}")
    try:
        s3 = get_s3_client()
        try:
            s3.head_bucket(Bucket=BUCKET)
            print(f"[OK] Bucket '{BUCKET}' already exists.")
        except ClientError as exc:
            error_code = str(exc.response.get("Error", {}).get("Code", ""))
            status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if error_code not in {"404", "NoSuchBucket", "NotFound"} and status != 404:
                raise
            s3.create_bucket(Bucket=BUCKET)
            print(f"[OK] Created bucket '{BUCKET}'.")

        for prefix in PREFIXES:
            key = prefix + ".keep"
            try:
                s3.head_object(Bucket=BUCKET, Key=key)
            except ClientError as exc:
                code = str(exc.response.get("Error", {}).get("Code", ""))
                status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
                if code not in {"404", "NoSuchKey", "NotFound"} and status != 404:
                    raise
                s3.put_object(Bucket=BUCKET, Key=key, Body=b"")
            print(f"  - minio://{BUCKET}/{prefix}")

        print("\n[OK] MinIO Lakehouse ready.")
        print("Console: " + os.getenv("MINIO_CONSOLE", "http://localhost:9001"))
        print("Bucket remains private by default; no anonymous access policy was changed.")
        return 0
    except Exception as exc:
        print(f"[ERROR] MinIO setup failed: {exc}", file=sys.stderr)
        print("Start Docker Desktop, then run: docker compose -f docker-compose.minio.yml up -d --build")
        return 1


if __name__ == "__main__":
    raise SystemExit(setup_minio_lake())
