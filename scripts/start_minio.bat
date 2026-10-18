@echo off
chcp 65001 >nul
setlocal
pushd "%~dp0.."
echo ======================================================================
echo VN-IT-Job-Mining - Start MinIO
 echo ======================================================================
where docker >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Docker CLI not found. Install Docker Desktop first.
  popd
  pause
  exit /b 1
)
docker info >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Docker Desktop is not running. Start it and retry.
  popd
  pause
  exit /b 1
)
docker compose -f docker-compose.minio.yml up -d --build
if errorlevel 1 (
  echo [ERROR] Could not start MinIO. Review Docker output.
  popd
  pause
  exit /b 1
)
echo.
echo [OK] MinIO Console: http://localhost:9001
echo [OK] S3 API:        http://localhost:9000
echo [OK] Bucket:        vn-it-jobs
echo Local defaults: minioadmin / minioadmin (development only).
echo Verify with: python scripts\check_minio.py
popd
pause
exit /b 0
