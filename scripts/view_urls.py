#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Công cụ kiểm tra & hiển thị danh sách URL đã lưu (URL Ledger) cho hệ thống VN-IT-Job-Mining.

Hỗ trợ:
1. Xem dữ liệu cục bộ trong data/<source>/url_ledger/
2. Xem dữ liệu trực tiếp trên MinIO Lakehouse: minio://vn-it-jobs/url_ledger/<source>/ (qua cờ --minio)
3. Lọc theo trạng thái (PENDING, DONE, FAILED, RECHECK_DUE, CLOSED), hiển thị bảng trực quan và xuất file.

Sử dụng:
    python scripts/view_urls.py --source topcv
    python scripts/view_urls.py --source topcv --minio
    python scripts/view_urls.py --source topcv --status PENDING --limit 20
    python scripts/view_urls.py --source topcv --status FAILED --show-errors
"""

import argparse
import csv
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_local_ledger(source: str) -> Dict[str, Any]:
    """Tải catalog_master.json từ thư mục cục bộ data/<source>/url_ledger/."""
    # Ưu tiên chuẩn mới data/<source>/url_ledger, fallback data/url_ledger/<source>
    target_path = Path(f"data/{source}/url_ledger/catalog_master.json")
    if not target_path.exists():
        legacy_path = Path(f"data/url_ledger/{source}/catalog_master.json")
        if legacy_path.exists():
            target_path = legacy_path

    if not target_path.exists():
        return {"records": {}, "source_path": str(target_path), "exists": False}

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {"records": data, "source_path": str(target_path), "exists": True}
    except Exception as exc:
        print(f"❌ Lỗi khi đọc {target_path}: {exc}", file=sys.stderr)
        return {"records": {}, "source_path": str(target_path), "exists": False}


def load_minio_ledger(
    source: str,
    bucket_name: str = "vn-it-jobs",
    endpoint: str = "http://localhost:9000",
    ak: str = "minioadmin",
    sk: str = "minioadmin",
) -> Dict[str, Any]:
    """Tải catalog_master.json và manifests trực tiếp từ MinIO S3 Lakehouse."""
    try:
        import boto3
        from botocore.client import Config

        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=ak,
            aws_secret_access_key=sk,
            config=Config(signature_version="s3v4", connect_timeout=3, retries={"max_attempts": 2}),
            region_name="us-east-1",
        )

        catalog_key = f"url_ledger/{source}/catalog_master.json"
        try:
            resp = s3.get_object(Bucket=bucket_name, Key=catalog_key)
            catalog_data = json.loads(resp["Body"].read().decode("utf-8"))
            return {
                "records": catalog_data,
                "source_path": f"minio://{bucket_name}/{catalog_key}",
                "exists": True,
                "from_minio": True,
            }
        except Exception:
            # Nếu catalog_master chưa có, quét các file manifest JSONL
            prefix = f"url_ledger/{source}/manifests/"
            objs = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
            contents = objs.get("Contents", [])
            if not contents:
                return {
                    "records": {},
                    "source_path": f"minio://{bucket_name}/{prefix}",
                    "exists": False,
                    "from_minio": True,
                }

            combined_records = {}
            for item in sorted(contents, key=lambda x: x["LastModified"], reverse=True):
                m_key = item["Key"]
                if not m_key.endswith(".jsonl"):
                    continue
                m_resp = s3.get_object(Bucket=bucket_name, Key=m_key)
                for line in m_resp["Body"].read().decode("utf-8").splitlines():
                    if line.strip():
                        rec = json.loads(line)
                        combined_records[rec["url_hash"]] = rec

            return {
                "records": combined_records,
                "source_path": f"minio://{bucket_name}/{prefix} ({len(contents)} manifests)",
                "exists": True,
                "from_minio": True,
            }

    except Exception as exc:
        print(f"❌ Không thể kết nối tới MinIO tại {endpoint}: {exc}", file=sys.stderr)
        print("💡 Gợi ý: Chạy 'bash scripts/start_minio.sh' hoặc kiểm tra Docker container MinIO.", file=sys.stderr)
        return {"records": {}, "source_path": f"minio://{bucket_name}/url_ledger/{source}/", "exists": False, "from_minio": True}


def render_dashboard(
    records: Dict[str, Dict[str, Any]],
    source: str,
    source_path: str,
    status_filter: Optional[str] = None,
    limit: int = 25,
    show_errors: bool = False,
    is_minio: bool = False,
):
    """Vẽ dashboard tóm tắt và bảng danh sách URL."""
    total = len(records)
    counts = Counter(r.get("status", "UNKNOWN") for r in records.values())
    repost_count = sum(1 for r in records.values() if r.get("repost_of_url_hash"))

    storage_label = "🌐 [MINIO S3 LAKEHOUSE]" if is_minio else "💻 [LOCAL STORAGE]"

    print("=" * 86)
    print(f"  BÁO CÁO KIỂM KÊ URL LEDGER — NGUỒN: {source.upper()} {storage_label}")
    print(f"  Đường dẫn: {source_path}")
    print("=" * 86)
    print(
        f"  Tổng phát hiện: {total:<6} | PENDING: {counts['PENDING']:<5} | DONE: {counts['DONE']:<5} "
        f"| FAILED: {counts['FAILED']:<5} | RECHECK: {counts['RECHECK_DUE']:<5} | REPOST: {repost_count}"
    )
    print("-" * 86)

    # Lọc danh sách
    filtered = list(records.values())
    if status_filter:
        s_filter = status_filter.upper()
        filtered = [r for r in filtered if r.get("status") == s_filter]

    # Sắp xếp mới nhất lên đầu
    filtered.sort(key=lambda x: x.get("discovered_at") or "", reverse=True)

    shown_count = len(filtered) if limit <= 0 else min(len(filtered), limit)
    filter_label = f" (Bộ lọc: {status_filter})" if status_filter else ""
    print(f"  Hiển thị {shown_count}/{len(filtered)} bài đăng{filter_label}:")
    print("-" * 86)
    print(f"{'#':<3} | {'Job ID':<10} | {'Status':<11} | {'Công Ty':<25} | {'Tiêu Đề':<28}")
    print("-" * 86)

    for i, r in enumerate(filtered[:shown_count], start=1):
        job_id = str(r.get("job_id", ""))[:10]
        st = r.get("status", "UNKNOWN")[:11]
        comp = (r.get("preliminary_company") or "Unknown")[:25]
        title = (r.get("preliminary_title") or r.get("canonical_url", ""))[:28]
        if not title.strip():
            title = r.get("canonical_url", "")[:28]

        # Đánh dấu màu trạng thái
        st_icon = "⏳" if st == "PENDING" else "✅" if st == "DONE" else "❌" if st == "FAILED" else "🔄"
        print(f"{i:<3} | {job_id:<10} | {st_icon} {st:<8} | {comp:<25} | {title:<28}")

        if show_errors and r.get("error_log"):
            print(f"    └── ⚠️ Lỗi: {r.get('error_log')}")

    print("-" * 86)
    if is_minio:
        print("💡 Bạn có thể xem trực quan trên MinIO Web Console UI: http://localhost:9001 (User: minioadmin / Pass: minioadmin)")
    else:
        print("💡 Để xem dữ liệu lưu trên MinIO S3, chạy thêm cờ: --minio")
    print("=" * 86)


def export_data(
    records: List[Dict[str, Any]],
    json_path: Optional[str] = None,
    csv_path: Optional[str] = None,
):
    """Xuất danh sách ra JSON hoặc CSV."""
    if json_path:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        print(f"✅ Đã xuất {len(records)} bản ghi ra JSON: {json_path}")

    if csv_path:
        fieldnames = [
            "job_id", "status", "canonical_url", "preliminary_title",
            "preliminary_company", "discovered_at", "last_scraped_at",
            "content_hash", "error_log"
        ]
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for r in records:
                writer.writerow(r)
        print(f"✅ Đã xuất {len(records)} bản ghi ra CSV: {csv_path}")


def main():
    parser = argparse.ArgumentParser(description="Xem và kiểm tra danh sách URL Ledger (Cục bộ & MinIO)")
    parser.add_argument("--source", type=str, default="topcv", help="Nguồn tuyển dụng (mặc định: topcv)")
    parser.add_argument("--minio", action="store_true", default=False, help="Đọc trực tiếp từ MinIO S3 Lakehouse")
    parser.add_argument("--status", type=str, default=None, help="Lọc theo trạng thái: PENDING, DONE, FAILED, RECHECK_DUE, CLOSED")
    parser.add_argument("--limit", type=int, default=25, help="Giới hạn số bài hiển thị (mặc định: 25, 0 = tất cả)")
    parser.add_argument("--show-errors", action="store_true", default=False, help="In chi tiết log lỗi cho các link FAILED")
    parser.add_argument("--export-json", type=str, default=None, help="Đường dẫn file xuất JSON")
    parser.add_argument("--export-csv", type=str, default=None, help="Đường dẫn file xuất CSV")
    parser.add_argument("--endpoint", type=str, default="http://localhost:9000", help="Endpoint MinIO (khi dùng --minio)")
    parser.add_argument("--bucket", type=str, default="vn-it-jobs", help="Tên bucket MinIO")

    args = parser.parse_args()

    if args.minio:
        res = load_minio_ledger(
            source=args.source,
            bucket_name=args.bucket,
            endpoint=args.endpoint,
        )
    else:
        res = load_local_ledger(source=args.source)

    if not res["exists"] or not res["records"]:
        print(f"⚠️ Không tìm thấy bản ghi URL Ledger nào cho '{args.source}' tại: {res['source_path']}")
        if not args.minio:
            print(f"💡 Thử chạy với cờ '--minio' hoặc chạy Phase 1 Discovery: python -m crawlers.sources.{args.source}.crawler --phase discovery")
        return

    render_dashboard(
        records=res["records"],
        source=args.source,
        source_path=res["source_path"],
        status_filter=args.status,
        limit=args.limit,
        show_errors=args.show_errors,
        is_minio=args.minio,
    )

    if args.export_json or args.export_csv:
        export_data(
            list(res["records"].values()),
            json_path=args.export_json,
            csv_path=args.export_csv,
        )


if __name__ == "__main__":
    main()
