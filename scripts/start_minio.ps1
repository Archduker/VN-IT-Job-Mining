# VN-IT-Job-Mining — Start MinIO (Windows PowerShell)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "[MinIO] Project: $ProjectRoot" -ForegroundColor Cyan
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI not found. Install Docker Desktop: https://www.docker.com/products/docker-desktop/"
}
try { docker info *> $null } catch { throw "Docker Desktop is not running. Start it and retry." }
if ($LASTEXITCODE -ne 0) { throw "Docker Desktop is not running. Start it and retry." }

Write-Host "[MinIO] Starting server and building one-time bucket initializer..." -ForegroundColor Cyan
docker compose -f .\docker-compose.minio.yml up -d --build
if ($LASTEXITCODE -ne 0) { throw "docker compose failed. Review Docker output." }

$deadline = (Get-Date).AddSeconds(90)
$ready = $false
while ((Get-Date) -lt $deadline) {
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:9000/minio/health/live" -TimeoutSec 3 -UseBasicParsing
        if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 300) { $ready = $true; break }
    } catch { Start-Sleep -Seconds 2 }
}
if (-not $ready) {
    docker compose -f .\docker-compose.minio.yml logs --tail 60 minio minio-init
    throw "MinIO did not become ready within 90 seconds. See logs above."
}

Write-Host "[OK] MinIO API:     http://localhost:9000" -ForegroundColor Green
Write-Host "[OK] MinIO Console: http://localhost:9001" -ForegroundColor Green
Write-Host "[OK] Bucket:        vn-it-jobs" -ForegroundColor Green
Write-Host "Local default credentials: minioadmin / minioadmin (development only)." -ForegroundColor Yellow
Write-Host "Check initializer: docker compose -f .\docker-compose.minio.yml logs minio-init" -ForegroundColor Gray
