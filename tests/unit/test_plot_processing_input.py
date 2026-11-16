"""scripts/plot_processing_input.py: số liệu đầu vào Processing lấy thẳng từ bảng 04 và báo cáo; không bịa."""

import numpy as np
import pandas as pd

import plot_processing_input as p


def _df():
    return pd.DataFrame({
        "job_id_global": ["a", "b", "c"], "source_platform": ["x", "x", "y"],
        "salary_min_vnd": [10e6, np.nan, 5e6], "salary_max_vnd": [20e6, np.nan, np.nan],
        "exp_min_years": [1.0, np.nan, 2.0], "seniority": ["Junior", None, "Middle"], "tinh_chinh": ["Hà Nội", None, "Đà Nẵng"],
        "posted_date": ["2026-10-01", None, None], "deadline_date": [None, None, None], "headcount": [1.0, np.nan, np.nan],
        "description_clean": ["abc def", "", "x"], "requirements_clean": ["r", "r", None],
        "skills_std": [np.array(["Python"]), np.array([]), np.array(["Java", "SQL"])],
        "benefits_std": [np.array(["Thưởng"]), np.array([]), np.array([])],
        "raw_employment_type": ["full", None, "full"], "job_family": ["Web", "Other", "Web"],
        "language": ["vi", "en", "vi"], "translation_status": ["not_needed", "failed", "not_needed"],
    })


def test_missing_rates_overall_and_by_source():
    s = p.summarize(_df(), pd.DataFrame({"job_id_global": ["a", "a", "b"], "section": ["mo_ta"] * 3}),
                    pd.DataFrame({"job_id_global": ["a", "c", "c"]}))
    miss = dict(s["missing"])
    assert miss["Lương (đủ min và max)"] == 2 and miss["Kỹ năng"] == 1 and miss["Phúc lợi"] == 2
    assert miss["Mô tả"] == 1 and miss["Nhóm nghề Other"] == 1 and miss["Hạn nộp"] == 3
    assert s["sources"] == ["x", "y"] and s["by_source"]["Lương (đủ min và max)"] == [50.0, 100.0]
    assert s["n_jobs"] == 3 and s["translation"] == {"not_needed": 2, "failed": 1}
    assert s["bullets_per_job"] == {0: 1, 1: 1, 2: 1} and s["skills_per_job"] == {0: 1, 1: 1, 2: 1}
