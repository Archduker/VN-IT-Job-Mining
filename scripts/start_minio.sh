#!/usr/bin/env bash
# ==============================================================================
# Script khởi động MinIO Lakehouse cho dự án VN-IT-Job-Mining
# Cổng 9000: S3 API Endpoint (Crawler, Airflow, DuckDB)
# Cổng 9001: MinIO Web Console UI (Xem bucket, quản lý file trên trình duyệt)
# ==============================================================================

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

echo "=== [VN-IT-Job-Mining] Khởi Động MinIO Lakehouse ==="

# 1. Kiểm tra docker compose
if ! command -v docker &> /dev/null; then
    echo "❌ Lỗi: Docker chưa được cài đặt trên hệ thống."
    exit 1
fi

# 2. Khởi động container MinIO
echo "⏳ Đang bật MinIO container qua Docker Compose..."
if docker compose -f docker-compose.minio.yml up -d 2>/dev/null; then
    echo "✅ Docker Compose khởi động thành công (User hiện tại)."
else
    echo "⚠️ Cần quyền sudo để truy cập Docker socket..."
    sudo docker compose -f docker-compose.minio.yml up -d
fi

# 3. Đợi MinIO sẵn sàng (tối đa 15 giây)
echo "⏳ Đang đợi MinIO sẵn sàng trên cổng 9000 và 9001..."
MAX_RETRIES=15
COUNT=0
while [ $COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:9000/minio/health/live > /dev/null 2>&1 || nc -z localhost 9000 2>/dev/null; then
        echo "✅ MinIO S3 API đã sẵn sàng trên cổng 9000."
        break
    fi
    sleep 1
    COUNT=$((COUNT+1))
done

# 4. Chạy script khởi tạo bucket vn-it-jobs
echo "⏳ Kiểm tra và khởi tạo bucket 'vn-it-jobs'..."
python3 "$REPO_DIR/scripts/setup_minio.py" || true

echo ""
echo "=============================================================================="
echo "🎉 MinIO Lakehouse đã sẵn sàng hoạt động!"
echo "👉 Web Console UI : http://localhost:9001"
echo "   - Tài khoản     : minioadmin"
echo "   - Mật khẩu      : minioadmin"
echo "👉 S3 API Endpoint: http://localhost:9000"
echo "👉 Bucket mặc định: vn-it-jobs"
echo "=============================================================================="
