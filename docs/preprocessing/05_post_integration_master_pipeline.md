# HƯỚNG XỬ LÝ TỔNG THỂ SAU BƯỚC INTEGRATION (POST-INTEGRATION MASTER PIPELINE)

> **Tài liệu quy chuẩn số 05 (Preprocessing Core Document 05 — Post-Integration Roadmap)**  
> **Dự án:** Phân tích thị trường lao động IT và nhu cầu kỹ năng nghề nghiệp tại Việt Nam (**VN-IT-Job-Mining**)  
> **Sứ mệnh:** Định hình lộ trình chuyển hóa dữ liệu toàn diện sau khi đã hoàn tất bước Integration (Gom trường chung & Ép phẳng JSON), từ Bảng Phẳng Staging đến Bộ Dữ Liệu Vàng (Golden Master Dataset) phục vụ trọn vẹn 5 mục tiêu chiến lược SD1 — SD5.

---

## 1. Bản Đồ Tổng Thể Quy Trình Sau Integration (End-to-End Post-Integration Flow)

Sau khi hoàn thành bước **Integration**, ta thu được **Một Bảng Phẳng Thống Nhất (Single Flat Staging Table)** chứa toàn bộ 9,390 bài đăng từ 8 sàn. Quy trình xử lý tổng thể tiếp theo được vận hành qua 4 giai đoạn liên hoàn:

