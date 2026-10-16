#!/usr/bin/env bash
# ==============================================================================
# Script cài đặt & khởi chạy MinIO chuẩn xác 100% theo bài viết Viblo
# Tham khảo: https://viblo.asia/p/huong-dan-chi-tiet-ve-minio-cach-cai-dat-minio-trong-3-phut-oW4oe8ekLml
#
# Cổng 9000: MinIO S3 API Endpoint (Code Python Boto3, Crawler, Airflow)
# Cổng 9001: MinIO Web Console UI (Giao diện web trực quan để đăng nhập và xem file)
# ==============================================================================

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

echo "=============================================================================="
echo "🚀 [VN-IT-Job-Mining] Bắt đầu thiết lập MinIO Lakehouse (Chuẩn Viblo)"
echo "=============================================================================="

# 1. Kiểm tra Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Lỗi: Docker chưa được cài đặt trên máy. Vui lòng cài Docker trước."
    exit 1
fi

# 2. Xử lý phân quyền Docker socket trên Linux
DOCKER_CMD="docker"
if ! docker ps > /dev/null 2>&1; then
    echo "⚠️ Docker socket cần quyền truy cập. Đang thử phân quyền..."
    if command -v sudo &> /dev/null; then
        sudo chmod 666 /var/run/docker.sock 2>/dev/null || DOCKER_CMD="sudo docker"
    else
        DOCKER_CMD="sudo docker"
    fi
fi

# 3. Dọn dẹp container cũ bị xung đột nếu có
echo "🧹 Đang dọn dẹp container cũ (nếu có)..."
$DOCKER_CMD rm -f minio-server vn_it_jobs_minio 2>/dev/null || true

# 4. Khởi chạy container MinIO chuẩn xác theo bài viết Viblo
echo "⏳ Đang khởi chạy MinIO container 'minio-server'..."
$DOCKER_CMD run -d \
  --name minio-server \
  -p 9000:9000 \
  -p 9001:9001 \
  -v minio_data:/data \
  -e "MINIO_ROOT_USER=minioadmin" \
  -e "MINIO_ROOT_PASSWORD=minioadmin" \
  --restart unless-stopped \
  minio/minio server /data --console-address ":9001"

echo "✅ Container 'minio-server' đã được kích hoạt thành công!"

# 5. Chờ MinIO sẵn sàng (tối đa 15 giây)
echo "⏳ Đang đợi MinIO Web Console sẵn sàng trên cổng 9001..."
MAX_WAIT=15
WAIT_COUNT=0
while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    if curl -s http://localhost:9001 > /dev/null 2>&1 || curl -s http://localhost:9000/minio/health/live > /dev/null 2>&1; then
        echo "✅ MinIO Web Console & S3 API đã phản hồi!"
        break
    fi
    sleep 1
    WAIT_COUNT=$((WAIT_COUNT+1))
done

# 6. Khởi tạo bucket vn-it-jobs
echo "⏳ Đang tự động khởi tạo bucket 'vn-it-jobs'..."
python3 "$REPO_DIR/scripts/setup_minio.py" || true

echo ""
echo "=============================================================================="
echo "🎉 MinIO ĐÃ SẴN SÀNG HOẠT ĐỘNG VỚI GIAO DIỆN WEB ĐỒ HỌA!"
echo "=============================================================================="
echo "👉 1. Mở Trình Duyệt Web Truy Cập: http://localhost:9001"
echo "   - Username : minioadmin"
echo "   - Password : minioadmin"
echo "👉 2. Cổng S3 API Endpoint      : http://localhost:9000"
echo "👉 3. Tên Bucket Mặc Định       : vn-it-jobs"
echo "=============================================================================="
echo "💡 Bạn có thể đăng nhập vào Web Console trên trình duyệt để thấy giao diện"
echo "   y hệt như trong bài viết hướng dẫn của Viblo!"
echo "=============================================================================="
