#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts.push_silver_to_r2
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Đẩy toàn bộ Bộ Dữ Liệu Chuẩn (Silver Dataset - Medallion Architecture)
lên Cloudflare R2 Cloud Lakehouse (Bucket: vn-it-jobs, Prefix: silver/).

Tệp tải lên:
  - silver/silver_master_dataset.json (Nested 11 Khóa Gốc, 8,959 bản ghi)
  - silver/silver_flat_jobs.json (Bảng phẳng 8,959 bản ghi)
  - silver/silver_dataset_health_card.json (Bệnh án chất lượng dữ liệu)

Sử dụng:
  python scripts/push_silver_to_r2.py            # Upload thật lên R2
  python scripts/push_silver_to_r2.py --dry-run  # Chạy thử xem trước
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from collection.common.r2_storage import get_r2_client


def main():
    parser = argparse.ArgumentParser(description="Đẩy Bộ Dữ Liệu Silver lên Cloudflare R2 Lakehouse.")
    parser.add_argument("--dry-run", action="store_true", help="Chạy thử nghiệm không tải thật")
    args = parser.parse_args()

    print("=" * 80)
    print("      ĐỒNG BỘ SILVER DATASET LÊN CLOUDFLARE R2 CLOUD LAKEHOUSE")
    print("      Dự án: VN-IT-Job-Mining (Medallion Architecture: Silver Layer)")
    if args.dry_run:
        print("      🔍 [CHẾ ĐỘ CHẠY THỬ — DRY RUN: Không tải thực tế]")
    print("=" * 80)

    bucket = os.getenv("R2_BUCKET_NAME") or os.getenv("S3_BUCKET_NAME") or "vn-it-jobs"
    silver_dir = PROJECT_ROOT / "data" / "silver"

    if not silver_dir.exists():
        print(f"❌ [LỖI] Không tìm thấy thư mục: {silver_dir}")
        return 1

    files_to_upload = []
    expected_files = [
        "silver_master_dataset.json",
        "silver_flat_jobs.json",
        "silver_dataset_health_card.json",
    ]

    for fname in expected_files:
        p = silver_dir / fname
        if p.exists() and p.is_file():
            rel_key = f"silver/{fname}"
            files_to_upload.append((p, rel_key))
        else:
            print(f"⚠️ Cảnh báo: Tệp {fname} chưa có trong {silver_dir}")

    # Thu thập thêm các tệp JSON khác nếu có trong silver_dir
    for p in silver_dir.glob("*.json"):
        if p.name not in expected_files:
            rel_key = f"silver/{p.name}"
            files_to_upload.append((p, rel_key))

    if not files_to_upload:
        print("❌ Không tìm thấy tệp nào trong data/silver/ để tải lên!")
        return 1

    total_files = len(files_to_upload)
    total_bytes = sum(f[0].stat().st_size for f in files_to_upload)

    print(f"\n1. Thông tin chuẩn bị đồng bộ:")
    print(f"  - Target Bucket: {bucket}")
    print(f"  - Target Prefix: silver/")
    print(f"  - Tổng số tệp:   {total_files}")
    print(f"  - Tổng dung lượng: {total_bytes / (1024 * 1024):.2f} MB\n")

    for idx, (local_path, rel_key) in enumerate(files_to_upload, 1):
        size_mb = local_path.stat().st_size / (1024 * 1024)
        print(f"  [{idx}/{total_files}] {local_path.name:<35} -> s3://{bucket}/{rel_key} ({size_mb:.2f} MB)")

    if args.dry_run:
        print("\n✅ DRY-RUN HOÀN TẤT: Tất cả các tệp đều sẵn sàng tải lên.")
        return 0

    # Khởi tạo S3 Client
    s3 = get_r2_client()
    success_count = 0
    t0 = time.time()

    print("\n2. Bắt đầu tải lên Cloudflare R2:")
    for idx, (local_path, rel_key) in enumerate(files_to_upload, 1):
        size_mb = local_path.stat().st_size / (1024 * 1024)
        print(f"  [{idx}/{total_files}] Đang tải {local_path.name} ({size_mb:.2f} MB)...", end="", flush=True)
        step_t0 = time.time()
        try:
            s3.upload_file(
                Filename=str(local_path),
                Bucket=bucket,
                Key=rel_key,
                ExtraArgs={"ContentType": "application/json; charset=utf-8"},
            )
            step_dur = time.time() - step_t0
            print(f" [OK] ({step_dur:.2f}s)")
            success_count += 1
        except Exception as exc:
            print(f" [FAIL: {exc}]")

    elapsed = time.time() - t0
    print("\n" + "=" * 80)
    print("3. Kiểm tra xác minh sau khi tải lên:")
    verified_count = 0
    for local_path, rel_key in files_to_upload:
        try:
            resp = s3.head_object(Bucket=bucket, Key=rel_key)
            remote_size = resp["ContentLength"]
            local_size = local_path.stat().st_size
            if remote_size == local_size:
                print(f"  ✅ s3://{bucket}/{rel_key:<40} (Size: {remote_size:,} bytes - 100% Khớp)")
                verified_count += 1
            else:
                print(f"  ⚠️ s3://{bucket}/{rel_key:<40} (Size lệch: Remote {remote_size} != Local {local_size})")
        except Exception as exc:
            print(f"  ❌ Không thể kiểm tra s3://{bucket}/{rel_key}: {exc}")

    print("=" * 80)
    if verified_count == total_files:
        print(f"🎉 TẤT CẢ {verified_count}/{total_files} TỆP SILVER DATASET ĐÃ ĐƯỢC TẢI LÊN VÀ XÁC MINH 100%!")
        print(f"   Thời gian thực thi: {elapsed:.2f} giây")
        print("=" * 80)
        return 0
    else:
        print(f"⚠️ Cảnh báo: Chỉ xác minh thành công {verified_count}/{total_files} tệp.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
