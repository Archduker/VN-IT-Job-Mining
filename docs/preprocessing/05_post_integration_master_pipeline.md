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
|   [GIAI ĐOẠN 1: TÍCH HỢP DỮ LIỆU ĐA NGUỒN] (raw_for_normalization.json)                             |
|   10,024 bài đăng x cấu trúc chuẩn hóa trung gian từ 8 sàn tuyển dụng                               |
|                                     │                                                              |
|                                     ▼                                                              |
|   [GIAI ĐOẠN 2: CHUYỂN HÓA & LÀM GIÀU GEMINI AGENT (GEMINI ENRICHMENT)]                            |
|   * Market Anchor Calculator: Tạo ma trận trung vị lương 2 chiều (Platform x Seniority)             |
|   * Gemini All-in-One Preprocessing Agent: Phân tầng kỹ năng 3 lớp (Core, Required, Preferred)     |
|   * Dịch tự động JD tiếng Anh sang tiếng Việt & Quy đổi tỷ giá 1 USD = 25,400 VND                  |
|   * Resumable Checkpoint Store: Lưu vết từng bản ghi vào checkpoint_gemini.jsonl an toàn           |
|                                     │                                                              |
|                                     ▼                                                              |
|   [GIAI ĐOẠN 3: ĐỊNH DẠNG TARGET SCHEMA 11 KHÓA & KHỬ TRÙNG LẶP (DEEP NORMALIZATION)]              |
|   * TargetSchemaFormatter: Gom dữ liệu về đúng 11 khóa root và sinh bảng phẳng (Flat View)          |
|   * Khử trùng lặp đa tầng (Deduplication) bảo toàn bản ghi có độ đầy đủ cao nhất                   |
|                                     │                                                              |
|                                     ▼                                                              |
|   [GIAI ĐOẠN 4: KIỂM ĐỊNH CHẤT LƯỢNG QA 5 KHẾ ƯỚC (QA VALIDATION SUITE)]                            |
|   * Lineage, Pure RFC 8259 JSON, Clean JD, Skills Contract, Outlier & Quality Score >= 0.70        |
|                                     │                                                              |
|                                     ▼                                                              |
|   [ĐẦU RA CUỐI CÙNG: BỘ DỮ LIỆU VÀNG CHUẨN] (100% PURE RFC 8259 JSON, 8,967 BẢN GHI)             |
|   * data/curated/golden_master.json (Nested 11 Khóa Gốc)                                           |
|   * data/curated/curated_flat_golden_jobs.json (Bảng phẳng phục vụ Machine Learning/Data Mining)   |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. Chi Tiết Các Giai Đoạn Sau Integration

### 2.1. Giai Đoạn 2: Chuyển Hóa & Bóc Tách Kiểu Dữ Liệu (Transformation)
- Hàm `transform_job_record` trong `preprocessing.transformation.record_transformer` bổ sung các trường chuẩn hóa
  trên bản ghi phẳng và giữ nguyên các trường `raw_*` để truy vết dữ liệu nguồn.
- Ngày đăng, cập nhật, hết hạn và thời điểm thu thập được chuẩn hóa thành chuỗi ISO `YYYY-MM-DD`;
  kiểu tuyển dụng, hình thức làm việc, số năm kinh nghiệm, số lượng tuyển và địa điểm có trường chuẩn riêng.
- Chạy Transformation riêng sau khi đã tạo dữ liệu Integration:
  `python -m preprocessing.integration.run_integration`, sau đó
  `python -m preprocessing.transformation.run_transformation`.
- Đầu vào là `data/integration/<source>/<source>_integrated_flat.json`; đầu ra theo nguồn là
  `data/transformation/<source>/<source>_transformed_flat.json`, kèm report tại `reports/transformation/`.
  Chạy `python -m preprocessing.transformation.run_transformation --source glints` để chỉ xử lý một nguồn.
- Mỗi nguồn xuất thêm `data/transformation/<source>/<source>_salary_sorted_vnd.json`; chạy tất cả nguồn
  xuất `data/transformation/salary_sorted_all_sources_vnd.json`. Báo cáo chỉ gồm tin có ít nhất một
  đầu mút lương VND đã parse được, sắp xếp tăng dần theo `salary_min_vnd` rồi `salary_max_vnd`.
  Tin thỏa thuận hoặc không parse được vẫn được giữ nguyên trong file transformed đầy đủ.
- USD được quy đổi theo tỷ giá dự án 25.400 VND/USD. SGD dùng tỷ giá lịch sử SGD/USD theo ngày đăng
  từ Frankfurter (`https://api.frankfurter.dev/v1`), nhân với tỷ giá USD/VND cố định 25.400 của dự án.
  Đây là tỷ giá VND quy đổi chéo, không phải báo giá SGD/VND lịch sử trực tiếp từ ngân hàng. Tỷ giá
  SGD/USD áp dụng và ngày tỷ giá được ghi ở `salary_fx_rate_to_vnd`, `salary_fx_rate_date` và
  `salary_fx_source`; số tiền SGD gốc vẫn được giữ ở `salary_min_original`, `salary_max_original` và
  `salary_currency_original`.
- Nếu ngày đăng không có tỷ giá (ngày nghỉ/cuối tuần), dùng ngày có tỷ giá gần nhất trước đó. Nếu thiếu
  ngày đăng thì lấy ngày crawl; nếu không có cả hai hoặc API không có tỷ giá thì dừng với lỗi rõ ràng,
  không âm thầm ghi lương SGD thành VND. Hiện EDA nhận diện VND, USD và SGD; mã tiền khác nếu xuất hiện
  sẽ được giữ nguyên dữ liệu gốc và thống kê là chưa quy đổi, không tự chọn tỷ giá không có căn cứ.
