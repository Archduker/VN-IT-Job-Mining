#!/usr/bin/env python3
"""
VN-IT-Job-Mining -- Kịch bản cấu hình Cloudflare R2 / S3 Cloud Storage dùng chung cho cả Team.
Hỗ trợ:
1. Nhập thông tin Cloudflare R2 qua CLI flags hoặc Wizard tương tác.
2. Kiểm tra bắt tay kết nối S3 API và tạo bucket 'vn-it-jobs' nếu chưa có.
3. Tự động đồng bộ 2.776 URL TopCV hiện có lên Cloud R2 để chia sẻ cho cả team.
4. Lưu an toàn cấu hình vào file .env cục bộ.
"""

import argparse
import json
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


def test_and_connect_r2(endpoint_url: str, access_key: str, secret_key: str, bucket_name: str):
    """Kiểm tra kết nối và tạo bucket trên Cloudflare R2 / S3."""
    print("\n[*] Đang kiểm tra bắt tay kết nối S3 API...")
    region = "auto" if "r2.cloudflarestorage.com" in endpoint_url else "us-east-1"
    
    try:
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4", connect_timeout=5, retries={"max_attempts": 2}),
            region_name=region,
        )

        # Kiểm tra bucket vn-it-jobs (dùng head_bucket để hỗ trợ cả token giới hạn phạm vi bucket)
        try:
            s3.head_bucket(Bucket=bucket_name)
            print(f"  [OK] Bucket '{bucket_name}' đã tồn tại và sẵn sàng truy cập trên Cloud!")
        except Exception as h_err:
            print(f"[*] Bucket '{bucket_name}' chưa có hoặc cần khởi tạo. Đang tạo bucket: {h_err}...")
            try:
                s3.create_bucket(Bucket=bucket_name)
                print(f"  [OK] Đã tạo thành công bucket '{bucket_name}' trên Cloud!")
            except Exception as c_err:
                print(f"  [!] Lưu ý khi khởi tạo bucket '{bucket_name}': {c_err}")

        return s3

    except Exception as exc:
        print(f"\n❌ Kết nối thất bại: {exc}")
        print("Vui lòng kiểm tra lại Endpoint URL, Access Key ID và Secret Access Key.")
        sys.exit(1)


def upload_existing_ledgers(s3, bucket_name: str):
    """Đẩy toàn bộ dữ liệu cào hiện có trong thư mục data/ lên Cloud R2."""
    data_dir = PROJECT_ROOT / "data"
    if not data_dir.exists():
        return

    print("\n[*] Đang quét và tải lên dữ liệu hiện có lên Cloud R2...")
    count = 0
    for root, _, files in os.walk(data_dir):
        for f in files:
            if f.endswith((".json", ".jsonl", ".parquet", ".html")):
                local_path = Path(root) / f
                rel_path = local_path.relative_to(PROJECT_ROOT / "data")
                s3_key = str(rel_path).replace("\\", "/")
                
                # Bỏ qua file checkpoint tạm
                if "checkpoints" in s3_key:
                    continue

                try:
                    s3.upload_file(str(local_path), bucket_name, s3_key)
                    count += 1
                    print(f"  ⬆️ Đã tải lên: {s3_key} ({local_path.stat().st_size:,} bytes)")
                except Exception as e:
                    print(f"  ❌ Lỗi tải lên {s3_key}: {e}")

    print(f"🎉 Hoàn thành tải lên {count} tệp dữ liệu lên Cloud R2 bucket '{bucket_name}'!")


