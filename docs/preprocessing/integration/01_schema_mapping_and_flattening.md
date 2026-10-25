# BƯỚC 1: TÍCH HỢP SCHEMA & ÉP PHẲNG JSON (SCHEMA MAPPING & JSON FLATTENING)

> **Tài liệu quy chuẩn số 01 (Preprocessing Core Document 01 — Step 1: Integration)**  
> **Dự án:** Phân tích thị trường lao động IT và nhu cầu kỹ năng nghề nghiệp tại Việt Nam (**VN-IT-Job-Mining**)  
> **Nhiệm vụ:** Gom toàn bộ dữ liệu dị thể từ 8 sàn về một bảng phẳng duy nhất (Single Flat Table / Wide DataFrame) chuẩn mực, loại bỏ cấu trúc JSON lồng nhau phức tạp.

---

## 1. Mục Đích & Ranh Giới Bước 1 (Integration)

```text
+----------------------------------------------------------------------------------------------------+
|                         RANH GIỚI BẮT BUỘC CỦA BƯỚC 1 (DATA INTEGRATION)                           |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [ĐẦU VÀO - INPUT]:                                                                                |
|  - 9,390 tệp JSON thô nguyên bản (RawJobEnvelope: metadata + raw_payload) từ 8 sàn.                |
|                                                                                                    |
|  [ĐƯỢC PHÉP LÀM (DO)]:                                                                             |
|  1. Đọc và giải mã payload thô.                                                                    |
|  2. Ánh xạ các trường có tên khác nhau về tên cột chuẩn chung (Schema Mapping).                   |
|  3. Ép phẳng (Flattening) các dictionary lồng nhau, mảng hỗn hợp, JSON-LD về các cột phẳng.        |
|  4. Gom danh sách kỹ năng thành cột mảng Python `skills_list` (list[str]).                         |
|  5. Gom danh sách quyền lợi thành cột mảng Python `benefits_list` (list[str]).                     |
|  6. Sinh khóa định danh duy nhất toàn hệ thống: `job_id_global = "<source>_<source_job_id>"`.     |
|                                                                                                    |
|  [TUYỆT ĐỐI CẤM (DO NOT DO)]:                                                                      |
|  - CẤM bóc tách dải số min, max của mức lương (để dành cho Bước 2: Transformation).                |
|  - CẤM quy đổi ngoại tệ USD sang VND (để dành cho Bước 2).                                         |
|  - CẤM xóa bỏ bất kỳ dòng dữ liệu nào (Không drop records).                                       |
|  - CẤM điền giá trị khuyết thiếu (Không fillna).                                                   |
|  - CẤM chia nhỏ thành các bảng SQL quan hệ phức tạp (DIM/FACT) - giữ nguyên bảng phẳng.            |
|                                                                                                    |
|  [ĐẦU RA - OUTPUT]:                                                                                |
|  - Một Bảng Phẳng Duy Nhất (Single Flat DataFrame / Staging Parquet).                              |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. Bảng Từ Điển Ánh Xạ Đa Nguồn Về Bảng Phẳng (Field Mapping Matrix)

Bảng đối chiếu cách lấy dữ liệu từ trường gốc của 8 sàn đưa về cột phẳng chuẩn:

| Cột Phẳng Chuẩn (Canonical Column) | Kiểu Dữ Liệu | TopCV | TopDev | VietnamWorks | ITViec | CareerViet | Vieclam24h | Glints | JobsGO |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `job_id_global` | `str` | `topcv_{id}` | `topdev_{id}` | `vnw_{id}` | `itviec_{id}` | `careerviet_{id}` | `24h_{id}` | `glints_{id}` | `jobsgo_{id}` |
| `source_platform` | `str` | `'topcv'` | `'topdev'` | `'vietnamworks'`| `'itviec'` | `'careerviet'` | `'vieclam24h'` | `'glints'` | `'jobsgo'` |
| `job_title` | `str` | `title` | `title` / `job-title` | `jobTitle` / `title` | `title` | `title` | `title` | `job-title` | `title` |
| `company_name` | `str` | `company` | `company` / `company-name` | `companyName` | `company_name` | `job-company-name` | `company.name` | `company-name` | `company` |
| `raw_salary_text` | `str` | `salary_raw` | `salary_raw` / `salary` | `prettySalary` / `salary_raw` | `salary_display_text` | Parse từ `detail-box` | `salary` | `salary` | `salary_raw` |
| `raw_experience_text` | `str` | `experience` | `requirements_arr` | `yearsOfExperience` | Bóc từ JD | Parse từ `detail-box` | `experience_summary` | `requirements` | `experience` |
| `raw_location_text` | `str` | `location` | `addresses[0]` | `workingLocations[0]` | `work_location` | `map` | `location_summary` | `jsonld.jobLocation` | `location` |
| `raw_seniority_text` | `str` | `general_info['Cấp bậc']` | Bóc từ title | `jobLevelVI` / `jobLevel` | Bóc từ title | Parse từ `detail-box` | `general_info.level` | `jsonld.employmentType` | `general_info.job_level` |
| `skills_list` | `list[str]`| `required_skills` / `Chuyên môn` | `skills_arr` | `skills[].skillName` | `skill_tags` | `job-tags` | `keywords` | `skills` | Bóc từ occupations |
| `benefits_list` | `list[str]`| `benefits_bullets` / `welfare_tags`| `benefits_original` | `benefits[].benefitValue` | `sections['Phúc lợi']` | `detail-row['Phúc lợi']`| `benefits` | `benefits` | `benefits_bullets` |
| `raw_description_text` | `str` | `description_bullets` | `content` (HTML) | `jobDescription` | `sections['Mô tả']` | `detail-row['Mô tả']` | `description` | `description` | `description_bullets` |
| `raw_requirements_text`| `str` | `requirements_bullets`| `requirements_original`| `jobRequirement` | `sections['Yêu cầu']`| `detail-row['Yêu cầu']`| `requirements` | `requirements` | `requirements_bullets` |
| `raw_posted_date` | `str` | `crawled_at` | `crawled_at` | `createdOn` | `posted_at_raw` | Parse từ `detail-box` | `general_info.posted_date` | `jsonld.datePosted` | `general_info.posted_date` |
| `raw_deadline` | `str` | `deadline_raw` | `recalled_at` | `expiredOn` | Bóc từ text | Parse từ `detail-box` | `deadline` | `jsonld.validThrough`| `deadline_raw` |

---

## 3. Công Thức Ép Phẳng (Flattening Recipes) Từng Nguồn Dị Cấu Trúc

### 3.1. CareerViet: Ép Phẳng Mảng Chuỗi Hỗn Hợp (`detail-box`)
- **Hiện trạng:** CareerViet lưu tất cả các thông tin cốt lõi (Lương, Hạn nộp, Cấp bậc, Kinh nghiệm) vào một mảng chuỗi duy nhất:
  ```json
  [
    "Ngày cập nhật 16/10/2026",
    "Ngành nghề Ngân hàng , CNTT - Phần mềm",
    "Hình thức Nhân viên chính thức",
    "Lương Cạnh tranh",
    "Kinh nghiệm 4 - 5 Năm",
    "Cấp bậc Nhân viên",
    "Hết hạn nộp 30/11/2026"
  ]
  ```
- **Kỹ thuật ép phẳng:** Quét qua từng phần tử của mảng và bóc tách thành các cột phẳng độc lập:
  - Nếu bắt đầu bằng `"Lương"` $\rightarrow$ Cắt prefix `"Lương"` lấy chuỗi giá trị gán vào `raw_salary_text`.
  - Nếu bắt đầu bằng `"Kinh nghiệm"` $\rightarrow$ Cắt prefix gán vào `raw_experience_text`.
  - Nếu bắt đầu bằng `"Cấp bậc"` $\rightarrow$ Cắt prefix gán vào `raw_seniority_text`.
  - Nếu bắt đầu bằng `"Hết hạn nộp"` $\rightarrow$ Cắt prefix gán vào `raw_deadline`.

### 3.2. Glints & ITViec: Bóc Tách Kho Báu JSON-LD (`job_posting_jsonld`)
- **Hiện trạng:** ITViec và Glints che giấu mức lương trên giao diện web (`"Đăng nhập để xem mức lương"` hoặc `"Công ty không công khai"`), nhưng trong payload lại chứa cấu trúc `job_posting_jsonld` chuẩn Google Schema.org.
- **Kỹ thuật ép phẳng:**
  - `job_posting_jsonld.get("baseSalary", {}).get("value", {}).get("value")` $\rightarrow$ gán vào `jsonld_salary_text`.
  - `job_posting_jsonld.get("jobLocation", {}).get("address", {}).get("addressLocality")` $\rightarrow$ gán vào `raw_location_text`.
  - `job_posting_jsonld.get("datePosted")` $\rightarrow$ gán vào `raw_posted_date`.

### 3.3. TopCV: Ép Phẳng Dictionary Phân Nhóm Thẻ (`overview_tags`)
- **Hiện trạng:** TopCV chia thẻ tag thành 3 nhóm lồng nhau:
  ```json
  "overview_tags": {
    "Yêu cầu": ["1 năm", "Đại học"],
    "Quyền lợi": ["Thưởng dự án", "Bảo hiểm PVI"],
    "Chuyên môn": ["Mobile App", "Marketing", "Game"]
  }
  ```
- **Kỹ thuật ép phẳng:** Tách trực tiếp thành 3 cột mảng phẳng:
  - `tag_requirements = overview_tags.get("Yêu cầu", [])`
  - `tag_benefits = overview_tags.get("Quyền lợi", [])`
  - `skills_list = overview_tags.get("Chuyên môn", []) + required_skills` (hợp nhất và khử trùng lặp).

### 3.4. Vieclam24h: Làm Phẳng Dictionary Công Ty Lồng Nhau (`company`)
- **Hiện trạng:** Trường `company` là một dict chứa: `{"name": "...", "scale": "...", "field": "...", "address": "..."}`.
- **Kỹ thuật ép phẳng:** Bóc tách trực tiếp:
  - `company_name = company.get("name")`
  - `company_scale = company.get("scale")`
  - `company_address = company.get("address")`

---

## 4. Đặc Tả Dữ Liệu Đầu Ra Của Bước 1 (Canonical Staging Schema)

Kết thúc bước 1, toàn bộ 8 nguồn được lưu trữ tại tầng Staging (`r2://vn-it-jobs/staging/staging_flat_jobs.parquet`) với cấu trúc phẳng hoàn toàn:

