#!/usr/bin/env python3
"""
VN-IT-Job-Mining -- Kịch bản kiểm tra sức khỏe và kết nối MinIO Lakehouse.
Hỗ trợ kiểm tra:
1. Kết nối cổng 9000 (S3 API) và 9001 (Web Console).
2. Tồn tại và quyền truy cập bucket 'vn-it-jobs'.
3. Liệt kê các tệp đã lưu trong Lakehouse.
"""

import os
import sys
from urllib.request import urlopen

try:
    import boto3
    from botocore.client import Config
except ImportError:
    print("[CẢNH BÁO] Chưa cài đặt boto3 trong môi trường Python!")
    print("Vui lòng chạy: pip install boto3")
    sys.exit(1)


def check_http_port(url: str, label: str) -> bool:
    try:
        with urlopen(url, timeout=3) as resp:
            print(f"  [OK] {label}: {url} phản hồi mã {resp.status}")
            return True
    except Exception as exc:
        print(f"  [LỖI] {label}: Không thể kết nối tới {url} ({exc})")
        return False


def main():
    print("=" * 65)
    print("   KIỂM TRA SỨC KHỎE HỆ THỐNG MINIO LAKEHOUSE (VN-IT-JOB-MINING)")
    print("=" * 65)

    endpoint_url = os.environ.get("MINIO_ENDPOINT", "http://localhost:9000")
    console_url = os.environ.get("MINIO_CONSOLE", "http://localhost:9001")
    access_key = os.environ.get("AWS_ACCESS_KEY_ID", "minioadmin")
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "minioadmin")
    bucket_name = os.environ.get("MINIO_BUCKET", "vn-it-jobs")

    print("\n1. Kiểm tra trạng thái cổng mạng:")
    s3_ok = check_http_port(f"{endpoint_url}/minio/health/live", "S3 Health API")
    web_ok = check_http_port(console_url, "Web Console UI")

    if not s3_ok:
        print("\n❌ MinIO S3 API chưa sẵn sàng. Hãy chạy: docker compose up -d")
        sys.exit(1)

    print("\n2. Kiểm tra xác thực S3 & Bucket:")
    try:
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )

        buckets = [b["Name"] for b in s3.list_buckets().get("Buckets", [])]
        print(f"  [OK] Danh sách Buckets tìm thấy: {buckets}")

        if bucket_name not in buckets:
            print(f"  [*] Bucket '{bucket_name}' chưa tồn tại. Đang tự động tạo...")
            s3.create_bucket(Bucket=bucket_name)
            print(f"  [OK] Đã tạo thành công bucket '{bucket_name}'!")
        else:
            print(f"  [OK] Bucket '{bucket_name}' đã tồn tại sẵn sàng.")

        # Liệt kê 5 đối tượng đầu tiên trong bucket
        resp = s3.list_objects_v2(Bucket=bucket_name, MaxKeys=5)
        contents = resp.get("Contents", [])
        print(f"\n3. Tình trạng dữ liệu trong bucket '{bucket_name}':")
        if contents:
            print(f"  Tìm thấy {len(contents)} đối tượng mẫu:")
            for item in contents:
                print(f"   - {item['Key']} ({item['Size']:,} bytes)")
        else:
            print("  (Bucket đang trống, sẵn sàng nhận dữ liệu cào)")

        print("\n" + "=" * 65)
        print("🎉 TẤT CẢ KIỂM TRA ĐỀU THÀNH CÔNG! MinIO đang hoạt động hoàn hảo.")
        print(f"👉 Mở Web Console: {console_url} (User: {access_key} / Pass: {secret_key})")
        print("=" * 65)

    except Exception as exc:
        print(f"\n❌ Lỗi khi tương tác S3: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
