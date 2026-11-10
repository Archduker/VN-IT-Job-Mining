#!/usr/bin/env bash
# Chạy cả chuỗi tiền xử lý + dịch EN→VI (envit5, GPU) trên máy, không đụng R2. Khoảng 2-3 giờ.
# Dùng:  bash scripts/translate_all.sh        (log: logs/translate_<giờ>.log, xem bằng tail -f)
set -euo pipefail
cd "$(dirname "$0")/.."
log="logs/translate_$(date +%Y%m%d_%H%M%S).log"
echo "Log: $log"
nohup .venv/bin/python scripts/run_preprocessing.py --step all --source all --translate >"$log" 2>&1 &
echo "PID $! đang chạy nền. Theo dõi: tail -f $log   |  Kết quả: reports/pipeline/chain_run.json"
