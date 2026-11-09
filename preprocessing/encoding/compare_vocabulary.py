"""Deterministic K comparison on a checksum-verified snapshot, no production writes."""

import hashlib
import json
from collections import Counter

import pandas as pd

KS = [50, 100, 150, 200, 230, 250, 300, 400, 500]
GROUPS = [
    "Programming Languages",
    "Frameworks & Libraries",
    "Databases & Caching",
    "Cloud & DevOps",
    "Tools, Architecture & Protocols",
    "Methodologies & Soft Skills",
]


def preserve_decisions(out, values):
    """Seed once from both legacy review files, fail on contradictory edits."""
    manual = out / "candidate_decisions.csv"
    if manual.exists():
        return
    columns = ["decision", "edit_canonical", "edit_group", "review_note"]
    edits = {v: dict.fromkeys(columns, "") for v in values}
    for name in ["candidate_review_full.csv", "candidate_review_priority.csv"]:
        path = out / name
        if not path.exists():
            continue
        for row in pd.read_csv(path, keep_default_na=False).to_dict("records"):
            target = edits.setdefault(row["value"], dict.fromkeys(columns, ""))
            for c in columns:
                value = row.get(c, "")
                if target[c] and value and target[c] != value:
                    raise ValueError(f"Conflicting manual reviews: {row['value']} / {c}")
                if value:
                    target[c] = value
    pd.DataFrame([dict(value=v, **fields) for v, fields in edits.items()]).to_csv(
        manual, index=False
    )


def compare(rows, sources, scenario, group_lookup):
    counts = Counter(s for row in rows for s in row)
    ordered = sorted(counts, key=lambda s: (-counts[s], s))
    n, pairs = len(rows), sum(counts.values())

    def measure(vocab):
        hits = [len(row & vocab) for row in rows]
        return dict(
            selected=len(vocab),
            jobs_hit=sum(h > 0 for h in hits),
            jobs_denominator=n,
            job_coverage=sum(h > 0 for h in hits) / n,
            pairs_kept=sum(hits),
            pairs_denominator=pairs,
            pair_coverage=sum(hits) / pairs if pairs else None,
            sparsity=1 - sum(hits) / (n * len(vocab)) if vocab else None,
            zero_columns=sum(counts[s] == 0 for s in vocab),
        )

    comparisons, by_source = [], []
    for k in KS:
        if len(ordered) < k:
            continue
        vocab = set(ordered[:k])
        boundary = counts[ordered[k - 1]]
        row = dict(
            scenario=scenario,
            K=k,
            boundary_frequency=boundary,
            boundary_ties=sum(v == boundary for v in counts.values()),
            **measure(vocab),
        )
        groups = Counter(group_lookup.get(s, "UNCLASSIFIED") for s in vocab)
        row.update({g: groups[g] for g in [*GROUPS, "UNCLASSIFIED"]})
        comparisons.append(row)
        for src in sorted(set(sources)):
            idx = [i for i, s in enumerate(sources) if s == src]
            hit = sum(bool(rows[i] & vocab) for i in idx)
            by_source.append(
                dict(
                    scenario=scenario,
                    K=k,
                    source=src,
                    jobs_hit=hit,
                    jobs_denominator=len(idx),
                    job_coverage=hit / len(idx),
                )
            )
    thresholds = [
        dict(scenario=scenario, threshold=t, **measure({s for s in ordered if counts[s] >= t}))
        for t in [5, 10, 20]
    ]
    return comparisons, by_source, thresholds


