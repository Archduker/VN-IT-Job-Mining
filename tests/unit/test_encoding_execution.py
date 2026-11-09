"""Full runner policies; all writes are temporary and all examples are logic fixtures."""

import json

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from scipy import sparse

from preprocessing.common import SOURCES
from preprocessing.encoding.execute import make_golden, run_execution, table_equal
from preprocessing.encoding.execution_features import build_features, cooccurrence
from preprocessing.encoding.execution_io import (
    NUMERIC,
    freeze_stopwords,
    freeze_vocabulary,
    load_snapshot,
    sha,
    validate_frame,
)
from preprocessing.encoding.execution_tfidf import corpus, fit_text, reconstruct_transform
from preprocessing.encoding.skills_taxonomy_230 import TAXONOMY_230


def vocab():
    return dict(version="unit-test-only", items=[dict(canonical=item.canonical) for item in TAXONOMY_230])


def frame():
    values = dict(job_id_global=["a", "b", "c", "d"], source_platform=[SOURCES[0]]*4,
        skills_std=[None, [], [TAXONOMY_230[0].canonical], ["unmatched"]], locations=[None, [], [], []],
        seniority=[None, "not a label", "Junior", "Chưa rõ"], job_family=[None, "unknown", "Khác", "Khác"],
        raw_employment_type=[None, "full time", "unknown", "internship"],
        posted_date=["2026-11-09", "bad", None, "2026-11-01"],
        deadline_date=["2026-11-01", None, None, "2026-11-10"],
        description_clean=[None, "alpha", "beta", "gamma"], requirements_clean=[None]*4,
        it_rule_level=[1, 2, None, 99], is_negotiable=[None, False, True, False],
        is_outlier_salary=[False]*4, seniority_can_kiem=[None]*4, job_family_can_kiem=[False]*4)
    values.update({name: [np.nan, 1., 2., 3.] for name in NUMERIC})
    values["exp_max_years"] = [np.nan, 0., 2., 3.]
    return pd.DataFrame(values)


def test_null_empty_unknown_boolean_category_and_anomaly_policies():
    df = frame()
    encoded, dictionary, unmatched, quality = build_features(df, vocab())
    assert encoded.skills__missing.tolist() == [1, 0, 0, 0]
    assert encoded.skills__empty.tolist() == [0, 1, 0, 0]
    assert encoded.other_skills_count.tolist() == [0, 0, 0, 1]
    assert encoded.is_negotiable.tolist() == [0, 0, 1, 0]
    assert encoded.is_negotiable__missing.tolist() == [1, 0, 0, 0]
    assert encoded.exp_range_invalid.tolist() == [0, 1, 0, 0]
    assert encoded.exp_min_years.iloc[1] == 1 and encoded.exp_max_years.iloc[1] == 0
    assert encoded.deadline_before_posted.tolist() == [1, 0, 0, 0]
    assert np.isnan(encoded.days_to_deadline.iloc[0])
    assert encoded.job_family__unknown.tolist() == [0, 1, 0, 0]
    assert encoded.seniority_ord.tolist() == [-1, -1, 2, -1]
    assert dictionary["employment_source"] == "raw_employment_type"
    assert unmatched.normalized_value.tolist() == ["unmatched"]
    assert "deadline_before_posted" in quality.reason.tolist()


def test_bad_inputs_fail_before_encoding():
    df = frame()
    with pytest.raises(ValueError, match="Missing P4"):
        validate_frame(df.drop(columns="skills_std"))
    df.loc[1, "job_id_global"] = "a"
    with pytest.raises(ValueError, match="unique"):
        validate_frame(df)
    df = frame()
    df["employment_type"] = "contradiction"
    with pytest.raises(ValueError, match="Employment conflict"):
        validate_frame(df)


def test_int64_cooccurrence_over255_and_nonbinary_rejected():
    columns = [f"skill_{i}" for i in range(230)]
    df = pd.DataFrame(np.ones((300, 230), dtype=np.uint8), columns=columns)
    counts = cooccurrence(df, columns)
    assert counts.iloc[0, 1] == 300 and counts.to_numpy().dtype == np.int64
    df.iloc[0, 0] = 2
    with pytest.raises(ValueError, match="binary"):
        cooccurrence(df, columns)


def test_sparse_tfidf_roundtrip_and_no_fallback(tmp_path):
    asset = tmp_path / "stopwords.json"
    freeze_stopwords(asset)
    df = pd.DataFrame(dict(description_clean=["alpha beta"]*5+["gamma delta"]*4+[None], requirements_clean=[None]*10))
    matrix, terms, config = fit_text(df, asset)
    delta = matrix - reconstruct_transform(corpus(df), terms, config)
    assert matrix.dtype == np.float32 and matrix.format == "csr" and matrix[9].nnz == 0
    assert not delta.nnz or abs(delta.data).max() < 2e-6
    with pytest.raises(ValueError):
        fit_text(df.iloc[:1], asset)


