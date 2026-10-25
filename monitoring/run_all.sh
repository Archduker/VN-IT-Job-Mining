#!/usr/bin/env bash
# Khởi chạy cả Backend và Frontend cho Monitoring Platform

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "========================================================"
echo "🚀 Khởi chạy VN-IT-Job-Mining Central Observatory"
echo "Thư mục gốc: $ROOT_DIR"
echo "========================================================"

# Khởi chạy Backend FastAPI ngầm
echo ">> Khởi động Backend FastAPI tại http://localhost:8000..."
cd "$ROOT_DIR/monitoring/backend" || exit 1
"$ROOT_DIR/.venv/bin/python" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Đợi backend sẵn sàng
sleep 2

# Khởi chạy Frontend Vite
echo ">> Khởi động Frontend Vite tại http://localhost:5173..."
cd "$ROOT_DIR/monitoring/frontend" || exit 1
npm run dev &
FRONTEND_PID=$!

trap "echo '>> Đang dừng hệ thống...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM

echo "========================================================"
echo "✅ Hệ thống đã sẵn sàng!"
echo "   - Web Dashboard: http://localhost:5173"
echo "   - API Backend  : http://localhost:8000/docs"
echo "   - Master API   : http://localhost:8000/api/dashboard"
echo "Nhấn Ctrl+C để dừng cả 2 dịch vụ."
echo "========================================================"

wait
