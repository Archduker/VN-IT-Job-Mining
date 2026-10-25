#!/usr/bin/env bash
# ==============================================================================
# Airflow Control & Management Utility (airflow_ctl.sh)
# Quản lý vòng đời Airflow (init, start, stop, status) và chạy demo E2E cục bộ.
#
# Cách dùng:
#   ./scripts/airflow_ctl.sh init     # Khởi tạo DB và 8 Pools (slots=1)
#   ./scripts/airflow_ctl.sh start    # Chạy Scheduler & Webserver nền
#   ./scripts/airflow_ctl.sh stop     # Dừng an toàn Scheduler & Webserver
#   ./scripts/airflow_ctl.sh status   # Kiểm tra tiến trình & trạng thái Pool
#   ./scripts/airflow_ctl.sh route    # Xem quyết định phân tuyến co giãn theo pending
#   ./scripts/airflow_ctl.sh demo     # Chạy demo E2E cô lập 2 Phase + Preprocess
# ==============================================================================
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export AIRFLOW_HOME="${PROJECT_ROOT}/airflow"
export PYTHONPATH="${PROJECT_ROOT}:${PROJECT_ROOT}/airflow/plugins:${PYTHONPATH:-}"
export PATH="${PROJECT_ROOT}/.venv/bin:${PATH}"

VENV_PYTHON="${PROJECT_ROOT}/.venv/bin/python"
AIRFLOW="${PROJECT_ROOT}/.venv/bin/airflow"

PID_DIR="${AIRFLOW_HOME}/run"
mkdir -p "${PID_DIR}"

SCHEDULER_PID_FILE="${PID_DIR}/scheduler.pid"
WEBSERVER_PID_FILE="${PID_DIR}/webserver.pid"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_err()   { echo -e "${RED}[ERROR]${NC} $*"; }

SOURCES=(
    "topdev"
    "vietnamworks"
    "careerviet"
    "vieclam24h"
    "itviec"
    "topcv"
    "jobsgo"
    "glints"
)

cmd_init() {
    log_info "1. Khởi tạo / cập nhật database Airflow SQLite..."
    "${AIRFLOW}" db migrate

    log_info "2. Thiết lập 8 Resource Pools cách ly 2 Pha (slots=1)..."
    for src in "${SOURCES[@]}"; do
        pool_name="pool_${src}"
        "${AIRFLOW}" pools set "${pool_name}" 1 "Isolation pool for ${src} crawler (Phase 1 & Phase 2)"
        log_ok "Đã cấu hình Pool '${pool_name}' với 1 slot."
    done

    echo ""
    log_info "Danh sách Pools hiện tại:"
    "${AIRFLOW}" pools list
    log_ok "Khởi tạo Airflow thành công!"
}

cmd_start() {
    log_info "Kiểm tra tiến trình Airflow..."

    if [ -f "${SCHEDULER_PID_FILE}" ] && kill -0 "$(cat "${SCHEDULER_PID_FILE}")" 2>/dev/null; then
        log_warn "Scheduler đã đang chạy (PID: $(cat "${SCHEDULER_PID_FILE}"))"
    else
        log_info "Khởi động Airflow Scheduler..."
        "${AIRFLOW}" scheduler \
            --pid "${SCHEDULER_PID_FILE}" \
            --stdout "${AIRFLOW_HOME}/scheduler.log" \
            --stderr "${AIRFLOW_HOME}/scheduler_err.log" \
            -D
        log_ok "Scheduler đã khởi động (PID: $(cat "${SCHEDULER_PID_FILE}"))"
    fi

    if [ -f "${WEBSERVER_PID_FILE}" ] && kill -0 "$(cat "${WEBSERVER_PID_FILE}")" 2>/dev/null; then
        log_warn "Webserver đã đang chạy (PID: $(cat "${WEBSERVER_PID_FILE}"))"
    else
        log_info "Khởi động Airflow Webserver (Port 8080)..."
        "${AIRFLOW}" webserver -p 8080 \
            --pid "${WEBSERVER_PID_FILE}" \
            --stdout "${AIRFLOW_HOME}/webserver.log" \
            --stderr "${AIRFLOW_HOME}/webserver_err.log" \
            -D
        log_ok "Webserver đã khởi động (PID: $(cat "${WEBSERVER_PID_FILE}"))"
    fi

    echo ""
    log_ok "=========================================================="
    log_ok " Airflow UI: http://localhost:8080"
    log_ok " Logs:       ${AIRFLOW_HOME}/*.log"
    log_ok "=========================================================="
}

