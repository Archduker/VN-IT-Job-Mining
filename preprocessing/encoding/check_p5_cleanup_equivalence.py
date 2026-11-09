"""Run before/after P5 in temporary directories using the same verified P4."""

# ruff: noqa: E402
import hashlib
import importlib
import json
import pickle
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "reports/preprocessing/05_encoding/cleanup_review_2026-11-08"
sys.path.insert(0, str(ROOT))
import pandas as pd


def run(mode):
    module = importlib.import_module("preprocessing.encoding.run")
    step = importlib.import_module("preprocessing.common.step_report")
    snap = ROOT / "reports/preprocessing/05_encoding/snapshot_audit_2026-11-08"
    manifest = json.loads((snap / "manifest.json").read_text())
    parts = []
    for item in manifest:
        p = snap / (item["key"].split("/")[1] + ".parquet")
        assert hashlib.sha256(p.read_bytes()).hexdigest() == item["sha256"]
        parts.append(pd.read_parquet(p))
    df = pd.concat(parts, ignore_index=True)
    assert len(df) == 5177 and df.job_id_global.is_unique
    prior_report = ROOT / "reports/preprocessing/05_encoding/_all.json"
    report_hash = hashlib.sha256(prior_report.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="p5-cleanup-equivalence-") as temporary:
        tmp = Path(temporary)
        source = tmp / "input.parquet"
        df.to_parquet(source, index=False)
        out = tmp / "out"
        overrides = dict(
            IN_FILE=source,
            OUT_DIR=out,
            OUT_FEATURES_FILE=out / "features.parquet",
            OUT_COOCCURRENCE_FILE=out / "skill_cooccurrence.parquet",
            OUT_DICT_FILE=out / "encoding_dictionary.json",
        )
        with (
            patch.multiple(module, **overrides),
            patch.object(step, "REPORTS_ROOT", tmp / "reports"),
        ):
            module.run(dry_run=True)
            assert not out.exists()
            module.run(dry_run=False)
            features = pd.read_parquet(out / "features.parquet")
            cooccur = pd.read_parquet(out / "skill_cooccurrence.parquet")
            dictionary = json.loads((out / "encoding_dictionary.json").read_text())
            report = json.loads((tmp / "reports/05_encoding/_all.json").read_text())
            artifact = json.loads((out / "artifact_manifest.json").read_text())
            payload = dict(
                features=features,
                cooccurrence=cooccur,
                dictionary=dictionary,
                rules=report["rules"],
                extra=report["extra"],
                vocabulary=module.ORDERED_SKILL_COLUMNS,
                schema={
                    name: pd.read_parquet(out / name).dtypes.astype(str).to_dict()
                    for name in ["features.parquet", "skill_cooccurrence.parquet"]
                },
                manifest_artifacts=artifact["artifacts"],
            )
    assert hashlib.sha256(prior_report.read_bytes()).hexdigest() == report_hash
    baseline = EVIDENCE / "p5_before_cleanup.pkl"
    if mode == "before":
        with baseline.open("wb") as f:
            pickle.dump(payload, f)
        print("BEFORE_CAPTURED", features.shape, cooccur.shape)
    else:
        with baseline.open("rb") as f:
            old = pickle.load(f)
        for field in ["features", "cooccurrence"]:
            pd.testing.assert_frame_equal(old[field], payload[field], check_exact=True)
        for field in ["dictionary", "rules", "extra", "vocabulary", "schema", "manifest_artifacts"]:
            assert old[field] == payload[field], field
        summary = dict(
            rows=len(features),
            feature_columns=len(features.columns),
            skill_columns=len(module.ORDERED_SKILL_COLUMNS),
            cooccurrence_shape=list(cooccur.shape),
            exact_values_ids_order_schema_missing_equal=True,
            artifact_bytes_sha256_equal=True,
            dry_run_wrote_data=False,
            original_report_preserved=True,
        )
        (EVIDENCE / "p5_cleanup_equivalence.json").write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary))


if __name__ == "__main__":
    run(sys.argv[1])
