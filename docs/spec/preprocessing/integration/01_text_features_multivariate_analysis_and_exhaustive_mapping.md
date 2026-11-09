# KHAI BÁO ÁNH XẠ TOÀN DIỆN (EXHAUSTIVE MAPPING) & PHÂN TÍCH ĐƠN BIẾN / ĐA BIẾN DỮ LIỆU VĂN BẢN (TEXT FEATURES)

> **Tài liệu quy chuẩn số 01.B (Preprocessing Core Document 01.B — Exhaustive Mapping & Text Intelligence)**  
> **Dự án:** Phân tích thị trường lao động IT và nhu cầu kỹ năng nghề nghiệp tại Việt Nam (**VN-IT-Job-Mining**)  
> **Nguyên tắc chỉ đạo:**  
> 1. Khai báo 100% ánh xạ tất cả các trường từ 8 sàn tuyển dụng về Bảng Phẳng Chuẩn.  
> 2. Phân tích định lượng Đơn biến (Univariate) và Đa biến (Multivariate) trên các trường văn bản tự do (`job_title`, `description`, `requirements`, `benefits`).  
> 3. Tổng hợp toàn bộ vấn đề của 8 nguồn vào một bảng đối chiếu tập trung duy nhất (kết hợp Integration & Phân tích).  
> 4. Ma trận phân bổ công việc (Work Breakdown Structure) phân định rõ bước nào xử lý phần nào.  
> 5. Chính sách đã phê duyệt: Loại bỏ bài đăng rác siêu ngắn (Stub JD < 30 từ); Chuẩn hóa dịch thuật đồng nhất về tiếng Việt.  
> 6. Tuyệt đối không dùng Mermaid (100% bảng Markdown và sơ đồ khối ASCII).

---

## 1. Khai Báo Ánh Xạ Toàn Diện 100% Các Trường (Exhaustive Mapping Declaration)

Để toàn bộ kỹ sư dữ liệu và Agent nắm rõ đường đi của dữ liệu, bảng dưới đây khai báo chi tiết **100% các biến thể trường thô** từ 8 sàn tuyển dụng (`careerviet`, `glints`, `itviec`, `jobsgo`, `topcv`, `topdev`, `vieclam24h`, `vietnamworks`) được ánh xạ về Bảng Phẳng Chuẩn (`CanonicalStagingFlatJob`):

```text
+----------------------------------------------------------------------------------------------------+
|                         BẢNG KHAI BÁO ÁNH XẠ 100% CÁC TRƯỜNG DỮ LIỆU ĐA NGUỒN                      |
+----------------------------------------------------------------------------------------------------+
```

