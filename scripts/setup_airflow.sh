#!/usr/bin/env bash
# =============================================================
# Setup script: Apache Airflow LocalExecutor trên laptop
# Chạy một lần duy nhất để khởi tạo môi trường Airflow.
#
# Usage:
#   chmod +x scripts/setup_airflow.sh
#   ./scripts/setup_airflow.sh
# =============================================================
set -euo pipefail

# ── Config ────────────────────────────────────────────────────
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"
AIRFLOW_HOME="${PROJECT_ROOT}/airflow"
AIRFLOW_VERSION="2.10.4"
PYTHON_BIN="python3"

# ── Colors ────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()    { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

info "Project root: ${PROJECT_ROOT}"
info "Airflow home: ${AIRFLOW_HOME}"

# ── Step 1: Create virtual environment ───────────────────────
if [ ! -d "${VENV_DIR}" ]; then
    info "Creating virtual environment at ${VENV_DIR} ..."
    "${PYTHON_BIN}" -m venv "${VENV_DIR}"
else
    warn "Virtual environment already exists, skipping creation."
fi

# Activate venv
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
info "Python: $(python --version)"
info "pip:    $(pip --version)"

# ── Step 2: Upgrade pip ───────────────────────────────────────
info "Upgrading pip ..."
pip install --quiet --upgrade pip setuptools wheel

# ── Step 3: Install project dependencies ──────────────────────
info "Installing project dependencies ..."
pip install --quiet -r "${PROJECT_ROOT}/requirements.txt"

# ── Step 4: Install Apache Airflow ────────────────────────────
info "Installing Apache Airflow ${AIRFLOW_VERSION} ..."
# Cài không dùng constraint file vì Python 3.14 chưa có file constraint chính thức.
# Nếu cần strict constraints, dùng:
#   CONSTRAINT_URL="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-3.12.txt"
#   pip install "apache-airflow==${AIRFLOW_VERSION}" --constraint "${CONSTRAINT_URL}"
pip install --quiet "apache-airflow==${AIRFLOW_VERSION}"

# ── Step 5: Configure AIRFLOW_HOME ────────────────────────────
export AIRFLOW_HOME="${AIRFLOW_HOME}"
info "AIRFLOW_HOME set to: ${AIRFLOW_HOME}"

# ── Step 6: Create airflow.cfg override ───────────────────────
mkdir -p "${AIRFLOW_HOME}"

# Khởi tạo DB và tạo file config mặc định trước
info "Initialising Airflow database (SQLite) ..."
AIRFLOW_HOME="${AIRFLOW_HOME}" airflow db migrate 2>/dev/null || \
AIRFLOW_HOME="${AIRFLOW_HOME}" airflow db init

# Patch config: LocalExecutor + point dags_folder về project
AIRFLOW_CFG="${AIRFLOW_HOME}/airflow.cfg"
info "Patching airflow.cfg ..."

# executor
sed -i "s|^executor = .*|executor = LocalExecutor|g" "${AIRFLOW_CFG}"

# dags_folder — point tới project dags directory
sed -i "s|^dags_folder = .*|dags_folder = ${PROJECT_ROOT}/airflow/dags|g" "${AIRFLOW_CFG}"

# plugins_folder
sed -i "s|^plugins_folder = .*|plugins_folder = ${PROJECT_ROOT}/airflow/plugins|g" "${AIRFLOW_CFG}"

# base_log_folder
sed -i "s|^base_log_folder = .*|base_log_folder = ${PROJECT_ROOT}/logs/airflow|g" "${AIRFLOW_CFG}"

# Tắt example DAGs cho gọn
sed -i "s|^load_examples = .*|load_examples = False|g" "${AIRFLOW_CFG}"

# Parallelism phù hợp cho laptop
sed -i "s|^parallelism = .*|parallelism = 4|g" "${AIRFLOW_CFG}"
sed -i "s|^max_active_runs_per_dag = .*|max_active_runs_per_dag = 1|g" "${AIRFLOW_CFG}"

info "airflow.cfg patched successfully."

# ── Step 7: Create admin user ─────────────────────────────────
info "Creating admin user (username: admin / password: admin) ..."
AIRFLOW_HOME="${AIRFLOW_HOME}" airflow users create \
    --username admin \
    --firstname Admin \
    --lastname UTH \
    --role Admin \
    --email admin@uth.edu.vn \
    --password admin 2>/dev/null || warn "Admin user may already exist."

# ── Step 8: Create .env với AIRFLOW_HOME ─────────────────────
ENV_FILE="${PROJECT_ROOT}/.env"
if [ ! -f "${ENV_FILE}" ]; then
    info "Creating .env from .env.example ..."
    cp "${PROJECT_ROOT}/.env.example" "${ENV_FILE}"
fi

# Append AIRFLOW_HOME if not present
if ! grep -q "AIRFLOW_HOME" "${ENV_FILE}"; then
    echo "" >> "${ENV_FILE}"
    echo "# Airflow" >> "${ENV_FILE}"
    echo "AIRFLOW_HOME=${AIRFLOW_HOME}" >> "${ENV_FILE}"
fi

# ── Done ──────────────────────────────────────────────────────
echo ""
info "=========================================="
info "  Airflow setup complete!"
info "=========================================="
echo ""
echo "  Next steps:"
echo "  1. Activate venv:     source .venv/bin/activate"
echo "  2. Export AIRFLOW_HOME: export AIRFLOW_HOME=${AIRFLOW_HOME}"
echo "  3. Start webserver:   make airflow-webserver"
echo "  4. Start scheduler:   make airflow-scheduler"
echo "  5. Open UI:           http://localhost:8080  (admin / admin)"
echo ""
