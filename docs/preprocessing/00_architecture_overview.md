# TỔNG QUAN KIẾN TRÚC TIỀN XỬ LÝ DỮ LIỆU (PREPROCESSING ARCHITECTURE)

> **Tài liệu quy chuẩn số 00 (Preprocessing Core Document 00)**  
> **Dự án:** Phân tích thị trường lao động IT và nhu cầu kỹ năng nghề nghiệp tại Việt Nam (**VN-IT-Job-Mining**)  
> **Nguyên tắc cốt lõi:**  
> 1. Phân định rạch ròi 100% giữa giai đoạn Thu thập (Collection) và Tiền xử lý (Preprocessing).  
> 2. Ép phẳng dữ liệu (JSON Flattening) về một bảng phẳng duy nhất (Single Flat Table) chuẩn Modern Data Mining.  
> 3. Ứng dụng GenAI (Gemini) làm công cụ trọng tâm để xử lý văn bản và bù khuyết các trường bị thiếu (Missing Values).  
> 4. Ranh giới đanh thép (Ironclad Boundaries) giữa 4 bước để ngăn chặn hoàn toàn Scope Creep của Agent.  
> 5. Tuyệt đối không dùng sơ đồ Mermaid (sử dụng sơ đồ khối ASCII và bảng Markdown).

---

## 1. Ranh Giới Giữa Giai Đoạn Collection Và Giai Đoạn Preprocessing

Để đảm bảo tính toàn vẹn của hệ thống, quy trình được phân rã thành hai giai đoạn độc lập:

