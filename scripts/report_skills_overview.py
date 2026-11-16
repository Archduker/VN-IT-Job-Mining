# -*- coding: utf-8 -*-
"""Báo cáo trực quan kỹ năng (bước V của plan 10–12). Chỉ đọc bảng 04, ghi một file HTML tĩnh.

So phương án A (chỉ văn bản gốc) với B (gốc + bản dịch) trên dữ liệu thật để người dùng chọn nguồn và min_df.
Chạy: .venv/bin/python scripts/report_skills_overview.py [--out data/processing/skills_overview.html]
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from processing.extraction import run as R  # noqa: E402
from processing.extraction import sections as S  # noqa: E402

CUTS = (5, 10, 15, 20, 50)


def _df_counts(per_job: list[set]) -> Counter:
    return Counter(s for slugs in per_job for s in slugs)


def build(df: pd.DataFrame) -> dict:
    matcher, headings, cues = R.default_matcher(), S.load_headings(), S.load_cues()
    a_jobs, b_jobs = [], []
    for rec in df.to_dict("records"):
        _, rows, _ = R.analyze(rec, matcher, headings, cues)
        a_jobs.append({r["slug"] for r in rows if r["via"] != "text_vi"})
        b_jobs.append({r["slug"] for r in rows})
    n = len(df)
    out = {"n_jobs": n, "n_translated": int((df["translation_status"] == "translated").sum())}
    for name, jobs in (("A", a_jobs), ("B", b_jobs)):
        dfc = _df_counts(jobs)
        total = sum(dfc.values())
        ranked = dfc.most_common()
        cum, run_sum = [], 0
        for _, c in ranked:
            run_sum += c
            cum.append(round(run_sum / total, 4))
        out[name] = {
            "df": dict(ranked), "mentions": total, "n_skills": len(dfc), "cum": cum,
            "jobs_no_skill": sum(1 for j in jobs if not j),
            "mean_per_job": round(total / n, 2),
            "cuts": {str(c): {"cols": sum(1 for v in dfc.values() if v >= c),
                              "jobs_lost_all": sum(1 for j in jobs if j and not any(dfc[s] >= c for s in j))}
                     for c in CUTS},
        }
    return out


def _bars(rows: list[tuple[str, int, int]], top: int = 40) -> str:
    mx = max((max(a, b) for _, a, b in rows[:top]), default=1)
    lines = []
    for slug, a, b in rows[:top]:
        lines.append(f"<tr><td>{html.escape(slug)}</td><td><div class=ba style='width:{a / mx * 100:.1f}%'></div>{a}</td>"
                     f"<td><div class=bb style='width:{b / mx * 100:.1f}%'></div>{b}</td><td>{b - a:+d}</td></tr>")
    return "".join(lines)


def render(m: dict) -> str:
    a, b = m["A"], m["B"]
    top = [(s, a["df"].get(s, 0), c) for s, c in b["df"].items()]
    diff = sorted(((s, a["df"].get(s, 0), c) for s, c in b["df"].items()), key=lambda t: -(t[2] - t[1]))[:15]
    cut_rows = "".join(
        f"<tr><td>{c}</td><td>{a['cuts'][str(c)]['cols']}</td><td>{a['cuts'][str(c)]['jobs_lost_all']}</td>"
        f"<td>{b['cuts'][str(c)]['cols']}</td><td>{b['cuts'][str(c)]['jobs_lost_all']}</td></tr>" for c in CUTS)
    cov = {k: next((i + 1 for i, v in enumerate(b["cum"]) if v >= k), len(b["cum"])) for k in (0.5, 0.8, 0.9)}
    return f"""<!doctype html><html lang=vi><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Tổng quan kỹ năng</title><style>
:root{{--bg:#fff;--fg:#1a1a1a;--mut:#666;--a:#8aa4c8;--b:#2f6f4f;--line:#ddd}}
@media(prefers-color-scheme:dark){{:root{{--bg:#161616;--fg:#eee;--mut:#aaa;--a:#5b7699;--b:#5fb88a;--line:#333}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui;margin:0 auto;max-width:900px;padding:16px}}
table{{border-collapse:collapse;width:100%;margin:8px 0 24px}}td,th{{border-bottom:1px solid var(--line);padding:4px 6px;text-align:left}}
.ba,.bb{{height:8px;border-radius:3px;margin-bottom:2px}}.ba{{background:var(--a)}}.bb{{background:var(--b)}}.mut{{color:var(--mut)}}
.wrap{{overflow-x:auto}}</style>
<h1>Tổng quan kỹ năng</h1>
<p class=mut>{m['n_jobs']} tin, trong đó {m['n_translated']} tin đã dịch. A = chỉ văn bản gốc, B = gốc + bản dịch. Số thật từ bảng 04.</p>
<table><tr><th></th><th>A</th><th>B</th></tr>
<tr><td>Số kỹ năng khác nhau</td><td>{a['n_skills']}</td><td>{b['n_skills']}</td></tr>
<tr><td>Lượt nhắc</td><td>{a['mentions']}</td><td>{b['mentions']}</td></tr>
<tr><td>Kỹ năng trung bình/tin</td><td>{a['mean_per_job']}</td><td>{b['mean_per_job']}</td></tr>
<tr><td>Tin không có kỹ năng nào</td><td>{a['jobs_no_skill']}</td><td>{b['jobs_no_skill']}</td></tr></table>
<h2>Mức cắt min_df</h2><p class=mut>Số cột còn lại và số tin mất hết kỹ năng.</p><div class=wrap><table>
<tr><th>min_df</th><th>A cột</th><th>A tin mất hết</th><th>B cột</th><th>B tin mất hết</th></tr>{cut_rows}</table></div>
<h2>Độ phủ (B)</h2><p>{cov[0.5]} kỹ năng phủ 50% lượt nhắc, {cov[0.8]} kỹ năng phủ 80%, {cov[0.9]} kỹ năng phủ 90%.</p>
<h2>Top 40 theo số tin (xanh nhạt = A, xanh đậm = B)</h2><div class=wrap><table>
<tr><th>Kỹ năng</th><th>A</th><th>B</th><th>B−A</th></tr>{_bars(top)}</table></div>
<h2>15 kỹ năng tăng nhiều nhất nhờ bản dịch</h2><div class=wrap><table>
<tr><th>Kỹ năng</th><th>A</th><th>B</th><th>B−A</th></tr>{_bars(diff, 15)}</table></div></html>"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, default=R.DEFAULT_INPUT)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "processing" / "skills_overview.html")
    args = ap.parse_args(argv)
    m = build(pd.read_parquet(args.input))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(m), encoding="utf-8")
    summary = {k: {kk: vv for kk, vv in m[k].items() if kk not in ("df", "cum")} for k in ("A", "B")}
    print(json.dumps({"n_jobs": m["n_jobs"], "n_translated": m["n_translated"], **summary}, ensure_ascii=False, indent=1))
    print("ghi", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
