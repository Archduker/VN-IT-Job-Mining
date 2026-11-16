"""scripts/plot_clusters_3d.py: HTML 3D từ job_clusters.parquet; thiếu file thì lỗi, không vẽ giả."""

import pandas as pd
import pytest

import plot_clusters_3d as p


def _df():
    return pd.DataFrame({"job_id": ["a", "b"], "job_title": ["Dev", "QA"], "job_family": ["Backend", "QA/QC"],
                         "cluster_id": [0, 1], "cluster_name": ["c0", "c1"], "pca_x": [0.1, 0.2],
                         "pca_y": [0.3, 0.4], "pca_z": [0.5, 0.6], "is_outlier": [False, True]})


def test_html_has_every_point_and_cluster(tmp_path):
    src, out = tmp_path / "c.parquet", tmp_path / "o.html"
    _df().to_parquet(src)
    n = p.build(src, out)
    html = out.read_text(encoding="utf-8")
    assert n == 2 and "scatter3d" in html and "c0" in html and "c1" in html and "Dev" in html


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        p.build(tmp_path / "none.parquet", tmp_path / "o.html")
