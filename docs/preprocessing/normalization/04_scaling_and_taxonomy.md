# BƯỚC 4: CHUẨN HÓA TOÀN DIỆN, TAXONOMY & ĐẶC TẢ BỘ DỮ LIỆU VÀNG (FINAL NORMALIZATION & GOLDEN MASTER PROTOCOL)

> **Tài liệu quy chuẩn số 04 (Preprocessing Core Document 04 — Step 4: Final Normalization)**  
> **Dự án:** Phân tích thị trường lao động IT và nhu cầu kỹ năng nghề nghiệp tại Việt Nam (**VN-IT-Job-Mining**)  
> **Sứ mệnh:** Thiết lập Cổng kiểm soát điều kiện tiên quyết (Pre-Normalization Readiness Gate), quy chuẩn 9 chiều chuẩn hóa chuyên sâu (Deep Normalization Engine), và định hình Khế ước Bộ Dữ Liệu Vàng (Golden Master Dataset Schema - Target Schema 3) phục vụ 5 mục tiêu chiến lược SD1 — SD5.  
> **Nguyên tắc bất biến:** Không áp dụng Normalization trên dữ liệu bẩn; Xóa bỏ 100% các cột thô `raw_*` ở root level khi tạo Golden Dataset.

---

## 1. Mục Đích & Ranh Giới Đanh Thép Của Bước 4 (Final Normalization)

Bước 4 là **chặng đích cuối cùng** của toàn bộ quy trình tiền xử lý dữ liệu. Dữ liệu sau bước này không còn mang tính chất trung gian mà được đóng gói thành **Bộ Dữ Liệu Vàng (Golden Master Dataset)** hoàn chỉnh, bất biến, tối ưu hóa cho các thuật toán Data Mining (Phân cụm, Phân loại, Khai phá luật kết hợp, Dự báo chuỗi thời gian).

