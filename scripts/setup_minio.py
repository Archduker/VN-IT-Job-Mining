#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Script kiểm tra và khởi tạo MinIO Bucket cho dự án VN-IT-Job-Mining.

Sử dụng:
    python scripts/setup_minio.py
"""

import os
import sys
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
BUCKET_NAME = os.getenv("MINIO_BUCKET", "vn-it-jobs")


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def setup_minio_lake():
    print(f"Connecting to MinIO at {MINIO_ENDPOINT}...")
    s3 = get_s3_client()

    try:
        # Kiểm tra danh sách bucket hiện có
        response = s3.list_buckets()
        existing_buckets = [b["Name"] for b in response.get("Buckets", [])]
        print(f"Existing buckets: {existing_buckets}")

        if BUCKET_NAME not in existing_buckets:
            print(f"Creating bucket '{BUCKET_NAME}'...")
            s3.create_bucket(Bucket=BUCKET_NAME)
            print(f"Bucket '{BUCKET_NAME}' created successfully!")
        else:
            print(f"Bucket '{BUCKET_NAME}' already exists.")

        # Tạo cấu trúc các folder phân tầng ban đầu
        initial_prefixes = [
            "url_ledger/",
            "raw/",
            "staging/",
            "curated/",
        ]
        for prefix in initial_prefixes:
            s3.put_object(Bucket=BUCKET_NAME, Key=f"{prefix}.keep", Body=b"")

        print("MinIO Lakehouse directory structure verified successfully:")
        for prefix in initial_prefixes:
            print(f"  - minio://{BUCKET_NAME}/{prefix}")

        print("\nMinIO Ready!")
        print("  - Web Console UI : http://localhost:9001 (User: minioadmin / Pass: minioadmin)")
        print(f"  - S3 API Endpoint: {MINIO_ENDPOINT}")
        print(f"  - Bucket Name    : {BUCKET_NAME}")

    except ClientError as e:
        print(f"ClientError: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Connection failed: {e}")
        print("Tip: Make sure MinIO is running (e.g., via 'bash scripts/start_minio.sh' or 'sudo docker compose -f docker-compose.minio.yml up -d')")
        sys.exit(1)


if __name__ == "__main__":
    setup_minio_lake()
