"""HTML trực quan hóa ĐẦU VÀO của Processing (bảng 04_normalization + 07/08 + báo cáo từng bước). Chỉ đọc file local.

    python scripts/plot_processing_input.py [--out docs/presentation/processing_input.html]
"""

import argparse
import html
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P04 = ROOT / "data" / "preprocessing" / "04_normalization" / "all.parquet"
P07 = ROOT / "data" / "processing" / "07_sections" / "all.parquet"
P08 = ROOT / "data" / "processing" / "08_skills" / "job_skills.parquet"
REP = ROOT / "reports" / "preprocessing"
OUT = ROOT / "docs" / "presentation" / "processing_input.html"
PLOTLY = "https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js"
STEPS = ["01_clean", "01b_deduplication", "02_integration", "03_transformation", "04_normalization"]


def _empty_list(s: pd.Series) -> pd.Series:
    return s.map(lambda v: v is None or len(v) == 0)


def _empty_text(s: pd.Series) -> pd.Series:
    return s.isna() | (s.fillna("").astype(str).str.strip() == "")


def missing_flags(df: pd.DataFrame) -> dict[str, pd.Series]:
    return {
        "Lương (đủ min và max)": df["salary_min_vnd"].isna() | df["salary_max_vnd"].isna(),
        "Số người tuyển": df["headcount"].isna(), "Ngày đăng": df["posted_date"].isna(), "Hạn nộp": df["deadline_date"].isna(),
        "Kinh nghiệm": df["exp_min_years"].isna(), "Cấp bậc": df["seniority"].isna(), "Tỉnh": df["tinh_chinh"].isna(),
        "Loại hình việc làm": df["raw_employment_type"].isna(), "Mô tả": _empty_text(df["description_clean"]),
        "Yêu cầu": _empty_text(df["requirements_clean"]), "Kỹ năng": _empty_list(df["skills_std"]),
        "Phúc lợi": _empty_list(df["benefits_std"]), "Nhóm nghề Other": df["job_family"] == "Other",
    }


def summarize(df: pd.DataFrame, bullets: pd.DataFrame, skills: pd.DataFrame) -> dict:
    flags = missing_flags(df)
    src = df["source_platform"]
    order = src.value_counts().index.tolist() if len(df) > 2 else sorted(src.unique())
    order = sorted(order, key=lambda x: (-int((src == x).sum()), x))
    missing = sorted(([k, int(v.sum())] for k, v in flags.items()), key=lambda x: -x[1])
    by_source = {k: [round(100 * float(v[src == s].mean()), 1) for s in order] for k, v in flags.items()}

    def per_job(frame):
        c = frame["job_id_global"].value_counts().reindex(df["job_id_global"]).fillna(0).astype(int)
        return {int(k): int(v) for k, v in c.value_counts().sort_index().items()}

    return {"n_jobs": len(df), "sources": order, "missing": missing, "by_source": by_source,
            "language": {k: int(v) for k, v in df["language"].value_counts().items()},
            "translation": {k: int(v) for k, v in df["translation_status"].value_counts().items()},
            "desc_len": df["description_clean"].fillna("").str.len().clip(upper=6000).tolist(),
            "bullets_per_job": per_job(bullets), "skills_per_job": per_job(skills)}


def funnel() -> tuple[list[list], list[list]]:
    steps, drops = [], []
    for i, s in enumerate(STEPS):
        j = json.loads((REP / s / "_all.json").read_text(encoding="utf-8"))
        if i == 0:
            steps.append(["Thu thập (đầu vào 01_clean)", j["input"]["rows"]])
            drops = [[f"{d['rule']}: {d['reason'][:38]}{'…' if len(d['reason']) > 38 else ''}", d["rows"]] for d in j["dropped"] if d["rows"]]
        steps.append([s, j["output"]["rows"]])
    return steps, sorted(drops, key=lambda x: -x[1])


