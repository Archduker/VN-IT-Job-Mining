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

## 2. Cách Chạy Airflow Trên Laptop

Để Airflow hoạt động hoàn chỉnh (vừa lập lịch tự động, vừa hiển thị UI), cần mở **2 cửa sổ Terminal**:

### Terminal 1: Khởi động Scheduler (Bộ điều phối & lập lịch)
```bash
cd /home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining
source .venv/bin/activate
export AIRFLOW_HOME=$(pwd)/airflow
export PYTHONPATH=.:$(pwd)/airflow/plugins

# Khởi động Scheduler
airflow scheduler
```

### Terminal 2: Khởi động Webserver (Giao diện điều khiển)
```bash
cd /home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining
source .venv/bin/activate
export AIRFLOW_HOME=$(pwd)/airflow
export PYTHONPATH=.:$(pwd)/airflow/plugins

# Khởi động Webserver ở port 8080
airflow webserver --port 8080
```

---

## 3. Kiến Thức Trọng Tâm Cần Nắm Từ [Airflow Official Docs](https://airflow.apache.org/docs/)

Theo tài liệu chuẩn của Apache Airflow, có **5 khái niệm cốt lõi (Core Concepts)** cần hiểu để tự tin trả lời câu hỏi của thầy:

```
┌────────────────────────────────────────────────────────┐
│ DAG (Directed Acyclic Graph)                           │
│ (Đồ thị có hướng không chu trình - đại diện quy trình) │
│                                                        │
│  ┌───────────────────────┐    >>    ┌────────────────┐ │
│  │ Task 1: Crawl Source  │          │ Task 2: Quality│ │
│  │ (JobCrawlerOperator)  │          │ (DataQualityOp)│ │
│  └───────────────────────┘          └────────────────┘ │
└────────────────────────────────────────────────────────┘
```

### 1. DAG (Directed Acyclic Graph)
- **Định nghĩa:** Là tập hợp các công việc (Tasks) được tổ chức theo thứ tự logic có quan hệ phụ thuộc lẫn nhau, **không tạo thành vòng lặp kín** (`A >> B`, không có chuyện `B quay lại A`).
- **Trong dự án:** Mỗi nguồn tuyển dụng là 1 DAG độc lập nằm trong [airflow/dags/crawler_dags.py](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/airflow/dags/crawler_dags.py) (`crawler_topdev`, `crawler_vietnamworks`, ...).

### 2. Operators & Tasks
- **Operator:** Là bản thiết kế (template / class) cho việc cần làm.
  - Trong dự án, team tự viết 2 custom operators tại [airflow/plugins/crawler_operators.py](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/airflow/plugins/crawler_operators.py):
    - `JobCrawlerOperator`: Đảm nhận việc chạy crawler.
    - `DataQualityOperator`: Đảm nhận việc kiểm tra file JSONL đầu ra.
- **Task:** Là một thực thể (instance) cụ thể của Operator được gán vào DAG (ví dụ: `crawl_vietnamworks >> check_quality_vietnamworks`).

### 3. Schedule Interval (Lập Lịch Bằng Cron Expression)
- Airflow sử dụng cú pháp Cron 5 trường: `phút giờ ngày-trong-tháng tháng ngày-trong-tuần`.
- **Rotating Daily Schedule trong dự án (chạy lúc 20:00 tối mỗi ngày):**
  - Thứ Hai: `0 20 * * 1` (TopDev)
  - Thứ Ba: `0 20 * * 2` (CareerViet)
  - Thứ Tư: `0 20 * * 3` (ITviec)
  - Thứ Năm: `0 20 * * 4` (VietnamWorks)
  - Thứ Sáu: `0 20 * * 5` (TopCV)
  - Thứ Bảy: `0 20 * * 6` (ViecLam24h)

### 4. XComs (Cross-Communication)
- **Định nghĩa:** Cơ chế cho phép các Task truyền những mẩu dữ liệu nhỏ cho nhau.
- **Trong dự án:** Task cào (`JobCrawlerOperator`) đẩy đường dẫn file vừa cào vào XCom:
  ```python
  context["ti"].xcom_push(key="output_file", value=stats["output_file"])
  ```
  Task kiểm tra chất lượng (`DataQualityOperator`) rút đường dẫn đó ra để thẩm định:
  ```python
  target_file = context["ti"].xcom_pull(task_ids="crawl_vietnamworks", key="output_file")
  ```

### 5. Catchup & Backfill
- Mặc định, nếu DAG có `start_date` trong quá khứ, Airflow sẽ cố gắng chạy bù toàn bộ các ngày bị thiếu.
- Trong dự án, ta đặt `catchup=False` để **chỉ chạy đúng phiên hiện tại**, không làm nghẽn máy tính khi mới bật lên.

---

## 4. Các Thao Tác Cơ Bản Trên Airflow UI (Dành Cho Buổi Báo Cáo)

Khi đăng nhập vào `http://localhost:8080`, bạn thao tác như sau:

1. **Xem danh sách DAGs:**
   - Màn hình chính liệt kê 6 DAGs của 6 trang tuyển dụng.
   - Bên trái mỗi DAG có nút gạt **Bật / Tắt (Pause / Unpause)**. Gạt sang màu xanh để cho phép DAG chạy tự động.
2. **Kích hoạt chạy thủ công (Trigger DAG):**
   - Ở cột **Actions** ngoài cùng bên phải của mỗi DAG, nhấn vào biểu tượng **▶ (Trigger DAG)**.
   - Nhấn **Trigger** để chạy ngay mà không cần đợi đến 20:00 tối.
3. **Theo dõi tiến độ chạy (Graph View & Grid View):**
   - Bấm vào tên DAG (ví dụ: `crawler_vietnamworks`).
   - Chuyển sang tab **Graph**: Sẽ thấy 2 ô nối nhau: `crawl_vietnamworks` ➜ `check_quality_vietnamworks`.
   - Màu sắc trạng thái:
     - 🟡 **Vàng (queued / running):** Đang xử lý.
     - 🟢 **Xanh lá cây (success):** Chạy thành công.
     - 🔴 **Đỏ (failed):** Có lỗi phát sinh.
4. **Xem Log chi tiết của từng Task:**
   - Bấm trực tiếp vào ô task hình chữ nhật màu xanh trên sơ đồ Graph.
   - Chọn nút **Log** ở thanh menu bật lên.
   - Toàn bộ log HTTP request, số lượng jobs cào được, và checkpoint sẽ hiển thị trực quan theo thời gian thực.

---

## 5. Các Lệnh Airflow CLI Cần Thuộc Lòng

Nếu thầy yêu cầu thao tác trực tiếp trên Terminal thay vì dùng Web UI:

```bash
# 1. Liệt kê toàn bộ DAGs của hệ thống
airflow dags list

# 2. Kiểm tra cú pháp lỗi của code DAG (báo lỗi nếu file Python bị sai import)
airflow dags report

# 3. Test chạy 1 task độc lập mà không cần scheduler (cực kỳ hữu ích khi demo)
airflow tasks test crawler_vietnamworks crawl_vietnamworks 2026-10-06

# 4. Trigger 1 DAG chạy ngay lập tức qua CLI
airflow dags trigger crawler_vietnamworks
```
