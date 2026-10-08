# BÁO CÁO TIẾN ĐỘ ĐỒ ÁN
## ĐỀ TÀI: KHAI PHÁ DỮ LIỆU TUYỂN DỤNG CÔNG NGHỆ THÔNG TIN TẠI VIỆT NAM (VN-IT-JOB-MINING)

---

## I. THÔNG TIN CHUNG
- **Tên đề tài:** Hệ Thống Tự Động Thu Thập, Kiểm Tra Chất Lượng & Khai Phá Dữ Liệu Việc Làm IT (VN-IT-Job-Mining)
- **Công nghệ cốt lõi:** Python, Apache Airflow, Pydantic, HTTPX/Playwright, JSONL Data Lake, PostgreSQL (kế hoạch nạp DB).
- **Mục tiêu giai đoạn 1:** Xây dựng thành công hạ tầng Data Pipeline tự động: cào dữ liệu xoay vòng từ 6 nền tảng tuyển dụng lớn, chuẩn hóa dữ liệu, loại bỏ trùng lặp và tự động kiểm định chất lượng dữ liệu (Data Quality Gate).

---

## II. KẾT QUẢ THU THẬP DỮ LIỆU THỰC TẾ

Tính đến thời điểm hiện tại, hệ thống đã hoàn thành thiết lập cho **6 nguồn tuyển dụng** và đã tiến hành thu thập thử nghiệm với **tỷ lệ toàn vẹn dữ liệu đạt 100%**:

| STT | Nguồn (Source) | Lịch Airflow (Cron) | Số Tin Đã Cào | Tỷ Lệ Chuẩn Schema | Trùng Lặp (Dedup) | Đánh Giá Chất Lượng |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: |
| 1 | **VietnamWorks** | Thứ Năm 20:00 | **100** | 100% (100/100) | 0% | ✅ **ĐẠT (PASS)** |
| 2 | **CareerViet** | Thứ Ba 20:00 | **100** | 100% (100/100) | 0% | ✅ **ĐẠT (PASS)** |
| 3 | **ITviec** | Thứ Tư 20:00 | **4** | 100% (4/4) | 0% | ✅ **ĐẠT (PASS)** |
| 4 | **TopDev** | Thứ Hai 20:00 | *(Sẵn sàng)* | Đã cấu hình Checkpoint | 0% | 🔄 Sẵn sàng cào |
| 5 | **TopCV** | Thứ Sáu 20:00 | *(Sẵn sàng)* | Đã cấu hình Checkpoint | 0% | 🔄 Sẵn sàng cào |
| 6 | **ViecLam24h** | Thứ Bảy 20:00 | *(Sẵn sàng)* | Đã cấu hình Checkpoint | 0% | 🔄 Sẵn sàng cào |
| **TỔNG** | **6 Nguồn** | **Xoay vòng cả tuần** | **204+ tin mẫu** | **100% đạt chuẩn** | **0%** | 🏆 **HỆ THỐNG ỔN ĐỊNH** |

> Lệnh kiểm tra tiến độ nhanh tại terminal:
> ```bash
> python3 scripts/report.py
> ```

---

## III. CÁC ĐẶC TRƯNG KỸ THUẬT NỔI BẬT ĐÃ TRIỂN KHAI

### 1. Điều Phối Tự Động Bằng Apache Airflow (6 Rotating DAGs)
- **Chiến lược xoay vòng (Rotating Crawling):** Để không gây quá tải mạng và tránh bị hệ thống đối tác chặn IP (Anti-scraping), mỗi ngày trong tuần hệ thống kích hoạt tự động cào đúng 1 trang việc làm vào khung giờ **20:00**.
- **Cơ chế chịu lỗi:** Thiết lập tự động thử lại (`retries=1`, `retry_delay=5 phút`) khi gặp sự cố gián đoạn đường truyền.

### 2. Thiết Kế Động Cơ Thu Thập Hướng Đối Tượng (`BaseCrawler`)
- Toàn bộ crawler đều kế thừa kiến trúc chung [`BaseCrawler`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/base/base_crawler.py).
- **Lịch sự & An toàn (Polite Crawling):** Tự động tạo khoảng nghỉ (delay ngẫu nhiên 2 - 5 giây) giữa các lượt request và xoay vòng User-Agent Header.
- **Khử trùng lặp qua Checkpoint:** Lưu trữ danh sách `source_job_id` đã từng cào vào file `<source>_checkpoint.json`. Những lần chạy sau chỉ cào tin mới, giúp tiết kiệm băng thông và tối ưu hiệu suất.

### 3. Chuẩn Hóa Schema Tuyệt Đối Với Pydantic (`JobRecord`)
Dữ liệu của 6 website tuyển dụng có cấu trúc HTML/JSON hoàn toàn khác nhau, nhưng đều được hệ thống chuyển đổi thống nhất về 1 schema `JobRecord`:
- `_meta`: Lưu trữ thông tin kỹ thuật (`source`, `source_job_id`, `url`, `crawled_at`, `batch_id`).
- `raw`: Tiêu đề việc làm (`title`), tên công ty (`company`), mức lương (`salary_text`), địa điểm (`location_text`), kỹ năng (`skills_text`), mô tả chi tiết (`description_text`), kinh nghiệm (`experience_text`).

