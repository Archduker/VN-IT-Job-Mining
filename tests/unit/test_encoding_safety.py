import importlib

import numpy as np
import pandas as pd
import pytest

from preprocessing.encoding.run import ORDERED_SKILL_COLUMNS, compute_skill_cooccurrence
from preprocessing.encoding.tfidf_extractor import extract_tfidf_space


def test_alias_and_slug_collisions():
    from preprocessing.encoding.skills_taxonomy_230 import (
        ALIAS_CONFLICTS,
        SKILL_LOOKUP_MAP,
        build_skill_lookup,
    )

    assert "critical thinking" in ALIAS_CONFLICTS
    assert "critical thinking" not in SKILL_LOOKUP_MAP
    lookup, conflicts = build_skill_lookup(
        [("A", "a", "g", ["shared"]), ("B", "b", "g", ["shared"])]
    )
    assert "shared" not in lookup and conflicts["shared"] == ["a", "b"]
    with pytest.raises(ValueError, match="slug"):
        build_skill_lookup([("A", "a", "g", []), ("B", "a", "g", [])])


def test_missing_input_preserves_report(tmp_path, monkeypatch):
    module = importlib.import_module("preprocessing.encoding.run")
    monkeypatch.setattr(module, "IN_FILE", tmp_path / "missing.parquet")
    sentinel = tmp_path / "report.json"
    sentinel.write_text("previous")
    with pytest.raises(ValueError, match="Legacy P5 writer is disabled"):
        module.run()
    assert sentinel.read_text() == "previous"
    from preprocessing.encoding.run_encoding import main

    assert main([]) == 1


def test_subset_blocked(tmp_path, monkeypatch):
    module = importlib.import_module("preprocessing.encoding.run")
    path = tmp_path / "input.parquet"
    path.write_bytes(b"untouched")
    monkeypatch.setattr(module, "IN_FILE", path)
    with pytest.raises(ValueError, match="subset"):
        module.run(["topcv"], dry_run=False)
    assert path.read_bytes() == b"untouched"


def test_cooccurrence_order_binary_and_overflow():
    x = pd.DataFrame(np.ones((300, 230), dtype=np.uint8), columns=ORDERED_SKILL_COLUMNS)
    c = compute_skill_cooccurrence(x)
    assert (c.to_numpy() == 300).all()
    assert list(c.index) == list(c.columns) == ORDERED_SKILL_COLUMNS
    with pytest.raises(ValueError):
        compute_skill_cooccurrence(x.iloc[:, ::-1])
    x.iloc[0, 0] = 2
    with pytest.raises(ValueError, match="binary"):
        compute_skill_cooccurrence(x)


def test_tfidf_configuration_and_alignment():
    df = pd.DataFrame(
        {
            "job_id_global": ["b", "a", "c"],
            "description_clean": ["python docker", "java redis", "python java"],
        }
    )
    result, meta = extract_tfidf_space(df, min_df=1, max_df=1.0)
    assert result.job_id_global.tolist() == ["b", "a", "c"]
    assert meta["configuration"]["min_df"] == 1
    assert all(isinstance(t, pd.SparseDtype) for t in result.drop(columns="job_id_global").dtypes)
    result, meta = extract_tfidf_space(df, min_df=10)
    assert result is None and meta["status"] == "ERROR"
    result, meta = extract_tfidf_space(df.drop(columns="description_clean"))
    assert result is None and meta["status"] == "SKIPPED"


def test_parquet_roundtrip(tmp_path):
    x = pd.DataFrame(np.ones((300, 230), dtype=np.uint8), columns=ORDERED_SKILL_COLUMNS)
    c = compute_skill_cooccurrence(x)
    path = tmp_path / "cooccurrence.parquet"
    c.to_parquet(path)
    pd.testing.assert_frame_equal(c, pd.read_parquet(path))
