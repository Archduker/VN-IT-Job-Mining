"""scripts/plot_mining_input.py: tổng hợp số liệu đầu vào Mining; số lấy thẳng từ bảng, không bịa."""

import numpy as np
import pandas as pd

import plot_mining_input as p


def test_summarize_counts_and_completeness():
    feats = pd.DataFrame({"job_id_global": ["a", "b", "c"], "skill__python": [1, 1, 0], "skill__sql": [1, 0, 0],
                          "skill__other_skill": [0, 1, 0], "n_skills": [2, 1, 0],
                          "salary_mid": [15.0, np.nan, 30.0], "exp_min_years__missing": [0, 1, 0],
                          "seniority_ord": [0, -1, 2], "tinh__unknown": [0, 1, 0]})
    meta = pd.DataFrame({"job_id_global": ["a", "b", "c"], "job_family": ["Backend", "Backend", "QA/QC"],
                         "source_platform": ["x", "x", "y"]})
    s = p.summarize(feats, meta)
    assert s["n_jobs"] == 3 and s["n_skill_cols"] == 2 and s["zero_skill_jobs"] == 1
    assert s["top_skills"][0] == ["python", 2] and ["other_skill", 1] not in s["top_skills"]
    assert s["families"] == [["Backend", 2], ["QA/QC", 1]] and s["sources"] == [["x", 2], ["y", 1]]
    assert dict(s["completeness"])["Lương"] == 2 and dict(s["completeness"])["Cấp bậc"] == 2
    assert s["salary_mid"] == [15.0, 30.0] and s["n_skills_hist"] == {0: 1, 1: 1, 2: 1}
