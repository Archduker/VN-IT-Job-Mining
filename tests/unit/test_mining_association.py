"""mining/association.py: FP-Growth phân tầng tìm lại luật cài sẵn và tính đúng chỉ số."""

import numpy as np
import pandas as pd
import pytest

from mining.association import (
    MACRO_SCOPE,
    find_skill,
    hand_check_rules,
    min_support_for,
    mine_rules,
    mine_stratified_rules,
    pair_stats,
    rare_skills,
    support_stability,
    top_skills_by_family,
    write_hand_check,
)
from mining.config import AssociationParams
from mining.data_io import prepare_mining_data
from mining.synthetic import make_synthetic_jobs


@pytest.fixture(scope="module")
def data():
    b = make_synthetic_jobs(n_jobs=1200, seed=7)
    return prepare_mining_data(b.golden, b.features, b.encoding_dict["skills"]["skills_map"])


def _has_rule(rules: pd.DataFrame, ante, cons, scope=None) -> bool:
    r = rules if scope is None else rules[rules["job_family_scope"] == scope]
    return any(list(a) == sorted(ante) and list(c) == sorted(cons) for a, c in zip(r["antecedents"], r["consequents"], strict=False))


def test_metrics_match_hand_computation():
    # 10 giao dịch có kỹ năng: A=5, B=9, A&B=4; thêm 1 dòng rỗng không được tính là giao dịch
    rows = [[1, 1]] * 4 + [[1, 0]] + [[0, 1]] * 5 + [[0, 0]]
    sk = pd.DataFrame(rows, columns=["A", "B"]).astype(np.uint8)
    r = mine_rules(sk, min_support=0.1, min_confidence=0.0, min_lift=0.0)
    ab = r[r["antecedents"].apply(lambda a: list(a) == ["A"])].iloc[0]
    assert ab["support"] == pytest.approx(0.4)
    assert ab["confidence"] == pytest.approx(0.8)
    assert ab["lift"] == pytest.approx(0.8 / 0.9)
    assert ab["cosine"] == pytest.approx(0.4 / np.sqrt(0.5 * 0.9))
    assert ab["n_transactions"] == 10


def test_empty_baskets_are_not_transactions():
    sk = pd.DataFrame({"A": [1, 1, 0, 0], "B": [1, 1, 0, 0]}, dtype=np.uint8)
    r = mine_rules(sk, 0.5, 0.5, 0.0)
    assert (r["support"] == 1.0).all() and (r["n_transactions"] == 2).all()


def test_planted_rules_found_and_thresholds_respected(data):
    rules, m = mine_stratified_rules(data.skills, data.meta["job_family"])
    p = AssociationParams()
    assert (rules["confidence"] >= p.min_confidence).all()
    assert (rules["lift"] > p.min_lift).all()
    assert _has_rule(rules, ["Spring Boot"], ["Java"], MACRO_SCOPE)
    # Flutter hiếm trên toàn thị trường -> phải ra ở tầng vi mô Mobile
    assert _has_rule(rules, ["Flutter"], ["Dart"], "Mobile")
    assert m["n_rules_total"] == len(rules) and m["meets_min_rules_target"]
    assert {s["scope"] for s in m["scopes"]} >= {MACRO_SCOPE, "Backend", "Mobile"}


def test_small_families_are_skipped(data):
    params = AssociationParams(min_group_size=10_000)
    rules, m = mine_stratified_rules(data.skills, data.meta["job_family"], params)
    assert set(rules["job_family_scope"]) <= {MACRO_SCOPE}
    assert all("skipped" in s for s in m["scopes"] if s["scope"] != MACRO_SCOPE)


def test_infinite_conviction_stored_as_null(data):
    rules, _ = mine_stratified_rules(data.skills, data.meta["job_family"])
    assert np.isfinite(rules["conviction"].dropna()).all()
    assert rules.loc[rules["confidence"] >= 0.9999, "conviction"].isna().all()


def test_find_skill_and_pair_stats(data):
    assert find_skill(data.skills, ["springboot"]) == "Spring Boot"
    assert find_skill(data.skills, ["nodejs"]) == "Node.js"
    assert find_skill(data.skills, ["Không có"]) is None
    st = pair_stats(data.skills, "Flutter", ["Dart"])
    # = 1 với tin thường; vài tin bất thường cài sẵn có Flutter ngẫu nhiên mà không có Dart
    assert st["confidence"] > 0.85 and st["lift"] > 1.5


# ---------------------------------------------------------------------------
# M2 (docs/spec/mining/M2_fp_growth.md, prompt mục 5)
# ---------------------------------------------------------------------------
def test_min_support_has_floor_of_ten_postings():
    assert min_support_for(150, 0.02, 10) == pytest.approx(10 / 150)
    assert min_support_for(3000, 0.02, 10) == 0.02


