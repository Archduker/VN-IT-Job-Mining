# -*- coding: utf-8 -*-
"""Bước 09_tokens của PH8: tokens và tokens_nostop theo JD (W3 [ĐỀ XUẤT]). Không bỏ JD."""

from __future__ import annotations

from typing import Dict

import pandas as pd

from preprocessing.common import SOURCES
from preprocessing.common.step_report import StepReport, merge_reports
from processing.extraction import sections as S
from processing.extraction.run import DEFAULT_INPUT, OUT_ROOT, REPORT_ROOT, analyze, default_matcher
from processing.transformation.tokenize import domain_stopwords, load_general_stopwords, remove_stopwords, tokenize

STEP = "09_tokens"


def run(sources=SOURCES, dry_run: bool = True, df=None, input_path=DEFAULT_INPUT, out_root=OUT_ROOT,
        report_root=REPORT_ROOT, matcher=None, headings=None, cues=None, df_threshold: float = 0.6) -> Dict[str, StepReport]:
    if df is None:
        if not input_path.exists():
            raise FileNotFoundError(f"thiếu bảng đầu vào {input_path} (P2 chưa chốt)")
        df = pd.read_parquet(input_path)
    matcher = matcher or default_matcher()
    headings = S.load_headings() if headings is None else headings
    cues = S.load_cues() if cues is None else cues
    df = df[df["source_platform"].isin(list(sources))].sort_values("job_id_global", kind="mergesort")
    docs = []
    for rec in df.to_dict("records"):
        bullets, _, hits = analyze(rec, matcher, headings, cues)
        toks = []
        for b in bullets:
            if b.section != "phuc_loi":  # phúc lợi không quét kỹ năng; vẫn tách từ
                toks += tokenize(b.text, hits.get(b.idx, ()))
            else:
                toks += tokenize(b.text)
        docs.append((rec["job_id_global"], rec["source_platform"], toks))
    general = load_general_stopwords()
    domain = domain_stopwords((t for _, _, t in docs), df_threshold)
    rows = [{"job_id_global": j, "source_platform": s, "tokens": t,
             "tokens_nostop": remove_stopwords(t, general, domain), "n_tokens": len(t)} for j, s, t in docs]
    reports = {}
    for src in sources:
        sub = [r for r in rows if r["source_platform"] == src]
        rep = StepReport(STEP, src, dry_run)
        rep.set_io(None, len(sub), out_root / STEP / "all.parquet", len(sub))
        rep.data["extra"] = {"mean_tokens_per_job": round(sum(r["n_tokens"] for r in sub) / len(sub), 2) if sub else None,
                             "df_threshold": df_threshold, "n_general_stopwords": len(general), "model": "không dùng model"}
        reports[src] = rep
    total = merge_reports(STEP, list(reports.values()), dry_run)
    total.data["extra"].update(df_threshold=df_threshold, domain_stopwords=domain)
    reports["_all"] = total
    for r in reports.values():
        r.check_conserved()
    if not dry_run:
        for r in reports.values():
            r.write(report_root)
        (out_root / STEP).mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_parquet(out_root / STEP / "all.parquet", index=False)
    return reports
