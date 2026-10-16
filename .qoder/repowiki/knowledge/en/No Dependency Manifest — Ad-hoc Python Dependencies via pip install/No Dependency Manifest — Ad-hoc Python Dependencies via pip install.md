---
kind: dependency_management
name: No Dependency Manifest — Ad-hoc Python Dependencies via pip install
category: dependency_management
scope:
    - '**'
source_files:
    - docs/ec2_s3_setup_guide.md
    - .env.example
    - crawlers/sources/itviec/crawler.py
    - crawlers/sources/itviec/parser.py
    - README.md
    - crawlers/README.md
---

## What system/approach is used

This repository has **no dependency manifest or lockfile** (no `requirements.txt`, `setup.py`, `pyproject.toml`, `Pipfile`, `poetry.lock`, etc.). Third-party Python packages are installed ad-hoc by running the one-liner documented in `docs/ec2_s3_setup_guide.md`:

```
pip install requests beautifulsoup4 boto3 python-dotenv
```

The only declared runtime dependencies visible in source code are:
- `requests` — HTTP client (`crawlers/sources/itviec/crawler.py`)
- `bs4` / `BeautifulSoup` — HTML parsing (`crawlers/sources/itviec/parser.py`)
- `boto3` — AWS S3 access (documented in the EC2 setup guide)
- `python-dotenv` — `.env` loading (documented in the EC2 setup guide; `.env.example` lists `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `S3_BUCKET`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`)

All other imports in the crawler codebase are from the Python standard library (`argparse`, `json`, `logging`, `os`, `sys`, `time`, `random`, `datetime`, `hashlib`, `re`, `unittest`, `tempfile`, `zoneinfo`).

There is no vendoring, private PyPI registry, `GOPRIVATE`, or package manager configuration of any kind.

## Key files and packages

- `docs/ec2_s3_setup_guide.md` — the sole authoritative list of third-party dependencies for the project (line 122).
- `.env.example` — declares environment variables consumed at runtime; not a dependency manifest but the closest thing to a config-as-dependency boundary.
- `crawlers/sources/itviec/crawler.py` — uses `requests.Session()` for HTTP calls with retry logic.
- `crawlers/sources/itviec/parser.py` — uses `bs4.BeautifulSoup` to parse job listing HTML.
- `README.md` and `crawlers/README.md` — document that crawlers use `requests + BS4` as their stack.

## Architecture and conventions

- Each crawler lives under `crawlers/sources/<site>/` and is self-contained; there is no shared Python package or importable library between them.
- Dependencies are pinned implicitly by the one-line `pip install` command in the EC2 setup guide rather than by a lockfile — versions are whatever `pip` resolves at install time on the target machine.
- The project targets an EC2 instance (per `docs/ec2_s3_setup_guide.md`) where dependencies are installed manually before running crawlers; there is no Dockerfile, CI pipeline, or automated dependency refresh tooling in this branch.

## Conventions and constraints

- **Observed convention**: new crawler modules should rely only on `requests` and `beautifulsoup4` for network and HTML parsing, as stated in the per-source READMEs (e.g. `crawlers/sources/topcv/README.md` notes "Không dùng requests + BS4 (bị chặn 100%)" for TopCV, implying the default approach for other sites). This is a design note in documentation, not enforced by code.
- **Constraint**: secrets (`AWS_*`, `TELEGRAM_*`) must be provided via a `.env` file loaded through `python-dotenv`; `.env.example` documents the required keys and the top-level `.gitignore` prevents committing real `.env` files.
- No version pinning, no lockfile, no reproducible build — dependency versions are resolved at install time on each EC2 instance.