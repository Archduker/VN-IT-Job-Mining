---
name: minio-lakehouse-guide
description: >-
  Chuyên gia vận hành hệ thống MinIO Object Storage & Data Lakehouse cho dự án VN-IT-Job-Mining.
  Chuyên sâu về: đóng gói Docker 1-lệnh đa nền tảng (Windows/macOS/Linux), quản lý bucket `vn-it-jobs`,
  kiến trúc phân tầng Lakehouse (url_ledger, raw, staging, curated), đồng bộ S3 API qua Boto3 SDK,
  tương tác Web Console UI (Port 9001), xử lý sự cố Docker Hub restriction (elestio/minio),
  và kiểm tra tính toàn vẹn dữ liệu cào cho cả nhóm phát triển.
---

# MinIO Lakehouse Guide Skill

Kỹ năng này trang bị cho AI Agent năng lực hướng dẫn, tự động hóa, cấu hình và khắc phục sự cố hệ thống lưu trữ đối tượng **MinIO Object Storage & Lakehouse** cho toàn bộ thành viên trong nhóm dự án VN-IT-Job-Mining.

---

## 1. Kiến Trúc Đóng Gói Docker Chuẩn Cho Team (Zero-Config Architecture)

Để đảm bảo mọi thành viên trong nhóm (dù sử dụng Windows, macOS hay Linux) đều có thể chạy được MinIO chỉ bằng **1 lệnh duy nhất** mà không gặp lỗi phân quyền hay xung đột thư viện:

### File cấu hình gốc: `docker-compose.yml`
```yaml
services:
  minio:
    image: elestio/minio:latest
    container_name: vn_it_jobs_minio
    restart: unless-stopped
    ports:
      - "9000:9000"   # MinIO S3 API Endpoint
      - "9001:9001"   # MinIO Web Console UI
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - minio_data:/data
    command: server /data --console-address ":9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 5s
      timeout: 3s
      retries: 5

  minio-init:
    image: elestio/minio:latest
    container_name: vn_it_jobs_minio_init
    depends_on:
      minio:
        condition: service_healthy
    entrypoint: >
      /bin/sh -c "
      mc alias set local http://minio:9000 minioadmin minioadmin &&
      mc mb --ignore-existing local/vn-it-jobs &&
      mc anonymous set download local/vn-it-jobs &&
      exit 0;
      "

volumes:
  minio_data:
    driver: local
```

> [!IMPORTANT]
> **Quy tắc hình ảnh Docker bắt buộc**:
> Tuyệt đối **không sử dụng `minio/minio` hay `minio/mc`** do Docker Hub đã đóng quyền truy cập public đối với các image này. Luôn sử dụng image cộng đồng đã được kiểm chứng: **`elestio/minio:latest`** (đã tích hợp sẵn cả MinIO Server lẫn công cụ dòng lệnh `mc`).

---

## 2. Quy Trình Khởi Động Theo Hệ Điều Hành

Khi thành viên nhóm hỏi cách khởi chạy MinIO trên máy cá nhân của họ, Agent hướng dẫn theo từng môi trường cụ thể:

### A. Windows (Desktop / WSL2)
- **Cách nhanh nhất**: Click đúp vào file `scripts/start_minio.bat`.
- **Hoặc qua PowerShell**:
  ```powershell
  .\scripts\start_minio.ps1
  ```
- **Điều kiện tiên quyết**: Đảm bảo ứng dụng Docker Desktop đang ở trạng thái Running.

### B. macOS & Linux
- Chạy script tự động:
  ```bash
  ./scripts/start_minio.sh
  ```
  *(Hoặc gõ trực tiếp: `docker compose up -d`)*

---

## 3. Cấu Trúc Phân Tầng Dữ Liệu Trong Bucket `vn-it-jobs`

Mọi dữ liệu được tổ chức thống nhất trong bucket `vn-it-jobs` theo 4 phân tầng kiến trúc Lakehouse:

