#!/usr/bin/env python3
"""Đo ba góc nhìn kỹ năng theo ngưỡng T1–T6 (docs/target/06_yeu_cau_du_lieu.md mục 4). Chỉ đọc; ghi trên máy.

Đọc `data/processing/08_skills/job_skills.parquet` (phải có cột `type`, K8.17), bảng Silver, bullet bước 07 và dữ liệu
ngoài `data/external/vnjt/step07.jsonl` (chỉ để đối chiếu, xem `_vnjt.py`). View lấy đúng từ `skill_view`.

- T1 trung vị số kỹ năng/tin của tin người mới (Intern/Fresher, Junior) ≤ 10 (đo trên K-tool)
- T2 React ⇒ JavaScript hoặc TypeScript, confidence ≥ 0,6
- T3 số kỹ năng phủ ≥ 20% tin ở **cả** 6 nghề lớn = 0
- T4 đọc tay 100 cặp (tin, kỹ năng K-tool) ngẫu nhiên seed 42 ≥ 90% đúng → `tool_check_100.csv`
- T5 trên tin ghép với dữ liệu ngoài: tỷ lệ `tech_stack` của họ mình bắt được ≥ 0,85
- T6 tỷ lệ kỹ năng của mình nằm trong `tech_stack ∪ keywords` của họ ≥ 0,70
T5, T6 báo trên hai tập: ghép theo mã + tiêu đề (`_vnjt.match_jobs`) và tập con trùng nguyên URL (tập đo 19/11).
Thêm coverage@10 của tin người mới theo nghề (SD5).

    python scripts/eval_skill_views.py [--out-json ...] [--out-csv ...]
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import _vnjt as X  # noqa: E402
from processing.extraction.skills import load_skills_v2, matcher_from_v2, skill_view  # noqa: E402

JOB_SKILLS = ROOT / "data" / "processing" / "08_skills" / "job_skills.parquet"
SILVER = ROOT / "data" / "preprocessing" / "04_normalization" / "silver.parquet"
BULLETS = ROOT / "data" / "processing" / "07_sections" / "all.parquet"
OUT_DIR = ROOT / "data" / "processing" / "skill_candidates"
SEED = 42
NEWCOMER = ("Intern/Fresher", "Junior")
BIG_FAMILIES = ("Web", "Bridge", "Data/AI", "Tester", "DevOps/Cloud", "Security")
VIEWS = ("all", "technical", "tool", "concept", "soft")
THRESHOLDS = {"T1": 10, "T2": 0.6, "T3": 0, "T4": 0.9, "T5": 0.85, "T6": 0.70}


def view(js: pd.DataFrame, name: str) -> pd.DataFrame:
    return js[js["kind"] == "technical"] if name == "technical" else skill_view(js, name)


def sets_by_job(df: pd.DataFrame) -> dict:
    return df.groupby("job_id_global")["slug"].apply(set).to_dict()


def median_per_job(sets: dict, jobs) -> float:
    return float(pd.Series([len(sets.get(j, ())) for j in jobs]).median()) if len(jobs) else float("nan")


def confidence(sets: dict, lhs: str, rhs: set) -> tuple:
    has = [s for s in sets.values() if lhs in s]
    return (round(sum(bool(s & rhs) for s in has) / len(has), 3) if has else None), len(has)


def broad_skills(sets: dict, silver: pd.DataFrame, share: float = 0.2) -> list:
    fam = dict(zip(silver["job_id"], silver["job_family"]))
    cov = {}
    for f in BIG_FAMILIES:
        jobs = [j for j, x in fam.items() if x == f]
        c = Counter(s for j in jobs for s in sets.get(j, ()))
        cov[f] = {s for s, n in c.items() if n / max(1, len(jobs)) >= share}
    return sorted(set.intersection(*cov.values())) if cov else []


def coverage_at(sets: dict, silver: pd.DataFrame, n: int = 10, need: float = 0.7) -> dict:
    """Mỗi nghề lớn: tỷ lệ tin người mới mà top-n kỹ năng của nghề (đếm trên tin người mới) phủ ≥ need kỹ năng của tin."""
    out = {}
    new = silver[silver["seniority"].isin(NEWCOMER)]
    for f in BIG_FAMILIES:
        jobs = list(new.loc[new["job_family"] == f, "job_id"])
        c = Counter(s for j in jobs for s in sets.get(j, ()))
        top = {s for s, _ in c.most_common(n)}
        ok = [len(sets[j] & top) / len(sets[j]) >= need for j in jobs if sets.get(j)]
        out[f] = {"n_jobs": len(jobs), "share_ok": round(sum(ok) / len(ok), 3) if ok else None}
    return out


def ext_scores(sets: dict, ext_sets: dict, jobs) -> dict:
    """Micro: T5 = |mình ∩ ts| / |ts|; T6 = |mình ∩ (ts ∪ kw)| / |mình|."""
    hit_ts = n_ts = hit_any = n_ours = 0
    for j in jobs:
        ours, (ts, kw) = sets.get(j, set()), ext_sets[j]
        hit_ts += len(ours & ts)
        n_ts += len(ts)
        hit_any += len(ours & (ts | kw))
        n_ours += len(ours)
    return {"n_jobs": len(jobs), "T5_recall_tech_stack": round(hit_ts / n_ts, 3) if n_ts else None,
            "T6_in_their_lists": round(hit_any / n_ours, 3) if n_ours else None}


def sample_pairs(tool: pd.DataFrame, silver: pd.DataFrame, bullets: pd.DataFrame, matcher, k: int = 100) -> pd.DataFrame:
    """100 cặp (tin, kỹ năng K-tool) ngẫu nhiên, kèm câu chứa chỗ khớp để đọc tay. Cột `dung` để trống."""
    pairs = tool[["job_id_global", "slug", "skill", "via", "section"]].sort_values(["job_id_global", "slug"])
    pairs = pairs.reset_index(drop=True)
    idx = sorted(random.Random(SEED).sample(range(len(pairs)), min(k, len(pairs))))
    title = dict(zip(silver["job_id"], silver["title"]))
    by_job = {j: g for j, g in bullets.groupby("job_id_global")}
    rows = []
    for i in idx:
        r = pairs.iloc[i]
        ctx = "(thẻ kỹ năng của sàn)" if r["via"] == "meta" else ""
        if r["via"] == "text_vi":
            ctx = "(chỉ thấy trong bản dịch)"
        g = by_job.get(r["job_id_global"])
        if r["via"] == "text" and g is not None:
            for t in g["text"]:
                if any(h.slug == r["slug"] for h in matcher.find(t)):
                    ctx = t[:300]
                    break
        rows.append({"job_id": r["job_id_global"], "title": title.get(r["job_id_global"]), "slug": r["slug"],
                     "skill": r["skill"], "via": r["via"], "section": r["section"], "context": ctx, "dung": ""})
    return pd.DataFrame(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-json", default=str(OUT_DIR / "skill_views_eval.json"))
    ap.add_argument("--out-csv", default=str(OUT_DIR / "tool_check_100.csv"))
    a = ap.parse_args(argv)
    js = pd.read_parquet(JOB_SKILLS)
    silver = pd.read_parquet(SILVER)
    matcher = matcher_from_v2(load_skills_v2())
    matched = X.match_jobs(zip(silver["job_id"], silver["source"], silver["url"], silver["title"]), X.load_ext())
    exact = {j for j, x in matched.items() if x.get("job_url") == dict(zip(silver["job_id"], silver["url"]))[j]}
    ext_sets = X.ext_slug_sets(matched, matcher)
    newcomer = list(silver.loc[silver["seniority"].isin(NEWCOMER), "job_id"])

    res = {"n_jobs": len(silver), "n_newcomer": len(newcomer), "n_ext_matched": len(matched),
           "n_ext_exact_url": len(exact), "thresholds": THRESHOLDS, "views": {}}
    for name in VIEWS:
        sets = sets_by_job(view(js, name))
        res["views"][name] = {
            "n_rows": int(sum(len(s) for s in sets.values())), "n_slugs": len({x for s in sets.values() for x in s}),
            "jobs_with_any": len(sets), "median_per_job": median_per_job(sets, list(silver["job_id"])),
            "T1_median_newcomer": median_per_job(sets, newcomer),
            "T2_react_js_ts": confidence(sets, "react", {"javascript", "typescript"}),
            "flutter_dart": confidence(sets, "flutter", {"dart"}),
            "T3_broad_in_6_families": broad_skills(sets, silver),
            "T5_T6_matched": ext_scores(sets, ext_sets, list(matched)),
            "T5_T6_exact_url": ext_scores(sets, ext_sets, sorted(exact)),
            "coverage_at_10_newcomer": coverage_at(sets, silver),
            "top20": sorted(Counter(x for s in sets.values() for x in s).items(), key=lambda kv: (-kv[1], kv[0]))[:20],
        }
    tool = skill_view(js, "tool")
    sample = sample_pairs(tool, silver, pd.read_parquet(BULLETS), matcher)
    csv = Path(a.out_csv)
    read = pd.read_csv(csv) if csv.exists() else None
    if read is not None and "dung" in read and read["dung"].notna().any():   # đã đọc tay: không ghi đè
        if not read[["job_id", "slug"]].equals(sample[["job_id", "slug"]]):
            print(f"CẢNH BÁO: {csv.name} đã đọc tay nhưng mẫu mới khác (dữ liệu đổi); xóa file để lấy mẫu mới")
        ok = pd.to_numeric(read["dung"], errors="coerce")
        res["T4_manual"] = {"n": int(ok.notna().sum()), "share_ok": round(float(ok.mean()), 3)}
    else:
        csv.parent.mkdir(parents=True, exist_ok=True)
        sample.to_csv(csv, index=False, encoding="utf-8")
    Path(a.out_json).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    t = res["views"]["tool"]
    print(f"tin {res['n_jobs']}, người mới {res['n_newcomer']}, ghép ngoài {res['n_ext_matched']} "
          f"(trùng nguyên URL {res['n_ext_exact_url']})")
    for name in VIEWS:
        v = res["views"][name]
        print(f"{name:9} slug {v['n_slugs']:5} | trung vị/tin {v['median_per_job']:5} | T1 {v['T1_median_newcomer']:5} | "
              f"T2 {v['T2_react_js_ts'][0]} | T3 {len(v['T3_broad_in_6_families'])} | "
              f"T5/T6 ghép {v['T5_T6_matched']['T5_recall_tech_stack']}/{v['T5_T6_matched']['T6_in_their_lists']} | "
              f"URL {v['T5_T6_exact_url']['T5_recall_tech_stack']}/{v['T5_T6_exact_url']['T6_in_their_lists']}")
    print("K-tool T3:", t["T3_broad_in_6_families"])
    print("K-tool coverage@10 người mới:", {f: x["share_ok"] for f, x in t["coverage_at_10_newcomer"].items()})
    print("ghi", a.out_json, "và", a.out_csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
