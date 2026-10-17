#!/bin/bash
# ======================================================================
# VN-IT-Job-Mining -- Trình Khởi Động MinIO Object Storage (macOS / Linux)
# ======================================================================

set -e

echo "======================================================================"
echo "   VN-IT-Job-Mining -- Trình Khởi Động MinIO Object Storage (Docker)"
echo "======================================================================"
echo ""

# 1. Kiểm tra docker command
if ! command -v docker &> /dev/null; then
    echo "[LỖI] Không tìm thấy Docker CLI!"
    echo "Vui lòng cài đặt Docker hoặc Docker Desktop từ: https://docs.docker.com/get-docker/"
    exit 1
fi

# 2. Kiểm tra docker daemon
if ! docker info &> /dev/null; then
    echo "[CẢNH BÁO] Docker Daemon chưa hoạt động!"
    echo "Vui lòng khởi động Docker service: sudo systemctl start docker (Linux) hoặc mở Docker Desktop (macOS)"
    exit 1
fi

# 3. Khởi chạy docker compose
echo "[*] Đang khởi chạy MinIO container & tự động khởi tạo bucket 'vn-it-jobs'..."
docker compose up -d

echo ""
echo "======================================================================"
echo " [THÀNH CÔNG] MinIO Lakehouse đã sẵn sàng cho dự án VN-IT-Job-Mining!"
echo ""
echo " 🌐 MinIO Web Console UI:  http://localhost:9001"
echo " 🔑 Tên đăng nhập (User):   minioadmin"
echo " 🔒 Mật khẩu (Password):    minioadmin"
echo ""
echo " ⚡ S3 API Endpoint:        http://localhost:9000"
echo " 📦 Bucket mặc định:        vn-it-jobs"
echo "======================================================================"
echo ""
echo "💡 Bạn có thể mở trình duyệt và truy cập http://localhost:9001 ngay bây giờ!"
