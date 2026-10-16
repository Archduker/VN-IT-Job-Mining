@echo off
chcp 65001 >nul
echo ======================================================================
echo    VN-IT-Job-Mining -- Trình Khởi Động MinIO Object Storage (Docker)
echo ======================================================================
echo.

:: 1. Kiểm tra xem Docker CLI có khả dụng không
where docker >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [LỖI] Không tìm thấy Docker trong hệ thống!
    echo Vui lòng cài đặt Docker Desktop từ: https://www.docker.com/products/docker-desktop/
    echo Sau khi cài đặt, hãy mở Docker Desktop rồi chạy lại script này.
    echo.
    pause
    exit /b 1
)

:: 2. Kiểm tra xem Docker Daemon có đang chạy không
docker info >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [CẢNH BÁO] Docker Desktop chưa được bật!
    echo Đang thử chờ Docker Desktop khởi động...
    echo Vui lòng đảm bảo Docker Desktop có biểu tượng cá voi màu xanh lá cây (Running).
    echo.
    pause
    exit /b 1
)

:: 3. Khởi chạy MinIO và container khởi tạo bucket
echo [*] Đang khởi chạy MinIO container qua Docker Compose...
docker compose up -d

if %ERRORLEVEL% NEQ 0 (
    echo [LỖI] Không thể khởi chạy container MinIO.
    echo Vui lòng kiểm tra lại xung đột cổng 9000 hoặc 9001.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ======================================================================
echo  [THÀNH CÔNG] MinIO Lakehouse đã sẵn sàng cho dự án VN-IT-Job-Mining!
echo.
echo  🌐 MinIO Web Console UI:  http://localhost:9001
echo  🔑 Tên đăng nhập (User):   minioadmin
echo  🔒 Mật khẩu (Password):    minioadmin
echo.
echo  ⚡ S3 API Endpoint:        http://localhost:9000
echo  📦 Bucket mặc định:        vn-it-jobs
echo ======================================================================
echo.
echo Bạn có thể mở trình duyệt và truy cập http://localhost:9001 ngay bây giờ!
pause
