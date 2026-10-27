#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kiểm tra kết nối và sức khỏe hệ thống Cloudflare R2 Cloud Lakehouse.

VN-IT-Job-Mining (R2-Exclusive Object Storage).
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from collection.common.r2_storage import get_r2_client


def main():
    print("=" * 70)
    print("   KIỂM TRA SỨC KHỎE HỆ THỐNG CLOUDFLARE R2 CLOUD LAKEHOUSE")
    print("   Dự án: VN-IT-Job-Mining (R2-Exclusive Architecture)")
    print("=" * 70)

    endpoint = (
        os.getenv("R2_ENDPOINT_URL")
        or os.getenv("S3_ENDPOINT_URL")
        or "https://bb8811262069cd3e4d244a9dc7bf6a84.r2.cloudflarestorage.com"
    )
    bucket = os.getenv("R2_BUCKET_NAME") or os.getenv("S3_BUCKET_NAME") or "vn-it-jobs"

    print(f"1. Cấu hình kiểm tra:")
    print(f"  - Endpoint URL: {endpoint}")
    print(f"  - Target Bucket: {bucket}")

    try:
        s3 = get_r2_client()
        print("\n2. Kiểm tra xác thực Cloudflare R2 trên Bucket:")
        # Thử liệt kê đối tượng mẫu để kiểm tra kết nối tới bucket
        test_resp = s3.list_objects_v2(Bucket=bucket, MaxKeys=1)
        print(f"  [OK] Xác thực API thành công! Bucket '{bucket}' đang hoạt động.")

        print("\n3. Thống kê phân tầng dữ liệu trên Cloudflare R2:")
        paginator = s3.get_paginator("list_objects_v2")
        total_files = 0
        total_size = 0
        categories = {}

        for page in paginator.paginate(Bucket=bucket):
            for item in page.get("Contents", []):
                total_files += 1
                total_size += item["Size"]
                key = item["Key"]
                root_folder = key.split("/")[0] if "/" in key else "root"
                categories[root_folder] = categories.get(root_folder, 0) + 1

        print(f"  - Tổng số đối tượng (Objects): {total_files:,}")
        print(f"  - Tổng dung lượng lưu trữ:    {total_size / (1024 * 1024):.2f} MB")
        
        layer_icons = {
            "bronze": "🥉 [BRONZE]",
            "raw": "🥉 [BRONZE/RAW]",
            "url_ledger": "🥉 [BRONZE/LEDGER]",
            "silver": "🥈 [SILVER - MASTER]",
            "gold": "🥇 [GOLD - MINING]",
            "transformation": "⚙️  [INTERMEDIATE]",
            "integration": "⚙️  [INTERMEDIATE]",
        }
        for cat, cnt in sorted(categories.items()):
            tag = layer_icons.get(cat, "📁")
            print(f"    {tag:<22} {cat:<15}: {cnt:>6} files")

        print("\n4. Kiểm tra quyền ghi/xóa (Write/Delete probe):")
        probe_key = ".health_probe_r2.tmp"
        s3.put_object(Bucket=bucket, Key=probe_key, Body=b"healthcheck_ok")
        s3.delete_object(Bucket=bucket, Key=probe_key)
        print("  [OK] Quyền ghi & xóa trên Cloudflare R2 hoạt động hoàn hảo!")

        print("\n" + "=" * 70)
        print("🎉 TẤT CẢ KIỂM TRA ĐỀU THÀNH CÔNG! Cloudflare R2 đang sẵn sàng 100%.")
        print("=" * 70)
        return 0

    except Exception as exc:
        print(f"\n❌ Lỗi kết nối Cloudflare R2: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
