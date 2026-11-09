"""Targeted scope-review queue and RAM-only impact; never changes cohorts/artifacts.

Regexes nominate candidates only. Decisions are explicit per-ID Agent proposals
from full available texts, with blank human decision fields and validated quotes.
"""

import argparse
import hashlib
import json
import platform
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from preprocessing.encoding import scope_review_annotations
from preprocessing.encoding.candidate_lookup import build_candidate_lookup, encode_candidate_rows
from preprocessing.encoding.execution_io import load_snapshot, sha, write_json

ROOT = Path(__file__).resolve().parents[2]
TEXT_FIELDS = ["job_title", "description_clean", "requirements_clean"]
RULES = [
    dict(rule_id="S01_CIVIL", pattern=r"\bcivil\b|construction (?:site|engineering|work|quality)|thi công xây dựng|công trường|kỹ (?:sư|thuật) xây dựng|kết cấu (?:thép|bê tông)|hồ sơ (?:nghiệm thu|hoàn công)|vật liệu (?:xây dựng|thi công)"),
    dict(rule_id="S02_MECHANICAL_HVAC", pattern=r"thiết kế cơ khí|cơ khí chế tạo|chế tạo máy|khuôn mẫu|\bmechanical\b|\bhvac\b|hệ thống lạnh|điều hòa không khí|kỹ thuật nhiệt|sản phẩm cơ khí"),
    dict(rule_id="S03_SPATIAL_CAD_BIM", pattern=r"\bbim\b|\bautocad\b|\bcad\b|\brevit\b|\barchitectural\b|design engineer\s*\(architect\)|kiến trúc sư(?! giải pháp| phần mềm| hệ thống)|cảnh quan|shop drawing|bản vẽ (?:chế tạo|lắp dựng|thi công)|booth|sân khấu|nội thất"),
    dict(rule_id="S04_CNC_MANUFACTURING", pattern=r"\bcnc\b|gia công (?:cơ khí|chi tiết|cắt)|máy (?:phay|tiện)|g-code|m-code|đường chạy dao|lập trình (?:máy|gia công)|chế tạo khuôn"),
    dict(rule_id="S05_PLC_BOUNDARY", pattern=r"\bplc\b|lập trình (?:điều khiển|hmi)|industrial automation|tự động hóa công nghiệp|biến tần|\bscada\b|\bservo\b"),
    dict(rule_id="S06_TELECOM_SITE", pattern=r"tower climber|site tower|antenna bracket|ran site|cột (?:ăng ten|anten)|thi công (?:trạm|cáp)|lắp đặt (?:trạm|anten)|base station|grounding (?:cable|bar)|\b(?:BBU|RRU)\b"),
    dict(rule_id="S07_GRAPHICS_BOUNDARY", pattern=r"\bposm\b|standee|brochure|bao bì|tem nhãn|nhận diện thương hiệu|ấn phẩm (?:quảng cáo|truyền thông|in ấn)|banner quảng cáo|\bpackaging\b|event décor|activation|biển hiệu"),
]
IT_SIGNALS = [
    dict(rule_id="I01_SOFTWARE_ACTIVITY", pattern=r"(?:phát triển|lập trình|kiểm thử).{0,45}(?:phần mềm|ứng dụng|website)|software (?:development|testing)|develop.{0,30}(?:application|software)|\bbackend\b|\bfrontend\b"),
    dict(rule_id="I02_DIGITAL_INTERFACE", pattern=r"thiết kế giao diện|giao diện (?:website|ứng dụng|landing)|ui/ux|user experience|user interface|wirefram|usability testing"),
    dict(rule_id="I03_NETWORK_ACTIVITY", pattern=r"quản trị.{0,30}(?:mạng|máy chủ)|network (?:security|administration|operation)|router|switching|cấu hình.{0,30}(?:mạng|router|firewall)"),
    dict(rule_id="I04_EMBEDDED_ACTIVITY", pattern=r"\bfirmware\b|\bembedded\b|vi điều khiển|\bmicrocontroller\b|lập trình nhúng|\brtos\b|board bring.up"),
]
SUSPECT_FAMILIES = {"Backend", "Thiết kế UI/UX", "Kiểm thử (QA/QC)"}
BOUNDARY_POLICIES = {
    "graphics_vs_product": dict(include_option="Include wider branding/advertising design", exclude_option="Exclude marketing/print-only; retain explicit web/app interface roles", consequence="Changes marketing designers' cohort and Adobe/soft-skill frequencies; never use company sector alone", recommendation="Retain explicit interface activity proposals; ask Phát about mixed or marketing-only work"),
    "industrial_plc": dict(include_option="Include PLC/HMI control programming within IT/OT", exclude_option="Limit IT to software systems/embedded; exclude PLC-only industrial work", consequence="PLC jobs may have real C++/Python; do not remove WMS software development with PLC integration", recommendation="Keep software development clear cases; defer PLC-only policy to Phát"),
    "telecom_field_installation": dict(include_option="Include RAN/tower installation in ICT scope", exclude_option="Include software/network operations but exclude tower/site construction", consequence="Affects installation/QC rows, not all telecommunications employers or network engineers", recommendation="Phát decides physical site-installation scope; preserve both proposed IDs pending decision"),
    "embedded_vs_machining": dict(include_option="Include software/firmware/embedded engineering", exclude_option="Exclude CNC/CAM machine operation and physical mould design", consequence="Distinguish firmware code from CNC toolpaths; no blanket hardware exclusion", recommendation="Retain firmware developer; propose excluding clearly observed machining activities by ID"),
    "bim_vs_software": dict(include_option="Include software plugin development for BIM/CAD", exclude_option="Exclude structural drafting/modelling without software-development duties", consequence="BIM domain alone cannot decide; source-truncated modeler remains unresolved", recommendation="Retain actual Command/Plugin coding; obtain/decide missing role context for structural modeler"),
    "hardware_test_vs_software": dict(include_option="Include equipment/hardware test engineering", exclude_option="Limit testing to software/firmware testing", consequence="Semiconductor equipment cycle test is not automatically software QA", recommendation="Ask Phát to define hardware-test boundary; do not infer firmware duty from title Test Engineer"),
    "mechanical_vs_software": dict(include_option="Include engineering automation where coding is a primary duty", exclude_option="Exclude mechanical CAD/material development without such duties", consequence="Python/VBA metadata does not establish the actual job activity, especially in truncated source", recommendation="Keep this role unresolved until activity/scope is clear"),
}


