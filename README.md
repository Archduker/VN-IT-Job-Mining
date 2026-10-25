# **VN IT Job Mining Data Collection System**

Hệ thống thu thập dữ liệu tuyển dụng IT tự động tại Việt Nam theo chuẩn **Modern Data Stack**, điều phối bằng **Apache Airflow**, kiến trúc **Two-Phase Decoupled Crawler** kết hợp **Cloudflare R2 Lakehouse (URL Ledger & Manifests)**, lưu trữ dữ liệu dạng **JSON mảng phân vùng (partitioned)**, kiểm soát chất lượng dữ liệu (**DataQualityChecker**) và chuẩn hóa theo **Data Contract Schema v1**.

---

## 🖥️ Trung Tâm Giám Sát & Điều Phối Toàn Hệ Thống (Central Observatory)

Hệ thống sở hữu trang web UI dashboard hiện đại đặt tại [`monitoring/`](monitoring/) phân chia rõ rệt **Backend (FastAPI)** và **Frontend (React 18 + Vite + Tailwind + Recharts + Plotly 3D)**:

- **Sứ mệnh cốt lõi (Visual Truth Engine)**: *Miêu tả hình ảnh thực tế của toàn bộ dòng chảy dữ liệu thông qua các chỉ số và biểu đồ liên tục, liền mạch theo chuẩn pipeline 3 giai đoạn (`Collection` ➔ `Pre-processing` ➔ `Processing`) để từng bước tinh chế ra **Bộ Dữ Liệu Vàng Hoàn Chỉnh Nhất (Golden Master Dataset)**.*
- **Chiến lược EDA Đa Tầng (Multi-stage EDA)**:
  - *Master Dashboard*: Cung cấp bức tranh toàn cảnh cấp cao về bộ dữ liệu hợp nhất (độ hội tụ schema, phân bổ lương thị trường, top kỹ năng vàng, hệ số làm sạch).
  - *EDA Chi Tiết Từng Giai Đoạn*: Được thiết kế chuyên biệt cho từng bước xử lý dữ liệu (EDA Thô As-Is tại Collection, EDA Regex & Outliers tại Pre-processing, EDA Deduplication & Semantic Drift tại Processing).
- **Phân Tách Rõ Ràng Vận Hành (Decoupled Operations)**:
  - *Crawling Operations*: Giám sát tiến độ cào, URL Ledger manifests, SSE live stream logs, kiểm soát batch run.
  - *EDA Intelligence*: Kiểm kê trường dữ liệu thô (field inventory), đo lường tỷ lệ khuyết thiếu (missingness profiling), và 5 họ biểu đồ khoa học 2D.
- **Giám Sát Apache Airflow Trực Tiếp**:
  - Tự động theo dõi tiến trình sống (PID) của Scheduler và Webserver (Port 8080).
  - Truy vấn trực tiếp SQLite Metadata DB (`airflow/PostgreSQL database (airflow)`) để cập nhật trạng thái của 7 DAGs cào xoay vòng hàng ngày.
- **Hạ Tầng Lưu Trữ Đám Mây Độc Quyền Cloudflare R2**:
  - 100% chuyển sang Cloudflare R2 bucket `vn-it-jobs` (đã loại bỏ hoàn toàn các cấu hình Cloudflare R2/S3 cũ).
  - Tích hợp **R2 Diff Engine & Đồng Bộ 1-Click** giúp kiểm toán chênh lệch giữa ổ đĩa cục bộ và Remote Cloud.
- **Quy Chuẩn Giám Sát Không Đăng Nhập (Zero-Auth Standard)**:
  - Không có bất kỳ form đăng nhập, xác thực hay phân quyền người dùng nào. Đây là bảng điều khiển kỹ thuật nội bộ (Internal Engineering Monitor) tối ưu cho việc quan sát trực tiếp, phản hồi thời gian thực và tự động hóa.
- **Chuẩn Hóa 100% TypeScript (Strictly No JavaScript)**:
  - Toàn bộ frontend, các components, cấu hình (`vite.config.ts`, `tailwind.config.ts`) và models được định kiểu chặt chẽ bằng TypeScript. Khóa cứng `"allowJs": false` trong `tsconfig.json`.
