# VN-IT-Job-Mining: Nền Tảng Thu Thập & Tiền Xử Lý Dữ Liệu Tuyển Dụng IT Việt Nam

> **Hệ thống Khai phá & Tích hợp Dữ liệu Tuyển dụng CNTT Chuẩn Modern Data Stack**  
> Kiến trúc phân tầng **Two-Phase Decoupled Crawler** kết hợp **Cloudflare R2 Data Lakehouse**, điều phối tự động qua **Apache Airflow**, và chuỗi tiền xử lý tinh chế dữ liệu thông minh ứng dụng **GenAI (Gemini 1.5 Flash)** tạo nên **Bộ Dữ Liệu Vàng (Golden Master Dataset)**.

---

## 🌟 Tổng Quan Kiến Trúc 2 Giai Đoạn (End-to-End Pipeline)

Hệ thống được thiết kế theo ranh giới đanh thép (**Ironclad Boundaries**) giữa 2 giai đoạn độc lập: **Data Collection** (Thu thập dữ liệu thô nguyên bản) và **Data Preprocessing** (Tiền xử lý, Tích hợp Silver và Tinh chế Golden Master Dataset).

```text
+----------------------------------------------------------------------------------------------------+
|                         KIẾN TRÚC TỔNG THỂ DÒNG CHẢY DỮ LIỆU (DATA MINING PIPELINE)                 |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [GIAI ĐOẠN 1: DATA COLLECTION (THU THẬP NGUYÊN BẢN & EDA THÔ)]                                    |
|  * 8 Sàn IT: TopCV, TopDev, VietnamWorks, CareerViet, Vieclam24h, ITviec, Glints, JobsGO            |
|  * Phase 1: URL Discovery -> Làm sạch Canonical URL -> Cloudflare R2 URL Ledger (JSONL/Parquet)    |
|  * Phase 2: Detail Extraction -> Safe Skip -> RawJobEnvelope (Metadata + Raw Payload)              |
|  * Kiểm soát: Chu kỳ Re-crawl 21 ngày, băm Canonical JSON Hash SHA-256 (CDC)                       |
|  * Bệnh án dữ liệu: 8 Notebooks Jupyter EDA chẩn đoán 5 trụ cột lỗi (WHAT - WHY - HOW)             |
|                                     │                                                              |
|                                     ▼ (9,390 files JSON thô tại r2://vn-it-jobs/raw/)              |
|                                                                                                    |
|  [GIAI ĐOẠN 2: DATA PREPROCESSING (TIỀN XỬ LÝ & TÍCH HỢP GOLDEN DATASET)]                          |
|  * Giao thức EDA-First: Bắt buộc đọc Bệnh án EDA trước khi can thiệp mã nguồn                      |
|  * Step 1: Schema Mapping & JSON Flattening -> Ép phẳng JSON về Single Flat Staging Table (20 cột) |
|  * Step 2: Data Transformation -> Cascade Salary Parser (Regex + JD Scanner), USD->VND, Parse Date|
|  * Step 3: Text & Skill Processing -> Bullet Stitching, 12 Job Families (SD2), ESCO Taxonomy (SD3) |
|  * Step 4: Missing Values -> Bóc trần 9+ Sneaky Null Markers, bảo toàn MNAR, GenAI JD Imputer     |
|  * Step 5: Outlier & Quality Rules -> Kiểm định IQR, sửa 3 lỗi nhập liệu số, Winsorization P1-P99  |
|  * Step 6: Deduplication & Record Linkage -> Blocking + Cosine Semantic Match -> Golden Record    |
|  * Step 7: Master Pipeline Orchestrator -> Xuất bản chuẩn Bộ 3 Deliverables lên Lakehouse          |
|                                     │                                                              |
|                                     ▼                                                              |
|  [ĐẦU RA CUỐI CÙNG: GOLDEN MASTER DATASET] (curated_golden_flat_jobs.parquet)                     |
|  Sẵn sàng phục vụ trọn vẹn 5 bài toán khai phá chuyên sâu: SD1 - SD5                               |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

---

## 🛠️ Công Nghệ Sử Dụng (Tech Stack Matrix)

| Lớp Kiến Trúc (Layer) | Công Nghệ & Thư Viện Chính | Mục Đích Kỹ Thuật |
| :--- | :--- | :--- |
| **Ngôn Ngữ & Môi Trường** | **Python 3.12**, **TypeScript (ES2022)** | Nền tảng thực thi backend, data pipelines và giao diện giám sát |
| **Lưu Trữ Lakehouse** | **Cloudflare R2 Object Storage** (S3 API), **Parquet**, **JSONL** | Lưu trữ đối tượng đám mây phân tầng (`url_ledger/`, `raw/`, `staging/`, `curated/`) |
| **Điều Phối & Lập Lịch** | **Apache Airflow 2.8+** | Tự động hóa lịch cào Discovery hàng ngày & Detail định kỳ theo hạn ngạch |
| **Công Cụ Thu Thập** | **Playwright**, **HTTPX**, **BeautifulSoup4**, **Selectolax** | Thu thập SSR DOM, Next.js hydration data, Algolia Search API, GraphQL API |
| **Xử Lý Dữ Liệu & Query**| **DuckDB**, **Polars**, **Pandas**, **NumPy** | Đọc ghi Parquet tốc độ cao, xử lý vector hóa và ép phẳng dữ liệu quy mô lớn |
| **AI / NLP & Text Mining**| **Google Gemini API (`gemini-1.5-flash`)**, **Sentence-Transformers** | Bù khuyết văn bản JD, trích xuất kỹ năng ngầm định, tính Cosine Similarity |
| **Kiểm Định & Thống Kê** | **Scikit-learn**, **Tukey's IQR Fences**, **Pydantic v2**, **Pytest** | Phát hiện ngoại lai, kiểm soát hợp lệ Data Contract, kiểm thử toàn trình |
| **Trung Tâm Giám Sát (UI)**| **FastAPI**, **React 18**, **Vite**, **Tailwind CSS**, **Recharts**, **Plotly 3D** | Dashboard điều hành kỹ thuật thời gian thực, trực quan hóa 2D/3D |

---

## 📥 GIAI ĐOẠN 1: DATA COLLECTION (Thu Thập Dữ Liệu Thô & EDA)

### 1. Phạm Vi 8 Sàn Tuyển Dụng IT
Hệ thống kết nối và thu thập dữ liệu chuyên sâu từ 8 sàn việc làm hàng đầu Việt Nam:
1. **TopCV:** Phân tích SSR HTML, bóc tách cấu trúc 3 nhóm tags (`requirements`, `benefits`, `skills`) và xử lý dải lương một đầu.
2. **TopDev:** Khai thác REST API (`/api/v1/jobs`), chuẩn hóa danh mục công nghệ và địa điểm làm việc.
3. **VietnamWorks:** Tích hợp Algolia Search API, xử lý payload đa tầng và bóc tách dải lương chuyên gia.
4. **CareerViet:** Bóc tách DOM SSR, phân rã mảng chuỗi hỗn hợp trong `detail-box`.
5. **Vieclam24h:** Khai thác dữ liệu Next.js (`__NEXT_DATA__`) và giải quyết hiện tượng văn bản bullet bị ngắt dòng.
6. **ITViec:** Vượt Cloudflare nhẹ qua Playwright, khai thác trường lương ngầm định `baseSalary` trong `JSON-LD`.
7. **Glints:** Tương tác GraphQL API, xử lý mảng kỹ năng và dải lương đa tiền tệ (USD/VND).
8. **JobsGO:** Duyệt SSR DOM, chuẩn hóa form thuộc tính và danh mục đãi ngộ.

### 2. Kiến Trúc Two-Phase Decoupled Crawler
- **Pha 1 (URL Discovery):** Quét qua toàn bộ phân trang tìm kiếm việc làm CNTT, không giới hạn thời gian đăng tin. Làm sạch URL về dạng chính tắc (**Canonical URL** — loại bỏ các token rác `utm_*`, `fbclid`), đồng bộ vào URL Ledger Manifests trên Cloudflare R2: `manifest_<YYYY-MM-DD>.jsonl`.
- **Pha 2 (Detail Extraction & CDC):**
  - Đọc catalog URL: Chỉ cào các link có trạng thái `PENDING` hoặc bài viết đã hoàn tất (`DONE`) nhưng đã đủ $\ge 21$ ngày (Chu kỳ **Re-crawl 21 ngày**).
  - **Cơ chế Safe Skip (Chịu lỗi an toàn):** Bắt ngoại lệ 404/500/timeout tại từng link, tự động ghi log và bỏ qua mà không làm dừng tiến trình chung.
  - **Post-Crawl Canonical JSON Hashing:** Lưu dữ liệu thô nguyên bản (`RawJobEnvelope`: `metadata` + `raw_payload`), thực hiện băm SHA-256 trên dictionary chuẩn hóa khóa để kiểm soát biến động nội dung và reposting xuyên thời gian.

### 3. Khám Phá Dữ Liệu Thô (EDA Intelligence & Bệnh Án 5 Trụ Cột)
Hệ thống xây dựng **8 Jupyter Notebooks chuẩn mực (`collection/reports/EDA_<source>.ipynb`)** đóng vai trò là "Kính hiển vi chẩn đoán chất lượng dữ liệu":
- **Trụ cột 1 (Completeness):** Bóc trần các null markers trá hình (`""`, `"nan"`, `"null"`, `"n/a"`, `"0"`, `"thỏa thuận"`).
- **Trụ cột 2 (Validity):** Đo lường tính hợp lệ kiểu dữ liệu, định dạng lương đa tiền tệ, lương năm, và dữ liệu lồng nhau.
- **Trụ cột 3 (Uniqueness):** Đo lường tỷ lệ trùng lặp URL và trùng lặp logic theo cặp `(tiêu đề + công ty)`.
- **Trụ cột 4 (Distribution & Outliers):** Đo Skewness (+5.36), Kurtosis (+32.39), dải phân vị IQR Bounds và định vị 3 lỗi nhập liệu số.
- **Trụ cột 5 (Bias & Balance):** Đánh giá mức độ mất cân bằng cấp bậc (Seniority) và độ thiên lệch địa lý.
- **Chương 7 (Preprocessing Blueprint):** Đưa ra khuyến nghị kỹ thuật WHAT — WHY — HOW làm cơ sở trực tiếp cho giai đoạn tiền xử lý.

---

## ⚙️ GIAI ĐOẠN 2: DATA PREPROCESSING (Tiền Xử Lý & Tinh Chế Golden Dataset)

### 1. Nguyên Tắc Chẩn Đoán Tiên Quyết (EDA-First Protocol)
Khác với các pipeline truyền thống áp dụng công thức "mò mẫm" cho mọi nguồn, hệ thống bắt buộc áp dụng giao thức **Chẩn đoán Tiên quyết**:
- Trước khi thực thi bất kỳ logic tiền xử lý nào, hệ thống sử dụng công cụ [`scripts/read_eda_diagnosis.py`](scripts/read_eda_diagnosis.py) để trích xuất nhanh 5 phân vùng lỗi kỹ thuật (WHAT - WHY - HOW) và Preprocessing Blueprint từ notebook EDA của sàn đó (tiết kiệm $95\%$ token so với việc đọc toàn bộ notebook).
- Mọi luật regex lương, danh sách null markers hay ngưỡng phân vị IQR đều được cấu hình bám sát bệnh án thực tế của từng sàn.

### 2. Chuỗi Xử Lý 7 Bước Liên Hoàn

```text
+----------------------------------------------------------------------------------------------------+
|                         CHUỖI TIỀN XỬ LÝ & TINH CHẾ DỮ LIỆU LIÊN HOÀN (7 BƯỚC)                     |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [BƯỚC 1: INTEGRATION - ÉP PHẲNG JSON ĐA NGUỒN]                                                    |
|  * json_flattener.py: Phân rã toàn bộ nested dict, json-ld, array, detail-box                     |
|  * Tạo khóa toàn cục job_id_global = f"{source}_{job_id}"                                          |
|  * Đưa về Single Flat Staging Table (20 cột phẳng), mảng skills_list, benefits_list chuẩn Python   |
|                                     │                                                              |
|                     ┌───────────────┴───────────────┐                                              |
|                     ▼                               ▼                                              |
|  [BƯỚC 2: TRANSFORMATION]              [BƯỚC 3: TEXT & SKILL PROCESSING]                          |
|  * Cascade Salary Parser:              * Bullet Stitching: Nối dòng văn bản đứt gãy                |
|    - Tầng 1: Header Regex              * Text Cleaner: Bỏ HTML rác, emoji, tag [HN], [HCM]         |
|    - Tầng 2: JD Regex Scanner          * Taxonomy: Phân loại 12 Job Families chuẩn (SD2)           |
|    - Tầng 3: GenAI Fallback            * Seniority: Chuẩn hóa 6 cấp bậc (Intern -> Lead/Mgr)       |
|  * Quy đổi USD->VND (25,400)           * ESCO IT Taxonomy: Chuẩn hóa biến thể kỹ năng (SD3)        |
|  * Chuẩn hóa lương năm (/12), ngày ISO                                                             |
|                     │                               │                                              |
|                     └───────────────┬───────────────┘                                              |
|                                     ▼                                                              |
|  [BƯỚC 4: MISSING VALUES & GENAI IMPUTATION]                                                       |
|  * sneaky_null_detector.py: Bóc trần 9+ null markers ('thỏa thuận', '0', '[]', '…')                |
|  * Missing Not At Random (MNAR): Lương thỏa thuận giữ NaN nhưng bật cờ is_salary_negotiable = 1    |
|  * GenAI Imputer: Gemini 1.5 Flash đọc JD bù khuyết kinh nghiệm, cấp bậc, thành phố, kỹ năng       |
|  * Gắn cờ kiểm toán: is_imputed_by_genai = True, confidence_score >= 0.85                          |
|                                     │                                                              |
|                                     ▼                                                              |
|  [BƯỚC 5: OUTLIER & QUALITY RULES]                                                                 |
|  * Kiểm định khoảng phân vị IQR (Tukey's Fences) cho lương và kinh nghiệm                          |
|  * Tự động nhận diện & sửa 3 lỗi nhập liệu số (USD gõ vào VND, over-zeroing, lương năm vào tháng)  |
|  * Winsorization Capping (P1 - P99): Không drop hàng để bảo toàn hồ sơ kỹ năng                     |
|  * Quality Rules: Kiểm tra ràng buộc logic, tính chỉ số chất lượng quality_score                   |
|                                     │                                                              |
|                                     ▼                                                              |
|  [BƯỚC 6: DEDUPLICATION & RECORD LINKAGE]                                                          |
|  * Cấp 1 (Blocking): Nhóm theo (normalized_company, primary_city, job_family)                       |
|  * Cấp 2 (Matching): Tính độ tương đồng tiêu đề (Jaro-Winkler) và Cosine Similarity JD (>= 0.88)   |
|  * Golden Record Resolver: Áp dụng Survivorship Rules chọn bản ghi đại diện hoàn chỉnh nhất       |
|  * Gán cluster_id, cờ is_duplicate = True, lưu vết source_platforms                                |
|                                     │                                                              |
|                                     ▼                                                              |
|  [BƯỚC 7: PIPELINE ORCHESTRATION & LAKEHOUSE PUBLISHING]                                           |
|  * master_pipeline.py: Điều phối liên hoàn 6 bước, hỗ trợ chạy đơn nguồn hoặc gộp 8 sàn            |
|  * Xuất bản chuẩn Bộ 3 Deliverables sau xử lý cho từng nguồn và bộ dữ liệu hợp nhất                |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

### 3. Chuẩn Xuất Bản Bộ 3 Tài Liệu Sau Xử Lý (The 3-Deliverables Standard)
Mỗi sàn tuyển dụng sau khi đi qua pipeline tiền xử lý đều xuất bản đúng 3 tài liệu chuẩn mực tại Lakehouse:
1. **File 1 — Bảng Dữ Liệu Phẳng Chuẩn Hóa (Flat Clean Dataset):**  
   Đường dẫn: `staging/<source>/<source>_flat_clean.parquet` (và bản hợp nhất `curated/curated_golden_flat_jobs.parquet`). Toàn bộ cấu trúc lồng nhau đã được ép phẳng, các cột định lượng đã sẵn sàng cho mô hình hóa.
2. **File 2 — Bệnh Án Chất Lượng Dữ Liệu (Data Quality Health Card):**  
   Đường dẫn: `reports/<source>/<source>_quality_health_card.json`. Đo lường 5 trụ cột chất lượng: tỷ lệ khuyết thiếu trước/sau bù khuyết, ngưỡng IQR, phân vị P1-P99, tỷ lệ bản ghi qua GenAI, độ lệch Skewness.
3. **File 3 — Từ Điển Biến Đổi Dữ Liệu (Transformation Manifest):**  
   Đường dẫn: `reports/<source>/<source>_transformation_manifest.md`. Báo cáo giải trình minh bạch nguồn gốc dữ liệu (**Data Lineage**), công thức regex bóc tách lương và luật xử lý ngoại lệ.

---

## 🖥️ Trung Tâm Giám Sát Kỹ Thuật (Central Observatory)

Hệ thống tích hợp ứng dụng Dashboard giám sát tập trung tại thư mục [`monitoring/`](monitoring/):
- **Backend (FastAPI):** Cung cấp REST API phục vụ số liệu thống kê dữ liệu cào, tình trạng đồng bộ Lakehouse Cloudflare R2, và kiểm soát tiến trình Apache Airflow.
- **Frontend (React 18 + TypeScript + Tailwind CSS):**
  - **Master Dashboard:** Quan sát độ hội tụ schema, phân bổ dải lương thị trường, bản đồ nhiệt kỹ năng IT và phân bổ cấp bậc.
  - **Airflow Monitor:** Giám sát trực tiếp trạng thái tiến trình Scheduler, Webserver và lịch sử chạy của 7 DAGs cào dữ liệu.
  - **R2 Diff Engine & 1-Click Sync:** Đo lường sự sai lệch giữa dữ liệu cục bộ và Object Storage trên Cloudflare R2.
  - **3D Skill Graph (Plotly 3D):** Trực quan hóa không gian liên kết kỹ năng nghề nghiệp.

---

## 🚀 Hướng Dẫn Vận Hành & Khởi Chạy Nhanh (Quickstart)

### 1. Thiết Lập Môi Trường
```bash
# Tạo và kích hoạt môi trường ảo Python 3.12
python3 -m venv .venv
source .venv/bin/activate

# Cài đặt các gói phụ thuộc
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Cấu hình biến môi trường
cp .env.example .env
# Điền thông tin Cloudflare R2 credentials (R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT_URL)
# Điền GEMINI_API_KEY để phục vụ tính năng bù khuyết GenAI
```

### 2. Vận Hành Thu Thập Dữ Liệu (Giai Đoạn 1)
```bash
# Chạy Pha 1: Vét URL vào sổ cái URL Ledger
python run.py --source topcv --phase discover
python run.py --source itviec --phase discover

# Chạy Pha 2: Cào chi tiết có bọc Safe Skip & Re-crawl 21 ngày
python run.py --source topcv --phase detail --batch-size 50
python run.py --source itviec --phase detail --batch-size 50

# Đồng bộ dữ liệu thô lên Cloudflare R2 Lakehouse
python scripts/push_raw_to_r2.py
```

### 3. Tra Cứu Bệnh Án EDA (Giao Thức EDA-First)
```bash
# Xem bệnh án 5 phân vùng lỗi của TopCV (tiết kiệm 95% token)
python scripts/read_eda_diagnosis.py --source topcv

# Xem bệnh án của ITViec dạng JSON
python scripts/read_eda_diagnosis.py --source itviec --format json

# Trích xuất toàn bộ bệnh án của 8 sàn
python scripts/read_eda_diagnosis.py --source all
```

### 4. Vận Hành Tiền Xử Lý & Tinh Chế Dữ Liệu (Giai Đoạn 2)
```bash
# Chạy ép phẳng JSON thô và tích hợp dữ liệu
python preprocessing/integration/run_integration.py

# Chạy toàn bộ chuỗi tiền xử lý (ép phẳng, parse lương, text cleaning, imputer, outlier, dedup)
python scripts/run_staging_integration_pipeline.py

# Đồng bộ sản phẩm Bộ 3 Deliverables lên Cloudflare R2
python scripts/push_integration_to_r2.py
```

### 5. Chạy Kiểm Thử Tự Động (Test Suites)
```bash
# Chạy bộ test kiểm thử tiền xử lý toàn diện
pytest tests/test_preprocessing_pipeline.py -v

# Chạy kiểm thử khử trùng lặp và làm sạch văn bản
pytest tests/test_cross_deduplicator.py tests/test_text_preprocessing_and_metrics.py -v

# Chạy toàn bộ unit tests của hệ thống
pytest tests/ -v
```

### 6. Khởi Động Dashboard Giám Sát (Monitoring UI)
```bash
# Khởi chạy đồng thời FastAPI Backend (Port 8000) và React Frontend (Port 5173)
./monitoring/run_all.sh
```
Truy cập giao diện điều khiển tại: `http://localhost:5173`  
Tài liệu Swagger API tại: `http://localhost:8000/docs`

---

## 📂 Cấu Trúc Thư Mục Dự Án (Project Layout)

```text
VN-IT-Job-Mining/
├── .agents/                          # Antigravity Skills và bộ quy tắc vận hành cho AI Agent
│   ├── rules/                        # Quy chuẩn kiến trúc & monitoring
│   └── skills/                       # Skills chuyên biệt (data-integration-miner, visual-data-structure,...)
├── airflow/                          # Cấu hình và DAGs điều phối tự động Apache Airflow
│   ├── dags/                         # crawler_dags.py (Discovery & Detail DAGs)
│   └── plugins/                      # crawler_operators.py (JobCrawlerOperator, DataQualityOperator)
├── collection/                       # Giai đoạn 1: Hệ thống thu thập dữ liệu thô & EDA
│   ├── base/                         # BaseCrawler, BaseStorage, UrlLedger abstractions
│   ├── common/                       # r2_storage.py, r2_raw_pipeline.py, url_ledger.py
│   ├── reports/                      # 8 Jupyter Notebooks EDA_<source>.ipynb chẩn đoán 5 trụ cột lỗi
│   └── sources/                      # Mã nguồn crawler chuyên biệt của từng sàn
├── data/                             # Dữ liệu cục bộ phân tầng (raw/, staging/, curated/)
├── docs/                             # Hệ thống tài liệu kiến trúc kỹ thuật chuẩn mực
│   ├── preprocessing/                # Tài liệu quy chuẩn kỹ thuật 4 bước tiền xử lý & Post-Integration
│   └── crawl/                        # Tài liệu phân tích kiến trúc bóc tách của từng website
├── monitoring/                       # Trung tâm giám sát toàn hệ thống (Observatory)
│   ├── backend/                      # FastAPI service, Airflow monitor, R2 client, Alert system
│   └── frontend/                     # React 18 + Vite + Tailwind CSS dashboard
├── preprocessing/                    # Giai đoạn 2: Mã nguồn tiền xử lý và tinh chế Golden Dataset
│   ├── integration/                  # json_flattener.py (Ép phẳng JSON đa nguồn về bảng phẳng 20 cột)
│   ├── transformation/               # salary_parser.py, bullet_stitcher.py, html_cleaner.py
│   ├── missing_outlier/              # sneaky_null_detector.py, genai_text_imputer.py, outlier_handler.py
│   └── normalization/                # text_cleaner.py, cross_deduplicator.py, log_transformer.py
├── reports/                          # Bộ 3 Deliverables sau xử lý (Health Cards, Manifests, Integration reports)
├── scripts/                          # Bộ công cụ dòng lệnh tự động hóa (read_eda_diagnosis.py, push_to_r2,...)
└── tests/                            # Bộ kiểm thử đơn vị & kiểm thử tích hợp tự động (Pytest)
```

---

## ⚖️ Giấy Phép & Khuyến Cáo (License & Ethics)
- Dữ liệu thu thập và khai phá phục vụ mục đích nghiên cứu học thuật về thị trường lao động CNTT tại Việt Nam.
- Toàn bộ crawler tuân thủ chính sách giãn cách truy vấn (**Rate Limiting & Polite Crawling**), tôn trọng máy chủ đích và không gây ảnh hưởng đến dịch vụ tuyển dụng gốc.
