"""Vẽ HTML 3D xoay được từ mining/artifacts/job_clusters.parquet (PCA 3D, tô theo cụm). Chỉ đọc file local.

    python scripts/plot_clusters_3d.py [--src ...] [--out docs/presentation/clusters_3d.html]
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "mining" / "artifacts" / "job_clusters.parquet"
OUT = ROOT / "docs" / "presentation" / "clusters_3d.html"
PLOTLY = "https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js"


def build(src: Path, out: Path) -> int:
    src = Path(src)
    if not src.exists():
        raise FileNotFoundError(f"Thiếu {src}; chạy mining/run_mining_pipeline.py --only cluster trước.")
    df = pd.read_parquet(src)
    traces = []
    for cid, g in df.groupby("cluster_id"):
        traces.append({
            "type": "scatter3d", "mode": "markers", "name": f"{cid}: {g['cluster_name'].iloc[0]} ({len(g)})",
            "x": g["pca_x"].round(4).tolist(), "y": g["pca_y"].round(4).tolist(), "z": g["pca_z"].round(4).tolist(),
            "text": (g["job_title"].fillna("") + "<br>" + g["job_family"].fillna("")).tolist(),
            "hovertemplate": "%{text}<extra>" + str(g["cluster_name"].iloc[0]) + "</extra>",
            "marker": {"size": 2.5, "opacity": 0.75},
        })
    layout = {"title": f"Phân cụm {len(df)} tin IT (PCA 3D, {len(traces)} cụm)", "height": 720,
              "scene": {"xaxis": {"title": "PC1"}, "yaxis": {"title": "PC2"}, "zaxis": {"title": "PC3"}},
              "legend": {"font": {"size": 11}}}
    html = (f'<!doctype html><meta charset="utf-8"><title>Cụm 3D</title><script src="{PLOTLY}"></script>'
            f'<div id="g"></div><script>Plotly.newPlot("g",{json.dumps(traces, ensure_ascii=False)},'
            f'{json.dumps(layout, ensure_ascii=False)},{{responsive:true}});</script>')
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(html, encoding="utf-8")
    return len(df)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=SRC)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    try:
        print(f"Đã vẽ {build(a.src, a.out)} điểm -> {a.out}")
    except FileNotFoundError as e:
        sys.exit(str(e))
