"""Trực quan hóa đầu vào của Mining (10_features + 04_normalization + e5) thành 1 HTML. Chỉ đọc file local.

    python scripts/plot_mining_input.py [--out docs/presentation/mining_input.html]
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FEATS = ROOT / "data" / "processing" / "10_features" / "features.parquet"
META = ROOT / "data" / "preprocessing" / "04_normalization" / "all.parquet"
E5 = ROOT / "data" / "processing" / "12_e5" / "job_emb.npz"
OUT = ROOT / "docs" / "presentation" / "mining_input.html"
PLOTLY = "https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js"
SENIORITY = {-1: "Chưa rõ", 0: "Intern/Fresher", 1: "Junior", 2: "Middle", 3: "Senior", 4: "Lead/Manager"}


def summarize(feats: pd.DataFrame, meta: pd.DataFrame) -> dict:
    cols = [c for c in feats.columns if c.startswith("skill__") and c != "skill__other_skill"]
    S = feats[cols].to_numpy()
    top = sorted(((c[7:], int(S[:, i].sum())) for i, c in enumerate(cols)), key=lambda x: -x[1])
    n = len(feats)
    comp = [["Lương", int(feats["salary_mid"].notna().sum())], ["Kinh nghiệm", int((feats["exp_min_years__missing"] == 0).sum())],
            ["Cấp bậc", int((feats["seniority_ord"] >= 0).sum())], ["Tỉnh", int((feats["tinh__unknown"] == 0).sum())],
            ["Có kỹ năng", int((S.sum(1) > 0).sum())]]
    m = meta.set_index("job_id_global").reindex(feats["job_id_global"])
    return {"n_jobs": n, "n_skill_cols": len(cols), "density": float(S.mean()), "zero_skill_jobs": int((S.sum(1) == 0).sum()),
            "top_skills": [list(t) for t in top], "completeness": comp,
            "families": [[k, int(v)] for k, v in m["job_family"].fillna("Other").value_counts().items()],
            "sources": [[k, int(v)] for k, v in m["source_platform"].value_counts().items()],
            "n_skills_hist": {int(k): int(v) for k, v in feats["n_skills"].value_counts().sort_index().items()},
            "salary_mid": feats["salary_mid"].dropna().round(2).tolist(),
            "seniority": [[SENIORITY[int(k)], int(v)] for k, v in feats["seniority_ord"].value_counts().sort_index().items()]}


def cooccurrence(feats: pd.DataFrame, top: list[list]) -> tuple[list[str], list[list[float]]]:
    names = [t[0] for t in top[:15]]
    S = feats[[f"skill__{n}" for n in names]].to_numpy().astype(float)
    inter = S.T @ S
    cnt = np.diag(inter)
    jac = inter / (cnt[:, None] + cnt[None, :] - inter)
    return names, np.round(jac, 3).tolist()


def pca2(emb_all: np.ndarray) -> np.ndarray:
    X = emb_all - emb_all.mean(0)
    _, _, vt = np.linalg.svd(X, full_matrices=False)
    return X @ vt[:2].T


PAGE = """<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Đầu vào Mining</title><script src="%(plotly)s"></script>
<style>
:root{--bg:#f9f9f7;--surf:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--grid:#e1e0d9;--b:#2a78d6;--c:#c3c2b7}
@media(prefers-color-scheme:dark){:root{--bg:#0d0d0d;--surf:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--grid:#2c2c2a;--b:#3987e5;--c:#383835}}
body{margin:0;background:var(--bg);color:var(--ink);font:14px system-ui,sans-serif;padding:16px}
h1{font-size:20px;margin:0 0 4px}p.s{color:var(--ink2);margin:0 0 16px}
.k{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin-bottom:12px}
.k div{background:var(--surf);padding:10px 12px;border-radius:8px}.k b{display:block;font-size:22px}.k span{color:var(--ink2);font-size:12px}
.g{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%%,480px),1fr));gap:12px}
.c{background:var(--surf);border-radius:8px;padding:8px;min-width:0;overflow:hidden}.c h2{font-size:14px;margin:6px 8px 0}.c small{display:block;color:var(--ink2);margin:0 8px}
</style>
<h1>Đầu vào của Mining</h1><p class="s">%(n)s tin IT, lấy từ 10_features, 04_normalization và 12_e5 (chạy thật, không mock).</p>
<div class="k" id="k"></div><div class="g" id="g"></div>
<script>
const D=%(data)s;const css=getComputedStyle(document.documentElement);const v=n=>css.getPropertyValue(n).trim();
const BLUE=v('--b'),INK=v('--ink'),INK2=v('--ink2'),GRID=v('--grid');
const CAT=['#2a78d6','#eb6834','#1baf7a','#eda100','#e87ba4','#008300','#6250d6'],OTHER='#898781';
const fmt=x=>x.toLocaleString('vi-VN');
document.getElementById('k').innerHTML=[[fmt(D.n_jobs),'tin IT'],[D.n_skill_cols,'cột kỹ năng'],[(D.density*100).toFixed(1)+'%%','mật độ ma trận kỹ năng'],
 [fmt(D.zero_skill_jobs),'tin không có kỹ năng'],[fmt(D.salary_mid.length),'tin có lương']].map(a=>'<div><b>'+a[0]+'</b><span>'+a[1]+'</span></div>').join('');
