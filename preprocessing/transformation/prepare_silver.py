"""Convert an existing integrated JSON array into the Silver Parquet contract.

This is a format bridge only: it does not scrape, filter, deduplicate or impute.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_records(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        records = next((payload[key] for key in ("jobs", "records", "data", "items", "results")
                        if isinstance(payload.get(key), list)), None)
        if records is None:
            raise ValueError("JSON root object has no recognized records list")
    else:
        raise TypeError(f"Expected JSON list/object, got {type(payload).__name__}")
    if any(not isinstance(record, dict) for record in records):
        raise TypeError("Every integrated record must be a JSON object")
    return records


def prepare_silver(input_json: str | Path,
                   output_parquet: str | Path = "data/preprocessing/02_integration/all.parquet") -> dict[str, Any]:
    import pandas as pd
    source, target = Path(input_json), Path(output_parquet)
    if not source.is_file():
        raise FileNotFoundError(f"Integrated JSON not found: {source}")
    records = _load_records(source)
    frame = pd.DataFrame.from_records(records)
    target.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(target, index=False)
    source_counts: dict[str, int] = {}
    if "source_platform" in frame.columns:
        source_counts = {str(k): int(v) for k, v in frame["source_platform"].fillna("UNKNOWN").value_counts().items()}
    expected = {"careerviet", "glints", "itviec", "jobsgo", "topcv", "topdev", "vieclam24h", "vietnamworks"}
    return {
        "input_json": str(source), "output_parquet": str(target),
        "input_rows": len(records), "output_rows": len(frame),
        "row_count_preserved": len(records) == len(frame),
        "source_platform_counts": source_counts,
        "missing_sources_in_this_input": sorted(expected - set(source_counts)),
        "note": "Only existing records were converted. Empty source integrations are not restored by this step.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare Silver Parquet from integrated JSON")
    parser.add_argument("--input", default="data/integration/integrated_flat_all_sources.json")
    parser.add_argument("--output", default="data/preprocessing/02_integration/all.parquet")
    args = parser.parse_args()
    for key, value in prepare_silver(args.input, args.output).items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
