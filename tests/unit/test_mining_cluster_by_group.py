"""mining/clustering.cluster_by_group (SD3 theo 7 nhóm, người dùng chốt 24/11/2026) và luật nghề mới."""

import numpy as np
import pytest

from mining.clustering import cluster_by_group, is_generic_core, known_role, title_core
from mining.config import ClusteringParams
from mining.data_io import prepare_mining_data
from mining.job_group import SUB_ROLES
from mining.synthetic import make_synthetic_jobs

# nhóm nghề của dữ liệu giả -> job_family 11 nhóm hiện hành
FAMILY = {"Backend": "Web", "Frontend": "Web", "Fullstack": "Web", "Mobile": "Mobile", "Data Science/AI": "Data/AI",
          "DevOps/Cloud": "DevOps/Cloud", "Kiểm thử (QA/QC)": "Tester", "Phân tích nghiệp vụ (BA)": "Bridge"}


@pytest.fixture(scope="module")
def run():
    b = make_synthetic_jobs(n_jobs=900, seed=3)
    data = prepare_mining_data(b.golden, b.features, b.encoding_dict["skills"]["skills_map"])
    meta = data.meta.copy()
    meta["job_family"] = meta["job_family"].map(FAMILY)
    other = np.arange(0, 900, 25)  # 36 tin vào nhóm Khác
    meta.loc[other, "job_family"] = "Other"
    meta.loc[other, "job_title"] = ["Blockchain Engineer"] * 20 + ["Giám đốc công nghệ"] * 16
    out, m = cluster_by_group(data.skills, meta, ClusteringParams(stability_seeds=(42, 43)))
    return meta, out, m


def test_each_cluster_belongs_to_one_group(run):
    _, out, m = run
    c = out[out["cluster_id"] >= 0]
    assert (c.groupby("cluster_id")["job_group"].nunique() == 1).all()
    for pr in m["clusters"]:
        assert pr["cluster_name"].startswith(pr["job_group"] + " · ")
    assert len({pr["cluster_name"] for pr in m["clusters"]}) == len(m["clusters"])


def test_k_per_group_follows_listed_sub_roles(run):
    _, _, m = run
    for g, v in m["by_group"].items():
        if v["k"]:
            assert v["k"] == min(len(SUB_ROLES[g]), max(2, v["n"] // ClusteringParams().group_min_per_cluster))
    assert m["best_k"] == sum(v["k"] for v in m["by_group"].values())


def test_few_tools_and_other_are_not_clustered(run):
    meta, out, _ = run
    few = (meta["n_tools"] < 2).to_numpy()
    assert (out.loc[few, "cluster_id"] == -1).all() and not out.loc[few, "in_clustering"].any()
    assert (out.loc[few & (out["job_group"] != "Khác").to_numpy(), "sub_role"] == "Khác (JD ít thông tin)").all()
    oth = (out["job_group"] == "Khác").to_numpy()
    assert (out.loc[oth, "cluster_id"] == -1).all()
    assert out.loc[oth, "other_status"].notna().all() and out.loc[~oth, "other_status"].isna().all()


def test_every_job_has_a_place(run):
    meta, _, m = run
    cov = m["coverage"]
    assert cov["n_in_subclusters"] + cov["n_group_other_few_tools"] + cov["n_outside_groups"] == len(meta)


def test_min_cluster_share_is_within_group(run):
    _, _, m = run
    assert m["min_cluster_share_basis"] == "số tin của nhóm"
    assert m["min_cluster_share"] == min(pr["share_in_group"] for pr in m["clusters"])


def test_other_roles_counted_on_whole_data(run):
    _, _, m = run
    roles = {r["title_core"]: r for r in m["other"]["roles"]}
    assert roles["blockchain engineer"]["n_jobs"] == 20
    assert roles["giam doc cong nghe"]["verdict"] != "tiêu đề chung chung"


@pytest.mark.parametrize("title,core", [
    ("Senior Analytics Engineer (Data Engineer, Data Analyst)", "analytics engineer"),
    ("Senior/Lead - Data Engineering", "data engineering"),
    ("[Hà Nội] Chuyên gia Kiến trúc (SA)", "kien truc"),
    ("Full - Stack Developer / Lập Trình Viên", "fullstack developer"),
])
def test_title_core(title, core):
    assert title_core(title) == core


def test_known_role_and_generic():
    assert known_role("fullstack developer") == "Software · Full-stack"
    assert known_role("analytics engineer") is None
    assert is_generic_core("it") and is_generic_core("phan tich") and not is_generic_core("analytics engineer")
