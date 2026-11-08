"""Thuật toán 4: phát hiện tin tuyển dụng bất thường (spec 07 §5).

- Isolation Forest trên x = [kinh nghiệm, log lương, log lương lệch so với trung vị cùng cấp bậc,
  số kỹ năng, số kỹ năng / (cấp bậc + 1), cấp bậc].
  55% tin không có lương: không bù giá trị, mà điền hằng số + cờ salary__missing để cây tách được.
  anomaly_score = -score_samples() = s(x, n) của bài báo gốc (≈1 là bất thường, < 0.5 là bình thường).
- GLOSH (HDBSCAN, tính ở bước phân cụm): tin có điểm GLOSH vượt ngưỡng phân vị là ngoại lai hồ sơ kỹ năng.
- reason_code gán bằng luật dễ đọc để người xem hiểu vì sao tin bị gắn cờ.
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

ANOMALY_COLUMNS = ["job_id", "job_title", "company_name", "anomaly_score", "reason_code", "detected_by",
                   "isolation_score", "glosh_outlier_score"]


def build_anomaly_space(meta: pd.DataFrame) -> pd.DataFrame:
    sal = pd.to_numeric(meta["salary_avg_mil"], errors="coerce")
    sal = sal.where(sal > 0)
    exp = pd.to_numeric(meta["exp_min_years"], errors="coerce")
    sen = meta["seniority_ord"].astype(int)
    n_sk = meta["n_skills"].astype(float)
    log_sal = np.log1p(sal)
    # "lương ảo so với cấp bậc": độ lệch log lương so với trung vị cùng cấp bậc (0 khi không có lương)
    level_median = log_sal.groupby(sen).transform("median")
    return pd.DataFrame({
        "exp_min_years": exp.fillna(-1).to_numpy(),
        "exp__missing": exp.isna().astype(int).to_numpy(),
        "log_salary": log_sal.fillna(0).to_numpy(),
        "log_salary_vs_level": (log_sal - level_median).fillna(0).to_numpy(),
        "salary__missing": sal.isna().astype(int).to_numpy(),
        "n_skills": n_sk.to_numpy(),
        "skills_per_level": (n_sk / (sen.clip(lower=0) + 1)).to_numpy(),
        "seniority_ord": sen.to_numpy(),
    })


def _reason_codes(meta: pd.DataFrame, p: AnomalyParams) -> pd.Series:
    """Luật giải thích, xét theo thứ tự ưu tiên."""
    exp = pd.to_numeric(meta["exp_min_years"], errors="coerce")
    sen = meta["seniority_ord"].astype(int)
    n_sk = meta["n_skills"].astype(int)
    ratio = salary_level_ratio(meta)  # trung vị bền với chính các tin bất thường, khác phân vị 99%
    sk99 = n_sk.quantile(0.99)

    codes = pd.Series("ISOLATION_GENERIC", index=meta.index, dtype="object")
    rules = [
        ("TOO_MANY_SKILLS", n_sk > sk99),
        ("SALARY_TOO_LOW_FOR_LEVEL", ratio < 1 / p.salary_ratio_limit),
        ("SALARY_TOO_HIGH_FOR_LEVEL", ratio > p.salary_ratio_limit),
        ("EXP_SENIORITY_MISMATCH", (sen.between(0, 1)) & (exp >= p.exp_mismatch_years)),
        ("FRESHER_TOO_MANY_SKILLS", (sen.between(0, 1)) & (n_sk > p.fresher_skill_limit)),
    ]
    for code, cond in rules:  # luật sau ghi đè luật trước -> luật cụ thể nhất đứng cuối
        codes[cond.fillna(False).to_numpy()] = code
    return codes


def detect_anomalies(
    meta: pd.DataFrame,
    glosh_scores: np.ndarray | None = None,
    glosh_flags: np.ndarray | None = None,
    params: AnomalyParams | None = None,
    random_state: int = RANDOM_STATE,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Trả (bảng tin bất thường, metrics). Chỉ các tin bị gắn cờ có trong bảng."""
    p = params or AnomalyParams()
    X = build_anomaly_space(meta)
    iso = IsolationForest(n_estimators=p.n_estimators, contamination=p.contamination, random_state=random_state)
    iso_flag = iso.fit_predict(X) == -1
    iso_score = -iso.score_samples(X)

    glosh = np.zeros(len(meta)) if glosh_scores is None else np.asarray(glosh_scores, dtype=float)
    g_flag = np.zeros(len(meta), dtype=bool) if glosh_flags is None else np.asarray(glosh_flags, dtype=bool)

    reasons = _reason_codes(meta, p)
    flagged = iso_flag | g_flag
    detected_by = np.where(iso_flag & g_flag, "IsolationForest+HDBSCAN_GLOSH",
                           np.where(iso_flag, "IsolationForest", "HDBSCAN_GLOSH"))
    reasons = reasons.where(iso_flag | (reasons != "ISOLATION_GENERIC"), "SKILL_PROFILE_OUTLIER")

    out = pd.DataFrame({
        "job_id": meta["job_id"].astype(str).to_numpy(),
        "job_title": meta["job_title"].to_numpy(),
        "company_name": meta["company_name"].to_numpy(),
        # điểm tổng hợp: lấy điểm cao hơn của 2 phương pháp (cả hai đều trong 0..1)
        "anomaly_score": np.maximum(iso_score, glosh * g_flag),
        "reason_code": reasons.to_numpy(),
        "detected_by": detected_by,
        "isolation_score": iso_score,
        "glosh_outlier_score": glosh,
    })[flagged].sort_values("anomaly_score", ascending=False).reset_index(drop=True)

    metrics = {
        "params": {"contamination": p.contamination, "n_estimators": p.n_estimators,
                   "fresher_skill_limit": p.fresher_skill_limit, "exp_mismatch_years": p.exp_mismatch_years,
                   "salary_ratio_limit": p.salary_ratio_limit},
        "feature_space": list(X.columns),
        "n_jobs": int(len(meta)),
        "n_flagged": int(flagged.sum()),
        "anomaly_rate": round(float(flagged.mean()), 4),
        "n_isolation_forest": int(iso_flag.sum()),
        "n_glosh": int(g_flag.sum()),
        "n_both": int((iso_flag & g_flag).sum()),
        "reason_counts": out["reason_code"].value_counts().to_dict(),
        "isolation_score_threshold": round(float(-iso.offset_), 4),
    }
    return out, metrics