```text
+----------------------------------------------------------------------------------------------------+
|                      GIAI ĐOẠN 1: DATA COLLECTION (ĐÃ HOÀN TẤT & ĐÓNG GÓI)                         |
+----------------------------------------------------------------------------------------------------+
|  * Mục tiêu: Thu thập nguyên bản 100% (Zero Information Loss) từ 8 sàn tuyển dụng.                 |
|  * Lưu trữ: Snapshot thô dạng RawJobEnvelope (metadata + raw_payload) tại data/<source>/raw/.      |
|  * Kiểm soát: Quản lý vòng đời URL qua url_ledger (catalog_master.json / parquet).                 |
|  * Khám phá: 8 Jupyter Notebooks tại collection/reports/EDA_<source>.ipynb chẩn đoán lỗi thô.      |
|  * Tiêu chuẩn: Dữ liệu ở tầng này là BẤT BIẾN (IMMUTABLE), không sửa chữa, không làm sạch.         |
+----------------------------------------------------------------------------------------------------+
                                                  │
                                                  ▼ (Bàn giao files JSON thô)
+----------------------------------------------------------------------------------------------------+
|                     GIAI ĐOẠN 2: PREPROCESSING ENGINE (QUY HOẠCH MỚI ĐỘC LẬP)                      |
+----------------------------------------------------------------------------------------------------+
|  * Mục tiêu: Chuyển đổi dữ liệu thô dị thể thành Bảng Phẳng Chuẩn Vàng (Golden Flat Table).       |
|  * Tổ chức mã nguồn: preprocessing/ (tách rời hoàn toàn khỏi collection/).                         |
|  * Tổ chức tài liệu: docs/preprocessing/ (chia cụ thể theo 4 bước công việc).                     |
|  * 4 Bước tuần tự / thích ứng:                                                                     |
|    1. Integration: Mapping lấy các trường chung & Ép phẳng JSON (JSON Flattening).                 |
|    2. Transformation: Parse lương, quy đổi USD/SGD->VND, chuẩn hóa ngày tháng & xuất báo cáo lương.|
|    3. Missing & Outlier: Bóc trần null giả mạo, GenAI bù khuyết từ JD text, xử lý ngoại lai IQR.  |
|    4. Normalization: Biến đổi phân phối (Log-transform), chuẩn hóa cấp bậc, thành phố, taxonomy.   |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. Ma Trận Ranh Giới Đanh Thép (Ironclad Boundaries Matrix)

Bảng ma trận dưới đây là **Khế ước bắt buộc (Architectural Contract)** nhằm ngăn chặn hiện tượng Agent tự tiện làm vượt phạm vi (ví dụ: ở bước Integration mới chỉ gom trường mà Agent đã tự parse min/max salary hoặc xóa outlier):

| Giai đoạn | Mục tiêu duy nhất | ĐƯỢC PHÉP LÀM (DO) | TUYỆT ĐỐI CẤM (DO NOT DO) | Vai trò của GenAI / LLM |
| :--- | :--- | :--- | :--- | :--- |
| **Bước 1: Integration**<br>`preprocessing/integration/` | Gom dữ liệu đa nguồn về một cấu trúc phẳng thống nhất | - Đọc `RawJobEnvelope`<br>- Ánh xạ tên cột tương đương<br>- **Ép phẳng JSON lồng nhau** (dict, list, detail-box, jsonld)<br>- Tạo khóa toàn cục `job_id_global` | - **CẤM** parse số min/max lương<br>- **CẤM** đổi tiền tệ (USD->VND)<br>- **CẤM** xóa bỏ hàng (drop rows)<br>- **CẤM** điền giá trị khuyết thiếu (fillna) | **KHÔNG DÙNG** (100% Pure Deterministic Logic) |
| **Bước 2: Transformation**<br>`preprocessing/transformation/` | Bóc tách kiểu dữ liệu, chuẩn hóa dải số và định dạng | - Regex bóc tách dải lương `salary_min_vnd`, `salary_max_vnd`<br>- Regex quét lương ẩn trong JD text<br>- Quy đổi USD theo tỷ giá dự án 25,400 VND/USD<br>- Quy đổi SGD theo tỷ giá lịch sử SGD/USD × 25,400 VND/USD<br>- Quy đổi lương năm sang tháng (`/12`); ghi metadata tỷ giá<br>- Ép kiểu dữ liệu (`float`, `int`, `datetime`)<br>- Xuất danh sách tin có lương VND, sắp xếp theo khoảng lương; không xóa tin khỏi dataset chính | - **CẤM** tự ý xóa bản ghi nghi ngờ outlier<br>- **CẤM** điền giá trị trung bình vào ô null<br>- **CẤM** biến đổi phi tuyến (log-scale)<br>- Không tự đoán tỷ giá cho tiền tệ chưa nhận diện | Hỗ trợ fallback: trích xuất lương khi câu văn JD quá phức tạp |
| **Bước 3: Missing & Outlier**<br>`preprocessing/missing_outlier/` | Bóc trần null trá hình, bù khuyết qua GenAI & chặn ngoại lai | - Bóc trần 9+ null markers (`thỏa thuận`, `0`, `[]`)<br>- Bảo toàn cờ `is_negotiable=1` (MNAR)<br>- **Dùng GenAI đọc JD bù khuyết kinh nghiệm, level, thành phố, kỹ năng**<br>- Phát hiện 3 lỗi nhập liệu số bằng IQR<br>- Áp dụng Winsorization (capping 1% & 99%) | - **CẤM** fill Mean/Median vào lương thỏa thuận<br>- **CẤM** drop hàng làm mất thông tin kỹ năng<br>- **CẤM** dùng GenAI bịa đặt thông tin khi JD không có cơ sở<br>- **CẤM CHẠY BATCH GENAI KHI CHƯA CÓ TEAM SIGN-OFF** | **TRỌNG TÂM:** GenAI đọc hiểu sâu văn bản JD để điền giá trị thiếu (BẮT BUỘC có xác nhận từ User & Team) |
| **Bước 4: Normalization**<br>`preprocessing/normalization/` | Đưa các biến về cùng thang đo và hệ từ điển quy chuẩn | - Biến đổi Log-transform $y = \log(1 + \text{salary})$<br>- Min-Max Scaling hoặc RobustScaler<br>- Chuẩn hóa 63 tỉnh thành Việt Nam<br>- Chuẩn hóa 6 bậc Seniority (Intern -> Lead)<br>- Mapping kỹ năng về chuẩn ESCO | - **CẤM** scale dữ liệu trước khi xử lý outlier<br>- **CẤM** ghi đè làm mất nhãn gốc của sàn | Hỗ trợ mapping ngữ nghĩa các chức danh tự do về 12 Job Family chuẩn (BẮT BUỘC Pilot duyệt) |

---

## 3. Quy Trình Linh Hoạt Theo Từng Bộ Dữ Liệu (Adaptive Pipeline)

Modern Data Mining không áp dụng quy trình đường thẳng (Waterfall) cứng nhắc cho mọi sàn, mà **linh hoạt điều chỉnh thứ tự và lặp lại dựa trên kết quả khám phá từ EDA**:

```text
+----------------------------------------------------------------------------------------------------+
|                         ĐIỀU CHỈNH THÍCH ỨNG ĐỘNG CHO 8 SÀN TUYỂN DỤNG                             |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [NHÓM 1: SÀN CÓ API CẤU TRÚC SẴN - VietnamWorks, TopDev]                                          |
|  * Đặc điểm: Đã có sẵn trường số (salaryMin/Max) hoặc skills array, nhưng nhiều rác HTML / số 0.   |
|  * Luồng ưu tiên: Integration -> Clean HTML / Bóc trần số 0 -> Outlier Check -> GenAI Text.       |
|                                                                                                    |
|  [NHÓM 2: SÀN BỊ ẨN LƯƠNG TRÊN WEB NHƯNG CÓ JSON-LD NGẦM - ITviec, Glints]                        |
|  * Đặc điểm: Web ghi 'Đăng nhập để xem lương' hoặc 'Không công khai', nhưng JSON-LD có baseSalary. |
|  * Luồng ưu tiên: Integration -> JSON-LD Fallback Extractor -> Transform USD->VND -> GenAI Impute. |
|                                                                                                    |
|  [NHÓM 3: SÀN NHÉT TẤT CẢ VÀO MẢNG CHUỖI - CareerViet]                                            |
|  * Đặc điểm: Lương, kinh nghiệm, cấp bậc nhét chung vào detail-box; nhiều dòng bị lặp lại.         |
|  * Luồng ưu tiên: Integration -> Transform (Parse Regex mảng detail-box trước) -> Missing Check.   |
|                                                                                                    |
|  [NHÓM 4: SÀN PHÂN MẢNH VĂN BẢN BULLET - Vieclam24h]                                               |
|  * Đặc điểm: Các câu bullet bị đứt đoạn giữa dòng; dict company lồng nhau.                        |
|  * Luồng ưu tiên: Integration -> Bullet Stitching (Nối câu) -> Transform -> GenAI Impute.          |
|                                                                                                    |
|  [NHÓM 5: SÀN ĐẦY ĐỦ THUỘC TÍNH FORM - TopCV, JobsGO]                                              |
|  * Đặc điểm: Đầy đủ các trường tổng quan, TopCV có 3 nhóm tags (Yêu cầu/Quyền lợi/Chuyên môn).     |
|  * Luồng ưu tiên: Integration -> Ép phẳng 3 nhóm tags -> Transform dải lương -> Chuẩn hóa.        |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

