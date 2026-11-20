"""mining/sanity.py: S-01..S-06 (M0.7, M0.8, M0.9)."""

import numpy as np
import pandas as pd

from mining.data_io import prepare_mining_data
from mining.sanity import run_sanity_checks, summarize
from mining.synthetic import make_synthetic_jobs


def _by_id(checks):
    return {c["id"]: c for c in checks}


def _meta(sal, sen, neg=None, outlier=None, loc=None):
    n = len(sal)
    return pd.DataFrame({
        "salary_avg_mil": sal, "seniority_ord": sen,
        "is_negotiable": neg if neg is not None else [False] * n,
        "salary_outlier": outlier if outlier is not None else [False] * n,
        "location_group": loc if loc is not None else ["ha_noi"] * n,
    })


def test_all_gates_pass_on_synthetic_with_shap_table():
    b = make_synthetic_jobs(n_jobs=1500, seed=42)
    d = prepare_mining_data(b.golden, b.features, b.encoding_dict["skills"]["skills_map"])
    shap_tbl = pd.DataFrame({"skill_name": ["AWS", "Kubernetes"], "job_family": ["ALL", "ALL"],
                             "mean_shap_value": [0.05, 0.1], "marginal_trieu": [1.0, 2.0], "sample_size": [40, 40]})
    checks = _by_id(run_sanity_checks(d.meta, d.skills, shap_tbl))
    assert checks["S-02"]["status"] == "info"
    assert [checks[f"S-0{i}"]["status"] for i in (1, 3, 4, 5, 6)] == ["pass"] * 5
    assert summarize(list(checks.values()))["all_passed"]


def test_missing_skills_and_shap_are_skipped_not_failed():
    meta = _meta([10.0, 20.0], [1, 2], loc=["ha_noi", "khac"])
    skills = pd.DataFrame({"Python": [1, 0]}, dtype=np.uint8)
    checks = _by_id(run_sanity_checks(meta, skills, None))
    assert {c["status"] for c in checks.values()} == {"skipped"}
    s = summarize(list(checks.values()))
    assert s["n_skipped"] == 6 and not s["all_passed"]


def test_s02_is_info_and_does_not_gate():
    skills = pd.DataFrame({"Flutter": [1] * 10, "Dart": [1] * 4 + [0] * 6}, dtype=np.uint8)
    checks = run_sanity_checks(_meta([np.nan] * 10, [2] * 10, neg=[True] * 10), skills)
    s02 = _by_id(checks)["S-02"]
    assert s02["status"] == "info" and s02["values"]["confidence"] == 0.4
    s = summarize(checks)
    assert s["n_info"] == 1 and s["n_fail"] == 0


def test_s03_threshold_is_060():
    skills = pd.DataFrame({"React": [1] * 10, "JavaScript": [1] * 6 + [0] * 4}, dtype=np.uint8)
    s03 = _by_id(run_sanity_checks(_meta([np.nan] * 10, [2] * 10), skills))["S-03"]
    assert s03["status"] == "pass" and s03["values"]["confidence"] == 0.6
    skills["JavaScript"] = [1] * 5 + [0] * 5
    assert _by_id(run_sanity_checks(_meta([np.nan] * 10, [2] * 10), skills))["S-03"]["status"] == "fail"


def test_s04_uses_0_based_scale_and_reports_lead_separately():
    sal = [10.0] * 5 + [15.0] * 5 + [22.0] * 5 + [37.0] * 5 + [30.0] * 5
    sen = [0] * 5 + [1] * 5 + [2] * 5 + [3] * 5 + [4] * 5
    neg = [False] * 25
    s04 = _by_id(run_sanity_checks(_meta(sal, sen, neg), pd.DataFrame({"X": [0] * 25})))["S-04"]
    assert s04["status"] == "pass"
    assert s04["values"]["medians"] == {"Intern/Fresher": 10.0, "Junior": 15.0, "Middle": 22.0, "Senior": 37.0}
    assert s04["values"]["lead"]["median"] == 30.0 and s04["values"]["lead"]["n"] == 5


def test_s04_not_monotonic_fails():
    sal = [10.0] * 5 + [22.0] * 5 + [15.0] * 5 + [37.0] * 5
    sen = [0] * 5 + [1] * 5 + [2] * 5 + [3] * 5
    s04 = _by_id(run_sanity_checks(_meta(sal, sen), pd.DataFrame({"X": [0] * 20})))["S-04"]
    assert s04["status"] == "fail"


def test_s04_excludes_outliers_and_negotiable():
    sal = [10.0] * 5 + [15.0] * 5 + [22.0] * 5 + [37.0] * 5 + [500.0, 1.0]
    sen = [0] * 5 + [1] * 5 + [2] * 5 + [3] * 5 + [0, 3]
    outlier = [False] * 20 + [True, False]
    neg = [False] * 21 + [True]
    s04 = _by_id(run_sanity_checks(_meta(sal, sen, neg, outlier), pd.DataFrame({"X": [0] * 22})))["S-04"]
    assert s04["status"] == "pass" and s04["values"]["counts"]["Intern/Fresher"] == 5
