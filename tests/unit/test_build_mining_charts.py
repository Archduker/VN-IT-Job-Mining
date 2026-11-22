"""scripts/build_mining_charts.py: dựng biểu đồ từ mining/artifacts thật, chỉ đọc (không ghi file)."""
import pytest

from scripts import build_mining_charts as bmc


@pytest.mark.needs_data("mining/artifacts/mining_metrics.json", "mining/artifacts/job_clusters.parquet")
def test_build_returns_all_charts_without_writing():
    charts = bmc.build()
    assert {"cluster_map", "cluster_family", "k_silhouette", "stability", "skill_value", "cluster_table"} <= set(charts)
    for name, s in charts.items():
        assert s.lstrip().startswith(("<svg", "<table", "<style")), name
    assert charts["cluster_map"].count("<title>C") == 10  # 10 ô, mỗi ô một cụm
    ex = charts["cluster_explorer"]  # biểu đồ tương tác slide 11: dữ liệu nhúng, không gọi mạng
    assert '"clusters":[' in ex and ex.count('"center":') == 10
    assert "http" not in ex.split("<script>", 1)[1]


def test_vn_number_format():
    assert bmc.vn(0.0754, 3) == "0,075"