def field_hits(row, rules):
    hits = []
    for rule in rules:
        for field in TEXT_FIELDS:
            value = row.get(field)
            if not isinstance(value, str):
                continue
            hit = re.search(rule["pattern"], value, re.IGNORECASE)
            if hit:
                start, end = max(0, hit.start()-75), min(len(value), hit.end()+130)
                hits.append(dict(rule_id=rule["rule_id"], field=field, match=hit.group(), match_start=hit.start(),
                                 match_end=hit.end(), excerpt_start=start, excerpt_end=end, excerpt=value[start:end]))
    return hits


def scan_queue(rows, seed_ids):
    queue, flat = [], []
    for row in rows:
        job_id = row["job_id_global"]
        hits = field_hits(row, RULES)
        if job_id in seed_ids:
            hits.insert(0, dict(rule_id="S00_AUTOCAD_SEED", field="skills_std", match="AutoCAD whole-value metadata",
                                excerpt="AutoCAD", match_start=None, match_end=None, excerpt_start=None, excerpt_end=None))
        if not hits:
            continue
        signals = field_hits(row, IT_SIGNALS)
        mismatch = row.get("job_family") in SUSPECT_FAMILIES and any(hit["rule_id"] in {"S01_CIVIL", "S02_MECHANICAL_HVAC", "S04_CNC_MANUFACTURING"} for hit in hits)
        priority = "P0_AutoCAD" if job_id in seed_ids else "P1_family_conflict_candidate" if mismatch else "P2_targeted_candidate"
        queue.append(dict(job_id_global=job_id, source=row["source_platform"], title=row.get("job_title"),
            job_family=row.get("job_family"), priority=priority, autocad_seed=job_id in seed_ids,
            rule_ids=sorted({hit["rule_id"] for hit in hits}), rule_evidence=hits, it_counter_signals=signals,
            keyword_not_scope_decision=True))
        flat.extend(dict(job_id_global=job_id, signal_type="candidate", **hit) for hit in hits)
        flat.extend(dict(job_id_global=job_id, signal_type="IT_counter_signal_not_proof", **hit) for hit in signals)
    queue.sort(key=lambda item: (item["priority"], item["source"], item["job_id_global"]))
    return queue, flat


