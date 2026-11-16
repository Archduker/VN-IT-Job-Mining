"""scripts/plot_k_selection.py: Elbow + Silhouette từ mining_metrics.json; thiếu file thì lỗi, không vẽ giả."""

import json

import pytest

import plot_k_selection as p


def test_build_from_metrics(tmp_path):
    src, out = tmp_path / "m.json", tmp_path / "o.html"
    scan = [{"k": k, "inertia": 100.0 / k, "silhouette": 0.05 + k / 100, "davies_bouldin": 3.0 - k / 10} for k in range(2, 6)]
    src.write_text(json.dumps({"clustering": {"k_scan": scan, "best_k": 4}}), encoding="utf-8")
    assert p.build(src, out) == 4
    html = out.read_text(encoding="utf-8")
    assert "Elbow" in html and "Silhouette" in html and "[2, 3, 4, 5]" in html.replace('"', "")


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        p.build(tmp_path / "none.json", tmp_path / "o.html")
