#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Đẩy raw và URL Ledger cục bộ lên Cloudflare R2 Cloud Lakehouse.

Raw và ledger phải lên cùng nhau: chỉ đẩy raw thì ledger trên R2 không biết các tin đã cào, lần chạy sau
cào lại và trang Crawling đếm thiếu (SCRAPE-4). Ledger chỉ được đẩy khi không cũ hơn bản trên R2.
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, Tuple
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from collection.common.r2_storage import get_r2_client, to_r2_key, upload_file_to_r2


def _latest_scrape(records: Dict[str, Any]) -> str:
    stamps = [str(r.get("last_scraped_at") or "") for r in records.values() if isinstance(r, dict)]
    return max(stamps, default="")


def ledger_push_decision(local: Dict[str, Any], remote: Dict[str, Any] | None) -> Tuple[bool, str]:
    """Có nên ghi ledger trên máy lên R2 không. Không bao giờ để bản cũ hoặc rỗng đè bản mới hơn."""
    if not local:
        return False, "ledger trên máy rỗng"
    if remote:
        local_last, remote_last = _latest_scrape(local), _latest_scrape(remote)
        if remote_last > local_last:
            return False, (f"ledger trên R2 mới hơn ({remote_last[:16]} > {local_last[:16]}); "
                           "chạy crawler --phase sync hoặc kéo về và merge trước")
        missing = len(set(remote) - set(local))
        if missing:
            return False, f"ledger trên R2 có {missing} URL mà máy không có; kéo về và merge trước"
    return True, "ok"


def push_ledger(src: str, s3, bucket: str, data_dir: Path, dry_run: bool) -> bool:
    ledger_dir = data_dir / src / "url_ledger"
    catalog = ledger_dir / "catalog_master.json"
    if not catalog.exists():
        print(f"  [LEDGER] {src}: không có {catalog.relative_to(data_dir)}, bỏ qua")
        return False
    local = json.loads(catalog.read_text(encoding="utf-8"))
    key = to_r2_key(f"url_ledger/{src}/catalog_master.json")
    try:
        remote = json.loads(s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8"))
    except Exception:
        remote = None
    ok, reason = ledger_push_decision(local, remote)
    if not ok:
        print(f"  [LEDGER] {src}: KHÔNG đẩy, {reason}")
        return False
    files = [catalog, *sorted((ledger_dir / "manifests").glob("*.jsonl"))]
    parquet = ledger_dir / "catalog_master.parquet"
    if parquet.exists():
        files.append(parquet)
    for f in files:
        object_key = to_r2_key(f"url_ledger/{src}/{f.relative_to(ledger_dir).as_posix()}")
        if dry_run:
            print(f" [DRY-RUN] Sẽ upload: {object_key}")
        else:
            upload_file_to_r2(f, object_key, bucket_name=bucket)
    print(f"  [LEDGER] {src}: {'sẽ đẩy' if dry_run else 'đã đẩy'} {len(files)} file ({len(local)} URL)")
    return True


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
            object_key = to_r2_key(f"raw/{src}/{rel_under_raw}")

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

        push_ledger(src, s3, bucket, data_dir, dry_run)

    print("\n" + "=" * 70)
    print(f"Hoàn thành! Đã upload: {total_uploaded} files | Đã tồn tại (Bỏ qua): {total_skipped} files")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Push local raw data to Cloudflare R2")
    parser.add_argument("--source", type=str, help="Lọc theo nguồn cụ thể")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ xem danh sách file cần đẩy")
    args = parser.parse_args()

    push_source_data(source=args.source, dry_run=args.dry_run)
