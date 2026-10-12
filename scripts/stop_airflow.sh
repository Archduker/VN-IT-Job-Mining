#!/usr/bin/env bash
# ==============================================================================
# stop_airflow.sh — Dừng tất cả Airflow processes an toàn
# ==============================================================================
# Cách dùng:
#   bash scripts/stop_airflow.sh
#   hoặc: make stop-airflow
# ==============================================================================

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info() { echo -e "${GREEN}[INFO]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AIRFLOW_HOME="${PROJECT_ROOT}/airflow"

echo ""
echo "⏹  Đang dừng tất cả tiến trình Airflow..."
echo ""

# 1. Dừng theo PID file
for pidfile in "${AIRFLOW_HOME}"/*.pid; do
    if [ -f "${pidfile}" ]; then
        pid=$(cat "${pidfile}" 2>/dev/null || true)
        if [ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null; then
            kill "${pid}" 2>/dev/null || true
            info "Đã gửi tín hiệu dừng PID ${pid} (${pidfile##*/})"
        fi
        rm -f "${pidfile}"
    fi
done

# 2. Dừng bằng pgrep các tiến trình Airflow chính xác (loại trừ chính script này và make)
CURRENT_PID=$$
PARENT_PID=$PPID

PATTERNS=(
    "airflow scheduler"
    "airflow webserver"
    "airflow-webserver"
    "gunicorn.*airflow-webserver"
    "airflow task runner"
)

for pattern in "${PATTERNS[@]}"; do
    pids=$(pgrep -f "${pattern}" 2>/dev/null | grep -v -E "^(${CURRENT_PID}|${PARENT_PID})$" || true)
    if [ -n "${pids}" ]; then
        echo "${pids}" | xargs kill 2>/dev/null || true
        info "Đã dừng các tiến trình khớp với '${pattern}'"
    fi
done

# Chờ tiến trình kết thúc
sleep 2

# 3. Quét kiểm tra còn sót không (loại trừ script hiện tại)
remaining=$(pgrep -f "bin/airflow" 2>/dev/null | grep -v -E "^(${CURRENT_PID}|${PARENT_PID})$" || true)
if [ -n "${remaining}" ]; then
    warn "Đang dọn dẹp các tiến trình còn lại..."
    echo "${remaining}" | xargs kill -9 2>/dev/null || true
    sleep 1
fi

# Xóa toàn bộ file PID còn sót
rm -f "${AIRFLOW_HOME}"/*.pid

echo ""
echo -e "${GREEN}  ✅ Tất cả tiến trình Airflow đã được dừng hoàn toàn an toàn.${NC}"
echo ""
