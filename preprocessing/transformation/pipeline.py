"""Consolidated Silver -> Transformation/Normalization pipeline.

Input : data/preprocessing/02_integration/all.parquet
Output: data/preprocessing/04_normalization/all.parquet

All Silver columns are retained. Ten feature columns from Duy's handbook are
appended. Unknown seniority is -1; unknown salary/experience values remain NaN.
"""
from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from preprocessing.normalization.location_normalizer import normalize_location_from_fields
from preprocessing.normalization.skill_normalizer import extract_skills
from preprocessing.transformation.experience_parser import (
    UNKNOWN_SENIORITY,
    normalize_seniority,
    parse_experience_range,
)
from preprocessing.transformation.job_family_classifier import classify_job_family
from preprocessing.transformation.salary_parser import parse_salary


@dataclass(frozen=True)
class ColumnConfig:
    salary: tuple[str, ...] = ("raw_salary_text", "salary", "salary_raw", "raw_salary", "salary_text", "salary_range", "salary_description", "salary_info", "wage", "compensation")
    title: tuple[str, ...] = ("job_title", "title", "position", "job_name", "name")
    description: tuple[str, ...] = ("raw_description_text", "job_description", "description", "job_detail", "raw_description", "content", "detail")
    requirements: tuple[str, ...] = ("raw_requirements_text", "requirements", "requirement", "job_requirements", "qualifications", "candidate_requirements")
    experience: tuple[str, ...] = ("raw_experience_text", "experience", "experience_required", "experience_text", "exp_requirement", "required_experience", "experience_years", "exp_min_years", "min_experience_years")
    seniority: tuple[str, ...] = ("raw_seniority_text", "seniority_level_raw", "seniority_text", "seniority", "level")
    working_locations: tuple[str, ...] = ("working_locations", "work_locations", "job_locations")
    raw_location: tuple[str, ...] = ("raw_location_text", "location", "location_province", "province", "city")
    company_address: tuple[str, ...] = ("company_address", "company_location", "address")
    category: tuple[str, ...] = ("raw_category_text", "job_category", "category", "industry_category")
    skills: tuple[str, ...] = ("skills_list", "skills", "technical_skills", "skill", "skills_raw", "required_skills")


def _is_missing(value: Any) -> bool:
    if value is None or value.__class__.__name__ in {"NAType", "NaTType"}:
        return True
    if isinstance(value, float):
        return math.isnan(value)
    if isinstance(value, (str, bytes)):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    try:
        import pandas as pd
        marker = pd.isna(value)
        return bool(marker) if not hasattr(marker, "__len__") else False
    except (ImportError, TypeError, ValueError):
        return False


def _find_column(columns: Any, candidates: tuple[str, ...]) -> str | None:
    lookup = {str(column).casefold(): str(column) for column in columns}
    return next((lookup[candidate.casefold()] for candidate in candidates if candidate.casefold() in lookup), None)


def _cell(row: Any, column: str | None) -> Any:
    return row[column] if column is not None else None


def _join_context(*values: Any) -> str:
    parts: list[str] = []
    for value in values:
        if _is_missing(value):
            continue
        if isinstance(value, dict):
            value = " ".join(str(item) for item in value.values() if not _is_missing(item))
        elif isinstance(value, (list, tuple, set)):
            value = " ".join(str(item) for item in value if not _is_missing(item))
        parts.append(str(value))
    return " ".join(parts)


def transform_dataframe(dataframe: Any, column_config: ColumnConfig | None = None) -> Any:
    """Append ten normalized feature columns without dropping source records."""
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pandas is required to transform Silver DataFrame") from exc
    if not isinstance(dataframe, pd.DataFrame):
        raise TypeError("transform_dataframe expects a pandas.DataFrame")

    config = column_config or ColumnConfig()
    cols = dataframe.columns
    selected = {name: _find_column(cols, getattr(config, name)) for name in (
        "salary", "title", "description", "requirements", "experience", "seniority",
        "working_locations", "raw_location", "company_address", "category", "skills",
    )}

    values: dict[str, list[Any]] = {
        "salary_min": [], "salary_max": [], "salary_avg": [], "is_negotiable": [],
        "exp_min_years": [], "exp_max_years": [], "seniority_level": [],
        "city_normalized": [], "job_family": [], "skills_extracted": [],
    }

    for _, row in dataframe.iterrows():
        salary_result = parse_salary(_cell(row, selected["salary"]))
        values["salary_min"].append(salary_result.salary_min)
        values["salary_max"].append(salary_result.salary_max)
        values["salary_avg"].append(salary_result.salary_avg)
        values["is_negotiable"].append(salary_result.is_negotiable)

        title = _cell(row, selected["title"])
        description = _cell(row, selected["description"])
        requirements = _cell(row, selected["requirements"])
        exp_value = _cell(row, selected["experience"])
        seniority_raw = _cell(row, selected["seniority"])
        category = _cell(row, selected["category"])
        raw_skills = _cell(row, selected["skills"])

        exp_min, exp_max, _status = parse_experience_range(exp_value, requirements, description)
        values["exp_min_years"].append(exp_min)
        values["exp_max_years"].append(exp_max)
        values["seniority_level"].append(normalize_seniority(title, seniority_raw, exp_min))

        values["city_normalized"].append(normalize_location_from_fields(
            working_locations=_cell(row, selected["working_locations"]),
            raw_location_text=_cell(row, selected["raw_location"]),
            company_address=_cell(row, selected["company_address"]),
        ))

        skills = extract_skills(title, description, requirements, raw_skills)
        values["skills_extracted"].append(skills)
        values["job_family"].append(classify_job_family(
            title, skills, _join_context(description, requirements), category
        ))

    result = dataframe.copy()
    for column in ("salary_min", "salary_max", "salary_avg", "exp_min_years", "exp_max_years"):
        result[column] = pd.Series(values[column], index=result.index, dtype="float64")
    result["is_negotiable"] = pd.array(values["is_negotiable"], dtype="boolean")
    result["seniority_level"] = pd.Series(values["seniority_level"], index=result.index, dtype="int64")
    result["city_normalized"] = values["city_normalized"]
    result["job_family"] = values["job_family"]
    result["skills_extracted"] = values["skills_extracted"]
    return result