| Cột Phẳng Chuẩn (Target Column) | Kiểu Dữ Liệu | Nguồn TopCV | Nguồn TopDev | Nguồn VietnamWorks | Nguồn ITViec | Nguồn CareerViet | Nguồn Vieclam24h | Nguồn Glints | Nguồn JobsGO | Logic Ép Phẳng & Fallback |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`job_id_global`** | `str` (PK) | `'topcv_' + job_id` | `'topdev_' + id` | `'vnw_' + jobId` | `'itviec_' + job_id` | `'careerviet_' + job_id`| `'vieclam24h_' + id`| `'glints_' + id` | `'jobsgo_' + id` | Sinh mã duy nhất toàn cục dạng `<source>_<id>`. |
| **`source_platform`** | `str` | `'topcv'` | `'topdev'` | `'vietnamworks'` | `'itviec'` | `'careerviet'` | `'vieclam24h'` | `'glints'` | `'jobsgo'` | Định danh nguồn sàn tuyển dụng. |
| **`source_url`** | `str` | `metadata.source_url` | `raw_payload.detail_url` | `raw_payload.jobUrl` | `metadata.source_url` | `metadata.source_url` | `metadata.source_url` | `metadata.source_url` | `metadata.source_url` | Làm sạch tracking params (`utm_*`, `ref`). |
| **`job_title`** | `str` | `raw_payload.title` | `raw_payload.title` hoặc `job-title` | `raw_payload.jobTitle` hoặc `title` | `raw_payload.title` | `raw_payload.title` | `raw_payload.title` | `raw_payload.job-title` hoặc `title` | `raw_payload.title` | Cắt bỏ tiền tố `[HN/HCM]`, hậu tố lương `Lương 20M`. |
| **`company_name`** | `str` | `raw_payload.company` | `company` hoặc `company-name` | `raw_payload.companyName` | `company_name` hoặc `company` | `raw_payload['job-company-name']` | `raw_payload.company['name']` (làm phẳng dict) | `company-name` hoặc `company` | `raw_payload.company` | Strip khoảng trắng, chuẩn hóa tên công ty. |
| **`company_address`** | `str` (opt) | `company_address` | `addresses.full_address` | `address` hoặc `workingLocations[0].address` | Trích xuất text | `detail-row['Địa điểm làm việc']` | `company['address']` | `job_posting_jsonld.jobLocation.address` | `company_address` | Làm phẳng dict lồng nhau thành chuỗi địa chỉ. |
| **`company_scale`** | `str` (opt) | `company_scale` | `None` | `companySize` | `None` | Trích xuất text | `company['scale']` | `job_posting_jsonld.hiringOrganization` | `company_field` | Quy mô nhân sự công ty. |
| **`raw_description_text`** | `str` | `description_bullets` (nối chuỗi `\n`) | `responsibilities_original` hoặc `content` (Strip HTML) | `jobDescription` (HTML) hoặc `description_list` | `sections['Mô tả công việc']` (nối list) | `detail-row['Mô tả Công việc']` | `description` (nối mảng chuỗi) | `raw_payload.description` | `description_bullets` (nối mảng chuỗi) | Nối các đoạn văn bản/bullet thành 1 chuỗi hoàn chỉnh. |
| **`raw_requirements_text`**| `str` | `requirements_bullets` (nối chuỗi `\n`) | `requirements_original` (Strip HTML) | `jobRequirement` (HTML) hoặc `requirements_list` | `sections['Yêu cầu công việc']` (nối list) | `detail-row['Yêu Cầu Công Việc']` | `requirements` (nối mảng chuỗi) | `raw_payload.requirements` | `requirements_bullets` (nối mảng chuỗi) | Làm sạch ký tự bullet rác (`•`, `-`, `*`). |
| **`benefits_list`** | `list[str]` | `benefits_bullets` + `welfare_tags` | `benefits_original` (bóc text thẻ li) | `benefits[].benefitValue` | `sections['Tại sao bạn sẽ yêu thích...']` | `detail-row['Phúc lợi']` (tách câu) | `raw_payload.benefits` | `benefits` (tách dòng) | `benefits_bullets` | Danh sách mảng chuỗi Python `list[str]`. |
| **`skills_list`** | `list[str]` | `overview_tags['Chuyên môn']` + `required_skills` | `skills_arr` hoặc tách `skills_str` | `skills[].skillName` | `skill_tags` hoặc `specialization` | `raw_payload['job-tags']` | `raw_payload.keywords` | `skills` (tách theo `,`, `;`) | `occupations` | Danh sách kỹ năng mảng Python `list[str]`. |
| **`raw_salary_text`** | `str` | `raw_payload.salary_raw` | `salary_raw` hoặc `salary` | `prettySalary` hoặc `salaryMin - salaryMax` | `salary_display_text` (fallback JSON-LD `baseSalary`) | Bóc từ mảng chuỗi `detail-box` (cắt prefix Lương) | `raw_payload.salary` | `raw_payload.salary` | `raw_payload.salary_raw` | Chuỗi mức lương nguyên bản chưa bóc tách số. |
| **`raw_experience_text`** | `str` | `raw_payload.experience` | `requirements_arr` | `yearsOfExperience` + ' năm' | Bóc từ thân JD | Bóc từ mảng chuỗi `detail-box` (cắt prefix Kinh nghiệm)| `experience_summary` | `raw_payload.requirements` | `raw_payload.experience` | Chuỗi số năm kinh nghiệm nguyên bản. |
| **`raw_location_text`** | `str` | `raw_payload.location` | `addresses.address_region_list` (nối `, `) | `location` hoặc `workingLocations[0].cityName` | `raw_payload.work_location` | `raw_payload.map` | `location_summary` | `job_posting_jsonld.jobLocation` | `raw_payload.location` | Chuỗi địa điểm tuyển dụng nguyên bản. |
| **`raw_seniority_text`** | `str` | `general_info['Cấp bậc']` | Trích xuất từ title | `jobLevelVI` hoặc `jobLevel` | Trích xuất từ title | Bóc từ mảng chuỗi `detail-box` (cắt prefix Cấp bậc) | `general_info['level']` | `job_posting_jsonld.employmentType` | `general_info['job_level']` | Chuỗi cấp bậc nghề nghiệp nguyên bản. |
| **`raw_posted_date`** | `str` | `metadata.scraped_at` | `metadata.scraped_at` | `createdOn` hoặc `approvedOn` | `posted_at_raw` | Bóc từ `detail-box` ('Ngày cập nhật') | `general_info['posted_date']` | `job_posting_jsonld.datePosted` | `general_info['posted_date']` | Chuỗi ngày đăng tin gốc. |
| **`raw_deadline`** | `str` | `raw_payload.deadline_raw` | `recalled_at` | `expiredOn` | Bóc từ thân JD | Bóc từ `detail-box` ('Hết hạn nộp') | `raw_payload.deadline` | `job_posting_jsonld.validThrough` | `raw_payload.deadline_raw` | Chuỗi hạn nộp hồ sơ gốc. |

