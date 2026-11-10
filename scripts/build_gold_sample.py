#!/usr/bin/env python3
"""Chọn 100 JD cho bộ gold (trước lọc IT, raw mới nhất mỗi job_id) -> data/preprocessing/gold/gold_sample.json.

Đặc tả: docs/spec/preprocessing/spec/PH1_gold_va_profiling.md. Cùng --seed cho cùng danh sách job_id.
    python scripts/build_gold_sample.py --seed 42
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from preprocessing.common import SOURCES  # noqa: E402
from preprocessing.common.raw_reader import latest_envelopes  # noqa: E402
from preprocessing.integration.json_flattener import flatten_raw_job_record  # noqa: E402

OUT = REPO_ROOT / "data" / "preprocessing" / "gold" / "gold_sample.json"
TAG = re.compile(r"<[^>]+>")


def quota(total: int = 100) -> dict:
    base, extra = divmod(total, len(SOURCES))
    return {s: base + (i < extra) for i, s in enumerate(SOURCES)}


def _text(flat: dict) -> str:
    parts = [flat.get("raw_description_text"), flat.get("raw_requirements_text")]
    text = "\n\n".join(str(p) for p in parts if p and str(p) != "None")
    text = TAG.sub("\n", text).replace("\r", "")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def build(seed: int, total: int = 100) -> dict:
    rng = random.Random(seed)
    items = []
    for source, n in quota(total).items():
        envs, _ = latest_envelopes(REPO_ROOT / "data" / source / "raw")
        flats = [flatten_raw_job_record(e) for e in sorted(envs, key=lambda e: str(e["metadata"].get("job_id")))]
        flats = [f for f in flats if f.get("job_id_global") and _text(f)]
        if len(flats) < n:
            sys.exit(f"{source}: chỉ có {len(flats)} tin có văn bản, cần {n}; chạy sync_cloud_lakehouse.py --download trước")
        for f in rng.sample(flats, n):
            items.append({
                "job_id": f["job_id_global"], "source": source, "url": f.get("source_url"),
                "title": f.get("job_title"), "company": f.get("company_name"), "text": _text(f),
                "raw": {k: (None if f.get(k) in (None, "None") else str(f.get(k)))
                        for k in ("raw_salary_text", "raw_experience_text", "raw_seniority_text", "raw_location_text", "raw_work_mode")},
            })
    return {"seed": seed, "items": items}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    sample = build(args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(sample, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Đã ghi {len(sample['items'])} JD (seed={args.seed}) -> {args.out}")


if __name__ == "__main__":
    main()
