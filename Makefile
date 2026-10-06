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

.PHONY: help setup install install-dev test test-cov lint format \
        airflow-webserver airflow-scheduler airflow-stop \
        crawl-topdev crawl-careerviet crawl-itviec crawl-vietnamworks \
        clean clean-data

# ── Default: show help ─────────────────────────────────────────
help:
	@echo ""
	@echo "  VN IT Job Mining — Available Commands"
	@echo "  ========================================"
	@echo ""
	@echo "  Setup:"
	@echo "    make setup              Full setup: venv + Airflow install"
	@echo "    make install            Install runtime deps only"
	@echo "    make install-dev        Install runtime + dev deps"
	@echo ""
	@echo "  Testing:"
	@echo "    make test               Run all tests"
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
	@echo "  Crawling (manual run):"
	@echo "    make crawl-topdev       Crawl TopDev (max 450 items)"
	@echo "    make crawl-careerviet   Crawl CareerViet (max 450 items)"
	@echo "    make crawl-itviec       Crawl ITviec (max 450 items)"
	@echo "    make crawl-vietnamworks Crawl VietnamWorks (max 450 items)"
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
	$(PIP) install --quiet --upgrade pip
	$(PIP) install --quiet -r requirements.txt
	@echo "[install] Runtime dependencies installed."

install-dev:
	@test -d $(VENV) || python3 -m venv $(VENV)
	$(PIP) install --quiet --upgrade pip
	$(PIP) install --quiet -r requirements-dev.txt
	@echo "[install-dev] Dev dependencies installed."

# ── Testing ────────────────────────────────────────────────────
test:
	$(PYTEST) tests/ -v

test-cov:
	$(PYTEST) tests/ --cov=crawlers --cov-report=term-missing --cov-report=html:htmlcov

# ── Code Quality ───────────────────────────────────────────────
lint:
	$(VENV)/bin/ruff check crawlers/ tests/

format:
	$(VENV)/bin/ruff format crawlers/ tests/

# ── Airflow ────────────────────────────────────────────────────
airflow-webserver:
	@echo "[airflow] Starting webserver on http://localhost:8080 ..."
	@echo "[airflow] Press Ctrl+C to stop."
	AIRFLOW_HOME=$(AIRFLOW_HOME) $(AIRFLOW) webserver --port 8080

airflow-scheduler:
	@echo "[airflow] Starting scheduler ..."
	@echo "[airflow] Press Ctrl+C to stop."
	AIRFLOW_HOME=$(AIRFLOW_HOME) $(AIRFLOW) scheduler

# ── Manual crawl commands ──────────────────────────────────────
crawl-topdev:
	$(PYTHON) run.py --source topdev --max-items 450

crawl-careerviet:
	$(PYTHON) run.py --source careerviet --max-items 450

crawl-itviec:
	$(PYTHON) run.py --source itviec --max-items 450

crawl-vietnamworks:
	$(PYTHON) run.py --source vietnamworks --max-items 450

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
