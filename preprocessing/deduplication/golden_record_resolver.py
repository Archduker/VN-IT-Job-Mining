# -*- coding: utf-8 -*-
"""Golden Record survivorship and provenance-preserving record fusion."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from typing import Any, Dict, List, Sequence, Set, Tuple

import numpy as np
import pandas as pd

_DESCRIPTION_FIELDS = (
    "jd_clean_text",
    "job_description_raw",
    "raw_description_text",
    "description_text",
    "job_description",
    "raw_requirements_text",
    "requirements_clean_text",
    "requirements_text",
)
_SKILL_FIELDS = ("skills_list", "extracted_skills", "raw_skill_tags", "skills", "skill_tags")
_BENEFIT_FIELDS = ("benefits_list", "benefits", "benefit_tags")
_SALARY_FIELDS = (
    "raw_salary_text", "salary_raw", "salary_min_vnd", "salary_max_vnd",
    "salary_currency", "salary_source", "pay_period", "is_salary_negotiable",
)
_DERIVED_FIELDS = {
    "is_duplicate", "duplicate_count", "source_platforms", "duplicate_type",
    "duplicate_job_ids", "duplicate_member_records_json", "is_golden_record",
    "survivor_job_id", "salary_survivor_job_id", "description_survivor_job_id",
    "cluster_id",
}


def _is_missing(value: Any) -> bool:
    """Handle None, pandas nullable sentinels, NumPy NaN and empty values."""
    if value is None or value is pd.NA or value is pd.NaT:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict, np.ndarray)):
        return len(value) == 0
    try:
        result = pd.isna(value)
        if result is pd.NA:
            return True
        return bool(result) if isinstance(result, (bool, np.bool_)) else False
    except (TypeError, ValueError):
        return False


def _safe_text(value: Any) -> str:
    return "" if _is_missing(value) else str(value).strip()


def _positive_number(value: Any) -> float | None:
    if _is_missing(value) or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        # Do not infer ranges from arbitrary raw salary text in this module; numeric
        # salary parsing belongs to the Transformation step.
        return None
    if not np.isfinite(number) or number <= 0:
        return None
    return number


def _has_explicit_numeric_salary(record: Mapping[str, Any]) -> bool:
    return any(_positive_number(record.get(field)) is not None for field in ("salary_min_vnd", "salary_max_vnd"))


def _salary_rank(record: Mapping[str, Any]) -> Tuple[int, int, int, int]:
    min_salary = _positive_number(record.get("salary_min_vnd"))
    max_salary = _positive_number(record.get("salary_max_vnd"))
    positive_count = int(min_salary is not None) + int(max_salary is not None)
    raw_salary = _safe_text(record.get("raw_salary_text")) or _safe_text(record.get("salary_raw"))
    raw_has_numbers = bool(re.search(r"\d", raw_salary)) and not re.search(
        r"thỏa thuận|thuong luong|thương lượng|cạnh tranh|negotiable|undisclosed|không công khai",
        raw_salary,
        flags=re.IGNORECASE,
    )
    negotiable_flag = record.get("is_salary_negotiable")
    is_negotiable = isinstance(negotiable_flag, (bool, np.bool_)) and bool(negotiable_flag)
    return (positive_count, int(raw_has_numbers), int(not is_negotiable), int(bool(raw_salary)))


def _as_items(value: Any) -> List[Any]:
    if _is_missing(value):
        return []
    if isinstance(value, str):
        # Skill/benefit fields should be arrays by contract; this fallback keeps a
        # legacy string field as one item instead of splitting skill names arbitrarily.
        return [value]
    if isinstance(value, Mapping):
        return list(value.values())
    if isinstance(value, Iterable):
        return list(value)
    return [value]


def _merge_items(records: Sequence[Mapping[str, Any]], field: str) -> List[Any]:
    merged: List[Any] = []
    seen: Set[str] = set()
    for record in records:
        for item in _as_items(record.get(field)):
            if _is_missing(item):
                continue
            key = " ".join(str(item).split()).casefold()
            if key and key not in seen:
                seen.add(key)
                merged.append(item)
    return merged


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, (np.ndarray, tuple, set)):
        return list(value)
    if value is pd.NA:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def _record_completeness(record: Mapping[str, Any]) -> int:
    return sum(not _is_missing(value) for key, value in record.items() if key not in _DERIVED_FIELDS)


def _recency_value(record: Mapping[str, Any]) -> str:
    for field in ("scraped_at", "crawled_at", "posted_date", "raw_posted_date", "posted_at"):
        value = record.get(field)
        if not _is_missing(value):
            try:
                return pd.Timestamp(value).isoformat()
            except (TypeError, ValueError, OverflowError):
                return _safe_text(value)
    return ""


def _record_id(record: Mapping[str, Any]) -> str:
    for field in ("job_id_global", "source_job_id", "source_url", "url"):
        value = _safe_text(record.get(field))
        if value:
            return value
    return "unknown_record"


def _source_name(record: Mapping[str, Any]) -> str:
    """Read source safely even when source_platform is pandas.NA."""
    return (_safe_text(record.get("source_platform")) or _safe_text(record.get("source"))).casefold()


def _serialize_member_records(records: Sequence[Mapping[str, Any]]) -> str:
    snapshots = []
    for record in records:
        snapshots.append({key: value for key, value in record.items() if key not in _DERIVED_FIELDS})
    return json.dumps(snapshots, ensure_ascii=False, sort_keys=True, default=_json_default, separators=(",", ":"))


def resolve_golden_records(linked_df: pd.DataFrame) -> pd.DataFrame:
    """Resolve one golden row per ``cluster_id`` while preserving every member record.

    Survivorship order:
      1. Clearest explicit numeric salary (number of populated positive min/max values).
      2. Richest skills array.
      3. Longest job description.
      4. General record completeness, then latest available timestamp and stable ID.

    All list-valued columns are unioned. Description/requirements text fields keep the
    longest non-empty value independently. The full source rows are retained as JSON in
    ``duplicate_member_records_json`` so alternate values are auditable and recoverable.
    """
    if not isinstance(linked_df, pd.DataFrame):
        raise TypeError("linked_df must be a pandas DataFrame")
    if linked_df.empty:
        output = linked_df.copy()
        for column, dtype_value in (
            ("is_duplicate", pd.Series(dtype="bool")),
            ("duplicate_count", pd.Series(dtype="int64")),
            ("source_platforms", pd.Series(dtype="object")),
            ("duplicate_job_ids", pd.Series(dtype="object")),
            ("duplicate_member_records_json", pd.Series(dtype="object")),
            ("is_golden_record", pd.Series(dtype="bool")),
            ("duplicate_type", pd.Series(dtype="object")),
            ("survivor_job_id", pd.Series(dtype="object")),
            ("salary_survivor_job_id", pd.Series(dtype="object")),
            ("description_survivor_job_id", pd.Series(dtype="object")),
        ):
            if column not in output.columns:
                output[column] = dtype_value
        return output

    records = linked_df.to_dict(orient="records")
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for index, record in enumerate(records):
        cluster_value = _safe_text(record.get("cluster_id")) or f"singleton_{index:08d}"
        grouped.setdefault(cluster_value, []).append(record)

    golden_records: List[Dict[str, Any]] = []
    for cluster_id, members in grouped.items():
        # Stable tie-breaking; the configured fields follow the team's survivorship order.
        ordered = sorted(
            members,
            key=lambda row: (
                _salary_rank(row),
                max((len(_as_items(row.get(field))) for field in _SKILL_FIELDS), default=0),
                max((len(_safe_text(row.get(field))) for field in _DESCRIPTION_FIELDS), default=0),
                _record_completeness(row),
                _recency_value(row),
                _record_id(row),
            ),
            reverse=True,
        )
        winner = ordered[0]
        golden = dict(winner)
        cluster_size = len(members)
        source_platforms = list(dict.fromkeys(
            _source_name(row)
            for row in ordered
            if _source_name(row)
        ))
        duplicate_ids = list(dict.fromkeys(_record_id(row) for row in ordered if _record_id(row)))

        # Merge every list/tuple/array column across members. This includes skills,
        # benefits, raw tags and other list-valued fields supplied by source adapters.
        all_columns = list(dict.fromkeys(key for row in ordered for key in row.keys()))
        for field in all_columns:
            values = [row.get(field) for row in ordered]
            if any(isinstance(value, (list, tuple, set, np.ndarray)) for value in values if value is not None):
                golden[field] = _merge_items(ordered, field)

        # Description fields are selected separately so a long requirements field does
        # not overwrite a good description, and neither field is lost from provenance.
        for field in _DESCRIPTION_FIELDS:
            candidates = [(_safe_text(row.get(field)), row) for row in ordered]
            nonempty = [(text, row) for text, row in candidates if text]
            if nonempty:
                text, source_row = max(nonempty, key=lambda item: (len(item[0]), _record_id(item[1])))
                golden[field] = text
                if field in {"jd_clean_text", "job_description_raw", "raw_description_text", "description_text", "job_description"}:
                    golden["description_survivor_job_id"] = _record_id(source_row)

        # Salary provenance is selected as one consistent bundle, rather than taking
        # min and max from different postings. If no numeric salary exists, retain the
        # winner's original salary fields and never infer values here.
        salary_source = max(ordered, key=lambda row: (_salary_rank(row), _record_id(row)))
        if _has_explicit_numeric_salary(salary_source):
            for field in _SALARY_FIELDS:
                if field in salary_source and not _is_missing(salary_source.get(field)):
                    golden[field] = salary_source[field]
            golden["salary_survivor_job_id"] = _record_id(salary_source)
        else:
            # Fill only absent salary values, keeping the survivorship decision in the
            # Transformation domain and avoiding overwriting the original declaration.
            for field in _SALARY_FIELDS:
                if _is_missing(golden.get(field)):
                    value = next((row.get(field) for row in ordered if not _is_missing(row.get(field))), None)
                    if value is not None:
                        golden[field] = value

        # Generic scalar fill: take the first non-empty value in survivorship order;
        # never overwrite a value already selected from the strongest record.
        for field in all_columns:
            if field in _DERIVED_FIELDS or field in _DESCRIPTION_FIELDS or field in _SALARY_FIELDS:
                continue
            current = golden.get(field)
            if _is_missing(current):
                for row in ordered:
                    value = row.get(field)
                    if not _is_missing(value):
                        golden[field] = value
                        break

        golden["cluster_id"] = cluster_id
        golden["is_duplicate"] = cluster_size > 1
        golden["duplicate_count"] = cluster_size
        golden["source_platforms"] = source_platforms
        golden["duplicate_job_ids"] = duplicate_ids
        golden["duplicate_member_records_json"] = _serialize_member_records(ordered)
        golden["is_golden_record"] = True
        golden["survivor_job_id"] = _record_id(winner)
        golden_records.append(golden)

    result = pd.DataFrame(golden_records)
    # Stable output order by cluster ID makes reruns reproducible.
    if "cluster_id" in result.columns:
        result = result.sort_values("cluster_id", kind="stable").reset_index(drop=True)
    return result
