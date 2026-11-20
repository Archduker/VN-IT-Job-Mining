"""mining/salary_model.py: Subset A, chống rò rỉ, đánh giá và giá trị biên SHAP."""

import numpy as np
import pandas as pd
import pytest

from mining.data_io import prepare_mining_data
from mining.config import SalaryParams
from mining.salary_model import (
    ALL_SCOPE,
    LeakageError,
    _groups,
    assert_no_leakage,
    baseline_level_family,
    build_salary_features,
    company_split,
    compare_distributions,
    select_training_subset,
    skill_values_from_shap,
    train_salary_model,
)
from mining.synthetic import make_synthetic_jobs

SHAP_MART_COLUMNS = ["skill_name", "job_family", "mean_shap_value", "marginal_dollar_vnd", "sample_size"]


@pytest.fixture(scope="module")
def data():
    b = make_synthetic_jobs(n_jobs=2000, seed=11)
    return prepare_mining_data(b.golden, b.features, b.encoding_dict["skills"]["skills_map"])


@pytest.fixture(scope="module")
def trained(data):
    return train_salary_model(data.meta, data.skills, concepts=data.concepts)


def test_subset_excludes_negotiable_suspect_and_implausible():
    meta = pd.DataFrame({
        "salary_avg_mil": [10, 12, np.nan, 11, 700, 400] + [15] * 25,
        "is_negotiable": [False, True, True, False, False, False] + [False] * 25,
        "salary_outlier": [False, False, False, True, False, False] + [False] * 25,
        "seniority_ord": [2] * 31,
    })
    mask, c = select_training_subset(meta, level_ratio_limit=3.0)
    assert not mask[1] and not mask[2] and not mask[3]  # thỏa thuận, thiếu, nghi ngờ
    assert not mask[4]  # ngoài 1–500 triệu
    assert not mask[5]  # > 3x trung vị cùng cấp bậc
    assert mask[0] and c["n_dropped_implausible_vs_level"] == 1
    assert c["n_train_subset"] == int(mask.sum())
    mask_off, _ = select_training_subset(meta, level_ratio_limit=None)
    assert mask_off[5]


def test_features_have_no_salary_columns(data):
    X = build_salary_features(data.meta, data.skills)
    assert not [c for c in X.columns if "salary" in c.lower() and not c.startswith("skill::")]
    assert {"seniority_ord", "exp_min_years", "exp_min_years__missing", "loc::ha_noi"} <= set(X.columns)
    assert not X.isna().any().any()
    with pytest.raises(LeakageError):
        assert_no_leakage(["seniority_ord", "log_salary_max"])
    with pytest.raises(LeakageError):
        assert_no_leakage(["is_negotiable"])


def test_model_beats_baseline_and_reports_targets(trained):
    model, _, m, _ = trained
    assert model is not None
    assert m["holdout"]["mae_mil"] < m["baseline_level_family"]["mae_mil"]
    assert set(m["configs"]) == {"tool_only", "tool_concept"} and m["config_used"] == "tool_concept"
    assert m["holdout"]["r2_log"] >= 0.6 and m["meets_r2_target"]
    assert len(m["param_search"]) >= 2 and m["best_params"] in [g["params"] for g in m["param_search"]]
    assert m["n_train"] + m["n_test"] == m["subset"]["n_train_subset"]
    assert list(model.feature_names_in_)[:1][0].startswith("skill::")


def test_shap_recovers_planted_premiums(trained):
    _, values, m, _ = trained
    assert list(values.columns[:len(SHAP_MART_COLUMNS)]) == SHAP_MART_COLUMNS
    allv = values[values["job_family"] == ALL_SCOPE].set_index("skill_name")
    assert allv.loc["Kubernetes", "mean_shap_value"] > 0
    assert allv.loc["AWS", "mean_shap_value"] > 0
    # Kubernetes (+20% cài sẵn) phải đáng giá hơn một kỹ năng không có thưởng như HTML
    assert allv.loc["Kubernetes", "marginal_dollar_vnd"] > allv.loc["HTML", "marginal_dollar_vnd"]
    assert m["shap"]["baseline_salary_mil"] > 0
    assert values["is_reliable"].all() and values["rank"].notna().all()  # M5.10: chỉ giữ kỹ năng >= 30 tin


