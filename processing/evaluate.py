# -*- coding: utf-8 -*-
"""Đo độ đúng tách section (PH8 5.1) và F1 kỹ năng (5.2) so với nhãn gold (preprocessing/common/gold.py).

Chưa có nhãn thật thì hàm gọi không có gì để đo: script trả "chưa có nhãn", không điền số.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Callable, Dict, Iterable, List

from preprocessing.common.text_clean import clean_text
from preprocessing.deduplication.text_norm import fold
from processing.extraction.skills import SkillMatcher, alias_owners


def _line_key(line: str) -> str:
    t = (clean_text(line) or "").strip()
    return fold(t[2:] if t.startswith("- ") else t).rstrip(":").strip()


def section_accuracy(labels: Dict[str, dict], texts: Dict[str, str], sources: Dict[str, str],
                     predict: Callable[[str], list]) -> dict:
    """predict(job_id) -> list[Bullet]. Đúng = fold(bullet) nằm trong dòng của đoạn nhãn cùng section. Bullet ngoài vùng nhãn: không tính."""
    tot = defaultdict(lambda: [0, 0, 0, 0])  # bullet đúng, bullet tính, JD tính, JD đúng 100%
    for jid, lab in labels.items():
        segs = lab.get("sections")
        if segs in (None, "none") or jid not in texts:
            continue
        by_line: Dict[str, set] = defaultdict(set)
        for s in segs:
            for line in texts[jid][s["start"]:s["end"]].split("\n"):
                if _line_key(line):
                    by_line[_line_key(line)].add(s["section"])
        ok = n = 0
        for b in predict(jid):
            secs = by_line.get(_line_key(b.text))
            if secs is None:
                continue
            n += 1
            ok += b.section in secs
        for key in (sources[jid], "_all"):
            t = tot[key]
            t[0] += ok; t[1] += n; t[2] += 1; t[3] += (n > 0 and ok == n)
    return {k: {"accuracy": round(v[0] / v[1], 4) if v[1] else None, "bullets": v[1], "jobs": v[2], "jobs_all_correct": v[3]}
            for k, v in sorted(tot.items())}


def _prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f = 2 * p * r / (p + r) if p and r else (0.0 if tp + fp + fn else None)
    return {"precision": p and round(p, 4), "recall": r and round(r, 4), "f1": f and round(f, 4), "tp": tp, "fp": fp, "fn": fn}


def skills_f1(labels: Dict[str, dict], sources: Dict[str, str], predict: Callable[[str], List[dict]],
              matcher: SkillMatcher) -> dict:
    """predict(job_id) -> skill rows (extract_skills). Chỉ via=text. Nhãn ngoài taxonomy tính FN và liệt kê riêng (K5)."""
    lookup = {k: next(iter(v)) for k, v in alias_owners(list(matcher.taxonomy.values())).items() if len(v) == 1}
    cnt = defaultdict(lambda: [0, 0, 0])
    lvl = defaultdict(lambda: [0, 0, 0])
    outside: Dict[str, int] = defaultdict(int)
    n_jobs = 0
    for jid, lab in labels.items():
        sk = lab.get("skills")
        if sk is None:
            continue
        n_jobs += 1
        gold, gold_lvl, miss = set(), set(), 0
        for s in [] if sk == "none" else sk:
            slug = lookup.get(fold(s["name"]))
            if slug:
                gold.add(slug); gold_lvl.add((slug, s["level"]))
            else:
                miss += 1; outside[fold(s["name"])] += 1
        rows = [r for r in predict(jid) if r["via"] == "text"]
        pred, pred_lvl = {r["slug"] for r in rows}, {(r["slug"], r["level"]) for r in rows}
        for key in (sources[jid], "_all"):
            c = cnt[key]; c[0] += len(pred & gold); c[1] += len(pred - gold); c[2] += len(gold - pred) + miss
            l = lvl[key]; l[0] += len(pred_lvl & gold_lvl); l[1] += len(pred_lvl - gold_lvl); l[2] += len(gold_lvl - pred_lvl) + miss
    return {"n_jobs_labeled": n_jobs, "micro": {k: _prf(*v) for k, v in sorted(cnt.items())},
            "by_level_info": {k: _prf(*v) for k, v in sorted(lvl.items())},
            "labels_outside_taxonomy": dict(sorted(outside.items(), key=lambda kv: -kv[1]))}
