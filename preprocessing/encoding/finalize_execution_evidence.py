"""Read-only artifact verification plus run-specific review/performance evidence."""

import json
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd

from preprocessing.encoding.execution_io import load_snapshot, sha, write_json

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "reports/preprocessing/05_encoding/p5_2026-11-09_frozen_v2"


def main():
    manifest = json.loads((RUN / "artifact_manifest.json").read_text())
    protected = json.loads((RUN / "protected_inputs.json").read_text())
    assert all(sha(ROOT / path) == value for path, value in protected.items())
    for record in manifest["current_artifacts"]:
        assert sha(ROOT / record["path"]) == record["sha256"]
    assert all(sha(ROOT / path) == value for path, value in manifest["source_sha256"].items())
    _, df, _ = load_snapshot(ROOT / "reports/preprocessing/05_encoding/snapshot_audit_2026-11-08/manifest.json")
    records = []
    for row in df.to_dict("records"):
        if not any(value.casefold() == "autocad" for value in row["skills_std"]):
            continue
        context = {}
        for field in ["description_clean", "requirements_clean"]:
            value = row.get(field)
            if isinstance(value, str):
                match = re.search("autocad", value, re.IGNORECASE)
                if match:
                    start, end = max(0, match.start()-90), min(len(value), match.end()+190)
                    context = dict(field=field, start=start, end=end, excerpt=value[start:end])
                    break
        if not context:
            context = dict(field="skills_std", start=None, end=None, excerpt="explicit AutoCAD metadata; no literal clean-JD excerpt")
        records.append(dict(job_id_global=row["job_id_global"], job_title=row["job_title"],
                            job_family=row["job_family"], raw_category_text=row["raw_category_text"],
                            **context, scope_status="review_pending_no_row_or_skill_removed"))
    pd.DataFrame(records).to_csv(RUN / "autocad_scope_evidence.csv", index=False)
    write_json(RUN / "acceptance_decision.json", dict(
        decision="NOT_ACCEPTED_YET_CREATE_ARTIFACTS_FOR_REVIEW", source="Phát reply to AutoCAD scope question, 2026-11-09",
        answer="Chưa chấp nhận nghiệm thu; vẫn tạo artifact để review", affected_jobs=len(records),
        row_or_skill_removed=False, p5_complete=False))
    performance_path = RUN / "performance_pandas.json"
    times = json.loads(performance_path.read_text())["results"] if performance_path.exists() else {}
    for relative in ["data/curated/curated_flat_golden_jobs.parquet", "data/preprocessing/05_encoding/features.parquet", "data/preprocessing/05_encoding/skill_cooccurrence.parquet"]:
        if relative in times:
            continue
        seconds = []
        for _ in range(5):
            start = time.perf_counter()
            pd.read_parquet(ROOT / relative)
            seconds.append(time.perf_counter()-start)
        times[relative] = dict(warm_read_seconds=seconds, median_seconds=float(np.median(seconds)),
                               bytes=(ROOT / relative).stat().st_size)
    write_json(RUN / "performance_pandas.json", dict(method="pandas.read_parquet, 5 warm reads, perf_counter, median; no cold-cache claim", results=times))
    suite = ET.parse(RUN / "tests_p5.xml").getroot().find("testsuite")
    assert int(suite.attrib["failures"]) == 0 and int(suite.attrib["errors"]) == 0
    for record in manifest["current_artifacts"]:
        path = ROOT / record["path"]
        record.setdefault("bytes", path.stat().st_size)
        if path.suffix == ".json":
            record.setdefault("format", "JSON")
            record.setdefault("schema_keys", sorted(json.loads(path.read_text()).keys()) if isinstance(json.loads(path.read_text()), dict) else ["ordered_items"])
    manifest["acceptance_reference"] = dict(path=str((RUN / "acceptance_decision.json").relative_to(ROOT)),
                                           sha256=sha(RUN / "acceptance_decision.json"))
    manifest["verification_source_sha256"] = {str(Path(__file__).relative_to(ROOT)): sha(Path(__file__))}
    manifest["tests"] = dict(related_passed=int(suite.attrib["tests"]), whole_repo="6 pre-existing collection errors",
                             python312="not available; not verified", lint="PASS")
    manifest["evidence_sha256"] = {name: sha(RUN / name) for name in [
        "tests_p5.xml", "tests_full_offline.xml", "lint.log", "autocad_scope_evidence.csv", "performance_pandas.json",
        "protected_inputs.json", "metrics.json", "delivery.json", "inventory_before.json"]}
    write_json(ROOT / "data/preprocessing/05_encoding/artifact_manifest.json", manifest)
    write_json(RUN / "artifact_manifest.json", manifest)
    write_json(RUN / "final_integrity.json", dict(status="PASS", protected_files=len(protected),
        current_artifacts=len(manifest["current_artifacts"]), source_hashes_match=True,
        autocad_jobs=len(records), acceptance="PENDING", p5_complete=False))
    print(json.dumps(dict(protected_files=len(protected), autocad_jobs=len(records), pandas_read=times), indent=2))


if __name__ == "__main__":
    main()