cmd_stop() {
    log_info "Dừng các dịch vụ Airflow..."

    if [ -f "${WEBSERVER_PID_FILE}" ]; then
        W_PID="$(cat "${WEBSERVER_PID_FILE}")"
        if kill -0 "${W_PID}" 2>/dev/null; then
            log_info "Dừng Webserver (PID: ${W_PID})..."
            kill "${W_PID}" 2>/dev/null || true
            sleep 2
            kill -9 "${W_PID}" 2>/dev/null || true
        fi
        rm -f "${WEBSERVER_PID_FILE}"
        log_ok "Webserver đã dừng."
    else
        log_info "Webserver không chạy."
    fi

    if [ -f "${SCHEDULER_PID_FILE}" ]; then
        S_PID="$(cat "${SCHEDULER_PID_FILE}")"
        if kill -0 "${S_PID}" 2>/dev/null; then
            log_info "Dừng Scheduler (PID: ${S_PID})..."
            kill "${S_PID}" 2>/dev/null || true
            sleep 2
            kill -9 "${S_PID}" 2>/dev/null || true
        fi
        rm -f "${SCHEDULER_PID_FILE}"
        log_ok "Scheduler đã dừng."
    else
        log_info "Scheduler không chạy."
    fi
}

cmd_status() {
    echo "=========================================================="
    echo " AIRFLOW SERVICE STATUS"
    echo "=========================================================="

    if [ -f "${SCHEDULER_PID_FILE}" ] && kill -0 "$(cat "${SCHEDULER_PID_FILE}")" 2>/dev/null; then
        log_ok "Scheduler: Đang chạy (PID: $(cat "${SCHEDULER_PID_FILE}"))"
    else
        log_warn "Scheduler: Đã dừng"
    fi

    if [ -f "${WEBSERVER_PID_FILE}" ] && kill -0 "$(cat "${WEBSERVER_PID_FILE}")" 2>/dev/null; then
        log_ok "Webserver: Đang chạy (PID: $(cat "${WEBSERVER_PID_FILE}")) - http://localhost:8080"
    else
        log_warn "Webserver: Đã dừng"
    fi

    echo ""
    log_info "Airflow Pools Status:"
    "${AIRFLOW}" pools list
}

cmd_demo() {
    TODAY="$(date +%Y-%m-%d)"
    echo "=========================================================="
    echo " AIRFLOW END-TO-END DEMO: TOPDEV CRAWL & PREPROCESS"
    echo " Date: ${TODAY}"
    echo "=========================================================="

    log_info "Bước 1: Chạy Task Discovery (Pha 1 - Lấy link mới nhất TopDev)"
    "${AIRFLOW}" tasks test dag_discovery_daily discover_topdev "${TODAY}"

    log_info "Bước 2: Chạy Task Detail Crawler (Pha 2 - Bóc tách chi tiết TopDev)"
    "${AIRFLOW}" tasks test crawler_detail_topdev crawl_topdev_detail "${TODAY}"

    log_info "Bước 3: Chạy Task Data Quality (Kiểm tra chất lượng dữ liệu)"
    "${AIRFLOW}" tasks test crawler_detail_topdev check_quality_topdev "${TODAY}"

    log_info "Bước 4: Chạy Task Data Preprocessing (Làm sạch text & chuẩn hóa staging)"
    "${AIRFLOW}" tasks test crawler_detail_topdev preprocess_topdev "${TODAY}"

    echo ""
    log_ok "=========================================================="
    log_ok " KẾT QUẢ DEMO THÀNH CÔNG:"
    log_ok "=========================================================="
    
    RAW_COUNT=$(find "data/topdev/raw/${TODAY}" -type f -name "*.json" 2>/dev/null | wc -l || echo 0)
    STAGING_COUNT=$(find "data/topdev/staging/${TODAY}" -type f -name "*.json" 2>/dev/null | wc -l || echo 0)
    
    echo "  - File Raw Snapshot: ${RAW_COUNT} files trong data/topdev/raw/${TODAY}/"
    echo "  - File Staging Sạch: ${STAGING_COUNT} files trong data/topdev/staging/${TODAY}/"
    echo ""
    if [ "${STAGING_COUNT}" -gt 0 ]; then
        SAMPLE_FILE=$(find "data/topdev/staging/${TODAY}" -type f -name "*.json" | head -n 1)
        echo "Mẫu 1 bản ghi Staging đã tiền xử lý (${SAMPLE_FILE}):"
        head -n 35 "${SAMPLE_FILE}"
    fi
}

