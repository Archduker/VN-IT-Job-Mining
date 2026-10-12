# Hướng Dẫn Tự Học & Vận Hành Apache Airflow (VN-IT-Job-Mining)

Tài liệu này được tổng hợp và đối chiếu trực tiếp từ tài liệu chính thức của **[Apache Airflow Documentation](https://airflow.apache.org/docs/)**, kết hợp hướng dẫn thực hành cụ thể trên dự án **VN-IT-Job-Mining**.

---

## 1. Thông Tin Đăng Nhập Airflow UI

Sau khi khởi động Webserver, truy cập vào giao diện web tại:
- **Địa chỉ:** `http://localhost:8080`
- **Username:** `admin`
- **Password:** `admin`
*(Role: Admin — toàn quyền xem log, kích hoạt DAG, kiểm tra biến XCom và trạng thái task).*

---

### 2. Cách Khởi Động & Vận Hành Airflow Chuẩn Production

Không cần mở nhiều terminal thủ công, hệ thống đã được tự động hóa qua Makefile và background daemon scripts:

```bash
# 1. Khởi động Airflow Production (Scheduler + Webserver chạy nền, lưu PID)
make start-airflow

# 2. Bật màn hình Giám Sát Thời Gian Thực (Live Terminal Monitor)
make monitor

# 3. Dừng an toàn toàn bộ tiến trình Airflow khi hoàn tất
make stop-airflow
```

> [!NOTE]
> Script [`scripts/start_airflow.sh`](scripts/start_airflow.sh) tự động kích hoạt virtualenv `.venv`, thiết lập `AIRFLOW_HOME=airflow`, khởi chạy Scheduler và Webserver dưới dạng daemon ngầm (`nohup`), ghi PID vào `airflow/scheduler.pid` và `airflow/webserver.pid`, đồng thời kiểm tra sức khỏe HTTP endpoint `http://localhost:8080` trước khi thông báo sẵn sàng.

---

## 3. Kiến Thức Trọng Tâm Cần Nắm Từ [Airflow Official Docs](https://airflow.apache.org/docs/)

Theo tài liệu chuẩn của Apache Airflow, có **6 khái niệm cốt lõi (Core Concepts)** trong hệ thống cần nắm vững:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. DAGs Architecture (9 DAGs Hoạt Động Song Song)                           │
│                                                                             │
│  [A] 7 Daily Rotating DAGs: crawler_topdev ... crawler_glints (20:00 Daily) │
│      crawl_task >> quality_task                                             │
│                                                                             │
│  [B] 1 Master Weekly DAG: crawler_weekly_all (CN 22:00)                     │
│      [crawl_topdev, crawl_topcv, ...] >> CrawlSummaryOperator               │
│                                                                             │
│  [C] 1 Periodic 4-day DAG: periodic_it_job_mining_4days                     │
│      HarvestListingOp >> Dedup O(1) >> DetailQueueOp >> DataQualityOp       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1. DAG (Directed Acyclic Graph)
- **Định nghĩa:** Là tập hợp các công việc (Tasks) được tổ chức theo thứ tự logic có quan hệ phụ thuộc lẫn nhau, **không tạo thành vòng lặp kín** (`A >> B`, không quay ngược).
- **Trong dự án:** Gồm **9 DAGs** được định nghĩa tại:
  - [`airflow/dags/crawler_dags.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/airflow/dags/crawler_dags.py): 7 DAGs thường nhật xoay vòng + 1 DAG Master Weekly (`crawler_weekly_all`).
  - [`airflow/dags/periodic_job_mining_dag.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/airflow/dags/periodic_job_mining_dag.py): Pipeline hàng đợi 2 giai đoạn chu kỳ 4 ngày.

### 2. Operators & Custom Task Design
- **Operator:** Là khuôn mẫu (template / class) cho một tác vụ cụ thể. Dự án thiết kế **5 Custom Operators độc lập**:
  1. `JobCrawlerOperator`: Đảm nhận việc chạy crawler nguồn, tích hợp callback logging và XCom output.
  2. `DataQualityOperator`: Đảm nhận kiểm định tính toàn vẹn file JSON (`DataQualityChecker`).
  3. `CrawlSummaryOperator`: Đọc XCom từ tất cả các task, tổng hợp chỉ số và xuất báo cáo JSON ra `logs/crawl_reports/`.
  4. `HarvestListingOperator`: Quét toàn bộ listing ID của các sàn, đăng ký vào SQLite State Catalog.
  5. `DetailCrawlerQueueOperator`: Rút tin mới từ hàng đợi để cào chi tiết có kiểm soát tốc độ.

### 3. Task Callbacks & Audit Logging
- Để theo dõi mẻ cào mà không làm bẩn code nghiệp vụ, DAGs sử dụng Airflow Callbacks:
  - `on_success_callback=_on_crawl_success`: Bắt log số tin mới, tin bỏ qua, đường dẫn batch.
  - `on_failure_callback=_on_crawl_failure`: Ghi nhận lỗi ngoại lệ và hỗ trợ gửi alert.

### 4. Schedule Interval (Cron Expressions)
- Airflow sử dụng cú pháp Cron chuẩn 5 trường: `phút giờ ngày tháng thứ`.
- **Lịch xoay vòng thường nhật (20:00 hàng ngày):**
  - Thứ Hai: `0 20 * * 1` (TopDev)
  - Thứ Ba: `0 20 * * 2` (CareerViet)
  - Thứ Tư: `0 20 * * 3` (ITviec)
  - Thứ Năm: `0 20 * * 4` (VietnamWorks)
  - Thứ Sáu: `0 20 * * 5` (TopCV)
  - Thứ Bảy: `0 20 * * 6` (ViecLam24h)
  - Chủ Nhật: `0 20 * * 0` (Glints)
- **Master Weekly:** `0 22 * * 0` (Chủ Nhật 22:00) — cào tổng lực 8 nguồn và xuất summary.
- **Periodic 4-day:** `0 2 * * *` (Mỗi 4 ngày lúc 02:00 sáng).

### 5. XComs (Cross-Communication)
- Cơ chế cho phép các Task truyền payload meta nhỏ cho nhau. Task cào đẩy đường dẫn file vừa cào vào XCom:
  ```python
  context["ti"].xcom_push(key="output_file", value=stats["output_file"])
  ```
  Task kiểm tra chất lượng rút đường dẫn đó ra để thẩm định:
  ```python
  target_file = context["ti"].xcom_pull(task_ids="crawl_vietnamworks", key="output_file")
  ```

### 6. Metadata DB: SQLite vs PostgreSQL
- **Hiện tại:** Sử dụng SQLite (`airflow/airflow.db`) kèm `SequentialExecutor` cho môi trường cục bộ / máy ảo nhẹ nhàng, zero-configuration.
- **Mở rộng Production:** Sẵn sàng chuyển đổi chuỗi kết nối sang PostgreSQL (`postgresql+psycopg2://...`) để kích hoạt `LocalExecutor` hoặc `CeleryExecutor` cho xử lý phân tán đa tiến trình.

---

## 4. Các Thao Tác Cơ Bản Trên Airflow UI (Dành Cho Buổi Báo Cáo)

Khi đăng nhập vào `http://localhost:8080`, bạn thao tác như sau:

1. **Xem danh sách 9 DAGs:**
   - Màn hình chính liệt kê 7 Daily DAGs, 1 Master Weekly DAG, và 1 Periodic DAG.
   - Nút gạt **Pause / Unpause**: Gạt sang xanh để kích hoạt lịch tự động.
2. **Kích hoạt chạy thử nghiệm ngay (Trigger DAG):**
   - Bấm vào biểu tượng **▶ (Trigger DAG)** ở dòng `crawler_weekly_all` để demo cho thầy thấy toàn bộ 8 nguồn cùng được điều phối.
3. **Theo dõi tiến độ chạy (Graph View & Grid View):**
   - Chuyển sang tab **Graph**: Quan sát các task crawler chạy song song và hội tụ về `weekly_summary`.
   - Màu sắc trạng thái:
     - 🟡 **Vàng (queued / running):** Đang xử lý.
     - 🟢 **Xanh lá cây (success):** Chạy thành công.
     - 🔴 **Đỏ (failed):** Có lỗi phát sinh.
4. **Xem Log chi tiết của từng Task:**
   - Bấm vào ô task hình chữ nhật ➜ Chọn nút **Log**.
   - Xem callback thành công và thống kê số tin mới cào được.

---

## 5. Các Lệnh Airflow CLI Cần Thuộc Lòng

```bash
# 1. Liệt kê toàn bộ DAGs của hệ thống
AIRFLOW_HOME=airflow .venv/bin/airflow dags list

# 2. Kiểm tra cú pháp lỗi của code DAG
AIRFLOW_HOME=airflow .venv/bin/airflow dags report

# 3. Test chạy 1 task độc lập mà không cần scheduler (cực kỳ hữu ích khi demo)
AIRFLOW_HOME=airflow .venv/bin/airflow tasks test crawler_vietnamworks crawl_vietnamworks 2026-10-12

# 4. Trigger 1 DAG chạy ngay lập tức qua CLI
AIRFLOW_HOME=airflow .venv/bin/airflow dags trigger crawler_weekly_all
```
