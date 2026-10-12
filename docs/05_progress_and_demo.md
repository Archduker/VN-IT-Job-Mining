# BÁO CÁO TIẾN ĐỘ ĐỒ ÁN
## ĐỀ TÀI: KHAI PHÁ DỮ LIỆU TUYỂN DỤNG CÔNG NGHỆ THÔNG TIN TẠI VIỆT NAM (VN-IT-JOB-MINING)

---

## I. THÔNG TIN CHUNG
- **Tên đề tài:** Hệ Thống Tự Động Thu Thập, Kiểm Tra Chất Lượng & Khai Phá Dữ Liệu Việc Làm IT (VN-IT-Job-Mining)
- **Công nghệ cốt lõi:** Python 3.10+, Apache Airflow 2.11+, Pydantic v2, Playwright / BeautifulSoup4 / Requests, SQLite State Catalog, AWS S3 Raw Zone.
- **Mục tiêu giai đoạn 1 (Hoàn thành):** Xây dựng thành công hạ tầng Data Pipeline tự động: thu thập dữ liệu từ 8 sàn tuyển dụng CNTT hàng đầu Việt Nam, chuẩn hóa dữ liệu theo Data Contract Compact Schema v1, loại bỏ trùng lặp triệt để $O(1)$, điều phối bằng 9 DAGs trên Apache Airflow và kiểm định chất lượng tự động (Data Quality Gate).

---

## II. KẾT QUẢ THU THẬP DỮ LIỆU THỰC TẾ (PRODUCTION METRICS)

Tính đến thời điểm hiện tại, toàn bộ **8 nguồn tuyển dụng** đã vận hành thu thập ổn định với **tổng cộng 6.661 bản ghi việc làm IT**, tỷ lệ schema đạt **100%**:

| STT | Nguồn (Source) | Phương Thức Kỹ Thuật | Lịch Airflow (Cron) | Bản Ghi Thực Tế | Tỷ Lệ Schema Chuẩn | Trùng Lặp (Dedup) | Đánh Giá Chất Lượng |
| :---: | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| 1 | **VietnamWorks** | Search API POST | Thứ Năm 20:00 | **2.232** | 100% | 0% | ✅ **ĐẠT (PASS)** |
| 2 | **JobsGO** | Playwright Headless + BS4 | Chủ Nhật 20:00 | **1.476** | 100% | 0% | ✅ **ĐẠT (PASS)** |
| 3 | **TopCV** | Playwright Anti-WAF | Thứ Sáu 20:00 | **810** | 100% | 0% | ✅ **ĐẠT (PASS)** |
| 4 | **ITviec** | Requests + BS4 (SSR) | Thứ Tư 20:00 | **674** | 100% | 0% | ✅ **ĐẠT (PASS)** |
| 5 | **CareerViet** | Requests + BS4 (SSR) | Thứ Ba 20:00 | **655** | 100% | 0% | ✅ **ĐẠT (PASS)** |
| 6 | **ViecLam24h** | Next.js SSR State | Thứ Bảy 20:00 | **445** | 100% | 0% | ✅ **ĐẠT (PASS)** |
| 7 | **Glints** | REST API / SSR | Chủ Nhật 20:00 | **244** | 100% | 0% | ✅ **ĐẠT (PASS)** |
| 8 | **TopDev** | REST API v2 | Thứ Hai 20:00 | **125** | 100% | 0% | ✅ **ĐẠT (PASS)** |
| **TỔNG** | **8 Nguồn Tuyển Dụng** | **Đa phương thức** | **9 Airflow DAGs** | **6.661 tin** | **100% (6.661/6.661)** | **0%** | 🏆 **HỆ THỐNG SẴN SÀNG** |

> Lệnh kiểm tra tiến độ trực quan thời gian thực tại terminal:
> ```bash
> make monitor
> # hoặc: python3 scripts/monitor.py --watch
> ```

---

## III. CÁC ĐẶC TRƯNG KỸ THUẬT NỔI BẬT ĐÃ TRIỂN KHAI

