#!/usr/bin/env bash
# VN-IT-Job-Mining — Start MinIO (macOS / Linux)
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "[ERROR] Docker CLI not found. Install Docker Desktop or Docker Engine." >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "[ERROR] Docker Engine is not running. Start Docker Desktop/daemon and retry." >&2
  exit 1
fi

echo "[MinIO] Starting MinIO and building the bucket initializer..."
docker compose -f docker-compose.minio.yml up -d --build

if command -v curl >/dev/null 2>&1; then
  for _ in $(seq 1 45); do
    if curl --silent --fail http://localhost:9000/minio/health/live >/dev/null; then break; fi
    sleep 2
  done
  curl --silent --show-error --fail http://localhost:9000/minio/health/live >/dev/null || {
    docker compose -f docker-compose.minio.yml logs --tail 60 minio minio-init
    echo "[ERROR] MinIO health endpoint did not become ready." >&2
    exit 1
  }
else
  echo "[INFO] curl is unavailable on host; use python scripts/check_minio.py to verify API readiness."
fi

echo "[OK] MinIO Console: http://localhost:9001"
echo "[OK] S3 API:       http://localhost:9000"
echo "[OK] Bucket:       vn-it-jobs"
echo "Local defaults: minioadmin / minioadmin (development only)."
