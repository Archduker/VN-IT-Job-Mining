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
|  [GIAI ĐOẠN 2: DATA PREPROCESSING (TIỀN XỬ LÝ & TINH CHẾ GOLDEN DATASET)]                          |
|  * Giao thức EDA-First: Bắt buộc đọc Bệnh án EDA trước khi can thiệp mã nguồn                      |
|  * Step 1: Schema Mapping & JSON Flattening -> Ép phẳng dữ liệu 8 sàn về raw_for_normalization.json|
|  * Step 2: Data Transformation -> Bóc tách dải lương, quy đổi USD->VND (25,400), chuẩn hóa ngày    |
|  * Step 3: Gemini Enrichment & Market Anchors -> Bù khuyết Zero-null, 3 lớp kỹ năng, dịch JD EN->VI|
|  * Step 4: Deep Normalization & Formatting -> Khử trùng lặp, xuất bản Target Schema 11 Khóa Gốc    |
|  * Step 5: QA Validation Suite -> Kiểm định 5 khế ước chất lượng tự động, đạt 5/5 PASSED           |
|                                     │                                                              |
|                                     ▼                                                              |
|  [ĐẦU RA TIỀN XỬ LÝ: SILVER MASTER DATASET] (100% PURE RFC 8259 JSON, 8,959 BẢN GHI GROUND TRUTH)  |
|  * data/silver/silver_master_dataset.json (Nested 11 Khóa Gốc, bảo tồn null lương thỏa thuận, 100% VI)|
|  * data/silver/silver_flat_jobs.json (Bảng phẳng phục vụ Machine Learning / Data Mining)            |
|  * Bản sao tương thích ngược: data/curated/golden_master.json & curated_flat_golden_jobs.json      |
|  * Đã đồng bộ Cloudflare R2: s3://vn-it-jobs/silver/                                               |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

---

## 🛠️ Công Nghệ Sử Dụng (Tech Stack Matrix)

| Lớp Kiến Trúc (Layer) | Công Nghệ & Thư Viện Chính | Mục Đích Kỹ Thuật |
| :--- | :--- | :--- |
| **Ngôn Ngữ & Môi Trường** | **Python 3.12**, **TypeScript (ES2022)** | Nền tảng thực thi backend, data pipelines và giao diện giám sát |
| **Lưu Trữ Lakehouse** | **Cloudflare R2 Object Storage** (S3 API), **JSON RFC 8259** | Kiến trúc Huy chương Medallion (`raw/` (Bronze) ➔ `silver/` (Silver Master) ➔ `gold/`) |
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

### 3. Chuẩn Xuất Bản Bộ Dữ Liệu Vàng Sau Tiền Xử Lý (Golden Deliverables Standard)
Sau khi hoàn tất toàn trình tiền xử lý, hệ thống xuất bản đúng 4 tài liệu và sản phẩm dữ liệu chuẩn mực tại `data/curated/` và `reports/`:
1. **File 1 — Bộ Dữ Liệu Vàng Phân Tầng (Nested Golden Master):**  
   Đường dẫn: [`data/curated/golden_master.json`](data/curated/golden_master.json).  
   Định dạng: **100% PURE RFC 8259 JSON** (0 NaN, 0 Parquet/CSV), đúng 11 Khóa Gốc, Zero-null lương, mô tả tiếng Việt sạch thẻ HTML.
2. **File 2 — Bảng Dữ Liệu Vàng Phẳng (Curated Flat Golden Dataset):**  
   Đường dẫn: [`data/curated/curated_flat_golden_jobs.json`](data/curated/curated_flat_golden_jobs.json).  
   Định dạng: Bảng phẳng 1 tầng phục vụ nạp trực tiếp vào DuckDB, Pandas, Polars, Scikit-Learn để phân cụm và dự đoán.
3. **File 3 — Báo Cáo Kiểm Định Chất Lượng QA (QA Pipeline Report):**  
   Đường dẫn: [`reports/qa/qa_pipeline_report.md`](reports/qa/qa_pipeline_report.md) & [`reports/qa/qa_pipeline_report.json`](reports/qa/qa_pipeline_report.json).  
   Đo lường 5 khế ước chất lượng tự động: Lineage, Pure JSON, Zero-raw & Clean JD, Skills Contract, Outliers & Quality Score (5/5 PASSED).
