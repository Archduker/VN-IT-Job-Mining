"""Thuật toán 2: phân cụm việc làm (spec 07 §3, docs/tasks/06 bước 2).

Không gian vector v = [kỹ năng 0/1 || e5], chuẩn hóa L2. TF-IDF đã gỡ (spec 07 quyết định 1, M0.6, 20/11);
M3 sẽ đổi sang ba khối tool / concept / e5 `job` (docs/spec/mining/M3_phan_cum.md).
Ma trận kỹ năng thưa ~97% nên K-Means chạy trên không gian đã giảm chiều bằng TruncatedSVD
(giữ ~80% phương sai), sau đó chuẩn hóa L2 lại để khoảng cách Euclid tương đương cosine.
Silhouette và Davies-Bouldin đo trên chính không gian này (ghi rõ trong metrics).

- K-Means: quét k trong [k_min, k_max], chọn silhouette cao nhất trong các k >= preferred_min_k.
- HDBSCAN: điểm ngoại lai GLOSH; dùng thư viện `hdbscan` nếu có (GLOSH thật),
  nếu không thì sklearn.cluster.HDBSCAN với 1 - probabilities_ (xấp xỉ, ghi trong metrics).
- PCA 3 thành phần trên không gian gốc (trước SVD) để vẽ 2D/3D: pca_x, pca_y, pca_z.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.decomposition import PCA, TruncatedSVD
from sklearn.mixture import GaussianMixture
from sklearn.metrics import (
    adjusted_rand_score,
    davies_bouldin_score,
    normalized_mutual_info_score,
    silhouette_score,
)
from sklearn.preprocessing import normalize

from mining.config import JOB_FAMILY_OTHER, RANDOM_STATE, ClusteringParams

logger = logging.getLogger(__name__)

def build_vector_space(
    skills: pd.DataFrame,
    e5: np.ndarray | None = None,
    e5_weight: float = 0.3,
) -> sparse.csr_matrix:
    """[kỹ năng L2 * sqrt(1-we) || e5 L2 * sqrt(we)] rồi chuẩn hóa L2 từng dòng."""
    s = normalize(sparse.csr_matrix(skills.to_numpy(dtype=np.float32)))
    blocks = []
    if e5 is not None:
        blocks.append((normalize(sparse.csr_matrix(np.asarray(e5, dtype=np.float32))), e5_weight))
    if not blocks:
        return normalize(s).tocsr()
    w_skill = 1 - sum(w for _, w in blocks)
    v = sparse.hstack([s * np.sqrt(w_skill)] + [b * np.sqrt(w) for b, w in blocks]).tocsr()
    return normalize(v).tocsr()


def reduce_svd(X: sparse.spmatrix, variance_target: float, max_components: int,
               random_state: int = RANDOM_STATE) -> tuple[np.ndarray, dict[str, Any]]:
    n_comp = int(max(2, min(max_components, X.shape[1] - 1, X.shape[0] - 1)))
    svd = TruncatedSVD(n_components=n_comp, random_state=random_state)
    Z = svd.fit_transform(X)
    cum = np.cumsum(svd.explained_variance_ratio_)
    keep = int(np.searchsorted(cum, variance_target) + 1)
    keep = max(2, min(keep, n_comp))
    Zk = normalize(Z[:, :keep])
    return Zk, {"svd_components": keep, "svd_explained_variance": round(float(cum[keep - 1]), 4),
                "svd_max_components": n_comp}


def fit_labels(Z: np.ndarray, k: int, algorithm: str = "kmeans",
               random_state: int = RANDOM_STATE) -> tuple[np.ndarray, float | None]:
    """Nhãn cụm và inertia (chỉ K-Means có inertia; Ward trả None)."""
    if algorithm == "agglomerative":
        return AgglomerativeClustering(n_clusters=k, linkage="ward").fit_predict(Z), None
    if algorithm == "gmm":  # hiệp phương sai chéo: SVD nhiều chiều, đủ dữ liệu cho ma trận đầy đủ là không chắc
        return GaussianMixture(n_components=k, covariance_type="diag", n_init=3, random_state=random_state).fit_predict(Z), None
    km = KMeans(n_clusters=k, n_init=10, random_state=random_state)
    return km.fit_predict(Z), float(km.inertia_)


def scan_k(Z: np.ndarray, k_min: int, k_max: int, sample_size: int,
           random_state: int = RANDOM_STATE, algorithm: str = "kmeans") -> pd.DataFrame:
    rows = []
    k_max = min(k_max, len(Z) - 1)
    for k in range(k_min, k_max + 1):
        labels, inertia = fit_labels(Z, k, algorithm, random_state)
        if len(set(labels)) < 2:
            continue
        sil = silhouette_score(Z, labels, sample_size=min(sample_size, len(Z)), random_state=random_state)
        rows.append({"k": k, "inertia": inertia, "silhouette": float(sil),
                     "davies_bouldin": float(davies_bouldin_score(Z, labels))})
    return pd.DataFrame(rows)


def choose_k(scan: pd.DataFrame, preferred_min_k: int) -> tuple[int, str]:
    if scan.empty:
        raise ValueError("Không quét được k nào (quá ít tin).")
    pref = scan[scan["k"] >= preferred_min_k]
    if not pref.empty:
        best = pref.loc[pref["silhouette"].idxmax()]
        return int(best["k"]), f"silhouette cao nhất trong k >= {preferred_min_k}"
    best = scan.loc[scan["silhouette"].idxmax()]
    return int(best["k"]), "silhouette cao nhất (không có k nào >= ngưỡng)"


def run_hdbscan(Z: np.ndarray, min_cluster_size: int) -> tuple[np.ndarray, np.ndarray, str]:
    """Trả (nhãn, điểm GLOSH 0..1, phương pháp)."""
    try:
        import hdbscan  # type: ignore

        model = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size)
        labels = model.fit_predict(Z)
        scores = np.nan_to_num(np.asarray(model.outlier_scores_, dtype=float), nan=0.0)
        return labels, scores, "hdbscan.GLOSH"
    except ImportError:
        from sklearn.cluster import HDBSCAN

        model = HDBSCAN(min_cluster_size=min_cluster_size)
        labels = model.fit_predict(Z)
        scores = 1.0 - np.asarray(model.probabilities_, dtype=float)
        return labels, scores, "sklearn.HDBSCAN(1-probabilities_, xấp xỉ GLOSH)"


def profile_clusters(
    labels: np.ndarray,
    skills: pd.DataFrame,
    job_family: pd.Series,
    salary_mil: pd.Series | None = None,
    top_n: int = 8,
) -> list[dict[str, Any]]:
    """Mô tả cụm: kỹ năng đặc trưng (theo lift so với toàn bộ), nhóm nghề chiếm đa số, lương trung vị."""
    S = skills.to_numpy(dtype=float)
    p_all = S.mean(axis=0)
    fam = pd.Series(job_family).reset_index(drop=True).fillna(JOB_FAMILY_OTHER).astype(str)
    sal = pd.Series(salary_mil).reset_index(drop=True) if salary_mil is not None else None
    profiles = []
    used_names: dict[str, int] = {}
    for cid in sorted(set(labels)):
        mask = labels == cid
        p_c = S[mask].mean(axis=0)
        lift = np.divide(p_c, p_all, out=np.zeros_like(p_c), where=p_all > 0)
        # kỹ năng phổ biến trong cụm (>= 20%) xếp theo lift, bù bằng tần suất nếu thiếu
        order = [j for j in np.argsort(-lift) if p_c[j] >= 0.20]
        order += [j for j in np.argsort(-p_c) if j not in order and p_c[j] > 0]
        top = [{"skill": skills.columns[j], "share": round(float(p_c[j]), 3), "lift": round(float(lift[j]), 2)}
               for j in order[:top_n]]
        fam_counts = fam[mask].value_counts()
        dominant = str(fam_counts.index[0]) if len(fam_counts) else JOB_FAMILY_OTHER
        purity = float(fam_counts.iloc[0] / mask.sum()) if len(fam_counts) else 0.0
        head = "/".join(t["skill"] for t in top[:2]) or "không kỹ năng"
        name = f"{dominant} · {head}"
        used_names[name] = used_names.get(name, 0) + 1
        if used_names[name] > 1:
            name = f"{name} ({used_names[name]})"
        med = float(sal[mask].median()) if sal is not None and sal[mask].notna().any() else None
        profiles.append({
            "cluster_id": int(cid), "cluster_name": name, "size": int(mask.sum()),
            "share": round(float(mask.mean()), 4), "dominant_job_family": dominant,
            "job_family_purity": round(purity, 3), "top_skills": top,
            "median_salary_mil": round(med, 2) if med is not None else None,
        })
    return profiles


def cluster_jobs(
    skills: pd.DataFrame,
    meta: pd.DataFrame,
    params: ClusteringParams | None = None,
    random_state: int = RANDOM_STATE,
    e5: np.ndarray | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Chạy toàn bộ phần phân cụm. Trả (bảng job_clusters, metrics)."""
    p = params or ClusteringParams()
    X = build_vector_space(skills, e5=e5, e5_weight=p.e5_weight)

    Z, svd_info = reduce_svd(X, p.svd_variance_target, p.svd_max_components, random_state)
    k_lo, k_hi = (min(p.k_min, p.k_fixed), max(p.k_max, p.k_fixed)) if p.k_fixed else (p.k_min, p.k_max)
    scan = scan_k(Z, k_lo, k_hi, p.silhouette_sample_size, random_state, p.algorithm)
    if p.k_fixed:
        best_k, reason = int(p.k_fixed), f"k cố định = {p.k_fixed} theo người dùng (Silhouette chỉ để báo cáo)"
    else:
        best_k, reason = choose_k(scan, p.preferred_min_k)
    labels, _ = fit_labels(Z, best_k, p.algorithm, random_state)
    best_row = scan[scan["k"] == best_k].iloc[0]

    hdb_labels, glosh, glosh_method = run_hdbscan(Z, p.hdbscan_min_cluster_size)
    glosh_threshold = float(np.quantile(glosh, p.glosh_outlier_quantile))
    is_outlier = glosh >= glosh_threshold if glosh_threshold > 0 else np.zeros(len(glosh), dtype=bool)

    pca = PCA(n_components=3, random_state=random_state)
    coords = pca.fit_transform(X.toarray())

    profiles = profile_clusters(labels, skills, meta["job_family"], meta.get("salary_avg_mil"),
                                p.top_skills_per_cluster)
    names = {pr["cluster_id"]: pr["cluster_name"] for pr in profiles}
    fam = meta["job_family"].fillna(JOB_FAMILY_OTHER).astype(str).to_numpy()
    known = fam != JOB_FAMILY_OTHER  # tin Other (chưa xếp được nhóm) không dùng để so với family

    out = pd.DataFrame({
        "job_id": meta["job_id"].astype(str).to_numpy(),
        "job_title": meta["job_title"].to_numpy(),
        "job_family": fam,
        "cluster_id": labels.astype(int),
        "cluster_name": [names[int(c)] for c in labels],
        "pca_x": coords[:, 0].astype(float),
        "pca_y": coords[:, 1].astype(float),
        "pca_z": coords[:, 2].astype(float),
        "is_outlier": is_outlier.astype(bool),
        "glosh_outlier_score": glosh.astype(float),
        "hdbscan_label": hdb_labels.astype(int),
    })

    metrics = {
        "params": {k: getattr(p, k) for k in ("k_min", "k_max", "preferred_min_k", "svd_variance_target",
                                             "hdbscan_min_cluster_size",
                                             "glosh_outlier_quantile")},
        "vector_space": {"n_skill_features": int(skills.shape[1]),
                         "n_e5_dims": 0 if e5 is None else int(np.asarray(e5).shape[1]), **svd_info,
                         "silhouette_space": f"TruncatedSVD {svd_info['svd_components']} chiều, chuẩn hóa L2"},
        "k_scan": scan.round(4).to_dict(orient="records"),
        "algorithm": {"agglomerative": "agglomerative(ward)", "gmm": "gmm(diag)"}.get(p.algorithm, "kmeans"),
        "best_k": best_k, "best_k_reason": reason,
        "silhouette": round(float(best_row["silhouette"]), 4),
        "davies_bouldin": round(float(best_row["davies_bouldin"]), 4),
        "meets_silhouette_target": bool(best_row["silhouette"] >= p.silhouette_target),
        "davies_bouldin_target": p.davies_bouldin_target,
        "meets_davies_bouldin_target": bool(best_row["davies_bouldin"] < p.davies_bouldin_target),
        "meets_min_clusters": bool(best_k >= p.preferred_min_k),
        "ari_vs_job_family": round(float(adjusted_rand_score(fam[known], labels[known])), 4),
        "nmi_vs_job_family": round(float(normalized_mutual_info_score(fam[known], labels[known])), 4),
        "n_eval_family": int(known.sum()), "n_family_other_excluded": int((~known).sum()),
        "pca_explained_variance": [round(float(v), 4) for v in pca.explained_variance_ratio_],
        "pca_cumulative_variance_3d": round(float(pca.explained_variance_ratio_.sum()), 4),
        "hdbscan": {"method": glosh_method, "n_clusters": int(len(set(hdb_labels) - {-1})),
                    "noise_ratio": round(float((hdb_labels == -1).mean()), 4),
                    "glosh_threshold": round(glosh_threshold, 4),
                    "outlier_ratio": round(float(is_outlier.mean()), 4)},
        "clusters": profiles,
    }
    return out, metrics
