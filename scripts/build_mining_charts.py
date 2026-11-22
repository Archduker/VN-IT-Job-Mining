"""Vẽ biểu đồ SVG cho slide từ kết quả Mining thật (mining/artifacts/), chỉ đọc.

Ghi từng biểu đồ ra docs/presentation/charts/<tên>.svg. Với --inject, thay phần giữa
<!-- chart:<tên> --> và <!-- /chart:<tên> --> trong docs/presentation/final_slides.html
bằng SVG inline (để chữ dùng font của slide).

    python scripts/build_mining_charts.py [--inject]

Biểu đồ:
- cluster_map: mỗi cụm một ô (small multiples) trên hình chiếu PCA 2 chiều; cụm tô xanh, mọi tin khác xám.
- cluster_family: heatmap tỷ lệ nhóm nghề trong từng cụm (thang một màu).
- k_silhouette, k_inertia: quét k 2–20 (hai biểu đồ riêng, không dùng hai trục).
- stability: ARI của 4 seed so với seed 42, ngưỡng 0,8.
- skill_value: giá trị SHAP quy ra triệu/tháng của kỹ năng, kèm khoảng tin cậy bootstrap.
"""
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "mining" / "artifacts"
OUT = ROOT / "docs" / "presentation" / "charts"
DECK = ROOT / "docs" / "presentation" / "final_slides.html"