---

## 2. Phân Tích Đơn Biến Dữ Liệu Văn Bản (Univariate Text Profiling)

Khảo sát định lượng trên mẫu thực tế của toàn bộ 9,390 bài đăng từ 8 nguồn:

```text
+----------------------------------------------------------------------------------------------------+
|                         KẾT QUẢ ĐO LƯỜNG ĐƠN BIẾN VĂN BẢN TRÊN 8 NGUỒN CÀO                         |
+----------------------------------------------------------------------------------------------------+
| Nguồn         | Số từ JD (Mean) | Số từ Req (Mean) | Số từ Ben (Mean) | Rác HTML (%) | Thuần Anh (%)   |
+---------------+-----------------+------------------+------------------+--------------+-----------------+
| CareerViet    | 286 từ          | 235 từ           | 26 từ            | 0.0%         | 0.0% (99% Việt) |
| Glints        | 377 từ          | 17 từ (*)        | 8 từ             | 0.0%         | 2.0%            |
| ITViec        | 207 từ          | 166 từ           | 136 từ           | 0.0%         | 47.0% (Rất cao) |
| JobsGO        | 123 từ          | 92 từ            | 77 từ            | 0.0%         | 5.0%            |
| TopCV         | 148 từ          | 116 từ           | 106 từ           | 0.0%         | 0.0%            |
| TopDev        | 283 từ          | 269 từ           | 0 từ (**)        | 100.0% (***) | 8.0%            |
| Vieclam24h    | 116 từ          | 89 từ            | 102 từ           | 0.0%         | 0.0% (Gãy câu)  |
| VietnamWorks  | 53 từ (snippet) | 53 từ            | 78 từ            | 0.0%         | 17.2%           |
+---------------+-----------------+------------------+------------------+--------------+-----------------+
```
*(Ghi chú kỹ thuật):*
- `(*)` **Glints:** Trường `requirements` riêng chỉ chứa 1-2 câu tóm tắt (17 từ) vì toàn bộ yêu cầu chi tiết đã bị gộp vào bên trong trường `description` chính (377 từ).
- `(**)` **TopDev:** Trường `benefits_original` lưu dưới dạng mảng HTML object lồng nhau chưa được bóc text nên giá trị text thô trả về 0 từ.
- `(***)` **TopDev:** $100\%$ bản ghi chứa rác mã HTML inline (`<p style="font-size:14px">`, `&nbsp;`, `<span>`).

### Các Đặc Trưng Đơn Biến Then Chốt & Biện Pháp Xử Lý:
1. **Phân phối độ dài từ (Word Count Distribution):**
   - Đạt phân phối lệch phải (Right-skewed) nặng. Đa số bài đăng dao động từ $150 - 400$ từ.
   - **Xử lý bài đăng rác siêu ngắn (Stub JD < 30 từ):** Áp dụng **Chính sách 1.B (Loại bỏ hoàn toàn)** đối với các bài đăng có tổng số từ $< 30$ từ (ví dụ tin spam: *"Tuyển dev làm web gấp inbox zalo..."*) vì hoàn toàn không có giá trị khai phá kỹ năng.
