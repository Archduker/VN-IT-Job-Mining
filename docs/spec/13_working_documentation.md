# HƯỚNG DẪN VẬN HÀNH HÀNG NGÀY & RUNBOOK KHẮC PHỤC SỰ CỐ (DAY-TO-DAY OPERATIONS & RUNBOOK)

> **Mã tài liệu:** `SPEC-13` | **Trạng thái:** Hoàn thiện & Hướng dẫn chính thức  
> **Dự án:** VN-IT-Job-Mining — Hệ thống khai phá dữ liệu việc làm IT Việt Nam  
> **Tài liệu liên quan:** [agents.md](../../agents.md), [09_monitoring_spec.md](09_monitoring_spec.md), [11_technical_decisions.md](11_technical_decisions.md), [12_coding_standards.md](12_coding_standards.md)

---

## 1. Thiết Lập Môi Trường Từ Con Số 0 (Zero-to-Hero Setup)

Tài liệu này hướng dẫn kỹ sư mới hoặc AI Agent thiết lập môi trường phát triển và vận hành toàn bộ hệ thống từ đầu trên máy tính cá nhân hoặc máy chủ Ubuntu Linux / macOS.

### 1.1. Yêu Cầu Phần Cứng & Hệ Điều Hành
- **Hệ điều hành:** Linux (Ubuntu 22.04 LTS hoặc 24.04 LTS khuyến nghị), macOS (Sonoma/Sequoia), hoặc WSL2 trên Windows 11.
- **Phần cứng tối thiểu:** 4 CPU Cores, 8 GB RAM (khuyến nghị 16 GB để chạy đồng thời Polars, Vite và Docker), 20 GB dung lượng ổ cứng trống.
- **Phần mềm nền tảng:**
  - Python: Phiên bản **3.12.x** (bắt buộc, không dùng Python 3.10 hoặc 3.11).
  - Node.js: Phiên bản **18.x** hoặc **20.x LTS** kèm npm.
  - Docker & Docker Compose: Dùng để chạy PostgreSQL cho Apache Airflow.
  - Git & Make.

### 1.2. Các Bước Cài Đặt Từng Bước

```bash
# Bước 1: Clone kho mã nguồn
git clone https://github.com/<your-org>/VN-IT-Job-Mining.git
cd VN-IT-Job-Mining

# Bước 2: Khởi tạo Virtual Environment với Python 3.12
python3.12 -m venv .venv
source .venv/bin/activate

# Bước 3: Cài đặt thư viện phụ thuộc Python
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Bước 4: Cài đặt Playwright browsers (phục vụ crawler JavaScript)
playwright install chromium

# Bước 5: Cài đặt thư viện Frontend
cd monitoring/frontend
npm ci
cd ../..

# Bước 6: Thiết lập file biến môi trường .env
cp .env.example .env 2>/dev/null || touch .env
```

### 1.3. Cấu Hình Biến Môi Trường (`.env`)
Điền các giá trị thực tế vào file `.env` tại thư mục gốc:

```ini
# ==========================================
# CẤU HÌNH CLOUDFLARE R2 LAKEHOUSE
# ==========================================
R2_ACCOUNT_ID=d9483c66f7f2b1840000000000000000
R2_ACCESS_KEY_ID=2a1b3c4d5e6f7a8b9c0d1e2f3a4b5c6d
R2_SECRET_ACCESS_KEY=a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2
R2_BUCKET_NAME=vn-it-jobs
R2_ENDPOINT_URL=https://d9483c66f7f2b1840000000000000000.r2.cloudflarestorage.com

# ==========================================
# CẤU HÌNH APACHE AIRFLOW & DATABASE
# ==========================================
AIRFLOW_HOME=/home/billtran/Desktop/Project/VN-IT-Job-Mining/airflow
AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@localhost:5432/airflow
AIRFLOW__CORE__LOAD_EXAMPLES=False
AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION=True

# ==========================================
# CẤU HÌNH GIÁM SÁT MONITORING
# ==========================================
MONITOR_BACKEND_PORT=8000
MONITOR_FRONTEND_PORT=5173
```

### 1.4. Kiểm Tra Sức Khỏe Kết Nối Hạ Tầng
```bash
# Kiểm tra kết nối tới Cloudflare R2
python scripts/sync_cloud_lakehouse.py --status

# Khởi động PostgreSQL trong Docker cho Airflow
make db-up

# Kiểm tra chạy test suite phân tầng (chạy offline không mạng)
make test-fast
```

---

## 2. Quy Trình Vận Hành Pipeline Thu Thập Dữ Liệu (Collection Operations)

