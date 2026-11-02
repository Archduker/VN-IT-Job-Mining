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


if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from collection.common.r2_storage import (  # noqa: E402
    LAKEHOUSE_SOURCES,
    canonicalize_lakehouse_key,
    get_r2_client,
    normalize_legacy_key,
    resolve_r2_bucket,
    resolve_r2_endpoint,
)


def get_s3_client():
    """Client R2 dùng chung với crawler (collection/common/r2_storage.py)."""
    endpoint = resolve_r2_endpoint()
    return get_r2_client(endpoint), resolve_r2_bucket(), endpoint


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


def local_path_to_s3_key(local_path: Path, data_dir: Path) -> str | None:
    """Ánh xạ đường dẫn local data/<source>/<layer>/... sang Lakehouse S3 key <layer>/<source>/..."""
    rel_path = local_path.relative_to(data_dir)
    parts = rel_path.parts

    # Bỏ qua các tệp/thư mục rác hoặc nhạy cảm
    for p in parts:
        if p.startswith(".") or p in ("checkpoints", "__pycache__", "router_state.json"):
            return None
    if parts[-1].endswith((".tmp", ".lock", ".swp")) or parts[-1] == "router_state.json":
        return None

    # Dùng chung luật với crawler: chuẩn hóa layout cũ, từ chối key không có tên nguồn hợp lệ
    try:
        return canonicalize_lakehouse_key("/".join(parts))
    except ValueError:
        return None


def s3_key_to_local_path(s3_key: str, data_dir: Path) -> Path:
    """Ánh xạ Lakehouse S3 key <layer>/<source>/... về đường dẫn local data/<source>/<layer>/...

    Key theo layout cũ (raw/crawling/<ngày>/<nguồn>/...) được đưa về đúng thư mục của nguồn.
    """
    parts = normalize_legacy_key(s3_key).split("/")
    if len(parts) >= 3 and parts[0] in ("raw", "url_ledger", "staging") and parts[1] in LAKEHOUSE_SOURCES:
        layer, source = parts[0], parts[1]
        rest = "/".join(parts[2:])
        return data_dir / source / layer / rest
    return data_dir / s3_key


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
            s3_key = local_path_to_s3_key(local_path, data_dir)
            if not s3_key:
                continue

            if filter_source and not s3_key.startswith(f"{filter_source}/") and not f"/{filter_source}/" in s3_key:
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
        skipped = 0
        total_bytes = 0

        for page in pages:
            for item in page.get("Contents", []):
                s3_key = item["Key"]
                size = item["Size"]

                if filter_source and not f"/{filter_source}/" in s3_key:
                    continue

                if s3_key.rsplit("/", 1)[-1].startswith("."):
                    continue  # file giữ chỗ như .keep
                local_dest = s3_key_to_local_path(s3_key, data_dir)
                if local_dest.exists() and local_dest.stat().st_size == size:
                    skipped += 1
                    continue  # đã tải ở lần trước, cho phép chạy lại để tải tiếp
                local_dest.parent.mkdir(parents=True, exist_ok=True)

                # Tải file về
                try:
                    s3.download_file(bucket, s3_key, str(local_dest))
                    count += 1
                    total_bytes += size
                    print(f"  ⬇️ Downloaded: {s3_key} ({size:,} bytes)")
                except Exception as d_err:
                    print(f"  ❌ Lỗi tải xuống {s3_key}: {d_err}")

        print(f"\n🎉 Đã tải xuống {count} tệp ({total_bytes / (1024 * 1024):.2f} MB) về máy cục bộ, bỏ qua {skipped} tệp đã có.")
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
