"""Offline reproducible P4 contract audit and deterministic skill review tables."""

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from preprocessing.encoding.run import SENIORITY_MAP
from preprocessing.encoding.skills_taxonomy_230 import TAXONOMY_230
from preprocessing.normalization.job_title import JOB_FAMILIES_12, OTHER


def main():
    root = Path(__file__).resolve().parents[2]
    snap = root / "reports/preprocessing/05_encoding/snapshot_audit_2026-11-08"
    out = root / "reports/preprocessing/05_encoding/review_2026-11-08"
    out.mkdir(exist_ok=True)
    manifest = json.loads((snap / "manifest.json").read_text())
    frames, checks, anomalies = [], [], []
    for item in manifest:
        source = item["key"].split("/")[1]
        p = snap / f"{source}.parquet"
        assert hashlib.sha256(p.read_bytes()).hexdigest() == item["sha256"]
        table = pq.read_table(p)
        df = table.to_pandas()
        assert len(df) == item["rows"]
        assert df.job_id_global.notna().all() and df.job_id_global.is_unique
        assert set(df.source_platform) == {source}
        checks.append(
            dict(
                source=source,
                rows=len(df),
                schema=[
                    dict(name=f.name, type=str(f.type), nullable=f.nullable) for f in table.schema
                ],
            )
        )
        frames.append(df)
    assert {p.name for p in snap.glob("*.parquet")} == {f"{x['source']}.parquet" for x in checks}
    df = pd.concat(frames, ignore_index=True)
    assert df.job_id_global.notna().all() and df.job_id_global.is_unique
    counts = Counter()
    sets = []
    for _, row in df.iterrows():

        def issue(field, value, reason, row=row):
            anomalies.append(
                dict(job_id_global=row.job_id_global, field=field, value=str(value), reason=reason)
            )

        for field, kind in [("skills_std", str), ("locations", dict)]:
            value = row[field]
            if not isinstance(value, (list, tuple, np.ndarray)):
                issue(field, value, "null or malformed array")
            elif any(not isinstance(v, kind) for v in value):
                issue(field, value, "wrong element type")
        skills = set(map(str, row.skills_std))
        sets.append(skills)
        counts.update(skills)
        for field, allowed in [
            ("seniority", set(SENIORITY_MAP)),
            ("job_family", set(JOB_FAMILIES_12) | {OTHER}),
        ]:
            if pd.notna(row[field]) and row[field] not in allowed:
                issue(field, row[field], "unknown label")
        for field in [
            "exp_min_years",
            "exp_max_years",
            "headcount",
            "log_salary_min",
            "log_salary_max",
        ]:
            v = row[field]
            if pd.notna(v) and (not np.isfinite(v) or v < 0):
                issue(field, v, "negative or nonfinite")
        for field in [
            "is_negotiable",
            "is_outlier_salary",
            "seniority_can_kiem",
            "job_family_can_kiem",
        ]:
            if row[field] not in [True, False, 0, 1]:
                issue(field, row[field], "invalid or missing flag")
        if row.exp_min_years > row.exp_max_years:
            issue("experience_range", (row.exp_min_years, row.exp_max_years), "min > max")
        if pd.to_datetime(row.deadline_date, errors="coerce") < pd.to_datetime(
            row.posted_date, errors="coerce"
        ):
            issue("date_range", (row.posted_date, row.deadline_date), "deadline before posting")
    shared = json.loads((root / "preprocessing/dictionaries/skills.json").read_text())
    lookup = {k.lower(): k for k in shared}
    for k, aliases in shared.items():
        for alias in aliases:
            lookup[alias.lower()] = k
    prototype = {s.canonical.lower(): s for s in TAXONOMY_230}
    ordered = sorted(counts, key=lambda s: (-counts[s], s))
    boundary = counts[ordered[229]]
    candidates = []
    for rank, s in enumerate(ordered, 1):
        canonical = lookup.get(s.lower())
        proposed = prototype.get(s.lower())
        candidates.append(
            dict(
                rank=rank,
                value=s,
                jobs=counts[s],
                job_rate=counts[s] / len(df),
                canonical_proposed=canonical or "",
                group_proposed=proposed.group if proposed else "",
                issue="upstream_grouped"
                if s == "Machine Learning"
                else ("alias" if canonical and canonical != s else "unclassified"),
                evidence="shared dictionary exact/alias" if canonical else "observed P4 value only",
                status="verified_mapping_only" if canonical else "unresolved",
                group_status="prototype_proposed" if proposed else "unresolved",
            )
        )

    def write_csv(name, rows):
        if not rows:
            return
        with (out / name).open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)

    write_csv("all_candidates.csv", candidates)
    write_csv(
        "priority_candidates.csv",
        [r for r in candidates if r["rank"] <= 300 or r["jobs"] == boundary],
    )
    write_csv("duy_anomalies.csv", anomalies)
    upstream = {}
    for term in ["tensorflow", "pytorch"]:
        upstream[term] = {
            field: int(df[field].apply(lambda v, term=term: term in str(v).lower()).sum())
            for field in [
                "skills_list",
                "raw_description_text",
                "raw_requirements_text",
                "skills_std",
            ]
        }
    metrics = {}
    for name, vocab in [
        ("raw_top230", set(ordered[:230])),
        ("prototype_canonical_exact", set(s.canonical for s in TAXONOMY_230)),
    ]:
        hits = [len(s & vocab) for s in sets]
        total = sum(hits)
        metrics[name] = dict(
            jobs_with_any_candidate=sum(h > 0 for h in hits),
            jobs_denominator=len(df),
            job_skill_pairs_retained=total,
            pairs_denominator=sum(counts.values()),
            sparsity=1 - total / (len(df) * len(vocab)),
            zero_columns=sum(counts[s] == 0 for s in vocab),
            status="UNAPPROVED_EXACT_MATCH_EXPERIMENT",
        )
    (out / "validation.json").write_text(
        json.dumps(
            dict(
                partitions=checks,
                schema_equal=all(c["schema"] == checks[0]["schema"] for c in checks),
                rows=len(df),
                nulls=df.isna().sum().to_dict(),
                empty_arrays={
                    f: int(df[f].apply(len).eq(0).sum()) for f in ["skills_std", "locations"]
                },
                anomalies=len(anomalies),
                snapshot_team_approval="NO_EVIDENCE",
                upstream_details=upstream,
                metrics=metrics,
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print("review", out, "rows", len(df), "anomalies", len(anomalies))


if __name__ == "__main__":
    main()
