"""M3: nhóm việc cho SD3 câu 3.1, 3.2 (docs/spec/mining/M3_phan_cum.md).

- Tập tin (M3.1b): chỉ tin có `n_tools + n_concepts >= 1`; tin còn lại vẫn có dòng trong `job_clusters`
  với `in_clustering = false`, `cluster_id = -1`, điểm GLOSH null.
- Vector (M3.1a): ba khối K-tool (`skill__`), K-concept (`concept__`), e5 khóa `job`; mỗi khối chuẩn hóa L2
  theo dòng rồi nhân √trọng số (người dùng chốt 20/11, 1.D: 0,15 / 0,15 / 0,7), chuẩn hóa L2 lại. Không dùng `job_family`.
- TruncatedSVD (~80% phương sai, tối đa 60) → L2; K-Means k = 10, n_init 50 (2.B; quét 2–20 với n_init 10 chỉ để báo cáo); HDBSCAN + GLOSH.
- Độ ổn định (M3.7): ARI giữa 5 seed. Hồ sơ cụm (M3.8): công cụ, khái niệm, tiêu đề, cấp, `n_tools`, lương.
- 3.2 (M3.9, M3.10): bảng chéo cụm × job_family; nghề lai, nghề ngách, tin có vẻ gán sai (`family_mismatch`).
- PCA 3 thành phần trên không gian gốc (trước SVD) để vẽ: pca_x, pca_y, pca_z.
"""

from __future__ import annotations

import logging
import re
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

def build_block_space(blocks: list[tuple[Any, float]]) -> sparse.csr_matrix:
    """[khối_1 L2 · √w_1 || khối_2 L2 · √w_2 || …] rồi chuẩn hóa L2 từng dòng.

    Trọng số của các khối có mặt được chia cho tổng (để tổng = 1). Dòng toàn 0 của một khối giữ 0, nên
    dòng đủ mọi khối có phần năng lượng của khối i đúng bằng w_i."""
    blocks = [(b, w) for b, w in blocks if b is not None and np.asarray(b.shape)[1] > 0 and w > 0]
    if not blocks:
        raise ValueError("Không có khối nào để dựng không gian vector.")
    tot = sum(w for _, w in blocks)
    parts = []
    for b, w in blocks:
        m = b if sparse.issparse(b) else sparse.csr_matrix(np.asarray(b, dtype=np.float32))
        parts.append(normalize(sparse.csr_matrix(m, dtype=np.float32)) * np.sqrt(w / tot))
    return normalize(sparse.hstack(parts).tocsr()).tocsr()


def build_vector_space(
    skills: pd.DataFrame,
    e5: np.ndarray | None = None,
    e5_weight: float = 0.3,
) -> sparse.csr_matrix:
    """Bản hai khối cũ: [kỹ năng · √(1-we) || e5 · √we]. M3 dùng `build_block_space` với ba khối."""
    blocks = [(skills.to_numpy(dtype=np.float32), 1 - (e5_weight if e5 is not None else 0.0))]
    if e5 is not None:
        blocks.append((np.asarray(e5, dtype=np.float32), e5_weight))
    return build_block_space(blocks)


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
               random_state: int = RANDOM_STATE, n_init: int = 10) -> tuple[np.ndarray, float | None]:
    """Nhãn cụm và inertia (chỉ K-Means có inertia; Ward trả None). `n_init` chỉ dùng cho K-Means."""
    if algorithm == "agglomerative":
        return AgglomerativeClustering(n_clusters=k, linkage="ward").fit_predict(Z), None
    if algorithm == "gmm":  # hiệp phương sai chéo: SVD nhiều chiều, đủ dữ liệu cho ma trận đầy đủ là không chắc
        return GaussianMixture(n_components=k, covariance_type="diag", n_init=3, random_state=random_state).fit_predict(Z), None
    km = KMeans(n_clusters=k, n_init=n_init, random_state=random_state)
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


def _lift_top(mat: pd.DataFrame | None, mask: np.ndarray, top_n: int, min_share: float = 0.20) -> list[dict]:
    """Kỹ năng phổ biến trong cụm (>= min_share) xếp theo lift so với toàn bộ, bù bằng tần suất nếu thiếu."""
    if mat is None or mat.shape[1] == 0:
        return []
    S = mat.to_numpy(dtype=float)
    p_all = S.mean(axis=0)
    p_c = S[mask].mean(axis=0)
    lift = np.divide(p_c, p_all, out=np.zeros_like(p_c), where=p_all > 0)
    order = [j for j in np.argsort(-lift, kind="stable") if p_c[j] >= min_share]
    order += [j for j in np.argsort(-p_c, kind="stable") if j not in order and p_c[j] > 0]
    return [{"skill": mat.columns[j], "share": round(float(p_c[j]), 3), "lift": round(float(lift[j]), 2)}
            for j in order[:top_n]]


