#!/usr/bin/env python3
"""
VN-IT-Job-Mining — Công cụ tải các file kết quả .json lên Cloudflare R2 Lakehouse.

Cung cấp giải pháp lưu trữ và chia sẻ các file kết quả tuyển dụng (.json) cho toàn nhóm:
- Batch dữ liệu cào chi tiết (Phase 2): data/<source>/dt=YYYY-MM-DD/batch_XXX.json
- Bộ 3 mẫu thử nghiệm (Samples DoD): crawlers/sources/<source>/samples/sample_*.json
- File kết quả kiểm thử: crawlers/sources/<source>/test_5_jobs.json

Cách sử dụng:
    # 1. Tải toàn bộ file kết quả .json của 1 nguồn cụ thể (VD: TopCV)
    python scripts/upload_to_r2.py --source topcv

    # 2. Tải 1 file kết quả cụ thể
    python scripts/upload_to_r2.py --file crawlers/sources/vietnamworks/test_5_jobs.json

    # 3. Tải toàn bộ kết quả của tất cả các nguồn trong thư mục data/
    python scripts/upload_to_r2.py --all-results

    # 4. Chế độ chạy thử (Dry Run) không tải thật
    python scripts/upload_to_r2.py --source vieclam24h --dry-run
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

try:
    import boto3
    from botocore.client import Config
except ImportError:
    print("❌ [LỖI] Thiếu thư viện boto3. Vui lòng chạy: pip install boto3 botocore python-dotenv")
    sys.exit(1)


SUPPORTED_SOURCES = [
    "topcv",
    "topdev",
    "vietnamworks",
    "careerviet",
    "vieclam24h",
    "itviec",
    "glints",
    "jobsgo",
]


def get_r2_client() -> tuple[Any, str, str]:
    """Khởi tạo S3 Client kết nối tới Cloudflare R2 từ biến môi trường .env."""
    endpoint = (
        os.getenv("S3_ENDPOINT_URL")
        or os.getenv("R2_ENDPOINT_URL")
        or ""
    )
    access_key = (
        os.getenv("AWS_ACCESS_KEY_ID")
        or os.getenv("R2_ACCESS_KEY_ID")
        or ""
    )
    secret_key = (
        os.getenv("AWS_SECRET_ACCESS_KEY")
        or os.getenv("R2_SECRET_ACCESS_KEY")
        or ""
    )
    bucket = (
        os.getenv("S3_BUCKET_NAME")
        or os.getenv("R2_BUCKET_NAME")
        or "vn-it-jobs"
    )

    if not endpoint or not access_key or not secret_key:
        print("\n" + "=" * 70)
        print("⚠️ [CẢNH BÁO] Chưa cấu hình thông tin Cloudflare R2 trong file .env!")
        print("=" * 70)
        print("Để kết nối Cloudflare R2, vui lòng cấu hình trong file .env:")
        print("  S3_ENDPOINT_URL=https://<your_account_id>.r2.cloudflarestorage.com")
        print("  AWS_ACCESS_KEY_ID=<your_r2_access_key_id>")
        print("  AWS_SECRET_ACCESS_KEY=<your_r2_secret_access_key>")
        print("  S3_BUCKET_NAME=vn-it-jobs")
        print("\n💡 Hoặc chạy script hướng dẫn tương tác 1 chạm:")
        print("  python scripts/setup_cloud_storage.py")
        print("=" * 70 + "\n")
        raise ValueError("Chưa thiết lập Cloudflare R2 credentials trong .env")

    region = "auto" if "r2.cloudflarestorage.com" in endpoint else "us-east-1"

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(
            signature_version="s3v4",
            connect_timeout=10,
            read_timeout=30,
            retries={"max_attempts": 3},
        ),
        region_name=region,
    )

    return s3, bucket, endpoint


def validate_json_file(file_path: Path) -> tuple[bool, str | None, int]:
    """Kiểm tra tính toàn vẹn và cú pháp của file JSON trước khi tải lên.

    Returns:
        (is_valid, error_message, record_count_or_size)
    """
    if not file_path.exists() or not file_path.is_file():
        return False, "File không tồn tại", 0

    if file_path.stat().st_size == 0:
        return False, "File rỗng (0 bytes)", 0

    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
            count = len(data) if isinstance(data, list) else 1
            return True, None, count
    except json.JSONDecodeError as exc:
        return False, f"Lỗi cú pháp JSON: {exc}", 0
    except Exception as exc:
        return False, f"Lỗi đọc file: {exc}", 0


def resolve_r2_key(local_path: Path, source: str | None = None, custom_dest: str | None = None) -> str:
    """Xác định S3/R2 Object Key chuẩn theo cấu trúc phân tầng Lakehouse."""
    if custom_dest:
        return custom_dest.strip().lstrip("/")

    resolved_path = local_path.resolve()
    rel_path_str = str(local_path).replace("\\", "/")

    # Trường hợp 1: Sổ cái URL Ledger (nếu có)
    if "url_ledger" in rel_path_str:
        src = source or _extract_source_from_path(rel_path_str)
        if "manifests" in rel_path_str:
            return f"url_ledger/{src}/manifests/{local_path.name}"
        return f"url_ledger/{src}/{local_path.name}"

    # Trường hợp 2: Mẫu deliverables (crawlers/sources/<source>/samples/sample_*.json)
    if "samples" in rel_path_str:
        src = source or _extract_source_from_path(rel_path_str)
        return f"samples/{src}/{local_path.name}"

    # Trường hợp 3: File test độc lập (test_5_jobs.json, ...)
    if "test" in local_path.name.lower():
        src = source or _extract_source_from_path(rel_path_str)
        return f"test/{src}/{local_path.name}"

    # Trường hợp 4: Nằm trong thư mục data/
    try:
        data_rel = resolved_path.relative_to(PROJECT_ROOT / "data")
        parts = data_rel.parts
        # Chuẩn hóa về raw/<source>/... nếu chưa có prefix raw
        if parts[0] != "raw":
            return f"raw/{str(data_rel).replace(chr(92), '/')}"
        return str(data_rel).replace("\\", "/")
    except ValueError:
        pass

    # Mặc định
    src = source or _extract_source_from_path(rel_path_str) or "misc"
    return f"raw/{src}/{local_path.name}"


def _extract_source_from_path(path_str: str) -> str:
    """Trích xuất tên nguồn tuyển dụng từ đường dẫn file."""
    for s in SUPPORTED_SOURCES:
        if f"/{s}/" in path_str or path_str.startswith(f"{s}/") or f"_{s}_" in path_str:
            return s
    return "unknown"


def discover_result_json_files(source: str | None = None, all_results: bool = False) -> list[Path]:
    """Quét và tìm kiếm các file kết quả JSON cần đồng bộ."""
    files: list[Path] = []
    seen: set[str] = set()

    sources = [source] if source else (SUPPORTED_SOURCES if all_results else [])

    for src in sources:
        # 1. Quét thư mục data/<src>/
        src_data_dir = PROJECT_ROOT / "data" / src
        if src_data_dir.exists():
            for p in src_data_dir.rglob("*.json"):
                if "checkpoints" not in str(p) and p.is_file() and str(p) not in seen:
                    seen.add(str(p))
                    files.append(p)

        # 2. Quét thư mục data/raw/<src>/
        raw_src_dir = PROJECT_ROOT / "data" / "raw" / src
        if raw_src_dir.exists():
            for p in raw_src_dir.rglob("*.json"):
                if p.is_file() and str(p) not in seen:
                    seen.add(str(p))
                    files.append(p)

        # 3. Quét file test_5_jobs.json
        test_file = PROJECT_ROOT / "crawlers" / "sources" / src / "test_5_jobs.json"
        if test_file.exists() and str(test_file) not in seen:
            seen.add(str(test_file))
            files.append(test_file)

        # 4. Quét thư mục samples/
        samples_dir = PROJECT_ROOT / "crawlers" / "sources" / src / "samples"
        if samples_dir.exists():
            for p in samples_dir.glob("*.json"):
                if p.is_file() and str(p) not in seen:
                    seen.add(str(p))
                    files.append(p)

    return sorted(files)


def upload_single_file(
    s3_client: Any,
    bucket: str,
    local_path: Path,
    r2_key: str,
    dry_run: bool = False,
) -> tuple[bool, int, str]:
    """Tải một file JSON lên Cloudflare R2 sau khi đã xác thực cú pháp.

    Returns:
        (is_success, file_size_bytes, message)
    """
    is_valid, err_msg, count_or_size = validate_json_file(local_path)
    if not is_valid:
        return False, 0, f"Bỏ qua file không hợp lệ: {err_msg}"

    size_bytes = local_path.stat().st_size

    if dry_run:
        return True, size_bytes, f"[DRY-RUN] Dự kiến tải lên: s3://{bucket}/{r2_key} ({size_bytes:,} bytes, {count_or_size} records)"

    try:
        s3_client.upload_file(
            Filename=str(local_path),
            Bucket=bucket,
            Key=r2_key,
            ExtraArgs={"ContentType": "application/json; charset=utf-8"},
        )
        return True, size_bytes, f"Đã tải lên: s3://{bucket}/{r2_key} ({size_bytes:,} bytes, {count_or_size} records)"
    except Exception as exc:
        return False, 0, f"Lỗi upload s3://{bucket}/{r2_key}: {exc}"


def run_upload(
    source: str | None = None,
    file_path: str | None = None,
    dest_key: str | None = None,
    all_results: bool = False,
    dry_run: bool = False,
) -> int:
    """Điều phối toàn bộ quy trình upload kết quả JSON lên Cloudflare R2."""
    print("=" * 80)
    print("☁️  VN-IT-JOB-MINING — CÔNG CỤ TẢI KẾT QUẢ .JSON LÊN CLOUDFLARE R2")
    if dry_run:
        print("   🔍 [CHẾ ĐỘ CHẠY THỬ — DRY RUN: Không thực hiện tải lên thực tế]")
    print("=" * 80)

    # 1. Tìm các file cần xử lý
    files_to_upload: list[tuple[Path, str]] = []

    if file_path:
        target = Path(file_path).resolve()
        if not target.exists():
            print(f"❌ [LỖI] Không tìm thấy file: {file_path}")
            return 1
        r2_key = resolve_r2_key(target, source=source, custom_dest=dest_key)
        files_to_upload.append((target, r2_key))

    elif source or all_results:
        found_paths = discover_result_json_files(source=source, all_results=all_results)
        if not found_paths:
            target_desc = f"nguồn '{source}'" if source else "tất cả các nguồn"
            print(f"⚠️  Không tìm thấy file kết quả .json nào cho {target_desc} trong hệ thống.")
            return 0

        for p in found_paths:
            r2_key = resolve_r2_key(p, source=source)
            files_to_upload.append((p, r2_key))

    else:
        print("⚠️  Vui lòng chọn một trong các tùy chọn:")
        print("   --source <source_name>   (Tải toàn bộ kết quả của 1 nguồn)")
        print("   --file <file_path>       (Tải 1 file cụ thể)")
        print("   --all-results            (Tải tất cả các nguồn)")
        print("   --help                   (Xem hướng dẫn chi tiết)")
        return 1

    # 2. Khởi tạo kết nối S3/R2 (nếu không dry-run)
    s3_client = None
    bucket = "vn-it-jobs"
    endpoint = "Cloudflare R2"

    if not dry_run:
        try:
            s3_client, bucket, endpoint = get_r2_client()
            print(f"[*] Đã kết nối thành công tới R2 Endpoint: {endpoint}")
            print(f"[*] Bucket đích: {bucket}\n")
        except Exception as exc:
            print(f"❌ Không thể kết nối tới Cloudflare R2: {exc}")
            return 1
    else:
        print(f"[*] Target Bucket: {bucket} | Mode: DRY RUN\n")

    # 3. Tiến hành kiểm tra và tải lên
    success_count = 0
    fail_count = 0
    total_bytes = 0

    for idx, (path_obj, key) in enumerate(files_to_upload, 1):
        rel_to_repo = str(path_obj.relative_to(PROJECT_ROOT)) if path_obj.is_relative_to(PROJECT_ROOT) else str(path_obj)
        print(f"[{idx:02d}/{len(files_to_upload):02d}] Đang xử lý: {rel_to_repo}")

        ok, size, msg = upload_single_file(
            s3_client=s3_client,
            bucket=bucket,
            local_path=path_obj,
            r2_key=key,
            dry_run=dry_run,
        )

        if ok:
            success_count += 1
            total_bytes += size
            print(f"   ✅ {msg}")
        else:
            fail_count += 1
            print(f"   ❌ {msg}")

    # 4. In bảng tổng kết
    print("\n" + "=" * 80)
    print("📊 BÁO CÁO TỔNG KẾT TẢI DỮ LIỆU LÊN CLOUDFLARE R2")
    print("=" * 80)
    print(f"  • Tổng số file quét được : {len(files_to_upload)}")
    print(f"  • Tải lên thành công     : {success_count} file(s)")
    print(f"  • Thất bại / Bỏ qua      : {fail_count} file(s)")
    print(f"  • Tổng dung lượng        : {total_bytes / 1024:.2f} KB ({total_bytes / (1024 * 1024):.4f} MB)")
    if dry_run:
        print("  • Trạng thái             : 🔍 Chạy thử nghiệm hoàn tất (DRY RUN)")
    else:
        print(f"  • Trạng thái             : 🎉 Đã đồng bộ an toàn lên Cloudflare R2 (Bucket: {bucket})")
    print("=" * 80 + "\n")

    return 0 if fail_count == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="VN-IT-Job-Mining — Tải các file kết quả .json lên Cloudflare R2 Lakehouse",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ thực tế:
  1. Tải kết quả của nguồn ViecLam24h:
     python scripts/upload_to_r2.py --source vieclam24h

  2. Tải 1 file cụ thể (kèm cờ dry-run xem trước):
     python scripts/upload_to_r2.py --file crawlers/sources/vieclam24h/test_5_jobs.json --dry-run

  3. Tải 1 file và chỉ định R2 key tùy chỉnh:
     python scripts/upload_to_r2.py --file data/topcv/dt=2026-10-16/batch_001.json --dest raw/topcv/dt=2026-10-16/batch_001.json

  4. Tải tất cả kết quả của cả 7 nguồn:
     python scripts/upload_to_r2.py --all-results
        """,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--source",
        "-s",
        type=str,
        choices=SUPPORTED_SOURCES,
        help="Tên nguồn tuyển dụng cần tải kết quả (topcv, topdev, vietnamworks,...)",
    )
    group.add_argument(
        "--file",
        "-f",
        type=str,
        help="Đường dẫn tới 1 file .json kết quả cụ thể cần tải lên",
    )
    group.add_argument(
        "--all-results",
        "-a",
        action="store_true",
        help="Tải toàn bộ các file kết quả .json của tất cả 7 nguồn",
    )

    parser.add_argument(
        "--dest",
        "-d",
        type=str,
        default=None,
        help="Key đích trên Cloudflare R2 (chỉ dùng kết hợp với --file)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chạy thử nghiệm kiểm tra cú pháp và hiển thị danh sách file sẽ upload mà không gửi đi thực tế",
    )

    args = parser.parse_args()

    exit_code = run_upload(
        source=args.source,
        file_path=args.file,
        dest_key=args.dest,
        all_results=args.all_results,
        dry_run=args.dry_run,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
