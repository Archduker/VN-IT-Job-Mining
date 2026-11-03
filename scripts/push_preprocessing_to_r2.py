#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Đẩy output pre-processing 5 bước lên R2: silver (bước 01–04) theo nguồn, gold (bước 05).

    python scripts/push_preprocessing_to_r2.py          # chạy thử: chỉ đọc R2, liệt kê key mới/lệch/khớp
    python scripts/push_preprocessing_to_r2.py --push   # ghi lên R2 (chỉ sau khi người dùng duyệt bản chạy thử)

Bố cục key và cách so: preprocessing/common/r2_export.py. Chỉ đẩy object chưa có hoặc lệch.
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
from preprocessing.common.r2_export import compare, object_metadata, plan_objects  # noqa: E402


def remote_meta(s3, bucket: str, key: str):
    from botocore.exceptions import ClientError

    try:
        return s3.head_object(Bucket=bucket, Key=key).get("Metadata", {})
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
            return None
        raise


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--push", action="store_true", help="ghi thật lên R2; không có cờ này thì chỉ so")
    args = ap.parse_args(argv)

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
    if not args.push or not todo:
        return 0

    for o in todo:
        body = o["build"]()
        s3.put_object(Bucket=bucket, Key=o["key"], Body=body, ContentType=o["content_type"], Metadata=object_metadata(o))
        print(f"đã đẩy {o['key']} ({len(body) / 1e6:.2f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
