#!/usr/bin/env python3
"""
VN-IT-Job-Mining -- Kịch bản đồng bộ dữ liệu hai chiều (Cloud Sync Tool).
Hỗ trợ:
- python scripts/sync_cloud_lakehouse.py --status : Xem thống kê dữ liệu trên Cloud
- python scripts/sync_cloud_lakehouse.py --upload : Đẩy dữ liệu cào mới từ máy mình lên Cloud R2
- python scripts/sync_cloud_lakehouse.py --download : Kéo dữ liệu của cả nhóm từ Cloud R2 về máy mình
- python scripts/sync_cloud_lakehouse.py --source topcv : Lọc theo nguồn cụ thể
"""

import argparse
import os
import sys
from pathlib import Path

try:
    import boto3
    from botocore.client import Config
    from dotenv import load_dotenv
except ImportError:
    print("[LỖI] Thiếu thư viện phụ thuộc. Vui lòng chạy: pip install boto3 python-dotenv")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def get_s3_client():
    endpoint = (
        os.getenv("S3_ENDPOINT_URL")
        or os.getenv("R2_ENDPOINT_URL")
        or os.getenv("MINIO_ENDPOINT")
        or "http://localhost:9000"
    )
    ak = (
        os.getenv("AWS_ACCESS_KEY_ID")
        or os.getenv("R2_ACCESS_KEY_ID")
        or os.getenv("MINIO_ROOT_USER")
        or "minioadmin"
    )
    sk = (
        os.getenv("AWS_SECRET_ACCESS_KEY")
        or os.getenv("R2_SECRET_ACCESS_KEY")
        or os.getenv("MINIO_ROOT_PASSWORD")
        or "minioadmin"
    )
    region = "auto" if "r2.cloudflarestorage.com" in endpoint else "us-east-1"

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=ak,
        aws_secret_access_key=sk,
        config=Config(signature_version="s3v4", connect_timeout=5, retries={"max_attempts": 2}),
        region_name=region,
    )
    bucket = (
        os.getenv("S3_BUCKET_NAME")
        or os.getenv("R2_BUCKET_NAME")
        or os.getenv("MINIO_BUCKET")
        or "vn-it-jobs"
    )
    return s3, bucket, endpoint


def show_status(s3, bucket: str, endpoint: str, filter_source: str = None):
    print("=" * 70)
    print("   THỐNG KÊ DỮ LIỆU TRÊN CLOUD DATA LAKEHOUSE")
    print(f"   Bucket: {bucket} | Endpoint: {endpoint}")
    print("=" * 70)

    try:
        paginator = s3.get_paginator("list_objects_v2")
        prefix = f"url_ledger/{filter_source}/" if filter_source else ""
        pages = paginator.paginate(Bucket=bucket, Prefix=prefix)

        total_files = 0
        total_size = 0
        categories = {}

        for page in pages:
            for item in page.get("Contents", []):
                key = item["Key"]
                size = item["Size"]
                total_files += 1
                total_size += size

                root_folder = key.split("/")[0] if "/" in key else "root"
                categories[root_folder] = categories.get(root_folder, 0) + 1

        print(f"Tổng số đối tượng (Files): {total_files:,}")
        print(f"Tổng dung lượng lưu trữ:   {total_size / (1024 * 1024):.2f} MB")
        print("\nPhân bổ theo phân tầng Lakehouse:")
        for cat, cnt in sorted(categories.items()):
            print(f"  📁 {cat:<15}: {cnt:>5} files")

        print("=" * 70)
    except Exception as exc:
        print(f"❌ Không thể lấy danh sách đối tượng từ Cloud: {exc}")