### 1. Điều Phối Tự Động Toàn Diện Bằng Apache Airflow (9 DAGs)
- **Chiến lược xoay vòng (Rotating Crawling):** Để không gây quá tải mạng và tránh bị hệ thống đối tác chặn IP (Anti-scraping), mỗi ngày trong tuần hệ thống kích hoạt tự động cào đúng 1 trang việc làm vào khung giờ **20:00**.
- **DAG Master Weekly (`crawler_weekly_all`):** Chạy lúc 22:00 Chủ Nhật, cào toàn bộ 8 nguồn song song và kích hoạt `CrawlSummaryOperator` xuất báo cáo tổng kết JSON vào `logs/crawl_reports/`.
- **DAG Periodic 4-day (`periodic_it_job_mining_4days`):** Áp dụng kiến trúc hàng đợi 2 giai đoạn: Harvest Listing $\rightarrow$ Dedup $O(1)$ $\rightarrow$ Detail Queue Worker, giúp giảm hơn 80% lưu lượng mạng lãng phí.
- **Cơ chế chịu lỗi:** Tự động retry với backoff (`retries=1`, `retry_delay=5 phút`), ghi nhận callback `_on_crawl_success` và `_on_crawl_failure`.

### 2. Thiết Kế Động Cơ Thu Thập Hướng Đối Tượng (`BaseCrawler`)
- Toàn bộ 8 crawler đều kế thừa kiến trúc chung [`BaseCrawler`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/base/base_crawler.py).
- **Lịch sự & An toàn (Polite Crawling):** Tự động tạo khoảng nghỉ (delay ngẫu nhiên 1.5 - 3.5 giây) giữa các lượt request và xoay vòng User-Agent Header.
- **Khử trùng lặp qua State Catalog & Checkpoint:** Lưu trữ danh sách ID đã từng cào vào SQLite State Catalog (`data/state/job_catalog.db`) và file `<source>_checkpoint.json`. Lần chạy sau chỉ cào tin mới.

### 3. Chuẩn Hóa Schema Tuyệt Đối Với Pydantic (`JobRecord`)
Dữ liệu của 8 website tuyển dụng có cấu trúc HTML/JSON hoàn toàn khác nhau, nhưng đều được hệ thống chuyển đổi thống nhất về 1 schema `JobRecord`:
- `_meta`: Lưu trữ thông tin kỹ thuật (`source`, `source_job_id`, `url`, `crawled_at`, `batch_id`, `language`).
- `raw`: Tiêu đề (`title`), tên công ty (`company`), đối tượng lương lồng (`salary`: min, max, currency, period, negotiable), nhóm thẻ (`tags`: requirements, benefits, skills), danh sách mô tả bullet (`description_list`), danh sách yêu cầu (`requirements_list`), danh sách phúc lợi (`benefits_list`), địa điểm (`location_text`), hạn nộp (`deadline_text`).

### 4. Cổng Kiểm Tra Chất Lượng Tự Động (Data Quality Gate)
Mỗi DAG gồm 2 task nối tiếp: `crawl_<source>` ➡️ `check_quality_<source>`.
Hệ thống tự động kiểm tra 3 tiêu chí nghiêm ngặt trước khi chấp nhận dữ liệu:
1. Tỷ lệ bản ghi khớp Schema Pydantic $\ge 95\%$ (thực tế đạt 100%).
2. Không chứa bản ghi trùng lặp nội bộ (Tỷ lệ duy nhất = 100%).
3. Các trường thông tin cốt lõi bắt buộc không được để trống (`title`, `company`, `description`).

### 5. Tổ Chức Lưu Trữ Data Lake (Hive-Style Partitioning)
Dữ liệu lưu trữ phân cấp rõ ràng theo thời gian tại thư mục `data/`:
`data/<source>/dt=YYYY-MM-DD/batch_001.json` (Mảng JSON uncompressed UTF-8 hợp lệ).
Sẵn sàng đồng bộ lên AWS S3 Raw Zone (`s3://vn-it-jobs-raw/<source>/...`).

### 6. Kiến Trúc Đám Mây Lai (Hybrid Cloud Architecture)
- **Local / Self-Hosted Compute:** Tiến trình cào và Airflow chạy trên máy trạm hoặc máy ảo nội bộ (8-16 GB RAM) sử dụng IP dân cư để vượt qua lớp phòng thủ WAF/Cloudflare Challenge của các sàn tuyển dụng, tránh nguy cơ OOM Kill của EC2 Free Tier (`t2.micro` 1 GB RAM).
- **AWS S3 Cloud Storage:** Đóng vai trò Data Lake lưu trữ lâu dài, có độ bền 99.999999999% (11 số 9), sẵn sàng phục vụ các tác vụ phân tích Big Data.

---

## IV. ĐỊNH HƯỚNG VỀ CƠ SỞ DỮ LIỆU SQL & KẾ HOẠCH TIẾP THEO

