"""Khung HTML tĩnh dùng chung cho các trang trực quan hóa trong docs/presentation/.

Dùng bởi scripts/visualize_raw_bronze.py và scripts/visualize_preprocessing_steps.py.
Biểu đồ vẽ bằng SVG thuần trong trình duyệt (vbars: cột dọc, hbars: thanh ngang), có tooltip và "Xem dạng bảng".
"""

from __future__ import annotations

import collections
import html
import json
from typing import Any, List

TOP_N = 15

CSS = """
:root{--surface:#fcfcfb;--surface-2:#f3f2ef;--border:#e4e2dc;--text:#0b0b0b;--text-2:#52514e;--muted:#7a7873;
--series-1:#2a78d6;--series-2:#eb6834;--series-3:#1baf7a;--grid:#e9e7e2;--accent:#2a78d6;--warn:#b35c00}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--surface:#1a1a19;--surface-2:#242422;--border:#3a3936;
--text:#f0efec;--text-2:#c3c2b7;--muted:#9a988f;--series-1:#3987e5;--series-2:#d95926;--series-3:#199e70;--grid:#2f2e2b;--accent:#3987e5;--warn:#f0a050}}
:root[data-theme="dark"]{--surface:#1a1a19;--surface-2:#242422;--border:#3a3936;--text:#f0efec;--text-2:#c3c2b7;--muted:#9a988f;
--series-1:#3987e5;--series-2:#d95926;--series-3:#199e70;--grid:#2f2e2b;--accent:#3987e5;--warn:#f0a050}
*{box-sizing:border-box}body{margin:0;background:var(--surface);color:var(--text);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:1080px;margin:0 auto;padding:24px 16px 64px}h1{font-size:26px;margin:0 0 4px}h2{font-size:18px;margin:36px 0 4px}
.sub{color:var(--text-2);margin:0 0 16px}.note{color:var(--muted);font-size:13px;margin:4px 0 12px}
nav{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 20px}nav a{padding:4px 10px;border:1px solid var(--border);border-radius:999px;color:var(--text-2);text-decoration:none;font-size:13px}
nav a.on{background:var(--accent);border-color:var(--accent);color:#fff}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.tile{background:var(--surface-2);border:1px solid var(--border);border-radius:10px;padding:12px 14px}
.tile .v{font-size:24px;font-weight:650;font-variant-numeric:tabular-nums}.tile .k{color:var(--text-2);font-size:13px}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,460px),1fr));gap:20px}
.card{border:1px solid var(--border);border-radius:10px;padding:14px;background:var(--surface);min-width:0}
.card h3{font-size:15px;margin:0 0 2px}svg{display:block;width:100%;height:auto;overflow:visible}
svg text{fill:var(--text-2);font-size:11px}svg .val{fill:var(--text);font-variant-numeric:tabular-nums}
.bar{fill:var(--series-1)}.bar:hover,.bar.hl{opacity:.8}.gridline{stroke:var(--grid)}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--border);vertical-align:top}
th{color:var(--text-2);font-weight:600}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.scroll{overflow-x:auto}.tbox{max-height:520px;overflow:auto}.samp{color:var(--text-2);word-break:break-word}
.meter{display:inline-block;width:70px;height:6px;background:var(--grid);border-radius:3px;vertical-align:middle;margin-right:6px}
.meter i{display:block;height:100%;background:var(--series-1);border-radius:3px}
td.heat{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.badge{display:inline-block;padding:1px 7px;border-radius:999px;font-size:12px;border:1px solid var(--border);color:var(--text-2)}
.badge.drop{border-color:var(--series-2);color:var(--series-2)}.badge.modify{border-color:var(--series-1);color:var(--series-1)}
.badge.flag{border-color:var(--series-3);color:var(--series-3)}.warn{color:var(--warn)}
details{margin-top:8px}summary{cursor:pointer;color:var(--text-2);font-size:13px}
pre{white-space:pre-wrap;word-break:break-word;font-size:12px;background:var(--surface-2);padding:10px;border-radius:8px;max-height:420px;overflow:auto}
.empty{padding:24px;border:1px dashed var(--border);border-radius:10px;color:var(--text-2)}
#tip{position:fixed;pointer-events:none;background:var(--text);color:var(--surface);padding:5px 8px;border-radius:6px;font-size:12px;opacity:0;transition:opacity .1s;max-width:320px;z-index:9}
"""

