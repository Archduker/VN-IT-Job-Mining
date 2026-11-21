"""mining/recommend.py: lộ trình học cho người mới (M6, docs/spec/mining/M6_lo_trinh.md)."""

import numpy as np
import pandas as pd
import pytest

from mining.config import RecommendParams
from mining.recommend import (
    coverage_share,
    defer_list,
    family_slug,
    learning_path,
    priority_scores,
    run_recommend,
)

P = RecommendParams()


def _rules(rows):
    """rows: (vế trái, vế phải, confidence, lift)."""
    return pd.DataFrame({"antecedents": [list(a) for a, *_ in rows], "consequents": [list(c) for _, c, *_ in rows],
                         "confidence": [r[2] for r in rows], "lift": [r[3] for r in rows]})


def test_low_demand_skill_is_not_prioritised():
    out = priority_scores({"A": 0.6, "B": 0.4, "C": 0.03}, {}, P)
    assert [r["skill"] for r in out] == ["A", "B"]


def test_premium_is_normalised_by_max_abs_delta():
    out = {r["skill"]: r for r in priority_scores({"A": 0.6, "B": 0.4}, {"A": 2.0, "B": -4.0}, P)}
    assert out["A"]["premium"] == pytest.approx(0.5) and out["A"]["score"] == pytest.approx(0.9)
    assert out["B"]["premium"] == pytest.approx(-1.0) and out["B"]["score"] == pytest.approx(0.0)


def test_unvalued_skill_has_zero_premium_and_soft_list_uses_demand_only():
    out = priority_scores({"A": 0.5}, {}, P)
    assert out[0]["premium"] == 0.0 and out[0]["premium_status"] == "không định giá"
    soft = priority_scores({"english": 0.3}, None, P)
    assert soft[0]["score"] == pytest.approx(0.3) and "premium" not in soft[0]


def test_chain_of_strong_rules_gives_levels_with_consequent_as_base():
    """1.B (20/11): luật B ⇒ A (tin có B gần như luôn có A) nghĩa là A là nền, A học trước."""
    path = learning_path(["A", "B", "C"], _rules([(["B"], ["A"], 0.8, 2.0), (["C"], ["B"], 0.7, 1.5)]), P)
    assert len(path["bundles"]) == 1
    lv = {s["skill"]: s["level"] for s in path["bundles"][0]["steps"]}
    assert lv == {"A": 1, "B": 2, "C": 3}
    b = next(s for s in path["bundles"][0]["steps"] if s["skill"] == "B")
    assert b["evidence"]["rule"] == "B ⇒ A" and b["evidence"]["confidence"] == 0.8


def test_cycle_cuts_lowest_confidence_edge():
    path = learning_path(["A", "B"], _rules([(["A"], ["B"], 0.9, 2.0), (["B"], ["A"], 0.7, 2.0)]), P)
    lv = {s["skill"]: s["level"] for s in path["bundles"][0]["steps"]}
    assert lv == {"B": 1, "A": 2} and path["bundles"][0]["cut_edges"] == ["B ⇒ A"]


def test_multi_item_rules_are_not_used_for_order():
    path = learning_path(["A", "B", "C"], _rules([(["A", "B"], ["C"], 0.95, 3.0)]), P)
    assert path["bundles"] == [] and path["standalone"] == ["A", "B", "C"]


def test_weak_rules_and_skills_outside_priority_are_ignored():
    rules = _rules([(["A"], ["B"], 0.5, 2.0), (["A"], ["Z"], 0.9, 2.0), (["C"], ["D"], 0.9, 1.1)])
    path = learning_path(["A", "B", "C", "D"], rules, P)
    assert path["bundles"] == [] and path["standalone"] == ["A", "B", "C", "D"]


def test_skill_mostly_in_senior_postings_is_deferred():
    sets_new = [{"D"}] * 2 + [set()] * 98  # 2% tin người mới
    sets_sen = [{"D"}] * 30 + [set()] * 70  # 30% tin Senior/Lead
    out = defer_list(sets_new, sets_sen, {"D": 0.02}, P)
    assert out[0]["skill"] == "D" and out[0]["ratio"] == pytest.approx(15.0)
    few = [{"E"}] * 9 + [set()] * 91  # 4.B: chỉ 9 tin Senior/Lead → không vào danh sách
    assert defer_list(sets_new, few, {"E": 0.0}, P) == []


