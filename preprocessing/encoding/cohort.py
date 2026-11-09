"""Version-bound Phát-authorized cohort ledger and one historical bundle archive."""

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa

from preprocessing.encoding import cohort_assessments
from preprocessing.encoding.execution_io import load_snapshot, ordered_ids_hash, sha, write_json

ROOT = Path(__file__).resolve().parents[2]
SCOPE = ROOT / "reports/preprocessing/05_encoding/scope_review_2026-11-09_v1"
ASSETS = ROOT / "preprocessing/encoding/assets/cohort_v1"
REPORT = ROOT / "reports/preprocessing/05_encoding/p5_2026-11-09_cohort_v1"
HISTORY = ROOT / "data/preprocessing/05_encoding_history/p5_2026-11-09_frozen_v2"
REVIEW_HASHES = {
    "scope_decisions_proposed.csv": "1ebb40b8f66daa58c38e34bd3a1d66d6a82fb6beb8e577277ee5e3fc39bd3b08",
    "scope_review_queue.csv": "8a848bf1f4a2dbf0bf3b5605485127057a52c037fa11d80901eddf2ea961045e",
    "annotations_proposed.json": "a91ea7c42e01dc64706dc83e00ee07f51486f0fabe2ccb52df26b4e60b5d7a97",
}
DISPOSITIONS = {"include", "exclude", "quarantine"}
REVIEW_STATUS = {"retained_reviewed", "retained_unreviewed", "excluded_by_approved_policy", "unresolved_quarantined"}


def relative(path):
    return str(Path(path).resolve().relative_to(ROOT))