```text
+----------------------------------------------------------------------------------------------------+
|                      RANH GIỚI BẮT BUỘC CỦA BƯỚC 4 (FINAL NORMALIZATION)                           |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [ĐẦU VÀO - INPUT]:                                                                                |
|  - Bảng dữ liệu phẳng đã vượt qua Cổng Kiểm Soát Điều Kiện Tiên Quyết (Readiness Gate):            |
|    + Không còn thẻ HTML, text sạch nhưng bảo toàn 100% token công nghệ (C++, C#, .NET, CI/CD).     |
|    + Lương đã parse Cascade, quy đổi USD/SGD -> VND (tỷ giá 25,400), năm/giờ -> tháng.             |
|    + Sneaky null markers đã bóc trần, cờ is_salary_negotiable = 1 được bảo vệ an toàn.             |
|    + Bù khuyết GenAI (Gemini) đã có Sign-off; Ngoại lai IQR đã được kiểm định & Winsorization.     |
|                                                                                                    |
|  [ĐƯỢC PHÉP LÀM (DO)]:                                                                             |
|  1. Thực hiện Log-transformation cho mức lương: log_salary = log(1 + salary_max_vnd).              |
|  2. Thực hiện RobustScaler / Min-Max Scaling cho các thuộc tính số học phục vụ mô hình hóa.       |
|  3. Chuẩn hóa Kỹ năng 3 chiều: Hard Skills (ESCO/Canonical), Soft Skills, Domain Skills.           |
|  4. Lọc bỏ 100% tag rác danh mục sàn (Portal Noise Skills: 'cntt', 'phần mềm', 'bán hàng').        |
|  5. Chuẩn hóa Chức danh tuyển dụng về 12 Job Family chuẩn ngành IT Việt Nam (SD2).                 |
|  6. Chuẩn hóa Cấp bậc nghề nghiệp về 6 bậc chuẩn (Intern -> Lead/Manager) (SD1).                   |
|  7. Phân cấp Địa bàn 3 cấp: cities_list (63 tỉnh thành), districts_list, detailed_locations.      |
|  8. Khai phá các thuộc tính nâng cao: is_saturday_work, work_mode, standardized_education,        |
|     age_min, age_max, employment_type.                                                             |
|  9. Khử trùng lặp thực thể xuyên sàn (Blocking + TF-IDF Cosine Similarity >= 0.82) -> Golden Record|
| 10. XÓA BỎ 100% CÁC TRƯỜNG raw_* Ở ROOT LEVEL TRONG GOLDEN DATASET (Thuần JSON RFC 8259).          |
|                                                                                                    |
|  [TUYỆT ĐỐI CẤM (DO NOT DO)]:                                                                      |
|  - CẤM chạy Normalization khi dữ liệu chưa pass Cổng Kiểm Soát Tiền Đề (Readiness Gate).          |
|  - CẤM scale hoặc Log-transform dữ liệu khi chưa qua bước Winsorization Outlier.                   |
|  - CẤM xóa bỏ ký tự đặc thù làm sai lệch tên công nghệ (biến C++, C# thành C).                    |
|  - CẤM xuất file Parquet/CSV ở tầng Golden (100% tuân thủ quy chuẩn Thuần JSON của dự án).        |
|                                                                                                    |
|  [ĐẦU RA - OUTPUT]:                                                                                |
|  - BỘ DỮ LIỆU VÀNG: data/curated/curated_golden_master_dataset.json (Golden Master Dataset).       |
|  - BỆNH ÁN CHẤT LƯỢNG: reports/curated_golden_dataset_health_card.json                             |
|  - MANIFEST CHUẨN HÓA: reports/curated_golden_dataset_transformation_manifest.md                 |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. Cổng Kiểm Soát Điều Kiện Tiên Quyết (Pre-Normalization Readiness Gate)

Trước khi kích hoạt runner `preprocessing.normalization.run_deep_normalization`, kỹ sư dữ liệu và AI Agent **bắt buộc phải đối chiếu 5 Trạm kiểm soát** dưới đây. Nếu một trạm có kết quả **FAIL**, quy trình phải dừng lại để xử lý ở bước tương ứng, tuyệt đối không được ép chạy:

```text
+----------------------------------------------------------------------------------------------------+
|                         CỔNG KIỂM SOÁT 5 TRẠM TRƯỚC KHI NORMALIZATION                              |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|   [TRẠM 1: INTEGRATION]  ───>  [TRẠM 2: TRANSFORMATION] ───>  [TRẠM 3: SNEAKY NULL & GENAI]        |
|   - Flat single table          - Regex Cascade Salary         - 9+ null markers bóc trần           |
|   - Zero nested dict/list      - USD/SGD -> VND (25,400)      - is_negotiable = 1 an toàn          |
|   - job_id_global duy nhất     - ISO 8601 Date & min_exp      - GenAI sign-off 20 samples          |
|                                                                             │                      |
|                                                                             ▼                      |
|   [CHẤP THUẬN NORMALIZATION]  <───  [TRẠM 5: TEXT PROCESSING] <───  [TRẠM 4: OUTLIER & WINSORIZE]  |
|   (Bật Deep Normalization)          - Strip HTML tag 100%           - Sửa 3 lỗi số (SĐT/Lộ số)     |
|                                     - Bảo vệ C++, C#, .NET          - Capping P1 - P99             |
|                                     - Unicode NFC & dọn ẩn          - Không drop dòng              |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

### Bảng Tiêu Trí Kiểm Tra Cụ Thể (Readiness Checklist)

| Trạm | Tiêu chí kỹ thuật bắt buộc | Ngưỡng đạt chuẩn (PASS Criteria) | Rủi ro nếu bỏ qua | Trạng thái |
| :---: | :--- | :--- | :--- | :---: |
| **1** | **Bảng Phẳng Tích Hợp (Integration)** | 100% bản ghi (9,390 bài) nằm trong schema 20 cột phẳng; `job_id_global` không trùng lặp; không còn lồng nhau. | Gây crash khi ép kiểu vector và băm khóa blocking. | [ ] PASS |
| **2** | **Quy đổi Ngoại tệ & Chu kỳ (Currency & Period)** | 100% tin lương USD quy đổi theo tỷ giá cố định 25,400 VND/USD; SGD quy đổi theo tỷ giá lịch sử Frankfurter $\times 25,400$; Lương năm chia 12. | Phân phối lương bị nhảy vọt hàng ngàn lần; phá vỡ Log-transformation. | [ ] PASS |
| **3** | **Bóc trần Null Trá Hình (Sneaky Nulls)** | Các giá trị `""`, `"none"`, `"thỏa thuận"`, `"0"`, `"[]"` được đưa về `None/NaN`; tin thỏa thuận bật `is_salary_negotiable = 1`. | Thống kê sai lệch mức lương trung bình; điền nhầm 0 VND vào bài đăng thương lượng. | [ ] PASS |
| **4** | **Phê duyệt Bù khuyết GenAI (GenAI Sign-off)** | Chạy Pilot đối chứng 20 mẫu cho kinh nghiệm/kỹ năng; có biên bản xác nhận của User & Team trước khi áp dụng batch. | Mô hình LLM hallucinate làm sai lệch yêu cầu kỹ năng và cấp bậc thực tế. | [ ] PASS |
| **5** | **Khử Ngoại Lai IQR & Winsorization (Outlier)** | Phát hiện và reset lỗi bắt nhầm SĐT ("Khánh Lương SĐT 0243..."); Capping giá trị lương tại $P_1$ (1%) và $P_{99}$ (99%); Không drop dòng. | Đuôi phân phối kéo dài vô tận ($Skewness > 5.0$), các thuật toán K-Means/PCA bị méo mó. | [ ] PASS |
| **6** | **Tiền Xử Lý Text & Bảo Toàn Tech Tokens** | Bóc HTML trước; Giải mã thực thể HTML; Unicode chuẩn NFC; **Bảo vệ tuyệt đối `C++`, `C#`, `.NET`, `CI/CD` không bị xóa ký tự**. | `C++` và `C#` biến thành chữ `C`; `.NET` thành `NET`; mất trắng kỹ năng lập trình trọng yếu. | [ ] PASS |

