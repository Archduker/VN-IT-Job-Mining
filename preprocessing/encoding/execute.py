"""One offline full-bundle P5 implementation, with an authorized cohort ledger.

Technical validation and acceptance remain distinct; no verified-IT claim is made
for retained_unreviewed rows. No R2 exporter or upstream producer is invoked.
"""

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import tempfile
import time
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import scipy
import sklearn
from scipy import sparse

from preprocessing.encoding.candidate_lookup import build_candidate_lookup, encode_candidate_rows
from preprocessing.encoding.cohort import apply_ledger
from preprocessing.encoding.cohort import relative as repo_relative
from preprocessing.encoding.execution_features import build_features, cooccurrence
from preprocessing.encoding.execution_io import (
    json_bytes,
    load_snapshot,
    ordered_ids_hash,
    sha,
    write_json,
)
from preprocessing.encoding.execution_tfidf import corpus, fit_text, reconstruct_transform

ROOT = Path(__file__).resolve().parents[2]
P5 = "preprocessing/05_encoding"
GOLDEN = "curated/curated_flat_golden_jobs.parquet"
CORE = [f"{P5}/features.parquet", f"{P5}/skill_cooccurrence.parquet", f"{P5}/encoding_dictionary.json", GOLDEN]


def table_equal(left, right):
    return left.schema.equals(right.schema, check_metadata=False) and left.combine_chunks().equals(right.combine_chunks(), check_metadata=False)


def make_golden(table, features, skills):
    if set(table.column_names) & set(skills):
        raise ValueError("Golden column collision")
    ids = table["job_id_global"].to_pylist()
    if not features.job_id_global.is_unique or set(ids) != set(features.job_id_global):
        raise ValueError("Golden requires one-to-one identical ID sets")
    aligned = features.set_index("job_id_global").loc[ids]
    result = table
    for column in skills:
        result = result.append_column(column, pa.array(aligned[column], type=pa.uint8()))
    return result


def inventory(output_root, search_roots):
    records = []
    candidates = set()
    for root in search_roots:
        if root.exists():
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                if path.suffix == ".parquet":
                    schema = pq.read_schema(path)
                    if any(name.startswith("skill_") for name in schema.names) or "tfidf" in path.name:
                        candidates.add(path)
                elif path.name in {"encoding_dictionary.json", "artifact_manifest.json", "tfidf_matrix.npz", "skill_matrix_review.npz"}:
                    candidates.add(path)
    for relative in CORE:
        path = output_root / relative
        records.append(dict(artifact=Path(relative).name, path=str(path), exists=path.exists(),
                            input_version="unknown until content validation" if path.exists() else None,
                            vocabulary_config="unknown until content validation" if path.exists() else None,
                            validation="pending" if path.exists() else "missing", action="inspect" if path.exists() else "missing"))
    for path in sorted(candidates):
        if str(path) not in {row["path"] for row in records}:
            records.append(dict(artifact=path.name, path=str(path), exists=True, input_version="inspect content",
                                vocabulary_config="inspect content", validation="not assumed valid", action="inspect"))
    return records


