---
kind: configuration_system
name: Per-Source Config Modules + .env Secrets
category: configuration_system
scope:
    - '**'
source_files:
    - .env.example
    - .gitignore
    - crawlers/sources/itviec/config.py
    - crawlers/sources/itviec/crawler.py
---

## Overview

The repository uses a minimal two-tier configuration system:

1. **Per-source Python config modules** — each crawler under `crawlers/sources/<source>/config.py` exposes plain Python constants (URLs, headers, delays, retry/backoff, output paths, time zone).
2. **`.env` secrets** — AWS credentials, region, bucket name, and Telegram bot token/chat ID are loaded from an `.env` file (ignored by git) via `python-dotenv` / `os.environ` at runtime.

There is no centralized configuration loader, no YAML/JSON/TOML config files, and no feature-flag framework. Configuration is effectively "code as config" plus env-based secrets.

## Key Files

- `.env.example` — template of required environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `S3_BUCKET`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`).
- `.gitignore` — explicitly ignores `.env` and `.env.local` (lines 42–43), enforcing that secrets never enter version control.
- `crawlers/sources/itviec/config.py` — the only concrete per-source config module; defines `SOURCE`, `CRAWLER_VERSION`, `BASE_URL`, `LISTING_LOCATIONS`, `MAX_LISTING_PAGES`, `REQUEST_DELAY_MIN/MAX`, `REQUEST_TIMEOUT`, `MAX_RETRIES`, `BACKOFF_BASE`, `HEADERS`, `REPO_ROOT`, `DATA_DIR`, `ERROR_DIR`, `CHECKPOINT_FILE`, `CHECKPOINT_INTERVAL`, `DEFAULT_MAX_ITEMS`, `TZ_NAME`.
- `crawlers/sources/itviec/crawler.py` — consumes the above constants; also contains inline mock implementations of `common/http_client`, `common/checkpoint`, `common/jsonl_writer` pending the future `crawlers/common/` module described in TASKS.md.

## Architecture & Conventions

- **Constants-only config modules**: `config.py` files contain only module-level constants and comments; parsing/validation logic lives elsewhere (`parser.py`, `crawler.py`). This is documented in the docstring of `itviec/config.py`: "Chỉ chứa hằng số. Logic parse nằm ở parser.py, logic crawl nằm ở crawler.py."
- **Data contract alignment**: Comments repeatedly tie config values to `TASKS.md §4.2` (e.g., delay 2–5 s, checkpoint every 10 records, backoff base 2 s doubling). The intent is that when `crawlers/common/` is implemented, these constants will be replaced without changing crawler logic.
- **Path resolution relative to repo root**: `REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))` then `DATA_DIR = os.path.join(REPO_ROOT, "data", SOURCE)`. Output goes to `data/<source>/dt=YYYY-MM-DD/batch_NNN.jsonl`; error HTML goes to `data/<source>/errors/`.
- **Secrets via `.env`**: The example file documents the shape of secrets; `.gitignore` enforces that real `.env` files are excluded. The current crawler code does not yet read `.env` directly — it references `config.S3_*` / `config.TELEGRAM_*` placeholders intended for the future `common/s3_uploader` and `common/telegram_notifier` modules.
- **No shared config loader**: Each crawler currently owns its own `config.py`. A shared `crawlers/common/config.py` is planned but not present yet (documented in both `itviec/config.py` and `itviec/crawler.py` as a future refactor target).

## Conventions & Constraints

- **Observed conventions**:
  - Crawler-specific tuning (URLs, listing locations, pagination limits, HTTP headers, delays, retries, output directories, time zone) lives in a sibling `config.py` next to `crawler.py`.
  - All numeric tuning constants are named in `UPPER_SNAKE_CASE` and grouped by section via comment headers (`# danh tính`, `# URL nguồn`, `# HTTP`, `# checkpoint / output`, `# hành vi crawl`).
  - Timezone is configured via `TZ_NAME = "Asia/Ho_Chi_Minh"` and used through `zoneinfo.ZoneInfo` with a fallback to `timedelta(hours=7)`.
  - Checkpoint persistence uses atomic write: JSON is written to `<path>.tmp` then `os.replace()` over the original.
  - JSONL records use `ensure_ascii=False` and `os.fsync()` after each line.

- **Enforced rules**:
  - `.env` and `.env.local` are git-ignored (`.gitignore` lines 42–43); committing them would violate the ignore rule.
  - Data outputs (`*.jsonl`, `*.parquet`, `*.csv`, `data/`, `output/`, `logs/`) are git-ignored (`.gitignore` lines 29–36), so runtime data must go to S3 per the architecture docs.
  - The `itviec` crawler's HTTP client retries on status codes `429, 500, 502, 503, 504` and raises `RuntimeError` for all others (403/404 etc.), which is enforced by the `HttpClient.get` loop.
  - Retry uses exponential backoff capped at 30 s: `_backoff(attempt)` sleeps `min(BACKOFF_BASE * 2^(attempt-1), 30)`.

- **Planned but not yet implemented**:
  - A shared `crawlers/common/` package (http_client, checkpoint, jsonl_writer, schema, s3_uploader, telegram_notifier) referenced throughout comments as the future home of cross-crawler configuration and helpers.