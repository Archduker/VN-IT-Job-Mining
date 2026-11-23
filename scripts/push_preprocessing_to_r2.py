#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Đẩy output Pre-processing, Processing và Mining lên R2; xóa key cũ không còn đúng với dữ liệu hiện tại.

    python scripts/push_preprocessing_to_r2.py                             # chạy thử: chỉ đọc R2
    python scripts/push_preprocessing_to_r2.py --push                      # ghi object chưa có hoặc lệch
    python scripts/push_preprocessing_to_r2.py --push --delete-obsolete    # ghi, rồi xóa key cũ

Bố cục key và cách so: preprocessing/common/r2_export.py. Chỉ đẩy object chưa có hoặc lệch.
Key cũ: mọi key dưới staging/, pipeline/, curated/ trên R2 mà dữ liệu trên máy không còn sinh ra
(raw/ và url_ledger/ không bao giờ bị đụng tới). Chỉ xóa sau khi đã đẩy xong và không lỗi.
Hai lệnh ghi chỉ chạy sau khi người dùng duyệt bản chạy thử.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from collection.common.r2_storage import canonicalize_lakehouse_key, get_r2_client, resolve_r2_bucket  # noqa: E402
from preprocessing.common.r2_export import OBSOLETE_KEYS, compare, object_metadata, plan_objects  # noqa: E402

MANAGED_PREFIXES = ("staging/", "pipeline/", "curated/")  # raw/, url_ledger/ là bất biến, không bao giờ xóa


def remote_meta(s3, bucket: str, key: str):
    from botocore.exceptions import ClientError

    try:
        return s3.head_object(Bucket=bucket, Key=key).get("Metadata", {})
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
            return None
        raise


def stale_keys(s3, bucket: str, planned: set) -> list:
    """Key dưới MANAGED_PREFIXES có trên R2 nhưng không có trong kế hoạch đẩy."""
    out = []
    for prefix in MANAGED_PREFIXES:
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
            for o in page.get("Contents", []):
                if o["Key"] not in planned:
                    out.append((o["Key"], o["Size"], o["LastModified"]))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--push", action="store_true", help="ghi thật lên R2; không có cờ này thì chỉ so")
    ap.add_argument("--delete-obsolete", action="store_true", help="cùng --push: xóa key cũ sau khi đẩy xong")
    args = ap.parse_args(argv)
    if args.delete_obsolete and not args.push:
        ap.error("--delete-obsolete chỉ dùng cùng --push")

    s3, bucket = get_r2_client(), resolve_r2_bucket()
    objs = plan_objects(build=args.push)
    todo = []
    for o in objs:
        assert canonicalize_lakehouse_key(o["key"]) == o["key"], o["key"]
        o["status"] = compare(o, remote_meta(s3, bucket, o["key"]))
        print(f"{o['status']:9} {o['key']:58} rows={o['rows']}")
        if o["status"] != "khop":
            todo.append(o)
    print(f"Tổng {len(objs)} object: {len(todo)} cần đẩy (chua_day/lech), {len(objs) - len(todo)} đã khớp. Bucket: {bucket}")

    stale = stale_keys(s3, bucket, {o["key"] for o in objs})
    for key, size, modified in stale:
        why = "bước/pipeline cũ" if key in OBSOLETE_KEYS else "máy không còn sinh"
        print(f"{'cu_xoa':9} {key:58} {size / 1e6:.2f} MB, {modified:%Y-%m-%d} ({why})")
    print(f"{len(stale)} key cũ sẽ bị xóa khi chạy --push --delete-obsolete")
    if not args.push:
        return 0

    for o in todo:
        body = o["build"]()
        s3.put_object(Bucket=bucket, Key=o["key"], Body=body, ContentType=o["content_type"], Metadata=object_metadata(o))
        print(f"đã đẩy {o['key']} ({len(body) / 1e6:.2f} MB)")
    if args.delete_obsolete:
        for key, _, _ in stale:
            assert key.startswith(MANAGED_PREFIXES), key
            s3.delete_object(Bucket=bucket, Key=key)
            print(f"đã xóa {key}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
