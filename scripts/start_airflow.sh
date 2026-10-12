#!/usr/bin/env bash
# ==============================================================================
# start_airflow.sh — Bộ khởi động hệ thống Apache Airflow (Production Runner)
# ==============================================================================
# Khởi động cả Scheduler và Webserver chạy ngầm (Background Daemon):
#   - Quản lý PID qua airflow/*.pid
#   - Ghi log hoạt động vào airflow/*.log
#   - Tự động kiểm tra sức khỏe (Health Check) cổng 8080
#   - Trả lại quyền điều khiển terminal ngay sau khi sẵn sàng
#
# Cách dùng:
#   bash scripts/start_airflow.sh
#   hoặc: make start-airflow
# ==============================================================================
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export AIRFLOW_HOME="${PROJECT_ROOT}/airflow"
export PYTHONPATH="${PROJECT_ROOT}:${PROJECT_ROOT}/airflow/plugins"
VENV_AIRFLOW="${PROJECT_ROOT}/.venv/bin/airflow"
VENV_PYTHON="${PROJECT_ROOT}/.venv/bin/python"

# ── Màu sắc terminal ──────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'
BOLD='\033[1m'; NC='\033[0m'
info()    { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
header()  { echo -e "\n${BOLD}${CYAN}$*${NC}"; }
divider() { echo -e "${CYAN}$(printf '═%.0s' {1..70})${NC}"; }

# ── Banner ────────────────────────────────────────────────────────────────────
divider
echo -e "${BOLD}${CYAN}  VN-IT-Job-Mining — Khởi Động Hệ Thống Apache Airflow Pipeline${NC}"
divider

# ── 1. Kiểm tra môi trường ────────────────────────────────────────────────────
if [ ! -f "${VENV_AIRFLOW}" ]; then
    echo -e "${YELLOW}[ERROR]${NC} Chưa tìm thấy môi trường ảo tại .venv/"
    echo "Hãy chạy: make setup để thiết lập môi trường trước."
    exit 1
fi

if [ ! -f "${AIRFLOW_HOME}/airflow.db" ]; then
    warn "Chưa tìm thấy database Airflow. Đang khởi tạo tự động..."
    AIRFLOW_HOME="${AIRFLOW_HOME}" "${VENV_AIRFLOW}" db migrate
fi

# ── 2. Khởi động Scheduler ────────────────────────────────────────────────────
SCHEDULER_PID_FILE="${AIRFLOW_HOME}/scheduler.pid"
SCHEDULER_RUNNING=false

if [ -f "${SCHEDULER_PID_FILE}" ]; then
    OLD_PID=$(cat "${SCHEDULER_PID_FILE}" 2>/dev/null || true)
    if [ -n "${OLD_PID}" ] && kill -0 "${OLD_PID}" 2>/dev/null; then
        SCHEDULER_RUNNING=true
        info "Scheduler đang hoạt động (PID: ${OLD_PID})."
    else
        rm -f "${SCHEDULER_PID_FILE}"
    fi
elif pgrep -f "airflow scheduler" > /dev/null 2>&1; then
    SCHEDULER_RUNNING=true
    SCH_PID=$(pgrep -f "airflow scheduler" | head -1)
    echo "${SCH_PID}" > "${SCHEDULER_PID_FILE}"
    info "Scheduler đang hoạt động (PID: ${SCH_PID})."
fi

if [ "${SCHEDULER_RUNNING}" = false ]; then
    info "Đang khởi động Airflow Scheduler..."
    AIRFLOW_HOME="${AIRFLOW_HOME}" PYTHONPATH="${PYTHONPATH}" \
        "${VENV_AIRFLOW}" scheduler \
        > "${AIRFLOW_HOME}/scheduler.log" 2>&1 &
    SCHEDULER_PID=$!
    echo "${SCHEDULER_PID}" > "${SCHEDULER_PID_FILE}"
    sleep 2
    info "Scheduler đã chạy ngầm (PID: ${SCHEDULER_PID}) → Log: airflow/scheduler.log"
fi

# ── 3. Khởi động Webserver ────────────────────────────────────────────────────
WEBSERVER_RUNNING=false

if curl -s --connect-timeout 2 http://localhost:8080 > /dev/null 2>&1; then
    WEBSERVER_RUNNING=true
    info "Webserver đã đang lắng nghe tại http://localhost:8080."
else
    # Kiểm tra xem có stale pid file không
    for pidfile in "${AIRFLOW_HOME}"/airflow-webserver*.pid "${AIRFLOW_HOME}"/webserver.pid; do
        if [ -f "${pidfile}" ]; then
            old_pid=$(cat "${pidfile}" 2>/dev/null || true)
            if [ -n "${old_pid}" ] && ! kill -0 "${old_pid}" 2>/dev/null; then
                rm -f "${pidfile}"
            fi
        fi
    done

    if pgrep -f "airflow.*webserver" > /dev/null 2>&1; then
        WEBSERVER_RUNNING=true
        info "Webserver process đang chạy (PID: $(pgrep -f 'airflow.*webserver' | head -1))."
    fi
fi

if [ "${WEBSERVER_RUNNING}" = false ]; then
    info "Đang khởi động Airflow Webserver ở port 8080 (Daemon)..."
    AIRFLOW_HOME="${AIRFLOW_HOME}" PYTHONPATH="${PYTHONPATH}" \
        "${VENV_AIRFLOW}" webserver --port 8080 --daemon \
        > "${AIRFLOW_HOME}/webserver.log" 2>&1
    sleep 3
    info "Webserver đã khởi động → Log: airflow/webserver.log"
fi

# ── 4. Kiểm tra sức khỏe (Health Check) ───────────────────────────────────────
info "Đang kiểm tra kết nối Web UI (http://localhost:8080)..."
READY=false
for i in {1..20}; do
    if curl -s --connect-timeout 2 http://localhost:8080 > /dev/null 2>&1; then
        READY=true
        break
    fi
    sleep 1
done

divider
if [ "${READY}" = true ]; then
    echo -e "${GREEN}${BOLD}  ✅ HỆ THỐNG AIRFLOW ĐÃ KHỞI ĐỘNG VÀ SẴN SÀNG VẬN HÀNH!${NC}"
else
    echo -e "${YELLOW}${BOLD}  ⏳ Airflow đang trong giai đoạn khởi tạo (Warmup), sẵn sàng sau ít giây.${NC}"
fi
divider

echo ""
echo -e "  ${BOLD}🌐 Địa chỉ Web UI:${NC}    http://localhost:8080"
echo -e "  ${BOLD}👤 Tài khoản:${NC}         admin / admin"
echo -e "  ${BOLD}📁 Thư mục Logs:${NC}      airflow/scheduler.log | airflow/webserver.log"
echo ""
echo -e "  ${BOLD}📊 Các lệnh điều khiển hệ thống:${NC}"
echo -e "    • Mở dashboard giám sát:  ${CYAN}make monitor${NC} (hoặc python3 scripts/monitor.py --watch)"
echo -e "    • Dừng hệ thống an toàn:  ${CYAN}make stop-airflow${NC} (hoặc bash scripts/stop_airflow.sh)"
echo -e "    • Chạy thử 1 nguồn:       ${CYAN}python run.py --source topdev --max-items 30${NC}"
echo ""
divider
