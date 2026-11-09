"""Read-only snapshot/source review; outputs stay in a separate candidate directory."""

# ruff: noqa: E402
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import pandas as pd

from preprocessing.encoding.compare_vocabulary import compare
from preprocessing.normalization.skill_normalizer import (
    SKILL_TAXONOMY,
    extract_skills,
    taxonomy_lookup,
    validate_taxonomy,
)
from preprocessing.normalization.text_cleaner import canonicalize_skills
from preprocessing.transformation.skill_extractor import extract_skills as old_extract


def as_list(value):
    if isinstance(value, (list, tuple)):
        return list(value)
    if hasattr(value, "tolist"):
        return value.tolist()
    return []


def text(value):
    return value if isinstance(value, str) else ""


def main():
    out = ROOT / "reports/preprocessing/05_encoding/p4_k_decision_evidence_v1"
    out.mkdir(exist_ok=False)
    snap = ROOT / "reports/preprocessing/05_encoding/snapshot_audit_2026-11-08"
    manifest = json.loads((snap / "manifest.json").read_text())
    frames = []
    for entry in manifest:
        p = snap / (entry["key"].split("/")[1] + ".parquet")
        assert hashlib.sha256(p.read_bytes()).hexdigest() == entry["sha256"]
        df = pd.read_parquet(p)
        assert len(df) == entry["rows"] and set(df.source_platform) == {entry["key"].split("/")[1]}
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    assert len(df) == 5177 and df.job_id_global.notna().all() and df.job_id_global.is_unique
    canonicals = {s["canonical"] for cat in SKILL_TAXONOMY for s in cat["skills"]}
    baseline = []
    replay = []
    newer = []
    records = []
    examples = []
    selected = [
        "TensorFlow",
        "PyTorch",
        "REST API",
        "Automation Test",
        "Automation Testing",
        "HTML/CSS",
        "Agile / Scrum",
        "Agile/Scrum",
        "C",
        "C++",
    ]
    for _, r in df.iterrows():
        original = set(map(str, as_list(r.skills_std)))
        skills = as_list(r.skills_list)
        previous = set(
            canonicalize_skills(
                old_extract(
                    skills,
                    text(r.description_clean) + " " + text(r.requirements_clean),
                    r.company_name,
                )
            )
        )
        new = set(
            extract_skills(
                r.job_title, r.raw_description_text, r.raw_requirements_text, r.skills_list
            )
        )
        assert new <= canonicals
        unmatched = [str(s) for s in skills if taxonomy_lookup(str(s)) is None]
        baseline.append(original)
        replay.append(previous)
        newer.append(new)
        records.append(
            dict(
                job_id_global=r.job_id_global,
                source=r.source_platform,
                original_metadata=json.dumps(skills, ensure_ascii=False),
                snapshot_skills_std=json.dumps(sorted(original), ensure_ascii=False),
                legacy_replay=json.dumps(sorted(previous), ensure_ascii=False),
                new_extractor=json.dumps(sorted(new), ensure_ascii=False),
                metadata_unmatched_or_ambiguous=json.dumps(unmatched, ensure_ascii=False),
                removed_names=json.dumps(sorted(original - new), ensure_ascii=False),
                added_names=json.dumps(sorted(new - original), ensure_ascii=False),
            )
        )
        for skill in selected:
            if (skill in original) != (skill in new) and sum(
                e["skill"] == skill for e in examples
            ) < 3:
                context = text(r.raw_requirements_text) + " " + text(r.raw_description_text)
                pos = context.lower().find(skill.lower())
                excerpt = (
                    context[max(0, pos - 35) : pos + len(skill) + 65]
                    if pos >= 0
                    else "Metadata/title match or differently spelled alias; no exact excerpt"
                )
                examples.append(
                    dict(
                        job_id_global=r.job_id_global,
                        skill=skill,
                        snapshot_has=skill in original,
                        new_has=skill in new,
                        context=excerpt,
                    )
                )
    pd.DataFrame(records).to_csv(out / "extractor_comparison_same_ids.csv", index=False)
    pd.DataFrame(examples).to_csv(out / "targeted_examples.csv", index=False)
    statistics = []
    for scenario, rows in [
        ("baseline_skills_std", baseline),
        ("legacy_replay_retained_clean_fields", replay),
        ("new92_retained_raw_fields", newer),
    ]:
        c = Counter(s for row in rows for s in row)
        statistics.append(
            dict(
                scenario=scenario,
                jobs_with_skills=sum(bool(s) for s in rows),
                jobs_denominator=len(df),
                distinct_values=len(c),
                pairs=sum(c.values()),
            )
        )
    crosswalk = {
        "Programming Languages": "Programming Languages",
        "Frameworks & Libraries": "Frameworks & Libraries",
        "Databases & Caching": "Databases & Caching",
        "Cloud & DevOps": "Cloud & DevOps",
        "Tools, Protocols & Architecture": "Tools, Architecture & Protocols",
        "Methodologies & Soft Skills": "Methodologies & Soft Skills",
    }
    group = {
        s["canonical"]: crosswalk[cat["name"]] for cat in SKILL_TAXONOMY for s in cat["skills"]
    }
    k, s, t = compare(baseline, df.source_platform.tolist(), "baseline_skills_std", group)
    for name, values in [
        ("baseline_k_comparison", k),
        ("baseline_source_coverage", s),
        ("baseline_thresholds", t),
    ]:
        pd.DataFrame(values).to_csv(out / f"{name}.csv", index=False)
    old = pd.read_csv(ROOT / "reports/preprocessing/05_encoding/review_2026-11-08/k_comparison.csv")
    old = old[old.scenario.eq("baseline_skills_std")].set_index("K")
    for row in k:
        assert abs(row["job_coverage"] - old.loc[row["K"], "job_coverage"]) < 1e-12
        assert abs(row["pair_coverage"] - old.loc[row["K"], "pair_coverage"]) < 1e-12
    # Case-normalization-only scenario is intentionally named as such.
    shared = json.loads((ROOT / "preprocessing/dictionaries/skills.json").read_text())
    case_lookup = {s.casefold(): s for s in shared}
    mapped = [{case_lookup.get(s.casefold(), s) for s in row} for row in baseline]
    ck, cs, ct = compare(
        mapped, df.source_platform.tolist(), "case_spelling_only_not_full_canonicalization", group
    )
    pd.DataFrame(ck).to_csv(out / "case_only_k_comparison.csv", index=False)
    pd.DataFrame(ct).to_csv(out / "case_only_thresholds.csv", index=False)
    target_counts = []
    for skill in selected:
        target_counts.append(
            dict(
                skill=skill,
                baseline_jobs=sum(skill in s for s in baseline),
                legacy_replay_jobs=sum(skill in s for s in replay),
                new92_jobs=sum(skill in s for s in newer),
            )
        )
    pd.DataFrame(target_counts).to_csv(out / "targeted_counts.csv", index=False)
    review_dir = ROOT / "reports/preprocessing/05_encoding/review_2026-11-08"
    decisions = pd.read_csv(review_dir / "candidate_decisions.csv", keep_default_na=False)
    shortlist = pd.read_csv(
        review_dir / "short_review/canonical_shortlist.csv", keep_default_na=False
    )
    summary = dict(
        head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        snapshot_sha256=hashlib.sha256((snap / "manifest.json").read_bytes()).hexdigest(),
        taxonomy_sha256=hashlib.sha256(
            (ROOT / "preprocessing/dictionaries/skills_taxonomy.json").read_bytes()
        ).hexdigest(),
        scenarios=statistics,
        legacy_replay_equal_snapshot_jobs=sum(
            a == b for a, b in zip(baseline, replay, strict=True)
        ),
        new92_upper_bound=len(canonicals),
        taxonomy_warnings=validate_taxonomy(),
        new92_status="supplemental_on_retained_P4_raw_not_verified_P2_rebuild",
        baseline_k_metrics_equal_existing=True,
        reviewed_decisions=int(decisions.decision.ne("").sum()),
        shortlist_proposed_count=len(shortlist),
        shortlist_status="proposed_not_all_semantically_validated",
        p2_p3_local_available=False,
        protected_files_sha256={
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [
                review_dir / "candidate_decisions.csv",
                review_dir / "candidate_generated.csv",
            ]
        },
    )
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def export_unreviewed():
    out = ROOT / "reports/preprocessing/05_encoding/p4_k_decision_evidence_v1"
    base = ROOT / "reports/preprocessing/05_encoding/review_2026-11-08"
    source = pd.read_csv(base / "candidate_generated.csv", keep_default_na=False)
    decisions = pd.read_csv(base / "candidate_decisions.csv", keep_default_na=False)
    joined = source.merge(decisions, on="value", validate="one_to_one")
    c = Counter(
        s
        for values in pd.read_csv(out / "extractor_comparison_same_ids.csv").snapshot_skills_std
        for s in json.loads(values)
    )
    assert dict(zip(source.value, source.jobs, strict=True)) == dict(c)
    pending = joined[joined.decision.eq("")].sort_values(["jobs", "value"], ascending=[False, True])
    pending.head(300)[
        ["value", "jobs", "canonical_proposed", "group_proposed", "issue", "decision"]
    ].to_csv(out / "unreviewed_high_frequency.csv", index=False, mode="x")
    print(
        "Manual accepted:",
        int(joined.decision.eq("accept").sum()),
        "rejected:",
        int(joined.decision.eq("reject").sum()),
        "unreviewed:",
        len(pending),
    )


if __name__ == "__main__":
    if "--unreviewed-only" in sys.argv:
        export_unreviewed()
    else:
        main()
