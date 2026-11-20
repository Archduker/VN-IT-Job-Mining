"""mining/clustering.py: không gian vector, chọn k, HDBSCAN/GLOSH, PCA 3D và hợp đồng job_clusters."""

import numpy as np
import pandas as pd
import pytest
from scipy import sparse

from mining.clustering import (
    build_vector_space,
    choose_k,
    cluster_jobs,
    profile_clusters,
)
from mining.config import JOB_FAMILY_OTHER, ClusteringParams
from mining.data_io import prepare_mining_data
from mining.synthetic import make_synthetic_jobs

# Cột bắt buộc theo scripts/sql/init_mart_schema.sql (bảng job_clusters)
MART_COLUMNS = ["job_id", "job_title", "job_family", "cluster_id", "cluster_name",
                "pca_x", "pca_y", "pca_z", "is_outlier", "glosh_outlier_score"]


@pytest.fixture(scope="module")
def result():
    b = make_synthetic_jobs(n_jobs=900, seed=3)
    data = prepare_mining_data(b.golden, b.features, b.encoding_dict["skills"]["skills_map"])
    params = ClusteringParams(k_min=4, k_max=10)
    out, m = cluster_jobs(data.skills, data.meta, params)
    return data, out, m


def test_output_matches_mart_contract(result):
    data, out, _ = result
    assert list(out.columns[:len(MART_COLUMNS)]) == MART_COLUMNS
    assert len(out) == data.n_jobs and out["job_id"].is_unique
    assert out[["pca_x", "pca_y", "pca_z"]].notna().all().all()
    assert out["is_outlier"].dtype == bool
    assert out["glosh_outlier_score"].between(0, 1).all()


def test_clusters_recover_planted_structure(result):
    _, _, m = result
    assert m["best_k"] >= 8  # ưu tiên >= 8 cụm theo spec 08
    assert m["silhouette"] > 0.28
    assert m["nmi_vs_job_family"] > 0.6
    names = " ".join(c["cluster_name"] for c in m["clusters"])
    assert "Mobile" in names and "Data Science/AI" in names
    assert sum(c["size"] for c in m["clusters"]) == 900
    assert len({c["cluster_name"] for c in m["clusters"]}) == len(m["clusters"])


def test_outlier_ratio_follows_quantile(result):
    _, out, m = result
    assert out["is_outlier"].mean() == pytest.approx(1 - ClusteringParams().glosh_outlier_quantile, abs=0.01)
    assert m["hdbscan"]["method"]  # ghi phương pháp GLOSH đã dùng
    assert 0 < m["pca_cumulative_variance_3d"] <= 1


def test_vector_space_rows_are_unit_norm():
    sk = pd.DataFrame({"A": [1, 0, 1], "B": [1, 1, 0]}, dtype=np.uint8)
    e5 = np.array([[0.5, 0.5], [1.0, 0.0], [0.0, 0.0]], dtype=np.float32)
    X = build_vector_space(sk, e5=e5)
    norms = np.sqrt(np.asarray(X.multiply(X).sum(axis=1)).ravel())
    assert np.allclose(norms, 1.0)


def test_choose_k_prefers_at_least_min_k():
    scan = pd.DataFrame({"k": [4, 6, 8, 10], "silhouette": [0.5, 0.4, 0.3, 0.35]})
    assert choose_k(scan, 8) == (10, "silhouette cao nhất trong k >= 8")
    assert choose_k(scan, 12)[0] == 4


def test_profile_top_skills_by_lift():
    sk = pd.DataFrame({"Java": [1, 1, 0, 0], "React": [0, 0, 1, 1], "Git": [1, 1, 1, 1]}, dtype=np.uint8)
    prof = profile_clusters(np.array([0, 0, 1, 1]), sk, pd.Series(["Backend"] * 2 + ["Frontend"] * 2))
    assert prof[0]["top_skills"][0]["skill"] == "Java"
    assert prof[1]["dominant_job_family"] == "Frontend" and prof[1]["job_family_purity"] == 1.0


def test_vector_space_with_e5_block_is_l2_and_has_all_columns():
    skills = pd.DataFrame(np.eye(4, dtype=np.uint8), columns=list("abcd"))
    e5 = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1], [0, 0, 0]], dtype=np.float32)  # dòng 4: JD không có bullet
    X = build_vector_space(skills, e5=e5, e5_weight=0.3)
    assert X.shape == (4, 4 + 3)
    norms = np.sqrt(np.asarray(X.multiply(X).sum(axis=1)).ravel())
    assert np.allclose(norms, 1.0)
    # không có e5 thì chỉ còn khối kỹ năng (TF-IDF đã gỡ, M0.6)
    assert build_vector_space(skills).shape == (4, 4)


def test_agglomerative_ward_clusters_and_reports_algorithm():
    b = make_synthetic_jobs(n_jobs=600, seed=3)
    data = prepare_mining_data(b.golden, b.features, b.encoding_dict["skills"]["skills_map"])
    out, m = cluster_jobs(data.skills, data.meta, ClusteringParams(k_min=4, k_max=8, algorithm="agglomerative"))
    assert m["algorithm"] == "agglomerative(ward)" and len(out) == data.n_jobs
    assert out["cluster_id"].nunique() == m["best_k"]
    out2, _ = cluster_jobs(data.skills, data.meta, ClusteringParams(k_min=4, k_max=8, algorithm="agglomerative"))
    assert (out["cluster_id"].to_numpy() == out2["cluster_id"].to_numpy()).all()  # tái lập


def test_gmm_clusters_reproducible_and_reports_algorithm():
    b = make_synthetic_jobs(n_jobs=600, seed=3)
    data = prepare_mining_data(b.golden, b.features, b.encoding_dict["skills"]["skills_map"])
    prm = ClusteringParams(k_min=4, k_max=6, algorithm="gmm")
    out, m = cluster_jobs(data.skills, data.meta, prm)
    out2, _ = cluster_jobs(data.skills, data.meta, prm)
    assert m["algorithm"] == "gmm(diag)" and len(out) == data.n_jobs
    assert (out["cluster_id"].to_numpy() == out2["cluster_id"].to_numpy()).all()


def test_fixed_k_overrides_selection_and_scan_still_reported():
    b = make_synthetic_jobs(n_jobs=600, seed=3)
    data = prepare_mining_data(b.golden, b.features, b.encoding_dict["skills"]["skills_map"])
    out, m = cluster_jobs(data.skills, data.meta, ClusteringParams(k_fixed=6, k_min=4, k_max=8))
    assert m["best_k"] == 6 and out["cluster_id"].nunique() == 6 and "cố định" in m["best_k_reason"]
    assert [r["k"] for r in m["k_scan"]] == [4, 5, 6, 7, 8] and all("inertia" in r for r in m["k_scan"])
    out2, m2 = cluster_jobs(data.skills, data.meta, ClusteringParams(k_fixed=12, k_min=4, k_max=8))  # k ngoài khoảng quét
    assert m2["best_k"] == 12 and 12 in [r["k"] for r in m2["k_scan"]]


def test_family_agreement_ignores_other():
    b = make_synthetic_jobs(n_jobs=600, seed=3)
    data = prepare_mining_data(b.golden, b.features, b.encoding_dict["skills"]["skills_map"])
    meta = data.meta.copy()
    meta.loc[meta.index[:100], "job_family"] = JOB_FAMILY_OTHER
    _, m = cluster_jobs(data.skills, meta, ClusteringParams(k_fixed=5, k_min=4, k_max=6))
    assert m["n_eval_family"] == 500 and m["n_family_other_excluded"] == 100