2. **Độ phong phú từ vựng (Lexical Diversity — Type-Token Ratio TTR):**
   - $\text{TTR} = \frac{\text{Số từ duy nhất}}{\text{Tổng số từ}}$. Các sàn IT chuyên sâu (ITViec, TopDev) đạt TTR cao ($0.65 - 0.72$) do sử dụng nhiều thuật ngữ công nghệ chuyên biệt. Các sàn đại chúng (Vieclam24h, JobsGO) có TTR thấp ($0.45 - 0.52$) do lặp lại các mẫu câu hành chính chung chung.
3. **Hiện tượng song ngữ Anh - Việt (Bilingual Code-Switching):**
   - ITViec có tới **$47\%$ bài đăng viết 100% bằng tiếng Anh**; VietnamWorks có **$17.2\%$**.
   - **Áp dụng Chính sách 2.B:** Xây dựng module chuẩn hóa và dịch thuật tự động các phần nội dung tiếng Anh quan trọng về tiếng Việt có đối chiếu, đảm bảo tính đồng nhất cho toàn bộ kho dữ liệu.
4. **Hiện tượng rác mã HTML:**
   - TopDev có $100\%$ bài đăng dính mã thẻ HTML và CSS inline. Bắt buộc xử lý qua `HTMLCleaner` chuyên dụng để strip toàn bộ thẻ trước khi đưa vào tokenization.
5. **Hiện tượng gãy câu Bullet (Bullet Fragmentation ở Vieclam24h):**
   - DOM selector cắt vụn câu thành từng từ rời rạc. Cần xử lý qua thuật toán ghép câu `BulletStitcher`.

---

## 3. Phân Tích Đa Biến Dữ Liệu Văn Bản (Multivariate Text Interactions)

Khai phá mối quan hệ tương hỗ giữa các đặc trưng văn bản với mức lương, cấp bậc và kỹ năng:

