"""Approved E1–E8 policies for the explicit frozen-vocabulary runner."""

from collections import Counter

import numpy as np
import pandas as pd

from preprocessing.common import SOURCES
from preprocessing.encoding.candidate_lookup import build_candidate_lookup, encode_candidate_rows
from preprocessing.encoding.execution_io import BOOLEANS, NUMERIC, is_null, validate_frame
from preprocessing.encoding.run import SENIORITY_MAP, _normalize_employment_type, to_col_slug
from preprocessing.normalization.job_title import JOB_FAMILIES_12, OTHER


def build_features(df, vocabulary):
    validate_frame(df)
    lookup = build_candidate_lookup(vocabulary["items"], expected_count=230)
    enc = encode_candidate_rows(df.skills_std, lookup)
    ids = df.job_id_global.tolist()
    columns, definitions, quality = {"job_id_global": ids}, {}, []

    def add(name, values, dtype, source, formula):
        if name in columns:
            raise ValueError(f"Feature column collision: {name}")
        columns[name] = np.asarray(values, dtype=dtype)
        definitions[name] = dict(dtype=dtype, source=source, formula=formula)

    def flag(name, mask, source, reason):
        add(name, mask, "uint8", source, reason)
        for i in np.flatnonzero(np.asarray(mask)):
            quality.append(dict(job_id_global=ids[i], field=source, reason=reason, value_repr=None))

    def categorical(field, categories):
        series = df[field]
        for category in categories:
            add(f"{field}__{to_col_slug(category)}", series.eq(category), "uint8", field, f"whole label == {category}")
        flag(f"{field}__missing", series.isna(), field, "missing")
        flag(f"{field}__unknown", series.notna() & ~series.isin(categories), field, "unknown_label")

    add("seniority_ord", df.seniority.map(SENIORITY_MAP).fillna(-1), "int8", "seniority", "frozen SENIORITY_MAP; unknown=-1")
    flag("seniority__missing", df.seniority.isna(), "seniority", "missing")
    flag("seniority__unknown", df.seniority.notna() & ~df.seniority.isin(list(SENIORITY_MAP)), "seniority", "unknown_label")
    families = list(dict.fromkeys([*JOB_FAMILIES_12, OTHER]))
    categorical("job_family", families)
    categorical("source_platform", list(SOURCES))
    employment = df.raw_employment_type.map(_normalize_employment_type)
    for category in ["full_time", "part_time", "intern", "other", "missing"]:
        add(f"employment_type__{category}", employment.eq(category), "uint8", "raw_employment_type", f"legacy employment mapping == {category}")
    flag("employment_type__unknown", employment.eq("other"), "raw_employment_type", "unrecognized_employment_label")

    counts = Counter()
    for locs in df.locations:
        if not is_null(locs):
            keys = {v.get("tinh_key") for v in locs if v.get("tinh_key") is not None}
            if any(not isinstance(v, str) for v in keys):
                raise ValueError("Location province keys must be strings")
            counts.update(keys)
    provinces = sorted(counts, key=lambda v: (-counts[v], v))[:10]
    for province in provinces:
        add(f"tinh__{province}", [False if is_null(v) else any(x.get("tinh_key") == province for x in v) for v in df.locations], "uint8", "locations[].tinh_key", f"province present: {province}")
    add("tinh__other", [False if is_null(v) else any(x.get("tinh_key") is not None and x.get("tinh_key") not in provinces for x in v) for v in df.locations], "uint8", "locations[].tinh_key", "known province outside frozen top10")
    flag("locations__missing", [is_null(v) for v in df.locations], "locations", "missing")
    flag("locations__empty", [not is_null(v) and len(v) == 0 for v in df.locations], "locations", "empty_array")
    for source, target in [("remote", "is_remote"), ("ngoai_vn", "is_foreign")]:
        values, missing = [], []
        for locs in df.locations:
            raw = [] if is_null(locs) else [loc.get(source) for loc in locs]
            if any(not is_null(v) and not isinstance(v, (bool, np.bool_)) for v in raw):
                raise ValueError(f"Malformed location boolean: {source}")
            observed = [v for v in raw if not is_null(v)]
            values.append(any(observed))
            missing.append(not observed or (not any(observed) and len(observed) < len(raw)))
        add(target, values, "uint8", f"locations[].{source}", "any observed true; unknown placeholder0 with flag")
        flag(f"{target}__missing", missing, f"locations[].{source}", "unknown_boolean")

    for i, column in enumerate(lookup.columns):
        add(column, enc.matrix[:, i], "uint8", "skills_std", f"whole casefold canonical/explicit aliases owner {i}")
    flag("skills__missing", enc.missing, "skills_std", "missing")
    flag("skills__empty", [not missing and len(values) == 0 for values, missing in zip(df.skills_std, enc.missing, strict=True)], "skills_std", "empty_array")
    add("other_skills_count", [len(v) for v in enc.unmatched], "int32", "skills_std", "distinct unmatched whole-value casefold per job")
    unmatched = []
    for job_id, values, unknown in zip(ids, df.skills_std, enc.unmatched, strict=True):
        if not is_null(values):
            for original in sorted(set(values)):
                if original.casefold() in unknown:
                    unmatched.append(dict(job_id_global=job_id, original_value=original, normalized_value=original.casefold(), reason="outside_frozen_vocabulary"))
    for field in NUMERIC:
        values = pd.to_numeric(df[field], errors="raise")
        add(field, values, "float32", field, "preserve numeric values, cast float32, no imputation")
        flag(f"{field}__missing", values.isna(), field, "missing_numeric")
    flag("exp_range_invalid", df.exp_min_years.notna() & df.exp_max_years.notna() & (df.exp_min_years > df.exp_max_years), "exp_min_years/exp_max_years", "min_gt_max_source_preserved")
    for field in BOOLEANS:
        add(field, df[field].map(lambda v: 0 if is_null(v) else int(v)), "uint8", field, "unknown placeholder0; see __missing")
        flag(f"{field}__missing", df[field].isna(), field, "unknown_boolean")
    level = pd.to_numeric(df.it_rule_level, errors="coerce")
    add("it_rule_level__2", level.eq(2), "uint8", "it_rule_level", "equals2; unknown placeholder0")
    flag("it_rule_level__2__missing", ~level.isin([1, 2]), "it_rule_level", "unknown_rule_level")
    dates = {}
    for field in ["posted_date", "deadline_date"]:
        dates[field] = pd.to_datetime(df[field], errors="coerce", format="mixed")
        flag(f"{field}__invalid", df[field].notna() & dates[field].isna(), field, "unparseable_date")
    month = dates["posted_date"].dt.month
    days = (dates["deadline_date"] - dates["posted_date"]).dt.days
    flag("deadline_before_posted", days.lt(0), "posted_date/deadline_date", "deadline_before_posted")
    days = days.where(days.ge(0), np.nan)
    for name, values in [("posted_month", month), ("days_to_deadline", days)]:
        add(name, values, "float32", "posted_date/deadline_date", "month or nonnegative date difference; invalid stays NaN")
        flag(f"{name}__missing", values.isna(), "posted_date/deadline_date", f"missing_{name}")
    auto = lookup.canonical.index("AutoCAD") if "AutoCAD" in lookup.canonical else None
    flag("autocad_scope_review", np.zeros(len(df)) if auto is None else enc.matrix[:, auto], "skills_std/AutoCAD", "autocad_presence_audit_no_auto_exclusion")
    frame = pd.DataFrame(columns)
    dictionary = dict(schema_version="p5-execution-v1", vocabulary_version=vocabulary["version"],
        skill_columns=list(lookup.columns), ordered_columns=frame.columns.tolist(), features=definitions,
        skills=dict(ordered_columns=list(lookup.columns), total_encoded=230, taxonomy=vocabulary["items"]),
        seniority_mapping=SENIORITY_MAP, categories=dict(job_family=families, source_platform=list(SOURCES),
            employment_type=["full_time", "part_time", "intern", "other", "missing"]),
        employment_source="raw_employment_type", employment_mapping="preprocessing.encoding.run._normalize_employment_type",
        top_provinces=provinces, province_selection="distinct job count desc, key asc; frozen for this run",
        numeric_columns=NUMERIC, boolean_columns=BOOLEANS,
        missing_policy="source null preserved; numeric NaN+indicator; boolean placeholder0+indicator",
        metadata_not_features=["skill_type", "entity_type", "group", "scope_decision"],
        quality_columns=[c for c in frame if c not in lookup.columns and (c.endswith("missing") or c.endswith("unknown") or "invalid" in c or c in ["skills__empty", "locations__empty", "deadline_before_posted", "autocad_scope_review"])])
    return frame, dictionary, pd.DataFrame(unmatched, columns=["job_id_global", "original_value", "normalized_value", "reason"]), pd.DataFrame(quality, columns=["job_id_global", "field", "reason", "value_repr"])


def cooccurrence(frame, skill_columns):
    if len(skill_columns) != 230 or len(set(skill_columns)) != 230 or not frame[skill_columns].isin([0, 1]).all().all():
        raise ValueError("Co-occurrence requires exactly230 ordered binary skills")
    values = frame[skill_columns].to_numpy(dtype=np.int64)
    return pd.DataFrame(values.T @ values, index=skill_columns, columns=skill_columns)
