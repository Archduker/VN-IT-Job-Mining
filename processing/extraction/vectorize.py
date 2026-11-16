# -*- coding: utf-8 -*-
"""Bước 12 (PH8): TF-IDF 1-2 gram trên tokens_nostop của bước 09. Không có tập huấn luyện/kiểm thử nên fit trên toàn bộ
(chỉ dùng cho Mining unsupervised). Bigram nối bằng `|` để không lẫn với token ghép có dấu cách."""

from __future__ import annotations

import json
from typing import Dict, List, Tuple

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from preprocessing.common.step_report import StepReport, merge_reports

STEP = "12_tfidf"


def _analyzer(tokens) -> List[str]:
    t = list(tokens)
    return t + [f"{a}|{b}" for a, b in zip(t, t[1:])]


def vectorize(tokens: pd.DataFrame, min_df: int = 5, max_features: int = 20000):
    vec = TfidfVectorizer(analyzer=_analyzer, min_df=min_df, max_features=max_features, norm="l2", sublinear_tf=True)
    m = vec.fit_transform(tokens["tokens_nostop"])
    vocab = sorted(vec.vocabulary_, key=vec.vocabulary_.get)
    return m, vocab


def run(sources, dry_run: bool = True, out_root=None, report_root=None, min_df: int = 5, max_features: int = 20000):
    import scipy.sparse as sp

    from processing.extraction.run import OUT_ROOT, REPORT_ROOT
    out_root, report_root = out_root or OUT_ROOT, report_root or REPORT_ROOT
    t = pd.read_parquet(out_root / "09_tokens" / "all.parquet")
    t = t[t["source_platform"].isin(list(sources))].sort_values("job_id_global", kind="mergesort").reset_index(drop=True)
    m, vocab = vectorize(t, min_df, max_features)
    reports: Dict[str, StepReport] = {}
    for src in sources:
        n = int((t["source_platform"] == src).sum())
        r = StepReport(STEP, src, dry_run)
        r.set_io(None, n, out_root / STEP / "tfidf.npz", n)
        r.data["extra"] = {"vocab_size": len(vocab), "min_df": min_df, "max_features": max_features, "model": "TF-IDF (sklearn)"}
        reports[src] = r
    total = merge_reports(STEP, list(reports.values()), dry_run)
    total.data["extra"].update(vocab_size=len(vocab), nnz=int(m.nnz), shape=list(m.shape))
    reports["_all"] = total
    for r in reports.values():
        r.check_conserved()
    if not dry_run:
        for r in reports.values():
            r.write(report_root)
        (out_root / STEP).mkdir(parents=True, exist_ok=True)
        sp.save_npz(out_root / STEP / "tfidf.npz", m)
        (out_root / STEP / "vocab.json").write_text(json.dumps(vocab, ensure_ascii=False), encoding="utf-8")
        (out_root / STEP / "job_ids.json").write_text(json.dumps(list(t["job_id_global"])), encoding="utf-8")
    return reports