def impact_preview(ids, matrix, sources, skill_items, exclude_ids):
    if len(ids) != len(set(ids)) or not exclude_ids <= set(ids):
        raise ValueError("Impact requires unique IDs and known explicit exclusions")
    if matrix.shape != (len(ids), 230):
        raise ValueError("Impact must preserve230 ordered columns")
    mask = np.array([value not in exclude_ids for value in ids])
    before, after = matrix.sum(axis=0), matrix[mask].sum(axis=0)
    reduced = [dict(canonical=skill_items[i]["canonical"], column=skill_items[i]["column"],
                    before=int(before[i]), after=int(after[i]), lost_jobs=int(before[i]-after[i]))
               for i in range(230) if after[i] < before[i]]
    auto = next(i for i, item in enumerate(skill_items) if item["canonical"] == "AutoCAD")
    return dict(status="UNAPPROVED_RAM_ONLY_SCENARIO", ninput_p4=len(ids), ncohort_proposed=int(mask.sum()),
        nexcluded_proposed=len(exclude_ids), conservation_identity="Ninput_P4 = Ncohort_proposed + Nexcluded_proposed",
        excluded_ids=sorted(exclude_ids), skill_width=230, columns_unchanged=True,
        source_counts={source: dict(before=sources.count(source), after=int(sum(keep and value == source for keep, value in zip(mask, sources, strict=True)))) for source in sorted(set(sources))},
        skill_frequency_reductions=reduced, new_zero_columns=[skill_items[i]["column"] for i in range(230) if before[i] > 0 and after[i] == 0],
        autocad_jobs=dict(before=int(before[auto]), after=int(after[auto])),
        job_coverage=dict(before=dict(numerator=int(matrix.any(axis=1).sum()), denominator=len(ids)),
                          after=dict(numerator=int(matrix[mask].any(axis=1).sum()), denominator=int(mask.sum()))),
        sparsity=dict(before=1-float(matrix.mean()), after=1-float(matrix[mask].mean()) if mask.any() else None),
        artifacts_requiring_recompute=["features", "C", "Golden", "TF-IDF fit/rows/vocabulary/IDF", "sidecars", "dictionary/province cohort counts", "manifest", "cohort EDA"],
        canonical_artifacts_modified=False, decisions_approved=False)


def protected_paths():
    roots = [ROOT / "data/preprocessing/05_encoding", ROOT / "reports/preprocessing/05_encoding/p5_2026-11-09_frozen_v2",
             ROOT / "reports/preprocessing/05_encoding/snapshot_audit_2026-11-08",
             ROOT / "reports/preprocessing/05_encoding/approval_package_v1", ROOT / "reports/preprocessing/05_encoding/approval_package_v2"]
    paths = [path for root in roots for path in root.rglob("*") if path.is_file()]
    paths += [ROOT / "data/curated/curated_flat_golden_jobs.parquet"]
    paths += [ROOT / "reports/preprocessing/05_encoding/review_2026-11-08" / name for name in ["candidate_generated.csv", "candidate_decisions.csv"]]
    return {str(path.relative_to(ROOT)): sha(path) for path in paths}