Quy trình thu thập dữ liệu gồm 2 pha tuần tự được điều phối bởi script trung tâm `run.py`.

```mermaid
flowchart LR
    subgraph Phase1["Giai Đoạn 1: Discovery"]
        P1_Run["python run.py --phase discover\n--source <source> --max-pages 5"]
        P1_Ledger["Ghi URL mới vào\ncatalog_master.json (PENDING)"]
        P1_Sync["--sync-r2: Đẩy ledger lên R2"]
        P1_Run --> P1_Ledger --> P1_Sync
    end

    subgraph Phase2["Giai Đoạn 2: Detail"]
        P2_Run["python run.py --phase detail\n--source <source> --max-items 30"]
        P2_Crawl["Cào chi tiết bài đăng\n(curl_cffi / Playwright)"]
        P2_Save["Ghi RawJobEnvelope JSON\nCập nhật status DONE"]
        P2_Sync["--sync-r2: Đẩy Raw + Ledger lên R2"]
        P2_Run --> P2_Crawl --> P2_Save --> P2_Sync
    end

    Phase1 --> Phase2
```

### 2.1. Lệnh Thực Thi Thu Thập
```bash
# 1. Cào Discovery (Quét URL danh sách) cho một nguồn cụ thể:
python run.py --source topcv --phase discover --max-pages 3 --sync-r2

# 2. Cào Chi tiết (Detail) theo lô an toàn (30 tin):
python run.py --source topcv --phase detail --max-items 30 --sync-r2

# 3. Chạy lại các bài đăng bị lỗi trước đó (Retry Failed URLs):
python run.py --source topcv --phase detail --retry-failed --max-items 20 --sync-r2

# 4. Cào toàn bộ 8 nguồn (chỉ khuyến nghị chạy theo lịch Airflow):
python run.py --source all --phase discover --max-pages 2 --sync-r2
```

### 2.2. Kiểm Toán & Đồng Bộ Hai Chiều Với Cloudflare R2
```bash
# Kiểm toán đối chiếu giữa ổ cứng máy và Cloudflare R2:
python scripts/audit_raw_data.py --r2

# Tải dữ liệu từ R2 về máy cá nhân (chỉ kéo file mới):
python scripts/sync_cloud_lakehouse.py --download --source topcv

# Đẩy dữ liệu mới từ máy lên Cloudflare R2:
python scripts/sync_cloud_lakehouse.py --upload --source topcv
```

---

## 3. Quy Trình Vận Hành Tiền Xử Lý Dữ Liệu (Preprocessing Operations)

Quy trình tiền xử lý chuyển đổi dữ liệu thô từ tầng Bronze sang Silver (`staging/`) và Gold (`curated/`).

```mermaid
flowchart TD
    BronzeRaw["Dữ liệu Raw JSON (Bronze)"] --> Step1["Bước 1: Clean\n(Lọc IT 2 tầng, bỏ rác, khử trùng nội sàn)"]
    Step1 --> Step2["Bước 2: Integration\n(Làm phẳng JSON 8 nguồn -> all.parquet)"]
    Step2 --> Step3["Bước 3: Transformation\n(Parse lương, kinh nghiệm, làm sạch văn bản)"]
    Step3 --> Step4["Bước 4: Normalization\n(Chuẩn hóa 34 tỉnh, Taxonomy kỹ năng)"]
    Step4 --> Step5["Bước 5: Encoding\n(Multi-Hot 230 kỹ năng -> features.parquet)"]
    Step5 --> Golden["Bộ Dữ Liệu Golden Master (curated_flat_golden_jobs.parquet)"]
```

### 3.1. Các Lệnh Thực Thi Pipeline 5 Bước
```bash
# Bước chuẩn bị: Đọc kết quả chẩn đoán khám phá dữ liệu (EDA) trước khi xử lý
python scripts/read_eda_diagnosis.py --source topcv

# Chạy trọn vẹn chuỗi 5 bước tiền xử lý:
python scripts/run_preprocessing.py --all

# Hoặc chạy từng bước độc lập khi cần debug:
python preprocessing/clean/run.py
python preprocessing/integration/run.py
python preprocessing/transformation/run.py
python preprocessing/normalization/run.py
python preprocessing/encoding/run.py

# Đẩy kết quả Silver & Gold đã làm sạch lên Cloudflare R2:
python scripts/push_preprocessing_to_r2.py --apply
```

### 3.2. Quy Tắc Kiểm Tra Tính Bảo Toàn Dữ Liệu (Conservation Rule)
Sau mỗi lần chạy, kiểm tra file báo cáo tại `reports/preprocessing/<bước>/_all.json`. Bắt buộc phải thỏa mãn phương trình:
$$\text{input.rows} = \text{output.rows} + \text{dropped.total}$$
Nếu xuất hiện sự thất thoát dữ liệu không giải thích được, script sẽ báo lỗi dừng lại ngay lập tức.

