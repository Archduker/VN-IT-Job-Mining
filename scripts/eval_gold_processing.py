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
from preprocessing.common.text_clean import clean_text  # noqa: E402
from processing import evaluate as E  # noqa: E402
from processing.extraction import sections as S  # noqa: E402
from processing.extraction.run import analyze, default_matcher  # noqa: E402

GOLD_SAMPLE = ROOT / "data" / "preprocessing" / "gold" / "gold_sample.json"


def _flat_by_id(ids):
    from preprocessing.integration.json_flattener import flatten_raw_job_record
    out = {}
    for p in sorted((ROOT / "data" / "preprocessing" / "01_clean").glob("*.jsonl")):
        for line in p.open(encoding="utf-8"):
            r = json.loads(line)
            f = flatten_raw_job_record(r)
            if f.get("job_id_global") in ids:
                out[f["job_id_global"]] = f
    return out


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
    if not cov["sections"] and not cov["skills"]:
        print("chưa có nhãn sections/skills")
        return 0
    items = {i["job_id"]: i for i in json.loads(a.sample.read_text(encoding="utf-8"))["items"]}
    labels = {j: l for j, l in labels.items() if j in items}
    texts = {j: items[j]["text"] for j in labels}
    sources = {j: items[j]["source"] for j in labels}
    matcher, headings, cues = default_matcher(), S.load_headings(), S.load_cues()

    flats = _flat_by_id(set(labels))

    def run_one(jid):
        f = flats.get(jid)  # tách đúng description/requirements; không có thì cả `text` coi là mô tả (số section kém tin cậy)
        rec = ({"description_clean": clean_text(f.get("raw_description_text")), "requirements_clean": clean_text(f.get("raw_requirements_text"))}
               if f else {"description_clean": items[jid]["text"], "requirements_clean": None})
        return analyze(rec, matcher, headings, cues)

    cache = {}
    get = lambda j: cache.setdefault(j, run_one(j))  # noqa: E731
    out = {"coverage": cov,
           "section": E.section_accuracy(labels, texts, sources, lambda j: get(j)[0]),
           "skills": E.skills_f1(labels, sources, lambda j: get(j)[1], matcher),
           "note": f"{cov['sections']} JD có nhãn section, {cov['skills']} JD có nhãn skills; số đo tạm nếu gold chưa gán hết"}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