```text
+----------------------------------------------------------------------------------------------------+
|                         CẤU TRÚC BẢNG PHẲNG STAGING (CANONICAL STAGING SCHEMA)                     |
+----------------------------------------------------------------------------------------------------+
| Tên Cột                  | Kiểu Dữ Liệu | Ý Nghĩa                                                  |
+--------------------------+--------------+----------------------------------------------------------+
| job_id_global            | string (PK)  | Mã định danh duy nhất (ví dụ: 'topcv_2324170')           |
| source_platform          | string       | Nguồn cào ('topcv', 'itviec', 'careerviet'...)           |
| source_job_id            | string       | ID gốc của bài tuyển dụng trên website                    |
| source_url               | string       | URL chi tiết bài đăng (đã làm sạch query params)         |
| job_title                | string       | Tiêu đề vị trí tuyển dụng                                |
| company_name             | string       | Tên công ty tuyển dụng                                   |
| company_address          | string (opt) | Địa chỉ trụ sở / văn phòng công ty                       |
| raw_salary_text          | string       | Chuỗi lương nguyên bản (chưa parse số)                    |
| raw_experience_text      | string       | Chuỗi kinh nghiệm nguyên bản                             |
| raw_location_text        | string       | Chuỗi địa điểm nguyên bản                                 |
| raw_seniority_text       | string (opt) | Chuỗi cấp bậc nguyên bản                                 |
| skills_list              | list[string] | Mảng danh sách kỹ năng bóc tách từ tags                  |
| benefits_list            | list[string] | Mảng danh sách quyền lợi đãi ngộ                         |
| raw_description_text     | string       | Văn bản mô tả công việc (đã nối bullets thành chuỗi)     |
| raw_requirements_text    | string       | Văn bản yêu cầu ứng viên                                 |
| raw_posted_date          | string       | Chuỗi ngày đăng tin gốc                                  |
| raw_deadline             | string (opt) | Chuỗi hạn nộp hồ sơ gốc                                  |
| crawled_at               | timestamp    | Thời điểm hệ thống thu thập                              |
+----------------------------------------------------------------------------------------------------+
```
