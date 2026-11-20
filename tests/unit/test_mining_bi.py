"""mining/bi.py: M1, bảng SD1 (docs/spec/mining/M1_bi.md, prompt docs/prompting/mining/M1_bi.md mục 5)."""

import numpy as np
import pandas as pd
import pytest

from mining.bi import (
    UNKNOWN,
    baseline_salary,
    count_table,
    crosstab_table,
    newcomer_demand,
    q1_4,
    q1_5,
    q1_7,
    run_bi,
    stat_table,
)
from mining.config import BIParams
from mining.data_io import MiningData


def _meta(n_web=40, n_game=10, n_null=2) -> pd.DataFrame:
    n = n_web + n_game + n_null
    fam = ["Web"] * n_web + ["Game"] * n_game + [None] * n_null
    return pd.DataFrame({
        "job_id": [f"j{i}" for i in range(n)],
        "job_family": fam,
        "source_platform": ["topcv"] * n,
        "seniority": ["Junior"] * n,
        "seniority_ord": [1] * n,
        "seniority_inferred": [False] * n,
        "province": ["TP. Hà Nội"] * n,
        "work_mode": ["onsite"] * n,
        "is_negotiable": [False] * n,
        "salary_outlier": [False] * n,
        "salary_target_m": [np.nan] * n,
        "exp_min_years": [1.0] * n,
        "exp_inferred": [False] * n,
        "n_tools": [3] * n,
        "language": ["vi"] * n,
        "benefits": [[] for _ in range(n)],
        "posted_month": ["2026-10"] * n,
    })


def _rows(table, **match):
    return [r for r in table["rows"] if all(r.get(k) == v for k, v in match.items())]


def test_count_table_has_unknown_row_and_totals():
    t = count_table(_meta()["job_family"], "job_family", BIParams())
    assert t["n_total"] == 52 and sum(r["n"] for r in t["rows"]) == 52
    assert _rows(t, job_family=UNKNOWN)[0]["n"] == 2
    assert t["coverage"] == round(50 / 52, 4)
    assert [r["job_family"] for r in t["rows"]][:2] == ["Web", "Game"]  # n giảm dần


def test_crosstab_small_row_has_no_share():
    m = _meta()
    m.loc[m["job_family"] == "Game", "seniority"] = ["Senior"] * 3 + ["Junior"] * 7
    t = crosstab_table(m["job_family"], m["seniority"], "job_family", "seniority", BIParams())
    game_senior = _rows(t, job_family="Game", seniority="Senior")[0]
    assert game_senior["n"] == 3 and game_senior["share"] is None and game_senior["note"] == "ít dữ liệu"
    web = _rows(t, job_family="Web", seniority="Junior")[0]
    assert web["share"] == 1.0
    assert sum(r["n"] for r in t["rows"]) == 52


def test_salary_stats_drop_outliers():
    vals = pd.Series([10.0] * 34 + [500.0])
    ok = pd.Series([True] * 34 + [False])
    t = stat_table(vals[ok], {"g": pd.Series(["Web"] * 34)}, BIParams())
    assert t["rows"][0]["n"] == 34 and t["rows"][0]["median"] == 10.0


def test_q1_4_salary_excludes_outlier_and_marks_mnar():
    m = _meta(n_web=75, n_game=0, n_null=0)
    m["seniority"] = ["Junior"] * 35 + ["Senior"] * 40
    m["seniority_ord"] = [1] * 35 + [3] * 40
    m["salary_target_m"] = [15.0] * 34 + [900.0] + [40.0] * 10 + [np.nan] * 30
    m["salary_outlier"] = [False] * 34 + [True] + [False] * 40
    m["is_negotiable"] = [False] * 45 + [True] * 30
    out = q1_4(m, BIParams())
    cell = _rows(out["tables"]["salary_by_family_seniority"], job_family="Web", seniority="Junior")[0]
    assert cell["n"] == 34 and cell["median"] == 15.0
    assert any("Senior" in s and "MNAR" in s for s in out["notes"])
    assert not any("Junior" in s and "MNAR" in s for s in out["notes"])


