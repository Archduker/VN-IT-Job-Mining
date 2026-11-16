"""Vẽ Elbow (inertia) và Silhouette theo k từ mining/artifacts/mining_metrics.json. Chỉ đọc file local.

    python scripts/plot_k_selection.py [--out docs/presentation/k_selection.html]
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "mining" / "artifacts" / "mining_metrics.json"
OUT = ROOT / "docs" / "presentation" / "k_selection.html"
PLOTLY = "https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js"

PAGE = """<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Chọn số cụm</title><script src="%(plotly)s"></script>
<style>
:root{--bg:#f9f9f7;--surf:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--grid:#e1e0d9;--b:#2a78d6;--o:#eb6834}
@media(prefers-color-scheme:dark){:root{--bg:#0d0d0d;--surf:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--grid:#2c2c2a;--b:#3987e5;--o:#d95926}}
body{margin:0;background:var(--bg);color:var(--ink);font:14px system-ui,sans-serif;padding:16px}
h1{font-size:20px;margin:0 0 4px}p{color:var(--ink2);margin:0 0 12px}
.g{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%%,460px),1fr));gap:12px}
.c{background:var(--surf);border-radius:8px;padding:8px;min-width:0;overflow:hidden}.c h2{font-size:14px;margin:6px 8px 0}
</style>
<h1>Chọn số cụm K-Means</h1><p>k đã chọn = %(best)s (đường đứt). Quét k = %(lo)s–%(hi)s trên 4.671 tin, số đo thật.</p><div class="g" id="g"></div>
<script>
const D=%(data)s;const css=getComputedStyle(document.documentElement);const v=n=>css.getPropertyValue(n).trim();
function add(title,ys,color,name){const c=document.createElement('div');c.className='c';c.innerHTML='<h2>'+title+'</h2><div></div>';document.getElementById('g').appendChild(c);
 Plotly.newPlot(c.lastChild,[{x:D.k,y:ys,mode:'lines+markers',line:{color:v(color),width:2},marker:{size:8},name:name,hovertemplate:'k=%%{x}: %%{y}<extra></extra>'}],
 {height:340,margin:{l:60,r:16,t:8,b:44},paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',font:{color:v('--ink2'),size:12},showlegend:false,
 xaxis:{title:'số cụm k',gridcolor:v('--grid'),dtick:1},yaxis:{gridcolor:v('--grid')},
 shapes:[{type:'line',x0:D.best,x1:D.best,y0:0,y1:1,yref:'paper',line:{color:v('--ink2'),dash:'dash',width:1}}]},{responsive:true,displayModeBar:false});}
add('Elbow: tổng bình phương khoảng cách trong cụm (inertia)',D.inertia,'--b');
add('Silhouette (càng cao càng tách; dữ liệu xáo ngẫu nhiên khoảng 0,04)',D.silhouette,'--o');
add('Davies-Bouldin (càng thấp càng tốt)',D.db,'--b');
window.addEventListener('load',()=>document.querySelectorAll('.c > div').forEach(d=>Plotly.Plots.resize(d)));
</script>"""


def build(src: Path, out: Path) -> int:
    src = Path(src)
    if not src.exists():
        raise FileNotFoundError(f"Thiếu {src}; chạy mining/run_mining_pipeline.py --only cluster trước.")
    c = json.loads(src.read_text(encoding="utf-8"))["clustering"]
    scan = c["k_scan"]
    d = {"k": [r["k"] for r in scan], "inertia": [round(r["inertia"], 1) for r in scan],
         "silhouette": [round(r["silhouette"], 4) for r in scan], "db": [round(r["davies_bouldin"], 3) for r in scan], "best": c["best_k"]}
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(PAGE % {"plotly": PLOTLY, "data": json.dumps(d), "best": c["best_k"],
                                 "lo": d["k"][0], "hi": d["k"][-1]}, encoding="utf-8")
    return len(scan)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=SRC)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    try:
        print(f"Đã vẽ {build(a.src, a.out)} giá trị k -> {a.out}")
    except FileNotFoundError as e:
        sys.exit(str(e))
