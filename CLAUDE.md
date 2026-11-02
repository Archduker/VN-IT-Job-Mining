# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Pipeline that mines IT job postings from 8 Vietnamese job boards (topcv, topdev, vietnamworks, careerviet, vieclam24h, itviec, glints, jobsgo) into a deduplicated "Golden Master" dataset, with a monitoring dashboard on top. Docs, comments, and log messages are mostly Vietnamese. `README.md` describes the intended design and is stale in places; see "Known mismatches" below.

## Commands

Setup needs Python 3.12 (`careerviet/crawler.py` uses 3.12-only f-string syntax). Makefile targets assume the venv is at `.venv/`.

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
touch .env   # config lives only in .env; there is no .env.example
```

Tests:

```bash
pytest tests/                                       # all
pytest tests/test_url_ledger_dedup.py               # one file
pytest tests/test_cross_deduplicator.py::test_name  # one test
```

Without local `data/`, 3 tests fail: both in `tests/test_integration_step.py` and `test_crawling_enum_summary` in `tests/test_monitoring_api.py`. They need pipeline outputs, not a code fix. `test_flatten_sources_samples` passes vacuously in that state because it only checks sample files that exist.

Lint: `make lint` / `make format` (ruff on `collection/` and `tests/` only). The tree currently has ~1,300 ruff findings, so check only the lines you change rather than aiming for a clean run.

Pipeline:

```bash
# Collection: --phase discover|detail|all, --source <name>|all
python run.py --source topcv --phase discover --max-pages 2
python run.py --source topcv --phase detail --max-items 30    # --engine only applies to topcv
python scripts/sync_cloud_lakehouse.py --status|--download|--upload [--source topcv]
python scripts/push_raw_to_r2.py [--source topcv] [--dry-run]

