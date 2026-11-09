# Duy — Transformation & Normalization overlay

This overlay is built against the code snapshot from the user's `main` review and the Duy task handbook. It changes/adds files only inside:

- `preprocessing/transformation/`
- `preprocessing/normalization/`
- `preprocessing/dictionaries/`

## Included changes

### Transformation

- `salary_parser.py`: accepts plain strings, numeric values, dictionaries, and Python/JSON dictionary strings; uses `ast.literal_eval` (never `eval`); handles scientific notation, USD/VND, thousand/decimal separators, monthly/yearly/hourly/daily periods, open ranges, and negotiable labels. `PROJECT` compensation is marked `unsupported_period` and is not converted to monthly salary.
- `experience_parser.py`: adds `parse_experience_range` with both `exp_min_years` and `exp_max_years`; preserves `parse_experience` as a backward-compatible wrapper; normalizes the Duy handbook seniority scale 0–4 and uses -1 for unknown.
- `job_family_classifier.py`: classifies the handbook's 12 families, including Embedded; Fullstack requires at least one backend and one frontend canonical skill. Generic-title taxonomy fallback requires an IT category plus at least two skills.
- `pipeline.py`: maps the real integrated field names (`raw_salary_text`, `raw_experience_text`, `raw_seniority_text`, `working_locations`, `company_address`, `raw_description_text`, `raw_requirements_text`, etc.); preserves rows and source columns; appends ten requested feature columns; writes Subset A and Subset B.
- `prepare_silver.py`: format-only conversion from the current integrated JSON array to the required Silver Parquet path. It does not deduplicate or fill missing sources.
- `run_transformation.py`: handbook-compatible entry point for the consolidated pipeline.

### Normalization

- `location_normalizer.py`: recognizes lists/dictionaries of locations, exposes per-record fallback from `working_locations` → `raw_location_text` → `company_address`, preserves multiple-province values as `Nhiều địa điểm` and handles `Remote`/`Toàn quốc`.
- `skill_normalizer.py`: keeps canonical taxonomy matching and strengthens context-aware alias matching for short/ambiguous tokens (C, R, Go, AI, REST, Spring, Node, Spark, RN, SOLID).
- `run_normalization.py`: validates the normalized Parquet produced by the consolidated pipeline.
- `audit_skill_samples.py`: prints up to 50 real JD extraction results for manual precision/false-positive review.

### Skill dictionaries

- `skills.json`: Legacy flat dictionary (Canonical -> Aliases),
  preserved for backward compatibility with existing modules.
- `skills_taxonomy.json`: Hierarchical taxonomy containing six
  categories, canonical skills, aliases and contextual rules.
  Used by the new `skill_normalizer.py`.

## Feature output columns

The output retains every Silver input column and appends:

1. `salary_min`
2. `salary_max`
3. `salary_avg`
4. `is_negotiable`
5. `exp_min_years`
6. `exp_max_years`
7. `seniority_level` (0 Intern/Fresher, 1 Junior, 2 Middle, 3 Senior, 4 Lead/Manager, -1 unknown)
8. `city_normalized`
9. `job_family`
10. `skills_extracted`

The -1 unknown seniority sentinel is explicit; it prevents unknown or generic `Nhân viên` source labels from being falsely marked Junior.

## Commands from the repository root

First, convert the **currently existing** integrated JSON into the Silver input Parquet:

```powershell
python -m preprocessing.transformation.prepare_silver
```

Optional explicit paths:

```powershell
python -m preprocessing.transformation.prepare_silver `
  --input data/integration/integrated_flat_all_sources.json `
  --output data/preprocessing/02_integration/all.parquet
```

Then run Transformation + Normalization (the codebase has one consolidated feature pipeline):

```powershell
python preprocessing/transformation/run_transformation.py
```

Print 50 real JD samples for a manual skill-extraction review:

```powershell
python preprocessing/normalization/audit_skill_samples.py --input data/preprocessing/02_integration/all.parquet --sample-size 50
```

Finally validate the produced Parquet:

```powershell
python preprocessing/normalization/run_normalization.py
```

You can also use the original module CLI:

```powershell
python -m preprocessing.transformation.pipeline --help
```

Run unit tests:

```powershell
python -m pytest preprocessing/transformation/tests/test_feature_engineering.py -v
```

Lint (requires Ruff in the project's virtual environment):

```powershell
ruff check preprocessing/transformation/ preprocessing/normalization/
```

## Important data caveats

- The user's inspected `integrated_flat_all_sources.json` contains 937 rows from Glints (5), TopDev (1), and VietnamWorks (931). Five other per-source integrated files were confirmed empty in that inspection. Conversion to Parquet will preserve only the 937 supplied rows; it does not restore the other five sources. Do not describe this as an 8-source complete dataset.
- Text saying `Thương lượng` overrides a crawler `is_negotiable: false` flag.
- Negotiable salaries have null min/max/avg. No mean/median/mode imputation is performed.
- A `PROJECT` pay period is not comparable to monthly salary without a project duration/pay frequency; it remains unsupported for Subset A and its raw input remains preserved in the master table.
- The exact five-vs-six seniority and Embedded-vs-UI/UX differences between the Duy handbook and SPEC-06 need team agreement before merge. This branch follows the Duy handbook's 5-level scale and 12-family list.
- The overlay does not edit Integration/Crawler/Deduplication modules and does not merge the old stash.