INK = "#14213D"
MUTED = "#4A5568"
GRID = "#D9D5CA"
BG_POINT = "#CFCBBF"
BLUE = "#2F6FB0"
ACCENT = "#C2561B"
# Thang một màu (xanh) cho heatmap, nhạt -> đậm
RAMP = ["#F3F1EA", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
SHORT_FAM = {"Infra/Support": "Infra", "DevOps/Cloud": "DevOps", "Security": "Sec.", "Data/AI": "Data/AI"}
FONT = "font-family=\"'Be Vietnam Pro', Arial, sans-serif\""


def esc(s: object) -> str:
    return html.escape(str(s), quote=True)


def vn(x: float, d: int = 2) -> str:
    return f"{x:.{d}f}".replace(".", ",")


def svg(w: int, h: int, body: str, label: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'role="img" aria-label="{esc(label)}" {FONT}>{body}</svg>')


def short_name(name: str) -> str:
    return name.replace("windows/windows_server", "windows/win_server")


def cluster_map(clusters: pd.DataFrame, profiles: list[dict]) -> str:
    """Small multiples 5 × 2 trên pca_x, pca_y."""
    c = clusters[clusters["in_clustering"]].copy()
    x0, x1 = c["pca_x"].quantile([0.002, 0.998])
    y0, y1 = c["pca_y"].quantile([0.002, 0.998])
    cols, pw, ph, gx, gy, top = 5, 316, 196, 21, 20, 62
    w = cols * pw + (cols - 1) * gx
    rows = int(np.ceil(len(profiles) / cols))
    h = rows * (ph + top) + (rows - 1) * gy
    rng = np.random.default_rng(42)
    bg = c.iloc[rng.choice(len(c), size=min(1400, len(c)), replace=False)]

    def px(v: float) -> float:
        return 8 + (min(max(v, x0), x1) - x0) / (x1 - x0) * (pw - 16)

    def py(v: float) -> float:
        return 8 + (1 - (min(max(v, y0), y1) - y0) / (y1 - y0)) * (ph - 16)

    bg_dots = "".join(f'<circle cx="{px(a):.1f}" cy="{py(b):.1f}" r="1.5"/>' for a, b in zip(bg["pca_x"], bg["pca_y"]))
    parts = []
    for i, pr in enumerate(profiles):
        cid = pr["cluster_id"]
        ox = (i % cols) * (pw + gx)
        oy = (i // cols) * (ph + top + gy)
        sub = c[c["cluster_id"] == cid]
        dots = "".join(f'<circle cx="{px(a):.1f}" cy="{py(b):.1f}" r="2"/>' for a, b in zip(sub["pca_x"], sub["pca_y"]))
        prefix, _, head = short_name(pr["cluster_name"]).partition(" · ")
        meta = f'{head} · ' + f'{pr["size"]:,} tin'.replace(",", ".") + f' · {round(pr["job_family_purity"] * 100)}%'
        name = prefix
        parts.append(
            f'<g transform="translate({ox},{oy})">'
            f'<text x="0" y="24" font-size="21" font-weight="700" fill="{INK}">C{cid} · {esc(name)}</text>'
            f'<text x="0" y="50" font-size="17" fill="{MUTED}">{esc(meta)}</text>'
            f'<g transform="translate(0,{top})">'
            f'<rect width="{pw}" height="{ph}" rx="10" fill="#FFFDF9" stroke="{GRID}" stroke-width="1.5"/>'
            f'<g fill="{BG_POINT}">{bg_dots}</g><g fill="{BLUE}" fill-opacity="0.85">{dots}</g></g>'
            f'<title>C{cid} {esc(pr["cluster_name"])}: {pr["size"]} tin</title></g>')
    return svg(w, h, "".join(parts), "Bản đồ 10 cụm trên hình chiếu PCA 2 chiều")


def cluster_family(crosstab: list[dict], profiles: list[dict]) -> str:
    ct = pd.DataFrame(crosstab)
    fam_order = ct.groupby("job_family")["n"].sum().sort_values(ascending=False).index.tolist()
    if "Other" in fam_order:
        fam_order = [f for f in fam_order if f != "Other"] + ["Other"]
    label_w, cw, ch, head = 250, 80, 46, 56
    w = label_w + cw * len(fam_order)
    h = head + ch * len(profiles) + 8
    cells = []
    for j, f in enumerate(fam_order):
        x = label_w + j * cw + cw / 2
        cells.append(f'<text x="{x}" y="{head - 16}" font-size="19" font-weight="600" fill="{MUTED}" '
                     f'text-anchor="middle">{esc(SHORT_FAM.get(f, f))}</text>')
    for i, pr in enumerate(profiles):
        cid = pr["cluster_id"]
        y = head + i * ch
        cells.append(f'<text x="{label_w - 14}" y="{y + ch / 2 + 8}" font-size="21" fill="{INK}" '
                     f'text-anchor="end">C{cid} · {esc(pr["cluster_name"].split(" · ")[0].replace("Infra/Support", "Infra"))}</text>')
        sub = ct[ct["cluster_id"] == cid].set_index("job_family")
        for j, f in enumerate(fam_order):
            share = float(sub["share"].get(f, 0.0)) if f in sub.index else 0.0
            n = int(sub["n"].get(f, 0)) if f in sub.index else 0
            k = 0 if share <= 0 else min(len(RAMP) - 1, 1 + int(share / 0.1))
            fill = RAMP[k]
            x = label_w + j * cw
            cells.append(f'<rect x="{x + 1}" y="{y + 1}" width="{cw - 2}" height="{ch - 2}" rx="4" fill="{fill}">'
                         f'<title>C{cid} × {esc(f)}: {n} tin ({vn(share * 100, 1)}%)</title></rect>')
            if share >= 0.10:
                tc = "#FFFFFF" if k >= 4 else INK
                cells.append(f'<text x="{x + cw / 2}" y="{y + ch / 2 + 8}" font-size="21" font-weight="600" '
                             f'fill="{tc}" text-anchor="middle">{round(share * 100)}%</text>')
    return svg(w, h, "".join(cells), "Tỷ lệ nhóm nghề trong từng cụm")


def line_chart(xs: list[int], ys: list[float], mark_x: int, y_fmt, title: str, w: int = 780, h: int = 360,
               y_min: float | None = None, y_max: float | None = None) -> str:
    l, r, t, b = 80, 24, 20, 56
    y_min = min(ys) if y_min is None else y_min
    y_max = max(ys) if y_max is None else y_max
    def X(v): return l + (v - xs[0]) / (xs[-1] - xs[0]) * (w - l - r)
    def Y(v): return t + (1 - (v - y_min) / (y_max - y_min)) * (h - t - b)
    g = []
    for k in range(5):
        yv = y_min + (y_max - y_min) * k / 4
        g.append(f'<line x1="{l}" x2="{w - r}" y1="{Y(yv):.1f}" y2="{Y(yv):.1f}" stroke="{GRID}" stroke-width="1"/>'
                 f'<text x="{l - 10}" y="{Y(yv) + 6:.1f}" font-size="17" fill="{MUTED}" text-anchor="end">{y_fmt(yv)}</text>')
    for xv in xs:
        if xv % 2 == 0:
            g.append(f'<text x="{X(xv):.1f}" y="{h - b + 26}" font-size="17" fill="{MUTED}" text-anchor="middle">{xv}</text>')
    g.append(f'<text x="{(l + w - r) / 2}" y="{h - 6}" font-size="17" fill="{MUTED}" text-anchor="middle">số cụm k</text>')
    pts = " ".join(f"{X(a):.1f},{Y(v):.1f}" for a, v in zip(xs, ys))
    g.append(f'<polyline points="{pts}" fill="none" stroke="{BLUE}" stroke-width="2.5" stroke-linejoin="round"/>')
    for a, v in zip(xs, ys):
        g.append(f'<circle cx="{X(a):.1f}" cy="{Y(v):.1f}" r="{7 if a == mark_x else 4}" '
                 f'fill="{ACCENT if a == mark_x else BLUE}" stroke="#FFFDF9" stroke-width="2"><title>k = {a}: {y_fmt(v)}</title></circle>')
    mv = ys[xs.index(mark_x)]
    g.append(f'<text x="{X(mark_x):.1f}" y="{Y(mv) + 34:.1f}" font-size="18" font-weight="600" fill="{ACCENT}" text-anchor="middle">k = {mark_x} (đã chốt): {y_fmt(mv)}</text>')
    return svg(w, h, "".join(g), title)


def stability(stab: dict, target: float) -> str:
    seeds = list(stab["ari_vs_first"].items())
    w, h, l, r, t, b = 700, 360, 70, 110, 20, 56
    def Y(v): return t + (1 - v) * (h - t - b)
    bw = (w - l - r) / len(seeds)
    g = []
    for k in range(6):
        yv = k / 5
        g.append(f'<line x1="{l}" x2="{w - r}" y1="{Y(yv):.1f}" y2="{Y(yv):.1f}" stroke="{GRID}"/>'
                 f'<text x="{l - 10}" y="{Y(yv) + 6:.1f}" font-size="17" fill="{MUTED}" text-anchor="end">{vn(yv, 1)}</text>')
    for i, (seed, v) in enumerate(seeds):
        x = l + i * bw + 14
        g.append(f'<path d="M{x},{Y(0):.1f} V{Y(v) + 4:.1f} q0,-4 4,-4 h{bw - 36:.1f} q4,0 4,4 V{Y(0):.1f} Z" fill="{BLUE}">'
                 f'<title>seed {seed}: ARI {vn(v, 3)}</title></path>'
                 f'<text x="{x + (bw - 28) / 2:.1f}" y="{Y(v) - 10:.1f}" font-size="18" font-weight="600" fill="{INK}" text-anchor="middle">{vn(v, 2)}</text>'
                 f'<text x="{x + (bw - 28) / 2:.1f}" y="{h - b + 26}" font-size="17" fill="{MUTED}" text-anchor="middle">seed {seed}</text>')
    g.append(f'<line x1="{l}" x2="{w - r}" y1="{Y(target):.1f}" y2="{Y(target):.1f}" stroke="{ACCENT}" stroke-width="2.5" stroke-dasharray="8 6"/>'
             f'<text x="{w - r + 8}" y="{Y(target) + 6:.1f}" font-size="17" font-weight="600" fill="{ACCENT}">ngưỡng {vn(target, 1)}</text>')
    return svg(w, h, "".join(g), "ARI giữa các seed")


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


def cluster_table(profiles: list[dict]) -> str:
    """Bảng HTML hồ sơ cụm (dùng class .t của slide)."""
    rows = ['<table class="t"><tr><th>Cụm</th><th class="r">Số tin</th><th class="r">Nghề đa số</th>'
            '<th>Công cụ đặc trưng (lift)</th><th class="r">Công cụ/tin</th><th class="r">Lương trung vị</th></tr>']
    for pr in sorted(profiles, key=lambda p: -p["size"]):
        tools = ", ".join(t["skill"] for t in pr["top_skills"][:4])
        sal = f'{vn(pr["median_salary_mil"], 1)} tr' if pr.get("median_salary_mil") is not None else "ít dữ liệu"
        rows.append(f'<tr><td>C{pr["cluster_id"]} · {esc(short_name(pr["cluster_name"]).split(" · ")[0])}</td>'
                    f'<td class="r">{pr["size"]:,}</td>'.replace(",", ".")
                    + f'<td class="r">{esc(pr["dominant_job_family"])} {round(pr["job_family_purity"] * 100)}%</td>'
                    f'<td>{esc(tools)}</td><td class="r">{vn(pr.get("median_n_tools", 0), 0)}</td><td class="r">{sal}</td></tr>')
    rows.append("</table>")
    return "".join(rows)


def build() -> dict[str, str]:
    m = json.loads((ART / "mining_metrics.json").read_text(encoding="utf-8"))
    cl = m["clustering"]
    clusters = pd.read_parquet(ART / "job_clusters.parquet")
    profiles = sorted(cl["clusters"], key=lambda p: p["cluster_id"])
    ks = [r["k"] for r in cl["k_scan"]]
    charts = {
        "cluster_map": cluster_map(clusters, profiles),
        "cluster_family": cluster_family(cl["crosstab"], profiles),
        "k_silhouette": line_chart(ks, [r["silhouette"] for r in cl["k_scan"]], cl["best_k"], lambda v: vn(v, 3),
                                   "Silhouette theo k", y_min=0.0, y_max=0.12),
        "k_inertia": line_chart(ks, [r["inertia"] for r in cl["k_scan"]], cl["best_k"], lambda v: f"{v:.0f}",
                                "Inertia theo k"),
        "stability": stability(cl["stability"], 0.8),
        "skill_value": skill_value(m["salary"]["shap"]["top_skills"]),
        "cluster_table": cluster_table(profiles),
    }
    return charts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--inject", action="store_true", help="chèn SVG vào docs/presentation/final_slides.html")
    args = ap.parse_args()
    charts = build()
    OUT.mkdir(parents=True, exist_ok=True)
    for name, s in charts.items():
        ext = "html" if s.startswith("<table") else "svg"
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