---

## 4. Quy Trình Huấn Luyện & Khai Phá Dữ Liệu (Data Mining Operations)

Quy trình thực thi bộ 3 thuật toán khai phá dữ liệu học thuật trên tập dữ liệu Gold Master (5.177 bài đăng IT sạch, 230 cột đặc trưng):

```bash
# 1. Chạy thuật toán Khai phá luật kết hợp kỹ năng (FP-Growth):
python scripts/run_association_rules.py \
    --input data/preprocessing/05_encoding/features.parquet \
    --min-support 0.02 \
    --min-confidence 0.50 \
    --output reports/models/fp_growth_rules.json

# 2. Chạy thuật toán Phân cụm công việc K-Means kết hợp PCA:
python scripts/run_kmeans_clustering.py \
    --input data/preprocessing/05_encoding/features.parquet \
    --n-clusters 8 \
    --output reports/models/kmeans_clusters.json

# 3. Chạy thuật toán Dự đoán & Giải thích mức lương (Random Forest & SHAP):
python scripts/run_salary_model.py \
    --input data/curated/curated_flat_golden_jobs.parquet \
    --calc-shap \
    --output reports/models/salary_shap_summary.json
```

---

## 5. Khởi Động & Vận Hành Hệ Thống Giám Sát (Central Observatory)

Hệ thống cung cấp kịch bản khởi động tự động `./start_monitoring.sh` hỗ trợ kiểm tra cấu hình, phụ thuộc và chạy ngầm song song cả Backend lẫn Frontend.

### 5.1. Các Lệnh Khởi Động Thường Dùng

```bash
# Khởi động đầy đủ (Kiểm tra .env, bật Postgres Docker, chạy FastAPI :8000 và Vite :5173, mở browser)
./start_monitoring.sh

# Khởi động chế độ nhẹ (Không bật DB Docker, không tự động mở trình duyệt) - Khuyến nghị dùng khi dev:
./start_monitoring.sh --no-db --no-browser

# Chỉ kiểm tra cấu hình môi trường mà không khởi chạy service:
./start_monitoring.sh --check
```

### 5.2. Các Cổng Dịch Vụ Mặc Định
- **Giao diện Dashboard (Frontend):** `http://localhost:5173`
- **Tài liệu API Tương tác (Swagger Docs):** `http://localhost:8000/docs`
- **Thư mục Logs:** `logs/monitoring/backend.log` và `logs/monitoring/frontend.log`

---

## 6. Sổ Tay Xử Lý Sự Cố Khẩn Cấp (Troubleshooting Runbook)

### Kịch Bản 1: Crawler Bị Chặn Cloudflare (HTTP 403 Forbidden / Turnstile)
- **Hiện tượng:** Khi chạy cào TopCV hoặc Glints, terminal báo lỗi liên tục `403 Client Error: Forbidden`, tỷ lệ Safe Skip tăng đột biến.
- **Nguyên nhân:** Cloudflare WAF phát hiện chữ ký mạng TLS không khớp với trình duyệt chuẩn hoặc IP gửi request quá dồn dập.
- **Cách khắc phục:**
  1. Kiểm tra engine đang dùng trong `collection/topcv/crawler.py`. Bắt buộc phải là `curl_cffi` với `impersonate="chrome120"` hoặc `chrome124`.
  2. Tuyệt đối không bật engine `cloakbrowser` nếu máy chưa có license hợp lệ.
  3. Mở file `collection/common/anti_blocking.py` và tăng thời gian nghỉ ngẫu nhiên:
     ```python
     # Tăng khoảng nghỉ tạm thời khi bị WAF nghi ngờ:
     anti_blocking.polite_sleep(min_s=4.0, max_s=8.0)
     ```
  4. Nếu IP bị chặn tạm thời, chuyển sang sử dụng mạng 4G/5G hoặc đợi 30 phút để WAF gỡ cờ nghi vấn.

---