def profile_clusters(
    labels: np.ndarray,
    skills: pd.DataFrame,
    job_family: pd.Series,
    salary_mil: pd.Series | None = None,
    top_n: int = 8,
    concepts: pd.DataFrame | None = None,
    meta: pd.DataFrame | None = None,
    min_salary_n: int = 30,
    params: ClusteringParams | None = None,
) -> list[dict[str, Any]]:
    """Hồ sơ cụm (M3.8): công cụ và khái niệm đặc trưng (theo lift), nghề đa số, top tiêu đề, phân bố cấp,
    trung vị n_tools / n_concepts, trung vị lương (chỉ khi >= min_salary_n tin có lương)."""
    fam = pd.Series(job_family).reset_index(drop=True).fillna(JOB_FAMILY_OTHER).astype(str)
    sal = pd.Series(salary_mil).reset_index(drop=True) if salary_mil is not None else None
    m = meta.reset_index(drop=True) if meta is not None else None
    p = params or ClusteringParams()
    profiles = []
    used_names: dict[str, int] = {}
    for cid in sorted(set(labels)):
        mask = labels == cid
        top = _lift_top(skills, mask, top_n)
        fam_counts = fam[mask].value_counts()
        dominant = str(fam_counts.index[0]) if len(fam_counts) else JOB_FAMILY_OTHER
        purity = float(fam_counts.iloc[0] / mask.sum()) if len(fam_counts) else 0.0
        head = "/".join(t["skill"] for t in top[:2]) or "không công cụ"
        if m is not None and "n_tools" in m:
            med_tools = float(pd.to_numeric(m.loc[mask, "n_tools"], errors="coerce").median())
        else:
            med_tools = float(np.median(np.asarray(skills.loc[mask].sum(axis=1)).ravel()))
        if med_tools <= p.name_few_tools_median:
            prefix = "Ít công cụ"
        elif purity < p.name_min_purity:
            prefix = "Hỗn hợp"
        else:
            prefix = dominant
        name = f"{prefix} · {head}"
        used_names[name] = used_names.get(name, 0) + 1
        if used_names[name] > 1:
            name = f"{name} ({used_names[name]})"
        s_c = sal[mask].dropna() if sal is not None else pd.Series(dtype=float)
        prof = {
            "cluster_id": int(cid), "cluster_name": name, "size": int(mask.sum()),
            "share": round(float(mask.mean()), 4), "dominant_job_family": dominant,
            "job_family_purity": round(purity, 3), "top_skills": top,
            "top_concepts": _lift_top(concepts, mask, 5),
            "median_salary_mil": round(float(s_c.median()), 2) if len(s_c) >= min_salary_n else None,
            "n_salary": int(len(s_c)),
        }
        if m is not None:
            if "job_title" in m:
                prof["top_titles"] = [{"title": str(k), "n": int(v)} for k, v in
                                      m.loc[mask, "job_title"].astype(str).str.strip().value_counts().head(5).items()]
            if "seniority" in m:
                prof["seniority"] = {str(k): round(float(v), 3) for k, v in
                                     m.loc[mask, "seniority"].astype(str).value_counts(normalize=True).items()}
            for c in ("n_tools", "n_concepts"):
                if c in m:
                    prof[f"median_{c}"] = float(pd.to_numeric(m.loc[mask, c], errors="coerce").median())
        profiles.append(prof)
    return profiles


def seed_stability(Z: np.ndarray, k: int, seeds: tuple[int, ...], algorithm: str = "kmeans",
                   n_init: int = 10) -> dict[str, Any]:
    """M3.7: ARI của nhãn ở mỗi seed so với seed đầu tiên (cùng n_init với lần fit chính)."""
    base, _ = fit_labels(Z, k, algorithm, seeds[0], n_init)
    aris = {int(s): round(float(adjusted_rand_score(base, fit_labels(Z, k, algorithm, s, n_init)[0])), 4)
            for s in seeds[1:]}
    vals = list(aris.values())
    return {"seeds": [int(s) for s in seeds], "ari_vs_first": aris,
            "ari_mean": round(float(np.mean(vals)), 4) if vals else None,
            "ari_min": round(float(np.min(vals)), 4) if vals else None, "n_init": int(n_init)}


def skill_count_violations(profiles: list[dict], overall_median: float, p: ClusteringParams) -> list[int]:
    """M3.8: cụm gom tin không công cụ (trung vị n_tools < 1) là cụm tách theo số kỹ năng.

    Người dùng chốt 20/11 (3.B): chỉ kiểm phía dưới. Phía trên (> 2 × trung vị) gắn cờ nhầm Backend, DevOps
    thật (trung vị 12, 11 so với 5); `skill_count_ratio_max` = None thì bỏ kiểm phía trên."""
    out = []
    for pr in profiles:
        med = pr.get("median_n_tools")
        if med is None:
            continue
        upper = p.skill_count_ratio_max is not None and med > p.skill_count_ratio_max * overall_median
        if med < 1 or upper:
            out.append(int(pr["cluster_id"]))
    return out


def family_crosstab(labels: np.ndarray, fam: np.ndarray) -> pd.DataFrame:
    """M3.9: cụm × job_family, số tin và tỷ lệ theo hàng (trong cụm)."""
    ct = pd.DataFrame({"cluster_id": labels, "job_family": fam}).value_counts().rename("n").reset_index()
    ct["share"] = (ct["n"] / ct.groupby("cluster_id")["n"].transform("sum")).round(4)
    return ct.sort_values(["cluster_id", "n", "job_family"], ascending=[True, False, True]).reset_index(drop=True)


def _shares(ct: pd.DataFrame) -> pd.DataFrame:
    if "share" in ct:
        return ct
    ct = ct.copy()
    ct["share"] = ct["n"] / ct.groupby("cluster_id")["n"].transform("sum")
    return ct


def hybrid_clusters(ct: pd.DataFrame, p: ClusteringParams) -> list[int]:
    """M3.10 nghề lai: cụm không có nghề nào > hybrid_max_share và có >= 2 nghề >= hybrid_min_second."""
    ct = _shares(ct)
    out = []
    for cid, g in ct.groupby("cluster_id"):
        if g["share"].max() <= p.hybrid_max_share and (g["share"] >= p.hybrid_min_second).sum() >= 2:
            out.append(int(cid))
    return out


