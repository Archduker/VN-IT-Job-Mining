"""M4: tin "khác hoặc mới" cho SD3 câu 3.3 (docs/spec/mining/M4_tin_khac_moi.md).

- Isolation Forest trên x = [kinh nghiệm, log lương, log lương lệch so với trung vị cùng cấp, số công cụ (`n_tools`
  của bước 10), số công cụ / (cấp + 1), cấp]. Lương là `salary_target_m` của tin không bị Silver gắn `salary_outlier`;
  thiếu thì điền hằng + cờ `salary__missing`, không bù.
- Quyết định 1.B (20/11): Isolation Forest chỉ fit trên tin biết cấp (seniority_ord >= 0). Cấp −1 nằm tách riêng
  trong không gian nên IF từng bắt "tin thiếu cấp" (97/117 cờ, nhóm này chỉ 7% dữ liệu). Tin chưa rõ cấp không có
  isolation_score; vẫn được xét bằng GLOSH và luật: có mã lý do cụ thể thì gắn cờ với nguồn "rule".
- GLOSH (M3): tin có cờ GLOSH là hồ sơ kỹ năng lạ. Tin không vào phân cụm (M3.1b) có GLOSH null, không cờ.
- Mã lý do theo luật dễ đọc, luật sau ghi đè luật trước (M4.4); ngưỡng số công cụ theo phân vị dữ liệu, tính lại
  mỗi lần chạy và ghi vào metrics (M4.4a).
- Loại (M4.5): "khac" = có mã cụ thể; "moi" = cờ GLOSH, mã chung, các trường nằm trong P5–P95 của cấp;
  còn lại "chua_ro". "Khác" không có nghĩa là lừa đảo; "mới" không có nghĩa là đang tăng.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from mining.config import RANDOM_STATE, AnomalyParams
from mining.salary_model import salary_level_ratio

logger = logging.getLogger(__name__)

# 6 cột đầu theo bảng Mart (scripts/load_mart_from_parquet.py); sau đó là cột M4
ANOMALY_COLUMNS = ["job_id", "job_title", "company_name", "anomaly_score", "reason_code", "detected_by",
                   "isolation_score", "glosh_outlier_score", "source_flag", "kind", "n_tools", "exp_min_years",
                   "salary_ratio_to_level"]
GENERIC_CODES = ("ISOLATION_GENERIC", "SKILL_PROFILE_OUTLIER")
NEWCOMER_ORDS = (0, 1)  # Intern/Fresher, Junior


def _n_tools(meta: pd.DataFrame) -> pd.Series:
    col = "n_tools" if "n_tools" in meta else "n_skills"
    return pd.to_numeric(meta[col], errors="coerce").fillna(0).astype(float).reset_index(drop=True)


def _valid_salary(meta: pd.DataFrame) -> pd.Series:
    """salary_target_m (= salary_avg_mil) > 0 và không bị Silver gắn salary_outlier (M4.4c)."""
    sal = pd.to_numeric(meta["salary_avg_mil"], errors="coerce").reset_index(drop=True)
    out = meta["salary_outlier"].astype("boolean").fillna(False).astype(bool).reset_index(drop=True) \
        if "salary_outlier" in meta else pd.Series(False, index=sal.index)
    return sal.where((sal > 0) & ~out)


def _ratio(meta: pd.DataFrame) -> pd.Series:
    m = pd.DataFrame({"salary_avg_mil": _valid_salary(meta),
                      "seniority_ord": meta["seniority_ord"].astype(int).reset_index(drop=True)})
    return salary_level_ratio(m)


def build_anomaly_space(meta: pd.DataFrame) -> pd.DataFrame:
    sal = _valid_salary(meta)
    exp = pd.to_numeric(meta["exp_min_years"], errors="coerce").reset_index(drop=True)
    sen = meta["seniority_ord"].astype(int).reset_index(drop=True)
    n_t = _n_tools(meta)
    log_sal = np.log1p(sal)
    level_median = log_sal.groupby(sen).transform("median")
    return pd.DataFrame({
        "exp_min_years": exp.fillna(-1).to_numpy(),
        "exp__missing": exp.isna().astype(int).to_numpy(),
        "log_salary": log_sal.fillna(0).to_numpy(),
        "log_salary_vs_level": (log_sal - level_median).fillna(0).to_numpy(),
        "salary__missing": sal.isna().astype(int).to_numpy(),
        "n_tools": n_t.to_numpy(),
        "tools_per_level": (n_t / (sen.clip(lower=0) + 1)).to_numpy(),
        "seniority_ord": sen.to_numpy(),
    })


def _reason_codes(meta: pd.DataFrame, p: AnomalyParams, glosh_flag: np.ndarray) -> tuple[pd.Series, dict[str, float]]:
    """M4.4: luật sau ghi đè luật trước (luật cụ thể nhất đứng cuối). Trả (mã, ngưỡng đã dùng)."""
    meta = meta.reset_index(drop=True)
    exp = pd.to_numeric(meta["exp_min_years"], errors="coerce")
    sen = meta["seniority_ord"].astype(int)
    n_t = _n_tools(meta)
    new = sen.isin(NEWCOMER_ORDS)
    ratio = _ratio(meta)
    t_all = float(np.quantile(n_t, p.too_many_q))
    t_new = float(np.quantile(n_t[new], p.fresher_q)) if new.any() else float("inf")
    flagged_out = meta["salary_outlier"].astype("boolean").fillna(False).astype(bool) if "salary_outlier" in meta \
        else pd.Series(False, index=meta.index)
    codes = pd.Series("ISOLATION_GENERIC", index=meta.index, dtype="object")
    rules = [
        ("SKILL_PROFILE_OUTLIER", pd.Series(np.asarray(glosh_flag, dtype=bool))),
        ("TOO_MANY_SKILLS", n_t > t_all),
        ("SALARY_OUTLIER_FLAGGED", flagged_out),
        ("SALARY_TOO_LOW_FOR_LEVEL", ratio < 1 / p.salary_ratio_limit),
        ("SALARY_TOO_HIGH_FOR_LEVEL", ratio > p.salary_ratio_limit),
        ("EXP_SENIORITY_MISMATCH", new & (exp >= p.exp_mismatch_years)),
        ("FRESHER_TOO_MANY_SKILLS", new & (n_t > t_new)),
    ]
    for code, cond in rules:
        codes[cond.fillna(False).to_numpy()] = code
    thresholds = {"too_many_skills_gt": round(t_all, 4), "too_many_q": p.too_many_q,
                  "fresher_too_many_skills_gt": round(t_new, 4), "fresher_q": p.fresher_q,
                  "salary_ratio_limit": p.salary_ratio_limit, "exp_mismatch_years": p.exp_mismatch_years}
    return codes, thresholds


def classify_kind(meta: pd.DataFrame, codes: pd.Series, glosh_flag: np.ndarray, p: AnomalyParams) -> pd.Series:
    """M4.5. Trường thiếu (không có lương, không ghi kinh nghiệm) coi như không lệch."""
    meta = meta.reset_index(drop=True)
    codes = pd.Series(codes).reset_index(drop=True)
    sen = meta["seniority_ord"].astype(int)
    lo, hi = p.normal_band
    inside = pd.Series(True, index=meta.index)
    for v in (pd.to_numeric(meta["exp_min_years"], errors="coerce"), _valid_salary(meta), _n_tools(meta)):
        q_lo = v.groupby(sen).transform(lambda s: s.quantile(lo))
        q_hi = v.groupby(sen).transform(lambda s: s.quantile(hi))
        inside &= (v.isna() | ((v >= q_lo) & (v <= q_hi))).fillna(True)
    generic = codes.isin(GENERIC_CODES)
    g = pd.Series(np.asarray(glosh_flag, dtype=bool))
    kind = pd.Series("chua_ro", index=meta.index, dtype="object")
    kind[~generic] = "khac"
    kind[generic & g & inside] = "moi"
    return kind


def hand_check_sample(out: pd.DataFrame, n: int, random_state: int = RANDOM_STATE) -> pd.DataFrame:
    """M4.6: n tin phân tầng theo kind, tỷ lệ theo số tin, mỗi loại có mặt >= 1 tin."""
    if out.empty:
        return pd.DataFrame(columns=["job_id", "job_title", "kind", "reason_code", "dung", "loi_parse", "ghi_chu"])
    vc = out["kind"].value_counts()
    n = min(n, len(out))
    alloc = {k: max(1, int(round(n * c / len(out)))) for k, c in vc.items()}
    while sum(alloc.values()) > n:  # bớt ở loại đông nhất
        k = max(alloc, key=lambda x: (alloc[x], x))
        alloc[k] -= 1
    while sum(alloc.values()) < n:
        k = max(vc.index, key=lambda x: (vc[x] - alloc[x], x))
        alloc[k] += 1
    parts = [out[out["kind"] == k].sample(min(a, int(vc[k])), random_state=random_state) for k, a in sorted(alloc.items())]
    cols = [c for c in ("job_id", "job_title", "kind", "reason_code", "n_tools", "exp_min_years", "salary_ratio_to_level")
            if c in out]
    return pd.concat(parts)[cols].assign(dung=pd.NA, loi_parse=pd.NA, ghi_chu=pd.NA).reset_index(drop=True)


def detect_anomalies(
    meta: pd.DataFrame,
    glosh_scores: np.ndarray | None = None,
    glosh_flags: np.ndarray | None = None,
    params: AnomalyParams | None = None,
    random_state: int = RANDOM_STATE,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Trả (bảng tin bị gắn cờ, metrics)."""
    p = params or AnomalyParams()
    meta = meta.reset_index(drop=True)
    X = build_anomaly_space(meta)
    known = (meta["seniority_ord"].astype(int) >= 0).to_numpy()
    iso = IsolationForest(n_estimators=p.n_estimators, contamination=p.contamination, random_state=random_state)
    iso_flag = np.zeros(len(meta), dtype=bool)
    iso_score = np.full(len(meta), np.nan)
    iso_flag[known] = iso.fit_predict(X[known]) == -1
    iso_score[known] = -iso.score_samples(X[known])

    glosh = np.full(len(meta), np.nan) if glosh_scores is None else np.asarray(glosh_scores, dtype=float)
    g_flag = np.zeros(len(meta), dtype=bool) if glosh_flags is None else np.asarray(glosh_flags, dtype=bool)
    g_flag = g_flag & ~np.isnan(glosh)  # tin không vào phân cụm không có cờ GLOSH

    reasons, thresholds = _reason_codes(meta, p, g_flag)
    kind = classify_kind(meta, reasons, g_flag, p)
    rule_flag = ~known & ~reasons.isin(GENERIC_CODES).to_numpy() & ~g_flag  # 1.B: tin chưa rõ cấp có mã cụ thể
    flagged = iso_flag | g_flag | rule_flag
    detected_by = np.where(iso_flag & g_flag, "IsolationForest+HDBSCAN_GLOSH",
                           np.where(iso_flag, "IsolationForest", np.where(g_flag, "HDBSCAN_GLOSH", "Rule")))
    source = np.where(iso_flag & g_flag, "both", np.where(iso_flag, "if", np.where(g_flag, "glosh", "rule")))
    out = pd.DataFrame({
        "job_id": meta["job_id"].astype(str).to_numpy(),
        "job_title": meta["job_title"].to_numpy() if "job_title" in meta else None,
        "company_name": meta["company_name"].to_numpy() if "company_name" in meta else None,
        "anomaly_score": np.maximum(np.nan_to_num(iso_score), np.nan_to_num(glosh) * g_flag),  # cả hai trong 0..1
        "reason_code": reasons.to_numpy(),
        "detected_by": detected_by,
        "isolation_score": iso_score,
        "glosh_outlier_score": glosh,
        "source_flag": source,
        "kind": kind.to_numpy(),
        "n_tools": _n_tools(meta).to_numpy(),
        "exp_min_years": pd.to_numeric(meta["exp_min_years"], errors="coerce").to_numpy(),
        "salary_ratio_to_level": _ratio(meta).round(3).to_numpy(),
    })[flagged].sort_values("anomaly_score", ascending=False, kind="stable").reset_index(drop=True)[ANOMALY_COLUMNS]

    metrics = {
        "params": {"contamination": p.contamination, "n_estimators": p.n_estimators, "normal_band": list(p.normal_band)},
        "thresholds_used": thresholds,
        "feature_space": list(X.columns),
        "n_jobs": int(len(meta)),
        "n_flagged": int(flagged.sum()),
        "anomaly_rate": round(float(flagged.mean()), 4),
        "n_isolation_forest": int(iso_flag.sum()),
        "n_glosh": int(g_flag.sum()),
        "n_both": int((iso_flag & g_flag).sum()),
        "n_rule_unknown_level": int(rule_flag.sum()),
        "n_unknown_level_excluded_from_if": int((~known).sum()),
        "n_without_glosh": int(np.isnan(glosh).sum()),
        "reason_counts": out["reason_code"].value_counts().to_dict(),
        "kind_counts": out["kind"].value_counts().to_dict(),
        "kind_by_reason": out.groupby(["kind", "reason_code"]).size().rename("n").reset_index().to_dict(orient="records"),
        "share_chua_ro": round(float((out["kind"] == "chua_ro").mean()), 4) if len(out) else None,
        "isolation_score_threshold": round(float(-iso.offset_), 4),
    }
    return out, metrics