### Kịch Bản 2: Lệch Pha Giữa URL Ledger Và Raw Storage Trên R2 (Sự Cố SCRAPE-4)
- **Hiện tượng:** Chạy `python scripts/audit_raw_data.py --r2` báo cáo dòng cảnh báo: `Ledger chậm hơn raw: > 0` hoặc `DONE thiếu raw: > 0`.
- **Nguyên nhân:** Đợt cào trước đó đã đẩy các file raw lên Cloudflare R2 nhưng quên không đẩy file ledger `catalog_master.json`, hoặc script cào bị tắt đột ngột trước khi lưu catalog.
- **Cách khắc phục:**
  1. Tải toàn bộ ledger và raw hiện có trên Cloudflare R2 về thư mục cục bộ:
     ```bash
     python scripts/sync_cloud_lakehouse.py --download --source <tên_nguồn>
     ```
  2. Kích hoạt tính năng tự động sửa chữa ledger (Reconcile & Repair):
     ```bash
     python scripts/repair_url_ledger.py --source <tên_nguồn>
     ```
     Script sẽ quét các file raw đang có trên đĩa, tính toán hash và cập nhật trạng thái `DONE` cho các URL tương ứng trong catalog.
  3. Đẩy đồng bộ cả Ledger và Raw lên lại Cloudflare R2:
     ```bash
     python scripts/sync_cloud_lakehouse.py --upload --source <tên_nguồn>
     ```

---

### Kịch Bản 3: Apache Airflow Báo Lỗi Kết Nối Database Hoặc Treo Tiến Trình
- **Hiện tượng:** Bảng điều khiển Monitoring hiển thị thẻ Airflow Database màu đỏ (`OFFLINE`), lỗi log `psycopg2.OperationalError: could not connect to server: Connection refused`.
- **Nguyên nhân:** Container Docker PostgreSQL của Airflow bị dừng hoặc chưa khởi động.
- **Cách khắc phục:**
  1. Kiểm tra trạng thái container Docker:
     ```bash
     docker compose ps
     ```
  2. Khởi động lại container PostgreSQL:
     ```bash
     make db-up
     # Hoặc: docker compose up -d postgres
     ```
  3. Kiểm tra biến kết nối trong `.env`:
     ```bash
     grep AIRFLOW__DATABASE__SQL_ALCHEMY_CONN .env
     ```
  4. **Lưu ý an toàn:** Tuyệt đối không khởi động `airflow scheduler` trên máy phát triển cá nhân, vì scheduler sẽ tự động kích hoạt cào ngầm và ghi dữ liệu chưa kiểm soát lên Cloudflare R2.

---

### Kịch Bản 4: Lỗi Tràn Bộ Nhớ (Out-Of-Memory) Khi Chạy Preprocessing / Mining
- **Hiện tượng:** Tiến trình Python bị hệ điều hành tắt đột ngột với thông báo `Killed`, hoặc xuất hiện lỗi `MemoryError` khi tạo ma trận đặc trưng.
- **Nguyên nhân:** Đọc toàn bộ các trường văn bản dài (HTML, Job Description) cùng lúc vào bộ nhớ RAM khi thực hiện One-Hot Encoding 230 cột kỹ năng.
- **Cách khắc phục:**
  1. Áp dụng kỹ thuật chọn lọc cột (**Projection Pushdown**) của Apache Parquet. Chỉ đọc các cột cần thiết cho mô hình:
     ```python
     import polars as pl
     # Chỉ đọc các cột phục vụ tính toán, bỏ qua raw_html cồng kềnh:
     df = pl.read_parquet(
         "data/preprocessing/04_normalization/all.parquet",
         columns=["job_id", "salary_min", "salary_max", "skills_list", "tinh_key"]
     )
     ```
  2. Đảm bảo cấu hình garbage collection (`gc.collect()`) sau các bước chuyển đổi dữ liệu nặng.

---

### Kịch Bản 5: Frontend Không Kết Nối Được Backend (Lỗi Network / CORS / Proxy)
- **Hiện tượng:** Mở giao diện `http://localhost:5173` thấy các bảng hiển thị trạng thái tải vô tận hoặc console trình duyệt báo đỏ `ERR_CONNECTION_REFUSED` tại các endpoint `/api/v1/...`.
- **Nguyên nhân:** Backend FastAPI chưa được bật, hoặc Vite dev server cấu hình sai cổng proxy chuyển tiếp.
- **Cách khắc phục:**
  1. Kiểm tra xem Backend FastAPI có đang lắng nghe trên cổng 8000 hay không:
     ```bash
     curl -I http://127.0.0.1:8000/docs
     ```
  2. Nếu Backend chưa chạy, kiểm tra file log: `cat logs/monitoring/backend.log`.
  3. Kiểm tra file `monitoring/frontend/vite.config.ts`, xác nhận cấu hình proxy chuẩn xác:
     ```typescript
     server: {
       port: 5173,
       proxy: {
         '/api': {
           target: 'http://127.0.0.1:8000',
           changeOrigin: true,
         },
       },
     }
     ```
  4. Khởi động lại toàn bộ hệ thống bằng lệnh chuẩn:
     ```bash
     ./start_monitoring.sh --no-db --no-browser
     ```