function add(title,sub,traces,layout){const c=document.createElement('div');c.className='c';c.innerHTML='<h2>'+title+'</h2><small>'+sub+'</small><div></div>';
 document.getElementById('g').appendChild(c);
 Plotly.newPlot(c.lastChild,traces,Object.assign({height:340,margin:{l:130,r:16,t:8,b:40},paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',
 font:{color:INK2,size:12},xaxis:{gridcolor:GRID,zerolinecolor:GRID},yaxis:{gridcolor:GRID},showlegend:false},layout||{}),{responsive:true,displayModeBar:false});}
const hbar=(a,color)=>[{type:'bar',orientation:'h',y:a.map(x=>x[0]).reverse(),x:a.map(x=>x[1]).reverse(),marker:{color:color||BLUE},hovertemplate:'%%{y}: %%{x}<extra></extra>'}];
add('Độ đầy đủ của trường chính','số tin có giá trị / '+fmt(D.n_jobs)+' (Lương = có cả min và max)',hbar(D.completeness));
add('20 kỹ năng phổ biến nhất','số tin nhắc tới',hbar(D.top_skills.slice(0,20)),{height:520});
add('Số kỹ năng mỗi tin','số tin theo số kỹ năng tìm thấy (0 = không có)',[{type:'bar',x:Object.keys(D.n_skills_hist).map(Number),y:Object.values(D.n_skills_hist),marker:{color:BLUE}}],{margin:{l:50,r:16,t:8,b:40}});
add('Nhóm nghề','số tin (Other = chưa xếp được nhóm)',hbar(D.families),{height:520});
add('Sàn tuyển dụng','số tin',hbar(D.sources));
add('Cấp bậc','số tin',[{type:'bar',x:D.seniority.map(x=>x[0]),y:D.seniority.map(x=>x[1]),marker:{color:BLUE}}],{margin:{l:50,r:16,t:8,b:60}});
add('Lương trung bình khoảng (triệu VNĐ/tháng)','chỉ tin có lương; cắt hiển thị tại 150',[{type:'histogram',x:D.salary_mid.filter(x=>x<=150),xbins:{size:5},marker:{color:BLUE}}],{margin:{l:50,r:16,t:8,b:40}});
add('Kỹ năng đi cùng nhau (Jaccard, 15 kỹ năng đầu)','càng đậm càng hay xuất hiện chung',[{type:'heatmap',x:D.co.names,y:D.co.names,z:D.co.z,colorscale:[[0,v('--surf')],[1,BLUE]],hovertemplate:'%%{x} + %%{y}: %%{z}<extra></extra>'}],{height:480,margin:{l:110,r:16,t:8,b:100}});
const fams=D.families.slice(0,7).map(f=>f[0]),by={};D.pca.fam.forEach((f,i)=>{const k=fams.includes(f)?f:'Khác';(by[k]=by[k]||[]).push(i)});
add('Không gian vector e5 của JD (PCA 2D)','mỗi điểm một tin, màu theo 7 nhóm nghề lớn nhất; hai chiều chỉ giữ một phần phương sai',
 Object.keys(by).map(k=>({type:'scattergl',mode:'markers',name:k,x:by[k].map(i=>D.pca.x[i]),y:by[k].map(i=>D.pca.y[i]),
 marker:{size:3,opacity:.6,color:k==='Khác'?OTHER:CAT[fams.indexOf(k)]}})),{showlegend:true,margin:{l:40,r:16,t:8,b:40},height:420,legend:{orientation:'h',y:-.15}});
window.addEventListener('load',()=>document.querySelectorAll('.c > div').forEach(d=>Plotly.Plots.resize(d)));
</script>"""


def build(out: Path) -> int:
    for f in (FEATS, META, E5):
        if not f.exists():
            raise FileNotFoundError(f"Thiếu {f}; chạy run_preprocessing.py các bước 04, 10_features, 12_e5 trước.")
    feats, meta = pd.read_parquet(FEATS), pd.read_parquet(META, columns=["job_id_global", "job_family", "source_platform"])
    s = summarize(feats, meta)
    names, z = cooccurrence(feats, s["top_skills"])
    s["co"] = {"names": names, "z": z}
    zf = np.load(E5, allow_pickle=True)
    pos = {str(j): i for i, j in enumerate(zf["ids"])}
    emb = zf["all"][[pos[str(j)] for j in feats["job_id_global"]]].astype(np.float32)
    xy = pca2(emb)
    fam = meta.set_index("job_id_global").reindex(feats["job_id_global"])["job_family"].fillna("Other")
    s["pca"] = {"x": xy[:, 0].round(4).tolist(), "y": xy[:, 1].round(4).tolist(), "fam": fam.tolist()}
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(PAGE % {"plotly": PLOTLY, "n": f"{s['n_jobs']:,}".replace(",", "."),
                                 "data": json.dumps(s, ensure_ascii=False)}, encoding="utf-8")
    return s["n_jobs"]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    print(f"Đã vẽ {build(ap.parse_args().out)} tin -> {ap.parse_args().out}")