cmd_demo_topcv() {
    TODAY="$(date +%Y-%m-%d)"
    echo "=========================================================="
    echo " AIRFLOW END-TO-END DEMO: TOPCV CRAWL & PREPROCESS"
    echo " Date: ${TODAY}"
    echo "=========================================================="

    log_info "Bước 1: Chạy Task Route Check (Đánh giá tải & phân cấp TopCV)"
    "${AIRFLOW}" tasks test crawler_detail_topcv check_route_topcv "${TODAY}" || true

    log_info "Bước 2: Chạy Task Detail Crawler (Cào chi tiết TopCV với CloakBrowser Stealth)"
    "${AIRFLOW}" tasks test crawler_detail_topcv crawl_topcv_detail "${TODAY}"

    log_info "Bước 3: Chạy Task Data Quality (Kiểm tra chất lượng dữ liệu)"
    "${AIRFLOW}" tasks test crawler_detail_topcv check_quality_topcv "${TODAY}"

    log_info "Bước 4: Chạy Task Data Preprocessing (Làm sạch text & chuẩn hóa staging)"
    "${AIRFLOW}" tasks test crawler_detail_topcv preprocess_topcv "${TODAY}"

    echo ""
    log_ok "=========================================================="
    log_ok " KẾT QUẢ DEMO TOPCV THÀNH CÔNG:"
    log_ok "=========================================================="

    RAW_COUNT=$(find "data/topcv/raw/${TODAY}" -type f -name "*.json" 2>/dev/null | wc -l || echo 0)
    STAGING_COUNT=$(find "data/topcv/staging/${TODAY}" -type f -name "*.json" 2>/dev/null | wc -l || echo 0)

    echo "  - File Raw Snapshot: ${RAW_COUNT} files trong data/topcv/raw/${TODAY}/"
    echo "  - File Staging Sạch: ${STAGING_COUNT} files trong data/topcv/staging/${TODAY}/"
    echo ""
    if [ "${STAGING_COUNT}" -gt 0 ]; then
        SAMPLE_FILE=$(find "data/topcv/staging/${TODAY}" -type f -name "*.json" | head -n 1)
        echo "Mẫu 1 bản ghi TopCV Staging đã tiền xử lý (${SAMPLE_FILE}):"
        head -n 35 "${SAMPLE_FILE}"
    fi
}

cmd_route() {
    echo "=========================================================================================="
    echo " ADAPTIVE WORKLOAD ROUTER: ĐIỀU PHỐI TẢI CO GIÃN THEO PENDING (HẠN MỨC CỨNG 30 TIN/LẦN)"
    echo " Thời gian đánh giá: $(date '+%Y-%m-%d %H:%M:%S %Z')"
    echo "=========================================================================================="
    "${VENV_PYTHON}" -c '
from collection.common.adaptive_router import AdaptiveWorkloadRouter
sources = ["topdev", "vietnamworks", "careerviet", "vieclam24h", "itviec", "topcv", "jobsgo", "glints"]
print("%-14s | %-9s | %-6s | %-5s | %-7s | %s" % ("NGUỒN", "PHÂN CẤP", "CHẠY?", "QUOTA", "PENDING", "LÝ DO ĐIỀU PHỐI"))
print("-" * 92)
for s in sources:
    r = AdaptiveWorkloadRouter(s)
    dec = r.evaluate()
    run_str = "RUN" if dec["should_run"] else "SKIP"
    print("%-14s | %-9s | %-6s | %5d | %7d | %s" % (
        s, dec["tier"], run_str, dec["quota"], dec["backlog"], dec["reason"]
    ))
'
    echo "=========================================================================================="
}

case "${1:-status}" in
    init)
        cmd_init
        ;;
    start)
        cmd_start
        ;;
    stop)
        cmd_stop
        ;;
    status)
        cmd_status
        ;;
    route)
        cmd_route
        ;;
    demo)
        cmd_demo
        ;;
    demo-topcv)
        cmd_demo_topcv
        ;;
    *)
        echo "Cách dùng: $0 {init|start|stop|status|route|demo|demo-topcv}"
        exit 1
        ;;
esac