- Runner kiểm tra đầu vào JSON, bảo toàn số lượng bản ghi và raw fields; không thực hiện imputation,
  xóa bản ghi hay winsorization.
- **Cascade Salary Extraction:**
  - Giải quyết bài toán *"Lương nằm trong mô tả công việc"*: Với $60\% - 70\%$ bài đăng ghi "Thỏa thuận" ở header, module `UniversalSalaryParser` kích hoạt bộ quét regex trên clean JD text để bóc tách lương ngầm định.
  - Giải quyết bài toán *"Lương năm"*: Nhận diện các bài đăng ghi thu nhập 300 - 500 triệu/năm và tự động quy đổi về lương tháng bằng phép chia cho 12.
  - Lưu trữ minh bạch: Giữ cờ `is_salary_negotiable_declared = 1` và lưu giá trị bóc tách được vào `salary_min_vnd`, `salary_max_vnd` kèm `salary_source = 'jd_regex'`.

### 2.2. Giai Đoạn 3: Bù Khuyết Bằng GenAI & Xử Lý Ngoại Lai (Missing & Outlier)
- **Cơ Chế Phản Hồi Vòng Lặp & Bộ Lọc Tiền Kiểm Định (Heuristic Scrubber & Cyclic Loop):**
  - Khảo sát thực chứng hậu Transformer phát hiện các dị biệt mới: Bắt nhầm số điện thoại liên hệ (sau tên người có chữ "Lương" như `"Khánh Lương SĐT 0243.936.6990"` thành 243 triệu) hoặc số bị che giấu (`"1*** USD"` thành 25,400 VND).
  - Trước khi tính phân vị IQR, module `outlier_handler.py` kích hoạt `scrub_salary_false_positives` để reset các trường hợp này về `None` và bật `is_negotiable = 1` an toàn.
- **Quy Chuẩn Quản Trị AI Bắt Buộc Có Xác Nhận (Human-in-the-Loop AI Sign-off):**
  - GenAI Imputer (Gemini 1.5 Flash) **tuyệt đối không được chạy tự do**. Bắt buộc chạy Pilot đối chứng (20 mẫu), xuất báo cáo kiểm định và chỉ thực thi khi có sự xác nhận của Bạn (User) và Team.
  - Tầng Heuristic (Regex trích xuất kinh nghiệm từ câu văn JD) được ưu tiên xử lý trước để giảm thiểu chi phí token.
- **GenAI Missing Value Imputation (Gemini 1.5 Flash - Có Phê Duyệt):**
  - Đọc toàn bộ văn bản JD để bù khuyết các trường bị trống:
    - Thiếu kinh nghiệm $\rightarrow$ Đọc câu yêu cầu trích xuất số năm (`min_experience_years`).
    - Thiếu cấp bậc $\rightarrow$ Suy luận bậc chuẩn (`job_seniority`: Intern, Junior, Middle, Senior, Lead).
    - Thiếu thành phố $\rightarrow$ Đọc địa chỉ văn phòng suy luận `primary_city`.
    - Danh mục `skills_list` rỗng $\rightarrow$ Trích xuất danh sách Hard Skills và Domain Skills.
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

## 3. Bản Xuất Bản Hồ Sơ Dữ Liệu Vàng Sau Tiền Xử Lý (Golden Deliverables Standard)

Sau khi xử lý qua Master Pipeline, toàn bộ hệ thống xuất bản đúng bộ tài liệu và sản phẩm dữ liệu vàng chuẩn mực:

```text
+----------------------------------------------------------------------------------------------------+
|                         BỘ TÀI LIỆU VÀ SẢN PHẨM DỮ LIỆU VÀNG XUẤT BẢN CHUẨN MỰC                    |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  FILE 1: BỘ DỮ LIỆU VÀNG PHÂN TẦNG (Golden Master Nested Dataset)                                  |
|  * Đường dẫn: data/curated/golden_master.json                                                      |
|  * Định dạng: 100% PURE RFC 8259 JSON, đúng 11 Khóa Gốc, Zero-null lương, mô tả tiếng Việt sạch.   |
|                                                                                                    |
|  FILE 2: BẢNG DỮ LIỆU VÀNG PHẲNG (Curated Flat Golden Dataset)                                    |
|  * Đường dẫn: data/curated/curated_flat_golden_jobs.json                                           |
|  * Định dạng: Bảng phẳng 1 tầng phục vụ nạp trực tiếp vào DuckDB, Pandas, Polars và Scikit-Learn.  |
|                                                                                                    |
|  FILE 3: BÁO CÁO KIỂM ĐỊNH CHẤT LƯỢNG QA (QA Pipeline Validation Report)                          |
|  * Đường dẫn: reports/qa/qa_pipeline_report.md (Markdown) & reports/qa/qa_pipeline_report.json     |
|  * Định dạng: Báo cáo kết quả kiểm định 5 khế ước chất lượng tự động đạt 5/5 PASSED.               |
|                                                                                                    |
|  FILE 4: BỆNH ÁN CHẤT LƯỢNG DỮ LIỆU VÀNG (Curated Golden Dataset Health Card)                      |
|  * Đường dẫn: reports/curated_golden_dataset_health_card.json                                      |
|  * Định dạng: Tệp JSON đo lường chi tiết phân vị lương, độ hoàn thiện của từng trường và thống kê.  |
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