def test_skill_values_average_only_rows_with_skill():
    X = pd.DataFrame({"skill::A": [1, 0, 0, 0], "seniority_ord": [1, 1, 1, 1]})
    sv = np.array([[0.2, 0.0], [-0.01, 0.0], [-0.01, 0.0], [-0.01, 0.0]])
    out = skill_values_from_shap(sv, X, pd.Series(["F"] * 4), base_salary_mil=20.0, min_sample=1)
    row = out[(out["job_family"] == ALL_SCOPE)].iloc[0]
    assert row["mean_shap_value"] == pytest.approx(0.2)  # không phải trung bình 4 dòng (0.0425)
    assert row["marginal_dollar_vnd"] == pytest.approx(20e6 * np.expm1(0.2))
    assert row["sample_size"] == 1


def test_too_few_salaries_is_skipped_not_crashed():
    b = make_synthetic_jobs(n_jobs=60, seed=2)
    d = prepare_mining_data(b.golden, b.features, b.encoding_dict["skills"]["skills_map"])
    model, values, m, extra = train_salary_model(d.meta, d.skills)
    assert model is None and "skipped" in m and values.empty and extra["estimates"].empty


# ---------------------------------------------------------------------------
# M5 (docs/spec/mining/M5_luong_shap.md, prompt mục 5)
# ---------------------------------------------------------------------------
SEN_LABELS = ["Intern/Fresher", "Junior", "Middle", "Senior", "Lead/Manager"]


def _hand_jobs(n=900, seed=0, n_companies=150, premium=8.0, fam_only=False, neg_share=0.0, senior_neg=None):
    """Lương = 10 + 5·cấp + 8·[python] + nhiễu nhỏ (fam_only: chỉ theo cấp × nghề, không kỹ năng)."""
    rng = np.random.default_rng(seed)
    lvl = rng.integers(0, 4, n)
    fam = rng.choice(["Web", "Data/AI", "Tester"], n)
    py = rng.random(n) < 0.35
    other = rng.random((n, 3)) < 0.3
    neg = rng.random(n) < neg_share
    if senior_neg is not None:  # 300 tin đầu thỏa thuận, tỷ lệ Senior khác tập có lương
        neg = np.zeros(n, dtype=bool)
        neg[:300] = True
        lvl[:300] = np.where(rng.random(300) < senior_neg[0], 3, rng.integers(0, 3, 300))
        lvl[300:] = np.where(rng.random(n - 300) < senior_neg[1], 3, rng.integers(0, 3, n - 300))
    if fam_only:
        sal = 10 + 5 * lvl + np.select([fam == "Web", fam == "Data/AI"], [0.0, 6.0], 3.0)
    else:
        sal = 10 + 5 * lvl + premium * py + rng.normal(0, 0.5, n)
    meta = pd.DataFrame({
        "job_id": [f"j{i}" for i in range(n)],
        "company_id": [f"c{i % n_companies}" for i in range(n)],
        "salary_avg_mil": np.where(neg, np.nan, sal),
        "salary_target_m": np.where(neg, np.nan, sal),
        "is_negotiable": neg, "salary_outlier": False,
        "seniority_ord": lvl, "seniority": [SEN_LABELS[i] for i in lvl],
        "exp_min_years": lvl.astype(float), "location_group": "ha_noi",
        "job_family": fam, "source_platform": rng.choice(["topcv", "itviec"], n),
    })
    skills = pd.DataFrame({"python": py.astype(np.uint8), "git": other[:, 0].astype(np.uint8),
                           "docker": other[:, 1].astype(np.uint8), "jira": other[:, 2].astype(np.uint8)})
    return meta, skills


def test_split_keeps_each_company_on_one_side():
    meta = pd.DataFrame({"job_id": [f"j{i}" for i in range(60)], "company_id": [f"c{i // 20}" for i in range(60)]})
    tr, te, overlap = company_split(meta, 0.2, 42)
    assert overlap == 0 and len(tr) + len(te) == 60 and len(te) > 0
    assert not set(meta["company_id"].iloc[tr]) & set(meta["company_id"].iloc[te])


