#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Đưa file theo layout cũ (raw/crawling/<ngày>/<nguồn>/...) về layout chuẩn raw/<nguồn>/<ngày>/...

Mặc định chỉ chạy thử và in kế hoạch. Thêm --apply để thực hiện.

    python scripts/migrate_lakehouse_layout.py --local            # data/crawling/ -> data/<nguồn>/raw/<ngày>/
    python scripts/migrate_lakehouse_layout.py --local --apply
    python scripts/migrate_lakehouse_layout.py --r2               # chỉ liệt kê, không ghi gì lên R2
    python scripts/migrate_lakehouse_layout.py --r2 --apply       # copy sang key chuẩn rồi xóa key cũ

Không ghi đè: đích đã có mà nội dung khác thì bỏ qua và báo lại. Đích đã có và giống hệt thì
chỉ bỏ bản theo layout cũ.
"""

from __future__ import annotations

import argparse
import filecmp
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from collection.common.r2_storage import normalize_legacy_key  # noqa: E402
from sync_cloud_lakehouse import local_path_to_s3_key, s3_key_to_local_path  # noqa: E402

LEGACY_R2_PREFIXES = ("raw/crawling/", "raw/url_ledger/")


def migrate_local(data_dir: Path, apply: bool) -> Dict[str, object]:
    legacy_root = data_dir / "crawling"
    stats: Counter = Counter()
    conflicts: List[str] = []
    unmapped: List[str] = []
    if not legacy_root.exists():
        return {"stats": dict(stats), "conflicts": conflicts, "unmapped": unmapped}
    for src in sorted(p for p in legacy_root.rglob("*") if p.is_file()):
        key = local_path_to_s3_key(src, data_dir)
        if not key:
            unmapped.append(str(src.relative_to(data_dir)))
            stats["unmapped"] += 1
            continue
        dest = s3_key_to_local_path(key, data_dir)
        if dest.exists():
            if filecmp.cmp(src, dest, shallow=False):
                stats["duplicate_removed"] += 1
                if apply:
                    src.unlink()
            else:
                stats["conflict_skipped"] += 1
                conflicts.append(f"{src.relative_to(data_dir)} -> {dest.relative_to(data_dir)}")
            continue
        stats["moved"] += 1
        if apply:
            dest.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dest)
    if apply:
        for d in sorted((p for p in legacy_root.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
            if not any(d.iterdir()):
                d.rmdir()
        if legacy_root.exists() and not any(legacy_root.iterdir()):
            legacy_root.rmdir()
    return {"stats": dict(stats), "conflicts": conflicts, "unmapped": unmapped}


def migrate_r2(apply: bool) -> Dict[str, object]:
    from sync_cloud_lakehouse import get_s3_client

    s3, bucket, _ = get_s3_client()
    stats: Counter = Counter()
    conflicts: List[str] = []
    for prefix in LEGACY_R2_PREFIXES:
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
            for item in page.get("Contents", []):
                old_key = item["Key"]
                new_key = normalize_legacy_key(old_key)
                if new_key == old_key:
                    stats["unmapped"] += 1
                    continue
                try:
                    target = s3.head_object(Bucket=bucket, Key=new_key)
                except s3.exceptions.ClientError:
                    target = None
                if target is not None:
                    if target["ETag"] == item["ETag"]:
                        stats["duplicate_removed"] += 1
                        if apply:
                            s3.delete_object(Bucket=bucket, Key=old_key)
                    else:
                        stats["conflict_skipped"] += 1
                        conflicts.append(f"{old_key} -> {new_key}")
                    continue
                stats["moved"] += 1
                if apply:
                    s3.copy_object(Bucket=bucket, Key=new_key, CopySource={"Bucket": bucket, "Key": old_key})
                    s3.delete_object(Bucket=bucket, Key=old_key)
    return {"stats": dict(stats), "conflicts": conflicts, "bucket": bucket}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--local", action="store_true", help="Chuyển file trong data/crawling/")
    parser.add_argument("--r2", action="store_true", help="Chuyển key raw/crawling/ và raw/url_ledger/ trên R2")
    parser.add_argument("--apply", action="store_true", help="Thực hiện thật; không có cờ này thì chỉ chạy thử")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    if not (args.local or args.r2):
        parser.error("Chọn --local hoặc --r2")
    mode = "THỰC HIỆN" if args.apply else "CHẠY THỬ (thêm --apply để thực hiện)"
    for name, result in (("local", migrate_local(args.data_dir.resolve(), args.apply) if args.local else None),
                         ("R2", migrate_r2(args.apply) if args.r2 else None)):
        if result is None:
            continue
        stats = result["stats"]
        print(f"[{name}] {mode}: chuyển {stats.get('moved', 0)}, bỏ bản trùng {stats.get('duplicate_removed', 0)}, "
              f"bỏ qua vì khác nội dung {stats.get('conflict_skipped', 0)}, không ánh xạ được {stats.get('unmapped', 0)}")
        for line in result["conflicts"][:10]:
            print(f"  khác nội dung: {line}")
        for line in result.get("unmapped", [])[:10]:
            print(f"  không ánh xạ được: {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
