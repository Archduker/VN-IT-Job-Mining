# -*- coding: utf-8 -*-
"""PH3: mẫu 100 tin bị loại ở 01_clean (C5 JD ngắn, C8 CTV/đa cấp) để người dùng gán nhãn tay. Chỉ đọc local.

Đọc data/preprocessing/rejected/01_clean/*.jsonl (do bước 01 ghi khi chạy thật), seed 42, phân tầng theo luật.
Ghi data/preprocessing/review/scope_rejected_sample.csv; file đã có nhãn (cột nhan_tay) thì không ghi đè.
"""
import csv
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "preprocessing" / "rejected" / "01_clean"
OUT = ROOT / "data" / "preprocessing" / "review" / "scope_rejected_sample.csv"


def main(total: int = 100) -> int:
    if OUT.exists() and any((r.get("nhan_tay") or "").strip() for r in csv.DictReader(OUT.open(encoding="utf-8-sig"))):
        print("đã có nhãn tay, không ghi đè")
        return 0
    rows = [json.loads(x) for f in sorted(SRC.glob("*.jsonl")) for x in f.open(encoding="utf-8") if x.strip()]
    by_rule: dict[str, list[dict]] = {}
    for r in rows:
        by_rule.setdefault(r["rule"], []).append(r)
    rng, pick = random.Random(42), []
    for rule in sorted(by_rule):  # chia đều theo luật, luật ít tin thì lấy hết
        pool = sorted(by_rule[rule], key=lambda r: (r["source"], r["job_id"]))
        pick += rng.sample(pool, min(len(pool), total // len(by_rule)))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["source", "job_id", "rule", "reason", "job_title", "source_url", "nhan_tay"])
        for r in pick:
            w.writerow([r["source"], r["job_id"], r["rule"], r["reason"], r["job_title"], r["source_url"], ""])
    print(f"{len(pick)} dòng -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
