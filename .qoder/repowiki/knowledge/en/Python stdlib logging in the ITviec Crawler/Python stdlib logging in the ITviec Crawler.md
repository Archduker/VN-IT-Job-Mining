---
kind: logging_system
name: Python stdlib logging in the ITviec Crawler
category: logging_system
scope:
    - '**'
source_files:
    - crawlers/sources/itviec/crawler.py
---

## What system/approach is used

The repository uses **Python's built-in `logging` module** (no third-party logger framework). Logging is present only in the ITviec crawler (`crawlers/sources/itviec/crawler.py`); other source crawers under `crawlers/sources/` currently have no logging code.

There is no centralized logger configuration, no log rotation, no structured JSON logs, and no external sinks (file handlers, syslog, cloud log collectors). Log output goes to stderr via the default `StreamHandler` configured by `logging.basicConfig` at process entry.

## Key files and packages

- `crawlers/sources/itviec/crawler.py` — the sole file that imports `logging`, creates a logger, and emits log records.
- No dedicated `log/` or `logging/` package exists; there is no shared logging utility.

## Architecture and conventions

### Logger instance

Each module that needs logging obtains a named logger via `logging.getLogger("itviec.crawler")`. The name follows a dotted hierarchy scoped to the source (`itviec.crawler`).

### Level strategy

- Default level: `INFO`.
- Verbose mode: `DEBUG` when the CLI flag `-v` / `--verbose` is passed.
- Levels used:
  - `info`: lifecycle milestones (checkpoint load, listing progress, batch completion, successful record write).
  - `warning`: recoverable issues (network retry attempts, HTTP 429/5xx, malformed checkpoint, missing fields detected by `record_warnings`).
  - `error`: non-recoverable failures (HTTP error for a listing page, detail download failure, invalid record, parse exception).
  - `exception`: used around parser exceptions to emit the traceback plus context.

### Configuration

`main()` calls `logging.basicConfig(...)` once at startup with:

```python
format="%(asctime)s %(levelname)-7s %(name)s: %(message)s"
```

No custom formatter, handler, or filter is installed. The format includes timestamp, level name, logger name, and message.

### Message style

Messages are plain English/Vietnamese strings formatted with `%`-style placeholders (e.g. `"Lỗi mạng (lần %d/%d) %s: %s"`). There is no structured field payload attached to log records; contextual data (URL, attempt count, batch_id, path) is interpolated into the message text.

### Sinks

Only one sink: the default `StreamHandler` from `basicConfig`. There is no file handler, no rotating file, no JSON encoder, and no integration with AWS CloudWatch, ELK, or any external log aggregation service.

### Conventions observed

- Network-layer problems (requests exceptions, HTTP 429/500/502/503/504) are logged at `warning` before exponential backoff retry.
- Unrecoverable errors (non-200 status codes like 403/404, parsing failures, validation failures) are logged at `error`.
- Parse exceptions use `log.exception(...)` so the full traceback is emitted alongside the contextual message.
- Missing-but-non-fatal fields reported by `job_parser.record_warnings` are logged at `warning` rather than failing the crawl.
- Checkpoint read/write paths log warnings on malformed or unreadable checkpoints instead of aborting.
- Successful record writes include a checkmark prefix (`"✓ [%d] %s | %s"`) at `info` level.

### Constraints / rules

- Only `crawler.py` in this repo uses `logging`; other modules do not import it, so there is no cross-module logger convention to enforce beyond what is already implemented here.
- The verbose/debug toggle is exclusively controlled through the `--verbose` / `-v` argparse flag in `main()`; there is no environment variable or config-driven log level.
- Because `basicConfig` is called at process entry, re-importing the module does not reconfigure the root logger — the first invocation wins.
- No test coverage was found for the logging behavior itself.