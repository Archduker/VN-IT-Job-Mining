#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Đẩy dữ liệu cào thô và manifests cục bộ lên Cloudflare R2 Cloud Lakehouse.

VN-IT-Job-Mining (R2-Exclusive Object Storage).
"""

import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from collection.common.r2_storage import get_r2_client, upload_file_to_r2


def push_source_data(source: str = None, dry_run: bool = False):
    data_dir = PROJECT_ROOT / "data"
    bucket = os.getenv("R2_BUCKET_NAME") or os.getenv("S3_BUCKET_NAME") or "vn-it-jobs"
    s3 = get_r2_client()

    print("=" * 70)
    print("   ĐỒNG BỘ DỮ LIỆU CÀO CỤC BỘ LÊN CLOUDFLARE R2 LAKEHOUSE")
    print(f"   Bucket: {bucket}")
    print("=" * 70)

    # 1. Quét file trong data/<source>/raw và data/<source>/url_ledger
    target_sources = [source] if source else [
        "topdev", "vietnamworks", "careerviet", "vieclam24h",
        "itviec", "topcv", "jobsgo", "glints"
    ]

    total_uploaded = 0
    total_skipped = 0

    for src in target_sources:
        src_raw = data_dir / src / "raw"
        if not src_raw.exists():
            continue

        raw_files = list(src_raw.rglob("*.json"))
        print(f"\n>> Đang xử lý nguồn: {src.upper()} ({len(raw_files)} files raw)...")

        for f in raw_files:
            rel_under_raw = str(f.relative_to(src_raw)).replace("\\", "/")
            object_key = f"raw/{src}/{rel_under_raw}"

            if dry_run:
                print(f" [DRY-RUN] Sẽ upload: {object_key}")
                total_uploaded += 1
                continue

            try:
                # Kiểm tra xem object đã tồn tại chưa để tránh upload lại
                try:
                    s3.head_object(Bucket=bucket, Key=object_key)
                    total_skipped += 1
                    continue
                except Exception:
                    pass

                upload_file_to_r2(f, object_key, bucket_name=bucket)
                total_uploaded += 1
                if total_uploaded % 50 == 0:
                    print(f"  - Đã upload {total_uploaded} files...")
            except Exception as e:
                print(f"  [LỖI] {object_key}: {e}")

    print("\n" + "=" * 70)
    print(f"Hoàn thành! Đã upload: {total_uploaded} files | Đã tồn tại (Bỏ qua): {total_skipped} files")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Push local raw data to Cloudflare R2")
    parser.add_argument("--source", type=str, help="Lọc theo nguồn cụ thể")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ xem danh sách file cần đẩy")
    args = parser.parse_args()

    push_source_data(source=args.source, dry_run=args.dry_run)
