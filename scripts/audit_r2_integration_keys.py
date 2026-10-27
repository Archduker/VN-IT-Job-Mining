# -*- coding: utf-8 -*-
"""scripts/audit_r2_integration_keys.py — READ-ONLY Data Contract audit.

Stream toàn bộ 8 file `integration/<source>/<source>_integrated_flat.json` trên
Cloudflare R2 bằng Range GET + ijson (không tải master 39.6MB, không ghi/xóa/sửa
bất kỳ object nào trên bucket).

Đếm: union key, tần suất xuất hiện theo key, kiểu dữ liệu theo key, theo từng sàn.
Đối chiếu tự động với dict khởi tạo trong json_flattener.py (trích bằng AST).
"""

from __future__ import annotations

import ast
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import ijson

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.inspect_r2_integration import get_client  # noqa: E402

SOURCES = ["careerviet", "glints", "itviec", "jobsgo", "topcv", "topdev", "vieclam24h", "vietnamworks"]
CHUNK = 4 * 1024 * 1024  # 4 MB / Range GET


def canonical_keys_from_flattener() -> list[str]:
    """Trích danh sách key của dict khởi tạo `flat` trong flatten_raw_job_record bằng AST."""
    src = (PROJECT_ROOT / "preprocessing" / "integration" / "json_flattener.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "flatten_raw_job_record")
    d = next(n for n in ast.walk(fn) if isinstance(n, ast.Dict))
    return [k.value for k in d.keys if isinstance(k, ast.Constant)]


def type_of(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def stream_objects(s3, bucket: str, key: str):
    """Yield từng object trong JSON array top-level qua Range GET + ijson feedable.

    MỘT coroutine duy nhất sống suốt vòng đời file -> state parser không gãy
    khi object bị cắt giữa hai chunk.
    """
    total = s3.head_object(Bucket=bucket, Key=key)["ContentLength"]
    sent = 0
    conn = ijson.sendable_list()
    coroutine = ijson.items_coro(conn, "item")
    while True:
        end = min(sent + CHUNK - 1, total - 1)
        chunk = s3.get_object(Bucket=bucket, Key=key, Range=f"bytes={sent}-{end}")["Body"].read()
        sent = end + 1
        try:
            coroutine.send(chunk)
        except StopIteration:
            pass
        while conn:
            yield conn.pop(0)
        if sent >= total:
            return


def main():
    s3, bucket = get_client()
    expected = canonical_keys_from_flattener()

    key_freq = Counter()                 # key -> số record chứa key
    key_types = defaultdict(Counter)     # key -> Counter(types)
    per_source = {}                      # source -> (n_records, set(keys))

    for s in SOURCES:
        r2key = f"integration/{s}/{s}_integrated_flat.json"
        n = 0
        keys_seen = set()
        for obj in stream_objects(s3, bucket, r2key):
            n += 1
            for k, v in obj.items():
                key_freq[k] += 1
                key_types[k][type_of(v)] += 1
                keys_seen.add(k)
            if n % 1000 == 0:
                print(f"  ... {s}: {n:,} records", file=sys.stderr)
        per_source[s] = (n, keys_seen)
        print(f"[DONE] {s}: {n:,} records, {len(keys_seen)} distinct keys")

    total_records = sum(n for n, _ in per_source.values())
    union_keys = set(key_freq)
    extra = sorted(union_keys - set(expected))
    missing = sorted(set(expected) - union_keys)

    print("\n=== TONG HOP ===")
    print(f"Tong records (8 file per-source): {total_records:,}")
    print(f"Tong key duy nhuat (union): {len(union_keys)}")
    print(f"Key khoi tao trong json_flattener.py (AST): {len(expected)}")
    print(f"Key THUA so voi flattener : {extra or 'KHONG CO'}")
    print(f"Key THIEU so voi flattener: {missing or 'KHONG CO'}")

    print("\n=== BANG DATA CONTRACT THUC TE (R2) ===")
    print(f"{'#':>3} {'key':<24} {'co trong record':>15} {'%':>7}  kieu du lieu")
    for i, k in enumerate(sorted(union_keys), 1):
        pct = key_freq[k] / total_records * 100
        types = ", ".join(f"{t}:{c:,}" for t, c in key_types[k].most_common())
        print(f"{i:>3} {k:<24} {key_freq[k]:>15,} {pct:>6.1f}%  {types}")

    print("\n=== PHAN BO THEO SAN (keys lac so) ===")
    base = None
    for s, (n, ks) in per_source.items():
        if base is None:
            base = ks
        diff = ks ^ base
        print(f"  {s:<13} records={n:>5,} distinct_keys={len(ks):>2}" + (f"  LECH vs {next(iter(per_source))}: {sorted(diff)}" if diff else "  (trung 100%)"))

    out = {
        "total_records": total_records,
        "union_key_count": len(union_keys),
        "flattener_ast_key_count": len(expected),
        "extra_keys_vs_flattener": extra,
        "missing_keys_vs_flattener": missing,
        "key_freq": dict(key_freq),
        "key_types": {k: dict(v) for k, v in key_types.items()},
        "per_source": {s: {"records": n, "distinct_keys": len(ks)} for s, (n, ks) in per_source.items()},
    }
    Path("/tmp/r2_key_audit.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print("\n(Chi tiết machine-readable: /tmp/r2_key_audit.json)")


if __name__ == "__main__":
    main()
