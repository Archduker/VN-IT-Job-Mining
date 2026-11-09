"""mining/anomaly.py: Isolation Forest + GLOSH bắt lại tin bất thường cài sẵn, mã lý do đúng."""

import numpy as np
import pytest

from mining.anomaly import build_anomaly_space, detect_anomalies
from mining.data_io import prepare_mining_data
from mining.synthetic import make_synthetic_jobs

MART_COLUMNS = ["job_id", "job_title", "company_name", "anomaly_score", "reason_code", "detected_by"]


@pytest.fixture(scope="module")
def setup():
    b = make_synthetic_jobs(n_jobs=1500, seed=42)
    data = prepare_mining_data(b.golden, b.features, b.encoding_dict["skills"]["skills_map"])
    return b, data


def test_planted_anomalies_are_flagged_with_reason(setup):
    b, data = setup
    out, m = detect_anomalies(data.meta)
    planted = set(b.truth["anomaly_ids"])
    flagged = out.set_index("job_id")
    assert planted <= set(flagged.index)
    reasons = flagged.loc[sorted(planted), "reason_code"].value_counts().to_dict()
    assert reasons == {"FRESHER_TOO_MANY_SKILLS": 12, "SALARY_TOO_HIGH_FOR_LEVEL": 6}
    assert list(out.columns[:len(MART_COLUMNS)]) == MART_COLUMNS
    assert out["anomaly_score"].is_monotonic_decreasing
    assert m["n_flagged"] == len(out) and m["anomaly_rate"] < 0.1


def test_glosh_flags_are_merged(setup):
    _, data = setup
    n = data.n_jobs
    g_flag = np.zeros(n, dtype=bool)
    g_flag[:5] = True
    out, m = detect_anomalies(data.meta, np.where(g_flag, 0.99, 0.1), g_flag)
    assert set(data.meta["job_id"].iloc[:5]) <= set(out["job_id"])
    assert m["n_glosh"] == 5
    glosh_only = out[out["detected_by"] == "HDBSCAN_GLOSH"]
    assert (glosh_only["anomaly_score"] >= 0.99).all()  # điểm tổng hợp = max(Isolation, GLOSH)
    assert set(glosh_only["reason_code"]) <= {"SKILL_PROFILE_OUTLIER", "TOO_MANY_SKILLS", "FRESHER_TOO_MANY_SKILLS",
                                             "SALARY_TOO_HIGH_FOR_LEVEL", "SALARY_TOO_LOW_FOR_LEVEL",
                                             "EXP_SENIORITY_MISMATCH"}


def test_missing_salary_is_flagged_not_imputed(setup):
    _, data = setup
    X = build_anomaly_space(data.meta)
    missing = data.meta["salary_avg_mil"].isna().to_numpy()
    assert (X.loc[missing, "salary__missing"] == 1).all()
    assert (X.loc[missing, "log_salary"] == 0).all() and (X.loc[missing, "log_salary_vs_level"] == 0).all()
    assert not X.isna().any().any()