def test_q1_5_exp_only_on_not_inferred_and_views_separate():
    m = _meta(n_web=40, n_game=0, n_null=0)
    m["seniority"] = ["Intern/Fresher"] * 20 + ["Senior"] * 20
    m["exp_min_years"] = [0.0] * 19 + [9.0] + [5.0] * 20
    m["exp_inferred"] = [False] * 19 + [True] + [False] * 20
    js = pd.DataFrame({
        "job_id_global": ["j0", "j0", "j1"],
        "slug": ["python", "english", "python"],
        "kind": ["technical", "language", "technical"],
        "type": ["tool", None, "tool"],
    })
    out = q1_5(m, js, BIParams(min_cell=5))
    stats = {r["group"]: r for r in out["tables"]["compare"]["rows"]}
    assert stats["newcomer"]["exp_median"] == 0.0 and stats["newcomer"]["n_exp"] == 19
    tools = [r["skill"] for r in out["tables"]["top_tools"]["rows"]]
    soft = [r["skill"] for r in out["tables"]["top_soft"]["rows"]]
    assert "english" not in tools and "python" not in soft and "python" in tools and "english" in soft


def test_q1_7_compare_months_only_on_dated_sources():
    m = _meta(n_web=130, n_game=0, n_null=0)
    m["source_platform"] = ["topcv"] * 50 + ["itviec"] * 80
    m["posted_month"] = ["2026-10"] * 50 + ["2026-09"] * 40 + ["2026-10"] * 40
    out = q1_7(m, BIParams())
    cmp = out["tables"]["compare_family"]
    assert cmp["scope_n"] == 80 and sum(r["n"] for r in cmp["rows"]) == 80


def test_baseline_falls_back_to_seniority_then_overall():
    m = _meta(n_web=40, n_game=0, n_null=0)
    m["job_family"] = ["Web"] * 35 + ["Data/AI"] * 5
    m["seniority"] = ["Senior"] * 40
    m["salary_target_m"] = [30.0] * 35 + [50.0] * 5
    b = baseline_salary(m, BIParams())
    assert b["cells"]["Web"]["Senior"] == {"median": 30.0, "n": 35, "fallback": None}
    d = b["cells"]["Data/AI"]["Senior"]
    assert d["fallback"] == "seniority" and d["median"] == b["by_seniority"]["Senior"]["median"]


def test_demand_only_for_families_with_enough_newcomers():
    m = _meta(n_web=40, n_game=20, n_null=0)
    js = pd.DataFrame({"job_id_global": [f"j{i}" for i in range(60)], "slug": ["python"] * 60,
                       "kind": ["technical"] * 60, "type": ["tool"] * 60})
    d = newcomer_demand(m, js, BIParams())
    assert set(d["families"]) == {"Web"} and d["families"]["Web"]["tool"]["python"] == 1.0
    assert d["low_data"]["Game"] == 20


def test_run_bi_totals_ok_and_deterministic():
    m = _meta()
    m["seniority"] = ["Junior"] * 30 + ["Middle"] * 22
    data = MiningData(meta=m, skills=pd.DataFrame({"python": [1] * 52}, dtype=np.uint8))
    out1, met1 = run_bi(data, BIParams())
    out2, _ = run_bi(data, BIParams())
    assert met1["totals_ok"] is True
    assert set(out1) >= {"sd1_1_1.json", "sd1_1_7.json", "sd1_baseline_salary.json", "sd1_demand.json"}
    assert out1 == out2


@pytest.mark.parametrize("word", ["tăng", "giảm", "xu hướng"])
def test_no_trend_words_in_output(word):
    data = MiningData(meta=_meta(), skills=pd.DataFrame({"python": [1] * 52}, dtype=np.uint8))
    out, _ = run_bi(data, BIParams())
    assert word not in str(out).lower()