def test_golden_nested_null_order_and_collision(tmp_path):
    table = pa.table(dict(job_id_global=["a", "b"], nested=pa.array([None, [dict(x=None), dict(x="v")]])))
    features = pd.DataFrame(dict(job_id_global=["b", "a"], skill_python=np.array([1, 0], dtype=np.uint8)))
    golden = make_golden(table, features, ["skill_python"])
    assert golden["skill_python"].to_pylist() == [0, 1]
    path = tmp_path / "golden.parquet"
    pq.write_table(golden, path, compression="snappy")
    assert table_equal(pq.read_table(path).select(table.column_names), table)
    with pytest.raises(ValueError, match="collision"):
        make_golden(golden, features, ["skill_python"])


def test_loader_null_only_lossless_and_schema_checksum_failures(tmp_path):
    entries = []
    for index, source in enumerate(SOURCES):
        row = frame().iloc[:1].copy()
        row["job_id_global"], row["source_platform"] = str(index), source
        row["skills_std"] = [["Python"]] if index else [None]
        row["locations"] = [[dict(tinh_key="hanoi", tinh_cu=None), dict(tinh_key="hanoi", tinh_cu=None)]] if index == 0 else [None]
        table = pa.Table.from_pandas(row, preserve_index=False)
        path = tmp_path / f"{source}.parquet"
        pq.write_table(table, path)
        entries.append(dict(key=f"step/{source}/all.parquet", sha256=sha(path), rows=1, schema=str(pq.read_table(path).schema)))
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(entries))
    table, df, _ = load_snapshot(manifest)
    assert len(df) == 8 and table["skills_std"].to_pylist()[0] is None
    assert len(table["locations"].to_pylist()[0]) == 2
    entries[0]["schema"] = "incorrect"
    manifest.write_text(json.dumps(entries))
    with pytest.raises(ValueError, match="schema"):
        load_snapshot(manifest)
    entries[0]["sha256"] = "incorrect"
    manifest.write_text(json.dumps(entries))
    with pytest.raises(ValueError, match="checksum"):
        load_snapshot(manifest)


def test_failure_does_not_write_success_or_accept_stale_output(tmp_path):
    output = tmp_path / "output"
    evidence = tmp_path / "evidence"
    output.mkdir()
    with pytest.raises(FileExistsError):
        run_execution(tmp_path / "missing", tmp_path / "vocab", tmp_path / "stop", output, evidence)
    with pytest.raises(FileNotFoundError):
        run_execution(tmp_path / "missing", tmp_path / "vocab", tmp_path / "stop", tmp_path / "new", evidence)
    assert not evidence.exists() and not (output / "artifact_manifest.json").exists()


def test_oracle_database_frozen_mapping_never_accepts_vendor(tmp_path, monkeypatch):
    import preprocessing.encoding.execution_io as io
    from preprocessing.encoding.candidate_lookup import (
        build_candidate_lookup,
        encode_candidate_rows,
    )

    original = tmp_path / "v2.json"
    original.write_text(json.dumps(dict(items=[dict(canonical="Oracle", aliases=["Oracle Database", "oracle"])])))
    decision = tmp_path / "decision.md"
    decision.write_text("unit fixture authorization")
    # Width is covered by lookup tests; this test isolates the semantic correction.
    monkeypatch.setattr(io, "build_candidate_lookup", lambda items, expected_count: None)
    frozen = freeze_vocabulary(original, decision, tmp_path / "frozen.json")
    assert frozen["items"][0]["canonical"] == "Oracle Database"
    result = encode_candidate_rows([["Oracle"], ["Oracle Database"]], build_candidate_lookup(frozen["items"]))
    assert result.matrix.tolist() == [[0], [1]]
    assert json.loads(original.read_text())["items"][0]["canonical"] == "Oracle"


def test_dry_run_and_validation_failure_have_no_dataset_or_success(tmp_path, monkeypatch):
    import preprocessing.encoding.execute as runner

    df = frame()
    table = pa.Table.from_pandas(df, preserve_index=False)
    manifest = tmp_path / "input.json"
    manifest.write_text("[]")
    vocabulary = tmp_path / "vocab.json"
    vocabulary.write_text(json.dumps(dict(**vocab(), status="frozen_authorized_for_run",
                                         input_manifest_sha256=sha(manifest), decision_reference={})))
    stop = tmp_path / "stop.json"
    stop.write_text("{}")
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "load_snapshot", lambda path: (table, df, []))
    monkeypatch.setattr(runner, "fit_text", lambda df, path: (sparse.csr_matrix((4, 1), dtype=np.float32), [], {}))
    monkeypatch.setattr(runner, "inventory", lambda output, roots: [])
    output, evidence = tmp_path / "output", tmp_path / "evidence"
    result = run_execution(manifest, vocabulary, stop, output, evidence, dry_run=True)
    assert result["status"] == "DRY_RUN_NO_WRITES"
    assert not output.exists() and not evidence.exists()
    def fail_validation(*args):
        raise ValueError("injected validation failure")
    monkeypatch.setattr(runner, "validate_bundle", fail_validation)
    with pytest.raises(ValueError, match="injected"):
        run_execution(manifest, vocabulary, stop, output, evidence)
    assert not output.exists() and not (evidence / "artifact_manifest.json").exists()