4. **File 4 — Bệnh Án Chất Lượng Dữ Liệu Vàng (Curated Golden Dataset Health Card):**  
   Đường dẫn: [`reports/curated_golden_dataset_health_card.json`](reports/curated_golden_dataset_health_card.json).  
   Đo lường phân vị lương P25 - P50 - P75, tỷ lệ bản ghi có kỹ năng và chỉ số hoàn thiện của từng trường.

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
# 1. Chạy toàn bộ Master Pipeline từ A-Z (Khuyến nghị dùng cờ --mock cho dev/test để không tốn quota API)
python preprocessing/master_pipeline.py --step all --mock

# 2. Hoặc chạy từng bước độc lập:
# Bước 1: Tích hợp và ép phẳng đa nguồn
python preprocessing/master_pipeline.py --step integration

# Bước 2: Bóc tách kiểu dữ liệu và chuẩn hóa dải số
python preprocessing/master_pipeline.py --step transformation

# Bước 3: Làm giàu bằng Gemini Preprocessing Agent kết hợp Market Anchors
python preprocessing/master_pipeline.py --step gemini_enrichment --mock --limit 100

# Bước 4: Chuẩn hóa sâu, khử trùng lặp và xuất bản Target Schema 11 Khóa
python preprocessing/master_pipeline.py --step normalization

# Bước 5: Kiểm định tự động 5 khế ước chất lượng dữ liệu Vàng
python preprocessing/master_pipeline.py --step qa
```

### 5. Chạy Kiểm Thử Tự Động Toàn Diện (Pytest Suites)
```bash
# Chạy bộ 34 tests chuyên sâu cho Agent, Market Anchor, Target Schema và QA Pipeline:
pytest tests/test_market_anchor_calculator.py \
       tests/test_gemini_all_in_one_agent.py \
       tests/test_target_schema_formatter.py \
       tests/test_checkpoint_store.py \
       tests/test_run_gemini_enrichment.py \
       tests/test_qa_pipeline.py -v

# Chạy kiểm định 5 khế ước chất lượng dữ liệu vàng trực tiếp:
python preprocessing/qa/run_qa_checks.py
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
│   ├── adr/                          # Architectural Decision Records (ADR 0001, ADR 0002)
│   ├── preprocessing/                # Đặc tả TARGET_SCHEMA_11_KEYS, GEMINI_AGENT_USER_GUIDE, QA_VALIDATION_SUITE
│   └── crawl/                        # Tài liệu phân tích kiến trúc bóc tách của từng website
├── monitoring/                       # Trung tâm giám sát toàn hệ thống (Observatory)
│   ├── backend/                      # FastAPI service, Airflow monitor, R2 client, Alert system
│   └── frontend/                     # React 18 + Vite + Tailwind CSS dashboard
├── preprocessing/                    # Giai đoạn 2: Mã nguồn tiền xử lý và tinh chế Golden Dataset
│   ├── master_pipeline.py            # CLI Orchestrator điều phối toàn trình 5 bước tiền xử lý
│   ├── integration/                  # Ép phẳng JSON đa nguồn về raw_for_normalization.json
│   ├── transformation/               # salary_parser.py, bullet_stitcher.py, html_cleaner.py
│   ├── missing_outlier/              # gemini_all_in_one_agent.py, market_anchor_calculator.py, checkpoint_store.py
│   └── normalization/                # target_schema_formatter.py, run_deep_normalization.py
├── reports/                          # QA Reports (qa_pipeline_report.md/json) & Health Cards
├── scripts/                          # Bộ công cụ dòng lệnh tự động hóa (read_eda_diagnosis.py, push_to_r2,...)
└── tests/                            # Bộ kiểm thử đơn vị & kiểm thử tích hợp tự động (Pytest)
```

---

## ⚖️ Giấy Phép & Khuyến Cáo (License & Ethics)
- Dữ liệu thu thập và khai phá phục vụ mục đích nghiên cứu học thuật về thị trường lao động CNTT tại Việt Nam.
- Toàn bộ crawler tuân thủ chính sách giãn cách truy vấn (**Rate Limiting & Polite Crawling**), tôn trọng máy chủ đích và không gây ảnh hưởng đến dịch vụ tuyển dụng gốc.
