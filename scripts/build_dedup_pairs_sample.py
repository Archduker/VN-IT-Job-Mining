# -*- coding: utf-8 -*-
"""PH4: mẫu 50 cặp gần ngưỡng để người dùng chấm tay (không tự chấm). Chỉ đọc data/preprocessing/01_clean, ghi 1 CSV local.

25 cặp bị loại (0.85 <= J < 0.90, cùng company_slug) + 25 cặp không bị loại (0.80 <= J < 0.85), seed 42,
tham số trong preprocessing/dictionaries/dedup_policy.json. Cột nhan_tay: "trung" / "khac". File đã có nhãn không bị ghi đè.
Precision = (số cặp nhóm 'bị loại' chấm "trung") / 25; nhóm 'không bị loại' chấm "trung" cho biết recall bị mất.
"""
import csv
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from preprocessing.deduplication import minhash as mh  # noqa: E402
from preprocessing.deduplication import run as dedup  # noqa: E402

OUT = ROOT / "data" / "preprocessing" / "review" / "dedup_pairs_sample.csv"


def main() -> int:
    if OUT.exists() and any((r.get("nhan_tay") or "").strip() for r in csv.DictReader(OUT.open(encoding="utf-8-sig"))):
        print("đã có nhãn tay, không ghi đè")
        return 0
    cfg = mh.policy()["manual_check"]
    items, seen = [], set()
    for src in dedup.SOURCES:
        for it in dedup.load_items(src):
            if it["fkey"] and it["fkey"] in seen:  # cặp sha1 trùng đã bị tầng 2 loại, không thuộc dải gần ngưỡng
                continue
            seen.add(it["fkey"])
            items.append(it)
    pairs = mh.candidate_pairs([i["sh"] for i in items])
    rem_lo, rem_hi = cfg["removed_band"]
    keep_lo, keep_hi = cfg["not_removed_band"]
    removed = [(i, j, v) for i, j, v in pairs if rem_lo <= v < rem_hi and items[i]["slug"] and items[i]["slug"] == items[j]["slug"]]
    kept = [(i, j, v) for i, j, v in pairs if keep_lo <= v < keep_hi]
    rng = random.Random(cfg["seed"])
    n = cfg["per_group"]
    pick = [("bi_loai", *p) for p in rng.sample(removed, min(n, len(removed)))] + \
           [("khong_bi_loai", *p) for p in rng.sample(kept, min(n, len(kept)))]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["pair_id", "nhom", "jaccard", "same_company", "same_source", "title_differs",
                    "src_a", "id_a", "title_a", "company_a", "url_a", "src_b", "id_b", "title_b", "company_b", "url_b", "nhan_tay"])
        for n_, (grp, i, j, v) in enumerate(pick, 1):
            a, b = items[i], items[j]
            w.writerow([n_, grp, round(v, 4), a["slug"] == b["slug"], a["src"] == b["src"], a["tkey"] != b["tkey"],
                        a["src"], a["jid"], a["flat"].get("job_title"), a["flat"].get("company_name"), a["url"],
                        b["src"], b["jid"], b["flat"].get("job_title"), b["flat"].get("company_name"), b["url"], ""])
    print(f"{len(pick)} cặp (bị loại có sẵn {len(removed)}, không bị loại có sẵn {len(kept)}) -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