---

## 3. Quy Chuẩn 9 Chiều Chuẩn Hóa Chuyên Sâu (Deep Normalization Engine)

Toàn bộ logic được hiện thực hóa trong module [`preprocessing.normalization.deep_normalizer`](file:///run/media/billtran/Data/Archduker/Study/UTH/Core/DataMining/VN-IT-Job-Mining/preprocessing/normalization/deep_normalizer.py) và điều phối qua runner [`preprocessing.normalization.run_deep_normalization`](file:///run/media/billtran/Data/Archduker/Study/UTH/Core/DataMining/VN-IT-Job-Mining/preprocessing/normalization/run_deep_normalization.py).

### 3.1. Chiều 1: Kỹ Năng 3 Phân Lớp & Lọc Rác Danh Mục Sàn (Skills Taxonomy)

Kỹ năng từ mảng `skills_list` và văn bản JD được bóc tách và phân loại nghiêm ngặt thành 3 danh mục độc lập, đồng thời loại bỏ các tag rác do sàn tuyển dụng gắn tự động:

```text
+----------------------------------------------------------------------------------------------------+
|                           HỆ THỐNG PHÂN LOẠI KỸ NĂNG 3 CHIỀU                                       |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [1. HARD SKILLS (TECH STACK)] ───> Canonical Mapping về chuẩn danh pháp công nghệ quốc tế:        |
|  * Frontend : React, Vue, Angular, Next.js, Nuxt.js, TypeScript, JavaScript, HTML, CSS, Tailwind    |
|  * Backend  : Node.js, Express.js, NestJS, Python, Django, FastAPI, Java, Spring, Go, PHP, C#, .NET|
|  * Mobile   : Flutter, React Native, iOS (Swift), Android (Kotlin)                                 |
|  * Database : SQL, PostgreSQL, MySQL, MongoDB, Redis, Elasticsearch, Oracle DB, SQL Server         |
|  * DevOps   : Docker, Kubernetes, AWS, Azure, GCP, CI/CD, Jenkins, Terraform, Linux, Kafka         |
|  * AI/Data  : Spark, Airflow, PyTorch, TensorFlow, Scikit-Learn, NLP, LLM, Generative AI, Pandas   |
|                                                                                                    |
|  [2. SOFT SKILLS (KỸ NĂNG MỀM)] ───> Ánh xạ các kỹ năng tương tác và phương pháp luận:             |
|  * Ngoại ngữ: Tiếng Anh, Tiếng Nhật (N1, N2, N3), Tiếng Hàn                                       |
|  * Làm việc: Giao tiếp, Làm việc nhóm, Giải quyết vấn đề, Tư duy logic, Quản lý thời gian         |
|  * Quy trình: Agile/Scrum, Kanban, Thuyết trình, Chịu áp lực cao                                   |
|                                                                                                    |
|  [3. DOMAIN KNOWLEDGE (NGHIỆP VỤ)] ───> Nhận diện miền nghiệp vụ ứng dụng:                        |
|  * Tài chính & Ngân hàng: Fintech, Banking, Payment Gateway                                       |
|  * Thương mại & Dịch vụ: E-Commerce, Logistics, Edtech, Healthtech, Proptech, Insurtech            |
|  * Bảo mật & Web3       : Cybersecurity, An toàn thông tin, Blockchain, Web3                       |
|                                                                                                    |
|  [BỘ LỌC RÁC SÀN (PORTAL NOISE PURGER)] ───> Xóa bỏ 100% các tag chung chung:                      |
|  'it - phần mềm', 'cntt', 'phần mềm máy tính', 'kinh doanh', 'nhân sự', 'bán hàng', 'khác'         |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

### 3.2. Chiều 2: Chuẩn Hóa 12 Nhóm Nghề Nghiệp (12 Job Families Taxonomy - SD2)

Mọi chức danh công việc tự do (`job_title`) và kỹ năng đi kèm được phân loại vào **12 Job Family chuẩn** của ngành IT Việt Nam:

| Mã Nhóm (Code) | Tên Job Family Chuẩn | Từ Khóa Nhận Diện Đặc Trưng (Keywords) |
| :--- | :--- | :--- |
| `JF01_BACKEND` | Backend Development | Java, Spring, Node.js, Python, Golang, PHP, .NET, Django, C#, Ruby, Scala |
| `JF02_FRONTEND` | Frontend Development | React, Vue, Angular, Next.js, HTML/CSS, Tailwind, TypeScript, Nuxt |
| `JF03_FULLSTACK` | Fullstack Development | Fullstack, Full-stack, MERN, MEVN, Web Developer |
| `JF04_MOBILE` | Mobile App Development | Flutter, React Native, iOS, Android, Swift, Kotlin |
| `JF05_DEVOPS` | DevOps / Cloud / SRE / SysAdmin | Docker, Kubernetes, CI/CD, AWS, Azure, GCP, Linux, Terraform, SRE |
| `JF06_DATA_ENG` | Data Engineering & Big Data | Spark, Hadoop, Kafka, Airflow, ETL, DWH, BigQuery, Databricks, Data Pipeline |
| `JF07_DATA_AI` | Data Science / AI / Machine Learning | Machine Learning, Deep Learning, PyTorch, TensorFlow, NLP, LLM, Computer Vision |
| `JF08_QA_QC` | Software QA / QC / Automation Test | Tester, QA, QC, Automation, Selenium, Playwright, Cypress, Postman, Manual Test |
| `JF09_SECURITY` | Cyber Security / InfoSec | SOC, Pentest, SIEM, Security, ISO 27001, CEH, CISSP, An toàn thông tin |
| `JF10_PROD_BA` | Product Management / Business Analyst | Product Owner, PO, PM, Business Analyst, BA, Scrum Master, Project Manager |
| `JF11_UI_UX` | UI/UX Design | Figma, UI/UX, Design, Wireframe, Prototype, Adobe XD |
| `JF12_EMBEDDED`| Embedded Systems / IoT / Hardware | C/C++, Embedded, IoT, Firmware, PLC, RTOS, PCB, Vi điều khiển |

### 3.3. Chiều 3: Chuẩn Hóa 6 Cấp Bậc Nghề Nghiệp (Seniority - SD1)

Chuẩn hóa trường `seniority_text` và nội dung JD về 6 bậc chuẩn quốc tế:
1. **`Intern`**: Thực tập sinh, Sinh viên thực tập, Trainee.
2. **`Fresher`**: Mới tốt nghiệp, dưới 1 năm kinh nghiệm, đang đào tạo on-the-job.
3. **`Junior`**: Từ 1 đến dưới 2 năm kinh nghiệm, thực thi task dưới sự hướng dẫn.
4. **`Middle`**: Từ 2 đến 4 năm kinh nghiệm, làm việc độc lập, làm chủ tính năng.
5. **`Senior`**: Từ 4 đến 7 năm kinh nghiệm, giải quyết bài toán kiến trúc, mentor cấp dưới.
6. **`Lead/Manager`**: Trên 7 năm kinh nghiệm, Tech Lead, Team Lead, Engineering Manager, Director, CTO.

### 3.4. Chiều 4: Phân Cấp Địa Bàn 3 Cấp (Hierarchical Locations)

Một bài đăng IT thường tuyển dụng cho nhiều chi nhánh hoặc làm việc linh hoạt. Hệ thống phân rã thành 3 trường độc lập:
- `cities_list` (`list[str]`): Danh sách tên Tỉnh/Thành phố chuẩn (đối chiếu danh mục 63 tỉnh thành Việt Nam hoặc `"Remote"`, `"Toàn quốc"`).
- `districts_list` (`list[str]`): Danh sách Quận/Huyện bóc tách được (ví dụ: `"Cầu Giấy"`, `"Quận 1"`, `"Bình Thạnh"`, `"Thành Phố Thủ Đức"`).
- `detailed_locations` (`list[dict]`): Mảng phân cấp chi tiết từng cơ sở `{province: ..., district: ..., full_address: ...}`.

### 3.5. Chiều 5: Khai Phá Chế Độ Làm Việc Thứ 7 (`is_saturday_work`)

Văn hóa làm việc Thứ 7 là một biến số phân hóa cực lớn trong đãi ngộ ngành IT:
- Quét các câu văn trong `raw_working_time` và `raw_description_text`:
  - `"làm từ thứ 2 đến thứ 6"`, `"nghỉ thứ 7 và chủ nhật"`, `"không làm thứ 7"` $\to$ `is_saturday_work = False`.
  - `"làm sáng thứ 7"`, `"thứ 7 cách tuần"`, `"làm từ thứ 2 đến thứ 7"` $\to$ `is_saturday_work = True`.
  - Không đề cập $\to$ `is_saturday_work = None` (Null an toàn).

### 3.6. Chiều 6: Hình Thức Làm Việc (`work_mode`)

Ánh xạ về 3 giá trị chuẩn:
- **`Remote`**: Làm việc từ xa 100%, WFH, toàn quốc.
- **`Hybrid`**: Kết hợp lên văn phòng và làm từ xa (ví dụ: 2 ngày WFH / tuần).
- **`Onsite`**: Làm việc trực tiếp toàn thời gian tại văn phòng / trụ sở.

### 3.7. Chiều 7: Học Vấn, Độ Tuổi & Loại Hợp Đồng

- **`standardized_education`**: `Đại học`, `Cao đẳng`, `Không yêu cầu`.
- **`age_min` / `age_max`**: Bóc tách dải tuổi tuyển dụng (`int / None`), ví dụ: `"Từ 22 - 30 tuổi"` $\to$ `age_min = 22`, `age_max = 30`.
- **`employment_type`**: `Full-time`, `Part-time`, `Internship`, `Contract`.

### 3.8. Chiều 8: Biến Đổi Phân Phối Số Học & Thang Đo (Scaling & Log-Transform)

Dữ liệu lương IT Việt Nam có chỉ số độ lệch $\text{Skewness} > 5.0$ do các vị trí Director/Architect kéo đuôi dài:
- **Biến đổi Log-Transformation:**
  $$\text{log\_salary\_max} = \log(1 + \text{salary\_max\_vnd})$$
  $$\text{log\_salary\_min} = \log(1 + \text{salary\_min\_vnd})$$
- **Chuẩn hóa Thang đo (Robust Scaling):**
  $$\text{salary\_scaled} = \frac{x - Q_2(x)}{Q_3(x) - Q_1(x)}$$
  *(Sử dụng Trung vị và Khoảng Tứ phân vị IQR để triệt tiêu ảnh hưởng của giá trị biên).*

### 3.9. Chiều 9: Khử Trùng Lặp Thực Thể Xuyên Sàn (Cross-Platform Entity Resolution)

Một vị trí tuyển dụng thường được đăng đồng thời trên nhiều sàn với văn phong hơi khác nhau:
1. **Khối Lọc Thô (Blocking):** Gom nhóm các bài đăng có cùng `company_name` (sau chuẩn hóa) và cùng `primary_city`.
2. **So Khớp Ngữ Nghĩa (Semantic Cosine Matching):** Tính toán Cosine Similarity trên ma trận TF-IDF của phần mô tả JD giữa các bài đăng trong cùng Block. Ngưỡng tương đồng quy chuẩn: $\text{Cosine} \ge 0.82$.
3. **Quy Tắc Chọn Bản Ghi Vàng (Golden Record Survivorship Rule):**
   - Trong một cụm trùng lặp (`cluster_id`), bản ghi có độ đầy đủ thông tin cao nhất (nhiều kỹ năng nhất, có dải lương công khai) được chọn làm đại diện chính.
   - Các trường thiếu ở bài đăng chính được bù đắp từ bài đăng phụ đối ứng.

---

## 4. Khế Ước Bộ Dữ Liệu Vàng (Golden Master Dataset Schema - Target Schema 3)

> [!CAUTION]
> **Quy định dọn dẹp cấp gốc (Root-Level Purge Rule):**  
> Trong tệp xuất bản cuối cùng `curated_golden_master_dataset.json`, **100% các cột có tiền tố `raw_*` ở cấp gốc bị XÓA BỎ HOÀN TOÀN**. Các giá trị gốc nếu cần lưu vết sẽ được đóng gói gọn trong sub-object `provenance` hoặc tham chiếu qua `source_url`.

### Bảng Đặc Tả Trường Bộ Dữ Liệu Vàng (Golden Flat Record)

| Tên trường vàng | Kiểu dữ liệu | Ý nghĩa nghiệp vụ | Nguồn gốc tạo thành |
| :--- | :--- | :--- | :--- |
| `job_id_global` | `str` | Khóa chính duy nhất toàn hệ thống (`source_id`) | Khóa định danh từ Integration |
| `source_platform` | `str` | Sàn tuyển dụng gốc | Sàn thu thập |
| `source_url` | `str` | Đường dẫn bài đăng gốc | Link URL gốc |
| `job_title` | `str` | Tiêu đề công việc đã gọt tag địa danh và lương | `clean_job_title()` |
| `job_family` | `str` | 1 trong 12 Job Family chuẩn IT (SD2) | `classify_job_family()` |
| `seniority` | `str` | 1 trong 6 cấp bậc chuẩn (Intern -> Lead/Manager) | `normalize_seniority()` |
| `company_name` | `str` | Tên công ty đã chuẩn hóa | `normalize_company_name()` |
| `company_scale` | `str / null` | Quy mô nhân sự doanh nghiệp | Chuẩn hóa quy mô |
| `company_address` | `str / null` | Địa chỉ trụ sở doanh nghiệp | Địa chỉ đã làm sạch |
| `company_industry` | `str / null` | Lĩnh vực kinh doanh | Lĩnh vực doanh nghiệp |
| `salary_min_vnd` | `float / null`| Lương tối thiểu (VND/tháng) đã xử lý ngoại lai | Regex Cascade + Winsorization |
| `salary_max_vnd` | `float / null`| Lương tối đa (VND/tháng) đã xử lý ngoại lai | Regex Cascade + Winsorization |
| `log_salary_max` | `float / null`| Lương tối đa sau biến đổi Log: $\log(1 + \text{vnd})$ | `log_transform_salary()` |
| `is_salary_negotiable`| `bool` | Cờ lương thỏa thuận (MNAR) | Sneaky Null Detector |
| `min_experience_years`| `float / null`| Số năm kinh nghiệm tối thiểu yêu cầu | Date & Experience Parser |
| `cities_list` | `list[str]` | Danh sách tỉnh/thành chuẩn (63 tỉnh + Remote) | `extract_hierarchical_locations()` |
| `districts_list` | `list[str]` | Danh sách quận/huyện chuẩn | `extract_hierarchical_locations()` |
| `work_mode` | `str` | `Remote`, `Hybrid`, hoặc `Onsite` | `extract_work_mode()` |
| `is_saturday_work` | `bool / null` | Chế độ làm việc Thứ 7 | `extract_saturday_work()` |
| `standardized_education`| `str` | Trình độ học vấn chuẩn hóa | `extract_education()` |
| `age_min` / `age_max` | `int / null` | Giới hạn độ tuổi tuyển dụng | `extract_age_range()` |
| `employment_type` | `str` | `Full-time`, `Part-time`, `Internship` | `normalize_employment_type()` |
| `tech_skills` | `list[str]` | Danh sách kỹ năng công nghệ chuẩn hóa ESCO | `extract_normalized_skills()` |
| `soft_skills` | `list[str]` | Danh sách kỹ năng mềm | `extract_normalized_skills()` |
| `domain_skills` | `list[str]` | Danh sách kỹ năng nghiệp vụ miền | `extract_normalized_skills()` |
| `benefits_list` | `list[str]` | Danh sách chế độ phúc lợi đã lọc tiền tố rác | `clean_benefits_list()` |
| `jd_clean_text` | `str` | Toàn văn mô tả JD đã bóc HTML và dọn sạch | `clean_text_for_extraction()` |
| `posted_date` | `str / null` | Ngày đăng tuyển chuẩn ISO 8601 (`YYYY-MM-DD`) | Date Parser |
| `deadline_date` | `str / null` | Hạn nộp hồ sơ chuẩn ISO 8601 (`YYYY-MM-DD`) | Date Parser |
| `cluster_id` | `str / null` | Mã cụm bài đăng trùng lặp xuyên sàn | `cross_deduplicator` |
| `quality_score` | `float` | Điểm chất lượng thông tin bài đăng ($0.0 - 1.0$) | `quality_rules.py` |

---

## 5. Kịch Bản Thực Thi (Execution Runbook) & Bộ 3 Deliverables

### 5.1. Lệnh Thực Thi Master Runner

Sau khi đã xác nhận đạt toàn bộ tiêu chí tại Cổng kiểm soát (Readiness Gate), kỹ sư thực thi lệnh duy nhất:

```bash
# Chạy bộ chuẩn hóa chuyên sâu trên toàn bộ bài đăng đã transform
python -m preprocessing.normalization.run_deep_normalization
```

### 5.2. Tiêu Chuẩn Bộ 3 Tài Liệu Nghiệm Thu (The 3-Deliverables Standard)

Sau khi hoàn thành, hệ thống xuất bản đúng bộ 3 tài liệu tại các đường dẫn quy ước:

```text
+----------------------------------------------------------------------------------------------------+
|                         BỘ 3 TÀI LIỆU NGHIỆM THU CHUẨN MỰC BƯỚC NORMALIZATION                      |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  FILE 1: BỘ DỮ LIỆU VÀNG HOÀN CHỈNH (Curated Golden Master Dataset)                                |
|  * Đường dẫn: data/curated/curated_golden_master_dataset.json                                        |
|  * Định dạng: 100% Thuần JSON (RFC 8259), xóa sạch cột raw_*, chuẩn hóa toàn diện 9 chiều.         |
|                                                                                                    |
|  FILE 2: BỆNH ÁN & CHỈ SỐ CHẤT LƯỢNG TOÀN DIỆN (Data Health Card)                                 |
|  * Đường dẫn: reports/curated_golden_dataset_health_card.json                                      |
|  * Định dạng: Tệp JSON đo lường tỷ lệ hoàn thiện trường, độ phủ 12 Job Family, phân phối 6 cấp bậc,|
|    phân vị lương P1-P99, và số lượng bài đăng trùng lặp xuyên sàn đã giải quyết.                   |
|                                                                                                    |
|  FILE 3: BẢNG GIẢI TRÌNH ÁNH XẠ CHUẨN HÓA (Transformation Manifest)                               |
|  * Đường dẫn: reports/curated_golden_dataset_transformation_manifest.md                            |
|  * Định dạng: Báo cáo Markdown chi tiết minh bạch hóa toàn bộ quá trình biến đổi (Data Lineage),   |
|    bảng so sánh Before vs After đại diện cho từng nhóm dữ liệu đặc thù.                            |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

---

## 6. Tiêu Chí Nghiệm Thu Hoàn Thành (Definition of Done - DoD)

Một lần chạy Normalization được công nhận hoàn thành khi thỏa mãn 7 điều kiện kiểm toán:
1. **Định dạng Thuần JSON:** Tệp `curated_golden_master_dataset.json` mở được bằng `json.load()` mà không gặp bất kỳ lỗi encode hay `NaN` không chuẩn.
2. **Zero Raw Fields:** Kiểm tra `any(k.startswith('raw_') for k in record.keys()) == False` trên 100% bản ghi.
3. **100% Job Family Assigned:** Tất cả bài đăng đều được gán vào 1 trong 12 Job Family chuẩn (hoặc `"JF13_OTHER_IT"` nếu ngoài danh mục).
4. **Bảo Toàn Kỹ Năng IT:** Không có trường hợp nào công nghệ `C++` hoặc `C#` bị lưu thành chữ `C`.
5. **Đồng Bộ Ngoại Tệ:** Không còn bất kỳ mức lương ngoại tệ USD nào chưa được nhân tỷ giá 25,400 sang VNĐ.
6. **Đầy Đủ Bộ 3 Deliverables:** Cả 3 tệp đầu ra tại Section 5.2 đều được sinh ra và ghi nhận timestamp khớp nhau.
7. **Báo Cáo Đối Chứng Before-After:** Tệp `reports/curated_sample_visual_comparison.json` hiển thị sự nâng cấp rõ rệt về chất lượng giữa bản ghi thô và bản ghi Vàng.
