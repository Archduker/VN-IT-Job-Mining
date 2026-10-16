# **VN IT Job Mining Data Collection System**

Hệ thống thu thập dữ liệu tuyển dụng IT tự động tại Việt Nam theo chuẩn **Modern Data Stack**, điều phối bằng **Apache Airflow**, kiến trúc **Two-Phase Decoupled Crawler** kết hợp **MinIO Lakehouse (URL Ledger & Manifests)**, lưu trữ dữ liệu dạng **JSON mảng phân vùng (partitioned)**, kiểm soát chất lượng dữ liệu (**DataQualityChecker**) và chuẩn hóa theo **Data Contract Schema v1**.

---

## 🔄 Quy Trình Thu Thập Dữ Liệu Từng Bước (Data Collection Pipeline)

Hệ thống triển khai thu thập dữ liệu tự động từ **7 sàn tuyển dụng CNTT** (TopDev, TopCV, VietnamWorks, CareerViet, Vieclam24h, ITviec, Glints & JobsGO) theo quy trình 6 bước chuẩn hóa:

### 🔹 Bước 1: Khởi Tạo Hạ Tầng Lưu Trữ & MinIO Lakehouse
- Thiết lập môi trường Python (`.venv`) và các thư viện phụ thuộc.
- Khởi chạy cụm lưu trữ đối tượng **MinIO Object Storage** qua Docker (`make minio-up`), cung cấp endpoint S3-compatible tại cổng `:9000` và Console UI tại `:9001`.
- Tự động kiểm tra và khởi tạo bucket `vn-it-jobs` với các vùng dữ liệu: `/manifests` (danh mục URL), `/raw` (dữ liệu cào thô), và `/staging` (dữ liệu tiền xử lý) qua `scripts/setup_minio.py`.

### 🔹 Bước 2: Pha 1 — Vét Sạch URL Không Giới Hạn (Phase 1: URL Discovery)
- Kích hoạt hàm `discover_urls()` trên từng nguồn tuyển dụng để quét toàn bộ phân trang danh mục CNTT mà không giới hạn thời gian đăng.
- Làm sạch URL về dạng chính tắc (Canonical URL): loại bỏ các tham số theo dõi phiên và quảng cáo (`utm_source`, `utm_campaign`, `utm_medium`, `fbclid`, token tracking).
- Ghi nhận danh sách URL vào MinIO URL Ledger dưới dạng manifest phân vùng ngày: `manifest_<YYYY-MM-DD>.jsonl`.

### 🔹 Bước 3: Pha 2 — Bóc Tách Chi Tiết & Chống Trùng Lặp (Phase 2: Detail Extraction & CDC)
- Đọc catalog URL từ sổ cái (URL Ledger): chỉ lọc ra các URL có trạng thái `PENDING` hoặc bài viết đã hoàn tất (`DONE`) nhưng đã tồn tại $\ge 21$ ngày để kiểm tra cập nhật (Chu kỳ Re-crawl 21 ngày).
- **Cơ chế Safe Skip (Chịu lỗi an toàn)**: Khi gặp link lỗi mạng (404 Not Found, 500 Server Error, timeout), crawler tự động log cảnh báo và bỏ qua link đó để tiếp tục cào các tin tiếp theo mà không làm sập tiến trình.
- **Tính toán Clean Container HTML Hash**: Bóc tách riêng khối nội dung chi tiết bài viết (loại trừ các thành phần giao diện động như widget đề xuất, banner quảng cáo, số lượt xem) và băm SHA-256 để phát hiện nội dung có thực sự thay đổi hay không (Change Data Capture - CDC Versioning), ngăn chặn việc tăng version oan.

### 🔹 Bước 4: Chuẩn Hóa Schema & Ghi Dữ Liệu Phân Vùng (Schema Normalization & Storage)
- Ép toàn bộ dữ liệu bóc tách được từ 7 sàn về thống nhất theo **Data Contract Schema v1** (`JobRecord` gồm metadata kỹ thuật `_meta` và nội dung nghiệp vụ `raw`):
  - **Mức lương lồng nhau (`JobSalary`)**: Bóc tách số học `salary_min`, `salary_max`, `salary_currency` và chu kỳ thanh toán `pay_period`.
  - **Phân nhóm thẻ tags (`JobTags`)**: Phân tách có ngữ nghĩa thành 3 nhóm riêng biệt (`requirements`, `benefits`, `skills`).
  - **Làm sạch văn bản**: Loại bỏ thẻ HTML và chuẩn hóa các dòng bullet (`•`, `-`, `*`) thành mảng chuỗi sạch `description_list`, `requirements_list`, `benefits_list`.
  - **Nhận diện ngôn ngữ**: Tự động gán nhãn `language: "vi"` hoặc `"en"` vào metadata.
- Ghi dữ liệu dạng mảng JSON chuẩn UTF-8 ra thư mục phân vùng thời gian: `data/<source>/dt=YYYY-MM-DD/batch_XXX.json` (sử dụng cơ chế ghi nguyên tử Atomic Write qua file `.tmp` để chống hỏng file khi mất điện/dừng đột ngột).

### 🔹 Bước 5: Kiểm Định Toàn Vẹn Dữ Liệu Tự Động (Data Quality Gate)
- Mỗi lô dữ liệu sau khi xuất file được tự động kiểm tra nghiêm ngặt qua `DataQualityChecker`:
  - Tỷ lệ bản ghi hợp lệ theo Pydantic Schema $\ge 95\%$ (thực tế toàn hệ thống đạt 100%).
  - Tỷ lệ trùng lặp khóa `dedup_key` = 0% (tính duy nhất đạt 100%).
  - Các trường cốt lõi bắt buộc không được phép để trống (`title`, `company`, `description_list`).
  - Nếu không vượt qua kiểm định, task kiểm tra chất lượng sẽ phát tín hiệu fail và dừng pipeline để kỹ sư can thiệp.