### 3.1. Quy Chuẩn Vòng Lặp Phản Hồi Hiện Đại (Modern Cyclic Feedback Loops)
> [!IMPORTANT]
> **Quy trình Data Mining hiện đại không phải đường thẳng 1 chiều (Waterfall):**
> - Một bước có thể lặp lại nhiều lần. Các bước sau liên tục gửi tín hiệu phản hồi ngược về các bước trước:
>   - **Step 3 (Outliers) $\longrightarrow$ Step 2 (Transformation):** Khi phân tích phân vị IQR phát hiện các ngoại lai do bóc nhầm số điện thoại (ví dụ: `Khánh Lương SĐT: 0243.936.6990` thành lương 243 triệu) hoặc nhầm số che giấu (`1*** USD`), hệ thống có quyền kích hoạt vòng lặp tinh chỉnh Regex và tái thực thi.
>   - **Step 4 (Deduplication) $\longrightarrow$ Step 3 (Missing Values):** Khi hợp nhất các bài đăng trùng lặp xuyên sàn, thông tin phong phú hơn từ các nguồn đối ứng giúp giảm tỷ lệ khuyết thiếu thực tế.

### 3.2. Quy Chuẩn Quản Trị Trí Tuệ Nhân Tạo Bắt Buộc Xác Nhận (Human-in-the-Loop AI Governance)
> [!CAUTION]
> **Quy chế phê duyệt bắt buộc trước khi chạy AI/LLM:**
> - Mọi can thiệp bằng mô hình AI (Gemini 1.5 Flash Imputer, Zero-shot Job Family, Embeddings ESCO) đều phải:
>   1. Khai báo rõ ràng cấu trúc prompt, model, chi phí token ước tính và cơ chế heuristic fallback.
>   2. Chạy thử nghiệm Pilot trên 20 - 30 bản ghi đối chứng xuất báo cáo trước/sau.
>   3. **BẮT BUỘC PHẢI CÓ SỰ XÁC NHẬN CHÍNH THỨC CỦA BẠN (USER) VÀ TEAM** trước khi kích hoạt chạy hàng loạt (Batch Inference).

---

## 4. Nguyên Tắc Cấu Trúc Dữ Liệu: Target Schema 11 Khóa & Bảng Phẳng

> [!IMPORTANT]
> **Quy Chuẩn Single Source of Truth:**  
> Hệ thống áp dụng cấu trúc dữ liệu vàng chuẩn hóa 2 tầng phân cấp tinh giản gồm đúng **11 Khóa Gốc** tại `data/curated/golden_master.json`, đồng thời xuất bản bảng phẳng duy nhất tại `data/curated/curated_flat_golden_jobs.json` theo tài liệu quy chuẩn:
> - Chi tiết từ điển dữ liệu: Xem [`TARGET_SCHEMA_11_KEYS.md`](TARGET_SCHEMA_11_KEYS.md)
> - Hướng dẫn vận hành Gemini Agent: Xem [`GEMINI_AGENT_USER_GUIDE.md`](GEMINI_AGENT_USER_GUIDE.md)
> - Quy chuẩn kiểm định QA 5/5: Xem [`QA_VALIDATION_SUITE.md`](QA_VALIDATION_SUITE.md)
> - Quyết định kiến trúc ADR: Xem [`docs/adr/0001-target-schema-11-keys-pure-json.md`](../adr/0001-target-schema-11-keys-pure-json.md) và [`docs/adr/0002-zero-null-market-anchored-salary.md`](../adr/0002-zero-null-market-anchored-salary.md)