```text
+----------------------------------------------------------------------------------------------------+
|                         BẢN ĐỒ TỔNG THỂ SAU BƯỚC INTEGRATION (POST-INTEGRATION)                    |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|   [GIAI ĐOẠN 1: BẢNG PHẲNG STAGING ĐÃ TÍCH HỢP] (staging_flat_jobs.parquet)                        |
|   9,390 dòng x 20 cột phẳng thô (toàn bộ cấu trúc lồng nhau đã được ép phẳng)                      |
|                                     │                                                              |
|                                     ▼                                                              |
|   [GIAI ĐOẠN 2: CHUYỂN HÓA & BÓC TÁCH KIỂU (TRANSFORMATION)]                                       |
|   * Cascade Salary Parser: Header Regex -> JD Regex Scanner (bóc lương ẩn) -> GenAI Fallback       |
|   * Quy đổi tiền tệ: USD -> VND (tỷ giá 25,400); quy đổi lương năm -> lương tháng (/12)            |
|   * Chuẩn hóa ngày tháng ISO 8601 & Bóc tách số năm kinh nghiệm                                    |
|                                     │                                                              |
|                                     ▼                                                              |
|   [GIAI ĐOẠN 3: BÙ KHUYẾT BẰNG GEN AI & XỬ LÝ NGOẠI LAI (MISSING & OUTLIER)]                       |
|   * Bóc trần 9+ Null Markers trá hình ('thỏa thuận', 'cạnh tranh', '0') -> giữ cờ is_negotiable    |
|   * GenAI Imputer: Gemini đọc JD bù khuyết kinh nghiệm, cấp bậc, thành phố, kỹ năng               |
|   * Kiểm định IQR: Nhận diện 3 lỗi số học & Winsorization (capping 1% và 99%, không drop hàng)     |
|                                     │                                                              |
|                                     ▼                                                              |
|   [GIAI ĐOẠN 4: KHỬ TRÙNG LẶP NGỮ NGHĨA XUYÊN SÀN (CROSS-PLATFORM DEDUPLICATION)]                  |
|   * Nhóm bài đăng theo: normalized_company + primary_city                                          |
|   * So khớp ngữ nghĩa: Cosine Similarity trên vector nhúng văn bản JD (ngưỡng >= 0.88)             |
|   * Hợp nhất: Giữ lại bản ghi có độ đầy đủ thông tin cao nhất (Golden Record Selection)            |
|                                     │                                                              |
|                                     ▼                                                              |
|   [GIAI ĐOẠN 5: CHUẨN HÓA & LÀM GIÀU AI (NORMALIZATION & TAXONOMY ENRICHMENT)]                     |
|   * Log-transformation cho mức lương: y = log(1 + salary_max_vnd)                                  |
|   * Phân loại Zero-shot Chức danh tuyển dụng về 12 Job Family chuẩn (SD2)                          |
|   * Mapping Kỹ năng về Taxonomy ESCO quốc tế qua Semantic Embeddings (SD3)                         |
|                                     │                                                              |
|                                     ▼                                                              |
|   [ĐẦU RA CUỐI CÙNG: GOLDEN MASTER DATASET] (curated_flat_jobs.parquet)                            |
|   Bộ dữ liệu phẳng hoàn chỉnh, không còn null trá hình, không còn outlier, chuẩn hóa toàn diện     |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. Chi Tiết Các Giai Đoạn Sau Integration

### 2.1. Giai Đoạn 2: Chuyển Hóa & Bóc Tách Kiểu Dữ Liệu (Transformation)
- **Cascade Salary Extraction:**
  - Giải quyết bài toán *"Lương nằm trong mô tả công việc"*: Với $60\% - 70\%$ bài đăng ghi "Thỏa thuận" ở header, module `UniversalSalaryParser` kích hoạt bộ quét regex trên clean JD text để bóc tách lương ngầm định.
  - Giải quyết bài toán *"Lương năm"*: Nhận diện các bài đăng ghi thu nhập 300 - 500 triệu/năm và tự động quy đổi về lương tháng bằng phép chia cho 12.
  - Lưu trữ minh bạch: Giữ cờ `is_salary_negotiable_declared = 1` và lưu giá trị bóc tách được vào `salary_min_vnd`, `salary_max_vnd` kèm `salary_source = 'jd_regex'`.

### 2.2. Giai Đoạn 3: Bù Khuyết Bằng GenAI & Xử Lý Ngoại Lai (Missing & Outlier)
- **GenAI Missing Value Imputation (Gemini 1.5 Flash):**
  - Đọc toàn bộ văn bản JD để bù khuyết các trường bị trống:
    - Thiếu kinh nghiệm $\rightarrow$ GenAI đọc câu yêu cầu trích xuất số năm (`min_experience_years`).
    - Thiếu cấp bậc $\rightarrow$ GenAI suy luận bậc chuẩn (`job_seniority`: Intern, Junior, Middle, Senior, Lead).
    - Thiếu thành phố $\rightarrow$ GenAI đọc địa chỉ văn phòng suy luận `primary_city`.
    - Danh mục `skills_list` rỗng $\rightarrow$ GenAI trích xuất danh sách Hard Skills và Domain Skills.
  - Mọi giá trị do GenAI điền đều được gắn cờ `is_imputed_by_genai = True` để bảo toàn tính minh bạch khoa học.
- **Xử lý Ngoại lai bằng Winsorization:**
  - Không xóa bỏ bản ghi (Zero Record Loss Policy) nhằm bảo toàn dữ liệu kỹ năng.
  - Kéo các giá trị lương cực đoan về ngưỡng phân vị $P_1$ và $P_{99}$.

### 2.3. Giai Đoạn 4: Khử Trùng Lặp Ngữ Nghĩa Xuyên Sàn (Cross-Platform Semantic Deduplication)
- **Bản chất bài toán:** Cùng một vị trí tuyển dụng (ví dụ: FPT Software tuyển Senior Java Developer tại Hà Nội) thường được đăng đồng thời trên cả TopCV, VietnamWorks, TopDev và CareerViet với tiêu đề hơi khác nhau.
- **Quy trình khử trùng 2 bước:**
  1. *Lọc thô (Blocking):* Nhóm các bài đăng có cùng `company_name` (sau khi chuẩn hóa chuỗi) và cùng `primary_city`.
  2. *So khớp ngữ nghĩa (Semantic Matching):* Tính toán Cosine Similarity giữa các vector nhúng (text embeddings qua `all-MiniLM-L6-v2` hoặc Gemini Embeddings) của phần mô tả công việc.
  3. *Hợp nhất (Golden Record Selection):* Nếu độ tương đồng $\ge 0.88$, xác định đây là một bài đăng trùng lặp xuyên sàn. Hệ thống hợp nhất thành một bản ghi duy nhất, ưu tiên giữ lại các trường có độ chi tiết cao nhất (ví dụ: lấy lương từ TopCV, lấy danh sách kỹ năng chi tiết từ VietnamWorks).

### 2.4. Giai Đoạn 5: Chuẩn Hóa & Làm Giàu Tri Thức (Normalization & Taxonomy Enrichment)
- **Log-Transformation:** Áp dụng biến đổi $y = \log(1 + \text{salary})$ giải quyết hiện tượng lệch phải nặng ($\text{Skewness} > 5.0$), đưa phân phối lương về dạng chuẩn.
- **Ánh xạ 12 Job Family Chuẩn (SD2):** Áp dụng Zero-shot Classification phân loại mọi chức danh tự do (*"Hiệp sĩ Coder"*, *"Kỹ sư giải pháp đám mây"*) về 12 nhóm nghề nghiệp chuẩn.
- **Chuẩn hóa Kỹ năng về Taxonomy ESCO (SD3):** Đồng nhất các biến thể kỹ năng (`ReactJS`, `React.js`, `React JS`, `react` $\rightarrow$ `React`).

---

## 3. Bản Xuất Bản Hồ Sơ 3 File Sau Khi Xử Lý (The 3-Deliverables Standard)

Để giải quyết trọn vẹn yêu cầu *"một chuỗi/nguồn tạo ra 3 file"*, sau khi xử lý qua pipeline, mỗi nguồn dữ liệu tuyển dụng xuất bản đúng bộ 3 tài liệu chuẩn mực tại Lakehouse:

```text
+----------------------------------------------------------------------------------------------------+
|                         BỘ 3 TÀI LIỆU XUẤT BẢN CHUẨN MỰC CHO MỖI NGUỒN CÀO                         |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  FILE 1: BẢNG DỮ LIỆU PHẲNG CHUẨN HÓA (Flat Clean Dataset)                                         |
|  * Đường dẫn: staging/<source>/<source>_flat_clean.parquet (hoặc .csv)                             |
|  * Định dạng: Bảng phẳng duy nhất, toàn bộ JSON lồng nhau đã được ép phẳng, các cột số đã được     |
|    bóc tách, các ô khuyết đã được GenAI bù đắp. Sẵn sàng đưa vào Pandas/DuckDB phân tích ngay.     |
|                                                                                                    |
|  FILE 2: BỆNH ÁN & HỒ SƠ CHẤT LƯỢNG DỮ LIỆU (Data Quality Health Card & Metrics)                   |
|  * Đường dẫn: reports/<source>/<source>_quality_health_card.json                                   |
|  * Định dạng: Tệp JSON đo lường chi tiết 5 trụ cột chất lượng: Tỷ lệ khuyết thiếu trước/sau bù,   |
|    chỉ số IQR, ngưỡng phân vị P1-P99, tỷ lệ bản ghi được GenAI xử lý, độ lệch Skewness/Kurtosis.   |
|                                                                                                    |
|  FILE 3: TỪ ĐIỂN ÁNH XẠ TRƯỜNG & LOG BIẾN ĐỔI (Transformation Manifest & Data Dictionary)          |
|  * Đường dẫn: reports/<source>/<source>_transformation_manifest.md                                 |
|  * Định dạng: Báo cáo Markdown giải trình minh bạch nguồn gốc dữ liệu (Data Lineage & Provenance):  |
|    Trường nào lấy từ đâu, công thức regex bóc tách lương ra sao, rule sửa lỗi ngoại lai là gì.     |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