- **API Trung Tâm Điều Hành**: [`GET /api/dashboard`](http://localhost:8000/api/dashboard) (hoặc `/api/v1/dashboard`) và tài liệu Swagger API tại [`http://localhost:8000/docs`](http://localhost:8000/docs).
- **Khởi chạy nhanh 1 lệnh**:
  ```bash
  ./monitoring/run_all.sh
  ```
  Giao diện Web Dashboard truy cập tại `http://localhost:5173`. Quy tắc phát triển xem tại [`.agents/rules/monitoring_system_rules.md`](.agents/rules/monitoring_system_rules.md) và Skill MCP tại [`.agents/skills/mcp-ui-architect/SKILL.md`](.agents/skills/mcp-ui-architect/SKILL.md).

---

## 🔄 Quy Trình Thu Thập Dữ Liệu Từng Bước (Data Collection Pipeline)

Hệ thống triển khai thu thập dữ liệu tự động từ **7 sàn tuyển dụng CNTT** (TopDev, TopCV, VietnamWorks, CareerViet, Vieclam24h, ITviec, Glints & JobsGO) theo quy trình 6 bước chuẩn hóa:

### 🔹 Bước 1: Khởi Tạo Hạ Tầng Lưu Trữ & Cloudflare R2 Lakehouse
- Thiết lập môi trường Python (`.venv`) và các thư viện phụ thuộc.
- Khởi chạy cụm lưu trữ đối tượng **Cloudflare R2 Object Storage** qua Docker (`make minio-up`), cung cấp endpoint S3-compatible tại cổng `:9000` và Console UI tại `:9001`.
- Tự động kiểm tra và khởi tạo bucket `vn-it-jobs` với các vùng dữ liệu: `/manifests` (danh mục URL), `/raw` (dữ liệu cào thô), và `/staging` (dữ liệu tiền xử lý) qua `scripts/setup_minio.py`.

### 🔹 Bước 2: Pha 1 — Vét Sạch URL Không Giới Hạn (Phase 1: URL Discovery)
- Kích hoạt hàm `discover_urls()` trên từng nguồn tuyển dụng để quét toàn bộ phân trang danh mục CNTT mà không giới hạn thời gian đăng.
- Làm sạch URL về dạng chính tắc (Canonical URL): loại bỏ các tham số theo dõi phiên và quảng cáo (`utm_source`, `utm_campaign`, `utm_medium`, `fbclid`, token tracking).
- Ghi nhận danh sách URL vào Cloudflare R2 URL Ledger dưới dạng manifest phân vùng ngày: `manifest_<YYYY-MM-DD>.jsonl`.

### 🔹 Bước 3: Pha 2 — Bóc Tách Chi Tiết & Chống Trùng Lặp (Phase 2: Detail Extraction & CDC)
- Đọc catalog URL từ sổ cái (URL Ledger): chỉ lọc ra các URL có trạng thái `PENDING` hoặc bài viết đã hoàn tất (`DONE`) nhưng đã tồn tại $\ge 21$ ngày để kiểm tra cập nhật (Chu kỳ Re-crawl 21 ngày).
- **Cơ chế Safe Skip (Chịu lỗi an toàn)**: Khi gặp link lỗi mạng (404 Not Found, 500 Server Error, timeout), crawler tự động log cảnh báo và bỏ qua link đó để tiếp tục cào các tin tiếp theo mà không làm sập tiến trình.
- **Băm Cấu Trúc JSON Sau Cào (Post-Crawl Canonical JSON Hashing & CDC)**: Tải nguyên bản dữ liệu thô (Raw As-Is) về Lakehouse, bóc tách cấu trúc trường vào JSON và băm SHA-256 trên dictionary đã chuẩn hóa khóa (`canonical JSON hash`) kèm băm theo từng trường (`salary_hash`, `requirements_hash`, etc.). Cơ chế này miễn nhiễm hoàn toàn với rác động HTML (lượt xem, CSRF, ads) và chỉ rõ chính xác trường nào bị thay đổi giữa các phiên bản.

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

### 2. Khởi động Cloudflare R2 Lakehouse (Docker)
```bash
make minio-up      # Khởi chạy Cloudflare R2 tại :9000 (Console UI: http://localhost:9001)
make setup-minio   # Khởi tạo bucket và cấu trúc Lakehouse
```

### 3. Chạy Crawler theo Kiến Trúc Two-Phase (Discovery & Detail)
```bash
# Phase 1: Vét sạch URL vào Cloudflare R2 URL Ledger
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
3. **Kiến trúc Two-Phase Crawler & Cloudflare R2 Lakehouse (Core 02)**: [`docs/02_crawling_architecture_guide.md`](docs/02_crawling_architecture_guide.md)
4. **Hướng dẫn EDA & Tích hợp dữ liệu đa nguồn (Core 03)**: [`docs/03_eda_and_integration_guide.md`](docs/03_eda_and_integration_guide.md)
5. **Hướng dẫn tự học & vận hành Apache Airflow**: [`docs/03_airflow_guide.md`](docs/03_airflow_guide.md)
6. **Phương pháp chuẩn bóc tách nguồn dữ liệu mới**: [`docs/guides/crawler_analysis_methodology.md`](docs/guides/crawler_analysis_methodology.md)
7. **Hồ sơ phân tích kiến trúc 7 sàn tuyển dụng**: Thư mục [`docs/crawl/`](docs/crawl/) (`topcv.md`, `topdev.md`, `vietnamworks.md`, `careerviet.md`, `vieclam24h.md`, `itviec.md`, `glints.md`).
8. **Antigravity Custom Skill cho AI**: [`.agents/skills/job-crawler-analyzer/SKILL.md`](.agents/skills/job-crawler-analyzer/SKILL.md)

---

## 🕒 Lập Lịch Hai Pha (Two-Phase Decoupled Schedule) trên Airflow
| Phân Loại | Nguồn | DAG ID | Lịch Chạy | Vai Trò |
|:---|:---|:---|:---|:---|
| **Pha 1 (Discovery)** | Cả 8 Sàn IT | `dag_discovery_daily` | `0 5 * * *` (05:00 hàng ngày) | Quét URL mới (sort=new), nạp vào UrlLedger |
| **Pha 2 (Detail)** | TopDev | `crawler_detail_topdev` | `0 9,14,18,21,22 * * *` | Cào chi tiết theo hạn ngạch 30 tin (Xả cuối tuần) |
| **Pha 2 (Detail)** | VietnamWorks | `crawler_detail_vietnamworks` | `0 9,14,18,21,22 * * *` | Cào chi tiết theo hạn ngạch 30 tin (Xả cuối tuần) |
| **Pha 2 (Detail)** | CareerViet | `crawler_detail_careerviet` | `0 9,14,18,21,22 * * *` | Cào chi tiết theo hạn ngạch 30 tin (Xả cuối tuần) |
| **Pha 2 (Detail)** | ViecLam24h | `crawler_detail_vieclam24h` | `0 9,14,18,21,22 * * *` | Cào chi tiết theo hạn ngạch 30 tin (Xả cuối tuần) |
| **Pha 2 (Detail)** | ITviec | `crawler_detail_itviec` | `0 9,14,18,21,22 * * *` | Cào chi tiết theo hạn ngạch 30 tin (Xả cuối tuần) |
| **Pha 2 (Detail)** | TopCV | `crawler_detail_topcv` | `0 9,14,18,21,22 * * *` | Cào chi tiết theo hạn ngạch 30 tin (Xả cuối tuần) |
| **Pha 2 (Detail)** | JobsGO | `crawler_detail_jobsgo` | `0 9,14,18,21,22 * * *` | Cào chi tiết theo hạn ngạch 30 tin (Xả cuối tuần) |
| **Pha 2 (Detail)** | Glints | `crawler_detail_glints` | `0 9,14,18,21,22 * * *` | Cào chi tiết theo hạn ngạch 30 tin (Xả cuối tuần) |


## Cloudflare R2 Lakehouse Guide

- Vận hành Cloudflare R2: [docs/minio_lakehouse_guide.md](docs/minio_lakehouse_guide.md)
- Agent skill: [.agents/skills/minio-lakehouse-guide/SKILL.md](.agents/skills/minio-lakehouse-guide/SKILL.md)