def niche_families(ct: pd.DataFrame, profiles: list[dict], p: ClusteringParams, n_jobs: int | None = None) -> dict[str, Any]:
    """M3.10 nghề ngách: (a) nghề chiếm >= niche_family_share ở >= 2 cụm (bị tách thành nhóm con);
    (b) cụm nhỏ (< niche_small_share số tin) có >= niche_min_skills công cụ lift >= niche_min_lift (share >= 20%)."""
    ct = _shares(ct)
    dom = ct[ct["share"] >= p.niche_family_share]
    split = {str(f): sorted(int(c) for c in g["cluster_id"]) for f, g in dom.groupby("job_family") if g["cluster_id"].nunique() >= 2}
    small = []
    total = n_jobs or int(ct["n"].sum())
    for pr in profiles:
        n_lift = sum(1 for s in pr.get("top_skills", []) if s["lift"] >= p.niche_min_lift and s["share"] >= 0.20)
        if pr["size"] / total < p.niche_small_share and n_lift >= p.niche_min_skills:
            small.append(int(pr["cluster_id"]))
    return {"split_families": split, "small_specialised_clusters": small}


def flag_family_mismatch(labels: np.ndarray, fam: np.ndarray, dist: np.ndarray, p: ClusteringParams) -> np.ndarray:
    """M3.10 có vẻ gán sai: nghề đa số của cụm chiếm >= mismatch_majority, tin mang nghề khác, nghề đó chiếm
    < mismatch_family_share cụm, và tin nằm gần tâm (khoảng cách <= phân vị mismatch_dist_q của cụm)."""
    labels, fam, dist = np.asarray(labels), np.asarray(fam).astype(str), np.asarray(dist, dtype=float)
    out = np.zeros(len(labels), dtype=bool)
    for cid in np.unique(labels):
        m = labels == cid
        vc = pd.Series(fam[m]).value_counts(normalize=True)
        if vc.iloc[0] < p.mismatch_majority:
            continue
        major = vc.index[0]
        q = np.quantile(dist[m], p.mismatch_dist_q)
        share = pd.Series(fam).map(vc).to_numpy()
        out |= m & (fam != major) & (fam != JOB_FAMILY_OTHER) & (share < p.mismatch_family_share) & (dist <= q)
    return out


def _salary(meta: pd.DataFrame) -> pd.Series:
    col = "salary_target_m" if "salary_target_m" in meta else "salary_avg_mil"
    sal = pd.to_numeric(meta[col], errors="coerce") if col in meta else pd.Series(np.nan, index=meta.index)
    if "salary_outlier" in meta:
        sal = sal.where(~meta["salary_outlier"].astype(bool))
    return sal.reset_index(drop=True)


