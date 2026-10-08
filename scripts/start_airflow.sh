#!/usr/bin/env bash
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export AIRFLOW_HOME="${PROJECT_ROOT}/airflow"
export PYTHONPATH="${PROJECT_ROOT}:${PROJECT_ROOT}/airflow/plugins"

echo "=========================================================="
echo " Starting Apache Airflow for VN-IT-Job-Mining"
echo " AIRFLOW_HOME: ${AIRFLOW_HOME}"
echo " UI Address:   http://localhost:8080"
echo " Credentials:  admin / admin"
echo "=========================================================="

source "${PROJECT_ROOT}/.venv/bin/activate"

# Start scheduler in background
airflow scheduler > "${AIRFLOW_HOME}/scheduler.log" 2>&1 &
SCHEDULER_PID=$!
echo "Scheduler started (PID: ${SCHEDULER_PID})"

# Trap exit to cleanup scheduler
trap "kill ${SCHEDULER_PID} 2>/dev/null; exit 0" SIGINT SIGTERM EXIT

# Start webserver in foreground
airflow webserver --port 8080