---

## 4. Bảng Kế Hoạch Triển Khai Tiếp Theo (Action Items)

| STT | Công Việc Cụ Thể | Thành Phần Chịu Trách Nhiệm | Kết Quả Đầu Ra |
| :--- | :--- | :--- | :--- |
| **1** | Chạy script ép phẳng 9,390 files JSON thô từ 8 nguồn | `preprocessing/integration/json_flattener.py` | `data/staging/staging_flat_all_sources.parquet` |
| **2** | Chạy bóc tách dải lương Cascade & quy đổi tiền tệ | `preprocessing/transformation/salary_parser.py` | Cột `salary_min_vnd`, `salary_max_vnd`, `salary_source` |
| **3** | Chạy GenAI Imputer quét JD bù khuyết kinh nghiệm/skills | `preprocessing/missing_outlier/genai_text_imputer.py`| Cột `is_imputed_by_genai = True`, bù đủ ô trống |
| **4** | Chạy kiểm định IQR & Winsorization dải lương | `preprocessing/missing_outlier/outlier_handler.py` | Chặn ngoại lai tại phân vị 1% và 99% |
| **5** | Khử trùng lặp ngữ nghĩa xuyên sàn (Entity Resolution) | Cross-platform deduplicator script | Golden Master Dataset phẳng hoàn chỉnh |
| **6** | Cập nhật 8 Notebooks EDA với đầy đủ kết luận WHAT-WHY-HOW | `collection/reports/EDA_<source>.ipynb` | 8 Notebooks hoàn thiện 100% tiêu chí nghiệm thu |
