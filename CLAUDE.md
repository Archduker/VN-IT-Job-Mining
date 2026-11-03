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

Tests (process and folder rules in `tests/README.md`):

```bash
make test-fast                                            # unit only
make test                                                 # everything except live; network is blocked
make check                                                # test + code quality report (docs/code_quality.md) + frontend build
pytest tests/unit/test_url_ledger_dedup.py::test_name     # one test
```

Tests live in `tests/unit/`, `tests/integration/`, `tests/contract/` (crawler standards C1–C14, offline fixtures in `tests/fixtures/<source>/`), and `tests/data/`. `tests/conftest.py` marks tests by folder, blocks non-localhost network unless `@pytest.mark.live` with `--run-live`, and skips `@pytest.mark.needs_data(paths)` tests when the local `data/` or `reports/` paths are missing.

Lint: `make lint` / `make format` (ruff on `collection/` and `tests/` only). The tree currently has ~1,300 ruff findings, so check only the lines you change rather than aiming for a clean run.

Pipeline:

```bash
# Collection: --phase discover|detail|all, --source <name>|all
python run.py --source topcv --phase discover --max-pages 2 --sync-r2
python run.py --source topcv --phase detail --max-items 30 --sync-r2   # without --sync-r2 nothing reaches R2; --engine only applies to topcv
python scripts/sync_cloud_lakehouse.py --status|--download|--upload [--source topcv]
python scripts/push_raw_to_r2.py [--source topcv] [--dry-run]

# Preprocessing (reads data/<source>/raw/, so download first)
python scripts/read_eda_diagnosis.py --source topcv           # run before changing preprocessing for a source
python preprocessing/integration/run_integration.py           # flatten only -> data/integration/, reports/integration/
python scripts/run_staging_integration_pipeline.py            # full chain -> data/staging/, data/curated/, reports/<source>/
python scripts/push_integration_to_r2.py                      # pushes data/integration/ + reports/integration/ JSON only
python scripts/sync_cloud_lakehouse.py --upload               # pushes everything else in data/, including staging and curated
```

Monitoring: `./start_monitoring.sh` (or `make monitor`) checks `.env` without printing values, creates `.venv` and runs `npm ci` when needed, starts PostgreSQL through docker for the Airflow cards, then runs FastAPI on 127.0.0.1:8000 (`/docs`) and Vite on :5173, which proxies `/api` to the backend. Logs go to `logs/monitoring/`. `--check` only verifies; `--no-db` and `--no-browser` skip those steps. It never starts the Airflow scheduler, because the scheduler crawls and writes to R2. `monitoring/run_all.sh` is a wrapper for it. Frontend type-check and build: `npm run build`. There is no frontend test or lint script.

Airflow: `make setup`, `make db-up` (Postgres via docker compose), `make airflow-webserver`, `make airflow-scheduler`. Airflow is installed by `scripts/setup_airflow.sh`, not `requirements.txt`.

## Folder guides

Each code folder has its own `CLAUDE.md` with the context for that area. Read it before working there:

| Folder | Covers |
|---|---|
| `collection/CLAUDE.md` | two-phase flow, ledger lifecycle and merge rule, R2 layout, envelope and CDC, per-source pitfalls, crawler standards C1–C14 |
| `airflow/CLAUDE.md` | DAGs, operators, pools, adaptive router, `run_crawler` as an API |
| `monitoring/CLAUDE.md` | backend and frontend layout, real-numbers rule, `feature_targets.py`, UI tokens, 390px checks |
| `preprocessing/CLAUDE.md` | step boundaries, EDA-first, deliverables, open PRE items |
| `scripts/CLAUDE.md` | which scripts only read, which write locally, which write or delete on R2 |
| `tests/CLAUDE.md` | test pitfalls and how to write a contract test (process in `tests/README.md`) |
| `docs/CLAUDE.md` | map of docs and how to log a fixed bug |

Fixed bugs, with cause and fix, are in `docs/issue_log.md`; open items are in `KNOWN_ISSUED.md`.

## Architecture

Collection (`collection/`, entry point `run.py`) → R2 (`url_ledger/`, `raw/`) → preprocessing (`preprocessing/`, driver `scripts/run_staging_integration_pipeline.py`) → `data/curated/curated_flat_golden_jobs.parquet`. Airflow (`airflow/`) schedules collection. Monitoring (`monitoring/`) reads `data/`, `reports/`, R2 and Airflow.

Crawlers are two-phase and decoupled; the URL Ledger (`collection/common/url_ledger.py`, `data/<source>/url_ledger/catalog_master.json`) is the contract between Discovery (registers `PENDING` URLs) and Detail (writes a `RawJobEnvelope` and a canonical JSON hash for CDC). The ledger on R2 is the source of truth. Seven sources subclass `BaseCrawler`; Glints runs through `GlintsRawPipeline`. `run.py` dispatches through hand-written `if/elif` branches and introspects `__code__.co_varnames` for an optional `online` argument, so a new source needs a branch there plus `SOURCES` lists in `scripts/run_staging_integration_pipeline.py`, `preprocessing/integration/run_integration.py`, `scripts/read_eda_diagnosis.py`, monitoring `config.py`, and a `_flatten_<source>` in `json_flattener.py`.

**Storage is Cloudflare R2 only.** Every connection goes through `collection/common/r2_storage.get_r2_client()`; missing config raises instead of falling back to localhost. All MinIO names were renamed to R2 on 2026-11-02 (`--sync-minio` is kept as an alias of `--sync-r2`). `canonicalize_lakehouse_key` enforces the bucket layout `url_ledger/`, `raw/`, `staging/`, `curated/`.

Raw data is immutable: fixes to parsed fields belong in preprocessing, not in stored raw files.

`reports/` holds pipeline outputs (health cards, manifests, integration reports) that the monitoring pages read; it is tracked in git. Do not put ad-hoc reports there; audit output (`reports/data_audit_*`) is git-ignored.

Safety rules that apply everywhere: config lives only in `.env` and its values are never printed (compare hashes instead); any write or delete on R2 is dry-run first and needs the user's approval; never start the Airflow scheduler, because it crawls and writes to R2.

## Agent resources

`.agents/skills/` holds project playbooks for other agents (for example `crawling-architect`, `data-integration-miner`, `collection-submission`). Claude Code does not load them automatically, so read the relevant `SKILL.md` when working in that area. Per-source site analysis is in `docs/crawl/<source>.md` (the "Hiện trạng 03/11/2026" box at the top of each is current; the rest may be stale), and crawler conventions are in `docs/two_phase_r2_crawler_playbook.md`. `docs/archive/` is historical.

## Known mismatches

Trust the code over the docs on these:

- The golden file is `data/curated/curated_flat_golden_jobs.parquet`; `TASKS.md` still uses the old planned name.
- `TASKS.md` is the original plan: `master_pipeline.py` was never built (the driver is `scripts/run_staging_integration_pipeline.py`), and dedup uses Jaccard plus TF-IDF cosine rather than Jaro-Winkler.
- Airflow runs on Postgres ("Zero-SQLite Policy"), so the `airflow.db` reference in the monitoring rules is outdated.
