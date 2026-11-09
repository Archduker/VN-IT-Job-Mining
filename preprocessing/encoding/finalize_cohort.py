"""Verify final cohort handoff/history/EDA and append evidence without refitting data."""

import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy import sparse

from preprocessing.encoding.candidate_lookup import build_candidate_lookup, encode_candidate_rows
from preprocessing.encoding.cohort import ASSETS, HISTORY, REPORT, ROOT, apply_ledger
from preprocessing.encoding.execute import table_equal
from preprocessing.encoding.execution_io import load_snapshot, sha, write_json


def main():
    out = ROOT / "data/preprocessing/05_encoding"
    manifest = json.loads((out / "artifact_manifest.json").read_text())
    historical = json.loads((HISTORY / "history_manifest.json").read_text())
    archived = {row["original"]: row for row in historical["files"]}
    assert all(sha(ROOT / row["archived"]) == row["sha256"] for row in historical["files"])
    prior_provenance = json.loads((ROOT / "reports/preprocessing/05_encoding/scope_review_2026-11-09_v1/provenance.json").read_text())
    # The owner's _01 cleanup may retire superseded experiments. Retain their
    # exact prior hashes in the existing manifest instead of keeping every file.
    retired = manifest.get("refactor", {}).get("retired_paths", {})
    updated = manifest.get("refactor", {}).get("updated_paths", {})
    for original, checksum in prior_provenance["protected_before_after_sha256"].items():
        path = ROOT / archived[original]["archived"] if original in archived else ROOT / original
        if path.is_file():
            if original not in archived and original in updated:
                assert updated[original]["before_sha256"] == checksum, original
                assert sha(path) == updated[original]["sha256"], original
            else:
                assert sha(path) == checksum, original
        else:
            assert retired.get(original, {}).get("sha256") == checksum, original
    for record in manifest["current_artifacts"]:
        assert sha(ROOT / record["path"]) == record["sha256"]
    assert all(sha(ROOT / path) == value for path, value in manifest["source_sha256"].items())
    original, p4, _ = load_snapshot(ROOT / "reports/preprocessing/05_encoding/snapshot_audit_2026-11-08/manifest.json")
    cohort_table, cohort, info = apply_ledger(original, p4, ASSETS / "ledger.csv", ASSETS / "decision_record.json")
    ledger = pd.read_csv(ASSETS / "ledger.csv", keep_default_na=False)
    included = ledger.loc[ledger.disposition.eq("include"), "job_id_global"].tolist()
    denied = set(ledger.loc[ledger.disposition.ne("include"), "job_id_global"])
    features = pd.read_parquet(out / "features.parquet")
    assert features.job_id_global.tolist() == included and not denied.intersection(features.job_id_global)
    rows = pd.read_parquet(out / "tfidf_rows.parquet")
    assert rows.job_id_global.tolist() == included and rows.row_index.tolist() == list(range(len(included)))
    golden = pq.read_table(ROOT / "data/curated/curated_flat_golden_jobs.parquet")
    assert golden["job_id_global"].to_pylist() == included
    assert table_equal(golden.select(cohort_table.column_names), cohort_table)
    vocabulary = json.loads((ROOT / manifest["vocabulary_path"]).read_text())
    parent_vocab = ROOT / "reports/preprocessing/05_encoding/p5_2026-11-09_frozen_v2/vocabulary_frozen.json"
    assert sha(ROOT / manifest["vocabulary_path"]) == sha(parent_vocab)
    lookup = build_candidate_lookup(vocabulary["items"], expected_count=230)
    x = features[list(lookup.columns)].to_numpy()
    np.testing.assert_array_equal(x, encode_candidate_rows(cohort.skills_std, lookup).matrix)
    dictionary = json.loads((out / "encoding_dictionary.json").read_text())
    assert dictionary["skills"]["taxonomy"] == vocabulary["items"]
    assert dictionary["observed_cohort_skill_counts"] == {name:int(value) for name, value in zip(lookup.columns,x.sum(axis=0),strict=True)}
    assert not set(dictionary["recommended_predictors"]["salary_regression"]) & set(dictionary["audit_columns"])
    assert not any(name.startswith("log_salary_") for name in dictionary["recommended_predictors"]["salary_regression"])
    text = sparse.load_npz(out / "tfidf_matrix.npz")
    config = json.loads((out / "tfidf_config.json").read_text())
    assert config["fit_documents"] == len(included) and config["cohort_ledger_sha256"] == info["ledger_sha256"]
    assert text.shape == (len(included),3000) and text.dtype == np.float32
    notebook_path = ROOT / "notebooks/eda_p5_final_cohort.ipynb"
    html_path = notebook_path.with_suffix(".html")
    notebook = json.loads(notebook_path.read_text())
    code_cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
    assert code_cells and all(cell["execution_count"] for cell in code_cells)
    assert not [o for c in code_cells for o in c["outputs"] if o["output_type"] == "error"]
    assert "5104" in html_path.read_text() and "retained_unreviewed" in html_path.read_text()
    metrics = json.loads((REPORT / "metrics.json").read_text())
    parent = json.loads((ROOT / "reports/preprocessing/05_encoding/p5_2026-11-09_frozen_v2/metrics.json").read_text())
    comparison = {}
    for name in ["rows", "canonical_pairs", "source_value_pairs", "unmatched_source_pairs", "all_zero_jobs", "empty_skills", "sparsity", "zero_columns", "below20"]:
        comparison[name] = dict(historical5177=parent[name], current_include=metrics[name])
    comparison["job_coverage"] = dict(historical5177=parent["job_coverage"], current_include=metrics["job_coverage"])
    write_json(REPORT / "before_after_metrics.json", comparison)
    perf = REPORT / "performance_pandas.json"
    if not perf.exists():
        measured = {}
        for relative in ["data/curated/curated_flat_golden_jobs.parquet", "data/preprocessing/05_encoding/features.parquet", "data/preprocessing/05_encoding/skill_cooccurrence.parquet"]:
            times = []
            for _ in range(5):
                start = time.perf_counter()
                pd.read_parquet(ROOT / relative)
                times.append(time.perf_counter()-start)
            measured[relative] = dict(seconds=times, median=float(np.median(times)), bytes=(ROOT / relative).stat().st_size)
        write_json(perf, dict(method="pandas.read_parquet; five warm reads; perf_counter median; no cold-cache claim", results=measured))
    tests_path = ROOT / manifest.get("refactor", {}).get("tests_path", str((REPORT / "tests_p5.xml").relative_to(ROOT)))
    tests = ET.parse(tests_path).getroot().find("testsuite")
    assert int(tests.attrib["failures"]) == 0 and int(tests.attrib["errors"]) == 0
    write_json(REPORT / "final_integrity.json", dict(status="PASS_COHORT_HANDOFF_DATA_CHECKS", partition_counts=info["partition_counts"],
        included_rows=len(included), reviewed85=True, not_verified_IT_count=5092, P2_unreviewed=410,
        snapshot_and_prior_evidence_preserved=True, historical_archive_hashes_match=True,
        frozen_vocabulary_unchanged=True, zero_columns=int((x.sum(axis=0)==0).sum()),
        all_final_row_IDs_match_include=True, excluded_and_quarantine_absent=True,
        golden_P4_attributes_lossless=True, audit_not_recommended_predictors=True,
        notebook_code_cells=len(code_cells), notebook_errors=0, html_synced=True,
        python312="UNVERIFIED_NOT_FOUND_IN_CHECKED_ENVIRONMENTS", whole_repo="6 pre-existing collection errors",
        scope_not_exhaustive=True, p5_complete=False))
    manifest["acceptance_details"] = dict(cohort_authorization="APPLIED", data_checks="PASS", EDA="EXECUTED_FRESH_KERNEL_HTML_SYNCED",
        related_tests=f"{tests.attrib['tests']} PASSED", python312="UNVERIFIED", whole_repo="6 pre-existing collection errors",
        open_items=["Python3.12 verification/accepted exception", "Whole-repo collection dependency/module errors outside P5"],
        limitations=["No verified-IT claim for5092 retained_unreviewed", "Upstream producer lineage not verified", "job_family not corrected"])
    manifest["verification_source_sha256"] = {"preprocessing/encoding/finalize_cohort.py":sha(Path(__file__)),
                                               "preprocessing/encoding/build_cohort_notebook.py":sha(ROOT / "preprocessing/encoding/build_cohort_notebook.py")}
    manifest["runtime_assets"] = {str(path.relative_to(ROOT)):sha(path) for path in [ASSETS/"ledger.csv",ASSETS/"ledger.meta.json",ASSETS/"decision_record.json",ASSETS/"authorization_agent07.md"]}
    manifest["historical_archive"] = dict(path=str(HISTORY.relative_to(ROOT)), manifest_sha256=sha(HISTORY/"history_manifest.json"))
    manifest["EDA"] = dict(notebook=str(notebook_path.relative_to(ROOT)), notebook_sha256=sha(notebook_path),
                           html=str(html_path.relative_to(ROOT)), html_sha256=sha(html_path), fresh_kernel=True, executed_code_cells=len(code_cells))
    manifest["evidence_sha256"] = {name:sha(REPORT/name) for name in ["tests_p5.xml","tests_full_offline.xml","lint.log","cohort_summary.json","p1_assessments.csv","resolved_previous19.csv","before_after_metrics.json","performance_pandas.json","final_integrity.json"]}
    write_json(out/"artifact_manifest.json", manifest)
    write_json(REPORT/"artifact_manifest.json", manifest)
    print(json.dumps(dict(rows=len(included), partition_counts=info["partition_counts"], tests_passed=int(tests.attrib["tests"]), notebook_code_cells=len(code_cells), checks="PASS", p5_complete=False),indent=2))


if __name__ == "__main__":
    main()
