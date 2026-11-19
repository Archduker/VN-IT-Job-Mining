#!/usr/bin/env python3
"""Đo bộ lọc IT (C4a) trên nhãn C4b, chỉ đọc (đặc tả 01 mục 6; prompt 01_clean_it_filter).

Đọc raw trên máy (`data/<nguồn>/raw/`, snapshot mới nhất như C1), nhãn `data/preprocessing/review/it_<nguồn>.csv` và
cách chia `data/preprocessing/gold/it_review/split_2026-11-19.csv`. In và ghi
`data/preprocessing/review/it_filter_eval.json`:

- `--rule old`: luật hai tầng cũ (`classify` + `classify_unknown`);
- `--rule new`: luật ba tầng với ngưỡng trong `preprocessing/dictionaries/it_filter_v2.json` (đo được cả bản chưa duyệt);
- `--grid`: thử lưới ngưỡng tầng 2 trên tập tune, in các phương án tốt nhất (ưu tiên precision IT).

    python scripts/eval_it_filter.py [--rule old|new|both] [--grid] [--split all|tune|giu_lai]
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from preprocessing.clean.label_review import wilson_ci  # noqa: E402
from preprocessing.common import SOURCES  # noqa: E402
from preprocessing.common import it_filter as F  # noqa: E402
from preprocessing.common.raw_reader import latest_envelopes  # noqa: E402
from preprocessing.integration.json_flattener import flatten_raw_job_record  # noqa: E402

REVIEW = ROOT / "data" / "preprocessing" / "review"
SPLIT = ROOT / "data" / "preprocessing" / "gold" / "it_review" / "split_2026-11-19.csv"
OUT = REVIEW / "it_filter_eval.json"
GRID = {"k_fam": [None, 1, 2, 3], "k_sec": [None, 2, 3, 4, 6], "k_cat": [None, 1, 2, 3, 4], "k_cat_itviec": [None, 0, 1],
        "k_core": [None, 6, 8, 10, 12, 15]}


def load_items(sources=SOURCES):
    """Mỗi tin có nhãn: nhãn, tập (tune/giu_lai), và các trường bộ lọc đọc."""
    split = {}
    if SPLIT.exists():
        with SPLIT.open(encoding="utf-8-sig") as f:
            split = {(r["nguon"], r["job_id"]): r["tap"] for r in csv.DictReader(f)}
    items, missing = [], 0
    for src in sources:
        path = REVIEW / f"it_{src}.csv"
        if not path.exists():
            continue
        with path.open(encoding="utf-8-sig") as f:
            labels = {r["job_id"]: r["nhan_tay"] for r in csv.DictReader(f) if r.get("nhan_tay") in ("it", "non_it")}
        envs, _ = latest_envelopes(ROOT / "data" / src / "raw")
        by_id = {str(e["metadata"].get("job_id")): e for e in envs}
        for jid, lab in sorted(labels.items()):
            env = by_id.get(jid)
            if env is None:
                missing += 1
                continue
            fl = flatten_raw_job_record(env, src)
            items.append({
                "source": src, "job_id": jid, "label": lab, "split": split.get((src, jid), "?"),
                "title": fl.get("job_title"), "company": fl.get("company_name"),
                "signals": list(fl.get("skills_list") or []) + list(fl.get("category_tags") or []),
                "jd": f"{fl.get('raw_description_text') or ''} {fl.get('raw_requirements_text') or ''}",
                "category": fl.get("raw_category_text") or "",
            })
    return items, missing


def old_rule(it):
    r = F.classify(it["title"], it["signals"])
    if r != "unknown":
        return r, 1
    return F.classify_unknown(it["title"], it["signals"], it["jd"], it["company"]), 2


def metrics(rows):
    """rows: (label, pred). P/R IT, precision non-IT, độ đúng, Wilson 95%."""
    tp = sum(1 for a, p in rows if a == "it" and p == "it")
    fp = sum(1 for a, p in rows if a != "it" and p == "it")
    fn = sum(1 for a, p in rows if a == "it" and p != "it")
    tn = len(rows) - tp - fp - fn
    r4 = lambda x: None if x is None else round(x, 4)  # noqa: E731
    ci = lambda a, b: None if not b else [round(v, 4) for v in wilson_ci(a, b)]  # noqa: E731
    return {"n": len(rows), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "accuracy": r4((tp + tn) / len(rows)) if rows else None, "accuracy_ci": ci(tp + tn, len(rows)),
            "precision_it": r4(tp / (tp + fp)) if tp + fp else None, "precision_it_ci": ci(tp, tp + fp),
            "recall_it": r4(tp / (tp + fn)) if tp + fn else None,
            "precision_non_it": r4(tn / (tn + fn)) if tn + fn else None}


def report(items, preds, name):
    out = {}
    for split in ("all", "tune", "giu_lai"):
        sel = [i for i, it in enumerate(items) if split == "all" or it["split"] == split]
        out[split] = {"_all": metrics([(items[i]["label"], preds[i][0]) for i in sel])}
        for key, f in (("tier", lambda i: f"tang_{preds[i][1]}"), ("source", lambda i: items[i]["source"])):
            g = defaultdict(list)
            for i in sel:
                g[f(i)].append((items[i]["label"], preds[i][0]))
            out[split][key] = {k: metrics(v) for k, v in sorted(g.items())}
    m = out["all"]["_all"]
    print(f"{name:5s} all: đúng {m['accuracy']}  P_IT {m['precision_it']}  R_IT {m['recall_it']}  "
          f"(tp {m['tp']} fp {m['fp']} fn {m['fn']} tn {m['tn']})  | giữ lại: đúng {out['giu_lai']['_all']['accuracy']} "
          f"P_IT {out['giu_lai']['_all']['precision_it']} {out['giu_lai']['_all']['precision_it_ci']}")
    return out


def grid(items, cfg, matcher):
    """Tầng 0, 1 và tín hiệu tầng 2 tính một lần; thử mọi tổ hợp ngưỡng trên tập tune."""
    base = []
    for it in items:
        if F.excluded_role(it["title"], cfg):
            base.append(("non_it", 0, None))
            continue
        r = F.classify_tier1(it["title"], it["signals"], cfg, matcher)
        base.append((r, 1, None) if r != "unknown" else
                    (None, 2, F.it_signals(it["title"], it["jd"], it["category"], cfg, matcher)))
    results = []
    for k_fam, k_sec, k_cat, k_iv, k_core in itertools.product(*GRID.values()):
        rule = {"k_fam": k_fam, "k_sec": k_sec, "k_cat": k_cat, "k_core": k_core,
                "k_cat_by_source": {} if k_iv is None else {"itviec": k_iv}}
        preds = [(st, lv) if st else (F.tier2_decide(sig, it["source"], rule), lv)
                 for (st, lv, sig), it in zip(base, items)]
        tune = metrics([(it["label"], p[0]) for it, p in zip(items, preds) if it["split"] == "tune"])
        results.append((rule, tune, preds))
    return results


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rule", choices=["old", "new", "both"], default="both")
    ap.add_argument("--grid", action="store_true")
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    items, missing = load_items()
    print(f"{len(items)} tin có nhãn đọc được raw; thiếu raw {missing}")
    if not items:
        print("chưa có nhãn hoặc raw (reason NO_LABELS)")
        return 0
    cfg = F.load_config(require_approved=False)
    out = {"n_items": len(items), "missing_raw": missing, "config_approved": cfg["_meta"].get("approved")}
    if a.rule in ("old", "both"):
        out["old"] = report(items, [old_rule(it) for it in items], "cũ")
    if a.rule in ("new", "both"):
        if all(cfg["tier2"]["rule"].get(k) is None for k in ("k_fam", "k_sec", "k_cat", "k_core")):
            print("mới: chưa có ngưỡng tầng 2 trong it_filter_v2.json (chạy --grid để chọn)")
        else:
            m = F.default_matcher()
            out["new"] = report(items, [F.classify_it(it["title"], it["signals"], it["jd"], it["category"], it["source"],
                                                      cfg, m) for it in items], "mới")
    if a.grid:
        res = grid(items, cfg, F.default_matcher())
        res.sort(key=lambda r: (-(r[1]["precision_it"] or 0), -(r[1]["accuracy"] or 0)))
        pareto, best_acc = [], -1.0
        for rule, tune, _ in sorted(res, key=lambda r: (-(r[1]["precision_it"] or 0), -(r[1]["recall_it"] or 0))):
            if (tune["recall_it"] or 0) > best_acc:   # biên precision ↔ recall trên tập tune
                pareto.append((rule, tune))
                best_acc = tune["recall_it"] or 0
        print("Biên precision IT ↔ recall IT trên tập tune:")
        for rule, tune in pareto[: a.top * 2]:
            print(f"  {json.dumps(rule)}  đúng {tune['accuracy']}  P_IT {tune['precision_it']}  R_IT {tune['recall_it']}")
        out["grid_pareto_tune"] = [{"rule": r, "tune": t} for r, t in pareto]
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("ghi", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
