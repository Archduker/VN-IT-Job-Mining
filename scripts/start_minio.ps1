# ======================================================================
# VN-IT-Job-Mining -- Trình Khởi Động MinIO Object Storage (PowerShell)
# ======================================================================

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "   VN-IT-Job-Mining -- Trình Khởi Động MinIO Object Storage (Docker)" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Kiểm tra Docker CLI
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "[LỖI] Không tìm thấy Docker trong PATH của hệ thống!" -ForegroundColor Red
    Write-Host "Vui lòng tải và cài đặt Docker Desktop từ: https://www.docker.com/products/docker-desktop/" -ForegroundColor Yellow
    exit 1
}

# 2. Kiểm tra Docker daemon đang chạy
docker info > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[CẢNH BÁO] Docker Daemon chưa hoạt động!" -ForegroundColor Red
    Write-Host "Vui lòng mở ứng dụng Docker Desktop và chờ đến khi biểu tượng báo 'Engine running'." -ForegroundColor Yellow
    exit 1
}

# 3. Chạy docker compose
Write-Host "[*] Đang khởi chạy MinIO và tự động tạo bucket 'vn-it-jobs'..." -ForegroundColor Green
docker compose up -d

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "======================================================================" -ForegroundColor Green
    Write-Host " [THÀNH CÔNG] MinIO Lakehouse đã sẵn sàng cho cả Team!" -ForegroundColor Green
    Write-Host ""
    Write-Host " 🌐 MinIO Web Console UI:  http://localhost:9001" -ForegroundColor Cyan
    Write-Host " 🔑 Tên đăng nhập (User):   minioadmin" -ForegroundColor White
    Write-Host " 🔒 Mật khẩu (Password):    minioadmin" -ForegroundColor White
    Write-Host ""
    Write-Host " ⚡ S3 API Endpoint:        http://localhost:9000" -ForegroundColor Cyan
    Write-Host " 📦 Bucket mặc định:        vn-it-jobs" -ForegroundColor Yellow
    Write-Host "======================================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Bạn có thể mở trình duyệt và truy cập http://localhost:9001 ngay!" -ForegroundColor White
} else {
    Write-Host "[LỖI] Không thể khởi động MinIO container. Hãy kiểm tra cổng 9000/9001 có bị chiếm dụng không." -ForegroundColor Red
}