def evidence(df: pd.DataFrame, n: int = 6) -> list[dict]:
    cols = ["raw_salary_text", "raw_experience_text", "raw_seniority_text", "raw_location_text"]
    d = df.dropna(subset=cols[:2]).sample(n=min(n, len(df)), random_state=42)
    rows = []
    for _, r in d.iterrows():
        sal = "—" if pd.isna(r["salary_min_vnd"]) and pd.isna(r["salary_max_vnd"]) else \
            f"{r['salary_min_vnd'] / 1e6 if pd.notna(r['salary_min_vnd']) else '?'} – {r['salary_max_vnd'] / 1e6 if pd.notna(r['salary_max_vnd']) else '?'} triệu"
        exp = f"{r['exp_min_years'] if pd.notna(r['exp_min_years']) else '?'} – {r['exp_max_years'] if pd.notna(r['exp_max_years']) else '?'} năm"
        rows.append({"id": f"{r['source_platform']}_{r['source_job_id']}", "title": r["job_title"], "salary_raw": r["raw_salary_text"],
                     "salary": sal, "exp_raw": r["raw_experience_text"], "exp": exp, "seniority_raw": r["raw_seniority_text"],
                     "seniority": r["seniority"], "loc_raw": r["raw_location_text"], "tinh": r["tinh_chinh"], "family": r["job_family"]})
    return rows


def _table(ev: list[dict]) -> str:
    h = ["Tin", "Tiêu đề", "Lương gốc → chuẩn hóa", "Kinh nghiệm gốc → chuẩn hóa", "Cấp bậc gốc → chuẩn hóa", "Địa điểm gốc → tỉnh", "Nhóm nghề"]
    e = lambda x: html.escape("" if x is None or (isinstance(x, float) and np.isnan(x)) else str(x))  # noqa: E731
    body = "".join(
        f"<tr><td>{e(r['id'])}</td><td>{e(r['title'])}</td><td>{e(r['salary_raw'])} → <b>{e(r['salary'])}</b></td>"
        f"<td>{e(r['exp_raw'])} → <b>{e(r['exp'])}</b></td><td>{e(r['seniority_raw'])} → <b>{e(r['seniority'])}</b></td>"
        f"<td>{e(r['loc_raw'])} → <b>{e(r['tinh'])}</b></td><td>{e(r['family'])}</td></tr>" for r in ev)
    return "<table><tr>" + "".join(f"<th>{x}</th>" for x in h) + "</tr>" + body + "</table>"


