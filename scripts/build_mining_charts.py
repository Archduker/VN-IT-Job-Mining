"""Vẽ biểu đồ SVG cho slide từ kết quả Mining thật (mining/artifacts/), chỉ đọc.

Ghi từng biểu đồ ra docs/presentation/charts/<tên>.svg. Với --inject, thay phần giữa
<!-- chart:<tên> --> và <!-- /chart:<tên> --> trong docs/presentation/final_slides.html
bằng SVG inline (để chữ dùng font của slide).

    python scripts/build_mining_charts.py [--inject]

Biểu đồ (SD3 theo 7 nhóm nghề, cụm con trong từng nhóm, người dùng chốt 24/11/2026):
- cluster_explorer: biểu đồ tương tác (canvas) 2D/3D trên pca_x/y/z, tô theo 7 nhóm; bấm một nhóm để thấy cụm con.
- cluster_table: thẻ mỗi nhóm, liệt kê cụm con (vai trò, số tin, công cụ đặc trưng, lương trung vị).
- role_coverage: vai trò người dùng liệt kê có tách thành cụm không, và cụm nào ngoài danh sách.
- group_stability: ARI 5 seed theo từng nhóm, ngưỡng 0,8.
- skill_value: giá trị SHAP quy ra triệu/tháng của kỹ năng, kèm khoảng tin cậy bootstrap.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))  # để import mining.job_group khi chạy như script
ART = ROOT / "mining" / "artifacts"
OUT = ROOT / "docs" / "presentation" / "charts"
DECK = ROOT / "docs" / "presentation" / "final_slides.html"

INK = "#14213D"
MUTED = "#4A5568"
GRID = "#D9D5CA"
BLUE = "#2F6FB0"
ACCENT = "#C2561B"
FONT = "font-family=\"'Be Vietnam Pro', Arial, sans-serif\""


def esc(s: object) -> str:
    return html.escape(str(s), quote=True)


def vn(x: float, d: int = 2) -> str:
    return f"{x:.{d}f}".replace(".", ",")


def svg(w: int, h: int, body: str, label: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'role="img" aria-label="{esc(label)}" {FONT}>{body}</svg>')


GROUP_ORDER = ["Software", "QA/QC", "Data & AI", "Hạ tầng", "Security", "Product & Business", "Support & Consulting"]
GROUP_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#c98500", "#e34948", "#6250d6", "#0f8b8d", "#8A8F98"]  # cuối: nhóm Khác
SHORT_GROUP = {"Product & Business": "Product & Business", "Support & Consulting": "Support & Consulting"}


def sub_label(pr: dict) -> str:
    """Tên cụm con bỏ tiền tố nhóm; cụm chưa khớp vai trò ghi "chưa khớp: <công cụ>"."""
    rest = pr["cluster_name"].split(" · ", 1)[1]
    return rest if pr.get("sub_role_matched") else f"chưa khớp: {rest}"


def sal_txt(pr: dict) -> str:
    return f'{vn(pr["median_salary_mil"], 1)} tr' if pr.get("median_salary_mil") is not None else "ít dữ liệu lương"


def group_stability(by_group: dict, target: float) -> str:
    """Thanh ngang gọn (đặt trong cột hẹp): ARI trung bình 5 seed của từng nhóm, vạch ngưỡng."""
    short = {"Product & Business": "Product", "Support & Consulting": "Support"}
    items = [(short.get(g, g), by_group[g]["stability"]["ari_mean"]) for g in GROUP_ORDER if by_group.get(g, {}).get("k")]
    lab, w, rh, t, b = 150, 420, 42, 28, 30
    h = t + rh * len(items) + b
    def X(v): return lab + v * (w - lab - 62)
    g = []
    for k in (0, 0.5, 1):
        g.append(f'<line x1="{X(k):.1f}" x2="{X(k):.1f}" y1="{t}" y2="{t + rh * len(items)}" stroke="{GRID}"/>'
                 f'<text x="{X(k):.1f}" y="{t + rh * len(items) + 24}" font-size="18" fill="{MUTED}" text-anchor="middle">{vn(k, 1)}</text>')
    for i, (name, v) in enumerate(items):
        y = t + i * rh
        g.append(f'<text x="{lab - 10}" y="{y + rh / 2 + 7}" font-size="21" fill="{INK}" text-anchor="end">{esc(name)}</text>'
                 f'<rect x="{lab}" y="{y + 8}" width="{X(v) - lab:.1f}" height="{rh - 16}" rx="4" fill="{BLUE}">'
                 f'<title>{esc(name)}: ARI {vn(v, 3)}</title></rect>'
                 f'<text x="{X(v) + 6:.1f}" y="{y + rh / 2 + 7}" font-size="20" font-weight="600" fill="{INK}">{vn(v, 2)}</text>')
    g.append(f'<line x1="{X(target):.1f}" x2="{X(target):.1f}" y1="{t}" y2="{t + rh * len(items)}" stroke="{ACCENT}" '
             f'stroke-width="2.5" stroke-dasharray="6 5"/><text x="{X(target):.1f}" y="{t - 8}" font-size="18" '
             f'font-weight="600" fill="{ACCENT}" text-anchor="middle">ngưỡng {vn(target, 1)}</text>')
    return svg(w, h, "".join(g), "ARI giữa 5 seed theo từng nhóm nghề")


def skill_value(top: list[dict], n_show: int = 12) -> str:
    rows = sorted(top, key=lambda d: -d["delta_m"])[:n_show]
    lab, w, rh, t, b = 210, 820, 38, 16, 50
    h = t + rh * len(rows) + b
    step = 0.2
    hi = float(np.ceil(max(max(d["ci"][1] for d in rows), 0.1) / step) * step)
    lo = float(min(0.0, np.floor(min(d["ci"][0] for d in rows) / step) * step))
    n_ticks = int(round((hi - lo) / step))
    def X(v): return lab + (v - lo) / (hi - lo) * (w - lab - 90)
    g = []
    for k in range(n_ticks + 1):
        xv = lo + step * k
        g.append(f'<line x1="{X(xv):.1f}" x2="{X(xv):.1f}" y1="{t}" y2="{t + rh * len(rows)}" stroke="{GRID}"/>'
                 f'<text x="{X(xv):.1f}" y="{t + rh * len(rows) + 26}" font-size="16" fill="{MUTED}" text-anchor="middle">{vn(xv, 1)}</text>')
    g.append(f'<text x="{(lab + w - 90) / 2}" y="{h - 4}" font-size="16" fill="{MUTED}" text-anchor="middle">triệu đồng/tháng (khoảng tin cậy bootstrap 95%)</text>')
    for i, d in enumerate(rows):
        y = t + i * rh + rh / 2
        g.append(f'<text x="{lab - 14}" y="{y + 6}" font-size="18" fill="{INK}" text-anchor="end">{esc(d["skill"])}</text>'
                 f'<line x1="{X(d["ci"][0]):.1f}" x2="{X(d["ci"][1]):.1f}" y1="{y}" y2="{y}" stroke="{BLUE}" stroke-width="3" stroke-linecap="round"/>'
                 f'<circle cx="{X(d["delta_m"]):.1f}" cy="{y}" r="7" fill="{BLUE}" stroke="#FFFDF9" stroke-width="2">'
                 f'<title>{esc(d["skill"])}: +{vn(d["delta_m"])} triệu (n = {d["n"]})</title></circle>'
                 f'<text x="{w - 80}" y="{y + 6}" font-size="17" font-weight="600" fill="{INK}">+{vn(d["delta_m"])}</text>')
    return svg(w, h, "".join(g), "Giá trị SHAP của kỹ năng, triệu đồng mỗi tháng")


GT_CSS = """<style>
.gt { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.gt-card { background: #FFFDF9; border: 2px solid #D9D5CA; border-radius: 12px; padding: 12px 14px; }
.gt-h { font-size: 22px; font-weight: 700; color: #14213D; }
.gt-m { font-size: 16px; color: #4A5568; margin: 2px 0 8px; }
.gt ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.gt li { font-size: 16px; line-height: 1.25; color: #14213D; }
.gt li span { color: #4A5568; font-size: 15px; }
.gt li.nm b { color: #C2561B; }
.gt li.ot b { color: #4A5568; font-weight: 600; }
</style>"""

RC_CSS = """<style>
.rc { display: flex; flex-direction: column; gap: 10px; }
.rc-row { display: grid; grid-template-columns: 230px 1fr; gap: 14px; align-items: center; }
.rc-g { font-size: 20px; font-weight: 700; color: #14213D; }
.rc-c { display: flex; flex-wrap: wrap; gap: 8px; }
.ch { font-size: 17px; padding: 4px 12px; border-radius: 999px; border: 2px solid; }
.ch.on { background: #2F6FB0; border-color: #2F6FB0; color: #FFFFFF; }
.ch.off { background: transparent; border-color: #CFCBBF; color: #4A5568; }
.ch.ex { background: #FBE9DF; border-color: #C2561B; color: #7A3410; }
.rc-key { display: flex; gap: 8px; margin-top: 6px; padding-top: 10px; border-top: 1px solid #D9D5CA; }
.rc-key .ch { font-size: 15px; }
</style>"""


def cluster_table(profiles: list[dict], by_group: dict, cov: dict, other: dict) -> str:
    """Thẻ mỗi nhóm (lưới 4 cột): cụm con theo số tin giảm dần, kèm công cụ đặc trưng và lương trung vị."""
    out = [GT_CSS, '<div class="gt">']
    for gi, g in enumerate(GROUP_ORDER):
        subs = sorted((p for p in profiles if p["job_group"] == g), key=lambda p: -p["size"])
        if not subs:
            continue
        few = cov["group_other_few_tools"].get(g, 0)
        n = sum(p["size"] for p in subs) + few
        n_txt = f"{n:,}".replace(",", ".")
        out.append(f'<div class="gt-card" style="border-top:6px solid {GROUP_COLORS[gi]}"><div class="gt-h">{esc(g)}</div>'
                   f'<div class="gt-m">{n_txt} tin · {len(subs)} cụm · ARI {vn(by_group[g]["stability"]["ari_mean"], 2)}</div><ul>')
        for p in subs:
            cls = "" if p.get("sub_role_matched") else ' class="nm"'
            sal = f' · {vn(p["median_salary_mil"], 1)} tr' if p.get("median_salary_mil") is not None else ""
            out.append(f'<li{cls}><b>{esc(sub_label(p))}</b> <span>{p["size"]} tin{sal}</span></li>')
        if few:
            out.append(f'<li class="ot"><b>Khác (JD ít thông tin)</b> <span>{few} tin</span></li>')
        out.append("</ul></div>")
    st = other["status_counts"]
    n_o = cov["n_outside_groups"]
    out.append(f'<div class="gt-card" style="border-top:6px solid {GROUP_COLORS[-1]}"><div class="gt-h">Khác (ngoài 7 nhóm)</div>'
               f'<div class="gt-m">{n_o} tin · xét bằng luật nghề mới</div><ul>'
               + "".join(f'<li class="ot"><b>{esc(k)}</b> <span>{v} tin</span></li>'
                         for k, v in sorted(st.items(), key=lambda kv: -kv[1]))
               + '<li class="ot"><b>nghề mới</b> <span>0 tin</span></li>' * (st.get("nghề mới", 0) == 0) + "</ul></div>")
    out.append("</div>")
    return "".join(out)


def role_coverage(profiles: list[dict]) -> str:
    """Mỗi nhóm một dòng: vai trò trong danh sách tách thành cụm (xanh) hay không (viền xám); cụm ngoài danh sách (cam)."""
    from mining.job_group import SUB_ROLES

    out = [RC_CSS, '<div class="rc">']
    for g in GROUP_ORDER:
        subs = [p for p in profiles if p["job_group"] == g]
        found = {}
        for p in subs:
            if p.get("sub_role_matched"):
                found[p["sub_role"]] = found.get(p["sub_role"], 0) + 1
        chips = []
        for name, _ in SUB_ROLES[g]:
            k = found.get(name, 0)
            chips.append(f'<span class="ch on">{esc(name)}{" ×" + str(k) if k > 1 else ""}</span>' if k
                         else f'<span class="ch off">{esc(name)}</span>')
        for p in subs:
            if not p.get("sub_role_matched"):
                chips.append(f'<span class="ch ex">{esc(p["head_skills"])} ({p["size"]})</span>')
        out.append(f'<div class="rc-row"><div class="rc-g">{esc(g)}</div><div class="rc-c">{"".join(chips)}</div></div>')
    out.append('<div class="rc-key"><span class="ch on">có cụm riêng (×2: hai cụm)</span><span class="ch off">không thành cụm</span>'
               '<span class="ch ex">cụm chưa khớp vai trò (số tin)</span></div>')
    out.append("</div>")
    return "".join(out)


SUB_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#c98500", "#e34948", "#6250d6"]

EXPLORER_CSS = """
<style>
.cx { display: grid; grid-template-columns: 1fr 540px; gap: 24px; align-items: start; }
.cx-plot { position: relative; background: #FFFDF9; border: 2px solid #D9D5CA; border-radius: 14px; overflow: hidden; }
.cx-plot canvas { display: block; width: 1080px; height: 640px; cursor: default; }
.cx-plot.d3 canvas { cursor: grab; }
.cx-modes { position: absolute; left: 16px; top: 14px; display: flex; gap: 8px; }
.cx-btn { font: 600 21px 'Be Vietnam Pro', Arial, sans-serif; color: #14213D; background: #F7F6F2; border: 2px solid #D9D5CA;
  border-radius: 10px; padding: 6px 14px; cursor: pointer; }
.cx-btn.on { background: #14213D; color: #F7F6F2; border-color: #14213D; }
.cx-hint { position: absolute; right: 16px; bottom: 12px; font-size: 18px; color: #4A5568; }
.cx-list { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.cx-item { display: flex; align-items: center; gap: 10px; text-align: left; font: 500 19px 'Be Vietnam Pro', Arial, sans-serif;
  color: #14213D; background: #FFFDF9; border: 2px solid #D9D5CA; border-radius: 10px; padding: 7px 10px; cursor: pointer; }
.cx-item .sw { width: 14px; height: 14px; border-radius: 4px; flex: none; }
.cx-item.on { border-color: #14213D; box-shadow: inset 0 0 0 1px #14213D; }
.cx-item.all { grid-column: 1 / -1; justify-content: center; font-weight: 600; }
.cx-info { margin-top: 12px; background: #FFFDF9; border: 2px solid #D9D5CA; border-radius: 12px; padding: 12px 16px;
  font-size: 17px; line-height: 1.4; color: #4A5568; min-height: 150px; }
.cx-info b { color: #14213D; }
.cx-info .t { font-size: 22px; font-weight: 700; color: #14213D; margin-bottom: 4px; }
.cx-info .s { display: flex; gap: 8px; align-items: baseline; margin-top: 5px; }
.cx-info .s i { width: 12px; height: 12px; border-radius: 3px; flex: none; display: inline-block; }
</style>
"""

EXPLORER_JS = r"""
<script>
(function () {
  var D = __DATA__, GC = __GCOLORS__, SC = __SCOLORS__, GREY = '#CFCBBF';
  var root = document.getElementById('cx'), cv = root.querySelector('canvas'), ctx = cv.getContext('2d');
  var W = 1080, H = 640, sel = -1, mode = '2d', yaw = 0.7, pitch = 0.3, drag = null, auto = true;
  cv.width = W * 2; cv.height = H * 2; ctx.scale(2, 2);
  function proj(p) {
    if (mode === '2d') return [W / 2 + p[0] * W * 0.44, H / 2 - p[1] * H * 0.42, 1];
    var cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
    var x = p[0] * cy + p[2] * sy, z = -p[0] * sy + p[2] * cy, y = p[1] * cp - z * sp; z = p[1] * sp + z * cp;
    var f = 3.2 / (3.2 + z);
    return [W / 2 + x * f * H * 0.5, H / 2 - y * f * H * 0.46, f];
  }
  function dot(p, color, r) { var q = proj(p); ctx.fillStyle = color; ctx.beginPath(); ctx.arc(q[0], q[1], r * q[2], 0, 6.2832); ctx.fill(); }
  function label(center, t) {
    var q = proj(center);
    ctx.font = '700 20px "Be Vietnam Pro", Arial, sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.lineWidth = 5; ctx.strokeStyle = '#FFFDF9'; ctx.strokeText(t, q[0], q[1]); ctx.fillStyle = '#14213D'; ctx.fillText(t, q[0], q[1]);
  }
  function draw() {
    ctx.clearRect(0, 0, W, H);
    if (mode === '3d') {
      [[[-1, 0, 0], [1, 0, 0]], [[0, -1, 0], [0, 1, 0]], [[0, 0, -1], [0, 0, 1]]].forEach(function (ax) {
        var a = proj(ax[0]), b = proj(ax[1]); ctx.strokeStyle = '#E3DFD4'; ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke();
      });
    }
    var pts = D.pts, i;
    if (sel < 0) {
      ctx.globalAlpha = 0.75;
      for (i = 0; i < pts.length; i++) dot(pts[i], GC[pts[i][3]], 2.6);
      ctx.globalAlpha = 1; D.groups.forEach(function (g) { label(g.center, g.short); });
    } else {
      ctx.globalAlpha = 0.5;
      for (i = 0; i < pts.length; i++) if (pts[i][3] !== sel) dot(pts[i], GREY, 2.2);
      ctx.globalAlpha = 0.9;
      for (i = 0; i < pts.length; i++) if (pts[i][3] === sel) dot(pts[i], D.groups[sel].subs.length ? SC[pts[i][4]] : '#4A5568', 3.2);
      ctx.globalAlpha = 1; D.groups[sel].subs.forEach(function (s, k) { label(s.center, String(k + 1)); });
    }
  }
  var list = root.querySelector('.cx-list'), info = root.querySelector('.cx-info');
  function fmt(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, '.'); }
  function showInfo() {
    if (sel < 0) {
      info.innerHTML = '<div class="t">' + fmt(D.n) + ' tin: 7 nhóm, ' + D.k + ' cụm con và nhóm Khác</div>Bấm một nhóm để xem các cụm con. Tin ghi dưới 2 công cụ nằm ở mục Khác của nhóm, không có trên hình. ' +
        'Hình là hình chiếu PCA (2D giữ ' + D.var2 + '%, 3D giữ ' + D.var3 + '% phương sai); K-Means chia cụm trong không gian SVD 60 chiều.';
      return;
    }
    var g = D.groups[sel];
    if (!g.subs.length) {
      info.innerHTML = '<div class="t">' + g.name + '</div><b>' + fmt(g.n) + '</b> tin, xét bằng luật chốt nghề mới · ' + g.few + ' tin JD ít thông tin (không có trên hình)' +
        g.status.map(function (s) { return '<div class="s"><span><b>' + s[0] + '</b>: ' + s[1] + ' tin</span></div>'; }).join('') +
        '<div class="s"><span><b>nghề mới</b>: 0</span></div>';
      return;
    }
    info.innerHTML = '<div class="t">' + g.name + '</div><b>' + fmt(g.n) + '</b> tin · ' + g.subs.length + ' cụm con · ARI <b>' + g.ari + '</b>' +
      (g.few ? '<div class="s"><i style="background:#CFCBBF"></i><span><b>Khác (JD ít thông tin)</b>: ' + fmt(g.few) + ' tin, không có trên hình</span></div>' : '') +
      g.subs.map(function (s, k) {
        return '<div class="s"><i style="background:' + SC[k] + '"></i><span><b>' + (k + 1) + '. ' + s.name + '</b> (' + fmt(s.n) + ' tin, ' + s.sal + ') · ' + s.tools + '</span></div>';
      }).join('');
  }
  function pick(id) {
    sel = (sel === id) ? -1 : id;
    Array.prototype.forEach.call(list.children, function (b) { b.classList.toggle('on', +b.dataset.id === sel); });
    showInfo(); draw();
  }
  var all = document.createElement('button'); all.className = 'cx-item all on'; all.dataset.id = -1; all.textContent = 'Tất cả (7 nhóm + Khác)';
  all.onclick = function () { pick(-1); all.blur(); }; list.appendChild(all);
  D.groups.forEach(function (g) {
    var b = document.createElement('button'); b.className = 'cx-item'; b.dataset.id = g.id;
    b.innerHTML = '<span class="sw" style="background:' + GC[g.id] + '"></span><span>' + g.name + ' <span style="color:#4A5568">(' + fmt(g.n) + ')</span></span>';
    b.onclick = function () { pick(g.id); b.blur(); }; list.appendChild(b);
  });
  root.querySelectorAll('.cx-modes .cx-btn').forEach(function (b) {
    b.onclick = function () {
      mode = b.dataset.mode; auto = true; b.blur();
      root.querySelectorAll('.cx-modes .cx-btn').forEach(function (x) { x.classList.toggle('on', x === b); });
      root.querySelector('.cx-plot').classList.toggle('d3', mode === '3d');
      root.querySelector('.cx-hint').textContent = mode === '3d' ? 'Kéo để xoay' : 'PC1 × PC2';
      draw();
    };
  });
  cv.addEventListener('pointerdown', function (e) { if (mode === '3d') { drag = [e.clientX, e.clientY]; auto = false; cv.setPointerCapture(e.pointerId); } });
  cv.addEventListener('pointermove', function (e) {
    if (!drag) return;
    yaw += (e.clientX - drag[0]) * 0.008; pitch = Math.max(-1.3, Math.min(1.3, pitch + (e.clientY - drag[1]) * 0.008));
    drag = [e.clientX, e.clientY]; draw();
  });
  cv.addEventListener('pointerup', function () { drag = null; });
  ['touchstart', 'touchend', 'touchmove'].forEach(function (t) { cv.addEventListener(t, function (e) { e.stopPropagation(); }, {passive: true}); });
  function tick() {
    var sec = root.closest('section');
    if (mode === '3d' && auto && !drag && sec && sec.classList.contains('on')) { yaw += 0.004; draw(); }
    requestAnimationFrame(tick);
  }
  showInfo(); draw(); requestAnimationFrame(tick);
})();
</script>
"""


def cluster_explorer(clusters: pd.DataFrame, profiles: list[dict], cl: dict) -> str:
    """Biểu đồ tương tác (canvas, không thư viện): 2D/3D trên pca_x/y/z, tô theo 7 nhóm; bấm nhóm để thấy cụm con."""
    by_group, pca_var, cov = cl["by_group"], cl["pca_explained_variance"], cl["coverage"]
    c = clusters[(clusters["cluster_id"] >= 0) | ((clusters["job_group"] == "Khác") & clusters["pca_x"].notna())].copy()
    xyz = c[["pca_x", "pca_y", "pca_z"]].to_numpy(dtype=float)
    lo, hi = np.quantile(xyz, 0.005, axis=0), np.quantile(xyz, 0.995, axis=0)
    mid, half = (lo + hi) / 2, (hi - lo) / 2
    norm = np.clip((xyz - mid) / half, -1.05, 1.05)
    gid = {g: i for i, g in enumerate(GROUP_ORDER + ["Khác"])}
    groups, sub_of = [], {}
    for g in GROUP_ORDER:
        subs = sorted((p for p in profiles if p["job_group"] == g), key=lambda p: -p["size"])
        if not subs:
            continue
        for k, p in enumerate(subs):
            sub_of[p["cluster_id"]] = k
        gm = (c["job_group"] == g).to_numpy()
        groups.append({"id": gid[g], "name": g, "short": SHORT_GROUP.get(g, g).split(" & ")[0],
                       "n": int(gm.sum()) + cov["group_other_few_tools"].get(g, 0), "few": cov["group_other_few_tools"].get(g, 0),
                       "ari": vn(by_group[g]["stability"]["ari_mean"], 2),
                       "center": [round(float(v), 3) for v in norm[gm].mean(axis=0)],
                       "subs": [{"name": sub_label(p), "n": p["size"], "sal": sal_txt(p),
                                 "tools": ", ".join(t["skill"] for t in p["top_skills"][:3]),
                                 "center": [round(float(v), 3) for v in norm[(c["cluster_id"] == p["cluster_id"]).to_numpy()].mean(axis=0)]}
                                for p in subs]})
    km = (c["job_group"] == "Khác").to_numpy()
    st = cl["other"]["status_counts"]
    groups.append({"id": gid["Khác"], "name": "Khác (ngoài 7 nhóm)", "short": "Khác", "n": cov["n_outside_groups"],
                   "few": st.get("JD ít thông tin", 0), "ari": None, "center": [round(float(v), 3) for v in norm[km].mean(axis=0)],
                   "status": [[k, v] for k, v in sorted(st.items(), key=lambda kv: -kv[1]) if k != "JD ít thông tin"], "subs": []})
    by_id = {g["id"]: g for g in groups}
    ordered = [by_id[i] for i in sorted(by_id)]
    pts = [[round(float(a), 3), round(float(b), 3), round(float(z), 3), gid[g], sub_of.get(int(k), 0)]
           for (a, b, z), g, k in zip(norm, c["job_group"], c["cluster_id"])]
    data = {"n": int(len(clusters)), "k": len(profiles), "pts": pts, "groups": ordered,
            "var2": vn(100 * sum(pca_var[:2]), 0), "var3": vn(100 * sum(pca_var[:3]), 0)}
    js = (EXPLORER_JS.replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
          .replace("__GCOLORS__", json.dumps(GROUP_COLORS)).replace("__SCOLORS__", json.dumps(SUB_COLORS)))
    body = ('<div class="cx" id="cx"><div class="cx-plot"><canvas aria-label="Bản đồ 7 nhóm nghề, chọn nhóm bằng các nút bên phải"></canvas>'
            '<div class="cx-modes"><button class="cx-btn on" data-mode="2d">2D</button>'
            '<button class="cx-btn" data-mode="3d">3D</button></div><div class="cx-hint">PC1 × PC2</div></div>'
            '<div class="cx-side"><div class="cx-list"></div><div class="cx-info"></div></div></div>')
    return EXPLORER_CSS + body + js


def build() -> dict[str, str]:
    m = json.loads((ART / "mining_metrics.json").read_text(encoding="utf-8"))
    cl = m["clustering"]
    clusters = pd.read_parquet(ART / "job_clusters.parquet")
    profiles = sorted(cl["clusters"], key=lambda p: p["cluster_id"])
    return {
        "cluster_explorer": cluster_explorer(clusters, profiles, cl),
        "cluster_table": cluster_table(profiles, cl["by_group"], cl["coverage"], cl["other"]),
        "role_coverage": role_coverage(profiles),
        "group_stability": group_stability(cl["by_group"], 0.8),
        "skill_value": skill_value(m["salary"]["shap"]["top_skills"]),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--inject", action="store_true", help="chèn SVG vào docs/presentation/final_slides.html")
    args = ap.parse_args()
    charts = build()
    OUT.mkdir(parents=True, exist_ok=True)
    for name, s in charts.items():
        ext = "svg" if s.startswith("<svg") else "html"
        (OUT / f"{name}.{ext}").write_text(s, encoding="utf-8", newline="\n")
        print(f"{name}: {len(s) // 1024} KB")
    if args.inject:
        deck = DECK.read_text(encoding="utf-8")
        for name, s in charts.items():
            pat = re.compile(rf"(<!-- chart:{name} -->).*?(<!-- /chart:{name} -->)", re.S)
            if not pat.search(deck):
                print(f"bỏ qua {name}: slide không có chỗ đánh dấu")
                continue
            deck = pat.sub(lambda mo: mo.group(1) + s + mo.group(2), deck)
        DECK.write_text(deck, encoding="utf-8", newline="\n")
        print(f"đã chèn vào {DECK.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