def test_rule_backed_by_four_postings_is_dropped():
    # 150 giỏ: A,B cùng xuất hiện 4 lần (conf 1, lift cao) -> support 0,027 < 10/150
    rows = [[1, 1, 0]] * 4 + [[0, 0, 1]] * 146
    sk = pd.DataFrame(rows, columns=["A", "B", "C"]).astype(np.uint8)
    fam = pd.Series(["Web"] * 150)
    rules, m = mine_stratified_rules(sk, fam, AssociationParams(min_group_size=100))
    assert not _has_rule(rules, ["A"], ["B"])
    web = [s for s in m["scopes"] if s["scope"] == "Web"][0]
    assert web["min_support"] == pytest.approx(10 / 150, abs=1e-4)


def test_family_by_level_group_scopes_and_skips():
    """2.B (20/11): nhóm cấp dùng ngưỡng riêng 40 giỏ; 30 giỏ thì skipped."""
    rows = [[1, 1, 0]] * 30 + [[0, 0, 1]] * 20 + [[1, 1, 1]] * 30  # người mới 50 giỏ: A => B có lift 50/30
    sk = pd.DataFrame(rows, columns=["A", "B", "C"]).astype(np.uint8)
    fam = pd.Series(["Web"] * 80)
    level = pd.Series(["newcomer"] * 50 + ["middle_plus"] * 30)
    rules, m = mine_stratified_rules(sk, fam, AssociationParams(min_group_size=60), level_group=level)
    assert AssociationParams().min_level_group_size == 40
    assert set(rules["level_group"]) == {"all", "newcomer"}
    assert ((rules["job_family_scope"] == "Web") & (rules["level_group"] == "newcomer")).any()
    skipped = [s for s in m["scopes"] if s["scope"] == "Web" and s.get("level_group") == "middle_plus"][0]
    assert "skipped" in skipped and skipped["n_transactions"] == 30
    assert (rules["n_support"] == (rules["support"] * rules["n_transactions"]).round().astype(int)).all()


def test_rare_skill_by_senior_share_and_not_rare_otherwise():
    n = 1000
    sk = pd.DataFrame({"base": [1] * n, "x": [0] * n, "y": [0] * n}, dtype=np.uint8)
    sk.loc[:9, "x"] = 1            # 1% giỏ, 8/10 ở Senior/Lead
    sk.loc[500:509, "y"] = 1       # 1% giỏ, 2/10 ở Senior/Lead, không trong luật nào
    sen = pd.Series(["Junior"] * n)
    sen[:8] = "Senior"
    sen[500:502] = "Lead/Manager"
    out = rare_skills(sk, mine_rules(sk.iloc[:0], 0.5, 0.6, 1.2), sen, AssociationParams())
    names = {r["skill"]: r for r in out["skills"]}
    assert "x" in names and names["x"]["senior_share"] == 0.8 and names["x"]["n"] == 10
    assert "y" not in names


def test_top_skills_three_views_are_separate():
    meta = pd.DataFrame({"job_id": [f"j{i}" for i in range(40)], "job_family": ["Web"] * 40})
    js = pd.DataFrame({"job_id_global": [f"j{i}" for i in range(40)] * 2,
                       "slug": ["python"] * 40 + ["english"] * 40,
                       "kind": ["technical"] * 40 + ["language"] * 40,
                       "type": ["tool"] * 40 + [None] * 40})
    t = top_skills_by_family(meta, js, None, AssociationParams())
    web = t["families"]["Web"]
    assert [r["skill"] for r in web["tool"]] == ["python"] and [r["skill"] for r in web["soft"]] == ["english"]
    assert web["concept"] == [] and t["families"]["ALL"]["tool"][0]["share"] == 1.0


def test_stability_top_ranks_by_confidence_times_support():
    """1.B (20/11): top 20 của M2.5 xếp theo confidence × support, không theo lift."""
    from mining.association import _top_keys

    r = pd.DataFrame({"antecedents": [["a"], ["b"]], "consequents": [["x"], ["y"]],
                      "confidence": [0.9, 0.7], "support": [0.02, 0.30], "lift": [40.0, 1.5]})
    assert _top_keys(r, 1) == ["b=>y"]


def test_support_stability_is_deterministic(data):
    s1 = support_stability(data.skills, data.meta["job_family"], AssociationParams())
    s2 = support_stability(data.skills, data.meta["job_family"], AssociationParams())
    assert s1 == s2 and {"x0.5", "x2"} <= set(s1["factors"])
    assert 0 <= s1["factors"]["x2"]["mean_overlap"] <= 1


def test_hand_check_is_not_overwritten_once_filled(tmp_path, data):
    rules, _ = mine_stratified_rules(data.skills, data.meta["job_family"])
    hc = hand_check_rules(rules, AssociationParams())
    assert len(hc) <= 20 and (hc["n_support"] >= 10).all() and {"dung", "ghi_chu"} <= set(hc.columns)
    assert hc.groupby(["job_family_scope", "level_group"]).size().max() <= 5
    path = tmp_path / "sd2_hand_check.csv"
    assert write_hand_check(hc, path) is True
    filled = pd.read_csv(path)
    filled.loc[0, "dung"] = 1
    filled.to_csv(path, index=False)
    assert write_hand_check(hc, path) is False
    assert pd.read_csv(path).loc[0, "dung"] == 1
