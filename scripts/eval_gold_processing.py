# -*- coding: utf-8 -*-
"""Đo PH8 trên bộ gold (chỉ đọc): độ đúng section và F1 kỹ năng.

    python scripts/eval_gold_processing.py --gold <file nhãn xuất từ gold_labeler.html>

Thiếu file nhãn hoặc chưa gán trường nào: in "chưa có nhãn", thoát 0, không in số.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from preprocessing.common.gold import coverage, load_gold  # noqa: E402
from processing import evaluate as E  # noqa: E402
from processing.extraction import sections as S  # noqa: E402
from processing.extraction.run import analyze, default_matcher  # noqa: E402

GOLD_SAMPLE = ROOT / "data" / "preprocessing" / "gold" / "gold_sample.json"


def benefits_prf(labels, items) -> dict:
    """Precision/recall phúc lợi (micro) của extract_benefits so với nhãn tay; chỉ tính JD đã gán nhãn."""
    from preprocessing.transformation.skill_extractor import extract_benefits
    tp = fp = fn = n = 0
    for jid, lab in labels.items():
        gold = lab.get("benefits")
        if gold is None:
            continue
        gold = set() if gold == "none" else set(gold)
        it = items[jid]
        pred = set(extract_benefits(it.get("benefits_list"), it.get("description_clean") or ""))
        tp += len(pred & gold); fp += len(pred - gold); fn += len(gold - pred); n += 1
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    return {"jobs": n, "tp": tp, "fp": fp, "fn": fn, "precision": None if p is None else round(p, 4), "recall": None if r is None else round(r, 4)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gold", type=Path, default=ROOT / "data" / "preprocessing" / "gold" / "gold_labels.json")
    ap.add_argument("--sample", type=Path, default=GOLD_SAMPLE)
    a = ap.parse_args(argv)
    if not a.gold.exists():
        print(f"chưa có nhãn ({a.gold} không tồn tại)")
        return 0
    labels = load_gold(a.gold)
    cov = coverage(labels)
    if not cov["sections"] and not cov["skills"] and not cov["benefits"]:
        print("chưa có nhãn sections/skills/benefits")
        return 0
    items = {i["job_id"]: i for i in json.loads(a.sample.read_text(encoding="utf-8"))["items"]}
    labels = {j: l for j, l in labels.items() if j in items}
    texts = {j: items[j]["text"] for j in labels}
    sources = {j: items[j]["source"] for j in labels}
    matcher, headings, cues = default_matcher(), S.load_headings(), S.load_cues()

    def run_one(jid):  # đúng cột mà bước 07/08 đọc (mẫu lấy từ bảng 04)
        it = items[jid]
        rec = {"description_clean": it.get("description_clean") or it["text"], "requirements_clean": it.get("requirements_clean"),
               "benefits_list": it.get("benefits_list"), "skills_list": it.get("skills_list")}
        return analyze(rec, matcher, headings, cues)

    cache = {}
    get = lambda j: cache.setdefault(j, run_one(j))  # noqa: E731
    out = {"coverage": cov, "benefits": benefits_prf(labels, items),
           "section": E.section_accuracy(labels, texts, sources, lambda j: get(j)[0]),
           "skills": E.skills_f1(labels, sources, lambda j: get(j)[1], matcher),
           "note": f"{cov['sections']} JD có nhãn section, {cov['skills']} JD có nhãn skills; số đo tạm nếu gold chưa gán hết"}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
