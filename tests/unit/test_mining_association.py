"""mining/association.py: FP-Growth phân tầng tìm lại luật cài sẵn và tính đúng chỉ số."""

import numpy as np
import pandas as pd
import pytest

from mining.association import (
    MACRO_SCOPE,
    find_skill,
    mine_rules,
    mine_stratified_rules,
    pair_stats,
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
    assert st["confidence"] > 0.9 and st["lift"] > 1.5
