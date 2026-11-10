# -*- coding: utf-8 -*-
"""Đếm chức danh lõi (N15) để người dùng duyệt ứng viên cho preprocessing/dictionaries/job_titles.json (PH6).

Chỉ đọc dữ liệu. Với --write-dict chỉ ghi file từ điển ứng viên, mọi mục approved=false; mục đã có trong file
(đã duyệt hay chưa) được giữ nguyên. Không tự duyệt mục nào. Nhóm nghề `family` là gợi ý của luật, người dùng xác nhận.
Dùng: python scripts/count_title_candidates.py [--input all.parquet] [--min-count 5] [--write-dict]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from preprocessing.common import REPO_ROOT  # noqa: E402
from preprocessing.normalization.job_title import DICT_PATH, FAMILY_RULES_V2, JOB_FAMILIES_12, core_title, fold  # noqa: E402
from preprocessing.normalization.text_cleaner import has_term  # noqa: E402


def count_candidates(titles, min_count: int = 5):
    forms, counts = defaultdict(Counter), Counter()
    for t in titles:
        core, _, _ = core_title(t)
        f = fold(core)
        if f:
            counts[f] += 1
            forms[f][core] += 1
    out = []
    for f, n in counts.most_common():
        if n < min_count:
            break
        family = next((fam for fam, terms in FAMILY_RULES_V2 if has_term(f, terms)), None)
        out.append({"canonical": forms[f].most_common(1)[0][0], "family": family, "aliases": [f],
                    "docs_with_title": n, "approved": False})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(REPO_ROOT / "data/preprocessing/03_transformation/all.parquet"))
    ap.add_argument("--min-count", type=int, default=5)
    ap.add_argument("--write-dict", action="store_true")
    a = ap.parse_args()
    df = pd.read_parquet(a.input, columns=["job_title_clean"])
    cands = count_candidates(df["job_title_clean"].dropna(), a.min_count)
    for c in cands:
        print(f"{c['docs_with_title']:>4}  {c['canonical']}  ->  {c['family']}")
    if a.write_dict:
        old = json.loads(DICT_PATH.read_text(encoding="utf-8")) if DICT_PATH.exists() else {}
        have = {e["canonical"] for e in old.get("entries", [])}
        entries = old.get("entries", []) + [c for c in cands if c["canonical"] not in have]
        DICT_PATH.write_text(json.dumps({
            "version": "0.1-candidates",
            "note": f"Mọi mục approved=false cho tới khi người dùng duyệt; chỉ mục approved=true được nạp. Đếm chức danh lõi (N15) với min-count={a.min_count}. `family` là gợi ý của luật, cần xác nhận.",
            "families": JOB_FAMILIES_12 + ["Other"], "entries": entries}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