### 4. Cổng Kiểm Tra Chất Lượng Tự Động (Data Quality Gate)
Mỗi DAG gồm 2 task nối tiếp: `crawl_<source>` ➡️ `check_quality_<source>`.
Hệ thống tự động kiểm tra 3 tiêu chí nghiêm ngặt trước khi chấp nhận dữ liệu:
1. Tỷ lệ bản ghi khớp Schema Pydantic $\ge 95\%$ (thực tế đạt 100%).
2. Không chứa bản ghi trùng lặp nội bộ (Tỷ lệ duy nhất = 100%).
3. Các trường thông tin cốt lõi bắt buộc không được để trống (`title`, `company`, `description`).

### 5. Tổ Chức Lưu Trữ Data Lake (Hive-Style Partitioning)
Dữ liệu lưu trữ phân cấp rõ ràng theo thời gian tại thư mục `data/`:
`data/<nguon>/dt=YYYY-MM-DD/batch_001.jsonl`
Giúp dễ dàng phân tích theo chuỗi thời gian (time-series) hoặc nạp vào Big Data / Cloud Data Lake sau này.

---

## IV. ĐỊNH HƯỚNG VỀ CƠ SỞ DỮ LIỆU SQL & KẾ HOẠCH TIẾP THEO

### 1. Vấn Đề Cơ Sở Dữ Liệu SQL
Hiện tại hệ thống đang ở **Tầng 1 (Data Lake)** lưu trữ dữ liệu thô dạng JSONL. Đây là mô hình chuẩn ELT (Extract - Load - Transform).
Để phục vụ phân tích chuyên sâu cho đồ án, nhóm đã chuẩn bị kế hoạch tích hợp **SQL Database (PostgreSQL)** với 2 mục tiêu:
1. **Làm Database cho Airflow (Metadata DB):** Thay thế SQLite bằng PostgreSQL để kích hoạt `LocalExecutor`, cho phép chạy song song nhiều task cùng lúc.
2. **Làm Data Warehouse (Bảng dữ liệu phân tích):** Thiết kế mô hình dữ liệu quan hệ gồm 3 bảng chính:
   - `companies` (id, name, location, website, company_size)
   - `jobs` (id, title, company_id, salary_min, salary_max, experience_level, source, url, posted_date)
   - `job_skills` (job_id, skill_name, category)

### 2. Kế Hoạch Triển Khai Giai Đoạn 2
- **Bước 1 (ETL Pipeline):** Viết thêm Task/DAG đọc dữ liệu JSONL sạch từ Data Lake và `UPSERT` vào PostgreSQL.
- **Bước 2 (NLP & Trích xuất kỹ năng):** Dùng biểu thức chính quy (Regex) và từ điển công nghệ trích xuất chuẩn xác các công nghệ (VD: Python, Java, Docker, React, AWS, Kubernetes, Prompt Engineering,...).
- **Bước 3 (Triển khai Cloud & S3):** Cấu hình đẩy file dữ liệu lên AWS S3 và triển khai toàn bộ hệ thống lên AWS EC2 để chạy tự động 24/7.
- **Bước 4 (Báo cáo & Dashboard):** Xây dựng Dashboard trực quan hóa bằng Streamlit / Power BI giải quyết các bài toán:
  - Top 10 kỹ năng lập trình được săn đón nhiều nhất tại Việt Nam.
  - Phân bổ mức lương theo vị trí và số năm kinh nghiệm.
  - Xu hướng tuyển dụng theo thành phố (TP.HCM, Hà Nội, Đà Nẵng).

---

## V. KỊCH BẢN BÁO CÁO VÀ DEMO NHANH CHO THẦY (3 PHÚT)

Khi thầy yêu cầu kiểm tra hoặc demo thực tế, bạn thực hiện theo 4 bước sau:

1. **Bước 1: Khởi động hệ thống Airflow (1 lệnh)**
   ```bash
   ./scripts/start_airflow.sh
   ```
   *Thuyết minh với thầy:* "Dạ thưa thầy, toàn bộ hệ thống lập lịch tự động của em được quản lý qua Apache Airflow, em đã đóng gói sẵn trong một script để khởi động cả Scheduler và Webserver."

2. **Bước 2: Mở Web UI trình diễn 6 DAGs**
   - Mở trình duyệt vào `http://localhost:8080` (Tài khoản: `admin` / `admin`).
   *Thuyết minh với thầy:* "Ở đây em đã thiết kế 6 DAGs tương ứng với 6 nguồn tuyển dụng lớn ở Việt Nam (TopDev, VietnamWorks, ITviec, TopCV,...). Hệ thống được lập lịch chạy tự động lúc 20:00 hàng ngày xoay vòng theo thứ trong tuần để đảm bảo an toàn mạng."

3. **Bước 3: Show kiểm tra chất lượng dữ liệu tự động**
   ```bash
   python3 scripts/report.py
   ```
   *Thuyết minh với thầy:* "Mỗi khi cào xong, hệ thống của em có một cổng Data Quality Gate tự động kiểm định tính toàn vẹn. Hiện tại em đã cào thử nghiệm được hơn 200 tin từ VietnamWorks, CareerViet và ITviec với tỷ lệ schema hợp lệ đạt 100% và không có tin nào bị trùng lặp."

4. **Bước 4: Show thư mục dữ liệu Data Lake**
   ```bash
   head -n 1 data/vietnamworks/dt=2026-10-06/batch_001.jsonl | jq .
   ```
   *Thuyết minh với thầy:* "Dữ liệu được lưu trữ phân vùng theo ngày (dt=YYYY-MM-DD) chuẩn Data Lake. Mỗi tin việc làm đều được chuẩn hóa qua schema Pydantic với đầy đủ metadata và thông tin chi tiết."
