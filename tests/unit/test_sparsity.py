from processing.selection.sparsity import OTHER, reduce_sparsity, remap


def row(j, s, lvl="required", w=1.0, n=1):
    return {"job_id_global": j, "slug": s, "level": lvl, "weight": w, "n_mentions": n}


ROWS = [row(0, "py"), row(1, "py"), row(2, "py"), row(0, "rare1"), row(1, "rare2", "preferred", 0.5)]
G = {"py": "lang", "rare1": "tools", "rare2": "tools"}


def test_merge_and_fold_to_family():
    after, rep = reduce_sparsity(ROWS, 4, G, 3, min_df=2)
    assert {r["slug"] for r in after} == {"py", "family_tools"}
    assert rep["before"]["jobs_with_zero_skills"] == 1 and rep["n_skills_folded"] == 2
    assert rep["after"]["n_cols_used"] == 2 and rep["after"]["nnz"] == 5
    assert rep["folded_into"]["family_tools"] == ["rare1", "rare2"]


def test_fold_to_other_and_dedup_per_job():
    rows = [row(0, "a"), row(0, "b", "preferred", 0.5, 2)]
    after, _ = reduce_sparsity(rows, 1, {"a": "g", "b": "g"}, min_df=2, mode="other")
    assert len(after) == 1 and after[0]["slug"] == OTHER and after[0]["n_mentions"] == 3 and after[0]["level"] == "required"


def test_default_does_nothing_and_alias_merge():
    after, rep = reduce_sparsity(ROWS, 4, G)
    assert after == ROWS and rep["n_skills_folded"] == 0
    assert {r["slug"] for r in remap(ROWS, {"rare1": "py"})} >= {"py"}