def validate_bundle(folder, table, df, vocabulary, expected_features, expected_dictionary, tfidf_expected):
    directory = folder / P5
    features = pd.read_parquet(directory / "features.parquet")
    pd.testing.assert_frame_equal(features, expected_features, check_exact=True)
    dictionary = json.loads((directory / "encoding_dictionary.json").read_text())
    if dictionary != expected_dictionary:
        raise ValueError("Dictionary differs from executed configuration")
    _, _, expected_unmatched, expected_quality = build_features(df, vocabulary)
    pd.testing.assert_frame_equal(pd.read_parquet(directory / "skill_unmatched.parquet"), expected_unmatched, check_exact=True)
    pd.testing.assert_frame_equal(pd.read_parquet(directory / "data_quality.parquet"), expected_quality, check_exact=True)
    columns = dictionary["skill_columns"]
    lookup = build_candidate_lookup(vocabulary["items"], expected_count=230)
    x = features[columns].to_numpy()
    np.testing.assert_array_equal(x, encode_candidate_rows(df.skills_std, lookup).matrix)
    if x.dtype != np.uint8 or not np.isin(x, [0, 1]).all():
        raise ValueError("Nonbinary/incorrect dtype X")
    counts = pd.read_parquet(directory / "skill_cooccurrence.parquet")
    if counts.index.tolist() != columns or counts.columns.tolist() != columns or counts.shape != (230, 230):
        raise ValueError("C label/order/shape mismatch")
    c = counts.to_numpy()
    if c.dtype != np.int64 or not np.array_equal(c, c.T) or (c < 0).any():
        raise ValueError("C symmetry/dtype/bounds failed")
    jobsets = [set() for _ in columns]
    for i, values in enumerate(df.skills_std):
        if values is not None:
            for value in values:
                owner = lookup.owners.get(value.casefold())
                if owner is not None:
                    jobsets[owner].add(i)
    for i in range(230):
        for j in range(i, 230):
            if c[i, j] != len(jobsets[i] & jobsets[j]):
                raise ValueError("Independent co-occurrence job intersection mismatch")
    np.testing.assert_array_equal(np.diag(c), x.sum(axis=0))
    if (c > np.minimum(np.diag(c)[:, None], np.diag(c)[None, :])).any():
        raise ValueError("C exceeds marginal frequencies")
    golden = pq.read_table(folder / GOLDEN)
    if not table_equal(golden.select(table.column_names), table):
        raise ValueError("Golden did not preserve P4 schema/values/null/nested")
    if golden.column_names != [*table.column_names, *columns]:
        raise ValueError("Golden columns differ")
    np.testing.assert_array_equal(golden.select(columns).to_pandas().to_numpy(), x)
    rows = pd.read_parquet(directory / "tfidf_rows.parquet")
    if rows.job_id_global.tolist() != df.job_id_global.tolist() or rows.row_index.tolist() != list(range(len(df))):
        raise ValueError("TF-IDF row alignment failed")
    text = sparse.load_npz(directory / "tfidf_matrix.npz").tocsr()
    if text.shape[0] != len(df) or text.dtype != np.float32 or not np.isfinite(text.data).all() or (text.data < 0).any():
        raise ValueError("Invalid sparse TF-IDF")
    delta = text - tfidf_expected
    if delta.nnz and abs(delta.data).max() > 2e-6:
        raise ValueError("TF-IDF serialization mismatch")
    terms = json.loads((directory / "tfidf_vocabulary.json").read_text())
    config = json.loads((directory / "tfidf_config.json").read_text())
    if [term["index"] for term in terms] != list(range(text.shape[1])) or len({term["term"] for term in terms}) != len(terms):
        raise ValueError("TF-IDF term-index mapping failed")
    rebuilt = reconstruct_transform(corpus(df), terms, config)
    delta = rebuilt - text
    if delta.nnz and abs(delta.data).max() > 2e-6:
        raise ValueError("TF-IDF transform reconstruction mismatch")
    norms = np.sqrt(np.asarray(text.multiply(text).sum(axis=1)).ravel())
    if not np.all(np.isclose(norms, 0, atol=2e-6) | np.isclose(norms, 1, atol=2e-6)):
        raise ValueError("TF-IDF rows not normalized")
    for path in [folder / GOLDEN, *directory.glob("*.parquet")]:
        metadata = pq.ParquetFile(path).metadata
        if any(metadata.row_group(i).column(j).compression != "SNAPPY" for i in range(metadata.num_row_groups) for j in range(metadata.num_columns)):
            raise ValueError("Parquet not Snappy")
    return dict(status="PASS_TECHNICAL_REVIEW", rows=len(df), features_shape=list(features.shape),
                skill_shape=list(x.shape), cooccurrence_shape=list(c.shape), tfidf_shape=list(text.shape),
                golden_shape=[golden.num_rows, golden.num_columns], tfidf_zero_rows=int((norms == 0).sum()),
                checks=["input IDs/order", "numeric feature schema/values", "every X bit from strict lookup", "independent C intersections/diagonal/bounds/int64/labels", "Golden Arrow values/schema/null/nested", "TF-IDF config/transform/CSR/row IDs/norms", "Snappy compression"],
                acceptance="TECHNICAL_CHECKS_PASS_ACCEPTANCE_RECORDED_SEPARATELY", p5_complete=False)


