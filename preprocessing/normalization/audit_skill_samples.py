"""Print a reproducible sample of JD skill extractions for manual review."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from preprocessing.normalization.skill_normalizer import extract_skills  # noqa: E402


def _first_existing(frame: Any, candidates: tuple[str, ...]) -> str | None:
    lookup = {str(column).casefold(): str(column) for column in frame.columns}
    return next((lookup[name.casefold()] for name in candidates if name.casefold() in lookup), None)


def audit_skill_samples(input_path: str | Path, sample_size: int = 50) -> dict[str, Any]:
    import pandas as pd

    source = Path(input_path)
    if not source.is_file():
        raise FileNotFoundError(f"Silver Parquet not found: {source}")
    frame = pd.read_parquet(source)
    title_col = _first_existing(frame, ("job_title", "title"))
    description_col = _first_existing(frame, ("raw_description_text", "job_description", "description"))
    requirements_col = _first_existing(frame, ("raw_requirements_text", "requirements", "job_requirements"))
    skills_col = _first_existing(frame, ("skills_list", "skills", "technical_skills"))
    id_col = _first_existing(frame, ("job_id_global", "source_job_id", "id"))
    source_col = _first_existing(frame, ("source_platform", "source"))

    samples = []
    for _, row in frame.iterrows():
        title = row[title_col] if title_col else ""
        description = row[description_col] if description_col else ""
        requirements = row[requirements_col] if requirements_col else ""
        skills_raw = row[skills_col] if skills_col else []
        if not any(value is not None and str(value).strip() for value in (title, description, requirements)):
            continue
        extracted = extract_skills(title, description, requirements, skills_raw)
        samples.append({
            "job_id": str(row[id_col]) if id_col and row[id_col] is not None else None,
            "source_platform": str(row[source_col]) if source_col and row[source_col] is not None else None,
            "job_title": str(title) if title is not None else "",
            "skills_extracted": extracted,
        })
        if len(samples) >= sample_size:
            break

    result = {
        "input_path": str(source),
        "requested_sample_size": sample_size,
        "sampled_rows": len(samples),
        "unique_skills_in_sample": sorted({skill for item in samples for skill in item["skills_extracted"]}),
        "samples": samples,
        "review_note": "This is an extraction sample for manual precision/false-positive review, not a measured precision score.",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit skill extraction on a sample of job descriptions")
    parser.add_argument("--input", default="data/preprocessing/02_integration/all.parquet")
    parser.add_argument("--sample-size", type=int, default=50)
    args = parser.parse_args()
    if args.sample_size < 1:
        parser.error("--sample-size must be at least 1")
    audit_skill_samples(args.input, args.sample_size)


if __name__ == "__main__":
    main()
