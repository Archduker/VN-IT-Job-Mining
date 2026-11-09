"""mining/salary_model.py: Subset A, chống rò rỉ, đánh giá và giá trị biên SHAP."""

import numpy as np
import pandas as pd
import pytest

from mining.data_io import prepare_mining_data
from mining.salary_model import (
    ALL_SCOPE,
    LeakageError,
    assert_no_leakage,
    build_salary_features,
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
    return train_salary_model(data.meta, data.skills)


def test_subset_excludes_negotiable_suspect_and_implausible():
    meta = pd.DataFrame({
        "salary_avg_mil": [10, 12, np.nan, 11, 700, 400] + [15] * 25,
        "is_negotiable": [False, True, True, False, False, False] + [False] * 25,
        "salary_suspect": [False, False, False, True, False, False] + [False] * 25,
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
    model, _, m = trained
    assert model is not None
    assert m["holdout"]["r2_log"] > m["baseline_seniority_exp"]["r2_log"]
    assert m["holdout"]["r2_log"] >= 0.6 and m["meets_r2_target"]
    assert len(m["param_search"]) >= 2 and m["best_params"] in [g["params"] for g in m["param_search"]]
    assert m["n_train"] + m["n_test"] == m["subset"]["n_train_subset"]
    assert list(model.feature_names_in_)[:1][0].startswith("skill::")


def test_shap_recovers_planted_premiums(trained):
    _, values, m = trained
    assert list(values.columns[:len(SHAP_MART_COLUMNS)]) == SHAP_MART_COLUMNS
    allv = values[values["job_family"] == ALL_SCOPE].set_index("skill_name")
    assert allv.loc["Kubernetes", "mean_shap_value"] > 0
    assert allv.loc["AWS", "mean_shap_value"] > 0
    # Kubernetes (+20% cài sẵn) phải đáng giá hơn một kỹ năng không có thưởng như HTML
    assert allv.loc["Kubernetes", "marginal_dollar_vnd"] > allv.loc["HTML", "marginal_dollar_vnd"]
    assert m["shap"]["baseline_salary_mil"] > 0
    assert values.loc[values["is_reliable"], "rank"].notna().all()
    assert values.loc[~values["is_reliable"], "rank"].isna().all()


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
    model, values, m = train_salary_model(d.meta, d.skills)
    assert model is None and "skipped" in m and values.empty
