"""Validate review evidence against frozen real P4; never write production data."""

import hashlib
import json
from collections import Counter
from pathlib import Path

import pandas as pd

from preprocessing.encoding.prepare_approval_package import make_proposal
from preprocessing.encoding.run import to_col_slug

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    base = ROOT / "reports/preprocessing/05_encoding"
    snapshot = base / "snapshot_audit_2026-11-08"
    package = base / "approval_package_v1"
    summary = json.loads((package / "summary.json").read_text())
    manifest = json.loads((snapshot / "manifest.json").read_text())
    assert sha(snapshot / "manifest.json") == summary["snapshot_manifest_sha256"]
    assert sha(package / "proposal_builder_source.py.txt") == summary["source_script_sha256"]
    frames = []
    for item in manifest:
        source = item["key"].split("/")[1]
        path = snapshot / f"{source}.parquet"
        assert sha(path) == item["sha256"]
        frame = pd.read_parquet(path)
        assert len(frame) == item["rows"]
        assert set(frame.source_platform) == {source}
        frames.append(frame)
    df = pd.concat(frames, ignore_index=True)
    assert len(df) == 5177 and df.job_id_global.notna().all() and df.job_id_global.is_unique
    rows = [set(map(str, values)) for values in df.skills_std]
    definitions, _ = make_proposal(rows)
    for filename, expected in [
        ("all_curated_proposals.csv", definitions),
        ("vocabulary_proposed.csv", definitions[:230]),
        ("vocabulary_reserves.csv", definitions[230:260]),
    ]:
        actual = pd.read_csv(package / filename, keep_default_na=False)
        pd.testing.assert_frame_equal(actual, pd.DataFrame(expected), check_dtype=False)
        assert actual.canonical.is_unique
        assert actual.jobs.gt(0).all()
        assert actual.decision.eq("").all() and actual.status.eq("proposed").all()
    columns = [f"skill_{to_col_slug(item['canonical'])}" for item in definitions[:230]]
    assert len(columns) == len(set(columns)) == 230
    for name, expected_hash in summary["protected_sha256"].items():
        assert sha(base / "review_2026-11-08" / name) == expected_hash
    counts = Counter(value for row in rows for value in row)
    cases = [
        ("C/C++", "ambiguous composite", "Defer; cannot infer separate C and C++"),
        ("HTML/CSS", "composite", "Keep composite only if approved; never split"),
        ("Agile/Scrum", "composite", "Keep composite only if approved; never split"),
        ("Machine Learning", "broad upstream category", "Keep broad; no framework recovery"),
        ("Tensorflow Serving", "distinct product", "Reserve only; do not map to TensorFlow"),
    ]
    focused = [dict(value=value, jobs=counts[value], issue=issue, recommendation=decision,
                    status="proposed", decision="")
               for value, issue, decision in cases if counts[value] > 0]
    pd.DataFrame(focused).to_csv(package / "ambiguities_for_review.csv", index=False)
    report = dict(
        status="PASS_REVIEW_EVIDENCE_ONLY", jobs=len(df), checked_partitions=len(manifest),
        proposals=len(definitions), selected=230, reserves=len(definitions[230:260]),
        canonical_semantics_approved=False, p5_complete=False,
        checks=["snapshot SHA/rows/source/unique IDs", "all CSVs equal recomputed job-union counts",
                "all proposed entries observed", "no alias/slug collision", "manual files unchanged",
                "all decision fields blank", "original builder hash verified"],
        current_builder_sha256=sha(ROOT / "preprocessing/encoding/prepare_approval_package.py"),
        original_source_note="Archived source matches generation hash; current source only splits E702 statement",
        environment_note="Python 3.14.4; Python 3.12 not validated",
        test_attempt_note=("test_results.xml: bad paths; pytest_validated.xml: repository hook rejects mixed test roots; "
                           "pytest_review.xml and pytest_existing.xml are separate corrected runs"),
    )
    report["artifact_sha256"] = {
        path.name: sha(path) for path in sorted(package.iterdir())
        if path.is_file() and path.name != "validation.json"
    }
    (package / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({key: value for key, value in report.items() if key != "artifact_sha256"}))


if __name__ == "__main__":
    main()