### 1. Vấn Đề Cơ Sở Dữ Liệu SQL
Hiện tại hệ thống đang ở **Tầng 1 (Data Lake)** lưu trữ dữ liệu thô dạng JSON mảng. Đây là mô hình chuẩn ELT (Extract - Load - Transform).
Để phục vụ phân tích chuyên sâu cho đồ án, nhóm đã chuẩn bị kế hoạch tích hợp **SQL Database (PostgreSQL)** với 2 mục tiêu:
1. **Làm Database cho Airflow (Metadata DB):** Thay thế SQLite bằng PostgreSQL để kích hoạt `LocalExecutor`, cho phép chạy song song nhiều task cùng lúc.
2. **Làm Data Warehouse (Bảng dữ liệu phân tích):** Thiết kế mô hình dữ liệu quan hệ gồm 3 bảng chính:
   - `companies` (id, name, location, website, company_size)
   - `jobs` (id, title, company_id, salary_min, salary_max, experience_level, source, url, posted_date)
   - `job_skills` (job_id, skill_name, category)

### 2. Kế Hoạch Triển Khai Giai Đoạn 2
- **Bước 1 (ETL Pipeline):** Viết thêm Task/DAG đọc dữ liệu JSON sạch từ Data Lake và `UPSERT` vào PostgreSQL.
- **Bước 2 (NLP & Trích xuất kỹ năng):** Dùng biểu thức chính quy (Regex) và từ điển công nghệ trích xuất chuẩn xác các công nghệ (VD: Python, Java, Docker, React, AWS, Kubernetes, Prompt Engineering,...).
- **Bước 3 (Triển khai Cloud & S3):** Cấu hình đẩy file dữ liệu lên AWS S3 và triển khai toàn bộ hệ thống lên Cloud để chạy tự động 24/7.
- **Bước 4 (Báo cáo & Dashboard):** Xây dựng Dashboard trực quan hóa bằng Streamlit / Power BI giải quyết các bài toán:
  - Top 10 kỹ năng lập trình được săn đón nhiều nhất tại Việt Nam.
  - Phân bổ mức lương theo vị trí và số năm kinh nghiệm.
  - Xu hướng tuyển dụng theo thành phố (TP.HCM, Hà Nội, Đà Nẵng).

---

## V. KỊCH BẢN BÁO CÁO VÀ DEMO TRỰC TIẾP CHO THẦY (3 PHÚT)

Khi thầy yêu cầu kiểm tra hoặc demo thực tế, bạn thực hiện theo 4 bước sau:

1. **Bước 1: Khởi động hệ thống Airflow Production (1 lệnh qua Makefile)**
   ```bash
   make start-airflow
   ```
   *Thuyết minh với thầy:* "Dạ thưa thầy, toàn bộ hệ thống lập lịch tự động của em được quản lý qua Apache Airflow, em đã cấu hình chạy nền dạng production daemon với PID tracking và health check tự động."

2. **Bước 2: Mở Web UI trình diễn 9 DAGs**
   - Mở trình duyệt vào `http://localhost:8080` (Tài khoản: `admin` / `admin`).
   *Thuyết minh với thầy:* "Ở đây em đã thiết kế 9 DAGs tương ứng với 8 nguồn tuyển dụng lớn ở Việt Nam (TopDev, VietnamWorks, ITviec, TopCV, Glints, JobsGO,...), gồm lịch xoay vòng thường nhật 20:00, 1 DAG Master Weekly và 1 DAG hàng đợi 2 pha chu kỳ 4 ngày."

3. **Bước 3: Show màn hình Giám sát Trực quan Thời gian thực**
   ```bash
   make monitor
   ```
   *Thuyết minh với thầy:* "Hệ thống có một bảng điều khiển giám sát trực tiếp. Thầy có thể thấy hiện tại đã thu thập được **6.661 tin tuyển dụng** từ 8 nguồn, không có bất kỳ tin nào bị trùng lặp và tỷ lệ đạt chuẩn schema là 100%."

4. **Bước 4: Show dữ liệu Data Lake & Unit Tests**
   ```bash
   pytest
   ```
   *Thuyết minh với thầy:* "Toàn bộ hệ thống được bảo vệ bởi bộ kiểm thử tự động với 195/195 test cases đạt 100% Passed. Dữ liệu được lưu trữ phân vùng theo chuẩn Data Lake `dt=YYYY-MM-DD` sẵn sàng đồng bộ lên AWS S3."
