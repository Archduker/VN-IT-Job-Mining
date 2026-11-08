"""Thuật toán 3: Random Forest dự báo lương + TreeSHAP định giá kỹ năng (spec 07 §4).

- Tập huấn luyện (Subset A): tin có salary_avg > 0, không thỏa thuận, không salary_suspect.
- y = log(1 + salary_avg), lương tính bằng triệu VNĐ/tháng.
- X: kỹ năng 0/1, seniority_ord, exp_min_years (+ cờ thiếu), nhóm địa bàn, job_family.
  Không có cột nào mang thông tin lương (assert_no_leakage).
- Đánh giá: holdout 20% + 5-fold CV trên phần train (GroupKFold nếu có dup_group_id từ bước dedup),
  so với baseline chỉ dùng cấp bậc + kinh nghiệm.
- SHAP: TreeExplainer trên model fit lại bằng toàn bộ Subset A. Giá trị biên của kỹ năng i là
  trung bình phi_i TRÊN CÁC TIN CÓ KỸ NĂNG i (trung bình trên mọi tin sẽ bị kéo về ~0 vì ma trận
  thưa ~97%). Quy đổi: delta = baseline_salary * (e^phi - 1), baseline = expm1(E[f(x)]).
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, GroupShuffleSplit, KFold, train_test_split

from mining.config import LOCATION_FEATURE_GROUPS, RANDOM_STATE, SalaryParams

logger = logging.getLogger(__name__)

SKILL_FEATURE_PREFIX = "skill::"
LOC_FEATURE_PREFIX = "loc::"
JF_FEATURE_PREFIX = "jf::"
LEAKAGE_TOKENS = ("salary", "luong", "lương", "negotiable", "log_sal", "suspect", "outlier")
SALARY_VALID_RANGE_MIL = (1.0, 500.0)  # giống luật N6a của Normalization
ALL_SCOPE = "ALL"


class LeakageError(ValueError):
    pass


def assert_no_leakage(columns: list[str]) -> None:
    bad = [c for c in columns if any(tok in c.lower() for tok in LEAKAGE_TOKENS)
           and not c.startswith(SKILL_FEATURE_PREFIX)]
    if bad:
        raise LeakageError(f"Feature mang thông tin lương: {bad}")


def salary_level_ratio(meta: pd.DataFrame, min_level_count: int = 20) -> pd.Series:
    """Lương / trung vị lương cùng cấp bậc (NaN nếu không có lương hoặc cấp bậc có < 20 tin có lương).

    Trung vị bền với chính các tin lương ảo, nên dùng được làm luật lọc và luật giải thích.
    """
    sal = pd.to_numeric(meta["salary_avg_mil"], errors="coerce")
    sal = sal.where(sal > 0)
    sen = meta["seniority_ord"].astype(int)
    n_level = sal.groupby(sen).transform("count")
    return (sal / sal.groupby(sen).transform("median")).where(n_level >= min_level_count)


def select_training_subset(
    meta: pd.DataFrame,
    level_ratio_limit: float | None = None,
) -> tuple[np.ndarray, dict[str, int]]:
    """Mask Subset A và số dòng bị loại theo từng lý do.

    level_ratio_limit: nếu đặt (vd 3.0), loại tin có lương > 3x hoặc < 1/3 trung vị cùng cấp bậc
    (cùng luật SALARY_*_FOR_LEVEL ở anomaly.py). Vài tin lương ảo đủ làm Std(R2) qua 5-fold tăng gấp 3.
    """
    sal = pd.to_numeric(meta["salary_avg_mil"], errors="coerce")
    has = sal.notna() & (sal > 0)
    neg = meta["is_negotiable"].astype(bool)
    sus = meta["salary_suspect"].astype(bool)
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
        "n_dropped_suspect": int((has & ~neg & sus).sum()),
        "n_dropped_out_of_range": int((has & ~neg & ~sus & ~in_range).sum()),
        "n_dropped_implausible_vs_level": n_before_ratio - int(mask.sum()),
        "level_ratio_limit": level_ratio_limit,
        "n_train_subset": int(mask.sum()),
    }
    counts["share_train_subset"] = round(counts["n_train_subset"] / max(1, counts["n_jobs"]), 4)
    return mask.to_numpy(), counts


def build_salary_features(meta: pd.DataFrame, skills: pd.DataFrame) -> pd.DataFrame:
    X = pd.DataFrame(index=range(len(meta)))
    for c in skills.columns:
        X[f"{SKILL_FEATURE_PREFIX}{c}"] = skills[c].to_numpy(dtype=np.uint8)
    X["seniority_ord"] = meta["seniority_ord"].astype(int).to_numpy()
    exp = pd.to_numeric(meta["exp_min_years"], errors="coerce")
    X["exp_min_years"] = exp.fillna(-1).to_numpy(dtype=float)
    X["exp_min_years__missing"] = exp.isna().astype(np.uint8).to_numpy()
    for g in LOCATION_FEATURE_GROUPS:
        X[f"{LOC_FEATURE_PREFIX}{g}"] = (meta["location_group"] == g).astype(np.uint8).to_numpy()
    fam = meta["job_family"].fillna("Khác").astype(str)
    for f in sorted(fam.unique()):
        X[f"{JF_FEATURE_PREFIX}{f}"] = (fam == f).astype(np.uint8).to_numpy()
    assert_no_leakage(list(X.columns))
    return X


def _groups(meta: pd.DataFrame) -> np.ndarray | None:
    g = meta.get("dup_group_id")
    if g is None:
        return None
    g = pd.Series(g)
    if g.isna().all():
        return None
    # tin không thuộc nhóm trùng nào là một nhóm riêng
    return g.astype("string").fillna(meta["job_id"].astype("string")).to_numpy()


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


def _holdout_metrics(y_true_log: np.ndarray, y_pred_log: np.ndarray) -> dict[str, float]:
    t, p = np.expm1(y_true_log), np.expm1(y_pred_log)
    return {
        "r2_log": round(float(r2_score(y_true_log, y_pred_log)), 4),
        "r2_mil": round(float(r2_score(t, p)), 4),
        "mae_mil": round(float(mean_absolute_error(t, p)), 3),
        "rmse_mil": round(float(np.sqrt(mean_squared_error(t, p))), 3),
    }


def skill_values_from_shap(
    shap_values: np.ndarray,
    X: pd.DataFrame,
    job_family: pd.Series,
    base_salary_mil: float,
    min_sample: int,
) -> pd.DataFrame:
    """Bảng giá trị biên của kỹ năng theo phạm vi ALL và từng job_family."""
    skill_cols = [c for c in X.columns if c.startswith(SKILL_FEATURE_PREFIX)]
    col_idx = {c: X.columns.get_loc(c) for c in skill_cols}
    fam = pd.Series(job_family).reset_index(drop=True).fillna("Khác").astype(str).to_numpy()
    scopes = [(ALL_SCOPE, np.ones(len(X), dtype=bool))] + [(f, fam == f) for f in sorted(set(fam))]
    rows = []
    for scope, smask in scopes:
        for c in skill_cols:
            j = col_idx[c]
            present = smask & (X[c].to_numpy() == 1)
            n = int(present.sum())
            if n == 0:
                continue
            phi = float(shap_values[present, j].mean())
            rows.append({  # 5 cột đầu theo hợp đồng spec 07 §5.3, sau đó là cột bổ sung
                "skill_name": c[len(SKILL_FEATURE_PREFIX):],
                "job_family": scope,
                "mean_shap_value": phi,
                "marginal_dollar_vnd": float(base_salary_mil * 1e6 * np.expm1(phi)),
                "sample_size": n,
                "marginal_trieu": float(base_salary_mil * np.expm1(phi)),
                "abs_mean_shap": float(np.abs(shap_values[smask, j]).mean()),
                "is_reliable": bool(n >= min_sample),
            })
    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=["skill_name", "job_family", "mean_shap_value", "marginal_dollar_vnd",
                                     "sample_size", "marginal_trieu", "abs_mean_shap", "is_reliable", "rank"])
    out["rank"] = np.nan
    rel = out["is_reliable"]
    out.loc[rel, "rank"] = (out[rel].groupby("job_family")["marginal_dollar_vnd"]
                            .rank(ascending=False, method="first"))
    out["rank"] = out["rank"].astype("Int64")
    return out.sort_values(["job_family", "rank", "marginal_dollar_vnd"], ascending=[True, True, False],
                           na_position="last").reset_index(drop=True)


def train_salary_model(
    meta: pd.DataFrame,
    skills: pd.DataFrame,
    params: SalaryParams | None = None,
    random_state: int = RANDOM_STATE,
    compute_shap: bool = True,
) -> tuple[RandomForestRegressor | None, pd.DataFrame, dict[str, Any]]:
    """Trả (model fit trên toàn Subset A, bảng giá trị kỹ năng, metrics)."""
    p = params or SalaryParams()
    mask, counts = select_training_subset(meta, p.level_ratio_limit)
    metrics: dict[str, Any] = {"subset": counts, "target": "log1p(salary_avg, triệu VNĐ/tháng)"}
    if counts["n_train_subset"] < max(50, p.cv_folds * 10):
        metrics["skipped"] = f"Chỉ có {counts['n_train_subset']} tin có lương, không đủ để huấn luyện."
        return None, skill_values_from_shap(np.zeros((0, 0)), pd.DataFrame(), pd.Series(dtype=str), 0, 1), metrics

    X_all = build_salary_features(meta, skills)
    X = X_all.loc[mask].reset_index(drop=True)
    sub_meta = meta.loc[mask].reset_index(drop=True)
    y = np.log1p(sub_meta["salary_avg_mil"].to_numpy(dtype=float))
    groups = _groups(sub_meta)

    if groups is not None:
        tr_idx, te_idx = next(GroupShuffleSplit(n_splits=1, test_size=p.test_size, random_state=random_state)
                              .split(X, y, groups))
        split_method = "GroupShuffleSplit theo dup_group_id"
    else:
        tr_idx, te_idx = train_test_split(np.arange(len(X)), test_size=p.test_size, random_state=random_state)
        split_method = "train_test_split ngẫu nhiên (chưa có dup_group_id)"
    X_tr, X_te, y_tr, y_te = X.iloc[tr_idx], X.iloc[te_idx], y[tr_idx], y[te_idx]
    g_tr = groups[tr_idx] if groups is not None else None

    # Chọn tham số bằng CV trên phần train (không nhìn holdout)
    grid = []
    for prm in p.param_grid:
        sc = _cv_scores(X_tr, y_tr, g_tr, prm, p.cv_folds, random_state)
        grid.append({"params": prm, "cv_r2_mean": float(np.mean(sc)), "cv_r2_std": float(np.std(sc)),
                     "cv_r2_folds": [round(s, 4) for s in sc]})
    best = max(grid, key=lambda g: g["cv_r2_mean"])
    model = _rf(best["params"], random_state).fit(X_tr, y_tr)
    holdout = _holdout_metrics(y_te, model.predict(X_te))

    base_cols = ["seniority_ord", "exp_min_years", "exp_min_years__missing"]
    base_model = _rf(best["params"], random_state).fit(X_tr[base_cols], y_tr)
    baseline = _holdout_metrics(y_te, base_model.predict(X_te[base_cols]))

    importances = sorted(zip(X.columns, model.feature_importances_, strict=False), key=lambda kv: -kv[1])[:20]
    metrics.update({
        "split_method": split_method,
        "n_train": int(len(tr_idx)), "n_test": int(len(te_idx)), "n_features": int(X.shape[1]),
        "param_search": [{**g, "cv_r2_mean": round(g["cv_r2_mean"], 4), "cv_r2_std": round(g["cv_r2_std"], 4)}
                         for g in grid],
        "best_params": best["params"],
        "cv_r2_mean": round(best["cv_r2_mean"], 4), "cv_r2_std": round(best["cv_r2_std"], 4),
        "holdout": holdout,
        "baseline_seniority_exp": baseline,
        "meets_r2_target": bool(holdout["r2_log"] >= p.r2_target),
        "meets_mae_target": bool(holdout["mae_mil"] <= p.mae_target_mil),
        "meets_cv_std_target": bool(best["cv_r2_std"] <= p.cv_std_target),
        "targets": {"r2_log": p.r2_target, "mae_mil": p.mae_target_mil, "cv_r2_std": p.cv_std_target},
        "top_feature_importances": [{"feature": f, "importance": round(float(v), 4)} for f, v in importances],
    })

    # Model cuối: fit lại trên toàn Subset A để giải thích và lưu
    final = _rf(best["params"], random_state).fit(X, y)
    metrics["final_model"] = "fit lại trên toàn Subset A (chỉ số đánh giá lấy từ holdout ở trên)"

    values = skill_values_from_shap(np.zeros((0, 0)), pd.DataFrame(), pd.Series(dtype=str), 0, 1)
    if compute_shap:
        import shap

        rng = np.random.default_rng(random_state)
        idx = np.arange(len(X)) if len(X) <= p.max_shap_rows else np.sort(rng.choice(len(X), p.max_shap_rows, replace=False))
        X_exp = X.iloc[idx].reset_index(drop=True)
        explainer = shap.TreeExplainer(final)
        sv = np.asarray(explainer.shap_values(X_exp, check_additivity=False))
        ev = float(np.ravel(explainer.expected_value)[0])
        base_mil = float(np.expm1(ev))
        values = skill_values_from_shap(sv, X_exp, sub_meta["job_family"].iloc[idx], base_mil, p.min_skill_sample)
        top = values[(values["job_family"] == ALL_SCOPE) & values["is_reliable"]].head(p.top_k_report)
        metrics["shap"] = {
            "n_rows_explained": int(len(X_exp)),
            "expected_value_log": round(ev, 4),
            "baseline_salary_mil": round(base_mil, 3),
            "formula": "marginal = baseline_salary * (exp(mean phi | skill=1) - 1)",
            "min_skill_sample": p.min_skill_sample,
            "top_skills": [{"skill": r.skill_name, "marginal_trieu": round(r.marginal_trieu, 2),
                            "phi": round(r.mean_shap_value, 4), "n": int(r.sample_size)}
                           for r in top.itertuples()],
        }
    return final, values, metrics
