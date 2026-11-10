#!/usr/bin/env python3
"""Xuất 50 cặp gốc/dịch (seed 42, phân tầng theo nguồn) ra CSV để kiểm tay. Chỉ đọc; ghi ngoài reports/ (JD là dữ liệu).

    python scripts/build_translation_review_sample.py [--in data/preprocessing/03_transformation/all.parquet] [--n 50]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
DEFAULT_IN = REPO_ROOT / "data" / "preprocessing" / "03_transformation" / "all.parquet"
DEFAULT_OUT = REPO_ROOT / "data" / "preprocessing" / "translation" / "review_sample_50.csv"


def stratified_sample(df: pd.DataFrame, n: int = 50, seed: int = 42) -> pd.DataFrame:
    """Mỗi nguồn >= 1 tin, phần còn lại theo tỉ lệ số tin; tin có đoạn failed luôn được ưu tiên."""
    df = df[df["translation_status"].isin(["translated", "failed"])]
    groups = {s: g for s, g in df.groupby("source_platform")}
    total = sum(len(g) for g in groups.values())
    quota = {s: max(1, round(n * len(g) / total)) for s, g in groups.items()}
    while sum(quota.values()) > n:  # làm tròn vượt: bớt nguồn lớn nhất
        quota[max(quota, key=quota.get)] -= 1
    while sum(quota.values()) < n and sum(quota.values()) < total:
        s = max((s for s in groups if quota[s] < len(groups[s])), key=lambda s: len(groups[s]) - quota[s])
        quota[s] += 1
    parts = []
    for s, g in groups.items():
        k = min(quota[s], len(g))
        failed = g[g["translation_status"] == "failed"].head(k)
        rest = g.drop(failed.index).sample(n=k - len(failed), random_state=42) if k > len(failed) else g.iloc[0:0]
        parts += [failed, rest]
    return pd.concat(parts)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", type=Path, default=DEFAULT_IN)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--n", type=int, default=50)
    a = ap.parse_args()
    if not a.inp.exists():
        sys.exit(f"Chưa có {a.inp}: chạy 03 với --translate trước (PH9).")
    s = stratified_sample(pd.read_parquet(a.inp), a.n)
    cols = ["job_id_global", "source_platform", "translation_status", "description_clean", "description_vi",
            "requirements_clean", "requirements_vi"]
    a.out.parent.mkdir(parents=True, exist_ok=True)
    s[cols].to_csv(a.out, index=False, encoding="utf-8-sig")
    print(f"{len(s)} tin -> {a.out}")


if __name__ == "__main__":
    main()