JS = r"""
const tip=document.getElementById('tip');
function showTip(e,t){tip.textContent=t;tip.style.opacity=1;tip.style.left=Math.min(e.clientX+12,innerWidth-330)+'px';tip.style.top=(e.clientY+12)+'px'}
function hideTip(){tip.style.opacity=0}
const fmt=n=>n.toLocaleString('vi-VN');
function esc(s){return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
// Cột dọc (theo thời gian / thứ tự)
function vbars(el,rows,unit){
  if(!rows.length){el.innerHTML='<p class="note">Không có dữ liệu.</p>';return}
  const W=480,H=200,L=40,B=40,T=14,max=Math.max(...rows.map(r=>r[1]),1);const bw=(W-L)/rows.length;
  let s=`<svg viewBox="0 0 ${W} ${H}" role="img">`;
  for(let i=0;i<=4;i++){const y=T+(H-T-B)*(1-i/4);s+=`<line class="gridline" x1="${L}" x2="${W}" y1="${y}" y2="${y}"/><text x="${L-6}" y="${y+4}" text-anchor="end">${fmt(Math.round(max*i/4))}</text>`}
  const step=Math.ceil(rows.length/12);
  rows.forEach((r,i)=>{const h=(H-T-B)*r[1]/max,x=L+i*bw+1,w=Math.max(bw-2,1),y=H-B-h;
    s+=`<path class="bar" d="M${x},${H-B}V${y+Math.min(4,h)}q0,-${Math.min(4,h)} ${Math.min(4,w/2)},-${Math.min(4,h)}H${x+w-Math.min(4,w/2)}q${Math.min(4,w/2)},0 ${Math.min(4,w/2)},${Math.min(4,h)}V${H-B}Z" data-t="${esc(r[0])}: ${fmt(r[1])} ${unit}"/>`;
    if(i%step==0)s+=`<text x="${x+w/2}" y="${H-B+14}" text-anchor="end" transform="rotate(-35 ${x+w/2} ${H-B+14})">${esc(r[0])}</text>`});
  el.innerHTML=s+'</svg>'+table(rows,unit);bind(el)}
// Thanh ngang (xếp hạng)
function hbars(el,rows,unit,total){
  if(!rows.length){el.innerHTML='<p class="note">Không có dữ liệu.</p>';return}
  const W=480,rh=22,L=190,H=rows.length*rh+4,max=Math.max(...rows.map(r=>r[1]),1);
  let s=`<svg viewBox="0 0 ${W} ${H}" role="img">`;
  rows.forEach((r,i)=>{const w=Math.max((W-L-60)*r[1]/max,2),y=i*rh+3;const lab=String(r[0]).length>30?String(r[0]).slice(0,29)+'…':r[0];
    const pct=total?` (${(100*r[1]/total).toFixed(1)}%)`:'';
    s+=`<text x="${L-8}" y="${y+12}" text-anchor="end">${esc(lab)}</text><path class="bar" d="M${L},${y}H${L+w-4}q4,0 4,4V${y+12}q0,4 -4,4H${L}Z" data-t="${esc(r[0])}: ${fmt(r[1])} ${unit}${pct}"/><text class="val" x="${L+w+6}" y="${y+12}">${fmt(r[1])}</text>`});
  el.innerHTML=s+'</svg>'+table(rows,unit);bind(el)}
function table(rows,unit){return `<details><summary>Xem dạng bảng</summary><div class="scroll"><table><tr><th>Giá trị</th><th>Số ${unit}</th></tr>${rows.map(r=>`<tr><td>${esc(r[0])}</td><td class="n">${fmt(r[1])}</td></tr>`).join('')}</table></div></details>`}
function bind(el){el.querySelectorAll('.bar').forEach(b=>{b.addEventListener('mousemove',e=>showTip(e,b.dataset.t));b.addEventListener('mouseleave',hideTip)})}
document.querySelectorAll('[data-chart]').forEach(el=>{const c=JSON.parse(el.dataset.chart);(c.kind==='v'?vbars:hbars)(el,c.rows,c.unit,c.total)});
"""


def vn(x: Any) -> str:
    """Số kiểu Việt Nam: 1.234 và 12,5."""
    if isinstance(x, bool) or x is None:
        return str(x)
    return f"{x:,}".replace(",", ".") if isinstance(x, int) else f"{x:.1f}".replace(".", ",")


def top(counter: collections.Counter, n: int = TOP_N) -> List[List[Any]]:
    return [[k, c] for k, c in counter.most_common(n)]


def hist(values: List[float], edges: List[float]) -> List[List[Any]]:
    out = []
    for i, lo in enumerate(edges):
        hi = edges[i + 1] if i + 1 < len(edges) else None
        if hi is None:
            label = f"≥ {vn(lo)}"
        elif isinstance(lo, int) and isinstance(hi, int):
            label = vn(lo) if hi == lo + 1 else f"{vn(lo)}–{vn(hi - 1)}"
        else:
            label = f"{vn(lo)}–<{vn(hi)}"
        out.append([label, sum(1 for v in values if v >= lo and (hi is None or v < hi))])
    return out


def chart(kind: str, rows: List[List[Any]], unit: str = "tin", total: int | None = None) -> str:
    return f"<div data-chart='{html.escape(json.dumps({'kind': kind, 'rows': rows, 'unit': unit, 'total': total}, ensure_ascii=False), quote=True)}'></div>"


def card(title: str, note: str, body: str) -> str:
    return f'<div class="card"><h3>{html.escape(title)}</h3><p class="note">{note}</p>{body}</div>'


def tile(v: Any, k: str) -> str:
    vv = vn(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else html.escape(str(v))
    return f'<div class="tile"><div class="v">{vv}</div><div class="k">{html.escape(k)}</div></div>'


def nav(items: List[tuple], active: str) -> str:
    """items: [(tên file không đuôi, nhãn)]."""
    return "<nav>" + "".join(
        f'<a href="{k}.html" class="{"on" if k == active else ""}">{html.escape(v)}</a>' for k, v in items) + "</nav>"


def heat(pct: float | None) -> str:
    """Ô phần trăm tô một sắc (đậm = phủ cao). Chữ luôn dùng màu chữ, không dùng màu series."""
    if pct is None:
        return "<td class='heat'>–</td>"
    a = round(min(max(pct, 0), 100) * 0.45)
    return f"<td class='heat' style='background:color-mix(in srgb,var(--series-1) {a}%,transparent)'>{vn(float(pct))}</td>"


def page(title: str, nav_html: str, body: str, footer: str) -> str:
    return f"""<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>{CSS}</style></head><body><main>{nav_html}{body}
<p class="note" style="margin-top:40px">{footer}</p>
</main><div id="tip"></div><script>{JS}</script></body></html>"""