def cluster_jobs(
    skills: pd.DataFrame,
    meta: pd.DataFrame,
    params: ClusteringParams | None = None,
    random_state: int = RANDOM_STATE,
    e5: np.ndarray | None = None,
    concepts: pd.DataFrame | None = None,
    compare_without_e5: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Chạy toàn bộ M3. Trả (bảng job_clusters cho mọi tin, metrics)."""
    p = params or ClusteringParams()
    meta = meta.reset_index(drop=True)
    skills = skills.reset_index(drop=True)
    concepts = concepts.reset_index(drop=True) if concepts is not None and concepts.shape[1] else None
    n_all = len(meta)

    # M3.1b: bỏ tin không có kỹ năng kỹ thuật nào (công cụ + khái niệm)
    if {"n_tools", "n_concepts"} <= set(meta.columns):
        tech = pd.to_numeric(meta["n_tools"], errors="coerce").fillna(0) + pd.to_numeric(meta["n_concepts"], errors="coerce").fillna(0)
        keep = (tech >= 1).to_numpy()
    else:
        keep = np.ones(n_all, dtype=bool)
    mk = meta[keep].reset_index(drop=True)
    sk = skills[keep].reset_index(drop=True)
    ck = concepts[keep].reset_index(drop=True) if concepts is not None else None
    ek = np.asarray(e5)[keep] if e5 is not None else None

    w = p.block_weights
    blocks = [(sk.to_numpy(dtype=np.float32), w["tool"])]
    used = {"tool": w["tool"]}
    if ck is not None:
        blocks.append((ck.to_numpy(dtype=np.float32), w["concept"]))
        used["concept"] = w["concept"]
    if ek is not None:
        blocks.append((ek.astype(np.float32), w["e5"]))
        used["e5"] = w["e5"]
    X = build_block_space(blocks)

    Z, svd_info = reduce_svd(X, p.svd_variance_target, p.svd_max_components, random_state)
    k_lo, k_hi = (min(p.k_min, p.k_fixed), max(p.k_max, p.k_fixed)) if p.k_fixed else (p.k_min, p.k_max)
    scan = scan_k(Z, k_lo, k_hi, p.silhouette_sample_size, random_state, p.algorithm)
    if p.k_fixed:
        best_k, reason = int(p.k_fixed), f"k cố định = {p.k_fixed} theo người dùng (Silhouette chỉ để báo cáo)"
    else:
        best_k, reason = choose_k(scan, p.preferred_min_k)
    labels, _ = fit_labels(Z, best_k, p.algorithm, random_state, p.kmeans_n_init)
    best_row = scan[scan["k"] == best_k].iloc[0]
    stability = seed_stability(Z, best_k, tuple(p.stability_seeds), p.algorithm, p.kmeans_n_init)

    hdb_labels, glosh, glosh_method = run_hdbscan(Z, p.hdbscan_min_cluster_size)
    glosh_threshold = float(np.quantile(glosh, p.glosh_outlier_quantile))
    is_outlier = glosh >= glosh_threshold if glosh_threshold > 0 else np.zeros(len(glosh), dtype=bool)

    pca = PCA(n_components=3, random_state=random_state)
    coords = pca.fit_transform(X.toarray())

    cent = np.vstack([Z[labels == c].mean(axis=0) for c in range(best_k)]) if p.algorithm == "kmeans" else \
        np.vstack([Z[labels == c].mean(axis=0) for c in sorted(set(labels))])
    lab_idx = {c: i for i, c in enumerate(sorted(set(labels)))}
    dist = np.linalg.norm(Z - cent[[lab_idx[c] for c in labels]], axis=1)

    sal = _salary(mk)
    profiles = profile_clusters(labels, sk, mk["job_family"], sal, p.top_skills_per_cluster, concepts=ck, meta=mk,
                                params=p)
    names = {pr["cluster_id"]: pr["cluster_name"] for pr in profiles}
    fam = mk["job_family"].fillna(JOB_FAMILY_OTHER).astype(str).to_numpy()
    known = fam != JOB_FAMILY_OTHER  # tin Other (chưa xếp được nhóm) không dùng để so với family
    ct = family_crosstab(labels, fam)
    hybrid = hybrid_clusters(ct, p)
    niche = niche_families(ct, profiles, p, n_jobs=len(mk))
    mismatch = flag_family_mismatch(labels, fam, dist, p)
    overall_tools = float(pd.to_numeric(mk["n_tools"], errors="coerce").median()) if "n_tools" in mk else float(sk.sum(axis=1).median())
    violations = skill_count_violations(profiles, overall_tools, p)

    def full(values: np.ndarray, fill: Any, dtype: Any = None) -> np.ndarray:
        arr = np.full(n_all, fill, dtype=dtype if dtype is not None else np.asarray(values).dtype)
        arr[keep] = values
        return arr

    fam_all = meta["job_family"].fillna(JOB_FAMILY_OTHER).astype(str).to_numpy()
    out = pd.DataFrame({
        "job_id": meta["job_id"].astype(str).to_numpy(),
        "job_title": meta["job_title"].to_numpy(),
        "job_family": fam_all,
        "cluster_id": full(labels.astype(int), -1, int),
        "cluster_name": full(np.array([names[int(c)] for c in labels], dtype=object), None, object),
        "pca_x": full(coords[:, 0].astype(float), np.nan, float),
        "pca_y": full(coords[:, 1].astype(float), np.nan, float),
        "pca_z": full(coords[:, 2].astype(float), np.nan, float),
        "is_outlier": full(is_outlier.astype(bool), False, bool),
        "glosh_outlier_score": full(glosh.astype(float), np.nan, float),
        "hdbscan_label": full(hdb_labels.astype(int), -2, int),
        "in_clustering": keep,
        "dist_to_centroid": full(dist.astype(float), np.nan, float),
        "family_mismatch": full(mismatch.astype(bool), False, bool),
    })

    sizes = np.bincount([lab_idx[c] for c in labels])
    metrics = {
        "params": {k: getattr(p, k) for k in ("k_min", "k_max", "preferred_min_k", "svd_variance_target",
                                             "hdbscan_min_cluster_size", "glosh_outlier_quantile")},
        "n_jobs": int(n_all), "n_clustered": int(keep.sum()),
        "n_dropped_no_technical_skill": int((~keep).sum()),
        "vector_space": {"block_weights": used, "n_skill_features": int(sk.shape[1]),
                         "n_concept_features": 0 if ck is None else int(ck.shape[1]),
                         "n_e5_dims": 0 if ek is None else int(ek.shape[1]), **svd_info,
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
        "stability": stability,
        "meets_stability_target": bool((stability["ari_mean"] or 0) >= p.stability_ari_target),
        "min_cluster_share": round(float(sizes.min() / len(mk)), 4),
        "meets_min_cluster_share": bool(sizes.min() / len(mk) >= p.min_cluster_share),
        "median_n_tools_overall": overall_tools,
        "skill_count_violations": violations,
        "ari_vs_job_family": round(float(adjusted_rand_score(fam[known], labels[known])), 4),
        "nmi_vs_job_family": round(float(normalized_mutual_info_score(fam[known], labels[known])), 4),
        "n_eval_family": int(known.sum()), "n_family_other_excluded": int((~known).sum()),
        "crosstab": ct.to_dict(orient="records"),
        "hybrid_clusters": hybrid, "niche": niche,
        "n_family_mismatch": int(mismatch.sum()),
        "pca_explained_variance": [round(float(v), 4) for v in pca.explained_variance_ratio_],
        "pca_cumulative_variance_3d": round(float(pca.explained_variance_ratio_.sum()), 4),
        "hdbscan": {"method": glosh_method, "n_clusters": int(len(set(hdb_labels) - {-1})),
                    "noise_ratio": round(float((hdb_labels == -1).mean()), 4),
                    "glosh_threshold": round(glosh_threshold, 4),
                    "outlier_ratio": round(float(is_outlier.mean()), 4)},
        "clusters": profiles,
    }
    if ek is not None and compare_without_e5:
        q = ClusteringParams(**{**p.__dict__, "block_weights": {"tool": w["tool"], "concept": w["concept"], "e5": w["e5"]}})
        _, m0 = cluster_jobs(skills, meta, q, random_state, e5=None, concepts=concepts, compare_without_e5=False)
        metrics["without_e5"] = {k: m0[k] for k in ("best_k", "silhouette", "davies_bouldin",
                                                    "ari_vs_job_family", "nmi_vs_job_family")}
        metrics["without_e5"]["block_weights"] = m0["vector_space"]["block_weights"]
    return out, metrics


def _subrole_name(group: str, roles: pd.Series, head: str, min_share: float) -> tuple[str | None, float]:
    """Vai trò con chiếm >= min_share tin của cụm (theo từ khóa tiêu đề), và tỷ lệ đó."""
    vc = roles.dropna().value_counts()
    share = float(vc.iloc[0] / len(roles)) if len(vc) else 0.0
    return (str(vc.index[0]) if share >= min_share else None), share


OTHER_IN_GROUP = "Khác (JD ít thông tin)"


def cluster_by_group(
    skills: pd.DataFrame,
    meta: pd.DataFrame,
    params: ClusteringParams | None = None,
    random_state: int = RANDOM_STATE,
    e5: np.ndarray | None = None,
    concepts: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """SD3 theo 7 nhóm (người dùng chốt 24/11): cụm con trong từng nhóm `job_group`.

    Không gian vector như `cluster_jobs` nhưng chỉ dựng trên tin có >= group_min_tools công cụ (cả nhóm Khác).
    Mỗi nhóm chạy K-Means riêng, k = số vai trò con đã liệt kê; tin Khác không vào cụm (xem `classify_other`).
    HDBSCAN/GLOSH và PCA tính trên toàn bộ không gian để M4 và hình vẽ dùng như trước.
    """
    from mining.job_group import GROUPS, OTHER, SUB_ROLES, add_job_group

    p = params or ClusteringParams()
    meta = meta.reset_index(drop=True)
    skills = skills.reset_index(drop=True)
    if "job_group" not in meta:
        meta = add_job_group(meta, skills)
    concepts = concepts.reset_index(drop=True) if concepts is not None and concepts.shape[1] else None
    n_all = len(meta)
    keep = (pd.to_numeric(meta["n_tools"], errors="coerce").fillna(0) >= p.group_min_tools).to_numpy()
    mk = meta[keep].reset_index(drop=True)
    sk = skills[keep].reset_index(drop=True)
    ck = concepts[keep].reset_index(drop=True) if concepts is not None else None
    ek = np.asarray(e5)[keep] if e5 is not None else None

    w = p.group_block_weights
    blocks, used = [(sk.to_numpy(dtype=np.float32), w["tool"])], {"tool": w["tool"]}
    if ck is not None:
        blocks.append((ck.to_numpy(dtype=np.float32), w["concept"]))
        used["concept"] = w["concept"]
    if ek is not None and w["e5"] > 0:
        blocks.append((ek.astype(np.float32), w["e5"]))
        used["e5"] = w["e5"]
    else:
        ek = None  # e5 trọng số 0 (chốt 24/11): không dựng khối, metrics không ghi số chiều e5
    Z, svd_info = reduce_svd(build_block_space(blocks), p.svd_variance_target, p.svd_max_components, random_state)

    grp = mk["job_group"].to_numpy()
    sal = _salary(mk)
    labels = np.full(len(mk), -1, dtype=int)
    dist = np.full(len(mk), np.nan)
    names: dict[int, str] = {}
    sub_role = np.array([None] * len(mk), dtype=object)
    profiles, by_group = [], {}
    offset = 0
    for g in GROUPS:
        idx = np.flatnonzero(grp == g)
        if len(idx) < 2 * p.group_min_per_cluster:
            by_group[g] = {"n": int(len(idx)), "k": 0, "note": "quá ít tin để chia cụm con"}
            continue
        k_list = len(SUB_ROLES[g])
        k = int(min(k_list, max(2, len(idx) // p.group_min_per_cluster)))
        Zg = Z[idx]
        lab, _ = fit_labels(Zg, k, p.algorithm, random_state, p.kmeans_n_init)
        stab = seed_stability(Zg, k, tuple(p.stability_seeds), p.algorithm, p.kmeans_n_init)
        cent = np.vstack([Zg[lab == c].mean(axis=0) for c in range(k)])
        dist[idx] = np.linalg.norm(Zg - cent[lab], axis=1)
        sub_meta = mk.iloc[idx].reset_index(drop=True)
        prof_g = profile_clusters(lab, sk.iloc[idx].reset_index(drop=True), sub_meta["job_family"],
                                  sal.iloc[idx].reset_index(drop=True), p.top_skills_per_cluster,
                                  concepts=None if ck is None else ck.iloc[idx].reset_index(drop=True),
                                  meta=sub_meta, params=p)
        seen: dict[str, int] = {}
        for pr in prof_g:
            c = pr["cluster_id"]
            m_c = lab == c
            head = "/".join(t["skill"] for t in pr["top_skills"][:2]) or "không công cụ"
            role, share = _subrole_name(g, sub_meta.loc[m_c, "sub_role_title"], head, p.subrole_min_share)
            base = f"{g} · {role}" if role else f"{g} · {head}"
            seen[base] = seen.get(base, 0) + 1
            pr.update({"cluster_id": offset + c, "job_group": g, "sub_role": role, "sub_role_matched": role is not None,
                       "sub_role_share": round(share, 3), "head_skills": head,
                       "share_in_group": round(float(m_c.mean()), 4)})
            pr["cluster_name"] = base
            profiles.append(pr)
            sub_role[idx[m_c]] = role or f"chưa khớp ({head})"
        # tên trùng trong nhóm (hai cụm cùng vai trò): thêm 2 công cụ đặc trưng để phân biệt
        for pr in profiles:
            if pr["job_group"] == g and seen.get(pr["cluster_name"], 0) > 1:
                pr["cluster_name"] = f"{pr['cluster_name']} · {pr['head_skills']}"
        for pr in profiles:
            if pr["job_group"] == g:
                names[pr["cluster_id"]] = pr["cluster_name"]
        labels[idx] = lab + offset
        sil = silhouette_score(Zg, lab, sample_size=min(p.silhouette_sample_size, len(Zg)), random_state=random_state)
        by_group[g] = {"n": int(len(idx)), "k": k, "k_listed": k_list, "stability": stab,
                       "meets_stability_target": bool((stab["ari_mean"] or 0) >= p.stability_ari_target),
                       "silhouette": round(float(sil), 4),
                       "n_sub_role_matched": sum(pr["sub_role_matched"] for pr in profiles if pr["job_group"] == g)}
        offset += k

    hdb_labels, glosh, glosh_method = run_hdbscan(Z, p.hdbscan_min_cluster_size)
    glosh_threshold = float(np.quantile(glosh, p.glosh_outlier_quantile))
    is_outlier = glosh >= glosh_threshold if glosh_threshold > 0 else np.zeros(len(glosh), dtype=bool)
    pca = PCA(n_components=3, random_state=random_state)
    coords = pca.fit_transform(Z)

    inc = labels >= 0
    sil_all = silhouette_score(Z[inc], labels[inc], sample_size=min(p.silhouette_sample_size, int(inc.sum())),
                               random_state=random_state)
    db_all = davies_bouldin_score(Z[inc], labels[inc])
    fam = mk["job_family"].fillna(JOB_FAMILY_OTHER).astype(str).to_numpy()
    ct = family_crosstab(labels[inc], fam[inc])
    sizes = np.bincount(labels[inc])
    overall_tools = float(pd.to_numeric(mk["n_tools"], errors="coerce").median())
    violations = skill_count_violations(profiles, overall_tools, p)
    n_g = {g: v["n"] for g, v in by_group.items() if v.get("k")}
    min_share_g = min(pr["share_in_group"] for pr in profiles)
    ari_w = sum(by_group[g]["stability"]["ari_mean"] * n for g, n in n_g.items()) / sum(n_g.values())

    def full(values: np.ndarray, fill: Any, dtype: Any = None) -> np.ndarray:
        arr = np.full(n_all, fill, dtype=dtype if dtype is not None else np.asarray(values).dtype)
        arr[keep] = values
        return arr

    # Mọi tin đều có chỗ (người dùng chốt 25/11): tin của 7 nhóm ghi < group_min_tools công cụ vào mục "Khác" của nhóm đó
    few = np.where(meta["job_group"].to_numpy() == OTHER, None, OTHER_IN_GROUP)
    out = pd.DataFrame({
        "job_id": meta["job_id"].astype(str).to_numpy(),
        "job_title": meta["job_title"].to_numpy(),
        "job_family": meta["job_family"].fillna(JOB_FAMILY_OTHER).astype(str).to_numpy(),
        "cluster_id": full(labels, -1, int),
        "cluster_name": full(np.array([names.get(int(c)) for c in labels], dtype=object), None, object),
        "pca_x": full(coords[:, 0].astype(float), np.nan, float),
        "pca_y": full(coords[:, 1].astype(float), np.nan, float),
        "pca_z": full(coords[:, 2].astype(float), np.nan, float),
        "is_outlier": full(is_outlier.astype(bool), False, bool),
        "glosh_outlier_score": full(glosh.astype(float), np.nan, float),
        "hdbscan_label": full(hdb_labels.astype(int), -2, int),
        "in_clustering": full(inc, False, bool),
        "dist_to_centroid": full(dist, np.nan, float),
        "family_mismatch": np.zeros(n_all, dtype=bool),
        "job_group": meta["job_group"].to_numpy(),
        "job_group_source": meta["job_group_source"].to_numpy(),
        "sub_role_title": meta["sub_role_title"].to_numpy(),
    })
    sr = np.array(few, dtype=object)
    sub_role[(labels < 0) & (grp != OTHER)] = "Khác (nhóm quá ít tin)"  # nhóm không đủ tin để chia cụm con
    sr[keep] = sub_role
    out["sub_role"] = sr
    grp_other = ((out["cluster_id"] < 0) & (out["job_group"] != OTHER)).to_numpy()  # tin 7 nhóm không vào cụm con
    other_cols, other_m = classify_other(meta, keep, Z, labels, sk, names,
                                         {pr["cluster_id"]: pr["sub_role"] for pr in profiles}, p)
    out = pd.concat([out, other_cols], axis=1)

    metrics = {
        "method": "cluster_by_group",
        "params": {k: getattr(p, k) for k in ("group_min_tools", "group_min_per_cluster", "subrole_min_share",
                                             "svd_variance_target", "hdbscan_min_cluster_size",
                                             "glosh_outlier_quantile", "kmeans_n_init")},
        "n_jobs": int(n_all), "n_in_space": int(keep.sum()), "n_clustered": int(inc.sum()),
        "n_few_tools": int((~keep).sum()), "n_other_in_space": int((grp == OTHER).sum()),
        # 3.718 = tin trong cụm con + tin ít công cụ ở mục "Khác" của 7 nhóm + nhóm Khác (ngoài 7 nhóm)
        "coverage": {"n_in_subclusters": int(inc.sum()),
                     "n_group_other_few_tools": int(grp_other.sum()),
                     "n_outside_groups": int((meta["job_group"] == OTHER).sum()),
                     "group_other_few_tools": meta.loc[grp_other, "job_group"].value_counts().to_dict()},
        "group_counts": meta["job_group"].value_counts().to_dict(),
        "group_counts_in_space": mk["job_group"].value_counts().to_dict(),
        "group_source_counts": meta["job_group_source"].value_counts().to_dict(),
        "vector_space": {"block_weights": used, "n_skill_features": int(sk.shape[1]),
                         "n_concept_features": 0 if ck is None else int(ck.shape[1]),
                         "n_e5_dims": 0 if ek is None else int(ek.shape[1]), **svd_info},
        "algorithm": "kmeans theo nhóm",
        "best_k": int(offset), "by_group": by_group,
        "silhouette": round(float(sil_all), 4), "davies_bouldin": round(float(db_all), 4),
        "meets_silhouette_target": bool(sil_all >= p.silhouette_target),
        "davies_bouldin_target": p.davies_bouldin_target,
        "meets_davies_bouldin_target": bool(db_all < p.davies_bouldin_target),
        "meets_min_clusters": bool(all(v.get("k", 0) >= 2 for v in by_group.values())),
        "stability": {"ari_mean": round(float(ari_w), 4),
                      "ari_min": round(float(min(by_group[g]["stability"]["ari_mean"] for g in n_g)), 4),
                      "weighting": "trung bình ARI các nhóm, trọng số theo số tin", "n_init": int(p.kmeans_n_init),
                      "seeds": [int(s) for s in p.stability_seeds]},
        "meets_stability_target": bool(ari_w >= p.stability_ari_target),
        "groups_below_stability": [g for g in n_g if not by_group[g]["meets_stability_target"]],
        # cổng tính trong nhóm (người dùng đổi 24/11 sau khi xem kết quả: cụm giờ được tìm trong từng nhóm)
        "min_cluster_share": round(min_share_g, 4),
        "min_cluster_share_basis": "số tin của nhóm",
        "min_cluster_share_overall": round(float(sizes.min() / inc.sum()), 4),
        "meets_min_cluster_share": bool(min_share_g >= p.min_cluster_share),
        "median_n_tools_overall": overall_tools,
        "skill_count_violations": violations,
        "n_sub_role_matched": int(sum(pr["sub_role_matched"] for pr in profiles)),
        "crosstab": ct.to_dict(orient="records"),
        "pca_explained_variance": [round(float(v), 4) for v in pca.explained_variance_ratio_],
        "pca_cumulative_variance_3d": round(float(pca.explained_variance_ratio_.sum()), 4),
        "hdbscan": {"method": glosh_method, "n_clusters": int(len(set(hdb_labels) - {-1})),
                    "noise_ratio": round(float((hdb_labels == -1).mean()), 4),
                    "glosh_threshold": round(glosh_threshold, 4),
                    "outlier_ratio": round(float(is_outlier.mean()), 4)},
        "clusters": profiles,
        "other": other_m,
    }
    return out, metrics


_SENIORITY = ("senior", "junior", "middle", "mid", "sr", "jr", "intern", "fresher", "principal", "remote", "expert",
              "thuc tap sinh", "nhan vien", "chuyen vien cao cap", "chuyen vien", "chuyen gia", "cvcc", "cv",
              "tuyen dung", "tuyen", "cao cap", "staff", "level")
_SENIORITY_RE = re.compile(r"\b(?:" + "|".join(re.escape(s) for s in _SENIORITY) + r")\b")
# Cụm không phải tên nghề (chỉ chức vụ, lĩnh vực chung): không xét nghề mới
_GENERIC_CORES = {"it", "cntt", "cong nghe thong tin", "ky thuat", "technical", "engineer", "developer", "ky su",
                  "lap trinh vien", "lap trinh", "phan mem", "ky su phan mem", "software engineer", "it engineer",
                  "ky su it", "he thong", "lead", "leader", "manager", "specialist", "officer", "associate",
                  "executive", "team leader", "pho phong", "truong phong", "full", "dev", "phan tich", "du lieu",
                  "san pham", "tu van", "test", "it phan mem", "giam sat", "van hanh", "trien khai"}


def title_core(title: Any) -> str:
    """Tiêu đề cốt lõi: fold, bỏ phần trong ngoặc, bỏ từ cấp bậc, lấy đoạn đầu có nghĩa trước dấu tách."""
    from preprocessing.normalization.job_title import fold

    t = re.sub(r"[\[\(].*?[\]\)]", " ", fold(title))
    t = re.sub(r"full\s*-\s*stack", "fullstack", t)
    for seg in re.split(r"\s[-–]\s|[|_,:;/]", t):
        s = re.sub(r"[^a-z0-9.+# ]", " ", _SENIORITY_RE.sub(" ", seg))
        s = re.sub(r"\s+", " ", s).strip()
        if len(s) >= 3 and s not in ("lead", "leader"):
            return s
    return ""


def is_generic_core(core: str) -> bool:
    from preprocessing.normalization.job_title import is_generic_title

    return len(core) < 3 or core in _GENERIC_CORES or is_generic_title(core)


def known_role(core: str) -> str | None:
    """'<nhóm> · <vai trò>' nếu tiêu đề cốt lõi khớp từ khóa một vai trò trong danh sách 7 nhóm của người dùng."""
    from mining.job_group import SUB_ROLES
    from preprocessing.normalization.text_cleaner import has_term

    for g, roles in SUB_ROLES.items():
        for name, terms in roles:
            if name in ("IT Helpdesk / Support", "SysAdmin"):  # từ khóa rộng ("it", "he thong"): không dùng để nhận tên
                terms = [t for t in terms if t not in ("it", "he thong", "quan tri", "system", "support", "ho tro")]
            if has_term(core, terms):
                return f"{g} · {name}"
    return None


def classify_other(meta_all: pd.DataFrame, keep: np.ndarray, Z: np.ndarray, labels: np.ndarray,
                   sk: pd.DataFrame, names: dict[int, str], sub_roles: dict[int, str | None],
                   p: ClusteringParams) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Tin nhóm Khác: luật chốt nghề mới (người dùng yêu cầu 24/11). Trả (cột cho mọi tin, metrics).

    Theo thứ tự: (1) tiêu đề cốt lõi chung chung -> không xét; (2) khớp vai trò trong danh sách 7 nhóm -> đã có;
    (3) đếm đúng tiêu đề cốt lõi trên toàn bộ dữ liệu < 3 tin hoặc < 2 công ty -> theo dõi;
    (4) từng tin có không gian vector: xa tâm cụm gần nhất hơn P90 khoảng cách tin-tâm của mọi tin đã vào cụm
    (một ngưỡng chung) -> "ngoài mọi cụm". >= 50% tin ngoài mọi cụm -> nghề mới; cụm gần nhất trải >= 2 nhóm,
    không nhóm nào >= 60% -> nghề lai; còn lại -> tên gọi khác của nhóm đa số. Nghề mới/lai cần >= 2 công cụ
    riêng (>= 30% tin của tiêu đề đó, lift >= 2 so với nhóm gần nhất).
    meta_all: toàn bộ tin (có job_group); keep, Z, labels, sk: theo thứ tự tin trong không gian vector."""
    n_all = len(meta_all)
    pos = np.full(n_all, -1)
    pos[keep] = np.arange(int(keep.sum()))
    cids = sorted(c for c in set(labels) if c >= 0)
    cent = np.vstack([Z[labels == c].mean(axis=0) for c in cids])
    inc = labels >= 0
    lab_idx = {c: i for i, c in enumerate(cids)}
    own_d = np.linalg.norm(Z[inc] - cent[[lab_idx[c] for c in labels[inc]]], axis=1)
    d_thr = float(np.quantile(own_d, 1 - p.other_sim_quantile))
    D = np.linalg.norm(Z[:, None, :] - cent[None, :, :], axis=2)  # tin trong không gian × cụm
    near = D.argmin(axis=1)
    outside = D.min(axis=1) > d_thr
    group_of = {c: names[c].split(" · ")[0] for c in cids}
    S = (sk.to_numpy() > 0).astype(float)
    tool_names = [c.replace("skill__", "") for c in sk.columns]

    comp = (meta_all["company_id"] if "company_id" in meta_all else meta_all["company_name"]).astype(str)
    cores = meta_all["job_title"].map(title_core)
    is_other = (meta_all["job_group"] == "Khác").to_numpy()
    roles = []
    for core in sorted(set(cores[is_other]) - {""}):
        hit = (cores == core).to_numpy()
        rows = pos[hit & keep]
        row = {"title_core": core, "n_jobs": int(hit.sum()), "n_companies": int(comp[hit].nunique()),
               "n_in_space": int(len(rows)), "groups": meta_all.loc[hit, "job_group"].value_counts().to_dict(),
               "examples": meta_all.loc[hit, "job_title"].astype(str).head(4).tolist()}
        kr = known_role(core)
        if is_generic_core(core):
            row["verdict"] = "tiêu đề chung chung"
        elif kr:
            row["verdict"] = f"đã có trong danh sách: {kr}"
        elif row["n_jobs"] < p.new_role_min_jobs or row["n_companies"] < p.new_role_min_companies:
            row["verdict"] = "theo dõi (chưa đủ tin)"
        elif len(rows) < 2:
            row["verdict"] = "theo dõi (JD ít thông tin)"
        else:
            grp_near = pd.Series([group_of[cids[i]] for i in near[rows]]).value_counts(normalize=True)
            share_out = float(outside[rows].mean())
            main = grp_near.index[0]
            base = S[np.isin(labels, [c for c in cids if group_of[c] == main])].mean(axis=0)
            share = S[rows].mean(axis=0)
            lift = np.divide(share, base, out=np.full_like(share, np.inf), where=base > 0)
            own = [tool_names[j] for j in np.argsort(-share)
                   if share[j] >= p.new_role_skill_share and lift[j] >= p.new_role_skill_lift]
            row.update({"share_outside": round(share_out, 3), "nearest_groups": grp_near.round(3).to_dict(),
                        "own_skills": own[:6]})
            if share_out >= 0.5 and len(own) >= p.new_role_min_skills:
                row["verdict"] = "nghề mới"
            elif grp_near.iloc[0] < 0.6 and len(own) >= p.new_role_min_skills:
                row["verdict"] = "nghề lai"
                row["between"] = list(grp_near.index[:2])
            else:
                row["verdict"] = f"tên gọi khác trong {main}"
        roles.append(row)
    verdict = {r["title_core"]: r["verdict"] for r in roles}

    status = np.array([None] * n_all, dtype=object)
    nearest = np.array([None] * n_all, dtype=object)
    for i in np.flatnonzero(is_other):
        v = verdict.get(cores[i], "")
        if not keep[i]:
            status[i] = "JD ít thông tin"
            continue
        nearest[i] = names[cids[near[pos[i]]]]
        if v in ("nghề mới", "nghề lai"):
            status[i] = v
        else:
            status[i] = "lẻ (ngoài mọi cụm)" if outside[pos[i]] else "giống cụm có sẵn"
    cols = pd.DataFrame({"title_core": cores.where(is_other, None).to_numpy(), "other_status": status,
                         "nearest_cluster": nearest})
    roles.sort(key=lambda r: (-r["n_jobs"], r["title_core"]))
    m = {"rule": "tiêu đề cốt lõi không chung chung, chưa có trong danh sách vai trò, >= %d tin và >= %d công ty "
                 "(đếm toàn bộ dữ liệu); >= 50%% tin xa tâm cụm gần nhất hơn P%d (ngưỡng chung) = nghề mới; "
                 "cụm gần nhất trải >= 2 nhóm, không nhóm nào >= 60%% = nghề lai; cả hai cần >= %d công cụ riêng "
                 "(>= %d%% tin, lift >= %g so với nhóm gần nhất)"
                 % (p.new_role_min_jobs, p.new_role_min_companies, int((1 - p.other_sim_quantile) * 100),
                    p.new_role_min_skills, int(p.new_role_skill_share * 100), p.new_role_skill_lift),
         "distance_threshold": round(d_thr, 4),
         "status_counts": pd.Series(status[is_other]).value_counts().to_dict(),
         "verdict_counts": pd.Series([r["verdict"].split(":")[0].split(" trong ")[0] for r in roles]).value_counts().to_dict(),
         "roles": roles}
    return cols, m