def generate(root):
    from preprocessing.encoding.skills_taxonomy_230 import TAXONOMY_230

    snap = root / "reports/preprocessing/05_encoding/snapshot_audit_2026-11-08"
    out = root / "reports/preprocessing/05_encoding/review_2026-11-08"
    manifest = json.loads((snap / "manifest.json").read_text())
    frames = []
    for m in manifest:
        p = snap / (m["key"].split("/")[1] + ".parquet")
        assert hashlib.sha256(p.read_bytes()).hexdigest() == m["sha256"]
        frames.append(pd.read_parquet(p))
    df = pd.concat(frames, ignore_index=True)
    baseline = [set(map(str, a)) for a in df.skills_std]
    old = pd.read_csv(out / "all_candidates.csv", keep_default_na=False)
    c = Counter(s for row in baseline for s in row)
    assert dict(zip(old.value, old.jobs, strict=True)) == dict(c), (
        "Candidate CSV differs from snapshot"
    )
    priority = pd.read_csv(out / "priority_candidates.csv", keep_default_na=False)
    assert all(c[row.value] == row.jobs for row in priority.itertuples()), (
        "Priority CSV differs from snapshot"
    )
    dictionary = root / "preprocessing/dictionaries/skills.json"
    shared = json.loads(dictionary.read_text())
    # Only spelling aliases of the SAME canonical skill. Broad upstream framework
    # or technology aggregation is deliberately not repeated here.
    aliases = {name.casefold(): name for name in shared}
    mapping_source = "shared canonical case-insensitive spelling only; no new synonyms"
    (out / "canonical_spelling_mapping.json").write_text(
        json.dumps(aliases, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    canonical = [{aliases.get(s.casefold(), s) for s in row} for row in baseline]
    crosswalk = dict(
        zip(
            [
                "programming_languages",
                "frameworks_libraries",
                "databases_streaming",
                "cloud_devops_security",
                "tools_architecture_qa",
                "methodologies_softskills_data",
            ],
            GROUPS,
            strict=True,
        )
    )
    groups = {s.canonical: crosswalk[s.group] for s in TAXONOMY_230}
    tables = [[], [], []]
    for label, rows in [("baseline_skills_std", baseline), ("canonical_spelling_only", canonical)]:
        for target, values in zip(
            tables, compare(rows, df.source_platform.tolist(), label, groups), strict=True
        ):
            target.extend(values)
    for name, values in zip(
        ["k_comparison", "k_source_coverage", "threshold_comparison"], tables, strict=True
    ):
        pd.DataFrame(values).to_csv(out / f"{name}.csv", index=False)
    ktable = pd.DataFrame(tables[0])
    deltas = []
    for scenario, g in ktable.groupby("scenario"):
        g = g.set_index("K")
        for a, b in [(200, 230), (230, 250), (230, 300)]:
            deltas.append(
                dict(
                    scenario=scenario,
                    from_K=a,
                    to_K=b,
                    job_coverage_pp=100 * (g.loc[b, "job_coverage"] - g.loc[a, "job_coverage"]),
                    pair_coverage_pp=100 * (g.loc[b, "pair_coverage"] - g.loc[a, "pair_coverage"]),
                )
            )
    pd.DataFrame(deltas).to_csv(out / "k_incremental.csv", index=False)
    # Generated fields only; review decisions are deliberately not touched.
    generated = old.drop(
        columns=[x for x in ["decision", "edit_canonical", "edit_group", "review_note"] if x in old]
    )
    generated["group_proposed"] = generated.value.map(groups).fillna("")
    generated["group_status"] = "prototype_crosswalk_proposed_or_unclassified"
    generated.to_csv(out / "candidate_generated.csv", index=False)
    preserve_decisions(out, old.value)
    provenance = dict(
        snapshot_manifest_sha256=hashlib.sha256((snap / "manifest.json").read_bytes()).hexdigest(),
        dictionary_sha256=hashlib.sha256(dictionary.read_bytes()).hexdigest(),
        mapping_source=mapping_source,
        version="p5-k-analysis-v1",
        analysis_code_sha256=hashlib.sha256(
            __import__("pathlib").Path(__file__).read_bytes()
        ).hexdigest(),
        group_status="prototype_crosswalk_proposed",
        approved_vocabulary=False,
        csv_input_checked="all_candidates frequencies exactly equal snapshot job-dedup counts",
    )
    (out / "k_provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    return df, ktable, pd.DataFrame(deltas)