```text
vn-it-jobs/
├── url_ledger/
│   ├── <source>/
│   │   ├── catalog_master.json         # Sổ cái toàn diện chứa mọi URL và hash
│   │   └── manifests/
│   │       └── manifest_YYYY-MM-DD.jsonl # Danh sách phát hiện theo ngày
├── raw/
│   └── <source>/
│       └── year=YYYY/month=MM/day=DD/  # Dữ liệu HTML thô nguyên bản & Envelope JSON
├── staging/
│   └── <source>/                       # Dữ liệu đã chuẩn hóa schema bước 1
└── curated/                            # Dữ liệu đã khử trùng lặp và làm giàu ML
```

---

## 4. Chuẩn Giao Tiếp S3 API Với Mã Nguồn Python

Khi viết mã Python (crawler, data pipeline, eda) để tương tác với MinIO, luôn tuân thủ chuẩn kết nối Boto3:

```python
import os
import boto3
from botocore.client import Config

def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("MINIO_ENDPOINT", "http://localhost:9000"),
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "minioadmin"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "minioadmin"),
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )
```

### Các công cụ tra cứu tích hợp sẵn trong repo:
1. **Kiểm tra trạng thái sức khỏe**:
   ```bash
   .venv/bin/python scripts/check_minio.py
   ```
2. **Xem sổ cái URL Ledger từ MinIO**:
   ```bash
   .venv/bin/python scripts/view_urls.py --source topcv --minio --limit 20
   ```

---

## 5. Bảng Khắc Phục Sự Cố Thường Gặp (Troubleshooting Playbook)

| Vấn đề | Biểu hiện | Cách xử lý |
| :--- | :--- | :--- |
| **Xung đột cổng mạng** | `Bind for 0.0.0.0:9000 failed: port is already allocated` | Chạy `docker ps` để tìm container cũ đang chiếm cổng, sau đó `docker stop <id>` hoặc đổi port mapping trong `docker-compose.yml`. |
| **Lỗi Docker daemon** | `Cannot connect to the Docker daemon at unix:///var/run/docker.sock` | Mở ứng dụng Docker Desktop (Windows/macOS) hoặc chạy `sudo systemctl start docker` (Linux). |
| **Bucket chưa xuất hiện** | Web UI không thấy bucket `vn-it-jobs` | Chạy lệnh `docker compose up -d minio-init` hoặc chạy `.venv/bin/python scripts/check_minio.py` để script tự động tạo bucket. |
| **Muốn xóa làm sạch dữ liệu** | Cần đưa MinIO về trạng thái trắng ban đầu | Chạy `docker compose down -v` để xóa sạch volumes dữ liệu. |

---

## 6. Kiến Trúc Chia Sẻ Dữ Liệu Nhóm: Cloudflare R2 Cloud Lakehouse

Khi dự án bước vào giai đoạn nhiều thành viên cào song song đa sàn (TopCV, ITViec, VietnamWorks,...), hệ thống hỗ trợ cơ chế **Hybrid Data Lakehouse**:
- **Offline / Dev cá nhân**: Dùng MinIO cục bộ (`localhost:9000`).
- **Làm việc nhóm tập trung**: Dùng Cloudflare R2 Bucket chung (`vn-it-jobs`), miễn phí 10 GB và $0 egress fee.

### Các công cụ hỗ trợ Cloud R2 trong repo:
1. **Thiết lập kết nối Cloud R2 tự động**:
   ```bash
   .venv/bin/python scripts/setup_cloud_storage.py
   ```
2. **Kéo dữ liệu cả nhóm về máy cục bộ**:
   ```bash
   .venv/bin/python scripts/sync_cloud_lakehouse.py --download
   ```
3. **Đẩy dữ liệu mới cào lên Cloud R2**:
   ```bash
   .venv/bin/python scripts/sync_cloud_lakehouse.py --upload
   ```
4. **Kiểm tra trạng thái lưu trữ trên Cloud**:
   ```bash
   .venv/bin/python scripts/sync_cloud_lakehouse.py --status
   ```