def save_env_file(endpoint_url: str, access_key: str, secret_key: str, bucket_name: str):
    """Lưu cấu hình an toàn vào .env."""
    env_path = PROJECT_ROOT / ".env"
    lines = []
    
    # Đọc nội dung cũ nếu có để giữ các biến khác
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                key = line.split("=")[0].strip()
                if key not in [
                    "S3_PROVIDER", "S3_ENDPOINT_URL", "MINIO_ENDPOINT",
                    "AWS_ACCESS_KEY_ID", "MINIO_ROOT_USER",
                    "AWS_SECRET_ACCESS_KEY", "MINIO_ROOT_PASSWORD",
                    "S3_BUCKET_NAME", "MINIO_BUCKET", "AWS_REGION"
                ]:
                    lines.append(line)

    lines.append("\n# --- Cloudflare R2 / S3 Lakehouse Cấu Hình Chung Cho Cả Team ---\n")
    lines.append("S3_PROVIDER=cloudflare_r2\n")
    lines.append(f"S3_ENDPOINT_URL={endpoint_url}\n")
    lines.append(f"MINIO_ENDPOINT={endpoint_url}\n")
    lines.append(f"AWS_ACCESS_KEY_ID={access_key}\n")
    lines.append(f"MINIO_ROOT_USER={access_key}\n")
    lines.append(f"AWS_SECRET_ACCESS_KEY={secret_key}\n")
    lines.append(f"MINIO_ROOT_PASSWORD={secret_key}\n")
    lines.append(f"S3_BUCKET_NAME={bucket_name}\n")
    lines.append(f"MINIO_BUCKET={bucket_name}\n")
    lines.append("AWS_REGION=auto\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    print(f"\n[OK] Đã lưu thông tin cấu hình vào tệp {env_path}")


def main():
    parser = argparse.ArgumentParser(description="Thiết lập kết nối Cloudflare R2 / S3 Cloud Storage dùng chung")
    parser.add_argument("--account-id", type=str, help="Cloudflare Account ID")
    parser.add_argument("--endpoint", type=str, help="Full S3 Endpoint URL")
    parser.add_argument("--access-key", type=str, help="R2 Access Key ID")
    parser.add_argument("--secret-key", type=str, help="R2 Secret Access Key")
    parser.add_argument("--bucket", type=str, default="vn-it-jobs", help="Tên bucket chung (mặc định: vn-it-jobs)")
    parser.add_argument("--skip-upload", action="store_true", help="Bỏ qua bước tải dữ liệu hiện tại lên Cloud")
    args = parser.parse_args()

    print("=" * 70)
    print("   THIẾT LẬP CLOUDFLARE R2 DATA LAKEHOUSE DÙNG CHUNG (VN-IT-JOB-MINING)")
    print("=" * 70)

    endpoint_url = args.endpoint
    access_key = args.access_key
    secret_key = args.secret_key
    bucket_name = args.bucket

    # Nếu chưa truyền qua tham số CLI, hỏi tương tác
    if not endpoint_url and args.account_id:
        endpoint_url = f"https://{args.account_id}.r2.cloudflarestorage.com"

    if not endpoint_url:
        print("\nNhập thông tin kết nối Cloudflare R2:")
        acc_id = input("1. Nhập Cloudflare Account ID (hoặc toàn bộ Endpoint URL): ").strip()
        if acc_id.startswith("http://") or acc_id.startswith("https://"):
            endpoint_url = acc_id
        else:
            endpoint_url = f"https://{acc_id}.r2.cloudflarestorage.com"

    if not access_key:
        access_key = input("2. Nhập R2 Access Key ID: ").strip()

    if not secret_key:
        secret_key = input("3. Nhập R2 Secret Access Key: ").strip()

    if not bucket_name:
        b_input = input("4. Nhập Tên Bucket (mặc định: vn-it-jobs): ").strip()
        bucket_name = b_input if b_input else "vn-it-jobs"

    print(f"\nThông tin cấu hình:")
    print(f" - Endpoint URL: {endpoint_url}")
    print(f" - Access Key:   {access_key[:8]}...{access_key[-4:] if len(access_key) > 12 else ''}")
    print(f" - Bucket:       {bucket_name}")

    # 1. Bắt tay kết nối
    s3 = test_and_connect_r2(endpoint_url, access_key, secret_key, bucket_name)

    # 2. Lưu vào .env
    save_env_file(endpoint_url, access_key, secret_key, bucket_name)

    # 3. Tải lên dữ liệu hiện có
    if not args.skip_upload:
        upload_existing_ledgers(s3, bucket_name)

    print("\n" + "=" * 70)
    print("🎉 CHÚC MỪNG! HỆ THỐNG ĐÃ KẾT NỐI CLOUDFLARE R2 THÀNH CÔNG!")
    print("Từ bây giờ:")
    print("  1. Mọi crawler bạn chạy sẽ tự động đẩy URL và Raw data lên Cloud R2 chung.")
    print("  2. Đồng đội chỉ cần cấu hình cùng Endpoint & Key là thấy toàn bộ dữ liệu.")
    print("  3. Xem dữ liệu trên Cloud bất kỳ lúc nào bằng:")
    print("     .venv/bin/python scripts/view_urls.py --source topcv --minio")
    print("  4. Đồng bộ 2 chiều qua lệnh:")
    print("     .venv/bin/python scripts/sync_cloud_lakehouse.py --download")
    print("=" * 70)


if __name__ == "__main__":
    main()
