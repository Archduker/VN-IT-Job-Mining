# ============================================================
# VN IT Job Mining — Makefile
# Usage: make <target>
# ============================================================

PROJECT_ROOT := $(shell pwd)
VENV         := $(PROJECT_ROOT)/.venv
PYTHON       := $(VENV)/bin/python
PIP          := $(VENV)/bin/pip
PYTEST       := $(VENV)/bin/pytest
AIRFLOW      := $(VENV)/bin/airflow
AIRFLOW_HOME := $(PROJECT_ROOT)/airflow

export AIRFLOW_HOME

.PHONY: help setup install install-dev test test-cov test-ledger lint format \
        db-up db-down check-r2 check-env \
        airflow-webserver airflow-scheduler airflow-stop \
        discover-topcv crawl-topcv discover-topdev crawl-topdev \
        crawl-topdev crawl-careerviet crawl-itviec crawl-vietnamworks \
        crawl-vieclam24h crawl-topcv \
        clean clean-data

# ── Default: show help ─────────────────────────────────────────
help:
	@echo ""
	@echo "  VN IT Job Mining — Available Commands"
	@echo "  ========================================"
	@echo ""
	@echo "  Setup & Environment:"
	@echo "    make setup              Full setup: venv + Airflow install"
	@echo "    make install            Install runtime deps (pandas, duckdb, minio...)"
	@echo "    make install-dev        Install runtime + dev deps"
	@echo "    make check-env          Verify environment & MinIO connection"
	@echo ""
	@echo "  MinIO Lakehouse:"
	@echo "    make minio-up           Start local MinIO server (Docker) + auto-init bucket"
	@echo "    make minio-down         Stop MinIO container"
	@echo "    make setup-minio        Verify/Create vn-it-jobs bucket via python script"
	@echo ""
	@echo "  Testing:"
	@echo "    make test               Run all unit tests"
	@echo "    make test-ledger        Run URL ledger & 21-day recrawl tests"
	@echo "    make test-cov           Run tests with coverage report"
	@echo ""
	@echo "  Code Quality:"
	@echo "    make lint               Run ruff linter"
	@echo "    make format             Auto-format with ruff"
	@echo ""
	@echo "  Airflow:"
	@echo "    make airflow-webserver  Start Airflow web UI (port 8080)"
	@echo "    make airflow-scheduler  Start Airflow scheduler"
	@echo ""
	@echo "  Crawling (Two-Phase):"
	@echo "    make discover-topcv     Run Phase 1: URL Discovery for TopCV"
	@echo "    make crawl-topcv        Run Phase 2: Detail Extraction for TopCV"
	@echo "    make discover-topdev    Run Phase 1: URL Discovery for TopDev"
	@echo "    make crawl-topdev       Run Phase 2: Detail Extraction for TopDev"
	@echo ""
	@echo "  Cleanup:"
	@echo "    make clean              Remove __pycache__, .pytest_cache"
	@echo "    make clean-data         Remove local data/ and logs/ dirs"
	@echo ""

# ── Setup ──────────────────────────────────────────────────────
setup:
	@echo "[setup] Running full setup..."
	@chmod +x scripts/setup_airflow.sh
	@bash scripts/setup_airflow.sh

# ── Install dependencies ───────────────────────────────────────
install:
	@test -d $(VENV) || python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo "[install] Runtime dependencies installed."

install-dev:
	@test -d $(VENV) || python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-dev.txt
	@echo "[install-dev] Dev dependencies installed."

check-env:
	@echo "Checking Python environment..."
	@$(PYTHON) --version
	@echo "Checking Cloudflare R2 Lakehouse..."
	@$(PYTHON) scripts/check_r2.py || true

# ── Database & Cloud Lakehouse (Zero-SQLite & R2 Exclusive) ─────
db-up:
	@echo "Starting PostgreSQL 16 (Zero-SQLite Policy)..."
	docker compose up -d postgres
	@echo "PostgreSQL is running on localhost:5432"

db-down:
	@echo "Stopping PostgreSQL..."
	docker compose down

check-r2:
	$(PYTHON) scripts/check_r2.py

# ── Testing ────────────────────────────────────────────────────
test:
	$(PYTEST) tests/ -v

test-ledger:
	$(PYTEST) tests/unit/test_url_ledger.py -v

test-cov:
	$(PYTEST) tests/ --cov=collection --cov-report=term-missing --cov-report=html:htmlcov

# ── Code Quality ───────────────────────────────────────────────
lint:
	$(VENV)/bin/ruff check collection/ tests/

format:
	$(VENV)/bin/ruff format collection/ tests/

# ── Airflow ────────────────────────────────────────────────────
airflow-webserver:
	@echo "[airflow] Starting webserver on http://localhost:8080 ..."
	@echo "[airflow] Press Ctrl+C to stop."
	AIRFLOW_HOME=$(AIRFLOW_HOME) $(AIRFLOW) webserver --port 8080

airflow-scheduler:
	@echo "[airflow] Starting scheduler ..."
	@echo "[airflow] Press Ctrl+C to stop."
	AIRFLOW_HOME=$(AIRFLOW_HOME) $(AIRFLOW) scheduler

# ── Crawling Commands (Two-Phase Supported) ────────────────────
discover-topcv:
	$(PYTHON) run.py --source topcv --phase discover

crawl-topcv:
	$(PYTHON) run.py --source topcv --phase detail --batch-size 50

discover-topdev:
	$(PYTHON) run.py --source topdev --phase discover

crawl-topdev:
	$(PYTHON) run.py --source topdev --phase detail --batch-size 50

crawl-careerviet:
	$(PYTHON) run.py --source careerviet --phase all

crawl-itviec:
	$(PYTHON) run.py --source itviec --phase all

crawl-vietnamworks:
	$(PYTHON) run.py --source vietnamworks --phase all

crawl-vieclam24h:
	$(PYTHON) run.py --source vieclam24h --phase all

crawl-glints:
	$(PYTHON) run.py --source glints --phase all

# ── Cleanup ────────────────────────────────────────────────────
clean:
	@find . -type d -name "__pycache__" -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
	@echo "[clean] Cleaned cache directories."

clean-data:
	@echo "[WARNING] This will delete all local crawl data in data/ and logs/!"
	@read -p "Are you sure? (y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	@rm -rf data/ logs/
	@echo "[clean-data] data/ and logs/ removed."
