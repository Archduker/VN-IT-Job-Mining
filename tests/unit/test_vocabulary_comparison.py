import pandas as pd
import pytest

from preprocessing.encoding.compare_vocabulary import compare, preserve_decisions


def test_job_dedup_denominators_and_ties():
    rows = [set(f"s{i:03d}" for i in range(500)), set(), {"s000"}]
    table, sources, thresholds = compare(rows, ["a", "a", "b"], "test", {})
    k230 = next(r for r in table if r["K"] == 230)
    assert k230["selected"] == 230
    assert k230["jobs_hit"] == 2 and k230["jobs_denominator"] == 3
    assert k230["pairs_kept"] == 231 and k230["pairs_denominator"] == 501
    assert k230["boundary_ties"] == 499
    assert k230["UNCLASSIFIED"] == 230
    assert next(r for r in sources if r["K"] == 230 and r["source"] == "a")["jobs_denominator"] == 2
    assert all(r["selected"] == 0 for r in thresholds)


def test_preserve_decisions(tmp_path):
    pd.DataFrame([dict(value="A", decision="accept")]).to_csv(
        tmp_path / "candidate_review_priority.csv", index=False
    )
    preserve_decisions(tmp_path, ["A", "B"])
    p = tmp_path / "candidate_decisions.csv"
    before = p.read_bytes()
    preserve_decisions(tmp_path, ["C"])
    assert p.read_bytes() == before
    assert pd.read_csv(p).iloc[0].decision == "accept"


def test_contradictory_decisions_fail(tmp_path):
    for name, decision in [
        ("candidate_review_full.csv", "accept"),
        ("candidate_review_priority.csv", "reject"),
    ]:
        pd.DataFrame([dict(value="A", decision=decision)]).to_csv(tmp_path / name, index=False)
    with pytest.raises(ValueError, match="Conflicting"):
        preserve_decisions(tmp_path, ["A"])
    assert not (tmp_path / "candidate_decisions.csv").exists()