def run_execution(manifest_path, vocabulary_path, stopwords, output_root, evidence_root, *, dry_run=False, publish=False,
                  cohort_ledger=None, decision_record=None, history_root=None):
    start = time.perf_counter()
    output_root, evidence_root = Path(output_root), Path(evidence_root)
    if not publish and output_root.exists():
        raise FileExistsError("Explicit candidate output root already exists")
    if (evidence_root / "artifact_manifest.json").exists():
        raise FileExistsError("Evidence run already completed; refuse overwrite")
    if publish and (cohort_ledger is None or decision_record is None or history_root is None):
        raise ValueError("Publishing requires explicit authorized cohort ledger, decision record and historical archive")
    input_before = sha(manifest_path)
    table, df, entries = load_snapshot(manifest_path)
    ninput_p4 = len(df)
    cohort_info = None
    if cohort_ledger is not None:
        if decision_record is None:
            raise ValueError("Cohort ledger requires a decision record")
        table, df, cohort_info = apply_ledger(table, df, cohort_ledger, decision_record)
        if cohort_info["snapshot_manifest_sha256"] != input_before:
            raise ValueError("Cohort ledger/input manifest mismatch")
    vocabulary = json.loads(Path(vocabulary_path).read_text())
    if vocabulary["status"] != "frozen_authorized_for_run":
        raise ValueError("Require frozen authorized vocabulary")
    if vocabulary["input_manifest_sha256"] != input_before:
        raise ValueError("Vocabulary/input snapshot mismatch")
    if decision_record is not None and json.loads(Path(decision_record).read_text())["vocabulary_sha256"] != sha(vocabulary_path):
        raise ValueError("Cohort authorization requires the original frozen vocabulary/order")
    frame, dictionary, unmatched, quality = build_features(df, vocabulary)
    skills = dictionary["skill_columns"]
    matrix, terms, text_config = fit_text(df, Path(stopwords))
    text_config.update(stopword_sha256=sha(stopwords), input_manifest_sha256=input_before,
                       corpus_sha256=hashlib.sha256(json_bytes(corpus(df))).hexdigest())
    if cohort_info:
        text_config.update(cohort_ledger_sha256=cohort_info["ledger_sha256"], fit_documents=len(df))
    dictionary.update(input_manifest_sha256=input_before, vocabulary_sha256=sha(vocabulary_path),
                      ordered_id_sha256=ordered_ids_hash(df.job_id_global), text_view_config=text_config,
                      decision_reference=vocabulary["decision_reference"])
    if cohort_info:
        dictionary.update(cohort=cohort_info, decision_reference=repo_relative(decision_record),
                          reference_counts="vocabulary.items.jobs refer to preserved5177; cohort counts below are independent")
    dictionary["observed_cohort_skill_counts"] = {name: int(value) for name, value in zip(skills, frame[skills].sum(), strict=True)}
    audit = set(dictionary["quality_columns"]) | {"it_rule_level__2", "seniority_can_kiem", "job_family_can_kiem", "is_outlier_salary", "other_skills_count"}
    salary_derived = {name for name in frame if name.startswith("log_salary_")} | {"is_negotiable", "is_negotiable__missing"}
    dictionary["audit_columns"] = sorted(audit)
    dictionary["recommended_predictors"] = dict(skill_mining=skills,
        salary_regression=[name for name in frame if name != "job_id_global" and name not in audit | salary_derived],
        note="Recommendations only; downstream selects target/cohort and fits train-only preprocessing. Ledger review status is never a feature.")
    c = cooccurrence(frame, skills)
    golden = make_golden(table, frame, skills)
    prior = inventory(output_root, [ROOT / "data", ROOT / "reports/preprocessing"])
    if dry_run:
        return dict(status="DRY_RUN_NO_WRITES", rows=len(df), features_shape=list(frame.shape), tfidf_shape=list(matrix.shape))
    evidence_root.mkdir(parents=True, exist_ok=True)
    write_json(evidence_root / "inventory_before.json", prior)
    # Preserve the existing review matrix as a reusable component only after comparison.
    review = ROOT / "reports/preprocessing/05_encoding/approval_package_v2/skill_matrix_review.npz"
    review_reuse = False
    if review.exists():
        previous = sparse.load_npz(review)
        review_reuse = previous.shape == (len(df), 230) and np.array_equal(previous.toarray(), frame[skills].to_numpy())
        if review_reuse:
            frame.loc[:, skills] = previous.toarray()
    with tempfile.TemporaryDirectory(prefix="p5-validated-stage-") as tmp:
        stage = Path(tmp)
        directory = stage / P5
        directory.mkdir(parents=True)
        (stage / "curated").mkdir()
        frame.to_parquet(directory / "features.parquet", compression="snappy", index=False)
        c.to_parquet(directory / "skill_cooccurrence.parquet", compression="snappy", index=True)
        write_json(directory / "encoding_dictionary.json", dictionary)
        pq.write_table(golden, stage / GOLDEN, compression="snappy")
        sparse.save_npz(directory / "tfidf_matrix.npz", matrix)
        pd.DataFrame(dict(row_index=np.arange(len(df), dtype=np.int64), job_id_global=df.job_id_global)).to_parquet(directory / "tfidf_rows.parquet", compression="snappy", index=False)
        write_json(directory / "tfidf_vocabulary.json", terms)
        write_json(directory / "tfidf_config.json", text_config)
        unmatched.to_parquet(directory / "skill_unmatched.parquet", compression="snappy", index=False)
        quality.to_parquet(directory / "data_quality.parquet", compression="snappy", index=False)
        checked = validate_bundle(stage, table, df, vocabulary, frame, dictionary, matrix)
        # Logical reproducibility: recompute transformations, no second persisted candidate.
        again, again_dictionary, again_unmatched, again_quality = build_features(df, vocabulary)
        pd.testing.assert_frame_equal(frame, again, check_exact=True)
        pd.testing.assert_frame_equal(unmatched, again_unmatched, check_exact=True)
        pd.testing.assert_frame_equal(quality, again_quality, check_exact=True)
        assert all(dictionary[key] == value for key, value in again_dictionary.items())
        again_text, again_terms, _ = fit_text(df, Path(stopwords))
        diff = again_text - matrix
        if again_terms != terms or (diff.nnz and abs(diff.data).max() > 2e-6):
            raise ValueError("Logical TF-IDF reproducibility failed")
        checked["logical_reproducibility"] = "PASS: E1-E8/sidecars/config exact; CSR float32 tolerance2e-6"
        checked.update(ninput_p4=ninput_p4, cohort=cohort_info,
                       conservation="N_P4 = N_include + N_exclude + N_quarantine; output rows = N_include" if cohort_info else "historical unfiltered staging only")
        results = []
        history_by_path = {}
        if history_root is not None:
            historical = json.loads((Path(history_root) / "history_manifest.json").read_text())
            history_by_path = {row["original"]: row for row in historical["files"]}
            if not all(sha(ROOT / row["archived"]) == row["sha256"] for row in historical["files"]):
                raise ValueError("Historical bundle checksum failed before replacement")
        old_manifest = output_root / P5 / "artifact_manifest.json"
        if old_manifest.exists():
            old_key = repo_relative(old_manifest)
            if old_key not in history_by_path or sha(old_manifest) != history_by_path[old_key]["sha256"]:
                raise ValueError("Archive the existing manifest before replacing a cohort bundle")
            # Readers cannot mistake a partially delivered cohort for the old successful run.
            old_manifest.unlink()
        # Check content for canonical and discovered equivalents before any replacement.
        for source in sorted(stage.rglob("*")):
            if not source.is_file():
                continue
            relative = source.relative_to(stage)
            dest = output_root / relative
            same = False
            if dest.exists():
                try:
                    if source.suffix == ".parquet":
                        same = table_equal(pq.read_table(source), pq.read_table(dest))
                    elif source.suffix == ".npz":
                        old = sparse.load_npz(dest)
                        same = old.shape == matrix.shape and (old != matrix).nnz == 0
                    else:
                        same = json.loads(dest.read_text()) == json.loads(source.read_text())
                except (ValueError, OSError, pa.ArrowException):
                    same = False
            # Equivalent existing files elsewhere are moved only if canonical is missing;
            # historic evidence/review files are never consumed or deleted.
            reused_elsewhere = None
            if not dest.exists() and source.suffix == ".parquet":
                for record in prior:
                    candidate = Path(record["path"])
                    if candidate.exists() and candidate.suffix == ".parquet" and "snapshot_audit" not in str(candidate):
                        if table_equal(pq.read_table(candidate), pq.read_table(source)):
                            reused_elsewhere = candidate
                            break
            existed = dest.exists()
            if not same:
                dest.parent.mkdir(parents=True, exist_ok=True)
                if existed:
                    old = history_by_path.get(str(dest.resolve().relative_to(ROOT)))
                    if old is not None:
                        if sha(dest) != old["sha256"] or sha(ROOT / old["archived"]) != old["sha256"]:
                            raise ValueError("Existing artifact differs from its preserved history")
                    else:
                        backup = evidence_root / "backups" / relative
                        backup.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(dest, backup)
                        if sha(dest) != sha(backup):
                            raise ValueError("Backup checksum failed")
                # Stage and destination may be on different filesystems: copy to a
                # destination-local temporary file, then rename atomically.
                pending = dest.with_name(f".{dest.name}.p5-pending")
                if pending.exists():
                    raise FileExistsError(f"Stale pending artifact: {pending}")
                shutil.copy2(reused_elsewhere or source, pending)
                os.replace(pending, dest)
            results.append(dict(artifact=str(relative), path=str(dest), status="EXISTS+VALID" if same else "REPLACED+VALID" if existed else "CREATED+VALID",
                                reuse_source=str(reused_elsewhere) if reused_elsewhere else None))
        checked_final = validate_bundle(output_root, table, df, vocabulary, frame, dictionary, matrix)
    if sha(manifest_path) != input_before:
        raise ValueError("Input changed during run")
    load_snapshot(manifest_path)  # verify partition bytes again, not just manifest text
    x = frame[skills].to_numpy()
    raw_pairs = sum(len(set(s.casefold() for s in values)) for values in df.skills_std if values is not None)
    canonical_pairs = int(x.sum())
    frequencies = x.sum(axis=0)
    top_pairs = sorted([(int(c.iloc[i, j]), skills[i], skills[j]) for i in range(230) for j in range(i+1, 230)], key=lambda row: (-row[0], row[1], row[2]))[:5]
    measures = {}
    for item in results:
        path = Path(item["path"])
        measurements = []
        if path.suffix == ".parquet":
            for _ in range(5):
                before = time.perf_counter()
                pq.read_table(path)
                measurements.append(time.perf_counter()-before)
        measures[item["artifact"]] = dict(bytes=path.stat().st_size, mb_decimal=path.stat().st_size/1_000_000,
                warm_read_seconds=measurements, warm_read_median_seconds=float(np.median(measurements)) if measurements else None)
    metrics = dict(rows=len(df), ninput_p4=ninput_p4, cohort=cohort_info, feature_columns=len(frame.columns), skills=230, skill_frequencies={name: int(n) for name, n in zip(skills, frequencies, strict=True)},
         job_coverage=dict(numerator=int(x.any(axis=1).sum()), denominator=len(df)), canonical_pairs=canonical_pairs,
         source_value_pairs=raw_pairs, unmatched_source_pairs=int(frame.other_skills_count.sum()),
         source_pair_coverage=dict(numerator=raw_pairs-int(frame.other_skills_count.sum()), denominator=raw_pairs),
         all_zero_jobs=int((x.sum(axis=1) == 0).sum()), null_skills=int(frame.skills__missing.sum()), empty_skills=int(frame.skills__empty.sum()),
         unmatched_only_jobs=int(((x.sum(axis=1) == 0) & (frame.other_skills_count > 0)).sum()),
         zero_columns=int((frequencies == 0).sum()), sparsity=1-float(x.mean()), below20=int((frequencies < 20).sum()),
         hard_soft=dict(Counter(i["skill_type"] for i in vocabulary["items"])), groups=dict(Counter(i["group"] or "NULL_METADATA_NOT_A_SEVENTH_GROUP" for i in vocabulary["items"])),
         quality_reasons=quality.reason.value_counts().to_dict(), tfidf_shape=list(matrix.shape), top5_pairs=top_pairs,
         runtime_seconds=time.perf_counter()-start, measurement_method="perf_counter; Arrow read_table five warm reads, median; decimal MB; full runner including validation", artifacts=measures,
         review_matrix_content_equivalent=review_reuse, tfidf_under2000=matrix.shape[1] < 2000)
    metrics["zero_column_skills"] = [name for name, count in zip(skills, frequencies, strict=True) if count == 0]
    write_json(evidence_root / "metrics.json", metrics)
    pd.DataFrame(dict(canonical=[i["canonical"] for i in vocabulary["items"]], column=skills, jobs=frequencies)).to_csv(evidence_root / "skill_frequencies.csv", index=False)
    write_json(evidence_root / "delivery.json", results)
    checked.update(final_checks=checked_final, metrics_file="metrics.json", results=results)
    write_json(output_root / P5 / "validation_report.json", checked)
    write_json(evidence_root / "validation_report.json", checked)
    files = []
    for item in results:
        path = Path(item["path"])
        record = dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path), delivery_status=item["status"])
        if path.suffix == ".parquet":
            arrow = pq.read_table(path)
            logical_shape = [230, 230] if path.name == "skill_cooccurrence.parquet" else [arrow.num_rows, arrow.num_columns]
            record.update(shape=logical_shape, physical_arrow_columns=arrow.num_columns, schema=str(arrow.schema))
        elif path.suffix == ".npz":
            record.update(shape=list(matrix.shape), dtype="float32", format="CSR")
        files.append(record)
    files.append(dict(path=str(output_root / P5 / "validation_report.json"), bytes=(output_root / P5 / "validation_report.json").stat().st_size, sha256=sha(output_root / P5 / "validation_report.json")))
    code_paths = [Path(__file__), *[ROOT / "preprocessing/encoding" / name for name in ["cohort.py", "cohort_assessments.py", "execution_io.py", "execution_features.py", "execution_tfidf.py", "candidate_lookup.py", "run.py", "tfidf_extractor.py"]]]
    manifest = dict(schema_version="p5-artifact-manifest-v1", run_id=evidence_root.name, validation_status="PASS_TECHNICAL_REVIEW",
         acceptance_status="PENDING_ENVIRONMENT_AND_FINAL_HANDOFF_CHECKS", p5_complete=False, cohort=cohort_info,
         input_manifest_sha256=input_before, inputs=entries, merged_input_schema=str(table.schema), producer_commit=None,
         vocabulary_path=repo_relative(vocabulary_path), vocabulary_sha256=sha(vocabulary_path), vocabulary_version=vocabulary["version"],
         stopword_path=repo_relative(stopwords), stopword_sha256=sha(stopwords), tfidf_config_sha256=sha(output_root / P5 / "tfidf_config.json"),
         ordered_id_sha256=ordered_ids_hash(df.job_id_global), head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
         dirty_worktree=bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)), source_sha256={str(p.relative_to(ROOT)): sha(p) for p in code_paths},
         environment=dict(python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__, pyarrow=pa.__version__, scipy=scipy.__version__, sklearn=sklearn.__version__),
         current_artifacts=files, contract="docs/preprocessing/encoding/06_p5_execution_contract.md")
    write_json(output_root / P5 / "artifact_manifest.json", manifest)
    write_json(evidence_root / "artifact_manifest.json", manifest)
    return metrics


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--vocabulary", type=Path, required=True)
    parser.add_argument("--stopwords", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--cohort-ledger", type=Path, required=True)
    parser.add_argument("--decision-record", type=Path, required=True)
    parser.add_argument("--history-root", type=Path, required=True)
    parser.add_argument("--publish", action="store_true", help="Deliver validated files to explicit root, preserving invalid existing files")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    result = run_execution(args.input_manifest, args.vocabulary, args.stopwords, args.output_root,
                           args.evidence_root, dry_run=args.dry_run, publish=args.publish,
                           cohort_ledger=args.cohort_ledger, decision_record=args.decision_record, history_root=args.history_root)
    print(json.dumps({key: value for key, value in result.items() if key not in {"skill_frequencies", "artifacts"}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
