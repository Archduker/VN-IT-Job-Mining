"""SD3 giai đoạn 1b: trực quan PCA 2D/3D của không gian vector theo 4 bộ trọng số khối, và chọn trọng số.

Chỉ đọc file local (Silver, features, e5, job_skills theo mining/config.py). Ghi docs/presentation/weight_views.html.
Tô màu theo 7 nhóm (mining/job_group.py) ở chế độ "Toàn bộ", theo vai trò con (từ khóa tiêu đề) trong từng nhóm.

Luật chọn (đặt trước khi xem hình, người dùng duyệt 24/11): bộ có độ đúng kNN vai trò con trung bình cao nhất;
chênh với bộ hiện tại dưới 0,02 thì giữ bộ hiện tại; một nhóm chỉ dùng bộ riêng khi hơn bộ chung >= 0,05.

    python scripts/plot_weight_views.py [--out docs/presentation/weight_views.html]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.neighbors import KNeighborsClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mining.clustering import build_block_space, reduce_svd  # noqa: E402
from mining.config import (DEFAULT_E5, DEFAULT_ENCODING_DICT, DEFAULT_FEATURES, DEFAULT_JOB_SKILLS,  # noqa: E402
                           DEFAULT_TABLE, RANDOM_STATE)
from mining.data_io import load_e5, load_mining_data  # noqa: E402
from mining.job_group import GROUPS, OTHER, add_job_group  # noqa: E402

OUT = ROOT / "docs" / "presentation" / "weight_views.html"
PLOTLY = "https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js"
CURRENT = "0,15 / 0,15 / 0,70 (hiện tại)"
WEIGHTS = {CURRENT: (0.15, 0.15, 0.70), "1/3 mỗi khối": (1 / 3, 1 / 3, 1 / 3),
           "0,5 / 0,5 / 0 (bỏ e5)": (0.5, 0.5, 0.0), "chỉ e5": (0.0, 0.0, 1.0)}
MIN_TOOLS, MIN_ROLE_N, KNN_K = 2, 10, 15
GAIN_KEEP, GAIN_GROUP = 0.02, 0.05


def knn_acc(Z: np.ndarray, y: np.ndarray) -> float:
    cv = StratifiedKFold(5, shuffle=True, random_state=RANDOM_STATE)
    return float(cross_val_score(KNeighborsClassifier(KNN_K, metric="cosine"), Z, y, cv=cv).mean())


def role_accs(Z: np.ndarray, groups: np.ndarray, roles: pd.Series) -> dict[str, float | None]:
    """Độ đúng kNN của vai trò con trong từng nhóm (chỉ tin khớp tiêu đề, vai trò >= MIN_ROLE_N tin)."""
    out = {}
    for g in GROUPS:
        r = roles[groups == g]
        ok = r.notna() & r.map(r.value_counts()).ge(MIN_ROLE_N)
        out[g] = round(knn_acc(Z[groups == g][ok.to_numpy()], r[ok].to_numpy()), 3) if r[ok].nunique() >= 2 else None
    return out


def compute() -> dict:
    d = load_mining_data(DEFAULT_TABLE, DEFAULT_FEATURES, DEFAULT_ENCODING_DICT, None, DEFAULT_JOB_SKILLS)
    meta = add_job_group(d.meta, d.skills)
    keep = (pd.to_numeric(meta["n_tools"], errors="coerce").fillna(0) >= MIN_TOOLS).to_numpy()
    m = meta[keep].reset_index(drop=True)
    S = d.skills.to_numpy(np.float32)[keep]
    C = d.concepts.to_numpy(np.float32)[keep]
    E = load_e5(DEFAULT_E5, meta["job_id"])[keep]
    g = m["job_group"].to_numpy()
    known = g != OTHER
    res = {"n": int(keep.sum()), "titles": m["job_title"].astype(str).str.slice(0, 70).tolist(),
           "group": g.tolist(), "role": m["sub_role_title"].fillna("không khớp tiêu đề").tolist(), "weights": {}}
    for name, w in WEIGHTS.items():
        X = build_block_space([b for b in ((S, w[0]), (C, w[1]), (E, w[2])) if b[1] > 0])
        Z, _ = reduce_svd(X, 0.80, 60, RANDOM_STATE)
        pca = PCA(3, random_state=RANDOM_STATE).fit(Z)
        views = {"Toàn bộ": {"idx": list(range(len(Z))), "xyz": pca.transform(Z).round(3).tolist(),
                             "var": round(float(pca.explained_variance_ratio_.sum()), 3)}}
        for grp in GROUPS:
            idx = np.flatnonzero(g == grp)
            p = PCA(3, random_state=RANDOM_STATE).fit(Z[idx])
            views[grp] = {"idx": idx.tolist(), "xyz": p.transform(Z[idx]).round(3).tolist(),
                          "var": round(float(p.explained_variance_ratio_.sum()), 3)}
        ra = role_accs(Z, g, m["sub_role_title"])
        vals = [v for v in ra.values() if v is not None]
        res["weights"][name] = {
            "w": w, "views": views, "role_acc": ra, "role_acc_mean": round(float(np.mean(vals)), 3),
            "group_acc": round(knn_acc(Z[known], g[known]), 3),
            "group_silhouette": round(float(silhouette_score(Z[known], g[known], metric="cosine", sample_size=2500,
                                                             random_state=RANDOM_STATE)), 3)}
    res["choice"] = choose(res["weights"])
    return res


def choose(ws: dict) -> dict:
    best = max(ws, key=lambda k: ws[k]["role_acc_mean"])
    common = best if ws[best]["role_acc_mean"] - ws[CURRENT]["role_acc_mean"] >= GAIN_KEEP else CURRENT
    per_group = {}
    for grp in GROUPS:
        base = ws[common]["role_acc"][grp]
        cand = max(ws, key=lambda k: ws[k]["role_acc"][grp] or -1)
        if base is not None and ws[cand]["role_acc"][grp] - base >= GAIN_GROUP:
            per_group[grp] = cand
    return {"common": common, "per_group": per_group,
            "rule": f"kNN vai trò con trung bình cao nhất; chênh < {GAIN_KEEP} thì giữ bộ hiện tại; "
                    f"nhóm dùng bộ riêng khi hơn >= {GAIN_GROUP}"}


PAGE = """<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Trọng số phân cụm</title><script src="__PLOTLY__"></script>
<style>body{font-family:system-ui,sans-serif;margin:16px;color:#1f2328;background:#fff;max-width:1200px}
table{border-collapse:collapse;font-size:13px;margin:8px 0 16px}td,th{border:1px solid #d0d7de;padding:4px 8px;text-align:right}
th:first-child,td:first-child{text-align:left}.pick{background:#dafbe1;font-weight:600}
.bar{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:8px 0}select,button{font-size:14px;padding:4px 8px}
#g{height:640px}p.note{color:#57606a;font-size:13px}</style>
<h1>Trực quan không gian phân cụm theo trọng số khối</h1>
<p class="note">__N__ tin có từ 2 công cụ. Trọng số: công cụ / khái niệm / e5. PCA trên không gian SVD dùng để phân cụm.
"Độ đúng kNN": lấy 15 tin gần nhất (cosine) rồi đoán nhãn theo đa số, kiểm chéo 5 phần; càng cao thì nhãn càng tách nhau trong không gian.</p>
<div id="t"></div>
<p><b>Chọn theo luật:</b> <span id="c"></span></p>
<div class="bar"><label>Trọng số <select id="w"></select></label><label>Xem <select id="v"></select></label>
<button id="d">2D / 3D</button><span id="info" class="note"></span></div><div id="g"></div>
<script>const D=__DATA__;let dim=3;const W=Object.keys(D.weights),V=Object.keys(D.weights[W[0]].views);
const ws=document.getElementById('w'),vs=document.getElementById('v');
W.forEach(k=>ws.add(new Option(k,k)));V.forEach(k=>vs.add(new Option(k,k)));
const G=Object.keys(D.weights[W[0]].role_acc);
let h='<table><tr><th>Bộ trọng số</th><th>kNN 7 nhóm</th><th>Silhouette 7 nhóm</th><th>kNN vai trò con TB</th>'+G.map(g=>'<th>'+g+'</th>').join('')+'</tr>';
W.forEach(k=>{const r=D.weights[k];h+='<tr class="'+(k==D.choice.common?'pick':'')+'"><td>'+k+'</td><td>'+r.group_acc+'</td><td>'+r.group_silhouette+'</td><td>'+r.role_acc_mean+'</td>'+G.map(g=>'<td>'+(r.role_acc[g]??'–')+'</td>').join('')+'</tr>'});
document.getElementById('t').innerHTML=h+'</table>';
const pg=Object.entries(D.choice.per_group).map(([g,k])=>g+' → '+k).join('; ');
document.getElementById('c').textContent=D.choice.common+(pg?' · riêng: '+pg:' · không nhóm nào cần bộ riêng')+' ('+D.choice.rule+')';
function draw(){const view=D.weights[ws.value].views[vs.value],lab=vs.value=='Toàn bộ'?D.group:D.role,by={};
view.idx.forEach((i,j)=>{const c=lab[i];(by[c]=by[c]||{x:[],y:[],z:[],t:[]});const p=view.xyz[j];by[c].x.push(p[0]);by[c].y.push(p[1]);by[c].z.push(p[2]);by[c].t.push(D.titles[i])});
const tr=Object.entries(by).sort((a,b)=>b[1].x.length-a[1].x.length).map(([c,s])=>({type:dim==3?'scatter3d':'scattergl',mode:'markers',name:c+' ('+s.x.length+')',x:s.x,y:s.y,z:dim==3?s.z:undefined,text:s.t,
hovertemplate:'%{text}<extra>'+c+'</extra>',marker:{size:dim==3?2.5:4,opacity:c=='Khác'||c=='không khớp tiêu đề'?0.35:0.8}}));
document.getElementById('info').textContent='PCA 3 trục giữ '+Math.round(view.var*100)+'% phương sai';
Plotly.react('g',tr,{margin:{l:0,r:0,t:10,b:0},legend:{font:{size:11}},scene:{xaxis:{title:'PC1'},yaxis:{title:'PC2'},zaxis:{title:'PC3'}},xaxis:{title:'PC1'},yaxis:{title:'PC2'}},{responsive:true})}
ws.onchange=draw;vs.onchange=draw;document.getElementById('d').onclick=()=>{dim=dim==3?2:3;draw()};draw();</script></html>"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    res = compute()
    html = (PAGE.replace("__PLOTLY__", PLOTLY).replace("__N__", f"{res['n']:,}".replace(",", "."))
            .replace("__DATA__", json.dumps(res, ensure_ascii=False, separators=(",", ":"))))
    a.out.write_text(html, encoding="utf-8")
    for k, r in res["weights"].items():
        print(f"{k:32s} kNN7={r['group_acc']} sil7={r['group_silhouette']} vai_trò_TB={r['role_acc_mean']} {r['role_acc']}")
    print("Chọn:", res["choice"])
    print("->", a.out)


if __name__ == "__main__":
    main()