def test_missing_company_id_is_its_own_group():
    meta = pd.DataFrame({"job_id": ["a", "b", "c"], "company_id": ["x", None, "x"]})
    g = _groups(meta)
    assert g[0] == g[2] == "x" and g[1] == "job:b"


def test_features_have_source_dummies_and_reject_salary_columns():
    meta, skills = _hand_jobs(n=50)
    X = build_salary_features(meta, skills)
    assert {"src::itviec", "src::topcv"} <= set(X.columns)
    with pytest.raises(LeakageError):
        assert_no_leakage(list(X.columns) + ["salary_mid"])


def test_baseline_small_cell_falls_back_to_seniority():
    tr = pd.DataFrame({"job_family": ["Web"] * 40 + ["Game"] * 5, "seniority": ["Junior"] * 45,
                       "salary_target_m": [10.0] * 40 + [50.0] * 5, "salary_outlier": False})
    te = pd.DataFrame({"job_family": ["Web", "Game"], "seniority": ["Junior", "Junior"]})
    pred, info = baseline_level_family(tr, te, min_cell=30)
    assert pred[0] == 10.0 and pred[1] == 10.0  # Game chỉ 5 tin → trung vị cấp Junior (10)
    assert info["n_fallback_seniority"] == 1


@pytest.fixture(scope="module")
def planted():
    meta, skills = _hand_jobs(n=900, seed=0, neg_share=0.15)
    return meta, train_salary_model(meta, skills, SalaryParams(bootstrap_n=50))


def test_planted_skill_premium_is_recovered(planted):
    _, (_, values, m, _) = planted
    py = values[(values["job_family"] == ALL_SCOPE) & (values["skill_name"] == "python")].iloc[0]
    assert 4 < py["delta_m"] < 12 and py["ci_low"] <= py["delta_m"] <= py["ci_high"]
    assert m["n_companies_overlap"] == 0 and m["plan"] == "A"


def test_negotiable_jobs_get_estimate_interval(planted):
    meta, (_, _, m, extra) = planted
    est = extra["estimates"]
    assert set(est["job_id"]) == set(meta.loc[meta["is_negotiable"], "job_id"]) and est["salary_is_estimated"].all()
    assert (est["p10_m"] <= est["salary_estimated_m"]).all() and (est["salary_estimated_m"] <= est["p90_m"]).all()
    assert m["n_test"] + m["n_train"] == m["subset"]["n_train_subset"]  # tin thỏa thuận không vào train/test


def test_no_gain_over_baseline_switches_to_plan_b():
    meta, skills = _hand_jobs(n=700, seed=1, fam_only=True)
    _, _, m, _ = train_salary_model(meta, skills, SalaryParams(bootstrap_n=10), compute_shap=False)
    assert m["plan"] == "B" and "band_classifier" in m
    assert 0 <= m["band_classifier"]["macro_f1"] <= 1


def test_overrepresented_group_in_negotiable_gets_warning():
    meta, skills = _hand_jobs(n=1300, seed=2, senior_neg=(0.4, 0.1))
    _, flagged = compare_distributions(meta[meta["is_negotiable"]], meta[~meta["is_negotiable"]], ["seniority"], 2.0)
    assert "Senior" in flagged["seniority"]
    _, _, _, extra = train_salary_model(meta, skills, SalaryParams(bootstrap_n=10), compute_shap=False)
    est = extra["estimates"].merge(meta[["job_id", "seniority"]], on="job_id")
    assert est.loc[est["seniority"] == "Senior", "warning"].str.contains("seniority=Senior").all()
    assert not est.loc[est["seniority"] != "Senior", "warning"].str.contains("seniority=Senior").any()


def test_skill_with_few_jobs_is_not_valued():
    X = pd.DataFrame({"skill::A": [1] * 10 + [0] * 40, "skill::B": [1] * 35 + [0] * 15, "seniority_ord": 1})
    out = skill_values_from_shap(np.zeros((50, 3)), X, pd.Series(["F"] * 50), base_salary_mil=20.0, min_sample=30)
    assert set(out["skill_name"]) == {"B"}
