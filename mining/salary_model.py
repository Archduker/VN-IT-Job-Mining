"""M5: giá trị kỹ năng và lương ước tính cho SD4 (docs/spec/mining/M5_luong_shap.md).

- Tập có lương (M5.1): salary_target_m có số, không thỏa thuận, không `salary_outlier` (cờ Silver), trong 1–500 triệu;
  bỏ tin lệch > 3 lần trung vị cùng cấp. Tin thỏa thuận không dùng để train hay chấm.
- y = log1p(salary_target_m) (M5.2). X: K-tool `skill::`, seniority_ord, exp_min_years (+ cờ thiếu), nhóm tỉnh,
  `jf::` nghề, `src::` nguồn (M5.3a); cấu hình phụ thêm `concept::` (M5.3b), báo cả hai, không tự chọn.
- Chia theo công ty (M5.4): GroupShuffleSplit 80/20 + GroupKFold 5 phần theo company_id (null → nhóm riêng).
- Baseline (M5.6): trung vị cấp × nghề tính trên phần train như M1.B (ô < 30 tin lùi về cấp, rồi toàn bộ).
- Phương án A đạt (M5.7) khi MAE thấp hơn baseline >= 10% và std R² CV <= 0,05; không thì báo phương án B
  (RF phân lớp 4 khung lương theo tứ phân vị train).
- SHAP trên model fit lại toàn tập (M5.13). Giá trị biên kỹ năng i = trung bình phi_i TRÊN CÁC TIN CÓ i, quy ra
  triệu: lương nền × (e^phi − 1); chỉ kỹ năng >= 30 tin; khoảng tin cậy bootstrap (M5.10).
- 4.4 (M5.11, M5.12): ước tính và P10–P90 cho tin thỏa thuận, cảnh báo nhóm bị đại diện >= 2 lần ở tập thỏa thuận.
SHAP mô tả cách model dùng đặc trưng, không phải nhân quả (MINE-6); cấp và kinh nghiệm chia điểm cho nhau (F10.6).
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, GroupShuffleSplit, KFold

from mining.bi import baseline_salary, labels
from mining.config import JOB_FAMILY_OTHER, LOCATION_FEATURE_GROUPS, RANDOM_STATE, BIParams, SalaryParams

logger = logging.getLogger(__name__)

SKILL_FEATURE_PREFIX = "skill::"
CONCEPT_FEATURE_PREFIX = "concept::"
LOC_FEATURE_PREFIX = "loc::"
JF_FEATURE_PREFIX = "jf::"
SRC_FEATURE_PREFIX = "src::"
NAME_PREFIXES = (SKILL_FEATURE_PREFIX, CONCEPT_FEATURE_PREFIX)  # tên kỹ năng có thể chứa chữ "salary"
LEAKAGE_TOKENS = ("salary", "luong", "lương", "negotiable", "log_sal", "suspect", "outlier")
SALARY_VALID_RANGE_MIL = (1.0, 500.0)  # giống luật N6a của Normalization
ALL_SCOPE = "ALL"
SENIORITY_STEPS = ("Intern/Fresher", "Junior", "Middle", "Senior")  # kiểm đóng góp SHAP tăng dần (Lead MNAR)
NOTES = [
    "MINE-6: SHAP mô tả cách model dùng đặc trưng, không phải quan hệ nhân quả.",
    "F10.6: cấp bậc và kinh nghiệm tương quan nên chia điểm SHAP với nhau.",
    "Chỉ học từ tin công bố lương; tin thỏa thuận có phân bố khác (MNAR), xem salary_distribution.",
]
SHAP_COLUMNS = ["skill_name", "job_family", "mean_shap_value", "marginal_dollar_vnd", "sample_size",
                "marginal_trieu", "delta_m", "ci_low", "ci_high", "abs_mean_shap", "is_reliable", "rank"]
ESTIMATE_COLUMNS = ["job_id", "salary_estimated_m", "p10_m", "p90_m", "salary_is_estimated", "warning"]


class LeakageError(ValueError):
    pass


def assert_no_leakage(columns: list[str]) -> None:
    bad = [c for c in columns if any(tok in c.lower() for tok in LEAKAGE_TOKENS) and not c.startswith(NAME_PREFIXES)]
    if bad:
        raise LeakageError(f"Feature mang thông tin lương: {bad}")


def salary_level_ratio(meta: pd.DataFrame, min_level_count: int = 20) -> pd.Series:
    """Lương / trung vị lương cùng cấp bậc (NaN nếu không có lương hoặc cấp bậc có < 20 tin có lương)."""
    sal = pd.to_numeric(meta["salary_avg_mil"], errors="coerce")
    sal = sal.where(sal > 0)
    sen = meta["seniority_ord"].astype(int)
    n_level = sal.groupby(sen).transform("count")
    return (sal / sal.groupby(sen).transform("median")).where(n_level >= min_level_count)


def select_training_subset(
    meta: pd.DataFrame,
    level_ratio_limit: float | None = None,
) -> tuple[np.ndarray, dict[str, int]]:
    """M5.1: mask tập có lương và số dòng bị loại theo từng lý do."""
    sal = pd.to_numeric(meta["salary_avg_mil"], errors="coerce")
    has = sal.notna() & (sal > 0)
    neg = meta["is_negotiable"].astype(bool)
    sus = meta["salary_outlier"].astype(bool)
    lo, hi = SALARY_VALID_RANGE_MIL
    in_range = sal.between(lo, hi)
    mask = has & ~neg & ~sus & in_range
    n_before_ratio = int(mask.sum())
    if level_ratio_limit:
        ratio = salary_level_ratio(meta)
        implausible = ((ratio > level_ratio_limit) | (ratio < 1 / level_ratio_limit)).fillna(False)
        mask = mask & ~implausible
    counts = {
        "n_jobs": int(len(meta)),
        "n_with_salary": int(has.sum()),
        "n_negotiable": int(neg.sum()),
        "n_dropped_negotiable_with_number": int((has & neg).sum()),
        "n_dropped_suspect": int((has & ~neg & sus).sum()),  # tên cũ giữ cho Mart; nghĩa: salary_outlier
        "n_dropped_out_of_range": int((has & ~neg & ~sus & ~in_range).sum()),
        "n_dropped_implausible_vs_level": n_before_ratio - int(mask.sum()),
        "level_ratio_limit": level_ratio_limit,
        "n_train_subset": int(mask.sum()),
    }
    counts["share_train_subset"] = round(counts["n_train_subset"] / max(1, counts["n_jobs"]), 4)
    return mask.to_numpy(), counts


def build_salary_features(meta: pd.DataFrame, skills: pd.DataFrame, concepts: pd.DataFrame | None = None) -> pd.DataFrame:
    """M5.3a (+ M5.3b khi có `concepts`)."""
    meta = meta.reset_index(drop=True)
    cols: dict[str, np.ndarray] = {}
    for c in skills.columns:
        cols[f"{SKILL_FEATURE_PREFIX}{c}"] = skills[c].to_numpy(dtype=np.uint8)
    if concepts is not None:
        for c in concepts.columns:
            cols[f"{CONCEPT_FEATURE_PREFIX}{c}"] = concepts[c].to_numpy(dtype=np.uint8)
    cols["seniority_ord"] = meta["seniority_ord"].astype(int).to_numpy()
    exp = pd.to_numeric(meta["exp_min_years"], errors="coerce")
    cols["exp_min_years"] = exp.fillna(-1).to_numpy(dtype=float)
    cols["exp_min_years__missing"] = exp.isna().astype(np.uint8).to_numpy()
    for g in LOCATION_FEATURE_GROUPS:
        cols[f"{LOC_FEATURE_PREFIX}{g}"] = (meta["location_group"] == g).astype(np.uint8).to_numpy()
    fam = meta["job_family"].fillna(JOB_FAMILY_OTHER).astype(str)
    for f in sorted(fam.unique()):
        cols[f"{JF_FEATURE_PREFIX}{f}"] = (fam == f).astype(np.uint8).to_numpy()
    if "source_platform" in meta:  # quyết định 5: nguồn là biến kiểm soát
        src = labels(meta["source_platform"])
        for s in sorted(src.unique()):
            cols[f"{SRC_FEATURE_PREFIX}{s}"] = (src == s).astype(np.uint8).to_numpy()
    X = pd.DataFrame(cols)
    assert_no_leakage(list(X.columns))
    return X


def _groups(meta: pd.DataFrame) -> np.ndarray:
    """M5.4: nhóm = company_id; tin không có company_id là một nhóm riêng "job:<job_id>"."""
    ids = "job:" + meta["job_id"].astype(str).reset_index(drop=True)
    if "company_id" not in meta:
        return ids.to_numpy()
    g = meta["company_id"].astype("string").reset_index(drop=True).str.strip()
    return g.where(g.notna() & (g != ""), ids).astype(str).to_numpy()


def company_split(meta: pd.DataFrame, test_size: float, random_state: int) -> tuple[np.ndarray, np.ndarray, int]:
    """GroupShuffleSplit theo công ty; trả (train idx, test idx, số công ty có ở cả hai phía)."""
    g = _groups(meta)
    tr, te = next(GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=random_state)
                  .split(np.zeros(len(g)), groups=g))
    return tr, te, len(set(g[tr]) & set(g[te]))


def baseline_level_family(meta_tr: pd.DataFrame, meta_te: pd.DataFrame, min_cell: int = 30) -> tuple[np.ndarray, dict[str, int]]:
    """M5.6: dự đoán = trung vị cấp × nghề của phần train (M1.B); ô < min_cell → cấp → toàn bộ."""
    b = baseline_salary(meta_tr.reset_index(drop=True), BIParams(min_cell=min_cell))
    fam, sen = labels(meta_te["job_family"]), labels(meta_te["seniority"])
    pred, how = [], []
    for f, s in zip(fam, sen, strict=True):
        cell = b["cells"].get(f, {}).get(s)
        if cell is not None:
            pred.append(cell["median"]); how.append(cell["fallback"] or "cell")
        elif s in b["by_seniority"] and b["by_seniority"][s]["n"] >= min_cell:
            pred.append(b["by_seniority"][s]["median"]); how.append("seniority")
        else:
            pred.append(b["overall"]["median"]); how.append("overall")
    how_s = pd.Series(how)
    return np.asarray(pred, dtype=float), {"n_cell": int((how_s == "cell").sum()),
                                           "n_fallback_seniority": int((how_s == "seniority").sum()),
                                           "n_fallback_overall": int((how_s == "overall").sum())}


def _rf(params: dict[str, Any], random_state: int) -> RandomForestRegressor:
    return RandomForestRegressor(random_state=random_state, n_jobs=-1, **params)


def _cv_scores(X: pd.DataFrame, y: np.ndarray, groups: np.ndarray | None, params: dict[str, Any],
               folds: int, random_state: int) -> list[float]:
    if groups is not None and len(set(groups)) >= folds:
        splits = GroupKFold(n_splits=folds).split(X, y, groups)
    else:
        splits = KFold(n_splits=folds, shuffle=True, random_state=random_state).split(X)
    scores = []
    for tr, va in splits:
        m = _rf(params, random_state).fit(X.iloc[tr], y[tr])
        scores.append(float(r2_score(y[va], m.predict(X.iloc[va]))))
    return scores


def _mil_metrics(t: np.ndarray, p: np.ndarray) -> dict[str, float]:
    return {"mae_mil": round(float(mean_absolute_error(t, p)), 3),
            "rmse_mil": round(float(np.sqrt(mean_squared_error(t, p))), 3),
            "r2_mil": round(float(r2_score(t, p)), 4)}


def _holdout_metrics(y_true_log: np.ndarray, y_pred_log: np.ndarray) -> dict[str, float]:
    return {"r2_log": round(float(r2_score(y_true_log, y_pred_log)), 4),
            **_mil_metrics(np.expm1(y_true_log), np.expm1(y_pred_log))}


def mae_by_group(meta_te: pd.DataFrame, y_true: np.ndarray, y_pred: np.ndarray, y_base: np.ndarray,
                 cols: dict[str, str], min_n: int) -> dict[str, list[dict[str, Any]]]:
    """M5.8 (4.3): MAE (triệu) của model và baseline theo nhóm; nhóm n < min_n ghi low_data."""
    out = {}
    for name, col in cols.items():
        if col not in meta_te:
            continue
        lab = labels(meta_te[col])
        rows = []
        for v in sorted(lab.unique()):
            m = (lab == v).to_numpy()
            rows.append({"value": v, "n": int(m.sum()),
                         "mae_mil": round(float(np.abs(y_true[m] - y_pred[m]).mean()), 3),
                         "mae_baseline_mil": round(float(np.abs(y_true[m] - y_base[m]).mean()), 3),
                         "median_true_mil": round(float(np.median(y_true[m])), 2),
                         "low_data": bool(m.sum() < min_n)})
        out[name] = sorted(rows, key=lambda r: -r["n"])
    return out


def train_band_classifier(X_tr: pd.DataFrame, y_tr_mil: np.ndarray, X_te: pd.DataFrame, y_te_mil: np.ndarray,
                          n_bands: int, random_state: int) -> dict[str, Any]:
    """Phương án B (M5.7): RF phân lớp n_bands khung theo phân vị của phần train."""
    edges = np.quantile(y_tr_mil, np.linspace(0, 1, n_bands + 1)[1:-1])
    b_tr, b_te = np.digitize(y_tr_mil, edges), np.digitize(y_te_mil, edges)
    clf = RandomForestClassifier(n_estimators=300, min_samples_leaf=3, random_state=random_state, n_jobs=-1).fit(X_tr, b_tr)
    pred = clf.predict(X_te)
    major = np.full_like(b_te, np.bincount(b_tr).argmax())
    return {"band_edges_mil": [round(float(e), 2) for e in edges],
            "macro_f1": round(float(f1_score(b_te, pred, average="macro")), 4),
            "accuracy": round(float(accuracy_score(b_te, pred)), 4),
            "majority_accuracy": round(float(accuracy_score(b_te, major)), 4),
            "majority_macro_f1": round(float(f1_score(b_te, major, average="macro")), 4)}


def _evaluate_config(X: pd.DataFrame, y: np.ndarray, groups: np.ndarray, tr: np.ndarray, te: np.ndarray,
                     base_pred: np.ndarray, sub_meta: pd.DataFrame, p: SalaryParams, random_state: int) -> dict[str, Any]:
    X_tr, X_te, y_tr, y_te = X.iloc[tr], X.iloc[te], y[tr], y[te]
    grid = []
    for prm in p.param_grid:
        sc = _cv_scores(X_tr, y_tr, groups[tr], prm, p.cv_folds, random_state)
        grid.append({"params": prm, "cv_r2_mean": round(float(np.mean(sc)), 4), "cv_r2_std": round(float(np.std(sc)), 4),
                     "cv_r2_folds": [round(s, 4) for s in sc]})
    best = max(grid, key=lambda g: g["cv_r2_mean"])
    model = _rf(best["params"], random_state).fit(X_tr, y_tr)
    pred_log = model.predict(X_te)
    holdout = _holdout_metrics(y_te, pred_log)
    base_mae = float(mean_absolute_error(np.expm1(y_te), base_pred))
    gain = 1 - holdout["mae_mil"] / base_mae if base_mae > 0 else 0.0
    return {
        "n_features": int(X.shape[1]), "param_search": grid, "best_params": best["params"],
        "cv_r2_mean": best["cv_r2_mean"], "cv_r2_std": best["cv_r2_std"], "holdout": holdout,
        "mae_gain_vs_baseline": round(gain, 4),
        "beats_baseline": bool(gain >= p.baseline_margin),
        "meets_cv_std_target": bool(best["cv_r2_std"] <= p.cv_std_target),
        "pass_A": bool(gain >= p.baseline_margin and best["cv_r2_std"] <= p.cv_std_target),
        "mae_by_group": mae_by_group(sub_meta.iloc[te].reset_index(drop=True), np.expm1(y_te), np.expm1(pred_log),
                                     base_pred, {"job_family": "job_family", "seniority": "seniority",
                                                 "source": "source_platform"}, p.min_group_eval),
        "top_feature_importances": [{"feature": f, "importance": round(float(v), 4)} for f, v in
                                    sorted(zip(X.columns, model.feature_importances_, strict=True), key=lambda kv: -kv[1])[:20]],
    }


def bootstrap_ci(phi: np.ndarray, base_mil: float, n_boot: int, rng: np.random.Generator, level: float = 0.95) -> tuple[float, float]:
    """Khoảng tin cậy của base × (e^mean(phi) − 1) khi lấy lại mẫu các tin có kỹ năng."""
    if n_boot <= 0 or len(phi) == 0:
        return float("nan"), float("nan")
    means = phi[rng.integers(0, len(phi), size=(n_boot, len(phi)))].mean(axis=1)
    d = base_mil * np.expm1(means)
    a = (1 - level) / 2
    return float(np.quantile(d, a)), float(np.quantile(d, 1 - a))


def skill_values_from_shap(
    shap_values: np.ndarray,
    X: pd.DataFrame,
    job_family: pd.Series,
    base_salary_mil: float,
    min_sample: int,
    bootstrap_n: int = 0,
    random_state: int = RANDOM_STATE,
) -> pd.DataFrame:
    """M5.10: giá trị biên kỹ năng theo phạm vi ALL và từng nghề; chỉ giữ kỹ năng >= min_sample tin."""
    skill_cols = [c for c in X.columns if c.startswith(SKILL_FEATURE_PREFIX)]
    col_idx = {c: X.columns.get_loc(c) for c in skill_cols}
    fam = pd.Series(job_family).reset_index(drop=True).fillna(JOB_FAMILY_OTHER).astype(str).to_numpy()
    scopes = [(ALL_SCOPE, np.ones(len(X), dtype=bool))] + [(f, fam == f) for f in sorted(set(fam))]
    rng = np.random.default_rng(random_state)
    rows = []
    for scope, smask in scopes:
        for c in skill_cols:
            j = col_idx[c]
            present = smask & (X[c].to_numpy() == 1)
            n = int(present.sum())
            if n == 0 or n < min_sample:
                continue
            phis = shap_values[present, j]
            phi = float(phis.mean())
            lo, hi = bootstrap_ci(phis, base_salary_mil, bootstrap_n, rng)
            delta = float(base_salary_mil * np.expm1(phi))
            rows.append({  # 5 cột đầu theo hợp đồng Mart (spec 07 §5.3)
                "skill_name": c[len(SKILL_FEATURE_PREFIX):], "job_family": scope, "mean_shap_value": phi,
                "marginal_dollar_vnd": delta * 1e6, "sample_size": n, "marginal_trieu": delta, "delta_m": delta,
                "ci_low": lo, "ci_high": hi, "abs_mean_shap": float(np.abs(shap_values[smask, j]).mean()),
                "is_reliable": True,
            })
    out = pd.DataFrame(rows, columns=SHAP_COLUMNS[:-1])
    out["rank"] = out.groupby("job_family")["delta_m"].rank(ascending=False, method="first").astype("Int64") \
        if len(out) else pd.Series(dtype="Int64")
    return out.sort_values(["job_family", "rank"]).reset_index(drop=True)[SHAP_COLUMNS]


def factor_importance(sv: np.ndarray, columns: list[str], top_n: int = 20) -> dict[str, Any]:
    """M5.9 (4.1): trung bình |tổng SHAP của nhóm| theo nhóm đặc trưng, và top kỹ năng theo mean|phi|."""
    groups = {
        "Cấp bậc": [c for c in columns if c == "seniority_ord"],
        "Kinh nghiệm": [c for c in columns if c.startswith("exp_min_years")],
        "Tỉnh": [c for c in columns if c.startswith(LOC_FEATURE_PREFIX)],
        "Nhóm nghề": [c for c in columns if c.startswith(JF_FEATURE_PREFIX)],
        "Nguồn tin": [c for c in columns if c.startswith(SRC_FEATURE_PREFIX)],
        "Công cụ (gộp)": [c for c in columns if c.startswith(SKILL_FEATURE_PREFIX)],
        "Khái niệm (gộp)": [c for c in columns if c.startswith(CONCEPT_FEATURE_PREFIX)],
    }
    idx = {c: i for i, c in enumerate(columns)}
    rows = []
    for g, cs in groups.items():
        if cs:
            rows.append({"group": g, "n_features": len(cs),
                         "mean_abs_shap": float(np.abs(sv[:, [idx[c] for c in cs]].sum(axis=1)).mean())})
    tot = sum(r["mean_abs_shap"] for r in rows) or 1.0
    for r in rows:
        r["share"] = round(r["mean_abs_shap"] / tot, 4)
        r["mean_abs_shap"] = round(r["mean_abs_shap"], 5)
    sk = [c for c in columns if c.startswith(SKILL_FEATURE_PREFIX)]
    top = sorted(((c, float(np.abs(sv[:, idx[c]]).mean())) for c in sk), key=lambda kv: -kv[1])[:top_n]
    return {"groups": sorted(rows, key=lambda r: -r["mean_abs_shap"]),
            "top_skills": [{"skill": c[len(SKILL_FEATURE_PREFIX):], "mean_abs_shap": round(v, 5)} for c, v in top],
            "method": "mean |sum phi trong nhóm| trên các tin được giải thích (thang log lương)"}


def compare_distributions(meta_neg: pd.DataFrame, meta_paid: pd.DataFrame, cols: list[str],
                          warn_ratio: float) -> tuple[list[dict[str, Any]], dict[str, set[str]]]:
    """M5.12: tỷ lệ từng giá trị ở tập thỏa thuận so với tập có lương; tỷ số >= warn_ratio → cảnh báo."""
    rows, flagged = [], {}
    for col in cols:
        if col not in meta_neg or col not in meta_paid:
            continue
        a, b = labels(meta_neg[col]), labels(meta_paid[col])
        sa, sb = a.value_counts(normalize=True), b.value_counts(normalize=True)
        flagged[col] = set()
        for v in sorted(set(sa.index) | set(sb.index)):
            share_neg, share_paid = float(sa.get(v, 0.0)), float(sb.get(v, 0.0))
            ratio = share_neg / share_paid if share_paid > 0 else (float("inf") if share_neg > 0 else 0.0)
            warn = bool(share_neg > 0 and ratio >= warn_ratio)
            if warn:
                flagged[col].add(v)
            rows.append({"column": col, "value": v, "n_negotiable": int((a == v).sum()), "share_negotiable": round(share_neg, 4),
                         "n_paid": int((b == v).sum()), "share_paid": round(share_paid, 4),
                         "ratio": None if np.isinf(ratio) else round(ratio, 3), "warning": warn})
    return rows, flagged


def estimate_negotiable(model: RandomForestRegressor, X_neg: pd.DataFrame, meta_neg: pd.DataFrame,
                        flagged: dict[str, set[str]]) -> pd.DataFrame:
    """M5.11 (4.4): expm1(dự đoán) và P10–P90 từ dự đoán từng cây; không ghi đè cột lương nào."""
    if len(X_neg) == 0:
        return pd.DataFrame(columns=ESTIMATE_COLUMNS)
    per_tree = np.stack([t.predict(X_neg.to_numpy(dtype=float)) for t in model.estimators_])
    center = np.expm1(per_tree.mean(axis=0))
    p10, p90 = np.expm1(np.quantile(per_tree, 0.10, axis=0)), np.expm1(np.quantile(per_tree, 0.90, axis=0))
    meta_neg = meta_neg.reset_index(drop=True)
    warns = [[] for _ in range(len(meta_neg))]
    for col, vals in flagged.items():
        lab = labels(meta_neg[col])
        for i, v in enumerate(lab):
            if v in vals:
                warns[i].append(f"{col}={v}")
    return pd.DataFrame({
        "job_id": meta_neg["job_id"].astype(str).to_numpy(),
        "salary_estimated_m": np.round(center, 2),
        "p10_m": np.round(np.minimum(p10, center), 2), "p90_m": np.round(np.maximum(p90, center), 2),
        "salary_is_estimated": True,
        "warning": ["; ".join(w) for w in warns],
    })


def _seniority_shap(sv: np.ndarray, X: pd.DataFrame, seniority: pd.Series) -> dict[str, Any]:
    """Đóng góp SHAP trung bình của seniority_ord theo cấp; kiểm tăng dần Intern/Fresher → Senior."""
    j = X.columns.get_loc("seniority_ord")
    lab = labels(seniority).to_numpy()
    by = {s: round(float(sv[lab == s, j].mean()), 4) for s in sorted(set(lab))}
    steps = [by[s] for s in SENIORITY_STEPS if s in by]
    return {"by_level": by, "increasing_intern_to_senior": bool(all(a < b for a, b in zip(steps, steps[1:], strict=False)))}


def _raw_sign_agreement(values: pd.DataFrame, X: pd.DataFrame, y_mil: np.ndarray) -> dict[str, Any]:
    """Chiều của delta_m so với chênh trung vị thô (tin có − không có kỹ năng) trên tập có lương, phạm vi ALL."""
    allv = values[values["job_family"] == ALL_SCOPE]
    same = []
    for r in allv.itertuples():
        has = X[f"{SKILL_FEATURE_PREFIX}{r.skill_name}"].to_numpy() == 1
        raw = float(np.median(y_mil[has]) - np.median(y_mil[~has])) if (~has).any() else 0.0
        same.append(np.sign(raw) == np.sign(r.delta_m))
    return {"n_skills": len(same), "share_same_sign": round(float(np.mean(same)), 4) if same else None}


def _empty_values() -> pd.DataFrame:
    return pd.DataFrame(columns=SHAP_COLUMNS)


def train_salary_model(
    meta: pd.DataFrame,
    skills: pd.DataFrame,
    params: SalaryParams | None = None,
    random_state: int = RANDOM_STATE,
    compute_shap: bool = True,
    concepts: pd.DataFrame | None = None,
) -> tuple[RandomForestRegressor | None, pd.DataFrame, dict[str, Any], dict[str, Any]]:
    """Trả (model cuối, bảng giá trị kỹ năng, metrics, {estimates, factor_importance, distribution})."""
    p = params or SalaryParams()
    meta = meta.reset_index(drop=True)
    skills = skills.reset_index(drop=True)
    mask, counts = select_training_subset(meta, p.level_ratio_limit)
    metrics: dict[str, Any] = {"subset": counts, "target": "log1p(salary_target_m, triệu VNĐ/tháng)", "notes": NOTES}
    extra: dict[str, Any] = {"estimates": pd.DataFrame(columns=ESTIMATE_COLUMNS), "factor_importance": None,
                             "distribution": None}
    if counts["n_train_subset"] < max(50, p.cv_folds * 10):
        metrics["skipped"] = f"Chỉ có {counts['n_train_subset']} tin có lương, không đủ để huấn luyện."
        return None, _empty_values(), metrics, extra

    sub_meta = meta.loc[mask].reset_index(drop=True)
    y = np.log1p(sub_meta["salary_avg_mil"].to_numpy(dtype=float))
    groups = _groups(sub_meta)
    tr, te, overlap = company_split(sub_meta, p.test_size, random_state)
    base_pred, base_info = baseline_level_family(sub_meta.iloc[tr], sub_meta.iloc[te], p.min_group_eval)
    baseline = {**_mil_metrics(np.expm1(y[te]), base_pred), **base_info,
                "method": "trung vị salary_target_m cấp × nghề trên phần train (M1.B)"}

    configs: dict[str, pd.DataFrame | None] = {"tool_only": None}
    if concepts is not None and concepts.shape[1]:
        configs["tool_concept"] = concepts.reset_index(drop=True)
    X_full, res = {}, {}
    for name, conc in configs.items():
        X_full[name] = build_salary_features(meta, skills, conc)
        res[name] = _evaluate_config(X_full[name].loc[mask].reset_index(drop=True), y, groups, tr, te, base_pred,
                                     sub_meta, p, random_state)
        logger.info("Lương %s: MAE %.3f (baseline %.3f), hơn baseline %.1f%%", name, res[name]["holdout"]["mae_mil"],
                    baseline["mae_mil"], 100 * res[name]["mae_gain_vs_baseline"])
    used = p.feature_config if p.feature_config in res else "tool_only"
    r = res[used]
    X = X_full[used].loc[mask].reset_index(drop=True)
    metrics.update({
        "split_method": "GroupShuffleSplit + GroupKFold theo company_id (null → nhóm riêng theo job_id)",
        "n_train": int(len(tr)), "n_test": int(len(te)), "n_companies": int(len(set(groups))),
        "n_companies_train": int(len(set(groups[tr]))), "n_companies_test": int(len(set(groups[te]))),
        "n_companies_overlap": int(overlap),
        "baseline_level_family": baseline,
        "configs": {k: {kk: vv for kk, vv in v.items() if kk != "mae_by_group"} | {"mae_by_group": v["mae_by_group"]}
                    for k, v in res.items()},
        "config_used": used,
        "config_choice": "người dùng chọn tool_concept 20/11 (1.B); phương án B chỉ chạy khi A không đạt (2.A)",
        "n_features": r["n_features"], "best_params": r["best_params"], "param_search": r["param_search"],
        "cv_r2_mean": r["cv_r2_mean"], "cv_r2_std": r["cv_r2_std"], "holdout": r["holdout"],
        "mae_gain_vs_baseline": r["mae_gain_vs_baseline"], "mae_by_group": r["mae_by_group"],
        "plan": "A" if r["pass_A"] else "B",
        "meets_baseline_margin": r["beats_baseline"], "baseline_margin": p.baseline_margin,
        "meets_r2_target": bool(r["holdout"]["r2_log"] >= p.r2_target),
        "meets_mae_target": bool(r["holdout"]["mae_mil"] <= p.mae_target_mil),
        "meets_cv_std_target": r["meets_cv_std_target"],
        "targets": {"r2_log": p.r2_target, "mae_mil": p.mae_target_mil, "cv_r2_std": p.cv_std_target,
                    "baseline_margin": p.baseline_margin, "note": "R², MAE tuyệt đối chỉ báo cáo (PRE-36)"},
        "top_feature_importances": r["top_feature_importances"],
    })
    if not r["pass_A"]:
        metrics["band_classifier"] = train_band_classifier(X.iloc[tr], np.expm1(y[tr]), X.iloc[te], np.expm1(y[te]),
                                                           p.n_bands, random_state)

    # M5.13: model cuối fit lại trên toàn tập có lương
    final = _rf(r["best_params"], random_state).fit(X, y)
    metrics["final_model"] = "fit lại trên toàn tập có lương (chỉ số đánh giá lấy từ holdout ở trên)"

    # M5.11, M5.12: tin thỏa thuận chưa có số
    neg = (meta["is_negotiable"].astype(bool) & pd.to_numeric(meta["salary_avg_mil"], errors="coerce").isna()).to_numpy()
    dist, flagged = compare_distributions(meta.loc[neg], sub_meta, ["seniority", "job_family", "source_platform"],
                                          p.dist_warn_ratio)
    extra["distribution"] = dist
    extra["estimates"] = estimate_negotiable(final, X_full[used].loc[neg].reset_index(drop=True), meta.loc[neg], flagged)
    est = extra["estimates"]
    metrics["estimates"] = {
        "n_estimated": int(len(est)), "n_with_warning": int((est["warning"] != "").sum()) if len(est) else 0,
        "flagged_groups": {k: sorted(v) for k, v in flagged.items() if v},
        "median_estimated_m": round(float(est["salary_estimated_m"].median()), 2) if len(est) else None,
        "median_paid_m": round(float(np.median(np.expm1(y))), 2),
        "median_interval_width_m": round(float((est["p90_m"] - est["p10_m"]).median()), 2) if len(est) else None,
    }

    values = _empty_values()
    if compute_shap:
        import shap

        rng = np.random.default_rng(random_state)
        idx = np.arange(len(X)) if len(X) <= p.max_shap_rows else np.sort(rng.choice(len(X), p.max_shap_rows, replace=False))
        X_exp = X.iloc[idx].reset_index(drop=True)
        explainer = shap.TreeExplainer(final)
        sv = np.asarray(explainer.shap_values(X_exp, check_additivity=False))
        ev = float(np.ravel(explainer.expected_value)[0])
        base_mil = float(np.expm1(ev))
        values = skill_values_from_shap(sv, X_exp, sub_meta["job_family"].iloc[idx], base_mil, p.min_skill_sample,
                                        p.bootstrap_n, random_state)
        extra["factor_importance"] = factor_importance(sv, list(X_exp.columns))
        top = values[values["job_family"] == ALL_SCOPE].head(p.top_k_report)
        metrics["shap"] = {
            "n_rows_explained": int(len(X_exp)), "expected_value_log": round(ev, 4),
            "baseline_salary_mil": round(base_mil, 3),
            "formula": "delta_m = baseline_salary × (exp(mean phi | có kỹ năng) − 1)",
            "min_skill_sample": p.min_skill_sample, "bootstrap_n": p.bootstrap_n,
            "n_skills_valued_all": int((values["job_family"] == ALL_SCOPE).sum()),
            "top_skills": [{"skill": t.skill_name, "delta_m": round(t.delta_m, 2), "ci": [round(t.ci_low, 2), round(t.ci_high, 2)],
                            "phi": round(t.mean_shap_value, 4), "n": int(t.sample_size)} for t in top.itertuples()],
            "factor_groups": extra["factor_importance"]["groups"],
            "seniority_contribution": _seniority_shap(sv, X_exp, sub_meta["seniority"].iloc[idx]
                                                      if "seniority" in sub_meta else sub_meta["seniority_ord"].iloc[idx]),
            "raw_sign_agreement": _raw_sign_agreement(values, X, np.expm1(y)),
        }
    return final, values, metrics, extra