def partition_salary_subsets(dataframe: Any) -> tuple[Any, Any]:
    """Return Subset A (numeric salary only) and Subset B (all records)."""
    required = {"salary_min", "salary_max", "is_negotiable"}
    missing = required - set(dataframe.columns)
    if missing:
        raise ValueError(f"Cannot partition salary subsets; missing columns: {sorted(missing)}")
    has_numeric_salary = dataframe["salary_min"].notna() | dataframe["salary_max"].notna()
    is_negotiable = dataframe["is_negotiable"].fillna(False).astype(bool)
    return dataframe.loc[has_numeric_salary & ~is_negotiable].copy(), dataframe.copy()


def run_pipeline(input_path: str | Path = "data/preprocessing/02_integration/all.parquet",
                 output_path: str | Path = "data/preprocessing/04_normalization/all.parquet",
                 write_subsets: bool = True) -> dict[str, Any]:
    """Read Silver Parquet, append features, and persist full/stratified datasets."""
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pandas and pyarrow are required") from exc

    source, target = Path(input_path), Path(output_path)
    if not source.is_file():
        raise FileNotFoundError(f"Silver input Parquet not found: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    silver = pd.read_parquet(source)
    transformed = transform_dataframe(silver)
    if len(transformed) != len(silver):
        raise RuntimeError("Row conservation failed: input and output counts differ")
    transformed.to_parquet(target, index=False)

    subset_a, subset_b = partition_salary_subsets(transformed)
    negotiable = transformed["is_negotiable"].fillna(False).astype(bool)
    numeric_salary = transformed["salary_min"].notna() | transformed["salary_max"].notna()
    family_counts = {str(k): int(v) for k, v in transformed["job_family"].value_counts(dropna=False).items()}
    source_counts: dict[str, int] = {}
    if "source_platform" in transformed.columns:
        source_counts = {str(k): int(v) for k, v in transformed["source_platform"].fillna("UNKNOWN").value_counts().items()}

    summary: dict[str, Any] = {
        "input_path": str(source), "output_path": str(target),
        "input_rows": int(len(silver)), "output_rows": int(len(transformed)),
        "row_count_preserved": len(silver) == len(transformed),
        "negotiable_rows": int(negotiable.sum()),
        "negotiable_rate_pct": round(float(negotiable.mean() * 100), 2) if len(transformed) else 0.0,
        "numeric_salary_rows": int(numeric_salary.sum()),
        "numeric_salary_rate_pct": round(float(numeric_salary.mean() * 100), 2) if len(transformed) else 0.0,
        "salary_benchmark_rows": int(len(subset_a)), "market_skill_demand_rows": int(len(subset_b)),
        "experience_min_parsed_rows": int(transformed["exp_min_years"].notna().sum()),
        "experience_max_parsed_rows": int(transformed["exp_max_years"].notna().sum()),
        "unknown_seniority_rows": int((transformed["seniority_level"] == UNKNOWN_SENIORITY).sum()),
        "unclassified_family_rows": int(transformed["job_family"].isna().sum()),
        "unmapped_location_rows": int(transformed["city_normalized"].isna().sum()),
        "job_family_counts": family_counts, "source_platform_counts": source_counts,
    }
    if write_subsets:
        a_path, b_path = target.with_name("salary_benchmark.parquet"), target.with_name("market_skill_demand.parquet")
        subset_a.to_parquet(a_path, index=False)
        subset_b.to_parquet(b_path, index=False)
        summary.update({"salary_benchmark_path": str(a_path), "market_skill_demand_path": str(b_path)})
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="VN-IT-Job-Mining feature transformation pipeline")
    parser.add_argument("--input", default="data/preprocessing/02_integration/all.parquet")
    parser.add_argument("--output", default="data/preprocessing/04_normalization/all.parquet")
    parser.add_argument("--no-subsets", action="store_true", help="Only write all.parquet")
    args = parser.parse_args()
    summary = run_pipeline(args.input, args.output, write_subsets=not args.no_subsets)
    for key, value in summary.items():
        if isinstance(value, dict):
            print(f"{key}:")
            for child_key, child_value in value.items():
                print(f"  {child_key}: {child_value}")
        else:
            print(f"{key}: {value}")


if __name__ == "__main__":
    main()
