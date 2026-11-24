"""scripts/build_mining_charts.py: dựng biểu đồ từ mining/artifacts thật, chỉ đọc (không ghi file)."""
import pytest

from scripts import build_mining_charts as bmc


@pytest.mark.needs_data("mining/artifacts/mining_metrics.json", "mining/artifacts/job_clusters.parquet")
def test_build_returns_all_charts_without_writing():
    charts = bmc.build()
    assert {"cluster_explorer", "cluster_table", "role_coverage", "group_stability", "skill_value"} == set(charts)
    for name, s in charts.items():
        assert s.lstrip().startswith(("<svg", "<style")), name
    ex = charts["cluster_explorer"]  # biểu đồ tương tác slide 11: 7 nhóm, dữ liệu nhúng, không gọi mạng
    assert '"groups":[' in ex and ex.count('"subs":') == 8  # 7 nhóm + nhóm Khác
    assert "http" not in ex.split("<script>", 1)[1]
    assert charts["cluster_table"].count('class="gt-card"') == 8
    assert charts["group_stability"].count("<title>") == 7


def test_vn_number_format():
    assert bmc.vn(0.0754, 3) == "0,075"