### 4.1. Cấu Trúc 11 Khóa Gốc (Golden Master Target Schema):
Mỗi bản ghi đại diện cho một tin tuyển dụng CNTT tinh chế 100% PURE RFC 8259 JSON:

```text
+----------------------------------------------------------------------------------------------------+
|                               TARGET SCHEMA 11 KHÓA GỐC (GOLDEN RECORD)                             |
+----------------------------------------------------------------------------------------------------+
| 1. job_id_global:    Định danh duy nhất toàn cục (<platform>_<id>)                                  |
| 2. source_platform:  Nguồn sàn tuyển dụng (itviec, topcv, vietnamworks, topdev...)                |
| 3. source_url:       Canonical URL truy vết nguồn gốc (Data Lineage)                               |
| 4. job_info:         title, job_role, working_model (onsite/hybrid/remote), work_format              |
| 5. company:          name, industry, size_range                                                    |
| 6. locations:        primary_city, addresses, geo_coordinates, all_locations                       |
| 7. salary:           salary_min_vnd, salary_max_vnd, is_salary_negotiable, salary_source (Zero-null)|
| 8. skills:           primary_tech_stack, required_technical, preferred_skills, soft_skills          |
| 9. requirements:     standardized_seniority, years_experience_min/max, education_level, age_range    |
| 10. jd_text:         description, requirements, benefits, language (100% tiếng Việt sạch)          |
| 11. date:            posted_date, crawled_date, expired_date (ISO 8601 YYYY-MM-DD)                 |
+----------------------------------------------------------------------------------------------------+
```

### 4.2. Cấu Trúc Bảng Phẳng (Canonical Flat View):
Tệp `data/curated/curated_flat_golden_jobs.json` được ép phẳng phục vụ huấn luyện mô hình học máy:

```text
+----------------------------------------------------------------------------------------------------+
|                                 CANONICAL FLAT JOB RECORD (1 HÀNG)                                 |
+----------------------------------------------------------------------------------------------------+
| 1. ĐỊNH DANH:     job_id_global, source_platform, source_url                                        |
| 2. CÔNG TY:       company_name                                                                     |
| 3. VỊ TRÍ:        job_title, job_role, working_model                                               |
| 4. ĐỊA ĐIỂM:      primary_city                                                                     |
| 5. LƯƠNG SỐ HỌC:  salary_min_vnd, salary_max_vnd, is_salary_negotiable, salary_source             |
| 6. KỸ NĂNG:       primary_tech_stack, required_technical, preferred_skills                         |
| 7. YÊU CẦU:       standardized_seniority, years_experience_min, years_experience_max               |
| 8. VĂN BẢN SẠCH:  jd_description                                                                   |
| 9. THỜI GIAN:     posted_date                                                                      |
+----------------------------------------------------------------------------------------------------+
```

---

## 5. Tổ Chức Thư Mục Dự Án (Directory Layout)

```text
VN-IT-Job-Mining/
├── collection/                       <-- Giai đoạn 1: Thu thập & Báo cáo EDA thô
│   ├── base/
│   ├── common/
│   ├── sources/
│   └── reports/                      <-- 8 Notebooks EDA_<source>.ipynb
│
├── preprocessing/                    <-- Giai đoạn 2: Mã nguồn tiền xử lý độc lập
│   ├── integration/                  <-- Bước 1: Ép phẳng & Ánh xạ trường chung
│   │   ├── json_flattener.py
│   │   └── schema_mapper.py
│   ├── transformation/               <-- Bước 2: Bóc tách kiểu & dải lương
│   │   ├── salary_parser.py
│   │   └── date_experience_parser.py
│   ├── missing_outlier/              <-- Bước 3: GenAI Imputer & Outliers
│   │   ├── sneaky_null_detector.py
│   │   ├── genai_text_imputer.py
│   │   └── outlier_handler.py
│   └── normalization/                <-- Bước 4: Chuẩn hóa thang đo & Taxonomy
│       ├── text_cleaner.py
│       └── log_transformer.py
│
└── docs/
    └── preprocessing/                <-- Bộ tài liệu quy chuẩn kỹ thuật
        ├── 00_architecture_overview.md
        ├── integration/
        │   └── 01_schema_mapping_and_flattening.md
        ├── transformation/
        │   └── 02_data_typing_and_parsing.md
        ├── missing_outlier/
        │   └── 03_genai_imputation_and_outliers.md
        └── normalization/
            └── 04_scaling_and_taxonomy.md
```