### 🔹 Bước 6: Điều Phối Tự Động Hóa Với Apache Airflow (Automated Scheduling)
- Vận hành 7 DAGs tương ứng với 7 nền tảng việc làm, được lập lịch chạy xoay vòng tự động vào khung giờ **20:00 hàng ngày** để tránh nghẽn mạng và chống bị sàn chặn IP.
- Mỗi DAG liên kết chặt chẽ 2 task kế tiếp nhau: `JobCrawlerOperator` (cào và đẩy đường dẫn file qua XCom) ➡️ `DataQualityOperator` (kéo đường dẫn file từ XCom và thẩm định chất lượng).

---

## 📦 Cài Đặt & Chạy Thử Nghiệm

### 1. Kích hoạt môi trường
```bash
source .venv/bin/activate
export PYTHONPATH=.
```

### 2. Khởi động MinIO Lakehouse (Docker)
MinIO AIStor cần license. Đăng ký Free Tier tại trang [MinIO AIStor](https://min.io/pricing), tải license và đặt tại `secrets/minio.license` (thư mục này đã được Git bỏ qua, không commit license).

```bash
make minio-up      # Khởi chạy MinIO AIStor tại :9000 (Console UI: http://localhost:9001)
make setup-minio   # Tạo bucket vn-it-jobs và cấu trúc Lakehouse
```

Đăng nhập Console bằng `minioadmin` / `minioadmin` (mặc định chỉ dùng local; có thể đặt `MINIO_ROOT_USER` và `MINIO_ROOT_PASSWORD` trong `.env`). Nếu không chạy script setup, hãy tự tạo bucket `vn-it-jobs` trong Console.

### 3. Chạy Crawler theo Kiến Trúc Two-Phase (Discovery & Detail)
```bash
# Phase 1: Vét sạch URL vào MinIO URL Ledger
python run.py --source topcv --phase discover
python run.py --source topdev --phase discover

# Phase 2: Cào chi tiết có bọc Safe Skip & Re-crawl 21 ngày
python run.py --source topcv --phase detail --batch-size 50
python run.py --source topdev --phase detail --batch-size 50
```

Hoặc chạy từng crawler độc lập:
```bash
python crawlers/sources/topcv/crawler.py --max-items 30
python crawlers/sources/topdev/crawler.py --max-items 30
python crawlers/sources/vietnamworks/crawler.py --max-items 50
python crawlers/sources/careerviet/crawler.py --max-items 30
python crawlers/sources/vieclam24h/crawler.py --max-items 30
python crawlers/sources/itviec/crawler.py --max-items 30
python crawlers/sources/glints/crawler.py --max-items 30
```

### 4. Xem báo cáo tiến độ thu thập
```bash
python scripts/report.py
```

### 5. Chạy Toàn Bộ Unit Tests
```bash
pytest tests/unit/ -v
```
Toàn bộ **130/130 test cases** đạt trạng thái **100% Passed**.

---

## 📚 Bộ Tài Liệu Quy Trình & Kiến Trúc Cốt Lõi

1. **Bảng phân công nhiệm vụ & Tiêu chuẩn nghiệm thu (DoD)**: [`TASKS.md`](TASKS.md)
2. **Tổng quan Data Mining & CRISP-DM hiện đại (Core 01)**: [`docs/01_modern_data_mining_overview.md`](docs/01_modern_data_mining_overview.md)
3. **Kiến trúc Two-Phase Crawler & MinIO Lakehouse (Core 02)**: [`docs/02_crawling_architecture_guide.md`](docs/02_crawling_architecture_guide.md)
4. **Hướng dẫn EDA & Tích hợp dữ liệu đa nguồn (Core 03)**: [`docs/03_eda_and_integration_guide.md`](docs/03_eda_and_integration_guide.md)
5. **Hướng dẫn tự học & vận hành Apache Airflow**: [`docs/03_airflow_guide.md`](docs/03_airflow_guide.md)
6. **Phương pháp chuẩn bóc tách nguồn dữ liệu mới**: [`docs/guides/crawler_analysis_methodology.md`](docs/guides/crawler_analysis_methodology.md)
7. **Hồ sơ phân tích kiến trúc 7 sàn tuyển dụng**: Thư mục [`docs/crawl/`](docs/crawl/) (`topcv.md`, `topdev.md`, `vietnamworks.md`, `careerviet.md`, `vieclam24h.md`, `itviec.md`, `glints.md`).
8. **Antigravity Custom Skill cho AI**: [`.agents/skills/job-crawler-analyzer/SKILL.md`](.agents/skills/job-crawler-analyzer/SKILL.md)

---

## 🕒 Rotating Daily Schedule trên Airflow
| Ngày | Nguồn | DAG ID | Lịch Chạy |
|:---|:---|:---|:---|
| Thứ Hai | **TopDev** | `crawler_topdev` | `0 20 * * 1` |
| Thứ Ba | **CareerViet** | `crawler_careerviet` | `0 20 * * 2` |
| Thứ Tư | **ITviec** | `crawler_itviec` | `0 20 * * 3` |
| Mỗi ngày | **VietnamWorks** | `crawler_vietnamworks` | `0 20 * * *` (20:00 giờ Việt Nam) |
| Thứ Sáu | **TopCV** | `crawler_topcv` | `0 20 * * 5` |
| Thứ Bảy | **ViecLam24h** | `crawler_vieclam24h` | `0 20 * * 6` |
| Chủ Nhật | **Glints** | `crawler_glints` | `0 20 * * 0` |
