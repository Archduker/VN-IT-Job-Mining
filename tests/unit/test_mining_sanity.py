"""mining/sanity.py: S-01..S-06 trả pass/fail/skipped đúng."""

import numpy as np
import pandas as pd

from mining.data_io import prepare_mining_data
from mining.sanity import run_sanity_checks, summarize
from mining.synthetic import make_synthetic_jobs


def _by_id(checks):
    return {c["id"]: c for c in checks}


def test_all_pass_on_synthetic_with_shap_table():
    b = make_synthetic_jobs(n_jobs=1500, seed=42)
    d = prepare_mining_data(b.golden, b.features, b.encoding_dict["skills"]["skills_map"])
    shap_tbl = pd.DataFrame({"skill_name": ["AWS", "Kubernetes"], "job_family": ["ALL", "ALL"],
                             "mean_shap_value": [0.05, 0.1], "marginal_trieu": [1.0, 2.0], "sample_size": [40, 40]})
    checks = _by_id(run_sanity_checks(d.meta, d.skills, shap_tbl))
    assert [checks[f"S-0{i}"]["status"] for i in range(1, 7)] == ["pass"] * 6
    assert summarize(list(checks.values()))["all_passed"]


def test_missing_skills_and_shap_are_skipped_not_failed():
    meta = pd.DataFrame({"salary_avg_mil": [10.0, 20.0], "is_negotiable": [False, False],
                         "salary_suspect": [False, False], "seniority_ord": [1, 2],
                         "location_group": ["ha_noi", "khac"]})
    skills = pd.DataFrame({"Python": [1, 0]}, dtype=np.uint8)
    checks = _by_id(run_sanity_checks(meta, skills, None))
    assert {c["status"] for c in checks.values()} == {"skipped"}
    s = summarize(list(checks.values()))
    assert s["n_skipped"] == 6 and not s["all_passed"]


def test_rule_fails_when_confidence_low():
    skills = pd.DataFrame({"Flutter": [1] * 10, "Dart": [1] * 5 + [0] * 5}, dtype=np.uint8)
    meta = pd.DataFrame({"salary_avg_mil": [np.nan] * 10, "is_negotiable": [True] * 10,
                         "salary_suspect": [False] * 10, "seniority_ord": [2] * 10, "location_group": ["khac"] * 10})
    s02 = _by_id(run_sanity_checks(meta, skills))["S-02"]
    assert s02["status"] == "fail" and s02["values"]["confidence"] == 0.5


def test_seniority_not_monotonic_fails():
    meta = pd.DataFrame({
        "salary_avg_mil": [20.0] * 5 + [10.0] * 5 + [30.0] * 5 + [40.0] * 5,
        "is_negotiable": [False] * 20, "salary_suspect": [False] * 20,
        "seniority_ord": [1] * 5 + [2] * 5 + [3] * 5 + [4] * 5, "location_group": ["ha_noi"] * 20,
    })
    s04 = _by_id(run_sanity_checks(meta, pd.DataFrame({"X": [0] * 20})))["S-04"]
    assert s04["status"] == "fail" and s04["values"]["medians"]["Fresher"] == 20.0
