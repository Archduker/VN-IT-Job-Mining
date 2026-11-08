#!/usr/bin/env bash
# ==============================================================================
# VN-IT-Job-Mining — Automated Setup Script for AWS EC2 (Ubuntu 22.04 / 24.04 LTS)
# ==============================================================================
# Script này tự động thiết lập toàn bộ môi trường trên EC2:
# 1. Kích hoạt 4GB Swap RAM (chống OOM cho t3.small / t3.medium)
# 2. Cài đặt Python 3.12, Chromium Headless, Docker, Git, Build Essentials
# 3. Tạo Virtualenv và cài đặt dependencies
# 4. Cấu hình Airflow chạy ngầm qua Systemd (Scheduler + Webserver)
# ==============================================================================

set -euo pipefail

echo "=================================================================="
echo "🚀 BẮT ĐẦU CÀI ĐẶT HỆ THỐNG VN-IT-JOB-MINING TRÊN AWS EC2"
echo "=================================================================="

# 1. Cấu hình Swap File 4GB (Bảo vệ RAM t3.small không bao giờ bị OOM)
if [ ! -f /swapfile ]; then
    echo ">>> [1/5] Tạo 4GB Swap RAM ảo..."
    sudo fallocate -l 4G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=4096
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    echo "vm.swappiness=10" | sudo tee -a /etc/sysctl.conf
    sudo sysctl vm.swappiness=10
    echo "✅ Đã kích hoạt 4GB Swap thành công!"
else
    echo "✅ Swap file đã tồn tại, bỏ qua."
fi

# 2. Cập nhật hệ thống và cài đặt các gói cần thiết
echo ""
echo ">>> [2/5] Cập nhật Ubuntu & cài đặt Chromium, Python 3, Docker..."
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    chromium-browser \
    chromium-chromedriver \
    ca-certificates \
    curl \
    git \
    htop \
    unzip

# 3. Cài đặt Docker & Docker Compose (tùy chọn container)
if ! command -v docker &> /dev/null; then
    echo "Đang cài đặt Docker Engine..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker "$USER"
    rm -f get-docker.sh
fi

# 4. Thiết lập Virtual Environment cho dự án
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

echo ""
echo ">>> [3/5] Khởi tạo Python Virtual Environment (.venv)..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# 5. Khởi tạo cơ sở dữ liệu Airflow
echo ""
echo ">>> [4/5] Khởi tạo cơ sở dữ liệu Airflow..."
export AIRFLOW_HOME="${PROJECT_DIR}/airflow"
mkdir -p "${AIRFLOW_HOME}/dags" "${AIRFLOW_HOME}/logs" "${AIRFLOW_HOME}/plugins"

# Khởi tạo db nếu chưa có
if [ ! -f "${AIRFLOW_HOME}/airflow.db" ]; then
    airflow db init
    # Tạo tài khoản admin mặc định
    airflow users create \
        --username admin \
        --firstname Admin \
        --lastname User \
        --role Admin \
        --email admin@vn-it-jobs.local \
        --password admin
fi

# 6. Thiết lập Systemd Service cho Airflow (Tự khởi động cùng EC2)
echo ""
echo ">>> [5/5] Cấu hình Systemd Services cho Airflow Scheduler & Webserver..."

# Airflow Scheduler Service
cat << EOF | sudo tee /etc/systemd/system/airflow-scheduler.service
[Unit]
Description=Airflow Scheduler Daemon for VN-IT-Job-Mining
After=network.target

[Service]
User=$USER
Group=$USER
Type=simple
WorkingDirectory=$PROJECT_DIR
Environment="AIRFLOW_HOME=$AIRFLOW_HOME"
Environment="PATH=$PROJECT_DIR/.venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$PROJECT_DIR/.venv/bin/airflow scheduler
Restart=always
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

# Airflow Webserver Service
cat << EOF | sudo tee /etc/systemd/system/airflow-webserver.service
[Unit]
Description=Airflow Webserver Daemon for VN-IT-Job-Mining
After=network.target

[Service]
User=$USER
Group=$USER
Type=simple
WorkingDirectory=$PROJECT_DIR
Environment="AIRFLOW_HOME=$AIRFLOW_HOME"
Environment="PATH=$PROJECT_DIR/.venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$PROJECT_DIR/.venv/bin/airflow webserver --port 8080
Restart=always
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

# Nạp cấu hình systemd
sudo systemctl daemon-reload
sudo systemctl enable airflow-scheduler airflow-webserver
sudo systemctl restart airflow-scheduler airflow-webserver

echo ""
echo "=================================================================="
echo "🎉 CHÚC MỪNG! HỆ THỐNG ĐÃ ĐƯỢC THIẾT LẬP HOÀN TẤT TRÊN AWS EC2!"
echo "=================================================================="
echo "1. Trạng thái Airflow Services:"
echo "   - Scheduler : $(sudo systemctl is-active airflow-scheduler)"
echo "   - Webserver : $(sudo systemctl is-active airflow-webserver)"
echo "2. Truy cập Giao diện Web Airflow UI:"
echo "   http://<EC2-PUBLIC-IP>:8080"
echo "   Tài khoản : admin"
echo "   Mật khẩu  : admin"
echo "3. Lịch chạy DAG tự động:"
echo "   - 05:00 sáng: dag_discovery_daily (Quét link mới nhất cả 8 nguồn)"
echo "   - 20:00 - 22:55 tối: 8 DAGs cào chi tiết rải rác theo quota"
echo "=================================================================="
