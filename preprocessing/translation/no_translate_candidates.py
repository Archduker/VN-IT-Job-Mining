# -*- coding: utf-8 -*-
"""Sinh ứng viên preprocessing/dictionaries/no_translate.json từ tần suất skills_list trên tin tiếng Anh.

Chỉ đọc data/preprocessing/02_integration/all.parquet; mọi mục approved=false, người dùng duyệt sau.
Giữ nguyên mục đã có (kể cả approved=true). Chạy: python -m preprocessing.translation.no_translate_candidates [--write]
"""
from __future__ import annotations

import argparse
import json
from collections import Counter

import pandas as pd

from preprocessing.common import REPO_ROOT
from preprocessing.common import text_clean as tc
from preprocessing.transformation.text_metrics import detect_jd_language
from preprocessing.translation.core import NO_TRANSLATE_FILE

SRC = REPO_ROOT / "data" / "preprocessing" / "02_integration" / "all.parquet"
SEED_TERMS = ("UI/UX",)  # spike 10/11: model dịch "UI/UX" thành "giao diện/giao diện"
MIN_DOCS = 3


def build(df: pd.DataFrame) -> list[dict]:
    texts = [tc.clean_text(f"{a or ''}\n{b or ''}") or "" for a, b in zip(df["raw_description_text"], df["raw_requirements_text"])]
    en = [i for i, t in enumerate(texts) if detect_jd_language(t, df["job_title"].iat[i], df["company_name"].iat[i]) == "en"]
    cnt: Counter = Counter()
    for i in en:
        sk = df["skills_list"].iat[i]
        cnt.update({str(s).strip() for s in (sk if sk is not None else []) if str(s).strip()})
    terms = {t: n for t, n in cnt.items() if n >= MIN_DOCS}
    for t in SEED_TERMS:
        terms.setdefault(t, sum(t.lower() in texts[i].lower() for i in en))
    return [{"term": t, "docs_en": n, "approved": False} for t, n in sorted(terms.items(), key=lambda x: -x[1])], len(en)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    cands, n_en = build(pd.read_parquet(SRC))
    old = json.loads(NO_TRANSLATE_FILE.read_text("utf-8")) if NO_TRANSLATE_FILE.exists() else {"entries": []}
    keep = {e["term"]: e for e in old["entries"]}
    for c in cands:
        keep.setdefault(c["term"], c)
    out = {"version": "0.1-candidates", "note": "Chỉ mục approved=true bị che khi dịch (PH5). Ứng viên từ skills_list tin tiếng Anh.",
           "docs_en_total": n_en, "entries": list(keep.values())}
    print(f"tin en: {n_en}; ứng viên: {len(cands)}; tổng mục: {len(keep)}")
    if a.write:
        NO_TRANSLATE_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