```text
+----------------------------------------------------------------------------------------------------+
|                         CÁC PHÁT HIỆN TƯƠNG QUAN ĐA BIẾN QUAN TRỌNG                                |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [PHÁT HIỆN 1: TƯƠNG QUAN ĐỘ DÀI VĂN BẢN (JD WORD COUNT) VS MỨC LƯƠNG TỐI ĐA]                      |
|  * Hệ số tương quan Pearson r = +0.28; Spearman rho = +0.34 (Tương quan dương đơn điệu).           |
|  * Ý nghĩa: Các bài đăng có JD viết chi tiết, rõ ràng (từ 250 - 500 từ) có mức lương trung vị     |
|    cao hơn 45% so với các bài đăng viết hời hợt (< 100 từ). Tuy nhiên khi JD quá dài (> 800 từ),  |
|    mức lương đi ngang do văn bản bị loãng bởi quy chế hành chính.                                  |
|                                                                                                    |
|  [PHÁT HIỆN 2: PHÂN TẦNG TỪ KHÓA TRÁCH NHIỆM THEO CẤP BẬC NGHỀ NGHIỆP (SENIORITY)]                 |
|  * Bậc Intern / Fresher: Từ khóa chiếm ưu thế tuyệt đối là: 'học hỏi', 'đào tạo', 'nhiệt huyết',    |
|    'sinh viên', 'nắm vững nền tảng', 'hỗ trợ team'.                                                |
|  * Bậc Middle: 'chịu trách nhiệm', 'độc lập giải quyết', 'tối ưu mã nguồn', 'kinh nghiệm 2-3 năm'. |
|  * Bậc Senior: 'thiết kế kiến trúc (architecture)', 'chịu tải cao (high concurrency)', 'microservices'. |
|  * Bậc Lead / Manager: 'dẫn dắt đội ngũ (mentorship)', 'chiến lược kỹ thuật', 'quản lý tiến độ'.   |
|                                                                                                    |
|  [PHÁT HIỆN 3: ĐỒNG XUẤT HIỆN KỸ NĂNG TRONG REQUIREMENT & THẶNG DƯ LƯƠNG (SALARY PREMIUM)]         |
|  * Nhóm kỹ năng cơ bản đơn lẻ: Chỉ yêu cầu `PHP` hoặc `HTML/CSS` -> Lương trung vị: 15 - 18 triệu.  |
|  * Nhóm kỹ năng kết hợp (Co-occurrence Cluster): `Backend` (Java/Go/NodeJS) + `Cloud` (AWS/Docker) |
|    + `System Design` -> Mức lương trung vị vọt lên 35 - 45 triệu VNĐ (Thặng dư +110%).             |
|                                                                                                    |
|  [PHÁT HIỆN 4: MA TRẬN NHIỆT TƯƠNG QUAN 6 BIẾN (CORRELATION HEATMAP)]                              |
|  * `req_word_count` tương quan mạnh nhất với `skills_count` (r = +0.51) và `min_exp` (r = +0.42).  |
|  * `benefits_count` tương quan mạnh với `company_scale` (Công ty lớn có phúc lợi phong phú hơn).    |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

---

## 4. Bảng Chẩn Đoán Đối Chiếu Tập Trung 8 Nguồn (Single Consolidated Matrix)

Thay vì tạo 8 file mô tả riêng lẻ, toàn bộ vấn đề kỹ thuật và chiến lược xử lý của 8 sàn được tổng hợp đối chiếu tập trung tại bảng sau:

| Nguồn Tuyển Dụng | Quy Mô (Records) | Vấn Đề Kỹ Thuật Văn Bản Lớn Nhất | Nguyên Nhân Căn Cốt (WHY) | Giải Pháp Tiền Xử Lý Kết Hợp (HOW) |
| :--- | :--- | :--- | :--- | :--- |
| **TopDev** | 2,758 | **$100\%$ rác mã HTML** trong content; trùng lặp trường `title` vs `job-title`. | Dữ liệu trả về từ REST API dạng Rich Text Editor lưu trữ nguyên văn thẻ HTML web. | Áp dụng `HTMLCleaner` bóc sạch thẻ; hợp nhất khóa trùng; bóc tách `skills_arr`. |
| **TopCV** | 1,717 | Tags bị phân tán thành 3 nhóm lồng nhau trong `overview_tags`. | Thiết kế giao diện TopCV chia rõ 3 box: Yêu cầu, Quyền lợi, Chuyên môn. | Làm phẳng 3 nhóm tags; hợp nhất `overview_tags['Chuyên môn']` + `required_skills` $\rightarrow$ `skills_list`. |
| **JobsGO** | 1,520 | Mức lương ghi có chữ `triệu VNĐ`; occupations vừa là ngành vừa là kỹ năng. | Định dạng form nhập liệu tiếng Việt tự do của sàn di động. | Regex chuẩn hóa dải số lương; bóc tách `general_info` thành các cột phẳng độc lập. |
| **VietnamWorks** | 1,154 | Giấu lương bằng **`salary=0`**; mô tả trong search hit bị cắt ngắn (snippet). | Cơ chế mã hóa backend ngụy trang tin thỏa thuận; API tìm kiếm chỉ trả tóm tắt. | Bóc trần `salary=0` thành `NaN` và bật `is_negotiable=1`; bóc mảng dict `skills[].skillName`. |
| **ITViec** | 692 | **$47\%$ thuần tiếng Anh**; che giấu lương trên web bằng *"Đăng nhập để xem"*. | Sàn IT cao cấp dùng paywall/login-wall; đối tượng phục vụ là doanh nghiệp nước ngoài. | Khai thác backdoor JSON-LD `baseSalary`; quy đổi USD sang VND; dịch chuẩn hóa tiếng Việt (Chính sách 2.B). |
| **Vieclam24h** | 619 | **Đứt gãy câu bullet** (câu bị cắt vụn); dict `company` lồng nhau. | DOM parser bắt từng thẻ con rời rạc; cấu trúc lưu trữ công ty dạng dictionary. | Áp dụng thuật toán ghép câu `BulletStitcher`; làm phẳng dict `company` thành `company_name`, `company_address`. |
| **CareerViet** | 599 | **Nhét tất cả vào mảng `detail-box`**; lặp lại các dòng dữ liệu giống nhau. | Kiến trúc template cũ lưu danh sách thuộc tính dưới dạng list chuỗi phẳng. | Viết bộ bóc tách regex phân rã `detail-box` thành các cột phẳng độc lập; khử trùng lặp dòng. |
| **Glints** | 331 | **Tách rời yêu cầu**: trường req chỉ có 17 từ, dồn hết vào description. | Giao diện Glints ưu tiên 1 vùng nhập mô tả lớn duy nhất cho nhà tuyển dụng. | Sử dụng GenAI đọc `description` bóc tách lại phần Requirements và Skills riêng biệt. |

---

## 5. Ma Trận Phân Bổ Công Việc (Work Breakdown Structure — WBS)

Bảng phân chia trách nhiệm cụ thể giúp định vị rõ ràng phần việc nào sẽ được xử lý ở giai đoạn nào trong pipeline:

```text
+----------------------------------------------------------------------------------------------------+
|                         MA TRẬN PHÂN BỔ TRÁCH NHIỆM THEO 4 GIAI ĐOẠN                               |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [BƯỚC 1: INTEGRATION (Schema Mapping & Flattening)]                                               |
|  - Trách nhiệm: Module `preprocessing/integration/json_flattener.py`                               |
|  - Nhiệm vụ:                                                                                       |
|    1. Bóc tách và ép phẳng 100% các trường theo Bảng Khai Báo Ánh Xạ tại Mục 1.                  |
|    2. Gom danh sách kỹ năng thành mảng Python `skills_list` (list[str]).                           |
|    3. Gom danh sách quyền lợi thành mảng Python `benefits_list` (list[str]).                       |
|    4. Làm phẳng dict lồng nhau (company, overview_tags, jsonld) thành cột phẳng.                   |
|                                                                                                    |
|  [BƯỚC 2: TRANSFORMATION (Parsing, Typing & Text Cleaning)]                                        |
|  - Trách nhiệm: Các module trong `preprocessing/transformation/`                                   |
|  - Nhiệm vụ:                                                                                       |
|    1. `html_cleaner.py`: Strip sạch mã rác HTML và CSS inline của TopDev.                          |
|    2. `bullet_stitcher.py`: Nối các câu bullet bị phân mảnh đứt đoạn của Vieclam24h.               |
|    3. `text_metrics.py`: Tính `jd_word_count`, `req_word_count`, `bullet_count`, `TTR`.           |
|    4. `salary_parser.py`: Cascade Regex bóc tách lương header và lương ẩn trong JD.                |
|    5. Quy đổi tỷ giá USD sang VND (25,400) và quy đổi lương năm sang tháng (/12).                  |
|                                                                                                    |
|  [BƯỚC 3: MISSING & OUTLIER HANDLING (Cleansing & GenAI Imputation)]                               |
|  - Trách nhiệm: Các module trong `preprocessing/missing_outlier/`                                  |
|  - Nhiệm vụ:                                                                                       |
|    1. `sneaky_null_detector.py`: Bóc trần 9+ null markers trá hình ('thỏa thuận', '0', '[]').      |
|    2. **Chính sách 1.B:** Loại bỏ hoàn toàn các bài đăng rác siêu ngắn (Stub JD < 30 từ).          |
|    3. `genai_text_imputer.py`: Dùng Gemini 1.5 Flash đọc JD bù khuyết kinh nghiệm, level, city.   |
|    4. `outlier_handler.py`: Phát hiện 3 lỗi nhập liệu số bằng IQR và Winsorization (capping 1%-99%).|
|                                                                                                    |
|  [BƯỚC 4: NORMALIZATION & TAXONOMY (Scaling, Translation & Mapping)]                               |
|  - Trách nhiệm: Các module trong `preprocessing/normalization/`                                    |
|  - Nhiệm vụ:                                                                                       |
|    1. **Chính sách 2.B:** Chuẩn hóa dịch thuật nội dung tiếng Anh về tiếng Việt đồng nhất.         |
|    2. `log_transformer.py`: Biến đổi Log-transformation $y = \log(1 + \text{salary})$.             |
|    3. `text_cleaner.py`: Cắt bỏ tag rác ở title, chuẩn hóa 63 tỉnh thành, 6 bậc Seniority.       |
|    4. Zero-shot Classification phân loại chức danh về 12 Job Family chuẩn (SD2).                   |
|    5. Mapping kỹ năng về Taxonomy ESCO quốc tế qua Embedding Cosine Similarity >= 0.88 (SD3).      |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```