# Preprocessing (reads data/<source>/raw/, so download first)
python scripts/read_eda_diagnosis.py --source topcv           # run before changing preprocessing for a source
python preprocessing/integration/run_integration.py           # flatten only -> data/integration/, reports/integration/
python scripts/run_staging_integration_pipeline.py            # full chain -> data/staging/, data/curated/, reports/<source>/
python scripts/push_integration_to_r2.py                      # pushes data/integration/ + reports/integration/ JSON only
python scripts/sync_cloud_lakehouse.py --upload               # pushes everything else in data/, including staging and curated
```

Monitoring: `./monitoring/run_all.sh` starts FastAPI on :8000 (`/docs`) and Vite on :5173, which proxies `/api` to the backend. It requires `.venv/` and `npm install` in `monitoring/frontend`. Frontend type-check and build: `npm run build`. There is no frontend test or lint script.

Airflow: `make setup`, `make db-up` (Postgres via docker compose), `make airflow-webserver`, `make airflow-scheduler`. Airflow is installed by `scripts/setup_airflow.sh`, not `requirements.txt`.

## Architecture

### Stage 1: Collection (`collection/`, entry point `run.py`)

Crawlers are two-phase and decoupled, and the URL Ledger is the contract between the phases:

- **Discovery** (`discover_urls`) registers canonicalized URLs as `PENDING` with no hash.
- **Detail** (`crawl_details`) processes `PENDING` first, then `DONE` records at least 21 days old (`RECHECK_DUE`). It writes a `RawJobEnvelope` (`metadata` + `raw_payload`, in `collection/common/schema.py`) and stores a canonical JSON hash for CDC. Failures on a single URL are recorded and skipped; they never abort the batch ("Safe Skip").

`collection/common/url_ledger.py` holds the lifecycle (`PENDING`, `DONE`, `RECHECK_DUE`, `FAILED`, `CLOSED`), stored at `data/<source>/url_ledger/catalog_master.json` with daily manifests. The catalog on R2 is the source of truth: crawlers pull it before detail runs and sync it back during and after them.

There are two crawler bases. Seven sources subclass `BaseCrawler` (`collection/base/base_crawler.py`) and supply the two phase methods themselves. Glints runs through `GlintsRawPipeline` (`TwoPhaseRawCrawler`). `run.py` dispatches through hand-written `if/elif` branches and introspects `__code__.co_varnames` for an optional `online` argument, so a new source needs a branch there plus `SOURCES` lists elsewhere (`scripts/run_staging_integration_pipeline.py`, `preprocessing/integration/run_integration.py`, `scripts/read_eda_diagnosis.py`, monitoring `config.py`) and a `_flatten_<source>` in `json_flattener.py`.

**"MinIO" in names means Cloudflare R2.** `minio_raw_pipeline.py`, `MinioRawStore`, and `sync_to_minio` are the live R2 implementation; `r2_raw_pipeline.py` and `minio_storage.py` are thin aliases. MinIO itself was removed, so do not add MinIO infrastructure. `canonicalize_lakehouse_key` enforces the bucket layout `url_ledger/`, `raw/`, `staging/`, `curated/` and rejects cache and checkpoint files. `MinioRawStore` checks the bucket in `__init__` and raises on bad credentials.

Raw data is immutable: fixes to parsed fields belong in preprocessing, not in stored raw files.

### Stage 2: Preprocessing (`preprocessing/`, driver `scripts/run_staging_integration_pipeline.py`)

`preprocessing/` is a library of step functions; the driver in `scripts/` runs them per source and then merges: flatten → salary cascade (header regex, JD regex, GenAI) → null detection and stub-JD removal → GenAI imputation → outlier fixes and winsorizing → normalization → cross-platform dedup. Each source produces three deliverables: `<source>_flat_clean.parquet`, `<source>_quality_health_card.json`, and `<source>_transformation_manifest.md`.

Conventions enforced by `docs/preprocessing/00_architecture_overview.md`:

- **Step boundaries are a hard contract.** Integration must not parse salaries, convert currency, drop rows, or impute. Transformation must not delete suspected outliers or fill values. Missing/Outlier must not fill with mean or median. Normalization must not scale before outlier handling. Read the matrix there before moving logic between steps.
- **EDA-first.** Rules are per-source and come from `collection/reports/EDA_<source>.ipynb`. Load them with `scripts/read_eda_diagnosis.py` rather than reading the notebooks, which embed large base64 images.
- Negotiable salaries stay `NaN` with a flag (MNAR). Outliers are capped, not dropped. GenAI-filled values are flagged (`is_imputed_by_genai`). The imputer falls back to heuristics when no API key is set.

### Orchestration (`airflow/`)

`dag_discovery_daily` runs at 05:00. Eight `crawler_detail_<source>` DAGs run route check → crawl → data quality → preprocess. `collection/common/adaptive_router.py` skips or runs each slot depending on backlog, weekday, and a 55-minute cooldown, capped at 30 items per batch. Discovery and detail share `pool_<source>` (1 slot) so the two phases of a source never overlap. Operators call `run_crawler` from `run.py` directly, so its signature is an API.

`DataPreprocessOperator` is a separate lightweight cleaner writing `data/<source>/staging/<date>/`. It does not use `preprocessing/`, and the golden dataset never comes from Airflow.

### Monitoring (`monitoring/`)

FastAPI (`backend/app`: endpoints → services) plus React/TypeScript (`frontend/src/pages`). `.agents/rules/monitoring_system_rules.md` is mandatory for work here. Key rules: no login or auth UI; operational controls live on `/crawling` and analysis charts on `/eda`, never mixed; frontend is TypeScript only with no `.js`/`.jsx` files, and types go in `types.ts`; R2 diffing uses `content_hash`, not timestamps; follow the light theme, single font, and semantic colors defined there.

The main pages are Collection (`/`) and Raw (`/raw`), served by `/api/v1/monitor` (`collection_monitor_service.py`, `source_report_service.py`). They show only real numbers and return `null` with a reason when a source is missing. Field locations per source live in `backend/app/core/feature_targets.py` and must stay in step with `json_flattener.py`. Older pages under "Công cụ khác" keep their dark-era Tailwind classes: `tailwind.config.ts` inverts the `slate` palette and remaps accent shades, so in new code use the `ink`, `line`, `panel`, `brand`, and `state` tokens, never `slate`. EDA, Pre-processing, Processing, and Master Dashboard read pipeline outputs (`reports/`, `data/staging/`) through `pipeline_report_service.py`, under the same no-invented-numbers rule; `reports/` is tracked in git, so these pages show the last committed pipeline run. ML 3D is hidden from the menu, and its endpoint still returns random points.

## Agent resources

`.agents/skills/` holds project playbooks for other agents (for example `crawling-architect`, `data-integration-miner`, `collection-submission`). Claude Code does not load them automatically, so read the relevant `SKILL.md` when working in that area. Per-source site analysis is in `docs/crawl/<source>.md`, and crawler conventions are in `docs/two_phase_r2_crawler_playbook.md`. `docs/archive/` is historical.

## Known mismatches

Trust the code over the docs on these:

- The golden file is `data/curated/curated_flat_golden_jobs.parquet`; `TASKS.md` still uses the old planned name.
- `TASKS.md` is the original plan: `master_pipeline.py` was never built (the driver is `scripts/run_staging_integration_pipeline.py`), and dedup uses Jaccard plus TF-IDF cosine rather than Jaro-Winkler.
- Airflow runs on Postgres ("Zero-SQLite Policy"), so the `airflow.db` reference in the monitoring rules is outdated.