def build(output, annotations):
    output = Path(output)
    if output.exists():
        raise FileExistsError("Preserve existing scope review; choose a new run path")
    before = protected_paths()
    manifest_path = ROOT / "reports/preprocessing/05_encoding/snapshot_audit_2026-11-08/manifest.json"
    _, df, _ = load_snapshot(manifest_path)
    rows = df.to_dict("records")
    by_id = {row["job_id_global"]: row for row in rows}
    seeds = {row["job_id_global"] for row in rows if any(value.casefold() == "autocad" for value in row["skills_std"])}
    if len(seeds) != 36:
        raise ValueError("AutoCAD seed changed from verified snapshot")
    queue, hits = scan_queue(rows, seeds)
    annotations_path = Path(annotations) if annotations else Path(scope_review_annotations.__file__)
    proposals = json.loads(annotations_path.read_text()) if annotations else scope_review_annotations.proposals()
    if len({item["job_id_global"] for item in proposals}) != len(proposals):
        raise ValueError("Duplicate proposed decision")
    proposal_ids = {item["job_id_global"] for item in proposals}
    if not seeds <= proposal_ids or not proposal_ids <= {item["job_id_global"] for item in queue}:
        raise ValueError("Review must cover36 seeds and only queued IDs")
    evidence, decisions, family_proposals = [], [], []
    for item in proposals:
        row = by_id[item["job_id_global"]]
        if item["proposed_decision"] not in {"exclude_proposed", "retain_proposed", "unresolved"}:
            raise ValueError("Invalid proposed decision")
        if item["evidence_quote"] not in row[item["evidence_field"]]:
            raise ValueError(f"Quote not found: {item['job_id_global']}")
        text_hashes = {field: hashlib.sha256(str(row.get(field) or "").encode()).hexdigest()
                       for field in ["description_clean", "requirements_clean", "raw_description_text", "raw_requirements_text"]}
        evidence.append(dict(job_id_global=row["job_id_global"], full_available_fields_reviewed=["job_title", "description_clean", "requirements_clean", "skills_std", "raw_category_text", "it_rule", "job_family"],
                             field_sha256=text_hashes,
                             raw_clean_content_equivalent_after_whitespace={field: re.sub(r"\s+", " ", str(row.get(field) or "")).strip() == re.sub(r"\s+", " ", str(row.get(raw) or "")).strip()
                                 for field, raw in [("description_clean", "raw_description_text"), ("requirements_clean", "raw_requirements_text")]},
                             source_contains_ellipsis=any("..." in str(row.get(field)) or "…" in str(row.get(field)) for field in ["description_clean", "requirements_clean"])))
        decisions.append(dict(**item, source=row["source_platform"], title=row["job_title"], job_family=row["job_family"],
                              decision="", review_note="Agent proposal after reading full available fields; not a Phát-approved/human gold label", autocad_seed=row["job_id_global"] in seeds))
        family_proposals.append(dict(job_id_global=row["job_id_global"], current_family=row["job_family"], proposed_family=item["proposed_family"],
                                     family_status=item["family_status"], reason=item["reason"], decision="", applied_to_P4_or_Golden=False))
    vocabulary_path = ROOT / "reports/preprocessing/05_encoding/p5_2026-11-09_frozen_v2/vocabulary_frozen.json"
    vocabulary = json.loads(vocabulary_path.read_text())
    if vocabulary["input_manifest_sha256"] != sha(manifest_path):
        raise ValueError("Frozen vocabulary refers to a different input snapshot")
    lookup = build_candidate_lookup(vocabulary["items"], expected_count=230)
    # No re-encoding: read the valid existing X, verify ordered keys and binary values.
    features = pd.read_parquet(ROOT / "data/preprocessing/05_encoding/features.parquet")
    if features.job_id_global.tolist() != df.job_id_global.tolist():
        raise ValueError("Feature IDs/order differ from snapshot")
    matrix = features[list(lookup.columns)].to_numpy()
    if matrix.dtype != np.uint8 or not np.isin(matrix, [0, 1]).all():
        raise ValueError("Existing X is invalid")
    np.testing.assert_array_equal(matrix, encode_candidate_rows(df.skills_std, lookup).matrix)
    excluded = {item["job_id_global"] for item in proposals if item["proposed_decision"] == "exclude_proposed"}
    impact = impact_preview(df.job_id_global.tolist(), matrix, df.source_platform.tolist(), vocabulary["items"], excluded)
    if protected_paths() != before:
        raise ValueError("Protected files changed during review")
    output.mkdir(parents=True)
    reviewed = {item["job_id_global"]: item for item in decisions}
    for item in queue:
        item["review_state"] = "reviewed_proposed" if item["job_id_global"] in reviewed else "not_reviewed"
        for key in ["rule_ids", "rule_evidence", "it_counter_signals"]:
            item[key] = json.dumps(item[key], ensure_ascii=False)
    pd.DataFrame(queue).to_csv(output / "scope_review_queue.csv", index=False)
    pd.DataFrame(hits).to_csv(output / "scope_rule_hits.csv", index=False)
    pd.DataFrame(decisions).to_csv(output / "scope_decisions_proposed.csv", index=False)
    pd.DataFrame(family_proposals).to_csv(output / "family_decisions_proposed.csv", index=False)
    pd.DataFrame([dict(**item, **BOUNDARY_POLICIES[item["boundary_group"]]) for item in decisions if item.get("boundary_group")]).to_csv(output / "boundary_cases.csv", index=False)
    write_json(output / "boundary_policy_options.json", BOUNDARY_POLICIES)
    write_json(output / "annotations_proposed.json", proposals)
    write_json(output / "impact_preview.json", impact)
    write_json(output / "full_text_review_log.json", evidence)
    write_json(output / "rules.json", dict(candidate_rules=RULES, it_counter_signals=IT_SIGNALS,
               semantics="candidate retrieval only; no automatic scope/family decisions"))
    # Full source texts retained in review packet; ellipses already present in the
    # snapshot cannot be reconstructed and are not presented as complete original JDs.
    packet = []
    for item in proposals:
        row = by_id[item["job_id_global"]]
        packet.append(f"# {row['job_id_global']} — {row['job_title']}\n\nfamily(source, not ground truth): {row['job_family']}\n\n"
                      f"## Full available description_clean\n{row['description_clean']}\n\n## Full available requirements_clean\n{row['requirements_clean']}\n")
    (output / "reviewed_full_texts.md").write_text("\n\n".join(packet), encoding="utf-8")
    summary = dict(snapshot_jobs=len(df), queue_jobs=len(queue), autocad_seed_jobs=len(seeds), reviewed_jobs=len(decisions),
                   not_reviewed_jobs=len(queue)-len(decisions), proposal_counts=dict(Counter(item["proposed_decision"] for item in decisions)),
                   not_reviewed_by_priority=dict(Counter(item["priority"] for item in queue if item["job_id_global"] not in reviewed)),
                   autocad_proposals=dict(Counter(item["proposed_decision"] for item in decisions if item["autocad_seed"])),
                   family_statuses=dict(Counter(item["family_status"] for item in decisions)),
                   approved_decisions=0, full_snapshot_clean=False, p5_complete=False)
    write_json(output / "summary.json", summary)
    provenance = dict(snapshot_manifest_sha256=sha(manifest_path), script_sha256=sha(Path(__file__)),
        annotations_path=str(annotations_path), annotations_sha256=sha(annotations_path), vocabulary_sha256=sha(vocabulary_path),
        rules_sha256=sha(output / "rules.json"), protected_before_after_sha256=before,
        environment=dict(python=platform.python_version(), pandas=pd.__version__, numpy=np.__version__),
        instruction_sha256=sha(Path("/home/phat/Downloads/Yêu cầu cho agent_06.md")),
        agent_proposals_not_human_approval=True, automatic_model_or_translation=False,
        canonical_artifacts_modified=False, scenarios_saved_as_dataset=False)
    write_json(output / "provenance.json", provenance)
    validate(output)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def validate(output):
    output = Path(output)
    provenance = json.loads((output / "provenance.json").read_text())
    if protected_paths() != provenance["protected_before_after_sha256"]:
        raise ValueError("Protected artifacts changed")
    queue = pd.read_csv(output / "scope_review_queue.csv", keep_default_na=False)
    decisions = pd.read_csv(output / "scope_decisions_proposed.csv", keep_default_na=False)
    assert queue.job_id_global.is_unique and decisions.job_id_global.is_unique and decisions.decision.eq("").all()
    assert set(decisions.job_id_global) <= set(queue.job_id_global)
    _, df, _ = load_snapshot(ROOT / "reports/preprocessing/05_encoding/snapshot_audit_2026-11-08/manifest.json")
    sources = df.set_index("job_id_global")
    for row in decisions.to_dict("records"):
        assert row["evidence_quote"] in sources.loc[row["job_id_global"], row["evidence_field"]]
    impact = json.loads((output / "impact_preview.json").read_text())
    assert impact["ninput_p4"] == impact["ncohort_proposed"] + impact["nexcluded_proposed"] == 5177
    assert impact["skill_width"] == 230 and not impact["canonical_artifacts_modified"]
    assert sha(Path(__file__)) == provenance["script_sha256"]
    assert sha(output / "rules.json") == provenance["rules_sha256"]
    seeds = {row.job_id_global for row in df.itertuples() if any(v.casefold() == "autocad" for v in row.skills_std)}
    assert len(seeds) == 36 and seeds <= set(decisions.job_id_global)
    expected_queue, _ = scan_queue(df.to_dict("records"), seeds)
    assert set(queue.job_id_global) == {row["job_id_global"] for row in expected_queue}
    for row in queue.to_dict("records"):
        for hit in json.loads(row["rule_evidence"]):
            if hit["field"] != "skills_std":
                text = sources.loc[row["job_id_global"], hit["field"]]
                assert text[hit["match_start"]:hit["match_end"]] == hit["match"]
                assert text[hit["excerpt_start"]:hit["excerpt_end"]] == hit["excerpt"]
    vocabulary = json.loads((ROOT / "reports/preprocessing/05_encoding/p5_2026-11-09_frozen_v2/vocabulary_frozen.json").read_text())
    columns = [item["column"] for item in vocabulary["items"]]
    features = pd.read_parquet(ROOT / "data/preprocessing/05_encoding/features.parquet")
    excluded = set(decisions.loc[decisions.proposed_decision.eq("exclude_proposed"), "job_id_global"])
    assert impact == impact_preview(df.job_id_global.tolist(), features[columns].to_numpy(), df.source_platform.tolist(), vocabulary["items"], excluded)
    write_json(output / "validation.json", dict(status="PASS_REVIEW_ONLY", decision_fields_blank=True,
                artifact_hashes_unchanged=True, queue_unique=True, all_AutoCAD_reviewed=True,
                source_quotes_valid=True, impact_not_approved=True, p5_complete=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--annotations", type=Path)
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    validate(args.output) if args.validate else build(args.output, args.annotations)
