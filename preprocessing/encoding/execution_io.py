"""Offline, lossless P4 loading and versioned P5 run inputs."""

import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from preprocessing.common import SOURCES
from preprocessing.encoding.candidate_lookup import build_candidate_lookup
from preprocessing.encoding.run import to_col_slug

# Historical symbol provenance in the frozen JSON remains unchanged.
COMMON_JD_STOPWORDS = [
    # Tiếng Việt
    "và",
    "của",
    "các",
    "có",
    "cho",
    "với",
    "được",
    "trong",
    "để",
    "về",
    "người",
    "khi",
    "làm",
    "việc",
    "công",
    "ty",
    "tại",
    "theo",
    "yêu",
    "cầu",
    "kinh",
    "nghiệm",
    "vị",
    "trí",
    "nhân",
    "viên",
    "mức",
    "lương",
    "chế",
    "độ",
    "quyền",
    "lợi",
    "ứng",
    "viên",
    "tham",
    "gia",
    "phát",
    "triển",
    "thực",
    "hiện",
    "tốt",
    "năng",
    "lực",
    "khả",
    "năng",
    "năm",
    "tháng",
    "ngày",
    "chúng",
    "tôi",
    "mô",
    "tả",
    "chi",
    "tiết",
    "hồ",
    "sơ",
    "liên",
    "hệ",
    "tuyển",
    "dụng",
    # Tiếng Anh
    "and",
    "the",
    "to",
    "of",
    "in",
    "for",
    "with",
    "is",
    "a",
    "an",
    "as",
    "at",
    "be",
    "by",
    "on",
    "are",
    "from",
    "you",
    "will",
    "our",
    "we",
    "team",
    "company",
    "work",
    "experience",
    "job",
    "description",
    "requirements",
    "benefits",
    "skills",
    "candidate",
    "position",
    "years",
]


NUMERIC = ["log_salary_min", "log_salary_max", "exp_min_years", "exp_max_years", "headcount"]
BOOLEANS = ["is_negotiable", "is_outlier_salary", "seniority_can_kiem", "job_family_can_kiem"]
REQUIRED = ["job_id_global", "source_platform", "skills_std", "locations", "seniority", "job_family",
            "raw_employment_type", "posted_date", "deadline_date", "description_clean", "requirements_clean",
            "it_rule_level", *NUMERIC, *BOOLEANS]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


def write_json(path, value):
    Path(path).write_bytes(json_bytes(value))


def ordered_ids_hash(ids):
    return hashlib.sha256(json_bytes(list(ids))).hexdigest()


def validate_frame(df):
    missing = set(REQUIRED) - set(df)
    if missing:
        raise ValueError(f"Missing P4 fields: {sorted(missing)}")
    ids = df.job_id_global
    if not ids.map(lambda v: isinstance(v, str) and bool(v.strip())).all() or not ids.is_unique:
        raise ValueError("P4 IDs must be nonempty unique strings")
    if not df.source_platform.isin(SOURCES).all():
        raise ValueError("Unknown source_platform")
    if "employment_type" in df:
        for raw, other in zip(df.raw_employment_type, df.employment_type, strict=True):
            if not (is_null(raw) and is_null(other)) and raw != other:
                raise ValueError("Employment conflict: raw_employment_type != employment_type")
    for field, kind in [("skills_std", str), ("locations", dict)]:
        for values in df[field]:
            if not is_null(values) and (not isinstance(values, (list, tuple, np.ndarray)) or
                                        any(not isinstance(v, kind) for v in values)):
                raise ValueError(f"Malformed array in {field}")
    for field in ["description_clean", "requirements_clean", "seniority", "job_family", "raw_employment_type"]:
        if any(not is_null(v) and not isinstance(v, str) for v in df[field]):
            raise ValueError(f"Malformed string field: {field}")
    for field in NUMERIC:
        if any(not is_null(v) and (not isinstance(v, (int, float, np.number)) or not np.isfinite(v)) for v in df[field]):
            raise ValueError(f"Malformed numeric field: {field}")
    for field in BOOLEANS:
        if any(not is_null(v) and not isinstance(v, (bool, np.bool_)) for v in df[field]):
            raise ValueError(f"Malformed boolean field: {field}")


