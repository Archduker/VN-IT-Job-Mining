"""Read-only R2 P4 snapshot audit; isolated local artifacts, no P5 publication."""

from __future__ import annotations

import hashlib
import io
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main():
    import pandas as pd
    import pyarrow.parquet as pq
    from dotenv import load_dotenv

    from collection.common.r2_storage import get_r2_client, resolve_r2_bucket
    from preprocessing.common import SOURCES
    from preprocessing.encoding.run import compute_skill_cooccurrence, encode_dataset
    from preprocessing.encoding.skills_taxonomy_230 import ORDERED_SKILL_COLUMNS

    load_dotenv(ROOT / ".env")
    client = get_r2_client()
    bucket = resolve_r2_bucket()
    out = ROOT / "reports/preprocessing/05_encoding/snapshot_audit_2026-11-08"
    out.mkdir(parents=True, exist_ok=False)
    manifest, frames = [], []
    for source in SOURCES:
        key = f"staging/{source}/preprocessing/04_normalization.parquet"
        head = client.head_object(Bucket=bucket, Key=key)
        response = client.get_object(Bucket=bucket, Key=key, IfMatch=head["ETag"])
        body = response["Body"].read()
        assert len(body) == head["ContentLength"]
        table = pq.read_table(io.BytesIO(body))
        df = table.to_pandas()
        metadata = head.get("Metadata", {})
        assert len(df) == int(metadata["rows"])
        assert set(df.source_platform) == {source}
        (out / f"{source}.parquet").write_bytes(body)
        manifest.append(
            dict(
                key=key,
                etag=head["ETag"],
                sha256=hashlib.sha256(body).hexdigest(),
                bytes=len(body),
                rows=len(df),
                metadata={k: metadata.get(k) for k in ["step", "rows", "generated-at"]},
                schema=str(table.schema),
            )
        )
        frames.append(df)
    assert len({m["metadata"]["generated-at"] for m in manifest}) == 1
    df = pd.concat(frames, ignore_index=True)
    assert df.job_id_global.notna().all() and df.job_id_global.is_unique
    counts = Counter()
    for skills in df.skills_std:
        if isinstance(skills, (list, tuple)) or hasattr(skills, "tolist"):
            counts.update(set(map(str, skills)))
        else:
            raise ValueError("Unexpected skills_std type")
    features, dictionary, _ = encode_dataset(df)
    x = features[ORDERED_SKILL_COLUMNS]
    c = compute_skill_cooccurrence(x)
    assert len(features) == len(df)
    assert x.shape[1] == 230 and x.isin([0, 1]).all().all()
    stats = dict(
        rows=len(df),
        columns=len(df.columns),
        sources=df.source_platform.value_counts().to_dict(),
        nulls=df.isna().sum().to_dict(),
        distinct_skills=len(counts),
        frequency_thresholds={
            str(k): sum(v >= k for v in counts.values()) for k in [5, 10, 20, 50, 100]
        },
        skills_without_jobs=sum(len(s) == 0 for s in df.skills_std),
        current_prototype_zero_columns=int((x.sum() == 0).sum()),
        prototype_sparsity=float((x == 0).to_numpy().mean()),
        prototype_cooccurrence_shape=list(c.shape),
        prototype_feature_columns=len(features.columns),
        vocabulary_status="CANDIDATE_ONLY_NOT_APPROVED",
        candidate_frequency=[
            dict(skill=k, jobs=v) for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
    )
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "profiling.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {k: v for k, v in stats.items() if k not in ["nulls", "candidate_frequency"]},
            ensure_ascii=False,
        )
    )
    print("AUDIT_PATH", out)


def extended_eda():
    """Analyze the downloaded snapshot offline; no writes to pipeline outputs."""
    import numpy as np
    import pandas as pd

    from preprocessing.encoding.run import to_col_slug
    from preprocessing.encoding.skills_taxonomy_230 import SKILL_LOOKUP_MAP, TAXONOMY_230

    out = ROOT / "reports/preprocessing/05_encoding/snapshot_audit_2026-11-08"
    manifest = json.loads((out / "manifest.json").read_text())
    frames = []
    for entry in manifest:
        p = out / (entry["key"].split("/")[1] + ".parquet")
        assert hashlib.sha256(p.read_bytes()).hexdigest() == entry["sha256"]
        frames.append(pd.read_parquet(p))
    df = pd.concat(frames, ignore_index=True)
    rows = []
    for skills in df.skills_std:
        rows.append(sorted(set(map(str, skills))))
    n = np.array(list(map(len, rows)))
    pairs = [(i, s) for i, skills in enumerate(rows) for s in skills]
    long = pd.DataFrame(pairs, columns=["row", "skill"])
    raw_counts = long.skill.value_counts()
    counts = pd.Series(dict(sorted(raw_counts.items(), key=lambda kv: (-kv[1], kv[0]))))
    top = list(counts.head(20).index)
    breakdown = {}
    for field in ["job_family", "seniority", "source_platform"]:
        enriched = long.assign(label=long["row"].map(df[field]).fillna("(missing)"))
        ct = pd.crosstab(enriched.label, enriched.skill).reindex(columns=top, fill_value=0)
        denominators = df[field].fillna("(missing)").value_counts()
        breakdown[field] = dict(
            counts=ct.to_dict(), conditional_rates=ct.div(denominators, axis=0).to_dict()
        )
    group_lookup = {s.slug: s.group for s in TAXONOMY_230}
    group_counts = Counter()
    unmatched = 0
    for skill, frequency in counts.items():
        slug = SKILL_LOOKUP_MAP.get(skill.lower()) or SKILL_LOOKUP_MAP.get(to_col_slug(skill))
        if slug in group_lookup:
            group_counts[group_lookup[slug]] += int(frequency)
        else:
            unmatched += int(frequency)
    result = dict(
        jobs_with_skills=int((n > 0).sum()),
        coverage=float((n > 0).mean()),
        skill_count_summary=dict(
            min=int(n.min()), max=int(n.max()), mean=float(n.mean()), median=float(np.median(n))
        ),
        raw_top230_retention=float(counts.head(230).sum() / counts.sum()),
        raw_rank230=dict(skill=str(counts.index[229]), jobs=int(counts.iloc[229])),
        prototype_groups_occurrences=dict(group_counts),
        prototype_unmapped_occurrences=unmatched,
        group_status="PROTOTYPE_MAPPING_NOT_APPROVED_TAXONOMY",
        relationships=breakdown,
        invalid_experience_range=int((df.exp_min_years > df.exp_max_years).sum()),
        invalid_date_order=int(
            (
                pd.to_datetime(df.deadline_date, errors="coerce")
                < pd.to_datetime(df.posted_date, errors="coerce")
            ).sum()
        ),
    )
    (out / "eda_relationships.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in result.items() if k != "relationships"}, ensure_ascii=False))


if __name__ == "__main__":
    if "--offline-eda" in sys.argv:
        extended_eda()
    else:
        main()
