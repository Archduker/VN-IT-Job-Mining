# -*- coding: utf-8 -*-
"""scripts/inspect_r2_integration.py — READ-ONLY khảo sát tầng integration/staging/curated trên R2.
Phát Nguyễn: phục vụ xác định đầu vào Staging thật cho module Text & Skill Processing.

Nguyên tắc an toàn:
  - Chỉ gọi list_objects_v2 / head_object (metadata).
  - CHỈ đọc nội dung khi Content-Length <= MAX_INLINE_BYTES (mặc định 2 MB).
  - Không Put/Delete/Copy — không thay đổi bất kỳ object nào.
"""

from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from collection.common.r2_storage import get_r2_client  # dùng chung helper team (AWS_* fallback)

MAX_INLINE_BYTES = 2 * 1024 * 1024
INLINE_LIMIT = 3  # số file nhỏ nhất được peek nội dung theo từng prefix


def get_client():
    s3 = get_r2_client()
    bucket = os.getenv("R2_BUCKET_NAME") or os.getenv("S3_BUCKET_NAME") or "vn-it-jobs"
    return s3, bucket


def list_objects(s3, bucket: str, prefix: str) -> list[dict]:
    out, token = [], None
    while True:
        kwargs: dict[str, Any] = {"Bucket": bucket, "Prefix": prefix, "MaxKeys": 1000}
        if token:
            kwargs["ContinuationToken"] = token
        resp = s3.list_objects_v2(**kwargs)
        out += resp.get("Contents", [])
        if not resp.get("IsTruncated"):
            return out
        token = resp.get("NextContinuationToken")


def summarize_jsonl(text: str, max_lines: int = 3) -> str:
    lines = [ln for ln in text.splitlines() if ln.strip()][:max_lines]
    parsed = []
    for ln in lines:
        try:
            obj = json.loads(ln)
            parsed.append({k: type(v).__name__ for k, v in list(obj.items())[:30]})
        except Exception:
            parsed.append(ln[:120])
    return json.dumps(parsed, ensure_ascii=False, indent=1)


def summarize_json_array(text: str) -> str:
    try:
        data = json.loads(text)
    except Exception:
        return f"<không parse được JSON, {len(text):,} chars>"
    if isinstance(data, dict):
        info = {"type": "dict", "top_keys": list(data.keys())[:20]}
        for k, v in data.items():
            if isinstance(v, list) and v:
                first = v[0]
                info[f"list[{k}]"] = {
                    "count": len(v),
                    "first_item_keys": list(first.keys())[:30] if isinstance(first, dict) else type(first).__name__,
                }
        return json.dumps(info, ensure_ascii=False, indent=1)
    if isinstance(data, list):
        first = data[0] if data else None
        return json.dumps({
            "type": "list", "count": len(data),
            "first_item_keys": list(first.keys())[:30] if isinstance(first, dict) else type(first).__name__,
        }, ensure_ascii=False, indent=1)
    return "<định dạng khác>"


def main():
    s3, bucket = get_client()
    mode = "parquet" if len(sys.argv) > 1 and sys.argv[1] == "--parquet" else "json"
    prefixes = ["integration/", "staging/", "curated/"]

    for prefix in prefixes:
        objs = list_objects(s3, bucket, prefix)
        print(f"\n{'='*78}\nPHÂN TẦNG '{prefix}' — {len(objs)} objects\n{'='*78}")
        for o in sorted(objs, key=lambda x: x["Key"]):
            print(f"  {o['Size']:>12,} B  {o['LastModified']:%Y-%m-%d %H:%M}  {o['Key']}")
        # Peek 3 file JSON nhỏ nhất (read-only, dưới ngưỡng MAX_INLINE_BYTES)
        small = sorted(
            (o for o in objs if o["Key"].endswith(".json") and o["Size"] <= MAX_INLINE_BYTES),
            key=lambda x: x["Size"],
        )[:INLINE_LIMIT]
        for o in small:
            print(f"\n  ---- PEEK (read-only) {o['Key']} ({o['Size']:,} B) ----")
            buf = io.BytesIO()
            s3.download_fileobj(bucket, o["Key"], buf)
            text = buf.getvalue().decode("utf-8", errors="replace")
            if mode == "parquet":
                print(text[:500])
            elif text.lstrip().startswith("{") and "\n" in text.strip() and not text.lstrip().startswith("["):
                # JSON Lines hay dict đơn? thử parse dòng đầu
                try:
                    json.loads(text)
                    print(summarize_json_array(text))
                except Exception:
                    print(summarize_jsonl(text))
            else:
                print(summarize_json_array(text))


if __name__ == "__main__":
    main()