def test_coverage_counts_job_ok_at_70_percent_and_excludes_no_tool():
    top = {f"s{i}" for i in range(8)}
    job_ok = {f"s{i}" for i in range(10)}  # 8/10 = 0,8 ≥ 0,7
    job_bad = {"s0", "x", "y"}  # 1/3
    share, n_eval, n_excl = coverage_share([job_ok, job_bad, set()], top, 0.7)
    assert share == 0.5 and n_eval == 2 and n_excl == 1


def _toy_data():
    """Web: 40 tin người mới, Game: 20 tin người mới (dưới 30), Other: 40."""
    rng = np.random.default_rng(0)
    rows, sets = [], {}
    for i in range(160):
        fam = "Web" if i < 80 else ("Game" if i < 120 else "Other")
        sen = "Junior" if i % 2 == 0 else "Senior"
        jid = f"j{i}"
        rows.append({"job_id": jid, "job_family": fam, "seniority": sen})
        base = {"javascript", "html"} if rng.random() < 0.7 else {"java", "spring_boot"}
        if sen == "Senior" and rng.random() < 0.5:
            base |= {"kubernetes"}
        if rng.random() < 0.3:
            base |= {"git"}
        sets[jid] = base
    meta = pd.DataFrame(rows)
    return meta, sets


def test_run_recommend_writes_families_and_low_data_index():
    meta, sets = _toy_data()
    demand = {"families": {}, "low_data": {}}
    for fam in ("Web", "Game", "Other"):
        ids = meta.loc[(meta["job_family"] == fam) & (meta["seniority"] == "Junior"), "job_id"]
        if len(ids) < 30:
            demand["low_data"][fam] = len(ids)
            continue
        cnt = pd.Series([s for j in ids for s in sets[j]]).value_counts() / len(ids)
        demand["families"][fam] = {"n_newcomer": len(ids), "tool": cnt.round(4).to_dict(), "soft": {"english": 0.4}}
    rules = _rules([(["spring_boot"], ["java"], 0.95, 3.0), (["html"], ["javascript"], 0.9, 1.4)])
    rules["job_family_scope"], rules["level_group"] = "Web", "newcomer"
    files, m = run_recommend(meta, {"tool": sets, "soft": {}}, demand, rules, pd.DataFrame(), P)
    assert set(files) == {"sd5_web.json", "sd5_index.json"}
    idx = {r["job_family"]: r for r in files["sd5_index.json"]["families"]}
    assert idx["Game"]["status"] == "ít dữ liệu" and idx["Other"]["status"] == "không làm lộ trình"
    web = files["sd5_web.json"]
    assert {s["skill"] for s in web["priority_soft"]} == {"english"}
    assert "english" not in {s["skill"] for s in web["priority_tool"]}
    assert len(web["path"]["bundles"]) == 2 and web["path"]["rules_scope"] == "Web|newcomer"
    assert set(web["coverage"]) == {"5", "10", "15"} and "baseline" in web["coverage"]["10"]
    assert web["split_check"]["n_test"] > 0 and len(web["split_check"]["runs"]) == 5
    assert all("demand" in s and s["text"] for s in web["priority_tool"])
    assert m["families"]["Web"]["coverage10"] is not None


def test_family_slug():
    assert family_slug("Data/AI") == "data_ai" and family_slug("DevOps/Cloud") == "devops_cloud"


def test_level_uses_shortest_path_from_base():
    """3.B (20/11): C có luật trực tiếp về nền A nên ở bậc 2, dù có đường dài A → B → C."""
    rules = _rules([(["B"], ["A"], 0.8, 2.0), (["C"], ["B"], 0.7, 2.0), (["C"], ["A"], 0.65, 2.0)])
    path = learning_path(["A", "B", "C"], rules, P)
    lv = {s["skill"]: s["level"] for s in path["bundles"][0]["steps"]}
    assert lv == {"A": 1, "B": 2, "C": 2}
    c = next(s for s in path["bundles"][0]["steps"] if s["skill"] == "C")
    assert c["evidence"]["rule"] == "C ⇒ A"
