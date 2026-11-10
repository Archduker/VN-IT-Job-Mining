# -*- coding: utf-8 -*-
"""Bước 07_sections + 08_skills của PH8 trên bảng đã qua pre-processing.

Cột vào: job_id_global, source_platform, description_clean, requirements_clean (+ benefits_list, skills_list nếu có).
Không bỏ JD (dropped = 0). Ghi dưới out_root/<bước>/ và report_root/<bước>/; mặc định là data/processing, reports/processing.
"""

from __future__ import annotations

from collections import Counter
from typing import Dict, Optional

import pandas as pd

from preprocessing.common import REPO_ROOT, SOURCES
from preprocessing.common.step_report import StepReport, merge_reports
from processing.extraction import sections as S
from processing.extraction import skills as K
from processing.selection.sparsity import reduce_sparsity

DEFAULT_INPUT = REPO_ROOT / "data" / "preprocessing" / "04_normalization" / "all.parquet"
OUT_ROOT = REPO_ROOT / "data" / "processing"
REPORT_ROOT = REPO_ROOT / "reports" / "processing"
STEP7, STEP8 = "07_sections", "08_skills"


def _list(v):
    if v is None or (isinstance(v, float) and v != v):
        return []
    return list(v)


def analyze(row, matcher, headings, cues):
    """Dùng chung cho bước 7, 8, 9: (bullets, skill_rows, hits_by_bullet) của một JD."""
    benefits = "\n".join(map(str, _list(row.get("benefits_list")))) or None
    bullets = S.split_sections(row.get("description_clean"), row.get("requirements_clean"), benefits, headings, cues)
    rows, hits = K.extract_skills(bullets, matcher, _list(row.get("skills_list")))
    return bullets, rows, hits


def default_matcher() -> K.SkillMatcher:
    return K.SkillMatcher(K.load_taxonomy(), K.load_short_forms())


def run(sources=SOURCES, dry_run: bool = True, df: Optional[pd.DataFrame] = None, input_path=DEFAULT_INPUT,
        out_root=OUT_ROOT, report_root=REPORT_ROOT, matcher=None, headings=None, cues=None,
        min_df: Optional[int] = None, mode: str = "family", merge_map=None) -> Dict[str, Dict[str, StepReport]]:
    if df is None:
        if not input_path.exists():
            raise FileNotFoundError(f"thiếu bảng đầu vào {input_path} (P2 chưa chốt)")
        df = pd.read_parquet(input_path)
    matcher = matcher or default_matcher()
    headings = S.load_headings() if headings is None else headings
    cues = S.load_cues() if cues is None else cues
    groups = {s: v["group"] for s, v in matcher.taxonomy.items()}
    df = df.sort_values("job_id_global", kind="mergesort")
    df = df[df["source_platform"].isin(list(sources))]

    bullet_rows, skill_rows, per_src = [], [], {}
    for rec in df.to_dict("records"):
        src, jid = rec["source_platform"], rec["job_id_global"]
        bullets, srows, _ = analyze(rec, matcher, headings, cues)
        st = per_src.setdefault(src, {"jobs": 0, "no_bullet": 0, "no_skill": 0, "rule": {}, "sec": {}, "blocked": 0})
        st["jobs"] += 1
        st["no_bullet"] += not bullets
        st["no_skill"] += not any(r["via"] == "text" for r in srows)
        for b in bullets:
            bullet_rows.append({"job_id_global": jid, "source_platform": src, "bullet_idx": b.idx,
                                "section": b.section, "text": b.text, "section_rule": b.rule})
            st["rule"][b.rule] = st["rule"].get(b.rule, 0) + 1
            st["sec"][b.section] = st["sec"].get(b.section, 0) + 1
        skill_rows += [{**r, "job_id_global": jid, "source_platform": src} for r in srows]

    folded, spars = reduce_sparsity(skill_rows, len(df), groups, len(groups), merge_map, min_df, mode)
    reps7, reps8 = {}, {}
    for src in sources:
        st = per_src.get(src, {"jobs": 0, "no_bullet": 0, "no_skill": 0, "rule": {}, "sec": {}})
        r7, r8 = StepReport(STEP7, src, dry_run), StepReport(STEP8, src, dry_run)
        for r, step in ((r7, STEP7), (r8, STEP8)):
            r.set_io(input_path, st["jobs"], out_root / step / "all.parquet", st["jobs"])
        r7.data["extra"] = {"n_bullets": sum(st["sec"].values()), "bullets_by_section": st["sec"],
                            "bullets_by_rule": st["rule"], "n_jobs_no_bullet": st["no_bullet"],
                            "headings_approved": len(headings), "cues_approved": len(cues)}
        sk = [r for r in skill_rows if r["source_platform"] == src]
        r8.data["extra"] = {"n_job_skill_rows": len(sk), "n_jobs_no_skill": st["no_skill"],
                            "top_skills": [{"skill": s, "n_jobs": c} for s, c in
                                           Counter(r["slug"] for r in sk).most_common(30)],
                            "short_forms_approved": len(matcher.short_map), "alias_conflicts_dropped": len(matcher.conflicts)}
        reps7[src], reps8[src] = r7, r8
    for step, reps in ((STEP7, reps7), (STEP8, reps8)):
        total = merge_reports(step, list(reps.values()), dry_run)
        if step == STEP8:
            total.data["extra"]["sparsity"] = spars
        reps["_all"] = total
        for r in reps.values():
            r.check_conserved()
        if not dry_run:
            for r in reps.values():
                r.write(report_root)
    if not dry_run:
        (out_root / STEP7).mkdir(parents=True, exist_ok=True)
        (out_root / STEP8).mkdir(parents=True, exist_ok=True)
        pd.DataFrame(bullet_rows).to_parquet(out_root / STEP7 / "all.parquet", index=False)
        pd.DataFrame(skill_rows).to_parquet(out_root / STEP8 / "job_skills.parquet", index=False)
        if min_df or merge_map:
            pd.DataFrame(folded).to_parquet(out_root / STEP8 / "job_skills_reduced.parquet", index=False)
    return {STEP7: reps7, STEP8: reps8}