def archive_history():
    marker = HISTORY / "history_manifest.json"
    if marker.exists():
        result = json.loads(marker.read_text())
        if not all(sha(ROOT / row["archived"]) == row["sha256"] for row in result["files"]):
            raise ValueError("Historical archive checksum mismatch")
        return result
    manifest_path = ROOT / "data/preprocessing/05_encoding/artifact_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for item in manifest["current_artifacts"]:
        if sha(ROOT / item["path"]) != item["sha256"]:
            raise ValueError("Cannot archive an altered prior bundle")
    for path, checksum in manifest["source_sha256"].items():
        if sha(ROOT / path) != checksum:
            raise ValueError(f"Archive executed source before edits: {path}")
    paths = {ROOT / item["path"] for item in manifest["current_artifacts"]}
    paths.add(manifest_path)
    paths.update(ROOT / path for path in manifest["source_sha256"])
    paths.update(ROOT / path for path in ["docs/preprocessing/encoding/06_p5_execution_contract.md",
        "docs/preprocessing/encoding/07_p5_execution_report.md", "preprocessing/encoding/run_encoding.py",
        "tests/unit/test_encoding_step.py", "tests/unit/test_encoding_safety.py"])
    HISTORY.mkdir(parents=True, exist_ok=False)
    records = []
    for path in sorted(paths):
        dest = HISTORY / relative(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        assert sha(path) == sha(dest)
        records.append(dict(original=relative(path), archived=relative(dest), sha256=sha(path), bytes=path.stat().st_size))
    result = dict(version="historical-5177-v1", rows=5177, prior_run_id=manifest["run_id"], files=records,
                  purpose="One immutable historical bundle; not current Mining cohort")
    write_json(marker, result)
    return result


def validate_ledger(ids, ledger):
    required = {"job_id_global", "disposition", "review_status", "reason", "evidence_reference", "decision_reference"}
    if not required <= set(ledger):
        raise ValueError("Missing ledger columns")
    if not ledger.job_id_global.is_unique or ledger.job_id_global.tolist() != list(ids):
        raise ValueError("Ledger must account for every P4 ID exactly once in input order")
    if not ledger.disposition.isin(DISPOSITIONS).all() or not ledger.review_status.isin(REVIEW_STATUS).all():
        raise ValueError("Invalid ledger disposition/review status")
    expected = {"retained_reviewed": "include", "retained_unreviewed": "include", "excluded_by_approved_policy": "exclude", "unresolved_quarantined": "quarantine"}
    if not ledger.apply(lambda row: expected[row.review_status] == row.disposition, axis=1).all():
        raise ValueError("Ledger status contradicts disposition")
    for column in ["reason", "evidence_reference", "decision_reference"]:
        if not ledger[column].map(lambda value: isinstance(value, str) and bool(value.strip())).all():
            raise ValueError("Ledger decisions need auditable references")
    counts = ledger.disposition.value_counts().to_dict()
    if sum(counts.values()) != len(ids):
        raise ValueError("Ledger partition not conserved")
    return counts


def validate_approved_ids(ledger, approved):
    dispositions = ledger.set_index("job_id_global").disposition
    for row in approved.itertuples():
        if row.proposed_decision in {"retain_proposed", "exclude_proposed"}:
            expected = "include" if row.proposed_decision == "retain_proposed" else "exclude"
            if row.job_id_global not in dispositions or dispositions[row.job_id_global] != expected:
                raise ValueError("Ledger contradicts an explicitly approved retained/excluded ID")


def apply_ledger(table, df, ledger_path, decision_record):
    ledger_path, decision_record = Path(ledger_path), Path(decision_record)
    metadata_path = ledger_path.with_suffix(".meta.json")
    metadata = json.loads(metadata_path.read_text())
    decision = json.loads(decision_record.read_text())
    if metadata["ledger_sha256"] != sha(ledger_path) or metadata["decision_record_sha256"] != sha(decision_record):
        raise ValueError("Ledger/decision checksum mismatch")
    if decision["status"] != "authorized_by_Phat_for_cohort_run":
        raise ValueError("Cohort policy is not authorized")
    if sha(ROOT / decision["authorization_asset"]) != decision["authorization_sha256"]:
        raise ValueError("Repository authorization record changed")
    if metadata["snapshot_manifest_sha256"] != decision["snapshot_manifest_sha256"]:
        raise ValueError("Ledger and authorization refer to different P4 snapshots")
    for name, expected in decision["approved_review_files"].items():
        if sha(SCOPE / name) != expected:
            raise ValueError("Owner-approved review version changed")
    ledger = pd.read_csv(ledger_path, keep_default_na=False)
    counts = validate_ledger(df.job_id_global.tolist(), ledger)
    approved = pd.read_csv(SCOPE / "scope_decisions_proposed.csv", keep_default_na=False)
    validate_approved_ids(ledger, approved)
    if metadata["partition_counts"] != counts:
        raise ValueError("Ledger metadata count mismatch")
    positions = np.flatnonzero(ledger.disposition.eq("include").to_numpy())
    cohort = df.iloc[positions].reset_index(drop=True)
    if cohort.empty:
        raise ValueError("Empty include cohort")
    if ordered_ids_hash(cohort.job_id_global) != metadata["include_ordered_ids_sha256"]:
        raise ValueError("Cohort ID order checksum mismatch")
    info = dict(version=metadata["version"], ledger_path=relative(ledger_path), ledger_sha256=sha(ledger_path),
                decision_record_path=relative(decision_record), decision_record_sha256=sha(decision_record),
                ninput_p4=len(df), partition_counts=counts, include_ordered_ids_sha256=metadata["include_ordered_ids_sha256"],
                review_status_counts=ledger.review_status.value_counts().to_dict(),
                snapshot_manifest_sha256=metadata["snapshot_manifest_sha256"],
                limitations="Retained_unreviewed and outside-queue jobs are not verified IT; no upstream filter fix")
    return table.take(pa.array(positions, type=pa.int64())), cohort, info


def prepare(authorization_path):
    if (ASSETS / "ledger.csv").exists():
        raise FileExistsError("Frozen ledger already exists; do not overwrite")
    for name, checksum in REVIEW_HASHES.items():
        if sha(SCOPE / name) != checksum:
            raise ValueError(f"Owner approval refers to a different review version: {name}")
    previous = pd.read_csv(SCOPE / "scope_decisions_proposed.csv", keep_default_na=False)
    if previous.proposed_decision.value_counts().to_dict() != {"exclude_proposed": 27, "unresolved": 19, "retain_proposed": 8}:
        raise ValueError("Approved27/8 list changed")
    queue = pd.read_csv(SCOPE / "scope_review_queue.csv", keep_default_na=False)
    expected = set(queue.loc[queue.priority.eq("P1_family_conflict_candidate") & queue.review_state.eq("not_reviewed"), "job_id_global"])
    assessments = cohort_assessments.records()
    if len(expected) != 31 or {item["job_id_global"] for item in assessments} != expected or len(assessments) != 31:
        raise ValueError("Only and all31 outstanding P1 cases must be assessed")
    snapshot = ROOT / "reports/preprocessing/05_encoding/snapshot_audit_2026-11-08/manifest.json"
    table, df, _ = load_snapshot(snapshot)
    sources = df.set_index("job_id_global")
    for item in assessments:
        if item["evidence_quote"] not in sources.loc[item["job_id_global"], item["evidence_field"]]:
            raise ValueError(f"P1 quote not found: {item['job_id_global']}")
    history = archive_history()
    ASSETS.mkdir(parents=True, exist_ok=True)
    REPORT.mkdir(parents=True, exist_ok=True)
    authorization_dest = ASSETS / "authorization_agent07.md"
    shutil.copy2(authorization_path, authorization_dest)
    frozen_origin = ROOT / "reports/preprocessing/05_encoding/p5_2026-11-09_frozen_v2/vocabulary_frozen.json"
    runtime_vocab = ROOT / "preprocessing/encoding/assets/frozen_vocabulary_v1.json"
    if runtime_vocab.exists() and sha(runtime_vocab) != sha(frozen_origin):
        raise ValueError("Runtime vocabulary differs from preserved frozen vocabulary")
    if not runtime_vocab.exists():
        shutil.copy2(frozen_origin, runtime_vocab)
    decision = dict(version="p5-cohort-policy-v1", status="authorized_by_Phat_for_cohort_run",
        authority="Phát", authorization_asset=relative(authorization_dest), authorization_sha256=sha(authorization_dest),
        approved_review_files=REVIEW_HASHES, snapshot_manifest_sha256=sha(snapshot), vocabulary_sha256=sha(runtime_vocab),
        policy_sections="agent_07 §1/§3: approved27exclude/8retain; apply policy to19unresolved and31P1; retain410P2 and outsidequeue unreviewed",
        not_human_gold_labels=True, decision_reference=relative(authorization_dest))
    decision_path = ASSETS / "decision_record.json"
    write_json(decision_path, decision)
    prior_by_id = previous.set_index("job_id_global").to_dict("index")
    assessed_by_id = {item["job_id_global"]: item for item in assessments}
    queue_by_id = queue.set_index("job_id_global").to_dict("index")
    ledger = []
    old_unresolved = []
    for row in df.itertuples():
        job_id = row.job_id_global
        evidence = relative(SCOPE / "scope_review_queue.csv") + "#" + job_id
        if job_id in prior_by_id:
            prior = prior_by_id[job_id]
            proposed = prior["proposed_decision"]
            evidence = relative(SCOPE / "scope_decisions_proposed.csv") + "#" + job_id
            if proposed == "exclude_proposed":
                disposition, reason = "exclude", "Phát approved this exact ID in27exclude: " + prior["reason"]
            elif proposed == "retain_proposed":
                disposition, reason = "include", "Phát approved this exact ID in8retain: " + prior["reason"]
            else:
                group = prior["boundary_group"]
                excluded_groups = {"graphics_vs_product": "pure advertising/packaging/printing excluded", "industrial_plc": "pure PLC/HMI control excluded", "telecom_field_installation": "physical telecom site installation excluded"}
                disposition = "exclude" if group in excluded_groups else "quarantine"
                reason = "Apply approved policy: " + excluded_groups[group] if group in excluded_groups else "Insufficient evidence/new boundary remains unresolved, not confirmed non-IT"
                old_unresolved.append(dict(job_id_global=job_id, disposition=disposition, boundary_group=group, reason=reason,
                                           evidence_field=prior["evidence_field"], evidence_quote=prior["evidence_quote"], policy_reference="agent_07 §1/§3"))
        elif job_id in assessed_by_id:
            assessment = assessed_by_id[job_id]
            disposition, reason = assessment["disposition"], assessment["reason"]
            evidence = relative(REPORT / "p1_assessments.csv") + "#" + job_id
        else:
            disposition = "include"
            reason = "P2 retained_unreviewed by approved bounded-review policy" if job_id in queue_by_id else "not_flagged_by_targeted_rules; retained_unreviewed, not verified IT"
            if job_id not in queue_by_id:
                evidence = relative(SCOPE / "rules.json") + "#not_flagged_by_targeted_rules"
        reviewed = job_id in prior_by_id or job_id in assessed_by_id
        status = "retained_reviewed" if disposition == "include" and reviewed else "retained_unreviewed" if disposition == "include" else "excluded_by_approved_policy" if disposition == "exclude" else "unresolved_quarantined"
        ledger.append(dict(job_id_global=job_id, disposition=disposition, review_status=status, reason=reason,
                           evidence_reference=evidence, decision_reference=relative(decision_path) + "#agent_07_1_3"))
    ledger_df = pd.DataFrame(ledger)
    counts = validate_ledger(df.job_id_global.tolist(), ledger_df)
    ledger_path = ASSETS / "ledger.csv"
    ledger_df.to_csv(ledger_path, index=False)
    included = ledger_df.disposition.eq("include")
    metadata = dict(version="p5-cohort-ledger-2026-11-09-v1", ledger_sha256=sha(ledger_path), decision_record_sha256=sha(decision_path),
        snapshot_manifest_sha256=sha(snapshot), partition_counts=counts,
        include_ordered_ids_sha256=ordered_ids_hash(df.loc[included, "job_id_global"]),
        original_ordered_ids_sha256=ordered_ids_hash(df.job_id_global), review_status_counts=ledger_df.review_status.value_counts().to_dict(),
        source_dispositions=pd.crosstab(df.source_platform, ledger_df.disposition).to_dict(),
        p1_assessment_source_sha256=sha(Path(cohort_assessments.__file__)), approved_review_hashes=REVIEW_HASHES,
        reviewed_ids=85, retained_unreviewed_P2=410, not_flagged_by_targeted_rules=4682,
        applied_job_family_changes=False, history_manifest=relative(HISTORY / "history_manifest.json"))
    write_json(ledger_path.with_suffix(".meta.json"), metadata)
    pd.DataFrame(assessments).to_csv(REPORT / "p1_assessments.csv", index=False)
    pd.DataFrame(old_unresolved).to_csv(REPORT / "resolved_previous19.csv", index=False)
    # Entire available P1 texts are auditable; no ellipsis is added by this export.
    packet = []
    reviewed_hashes = []
    for item in assessments:
        source = sources.loc[item["job_id_global"]]
        packet.append(f"# {item['job_id_global']} — {source.job_title}\n\n## Full available description\n{source.description_clean}\n\n## Full available requirements\n{source.requirements_clean}\n")
        reviewed_hashes.append(dict(job_id_global=item["job_id_global"], fields_reviewed=["job_title", "description_clean", "requirements_clean", "skills_std", "raw_category_text", "job_family"],
                                   description_sha256=__import__("hashlib").sha256(source.description_clean.encode()).hexdigest(), requirements_sha256=__import__("hashlib").sha256(source.requirements_clean.encode()).hexdigest()))
    (REPORT / "p1_full_available_texts.md").write_text("\n\n".join(packet), encoding="utf-8")
    write_json(REPORT / "p1_full_text_review_log.json", reviewed_hashes)
    write_json(REPORT / "cohort_summary.json", metadata)
    write_json(REPORT / "historical_bundle_reference.json", history)
    apply_ledger(table, df, ledger_path, decision_path)
    print(json.dumps(dict(partition_counts=counts, reviewed85=True, P2_not_reviewed=410, status_counts=metadata["review_status_counts"]), indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization", type=Path, required=True)
    prepare(parser.parse_args().authorization)
