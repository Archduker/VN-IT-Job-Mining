#!/usr/bin/env python3
"""Chọn 100 JD cho bộ gold từ bảng đã xử lý 04_normalization -> data/preprocessing/gold/gold_sample.json.

Đặc tả: docs/spec/preprocessing/spec/PH1_gold_va_profiling.md. Cùng --seed cho cùng danh sách job_id.
    python scripts/build_gold_sample.py --seed 42
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import pandas as pd  # noqa: E402

from preprocessing.common import SOURCES  # noqa: E402

OUT = REPO_ROOT / "data" / "preprocessing" / "gold" / "gold_sample.json"
SRC = REPO_ROOT / "data" / "preprocessing" / "04_normalization" / "all.parquet"
RAW_KEYS = ("raw_salary_text", "raw_experience_text", "raw_seniority_text", "raw_location_text", "raw_work_mode")


def quota(total: int = 100) -> dict:
    base, extra = divmod(total, len(SOURCES))
    return {s: base + (i < extra) for i, s in enumerate(SOURCES)}


def _s(v):
    if v is None or (not hasattr(v, "__len__") and pd.isna(v)):
        return None
    return v.tolist() if hasattr(v, "tolist") else v


def _list(v) -> list:
    v = _s(v)
    return [str(x) for x in v if str(x).strip()] if isinstance(v, list) else []


def _text(row) -> str:
    """Mô tả + yêu cầu + phúc lợi của sàn (cột riêng, bước 07 cũng nối đúng 3 phần này)."""
    ben = "\n".join(_list(row.get("benefits_list")))
    parts = [row.get("description_clean"), row.get("requirements_clean"), ben]
    return "\n\n".join(str(p) for p in parts if isinstance(p, str) and p.strip())


def build(seed: int, total: int = 100, src: Path = SRC) -> dict:
    """Lấy mẫu từ bảng đã xử lý (04): job_id là tin còn lại sau lọc/khử trùng; `text` là văn bản đã làm sạch mà bước 07/08 xử lý."""
    df = pd.read_parquet(src)
    df = df[df.apply(lambda r: bool(_text(r)), axis=1)].sort_values("job_id_global")
    rng = random.Random(seed)
    items = []
    for source, n in quota(total).items():
        part = df[df["source_platform"] == source]
        if len(part) < n:
            sys.exit(f"{source}: chỉ có {len(part)} tin có văn bản, cần {n}; chạy lại pipeline trước")
        for i in sorted(rng.sample(range(len(part)), n)):
            r = part.iloc[i].to_dict()
            items.append({
                "job_id": r["job_id_global"], "source": source, "url": _s(r.get("source_url")),
                "title": _s(r.get("job_title")), "company": _s(r.get("company_name")), "language": _s(r.get("language")),
                "text": _text(r), "benefits_list": _list(r.get("benefits_list")), "skills_list": _list(r.get("skills_list")),
                "description_clean": _s(r.get("description_clean")), "requirements_clean": _s(r.get("requirements_clean")),
                "raw": {k: (None if _s(r.get(k)) in (None, "None") else str(r.get(k))) for k in RAW_KEYS},
                # máy đoán: chỉ hiện sau khi người gán xong tin đó, để không bị lệch theo máy
                "pipeline": {k: _s(r.get(k)) for k in (
                    "title_canonical", "job_family", "seniority", "exp_min_years", "salary_min_vnd", "salary_max_vnd",
                    "salary_currency_raw", "salary_period_raw", "salary_status", "tinh_chinh", "work_mode", "skills_std", "benefits_std")},
            })
    sid = hashlib.sha1("|".join(i["job_id"] for i in items).encode()).hexdigest()[:10]
    return {"seed": seed, "sample_id": sid, "items": items}


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
