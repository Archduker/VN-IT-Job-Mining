"""Validate the normalized Parquet emitted by the consolidated pipeline."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

REQUIRED_FEATURES = {
    "salary_min", "salary_max", "salary_avg", "is_negotiable", "exp_min_years",
    "exp_max_years", "seniority_level", "city_normalized", "job_family", "skills_extracted",
}


def validate_normalized_parquet(path: str | Path) -> dict[str, object]:
    import pandas as pd
    target = Path(path)
    if not target.is_file():
        raise FileNotFoundError(f"Normalized Parquet not found: {target}. Run run_transformation.py first.")
    frame = pd.read_parquet(target)
    missing = REQUIRED_FEATURES - set(frame.columns)
    if missing:
        raise ValueError(f"Missing required feature columns: {sorted(missing)}")
    return {
        "output_path": str(target), "rows": int(len(frame)), "required_features_present": True,
        "negotiable_rows": int(frame["is_negotiable"].fillna(False).sum()),
        "unknown_seniority_rows": int((frame["seniority_level"] == -1).sum()),
        "unmapped_location_rows": int(frame["city_normalized"].isna().sum()),
        "unclassified_family_rows": int(frame["job_family"].isna().sum()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate normalized feature Parquet")
    parser.add_argument("--input", default="data/preprocessing/04_normalization/all.parquet")
    args = parser.parse_args()
    for key, value in validate_normalized_parquet(args.input).items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