def upload_to_cloud(s3, bucket: str, filter_source: str = None):
    print("=" * 70)
    print("   ĐỒNG BỘ DỮ LIỆU CỤC BỘ LÊN CLOUD DATA LAKEHOUSE (UPLOAD)")
    print("=" * 70)

    data_dir = PROJECT_ROOT / "data"
    if not data_dir.exists():
        print("⚠️ Thư mục data/ chưa tồn tại trên máy bạn.")
        return

    count = 0
    total_bytes = 0

    for root, _, files in os.walk(data_dir):
        for f in files:
            if not f.endswith((".json", ".jsonl", ".parquet", ".html")):
                continue

            local_path = Path(root) / f
            rel_path = local_path.relative_to(PROJECT_ROOT / "data")
            s3_key = str(rel_path).replace("\\", "/")

            if filter_source and not s3_key.startswith(f"{filter_source}/") and not f"/{filter_source}/" in s3_key:
                continue

            # Bỏ qua checkpoints
            if "checkpoints" in s3_key:
                continue

            try:
                s3.upload_file(str(local_path), bucket, s3_key)
                count += 1
                f_size = local_path.stat().st_size
                total_bytes += f_size
                print(f"  ⬆️ Uploaded: {s3_key} ({f_size:,} bytes)")
            except Exception as e:
                print(f"  ❌ Lỗi tải lên {s3_key}: {e}")

    print(f"\n🎉 Đã tải lên {count} tệp ({total_bytes / (1024 * 1024):.2f} MB) lên Cloud bucket '{bucket}'!")


def download_from_cloud(s3, bucket: str, filter_source: str = None):
    print("=" * 70)
    print("   TẢI DỮ LIỆU CẢ NHÓM TỪ CLOUD VỀ MÁY CỤC BỘ (DOWNLOAD)")
    print("=" * 70)

    data_dir = PROJECT_ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    try:
        paginator = s3.get_paginator("list_objects_v2")
        prefix = f"url_ledger/{filter_source}/" if filter_source else ""
        pages = paginator.paginate(Bucket=bucket, Prefix=prefix)

        count = 0
        total_bytes = 0

        for page in pages:
            for item in page.get("Contents", []):
                s3_key = item["Key"]
                size = item["Size"]

                if filter_source and not s3_key.startswith(f"{filter_source}/") and not f"/{filter_source}/" in s3_key:
                    continue

                local_dest = data_dir / s3_key
                local_dest.parent.mkdir(parents=True, exist_ok=True)

                # Tải file về
                try:
                    s3.download_file(bucket, s3_key, str(local_dest))
                    count += 1
                    total_bytes += size
                    print(f"  ⬇️ Downloaded: {s3_key} ({size:,} bytes)")
                except Exception as d_err:
                    print(f"  ❌ Lỗi tải xuống {s3_key}: {d_err}")

        print(f"\n🎉 Đã tải xuống {count} tệp ({total_bytes / (1024 * 1024):.2f} MB) về máy cục bộ!")
        print("💡 Bạn có thể xem ngay bằng lệnh: .venv/bin/python scripts/view_urls.py --source topcv")

    except Exception as exc:
        print(f"❌ Lỗi khi tải dữ liệu từ Cloud: {exc}")


def main():
    parser = argparse.ArgumentParser(description="Đồng bộ dữ liệu hai chiều giữa Máy Cục Bộ và Cloud Data Lakehouse")
    parser.add_argument("--upload", "-u", action="store_true", help="Đẩy dữ liệu cào mới từ máy mình lên Cloud R2")
    parser.add_argument("--download", "-d", action="store_true", help="Tải dữ liệu của cả nhóm từ Cloud R2 về máy mình")
    parser.add_argument("--status", "-s", action="store_true", help="Xem tình trạng dữ liệu trên Cloud R2")
    parser.add_argument("--source", type=str, help="Lọc theo nguồn cụ thể (topcv, itviec,...)")
    args = parser.parse_args()

    s3, bucket, endpoint = get_s3_client()

    if args.upload:
        upload_to_cloud(s3, bucket, filter_source=args.source)
    elif args.download:
        download_from_cloud(s3, bucket, filter_source=args.source)
    else:
        show_status(s3, bucket, endpoint, filter_source=args.source)


if __name__ == "__main__":
    main()