def is_null(value):
    return value is None or (isinstance(value, (float, np.floating)) and np.isnan(value))


def load_snapshot(manifest_path):
    path = Path(manifest_path)
    entries = json.loads(path.read_text())
    if not isinstance(entries, list) or not entries:
        raise ValueError("Input manifest must list partitions")
    tables, sources = [], []
    for entry in entries:
        source = entry["key"].split("/")[1]
        file = path.parent / f"{source}.parquet"
        if sha(file) != entry["sha256"]:
            raise ValueError(f"Input checksum mismatch: {source}")
        table = pq.read_table(file)
        if table.num_rows != entry["rows"] or str(table.schema) != entry["schema"]:
            raise ValueError(f"Input rows/schema mismatch: {source}")
        if set(table["source_platform"].to_pylist()) != {source}:
            raise ValueError(f"Partition source mismatch: {source}")
        if tables and table.column_names != tables[0].column_names:
            raise ValueError("Partition field names/order differ")
        tables.append(table)
        sources.append(source)
    if len(sources) != len(set(sources)) or set(sources) != set(SOURCES):
        raise ValueError("Input must include each of eight sources once")
    # Arrow's default unification permits null -> known type, not lossy coercion.
    schema = pa.unify_schemas([t.schema for t in tables]).remove_metadata()
    cast_tables = []
    for table in tables:
        arrays = [table[field.name] if table[field.name].type == field.type else
                  pa.chunked_array([pa.array(table[field.name].to_pylist(), type=field.type)], type=field.type)
                  for field in schema]
        cast = pa.Table.from_arrays(arrays, schema=schema)
        if table.to_pylist() != cast.to_pylist():
            raise ValueError("Schema union changed source values")
        cast_tables.append(cast)
    merged = pa.concat_tables(cast_tables)
    df = merged.to_pandas()
    validate_frame(df)
    return merged, df, entries


def freeze_vocabulary(v2_path, decision_path, destination):
    original = json.loads(Path(v2_path).read_text())
    frozen = copy.deepcopy(original)
    found = 0
    for item in frozen["items"]:
        if item["canonical"] == "Oracle":
            item["canonical"] = "Oracle Database"
            item["aliases"] = [a for a in item["aliases"] if a.casefold() not in {"oracle", "oracle database"}]
            item["column"] = f"skill_{to_col_slug(item['canonical'])}"
            item["reason"] = "Database product only; bare Oracle is outside this owner. Authorized by agent_05 §1."
            found += 1
        item["status"] = "authorized_for_this_run"
    if found != 1:
        raise ValueError("Expected exactly one Oracle proposal to correct")
    build_candidate_lookup(frozen["items"], expected_count=230)
    frozen.update(version="p5-v2-oracle-database-2026-11-09", status="frozen_authorized_for_run",
                  parent_vocabulary_sha256=sha(v2_path), decision_reference=dict(
                      file=Path(decision_path).name, sha256=sha(decision_path), sections="approved decisions; §1–§10"))
    data = json_bytes(frozen)
    dest = Path(destination)
    if dest.exists() and dest.read_bytes() != data:
        raise FileExistsError("Refuse to overwrite a different frozen vocabulary")
    if not dest.exists():
        dest.write_bytes(data)
    return frozen


def freeze_stopwords(destination):
    payload = dict(version="jd-stopwords-v1", words=sorted(set(COMMON_JD_STOPWORDS)),
                   source="preprocessing.encoding.tfidf_extractor.COMMON_JD_STOPWORDS", modified_words=False)
    path = Path(destination)
    if path.exists() and path.read_bytes() != json_bytes(payload):
        raise ValueError("Frozen stopword asset differs")
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(json_bytes(payload))
    return payload