PAGE = """<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Đầu vào Processing</title><script src="%(plotly)s"></script>
<style>
:root{--bg:#f9f9f7;--surf:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--grid:#e1e0d9;--b:#2a78d6;--o:#eb6834}
@media(prefers-color-scheme:dark){:root{--bg:#0d0d0d;--surf:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--grid:#2c2c2a;--b:#3987e5;--o:#d95926}}
body{margin:0;background:var(--bg);color:var(--ink);font:14px system-ui,sans-serif;padding:16px}
h1{font-size:20px;margin:0 0 4px}p.s{color:var(--ink2);margin:0 0 16px}
.k{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin-bottom:12px}
.k div{background:var(--surf);padding:10px 12px;border-radius:8px}.k b{display:block;font-size:22px}.k span{color:var(--ink2);font-size:12px}
.g{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%%,480px),1fr));gap:12px}
.c{background:var(--surf);border-radius:8px;padding:8px;min-width:0;overflow:hidden}.c h2{font-size:14px;margin:6px 8px 0}.c small{display:block;color:var(--ink2);margin:0 8px}
.w{grid-column:1/-1}.t{overflow-x:auto}table{border-collapse:collapse;font-size:12px;width:100%%}
th,td{border-bottom:1px solid var(--grid);padding:6px 8px;text-align:left;vertical-align:top}th{color:var(--ink2)}
</style>
<h1>Đầu vào của Processing</h1><p class="s">%(n)s tin sau Pre-processing (04_normalization), cộng bullet (07) và kỹ năng (08). Số thật, lấy từ bảng và báo cáo từng bước.</p>
<div class="k" id="k"></div><div class="g" id="g"></div>
<div class="c w" style="margin-top:12px"><h2>Minh chứng: dòng thật trước và sau chuẩn hóa (mẫu ngẫu nhiên, seed 42)</h2>
<small>mỗi ô: giá trị gốc từ sàn → giá trị sau Pre-processing</small><div class="t">%(table)s</div></div>
<script>
const D=%(data)s;const css=getComputedStyle(document.documentElement);const v=n=>css.getPropertyValue(n).trim();
const BLUE=v('--b'),ORG=v('--o'),INK2=v('--ink2'),GRID=v('--grid');const fmt=x=>x.toLocaleString('vi-VN');
document.getElementById('k').innerHTML=[[fmt(D.n_jobs),'tin vào Processing'],[D.sources.length,'sàn tuyển dụng'],
 [fmt(D.funnel[0][1]),'tin thu thập ban đầu'],[(100*D.funnel[5][1]/D.funnel[0][1]).toFixed(1)+'%%','giữ lại sau Pre-processing']].map(a=>'<div><b>'+a[0]+'</b><span>'+a[1]+'</span></div>').join('');
function add(title,sub,traces,layout,wide){const c=document.createElement('div');c.className='c'+(wide?' w':'');c.innerHTML='<h2>'+title+'</h2><small>'+sub+'</small><div></div>';
 document.getElementById('g').appendChild(c);
 Plotly.newPlot(c.lastChild,traces,Object.assign({height:340,margin:{l:150,r:16,t:8,b:40},paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',
 font:{color:INK2,size:12},xaxis:{gridcolor:GRID,automargin:true},yaxis:{gridcolor:GRID,automargin:true},showlegend:false},layout||{}),{responsive:true,displayModeBar:false});}
const hbar=(a,color)=>[{type:'bar',orientation:'h',y:a.map(x=>x[0]).reverse(),x:a.map(x=>x[1]).reverse(),marker:{color:color||BLUE},hovertemplate:'%%{y}: %%{x}<extra></extra>'}];
add('Phễu: từ thu thập đến đầu vào Processing','số tin còn lại sau mỗi bước (báo cáo từng bước)',hbar(D.funnel),{margin:{l:120,r:16,t:8,b:40}});
add('Lý do bị loại ở bước 01_clean','số tin bị loại theo từng luật',hbar(D.drops,ORG),{margin:{l:120,r:16,t:8,b:40}});
add('Số tin thiếu theo trường','trên %(n)s tin; thiếu = null, rỗng hoặc (Nhóm nghề) là Other',hbar(D.missing),{height:480});
add('Tỷ lệ thiếu theo sàn (%%)','đậm = thiếu nhiều; mỗi ô là phần trăm tin của sàn đó',[{type:'heatmap',x:D.sources,y:Object.keys(D.by_source),z:Object.values(D.by_source),
 text:Object.values(D.by_source).map(r=>r.map(x=>x.toFixed(0))),texttemplate:'%%{text}',colorscale:[[0,v('--surf')],[1,BLUE]],zmin:0,zmax:100,hovertemplate:'%%{y} · %%{x}: %%{z}%%<extra></extra>'}],{height:480,margin:{l:150,r:16,t:8,b:60}});
add('Ngôn ngữ JD','số tin',hbar(Object.entries(D.language)));
add('Kết quả dịch EN→VI','not_needed = tiếng Việt; failed = dịch lỗi, giữ bản gốc',hbar(Object.entries(D.translation),ORG));
add('Độ dài mô tả (ký tự)','cắt hiển thị tại 6.000',[{type:'histogram',x:D.desc_len,xbins:{size:250},marker:{color:BLUE}}],{margin:{l:50,r:16,t:8,b:40}});
add('Số bullet mỗi tin (bước 07)','số tin theo số bullet',[{type:'bar',x:Object.keys(D.bullets_per_job).map(Number),y:Object.values(D.bullets_per_job),marker:{color:BLUE}}],{margin:{l:50,r:16,t:8,b:40}});
add('Số kỹ năng trích được mỗi tin (bước 08)','0 = không tìm thấy kỹ năng nào',[{type:'bar',x:Object.keys(D.skills_per_job).map(Number),y:Object.values(D.skills_per_job),marker:{color:BLUE}}],{margin:{l:50,r:16,t:8,b:40}});
window.addEventListener('load',()=>document.querySelectorAll('.c > div:not(.t)').forEach(d=>Plotly.Plots.resize(d)));
</script>"""


def build(out: Path) -> int:
    for f in (P04, P07, P08, REP / STEPS[0] / "_all.json"):
        if not f.exists():
            raise FileNotFoundError(f"Thiếu {f}; chạy run_preprocessing.py các bước đến 08 trước.")
    df = pd.read_parquet(P04)
    s = summarize(df, pd.read_parquet(P07, columns=["job_id_global"]), pd.read_parquet(P08, columns=["job_id_global"]))
    s["funnel"], s["drops"] = funnel()
    n = f"{s['n_jobs']:,}".replace(",", ".")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(PAGE % {"plotly": PLOTLY, "n": n, "data": json.dumps(s, ensure_ascii=False), "table": _table(evidence(df))},
                         encoding="utf-8")
    return s["n_jobs"]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    print(f"Đã vẽ {build(a.out)} tin -> {a.out}")
