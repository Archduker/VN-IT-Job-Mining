#!/usr/bin/env bash
# ==============================================================================
# VN-IT-Job-Mining — VPS Cron Runner (Stateless Worker Execution)
#
# Cách sử dụng trong Linux Crontab:
#   0 20 * * 1 /bin/bash /path/to/VN-IT-Job-Mining/scripts/vps_cron_runner.sh topdev 50
#   0 20 * * 2 /bin/bash /path/to/VN-IT-Job-Mining/scripts/vps_cron_runner.sh careerviet 50
#   0 20 * * 3 /bin/bash /path/to/VN-IT-Job-Mining/scripts/vps_cron_runner.sh itviec 50
#   0 20 * * 4 /bin/bash /path/to/VN-IT-Job-Mining/scripts/vps_cron_runner.sh vietnamworks 50
#   0 20 * * 5 /bin/bash /path/to/VN-IT-Job-Mining/scripts/vps_cron_runner.sh topcv 50
#   0 20 * * 6 /bin/bash /path/to/VN-IT-Job-Mining/scripts/vps_cron_runner.sh vieclam24h 50
#   0  8 * * 0 /bin/bash /path/to/VN-IT-Job-Mining/scripts/vps_cron_runner.sh jobsgo 50
#   0 20 * * 0 /bin/bash /path/to/VN-IT-Job-Mining/scripts/vps_cron_runner.sh glints 30
# ==============================================================================

set -eo pipefail

SOURCE="${1:-topcv}"
MAX_ITEMS="${2:-50}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

LOGS_DIR="${PROJECT_ROOT}/logs"
mkdir -p "${LOGS_DIR}"
LOG_FILE="${LOGS_DIR}/vps_cron_${SOURCE}.log"

echo "==================================================================" | tee -a "${LOG_FILE}"
echo " [$(date -u '+%Y-%m-%d %H:%M:%S UTC')] BẮT ĐẦU CRON RUNNER CHO NGUỒN: ${SOURCE}" | tee -a "${LOG_FILE}"
echo " Thư mục dự án: ${PROJECT_ROOT} | Max Items: ${MAX_ITEMS}" | tee -a "${LOG_FILE}"
echo "==================================================================" | tee -a "${LOG_FILE}"

cd "${PROJECT_ROOT}"

# Nạp Virtual Environment nếu có
if [ -d "${PROJECT_ROOT}/.venv" ]; then
    source "${PROJECT_ROOT}/.venv/bin/activate"
fi

# Nạp biến môi trường từ .env
if [ -f "${PROJECT_ROOT}/.env" ]; then
    export $(grep -v '^#' "${PROJECT_ROOT}/.env" | xargs -d '\n')
fi

# ------------------------------------------------------------------------------
# BƯỚC 1: KÉO URL LEDGER MỚI NHẤT TỪ CLOUDFLARE R2 (PULL)
# ------------------------------------------------------------------------------
echo ">>> [1/4] Kéo URL Ledger mới nhất từ Cloudflare R2 về VPS..." | tee -a "${LOG_FILE}"
python3 scripts/sync_cloud_lakehouse.py --download --source "${SOURCE}" 2>&1 | tee -a "${LOG_FILE}" || {
    echo "⚠️ Cảnh báo: Không thể kéo Ledger từ Cloud, sử dụng Ledger cục bộ sẵn có." | tee -a "${LOG_FILE}"
}

# ------------------------------------------------------------------------------
# BƯỚC 2: THỰC THI CÀO THEO MICRO-BATCH (CRAWL)
# ------------------------------------------------------------------------------
echo ">>> [2/4] Chạy crawler cho nguồn ${SOURCE} (Phase: ALL, Max: ${MAX_ITEMS})..." | tee -a "${LOG_FILE}"
python3 run.py --source "${SOURCE}" --max-items "${MAX_ITEMS}" --phase all 2>&1 | tee -a "${LOG_FILE}"

# ------------------------------------------------------------------------------
# BƯỚC 3: ĐẨY DỮ LIỆU CÀO MỚI LÊN CLOUDFLARE R2 LAKEHOUSE (PUSH)
# ------------------------------------------------------------------------------
echo ">>> [3/4] Đẩy dữ liệu cào mới và Ledger lên Cloudflare R2 Lakehouse..." | tee -a "${LOG_FILE}"
python3 scripts/sync_cloud_lakehouse.py --upload --source "${SOURCE}" 2>&1 | tee -a "${LOG_FILE}"

# ------------------------------------------------------------------------------
# BƯỚC 4: TỰ ĐỘNG DỌN DẸP Ổ CỨNG VPS (AUTO-PURGE FILES CŨ HƠN 3 NGÀY)
# ------------------------------------------------------------------------------
echo ">>> [4/4] Dọn dẹp cache cục bộ cũ hơn 3 ngày để bảo vệ ổ cứng VPS..." | tee -a "${LOG_FILE}"
RAW_DIR="${PROJECT_ROOT}/data/${SOURCE}/raw"
if [ -d "${RAW_DIR}" ]; then
    find "${RAW_DIR}" -type f -mtime +3 -delete 2>/dev/null || true
fi

echo "✅ [$(date -u '+%Y-%m-%d %H:%M:%S UTC')] HOÀN TẤT THÀNH CÔNG CHO NGUỒN: ${SOURCE}" | tee -a "${LOG_FILE}"
echo "==================================================================" | tee -a "${LOG_FILE}"
