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


# ---------------------------------------------------------------------------
# M4 (docs/spec/mining/M4_tin_khac_moi.md, prompt mục 5)
# ---------------------------------------------------------------------------
import pandas as pd  # noqa: E402

from mining.anomaly import _reason_codes, classify_kind, hand_check_sample  # noqa: E402
from mining.config import AnomalyParams  # noqa: E402

KIND_SET = {"khac", "moi", "chua_ro"}


def _meta(n_tools, seniority_ord=None, salary=None, outlier=None, exp=None):
    n = len(n_tools)
    return pd.DataFrame({
        "job_id": [f"j{i}" for i in range(n)],
        "n_tools": n_tools,
        "seniority_ord": seniority_ord if seniority_ord is not None else [2] * n,
        "salary_avg_mil": salary if salary is not None else [np.nan] * n,
        "salary_outlier": outlier if outlier is not None else [False] * n,
        "exp_min_years": exp if exp is not None else [2.0] * n,
    })


def test_too_many_skills_threshold_is_p99_of_data():
    meta = _meta(list(range(1, 101)))
    codes, th = _reason_codes(meta, AnomalyParams(), np.zeros(100, bool))
    assert th["too_many_skills_gt"] == pytest.approx(99.01)
    assert codes.iloc[99] == "TOO_MANY_SKILLS" and codes.iloc[98] == "ISOLATION_GENERIC"


def test_newcomer_above_p95_of_newcomers_is_fresher_too_many():
    tools = [3] * 95 + [4, 5, 6, 7, 20]
    meta = _meta(tools, seniority_ord=[1] * 100)  # Junior
    codes, th = _reason_codes(meta, AnomalyParams(), np.zeros(100, bool))
    assert th["fresher_too_many_skills_gt"] == pytest.approx(np.quantile(tools, 0.95))
    assert codes.iloc[99] == "FRESHER_TOO_MANY_SKILLS"
    kind = classify_kind(meta, codes, np.zeros(100, bool), AnomalyParams())
    assert kind.iloc[99] == "khac"


def test_flagged_salary_outlier_gets_own_code_not_level_code():
    sal = [20.0] * 40 + [200.0]
    meta = _meta([5] * 41, salary=sal, outlier=[False] * 40 + [True])
    codes, _ = _reason_codes(meta, AnomalyParams(), np.zeros(41, bool))
    assert codes.iloc[40] == "SALARY_OUTLIER_FLAGGED"


def test_glosh_job_with_normal_fields_is_new_and_isolation_only_odd_job_is_unclear():
    rng = np.random.default_rng(0)
    meta = _meta(list(rng.integers(3, 8, 200)), salary=list(rng.normal(20, 2, 200)), exp=list(rng.normal(3, 0.5, 200)))
    meta.loc[0, ["n_tools", "salary_avg_mil", "exp_min_years"]] = [5, 20.0, 3.0]  # giữa phân bố của cấp
    meta.loc[1, "exp_min_years"] = 12.0  # lệch kinh nghiệm so với cấp, không có mã cụ thể
    g = np.zeros(200, bool)
    g[0] = True
    codes, _ = _reason_codes(meta, AnomalyParams(), g)
    kind = classify_kind(meta, codes, g, AnomalyParams())
    assert codes.iloc[0] == "SKILL_PROFILE_OUTLIER" and kind.iloc[0] == "moi"
    assert codes.iloc[1] == "ISOLATION_GENERIC" and kind.iloc[1] == "chua_ro"


def test_job_left_out_of_clustering_keeps_isolation_score_and_null_glosh(setup):
    b, data = setup
    planted = set(b.truth["anomaly_ids"])
    ids = data.meta["job_id"].astype(str)
    glosh = np.where(ids.isin(planted), np.nan, 0.1)  # tin cài sẵn không vào phân cụm
    out, m = detect_anomalies(data.meta, glosh, np.zeros(len(ids), bool))
    rows = out[out["job_id"].isin(planted)]
    assert len(rows) == len(planted)
    assert rows["glosh_outlier_score"].isna().all() and rows["isolation_score"].notna().all()


def test_each_flagged_job_has_one_kind_and_reason_and_thresholds_in_metrics(setup):
    _, data = setup
    out, m = detect_anomalies(data.meta)
    assert out["kind"].isin(KIND_SET).all() and out["reason_code"].notna().all()
    assert out["source_flag"].isin({"if", "glosh", "both", "rule"}).all()
    assert {"too_many_skills_gt", "fresher_too_many_skills_gt"} <= set(m["thresholds_used"])
    assert sum(m["kind_counts"].values()) == len(out)


def test_hand_check_sample_is_stratified_by_kind():
    out = pd.DataFrame({"job_id": [f"j{i}" for i in range(100)], "job_title": "t",
                        "kind": ["khac"] * 70 + ["moi"] * 28 + ["chua_ro"] * 2, "reason_code": "X",
                        "n_tools": 1, "exp_min_years": 1.0, "salary_ratio_to_level": np.nan})
    hc = hand_check_sample(out, 20, 42)
    vc = hc["kind"].value_counts().to_dict()
    assert len(hc) == 20 and vc["chua_ro"] >= 1 and vc["khac"] > vc["moi"]
    assert {"dung", "loi_parse", "ghi_chu"} <= set(hc.columns)


def test_unknown_level_jobs_are_not_scored_by_isolation_forest(setup):
    """1.B (20/11): IF chỉ fit trên tin biết cấp; tin chưa rõ cấp chỉ được gắn cờ qua GLOSH hoặc mã lý do cụ thể."""
    _, data = setup
    meta = data.meta.copy()
    meta.loc[meta.index[:60], "seniority_ord"] = -1
    meta.loc[meta.index[0], "n_tools"] = 500  # chưa rõ cấp nhưng quá nhiều công cụ → mã cụ thể
    out, m = detect_anomalies(meta)
    unk = out[out["job_id"].isin(meta["job_id"].iloc[:60].astype(str))]
    assert unk["isolation_score"].isna().all() and (unk["source_flag"] != "if").all()
    row = out[out["job_id"] == str(meta["job_id"].iloc[0])].iloc[0]
    assert row["source_flag"] == "rule" and row["reason_code"] == "TOO_MANY_SKILLS"
    assert m["n_unknown_level_excluded_from_if"] == int((meta["seniority_ord"] < 0).sum())
